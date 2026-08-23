"""Diagnostics for missing longitudinal channels and cohort disagreement."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .cohort_alpha import CohortAlphaState
from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .cohort_alpha_frontier_governance import CohortAlphaFrontierMetrics, CohortAlphaFrontierPolicy, CohortAlphaFrontierReconciliation
from .serialization import content_hash, jsonable


class CohortAlphaFrontierDiagnosticSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierDiagnosticFinding:
    code: str
    operation: str | None
    severity: CohortAlphaFrontierDiagnosticSeverity
    message: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierDiagnosticReport:
    findings: tuple[CohortAlphaFrontierDiagnosticFinding, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_diagnostics(evaluation: CohortAlphaFrontierEvaluation, metrics: CohortAlphaFrontierMetrics, policy: CohortAlphaFrontierPolicy, reconciliation: CohortAlphaFrontierReconciliation) -> CohortAlphaFrontierDiagnosticReport:
    findings = []
    for operation in ("C09", "C10", "C11", "C12"):
        rows = tuple(row for row in evaluation.rows if row.operation == operation)
        if any(row.observed_state is CohortAlphaState.PARTIAL for row in rows):
            code, severity, message = "missing-channel", CohortAlphaFrontierDiagnosticSeverity.WARNING, "one path lacks a required longitudinal or comparator channel"
        elif any(row.observed_state is CohortAlphaState.AMBIGUOUS for row in rows):
            code, severity, message = "direction-disagreement", CohortAlphaFrontierDiagnosticSeverity.WARNING, "cohort directions disagree and remain ambiguous"
        else:
            code, severity, message = "operation-covered", CohortAlphaFrontierDiagnosticSeverity.INFO, "positive and boundary paths are represented"
        body = {"code": code, "operation": operation, "severity": severity, "message": message}
        findings.append(CohortAlphaFrontierDiagnosticFinding(code, operation, severity, message, content_hash(body, prefix="alpha-diagnostic")))
    if reconciliation.mismatch_count:
        findings.append(CohortAlphaFrontierDiagnosticFinding("state-mismatch", None, CohortAlphaFrontierDiagnosticSeverity.BLOCKING, "expected and observed alpha states diverge", content_hash(reconciliation.mismatch_count, prefix="alpha-diagnostic")))
    return CohortAlphaFrontierDiagnosticReport(tuple(findings), reconciliation.reconciled and metrics.acceptance_percent == 100.0, content_hash(findings, prefix="alpha-diagnostics"))


__all__ = ["CohortAlphaFrontierDiagnosticFinding", "CohortAlphaFrontierDiagnosticReport", "CohortAlphaFrontierDiagnosticSeverity", "build_cohort_alpha_frontier_diagnostics"]
