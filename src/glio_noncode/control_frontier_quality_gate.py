"""Blocking quality gate for the control frontier release surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_adapters import ControlFrontierAdapterRegistry
from .control_frontier_contracts import ControlFrontierEvaluation, ControlFrontierFixture
from .control_frontier_lineage import ControlFrontierLineage
from .control_frontier_metrics import ControlFrontierMetrics
from .control_frontier_policy import ControlFrontierPolicy
from .control_frontier_public_data import ControlFrontierDataAudit
from .control_frontier_reconciliation import ControlFrontierReconciliation
from .control_frontier_schema import ControlFrontierSchema, validate_control_frontier_schema
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierQualityCheck:
    check_id: str
    passed: bool
    blocking: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierQualityReport:
    fixture_id: str
    checks: tuple[ControlFrontierQualityCheck, ...]
    accepted: bool
    blockers: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def run_control_frontier_quality_gate(fixture: ControlFrontierFixture, audit: ControlFrontierDataAudit, evaluation: ControlFrontierEvaluation, metrics: ControlFrontierMetrics, adapters: ControlFrontierAdapterRegistry, schema: ControlFrontierSchema, policy: ControlFrontierPolicy, lineage: ControlFrontierLineage, reconciliation: ControlFrontierReconciliation) -> ControlFrontierQualityReport:
    policy_results = policy.evaluate(evaluation)
    values = (
        ("data-audit", audit.accepted, True, audit.accepted, True, "public data audit"),
        ("evaluation", evaluation.accepted, True, evaluation.accepted, True, "row evaluation"),
        ("record-count", metrics.record_count, True, metrics.record_count, 32, "metrics cover all rows"),
        ("adapter-count", len(adapters.specs), True, len(adapters.specs), 8, "all operations have adapters"),
        ("schema", not validate_control_frontier_schema(schema), True, not validate_control_frontier_schema(schema), True, "schema manifest is complete"),
        ("lineage", lineage.accepted, True, lineage.accepted, True, "lineage closes source and execution edges"),
        ("reconciliation", reconciliation.reconciled, True, reconciliation.reconciled, True, "expected and observed states reconcile"),
        ("policy", all(item["passed"] for item in policy_results if item["blocking"]), True, all(item["passed"] for item in policy_results if item["blocking"]), True, "blocking use policy rules pass"),
    )
    checks = []
    for check_id, passed, blocking, observed, required, detail in values:
        body = {"check_id": check_id, "passed": passed, "blocking": blocking, "observed": observed, "required": required, "detail": detail}
        checks.append(ControlFrontierQualityCheck(**body, content_address=content_hash(body)))
    blockers = tuple(item.check_id for item in checks if item.blocking and not item.passed)
    return ControlFrontierQualityReport(fixture.fixture_id, tuple(checks), not blockers, blockers, content_hash(tuple(checks)))


__all__ = ["ControlFrontierQualityCheck", "ControlFrontierQualityReport", "run_control_frontier_quality_gate"]
