"""Quality gate for the D07 C05-C08 aggregate evidence plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .methylation_frontier_fixture_eval import MethylationFrontierEvaluation
from .methylation_frontier_metrics import MethylationFrontierMetrics
from .methylation_frontier_public_data import (
    MethylationFrontierDataAudit,
    MethylationFrontierFixture,
)
from .methylation_frontier_reconciliation import MethylationFrontierReconciliation
from .methylation_frontier_schema import MethylationFrontierSchemaReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class MethylationFrontierQualityCheck:
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
class MethylationFrontierQualityReport:
    checks: tuple[MethylationFrontierQualityCheck, ...]
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


def build_methylation_frontier_quality(
    fixture: MethylationFrontierFixture,
    data: MethylationFrontierDataAudit,
    schema: MethylationFrontierSchemaReport,
    evaluation: MethylationFrontierEvaluation,
    metrics: MethylationFrontierMetrics,
    reconciliation: MethylationFrontierReconciliation,
) -> MethylationFrontierQualityReport:
    checks = (
        MethylationFrontierQualityCheck(
            "data_audit", data.accepted, "error", "public fixture audit accepted"
        ),
        MethylationFrontierQualityCheck(
            "schema", schema.accepted, "error", "record schema accepted"
        ),
        MethylationFrontierQualityCheck(
            "fixture_identity", bool(fixture.fixture_id), "error", "fixture identity is present"
        ),
        MethylationFrontierQualityCheck(
            "positive_count",
            len(fixture.positive_records) == 4,
            "error",
            "four positive cases are retained",
        ),
        MethylationFrontierQualityCheck(
            "control_count",
            len(fixture.control_records) == 12,
            "error",
            "twelve controls are retained",
        ),
        MethylationFrontierQualityCheck(
            "operation_count",
            len({record.operation for record in fixture.records}) == 4,
            "error",
            "four methylation operations are covered",
        ),
        MethylationFrontierQualityCheck(
            "record_evaluation",
            evaluation.accepted,
            "error",
            "all expected states and issue paths match",
        ),
        MethylationFrontierQualityCheck(
            "state_matches",
            evaluation.state_match_count == len(evaluation.records),
            "error",
            "every record state matches",
        ),
        MethylationFrontierQualityCheck(
            "issue_matches",
            evaluation.issue_match_count == len(evaluation.records),
            "error",
            "every record issue path matches",
        ),
        MethylationFrontierQualityCheck(
            "metrics", metrics.accepted, "error", "all release metrics meet their floors"
        ),
        MethylationFrontierQualityCheck(
            "reconciliation",
            reconciliation.accepted,
            "error",
            "expected and observed paths reconcile",
        ),
        MethylationFrontierQualityCheck(
            "receipts",
            all(item.adapter.content_address.startswith("sha256:") for item in evaluation.records),
            "error",
            "result receipts are present",
        ),
        MethylationFrontierQualityCheck(
            "warnings",
            all(item.adapter.warnings for item in evaluation.records),
            "warning",
            "primitive cautions remain visible",
        ),
        MethylationFrontierQualityCheck(
            "context_lock",
            all(record.context_key == fixture.context_key for record in fixture.records),
            "error",
            "fixture context is locked",
        ),
        MethylationFrontierQualityCheck(
            "source_receipts",
            all(source.checksum for source in fixture.sources),
            "error",
            "source checksums are present",
        ),
        MethylationFrontierQualityCheck(
            "no_subject_fields",
            all(
                not {str(key).lower() for key in record.payload}
                & {"patient", "subject", "sample_id"}
                for record in fixture.records
            ),
            "error",
            "payload boundary is retained",
        ),
        MethylationFrontierQualityCheck(
            "distinct_results",
            len({item.adapter.content_address for item in evaluation.records})
            == len(evaluation.records),
            "warning",
            "record result addresses are distinct",
        ),
        MethylationFrontierQualityCheck(
            "out_of_domain_control",
            any(
                item.observed_state.value == "out_of_domain"
                for item in evaluation.records
                if item.role == "control"
            ),
            "warning",
            "out-of-domain controls are visible",
        ),
        MethylationFrontierQualityCheck(
            "partial_control",
            any(
                item.observed_state.value == "partial"
                for item in evaluation.records
                if item.role == "control"
            ),
            "warning",
            "partial controls are visible",
        ),
        MethylationFrontierQualityCheck(
            "invalid_control",
            any(
                item.observed_state.value == "invalid"
                for item in evaluation.records
                if item.role == "control"
            ),
            "warning",
            "invalid controls are visible",
        ),
        MethylationFrontierQualityCheck(
            "abstention_control",
            any(
                item.observed_state.value == "abstained"
                for item in evaluation.records
                if item.role == "control"
            ),
            "warning",
            "abstention controls are visible",
        ),
        MethylationFrontierQualityCheck(
            "positive_states",
            all(
                item.observed_state.value == "supported"
                for item in evaluation.records
                if item.role == "positive"
            ),
            "error",
            "positive cases are supported",
        ),
        MethylationFrontierQualityCheck(
            "operation_balance",
            all(
                sum(item.adapter.operation.value == operation.value for item in evaluation.records)
                == 4
                for operation in {item.adapter.operation for item in evaluation.records}
            ),
            "error",
            "each operation has four rows",
        ),
        MethylationFrontierQualityCheck(
            "context_query",
            any(
                item.adapter.operation.value == "methylation_context_retrieval"
                and item.observed_state.value == "supported"
                for item in evaluation.records
            ),
            "error",
            "context retrieval support is represented",
        ),
        MethylationFrontierQualityCheck(
            "cpg_path",
            any(
                item.adapter.operation.value == "cpg_creation_loss"
                and "cpg_created" in item.observed_issue_codes
                for item in evaluation.records
            ),
            "error",
            "CpG creation path is represented",
        ),
        MethylationFrontierQualityCheck(
            "motif_path",
            any(
                item.adapter.operation.value == "methylation_sensitive_motif"
                and "sensitive_motif_observed" in item.observed_issue_codes
                for item in evaluation.records
            ),
            "error",
            "sensitive motif path is represented",
        ),
        MethylationFrontierQualityCheck(
            "idh_path",
            any(
                item.adapter.operation.value == "idh_hypermethylation_context"
                and "idh_panel_supported" in item.observed_issue_codes
                for item in evaluation.records
            ),
            "error",
            "IDH panel path is represented",
        ),
    )
    failed = tuple(
        check.check_id for check in checks if not check.passed and check.severity == "error"
    )
    return MethylationFrontierQualityReport(
        checks, not failed, sum(check.passed for check in checks), failed
    )


__all__ = [
    "MethylationFrontierQualityCheck",
    "MethylationFrontierQualityReport",
    "build_methylation_frontier_quality",
]
