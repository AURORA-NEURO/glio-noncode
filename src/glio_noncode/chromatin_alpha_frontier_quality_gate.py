"""Quality gate for the public chromatin-alpha release tranche."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_alpha_frontier_fixture_eval import ChromatinAlphaFrontierEvaluation
from .chromatin_alpha_frontier_metrics import ChromatinAlphaFrontierMetrics
from .chromatin_alpha_frontier_public_data import (
    ChromatinAlphaFrontierFixture,
    ChromatinAlphaFrontierOperation,
)
from .chromatin_alpha_frontier_reconciliation import ChromatinAlphaFrontierReconciliation
from .chromatin_alpha_frontier_schema import ChromatinAlphaFrontierSchemaReport
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierQualityCheck:
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
class ChromatinAlphaFrontierQualityReport:
    checks: tuple[ChromatinAlphaFrontierQualityCheck, ...]
    accepted: bool
    passed_count: int
    failed_check_ids: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.checks:
            raise ValidationError("quality report requires checks")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_chromatin_alpha_frontier_quality(
    fixture: ChromatinAlphaFrontierFixture,
    data: Any,
    schema: ChromatinAlphaFrontierSchemaReport,
    evaluation: ChromatinAlphaFrontierEvaluation,
    metrics: ChromatinAlphaFrontierMetrics,
    reconciliation: ChromatinAlphaFrontierReconciliation,
) -> ChromatinAlphaFrontierQualityReport:
    checks = (
        ChromatinAlphaFrontierQualityCheck(
            "data_audit", data.accepted, "error", "public data audit passes"
        ),
        ChromatinAlphaFrontierQualityCheck(
            "schema", schema.accepted, "error", "schema and boundary checks pass"
        ),
        ChromatinAlphaFrontierQualityCheck(
            "fixture_identity", bool(fixture.fixture_id), "error", "fixture identity is present"
        ),
        ChromatinAlphaFrontierQualityCheck(
            "fixture_version", bool(fixture.fixture_version), "error", "fixture version is present"
        ),
        ChromatinAlphaFrontierQualityCheck(
            "positive_count",
            len(fixture.positive_records) == 4,
            "error",
            "four positive rows are retained",
        ),
        ChromatinAlphaFrontierQualityCheck(
            "control_count",
            len(fixture.control_records) == 12,
            "error",
            "twelve controls are retained",
        ),
        ChromatinAlphaFrontierQualityCheck(
            "operation_balance",
            all(
                len(fixture.operation_records(operation)) == 4
                for operation in ChromatinAlphaFrontierOperation
            ),
            "error",
            "each operation has four rows",
        ),
        ChromatinAlphaFrontierQualityCheck(
            "evaluation", evaluation.accepted, "error", "all expected paths evaluate"
        ),
        ChromatinAlphaFrontierQualityCheck(
            "state_matches", evaluation.state_match_count == 16, "error", "all states match"
        ),
        ChromatinAlphaFrontierQualityCheck(
            "issue_matches", evaluation.issue_match_count == 16, "error", "all issue floors match"
        ),
        ChromatinAlphaFrontierQualityCheck(
            "metrics", metrics.accepted, "error", "release metrics meet floors"
        ),
        ChromatinAlphaFrontierQualityCheck(
            "reconciliation",
            reconciliation.accepted,
            "error",
            "expected and observed paths reconcile",
        ),
        ChromatinAlphaFrontierQualityCheck(
            "result_receipts",
            all(item.adapter.content_address.startswith("sha256:") for item in evaluation.records),
            "error",
            "result receipts are present",
        ),
        ChromatinAlphaFrontierQualityCheck(
            "source_receipts",
            all(source.content_address.startswith("sha256:") for source in fixture.sources),
            "error",
            "source receipts are present",
        ),
        ChromatinAlphaFrontierQualityCheck(
            "positive_states",
            all(
                item.observed_state == "supported"
                for item in evaluation.records
                if item.role == "positive"
            ),
            "error",
            "positive paths are supported",
        ),
        ChromatinAlphaFrontierQualityCheck(
            "out_of_domain_control",
            any(
                item.observed_state == "out_of_domain"
                for item in evaluation.records
                if item.role == "control"
            ),
            "warning",
            "foreign context control is visible",
        ),
        ChromatinAlphaFrontierQualityCheck(
            "ambiguous_control",
            any(
                item.observed_state == "ambiguous"
                for item in evaluation.records
                if item.role == "control"
            ),
            "warning",
            "mixed signal control is visible",
        ),
        ChromatinAlphaFrontierQualityCheck(
            "partial_control",
            any(
                item.observed_state == "partial"
                for item in evaluation.records
                if item.role == "control"
            ),
            "warning",
            "partial control is visible",
        ),
        ChromatinAlphaFrontierQualityCheck(
            "invalid_control",
            any(
                item.observed_state == "partial" and item.observed_issue_codes
                for item in evaluation.records
                if item.role == "control"
            ),
            "warning",
            "invalid-row control is visible",
        ),
        ChromatinAlphaFrontierQualityCheck(
            "segmentation_path",
            any(
                item.operation == ChromatinAlphaFrontierOperation.SEGMENTATION.value
                and item.observed_state == "supported"
                for item in evaluation.records
            ),
            "error",
            "segmentation support is represented",
        ),
        ChromatinAlphaFrontierQualityCheck(
            "allele_path",
            any(
                item.operation == ChromatinAlphaFrontierOperation.ALLELE_SPECIFIC.value
                and item.observed_state == "supported"
                for item in evaluation.records
            ),
            "error",
            "allele-specific support is represented",
        ),
        ChromatinAlphaFrontierQualityCheck(
            "purity_path",
            any(
                item.operation == ChromatinAlphaFrontierOperation.PURITY.value
                and item.observed_state == "supported"
                for item in evaluation.records
            ),
            "error",
            "purity support is represented",
        ),
        ChromatinAlphaFrontierQualityCheck(
            "composition_path",
            any(
                item.operation == ChromatinAlphaFrontierOperation.COMPOSITION_CORRECTION.value
                and item.observed_state == "supported"
                for item in evaluation.records
            ),
            "error",
            "composition correction support is represented",
        ),
        ChromatinAlphaFrontierQualityCheck(
            "context_lock",
            all(record.context_key == fixture.context_key for record in fixture.records),
            "error",
            "context key is locked",
        ),
        ChromatinAlphaFrontierQualityCheck(
            "boundary",
            fixture.evidence_boundary == "public_aggregate_non_patient",
            "error",
            "aggregate boundary is locked",
        ),
        ChromatinAlphaFrontierQualityCheck(
            "warnings",
            all(item.adapter.warnings for item in evaluation.records),
            "warning",
            "primitive limitations remain visible",
        ),
    )
    failed = tuple(
        check.check_id for check in checks if not check.passed and check.severity == "error"
    )
    return ChromatinAlphaFrontierQualityReport(
        checks, not failed, sum(check.passed for check in checks), failed
    )


__all__ = [
    "ChromatinAlphaFrontierQualityCheck",
    "ChromatinAlphaFrontierQualityReport",
    "build_chromatin_alpha_frontier_quality",
]
