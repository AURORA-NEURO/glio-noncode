"""Cross-operation diagnostics for missing comparators and boundary failures."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .cohort_beta import CohortBetaState
from .cohort_beta_frontier_fixture_eval import CohortBetaFrontierEvaluation
from .cohort_beta_frontier_metrics import CohortBetaFrontierMetrics
from .cohort_beta_frontier_policy import CohortBetaFrontierPolicy
from .cohort_beta_frontier_reconciliation import CohortBetaFrontierReconciliation
from .serialization import content_hash, jsonable


class CohortBetaFrontierDiagnosticSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierDiagnosticFinding:
    code: str
    severity: CohortBetaFrontierDiagnosticSeverity
    operation: str | None
    message: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierDiagnosticReport:
    findings: tuple[CohortBetaFrontierDiagnosticFinding, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_diagnostics(evaluation: CohortBetaFrontierEvaluation, metrics: CohortBetaFrontierMetrics, policy: CohortBetaFrontierPolicy, reconciliation: CohortBetaFrontierReconciliation) -> CohortBetaFrontierDiagnosticReport:
    findings: list[CohortBetaFrontierDiagnosticFinding] = []
    for operation in ("C05", "C06", "C07", "C08"):
        rows = tuple(item for item in evaluation.rows if item.operation == operation)
        if any(item.observed_state is CohortBetaState.PARTIAL for item in rows):
            code, severity, message = "partial-comparator", CohortBetaFrontierDiagnosticSeverity.WARNING, "at least one path is incomplete and must remain reviewable"
        else:
            code, severity, message = "operation-covered", CohortBetaFrontierDiagnosticSeverity.INFO, "positive and control paths are represented"
        body = {"code": code, "severity": severity, "operation": operation, "message": message}
        findings.append(CohortBetaFrontierDiagnosticFinding(code, severity, operation, message, content_hash(body, prefix="diagnostic")))
    if reconciliation.mismatch_count:
        findings.append(CohortBetaFrontierDiagnosticFinding("state-mismatch", CohortBetaFrontierDiagnosticSeverity.BLOCKING, None, "fixture reconciliation has mismatched states", content_hash(reconciliation.mismatch_count, prefix="diagnostic")))
    return CohortBetaFrontierDiagnosticReport(tuple(findings), reconciliation.reconciled and metrics.acceptance_percent == 100.0, content_hash(findings, prefix="diagnostics"))


__all__ = ["CohortBetaFrontierDiagnosticFinding", "CohortBetaFrontierDiagnosticReport", "CohortBetaFrontierDiagnosticSeverity", "build_cohort_beta_frontier_diagnostics"]
