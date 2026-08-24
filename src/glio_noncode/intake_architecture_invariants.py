"""Executable invariants that protect D01 denominator and scope assumptions."""

from __future__ import annotations

from .intake_architecture_contracts import IntakeArchitectureRuntime


def intake_architecture_invariants(runtime: IntakeArchitectureRuntime) -> tuple[str, ...]:
    issues: list[str] = []
    if len(runtime.evaluation.results) != 64:
        issues.append("evaluation_cardinality")
    if (
        len(runtime.evaluation.results)
        != runtime.evaluation.passed_cases + runtime.evaluation.failed_cases
    ):
        issues.append("evaluation_partition")
    if len(runtime.evaluation.checks) != 458:
        issues.append("evaluation_check_cardinality")
    if len(runtime.review_queue.items) != 48:
        issues.append("review_cardinality")
    if len(runtime.ledger.events) != len(runtime.evaluation.results):
        issues.append("ledger_cardinality")
    if any(
        item.observed_state.value == "accepted"
        for item in runtime.evaluation.results
        if item.scenario.value != "positive"
    ):
        issues.append("control_accepted")
    if any(
        item.observed_state.value != "accepted"
        for item in runtime.evaluation.results
        if item.scenario.value == "positive"
    ):
        issues.append("positive_not_accepted")
    if len(runtime.stages) != 24:
        issues.append("stage_cardinality")
    if runtime.compliance is None or not runtime.compliance.accepted:
        issues.append("compliance_not_accepted")
    return tuple(sorted(set(issues)))


__all__ = ["intake_architecture_invariants"]
