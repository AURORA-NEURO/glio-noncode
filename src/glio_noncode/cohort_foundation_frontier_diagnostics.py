"""Cross-plane diagnostics for silent cohort-control failure modes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_fixture_eval import CohortFoundationEvaluation
from .cohort_foundation_frontier_metrics import CohortFoundationMetrics
from .cohort_foundation_frontier_policy import CohortFoundationDisposition, CohortFoundationPolicy
from .cohort_foundation_frontier_public_data import CohortFoundationFixture
from .cohort_foundation_frontier_reconciliation import CohortFoundationReconciliation


class CohortFoundationDiagnosticSeverity(StrEnum):
    INFO = "info"
    REVIEW = "review"
    BLOCKING = "blocking"


@dataclass(frozen=True, slots=True)
class CohortFoundationDiagnosticFinding:
    finding_id: str
    severity: CohortFoundationDiagnosticSeverity
    operation: str
    record_ids: tuple[str, ...]
    message: str
    evidence_addresses: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationDiagnosticReport:
    report_id: str
    findings: tuple[CohortFoundationDiagnosticFinding, ...]
    accepted: bool
    content_address: str

    @property
    def review_findings(self) -> tuple[CohortFoundationDiagnosticFinding, ...]:
        return tuple(item for item in self.findings if item.severity is not CohortFoundationDiagnosticSeverity.INFO)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_foundation_frontier_diagnostics(fixture: CohortFoundationFixture, evaluation: CohortFoundationEvaluation, metrics: CohortFoundationMetrics, policy: CohortFoundationPolicy, reconciliation: CohortFoundationReconciliation) -> CohortFoundationDiagnosticReport:
    findings: list[CohortFoundationDiagnosticFinding] = []
    for operation in metrics.operation_metrics:
        record_ids = tuple(item.record_id for item in evaluation.executions if item.operation is operation.operation and item.issues)
        if operation.out_of_domain:
            values = tuple(item for item in evaluation.executions if item.operation is operation.operation and item.actual_state == "out_of_domain")
            body = {"operation": operation.operation, "record_ids": tuple(item.record_id for item in values), "addresses": tuple(item.content_address for item in values)}
            findings.append(CohortFoundationDiagnosticFinding(content_hash((operation.operation.value, "foreign"), prefix="finding"), CohortFoundationDiagnosticSeverity.REVIEW, operation.operation.value, tuple(item.record_id for item in values), "foreign-context inputs were quarantined", tuple(item.content_address for item in values), content_hash(body)))
        if operation.partial or operation.absent or operation.abstained:
            body = {"operation": operation.operation, "record_ids": record_ids, "partial": operation.partial, "absent": operation.absent, "abstained": operation.abstained}
            findings.append(CohortFoundationDiagnosticFinding(content_hash((operation.operation.value, "coverage"), prefix="finding"), CohortFoundationDiagnosticSeverity.REVIEW, operation.operation.value, record_ids, "coverage limitations remain visible in the descriptive plane", tuple(item.content_address for item in evaluation.executions if item.operation is operation.operation), content_hash(body)))
    if not reconciliation.reconciled:
        findings.append(CohortFoundationDiagnosticFinding("reconciliation-blocked", CohortFoundationDiagnosticSeverity.BLOCKING, "all", reconciliation.mismatches, "expected and observed states do not reconcile", (), content_hash(reconciliation.mismatches)))
    if not fixture.boundary == "public_aggregate_non_patient":
        findings.append(CohortFoundationDiagnosticFinding("boundary-blocked", CohortFoundationDiagnosticSeverity.BLOCKING, "all", (), "fixture boundary is not public aggregate", (), content_hash(fixture.boundary)))
    if all(item.disposition is CohortFoundationDisposition.ALLOW_DESCRIPTIVE for item in policy.decisions):
        findings.append(CohortFoundationDiagnosticFinding("control-plane-missing", CohortFoundationDiagnosticSeverity.BLOCKING, "all", (), "policy contains no review or quarantine state", (policy.content_address,), content_hash(policy.content_address)))
    if not findings:
        findings.append(CohortFoundationDiagnosticFinding("no-findings", CohortFoundationDiagnosticSeverity.INFO, "all", (), "no cross-plane findings", (), content_hash("no-findings")))
    body = {"report_id": "cohort-foundation-frontier-diagnostics", "findings": findings, "accepted": not any(item.severity is CohortFoundationDiagnosticSeverity.BLOCKING for item in findings)}
    return CohortFoundationDiagnosticReport(body["report_id"], tuple(findings), body["accepted"], content_hash(body))


__all__ = ["CohortFoundationDiagnosticFinding", "CohortFoundationDiagnosticReport", "CohortFoundationDiagnosticSeverity", "build_cohort_foundation_frontier_diagnostics"]
