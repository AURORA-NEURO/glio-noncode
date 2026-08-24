"""Deterministic D13 replay comparison."""

from __future__ import annotations

from dataclasses import dataclass

from .planning_architecture_contracts import (
    PlanningArchitectureCheck,
    PlanningArchitectureCheckKind,
    PlanningArchitectureFixture,
    addressed,
)
from .planning_architecture_operations import evaluate_planning_architecture_fixture


@dataclass(frozen=True, slots=True)
class PlanningArchitectureReplay:
    fixture_id: str
    checks: tuple[PlanningArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, object]:
        return {
            "fixture_id": self.fixture_id,
            "checks": [item.to_dict() for item in self.checks],
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def replay_planning_architecture_fixture(
    fixture: PlanningArchitectureFixture,
) -> PlanningArchitectureReplay:
    left = evaluate_planning_architecture_fixture(fixture)
    right = evaluate_planning_architecture_fixture(fixture)
    checks: list[PlanningArchitectureCheck] = []
    for check_id, passed, observed, required, detail in (
        (
            "replay:evaluation-address",
            left.content_address == right.content_address,
            left.content_address,
            right.content_address,
            "evaluation content address is stable",
        ),
        (
            "replay:receipt-addresses",
            tuple(item.content_address for item in left.receipts)
            == tuple(item.content_address for item in right.receipts),
            tuple(item.content_address for item in left.receipts),
            tuple(item.content_address for item in right.receipts),
            "receipt addresses are stable",
        ),
        (
            "replay:execution-states",
            tuple(item.observed_state for item in left.executions)
            == tuple(item.observed_state for item in right.executions),
            tuple(item.observed_state for item in left.executions),
            tuple(item.observed_state for item in right.executions),
            "observed states and issue paths are stable",
        ),
    ):
        body = {
            "check_id": check_id,
            "kind": PlanningArchitectureCheckKind.REPLAY,
            "passed": passed,
            "observed": observed,
            "required": required,
            "detail": detail,
        }
        checks.append(
            PlanningArchitectureCheck(
                **body,
                content_address=addressed(body, "planning-replay-check"),
            )
        )
    body = {"fixture_id": fixture.fixture_id, "checks": checks}
    return PlanningArchitectureReplay(
        fixture.fixture_id,
        tuple(checks),
        all(item.passed for item in checks),
        addressed(body, "planning-replay"),
    )


__all__ = ["PlanningArchitectureReplay", "replay_planning_architecture_fixture"]
