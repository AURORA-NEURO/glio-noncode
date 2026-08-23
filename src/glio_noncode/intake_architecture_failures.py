"""Failure-injection probes for the D01 control boundary."""

from __future__ import annotations

from .intake_architecture_contracts import (
    IntakeArchitectureFailureProbe,
    IntakeArchitectureFailureReport,
    IntakeArchitectureScenario,
    IntakeArchitectureState,
    addressed,
)
from .intake_architecture_operations import evaluate_intake_architecture_case
from .intake_architecture_public_data import default_intake_architecture_fixture


def run_intake_architecture_failure_injections() -> IntakeArchitectureFailureReport:
    fixture = default_intake_architecture_fixture()
    controls = tuple(item for item in fixture.cases if item.scenario is not IntakeArchitectureScenario.POSITIVE)
    probes = []
    for case in controls[::16]:
        result = evaluate_intake_architecture_case(case)
        body = {
            "probe_id": f"probe:{case.scenario.value}",
            "expected_state": case.expected_state,
            "observed_state": result.observed_state,
            "passed": result.observed_state is IntakeArchitectureState.REVIEW and case.expected_issue_codes == result.issue_codes,
            "issue_codes": result.issue_codes,
        }
        probes.append(IntakeArchitectureFailureProbe(**body, content_address=addressed(body, "intake-failure-probe")))
    body = {"probes": tuple(probes), "accepted": all(item.passed for item in probes)}
    return IntakeArchitectureFailureReport(**body, content_address=addressed(body, "intake-failure-report"))


__all__ = ["run_intake_architecture_failure_injections"]
