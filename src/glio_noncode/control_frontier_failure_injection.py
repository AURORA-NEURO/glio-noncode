"""Declared mutation probes for control frontier quality boundaries."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .control_frontier_contracts import ControlFrontierFixture
from .control_frontier_fixture_eval import evaluate_control_frontier_fixture
from .control_frontier_integrity import evaluate_control_frontier_integrity
from .control_frontier_reconciliation import reconcile_control_frontier
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierFailureInjection:
    injection_id: str
    target: str
    expected_signal: str
    observed_signal: str
    detected: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierFailureReport:
    injections: tuple[ControlFrontierFailureInjection, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def run_control_frontier_failure_injections(fixture: ControlFrontierFixture) -> ControlFrontierFailureReport:
    evaluation = evaluate_control_frontier_fixture(fixture)
    mutated_record = replace(fixture.records[0], expected_state=fixture.records[0].expected_state.__class__.BLOCKED)
    mutated_fixture = replace(fixture, records=(mutated_record,) + fixture.records[1:])
    reconciliation = reconcile_control_frontier(mutated_fixture, evaluation)
    mutated_execution = replace(evaluation.executions[0], content_address="sha256:mutation")
    mutated_evaluation = replace(evaluation, executions=(mutated_execution,) + evaluation.executions[1:])
    integrity = evaluate_control_frontier_integrity(fixture, mutated_evaluation)
    rows = (
        ("wrong-expected-state", "reconciliation", "C05-POS-001", bool(reconciliation.failed_record_ids)),
        ("execution-address-mutation", "integrity", "execution-addresses", not integrity.accepted),
        ("control-retention", "evaluation", "controls-visible", sum(item.role.value == "control" for item in evaluation.executions) == 24),
    )
    injections = []
    for injection_id, target, expected_signal, detected in rows:
        body = {"injection_id": injection_id, "target": target, "expected_signal": expected_signal, "observed_signal": expected_signal if detected else "undetected", "detected": detected}
        injections.append(ControlFrontierFailureInjection(**body, content_address=content_hash(body)))
    return ControlFrontierFailureReport(tuple(injections), all(item.detected for item in injections), content_hash(tuple(injections)))


__all__ = ["ControlFrontierFailureInjection", "ControlFrontierFailureReport", "run_control_frontier_failure_injections"]
