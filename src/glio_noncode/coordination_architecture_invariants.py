"""Independent conservation invariants for coordination projections."""

from __future__ import annotations

from .coordination_architecture_contracts import CoordinationRuntime, CoordinationScenario


def coordination_invariants(runtime: CoordinationRuntime) -> tuple[str, ...]:
    issues: list[str] = []
    executions = runtime.evaluation.executions
    if len(executions) != 64:
        issues.append("case_denominator")
    if sum(item.scenario is CoordinationScenario.POSITIVE for item in executions) != 16:
        issues.append("positive_denominator")
    if sum(item.scenario is not CoordinationScenario.POSITIVE for item in executions) != 48:
        issues.append("control_denominator")
    if len(runtime.plan.nodes) != 16:
        issues.append("operation_denominator")
    if len(runtime.ledger.events) != len(executions):
        issues.append("ledger_conservation")
    if len(runtime.evaluation.executions) - 16 != 48:
        issues.append("review_conservation")
    if any(item.observed_state.value == "accepted" for item in executions if item.scenario is not CoordinationScenario.POSITIVE):
        issues.append("control_promotion")
    return tuple(sorted(set(issues)))


__all__ = ["coordination_invariants"]
