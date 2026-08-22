"""Quality gate with explicit checks for the aggregate release slice."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_regulation_frontier_fixture_eval import SequenceRegulationEvaluation
from .sequence_regulation_frontier_metrics import SequenceRegulationMetrics
from .sequence_regulation_frontier_public_data import (
    SequenceRegulationDataAudit,
    SequenceRegulationFixture,
)
from .sequence_regulation_frontier_reconciliation import SequenceRegulationReconciliation
from .sequence_regulation_frontier_schema import SequenceRegulationSchemaReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceRegulationQualityCheck:
    check_id: str
    passed: bool
    severity: str
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if (
            not self.check_id
            or not self.detail
            or self.severity not in {"info", "warning", "error"}
        ):
            raise ValidationError("quality check fields are invalid")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceRegulationQualityReport:
    checks: tuple[SequenceRegulationQualityCheck, ...]
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


def build_sequence_regulation_quality(
    fixture: SequenceRegulationFixture,
    data: SequenceRegulationDataAudit,
    schema: SequenceRegulationSchemaReport,
    evaluation: SequenceRegulationEvaluation,
    metrics: SequenceRegulationMetrics,
    reconciliation: SequenceRegulationReconciliation,
) -> SequenceRegulationQualityReport:
    checks = (
        SequenceRegulationQualityCheck(
            "data_audit", data.accepted, "error", "public fixture audit accepted"
        ),
        SequenceRegulationQualityCheck(
            "schema", schema.accepted, "error", "record schema accepted"
        ),
        SequenceRegulationQualityCheck(
            "fixture_id", bool(fixture.fixture_id), "error", "fixture identity is present"
        ),
        SequenceRegulationQualityCheck(
            "positive_count",
            len(fixture.positive_records) == 4,
            "error",
            "four positive cases are retained",
        ),
        SequenceRegulationQualityCheck(
            "control_count",
            len(fixture.control_records) == 12,
            "error",
            "twelve controls are retained",
        ),
        SequenceRegulationQualityCheck(
            "operation_count",
            len({record.operation for record in fixture.records}) == 4,
            "error",
            "four operations are covered",
        ),
        SequenceRegulationQualityCheck(
            "record_evaluation",
            evaluation.accepted,
            "error",
            "all expected states and issue paths match",
        ),
        SequenceRegulationQualityCheck(
            "state_matches",
            evaluation.state_match_count == len(evaluation.records),
            "error",
            "every record state matches",
        ),
        SequenceRegulationQualityCheck(
            "issue_matches",
            evaluation.issue_match_count == len(evaluation.records),
            "error",
            "every record issue path matches",
        ),
        SequenceRegulationQualityCheck(
            "metric_state_rate",
            next(
                metric for metric in metrics.metrics if metric.metric_id == "state_match_rate"
            ).value
            == 1,
            "error",
            "state match rate is complete",
        ),
        SequenceRegulationQualityCheck(
            "metric_issue_rate",
            next(
                metric for metric in metrics.metrics if metric.metric_id == "issue_match_rate"
            ).value
            == 1,
            "error",
            "issue match rate is complete",
        ),
        SequenceRegulationQualityCheck(
            "reconciliation", reconciliation.accepted, "error", "reconciliation has no differences"
        ),
        SequenceRegulationQualityCheck(
            "receipts",
            all(item.adapter.content_address.startswith("sha256:") for item in evaluation.records),
            "error",
            "result receipts are present",
        ),
        SequenceRegulationQualityCheck(
            "raw_warnings",
            all(item.adapter.warnings for item in evaluation.records),
            "warning",
            "primitive cautions remain visible",
        ),
        SequenceRegulationQualityCheck(
            "control_paths",
            all(item.role == "positive" or item.accepted for item in evaluation.records),
            "error",
            "controls follow expected boundary paths",
        ),
        SequenceRegulationQualityCheck(
            "context_lock",
            all(record.context_key == fixture.context_key for record in fixture.records),
            "error",
            "fixture context is locked",
        ),
        SequenceRegulationQualityCheck(
            "source_receipts",
            len(fixture.sources) == 4 and all(source.checksum for source in fixture.sources),
            "error",
            "four source checksums are present",
        ),
        SequenceRegulationQualityCheck(
            "no_subject_fields",
            all(
                not {str(key).lower() for key in record.payload}
                & {"patient", "subject", "sample_id"}
                for record in fixture.records
            ),
            "error",
            "payload boundary is retained",
        ),
        SequenceRegulationQualityCheck(
            "deterministic_addresses",
            len({item.adapter.content_address for item in evaluation.records})
            == len(evaluation.records),
            "warning",
            "record result addresses are distinct",
        ),
        SequenceRegulationQualityCheck(
            "accepted_metrics", metrics.accepted, "error", "all release metrics meet the gate"
        ),
        SequenceRegulationQualityCheck(
            "accepted_reconciliation",
            reconciliation.accepted,
            "error",
            "expected and observed records reconcile",
        ),
        SequenceRegulationQualityCheck(
            "supported_positive",
            all(
                item.observed_state.value in {"supported", "partial"}
                for item in evaluation.records
                if item.role == "positive"
            ),
            "error",
            "positive cases stay in declared supported states",
        ),
        SequenceRegulationQualityCheck(
            "invalid_controls_visible",
            any(
                item.observed_state.value == "invalid"
                for item in evaluation.records
                if item.role == "control"
            ),
            "warning",
            "invalid controls are visible",
        ),
        SequenceRegulationQualityCheck(
            "out_of_domain_visible",
            any(
                item.observed_state.value == "out_of_domain"
                for item in evaluation.records
                if item.role == "control"
            ),
            "warning",
            "context controls are visible",
        ),
        SequenceRegulationQualityCheck(
            "state_enum",
            all(item.observed_state.value for item in evaluation.records),
            "error",
            "all states use the declared enum",
        ),
    )
    failed = tuple(
        check.check_id for check in checks if not check.passed and check.severity == "error"
    )
    return SequenceRegulationQualityReport(
        checks, not failed, sum(check.passed for check in checks), failed
    )


__all__ = [
    "SequenceRegulationQualityCheck",
    "SequenceRegulationQualityReport",
    "build_sequence_regulation_quality",
]
