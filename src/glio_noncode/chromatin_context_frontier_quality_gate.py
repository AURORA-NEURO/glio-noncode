"""Strict quality gate for the C01-C04 release candidate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_context_frontier_fixture_eval import ChromatinContextFrontierEvaluation
from .chromatin_context_frontier_metrics import ChromatinContextFrontierMetrics
from .chromatin_context_frontier_public_data import (
    CHROMATIN_CONTEXT_FRONTIER_BOUNDARY,
    ChromatinContextFrontierFixture,
    ChromatinContextFrontierOperation,
)
from .chromatin_context_frontier_reconciliation import ChromatinContextFrontierReconciliation
from .chromatin_context_frontier_schema import ChromatinContextFrontierSchemaReport
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierQualityCheck:
    check_id: str
    passed: bool
    severity: str
    detail: str
    observed: Any = None
    required: Any = None
    content_address: str = ""

    def __post_init__(self) -> None:
        if (
            not self.check_id
            or not self.detail
            or self.severity not in {"info", "warning", "error"}
        ):
            raise ValidationError("quality check is invalid")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierQualityReport:
    checks: tuple[ChromatinContextFrontierQualityCheck, ...]
    accepted: bool
    passed_count: int
    failed_check_ids: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.checks:
            raise ValidationError("quality report requires checks")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def warning_count(self) -> int:
        return sum(item.severity == "warning" and not item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"warning_count": self.warning_count}


def build_chromatin_context_frontier_quality(
    fixture: ChromatinContextFrontierFixture,
    data: Any,
    schema: ChromatinContextFrontierSchemaReport,
    evaluation: ChromatinContextFrontierEvaluation,
    metrics: ChromatinContextFrontierMetrics,
    reconciliation: ChromatinContextFrontierReconciliation,
) -> ChromatinContextFrontierQualityReport:
    checks = (
        ChromatinContextFrontierQualityCheck(
            "data_audit", data.accepted, "error", "public aggregate data audit passes"
        ),
        ChromatinContextFrontierQualityCheck(
            "schema", schema.accepted, "error", "schema and boundary checks pass"
        ),
        ChromatinContextFrontierQualityCheck(
            "fixture_identity", bool(fixture.fixture_id), "error", "fixture identity is present"
        ),
        ChromatinContextFrontierQualityCheck(
            "fixture_version", bool(fixture.fixture_version), "error", "fixture version is present"
        ),
        ChromatinContextFrontierQualityCheck(
            "source_count",
            len(fixture.sources) == 5,
            "error",
            "five source receipts are present",
            len(fixture.sources),
            5,
        ),
        ChromatinContextFrontierQualityCheck(
            "record_count",
            len(fixture.records) == 16,
            "error",
            "sixteen records are present",
            len(fixture.records),
            16,
        ),
        ChromatinContextFrontierQualityCheck(
            "positive_count",
            len(fixture.positive_records) == 4,
            "error",
            "four positive rows are present",
        ),
        ChromatinContextFrontierQualityCheck(
            "control_count",
            len(fixture.control_records) == 12,
            "error",
            "twelve control rows are present",
        ),
        ChromatinContextFrontierQualityCheck(
            "operation_balance",
            all(
                len(fixture.operation_records(item)) == 4
                for item in ChromatinContextFrontierOperation
            ),
            "error",
            "each operation has four rows",
        ),
        ChromatinContextFrontierQualityCheck(
            "evaluation", evaluation.accepted, "error", "all fixture paths evaluate"
        ),
        ChromatinContextFrontierQualityCheck(
            "state_matches",
            evaluation.state_match_count == 16,
            "error",
            "all expected states match",
            evaluation.state_match_count,
            16,
        ),
        ChromatinContextFrontierQualityCheck(
            "issue_matches",
            evaluation.issue_match_count == 16,
            "error",
            "all expected issue floors match",
            evaluation.issue_match_count,
            16,
        ),
        ChromatinContextFrontierQualityCheck(
            "metrics", metrics.accepted, "error", "release metrics meet floors"
        ),
        ChromatinContextFrontierQualityCheck(
            "reconciliation",
            reconciliation.accepted,
            "error",
            "expected and observed rows reconcile",
        ),
        ChromatinContextFrontierQualityCheck(
            "receipt_rate",
            all(item.adapter.content_address.startswith("sha256:") for item in evaluation.records),
            "error",
            "adapter results have receipts",
        ),
        ChromatinContextFrontierQualityCheck(
            "source_receipts",
            all(item.content_address.startswith("sha256:") for item in fixture.sources),
            "error",
            "source receipts have addresses",
        ),
        ChromatinContextFrontierQualityCheck(
            "positive_states",
            all(item.observed_state == "supported" for item in evaluation.positive_rows),
            "error",
            "positive paths are supported",
        ),
        ChromatinContextFrontierQualityCheck(
            "out_domain_control",
            any(item.observed_state == "out_of_domain" for item in evaluation.control_rows),
            "warning",
            "foreign-context control is visible",
        ),
        ChromatinContextFrontierQualityCheck(
            "ambiguous_control",
            any(item.observed_state == "ambiguous" for item in evaluation.control_rows),
            "warning",
            "replicate ambiguity is visible",
        ),
        ChromatinContextFrontierQualityCheck(
            "partial_control",
            any(item.observed_state == "partial" for item in evaluation.control_rows),
            "warning",
            "malformed-row partial state is visible",
        ),
        ChromatinContextFrontierQualityCheck(
            "abstention_control",
            any(item.observed_state == "abstained" for item in evaluation.control_rows),
            "warning",
            "missing-measurement abstention is visible",
        ),
        ChromatinContextFrontierQualityCheck(
            "track_operation",
            any(
                item.operation == ChromatinContextFrontierOperation.TRACK_RETRIEVAL.value
                and item.observed_state == "supported"
                for item in evaluation.records
            ),
            "error",
            "track retrieval is supported",
        ),
        ChromatinContextFrontierQualityCheck(
            "delta_operation",
            any(
                item.operation == ChromatinContextFrontierOperation.ACCESSIBILITY_DELTA.value
                and item.observed_state == "supported"
                for item in evaluation.records
            ),
            "error",
            "accessibility delta is supported",
        ),
        ChromatinContextFrontierQualityCheck(
            "histone_operation",
            any(
                item.operation == ChromatinContextFrontierOperation.HISTONE_CONTEXT.value
                and item.observed_state == "supported"
                for item in evaluation.records
            ),
            "error",
            "histone context is supported",
        ),
        ChromatinContextFrontierQualityCheck(
            "h3k27ac_operation",
            any(
                item.operation == ChromatinContextFrontierOperation.H3K27AC_ACTIVITY.value
                and item.observed_state == "supported"
                for item in evaluation.records
            ),
            "error",
            "H3K27ac observation is supported",
        ),
        ChromatinContextFrontierQualityCheck(
            "aggregate_boundary",
            fixture.evidence_boundary == CHROMATIN_CONTEXT_FRONTIER_BOUNDARY,
            "error",
            "aggregate boundary is locked",
        ),
        ChromatinContextFrontierQualityCheck(
            "context_lock",
            all(item.context_key == fixture.context_key for item in fixture.records),
            "error",
            "context keys are locked",
        ),
        ChromatinContextFrontierQualityCheck(
            "limitations",
            all(item.adapter.warnings for item in evaluation.records),
            "warning",
            "limitations are visible on every result",
        ),
        ChromatinContextFrontierQualityCheck(
            "no_subject_keys",
            all(
                not {str(key).lower() for key in item.record.payload}
                & {"patient", "subject", "sample_id", "donor_id", "participant_id", "individual_id"}
                for item in evaluation.records
            ),
            "error",
            "payloads remain aggregate-shaped",
        ),
    )
    failed = tuple(item.check_id for item in checks if not item.passed and item.severity == "error")
    return ChromatinContextFrontierQualityReport(
        checks, not failed, sum(item.passed for item in checks), failed
    )


__all__ = [
    "ChromatinContextFrontierQualityCheck",
    "ChromatinContextFrontierQualityReport",
    "build_chromatin_context_frontier_quality",
]
