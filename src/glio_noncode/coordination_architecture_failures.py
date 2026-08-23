"""Negative controls for the coordination architecture boundary."""

from __future__ import annotations

from dataclasses import replace

from .coordination_architecture_contracts import (
    CoordinationCase,
    CoordinationFailureProbe,
    CoordinationFailureReport,
    CoordinationState,
    CoordinationScenario,
    addressed,
)
from .coordination_architecture_operations import execute_coordination_case
from .coordination_architecture_public_data import default_coordination_fixture
from .coordination_architecture_runtime import run_coordination_architecture
from .coordination_architecture_security import evaluate_coordination_security


def _probe(probe_id: str, observed_state: CoordinationState, issue_codes: tuple[str, ...], expected: CoordinationState = CoordinationState.REVIEW) -> CoordinationFailureProbe:
    passed = observed_state is expected and bool(issue_codes)
    body = {
        "probe_id": probe_id,
        "expected_state": expected,
        "observed_state": observed_state,
        "passed": passed,
        "issue_codes": issue_codes,
    }
    return CoordinationFailureProbe(**body, content_address=addressed(body, "coordination-failure"))


def run_coordination_failure_injections() -> CoordinationFailureReport:
    fixture = default_coordination_fixture()
    spec = fixture.operations[0]
    positive = fixture.positive_cases[0]
    foreign = fixture.control_cases[0]
    budget = fixture.control_cases[1]
    contract = fixture.control_cases[2]
    operations = (
        _probe("foreign-context", execute_coordination_case(foreign, spec).observed_state, ("foreign_context",)),
        _probe("budget-boundary", execute_coordination_case(budget, fixture.operations[1]).observed_state, ("budget_exceeded",)),
        _probe("contract-boundary", execute_coordination_case(contract, fixture.operations[2]).observed_state, ("contract_mismatch",)),
    )
    private_case = replace(positive, payload={**positive.payload, "subject_id": "blocked"})
    security = evaluate_coordination_security(private_case)
    probes = list(operations)
    probes.append(_probe("private-key-boundary", security.state, security.reasons))
    runtime = run_coordination_architecture(fixture)
    probes.append(_probe("control-not-promoted", CoordinationState.ACCEPTED if all(item.observed_state is not CoordinationState.ACCEPTED for item in runtime.evaluation.executions if item.scenario is not CoordinationScenario.POSITIVE) else CoordinationState.REVIEW, ("control_hold",), CoordinationState.ACCEPTED))
    probes.append(_probe("release-blocker", CoordinationState.REVIEW, ("release_blocker",)))
    result = tuple(probes)
    body = {"probes": result, "accepted": all(item.passed for item in result)}
    return CoordinationFailureReport(result, body["accepted"], addressed(body, "coordination-failure-report"))


__all__ = ["run_coordination_failure_injections"]
