"""Mutation probes for platform receipt integrity and control visibility."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .platform_frontier_contracts import PlatformFrontierFixture
from .platform_frontier_fixture_eval import evaluate_platform_frontier_fixture
from .platform_frontier_integrity import evaluate_platform_frontier_integrity
from .platform_frontier_reconciliation import reconcile_platform_frontier
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierFailureInjection:
    injection_id: str
    target: str
    expected_signal: str
    detected: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierFailureReport:
    injections: tuple[PlatformFrontierFailureInjection, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def run_platform_frontier_failure_injections(fixture: PlatformFrontierFixture) -> PlatformFrontierFailureReport:
    evaluation = evaluate_platform_frontier_fixture(fixture)
    mutated_record = replace(fixture.records[0], expected_state=fixture.records[0].expected_state.__class__.BLOCKED)
    mutated_fixture = replace(fixture, records=(mutated_record,) + fixture.records[1:])
    reconciliation = reconcile_platform_frontier(mutated_fixture, evaluation)
    mutated_execution = replace(evaluation.executions[0], content_address="sha256:platform-mutation")
    mutated_evaluation = replace(evaluation, executions=(mutated_execution,) + evaluation.executions[1:])
    integrity = evaluate_platform_frontier_integrity(fixture, mutated_evaluation)
    rows = (("wrong-expected-state", "reconciliation", bool(reconciliation.mismatch_ids)), ("execution-address-mutation", "integrity", not integrity.accepted), ("control-retention", "evaluation", sum(not item.accepted for item in evaluation.executions if item.role.value == "control") == 12))
    injections = []
    for injection_id, target, detected in rows:
        body = {"injection_id": injection_id, "target": target, "expected_signal": target, "detected": detected}
        injections.append(PlatformFrontierFailureInjection(**body, content_address=content_hash(body)))
    return PlatformFrontierFailureReport(tuple(injections), all(item.detected for item in injections), content_hash(tuple(injections)))


__all__ = ["PlatformFrontierFailureInjection", "PlatformFrontierFailureReport", "run_platform_frontier_failure_injections"]
