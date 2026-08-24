"""Deterministic D12 replay comparison."""

from __future__ import annotations

from dataclasses import dataclass

from .cohort_architecture_contracts import (
    CohortArchitectureCheck,
    CohortArchitectureCheckKind,
    CohortArchitectureFixture,
    addressed,
)
from .cohort_architecture_operations import evaluate_cohort_architecture_fixture


@dataclass(frozen=True, slots=True)
class CohortArchitectureReplay:
    fixture_id: str
    checks: tuple[CohortArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, object]:
        return {
            "fixture_id": self.fixture_id,
            "checks": [item.to_dict() for item in self.checks],
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def replay_cohort_architecture_fixture(
    fixture: CohortArchitectureFixture,
) -> CohortArchitectureReplay:
    left = evaluate_cohort_architecture_fixture(fixture)
    right = evaluate_cohort_architecture_fixture(fixture)
    checks = (
        CohortArchitectureCheck(
            "replay:evaluation-address",
            CohortArchitectureCheckKind.REPLAY,
            left.content_address == right.content_address,
            left.content_address,
            right.content_address,
            "evaluation content address is stable",
            addressed((left.content_address, right.content_address), "cohort-replay-check"),
        ),
        CohortArchitectureCheck(
            "replay:receipt-addresses",
            CohortArchitectureCheckKind.REPLAY,
            tuple(item.content_address for item in left.receipts)
            == tuple(item.content_address for item in right.receipts),
            len(left.receipts),
            len(right.receipts),
            "receipt addresses are stable",
            addressed((left.receipts, right.receipts), "cohort-replay-check"),
        ),
        CohortArchitectureCheck(
            "replay:execution-states",
            CohortArchitectureCheckKind.REPLAY,
            tuple(item.observed_state for item in left.executions)
            == tuple(item.observed_state for item in right.executions),
            tuple(item.observed_state for item in left.executions),
            tuple(item.observed_state for item in right.executions),
            "observed states are stable",
            addressed((left.executions, right.executions), "cohort-replay-check"),
        ),
    )
    body = {"fixture_id": fixture.fixture_id, "checks": checks}
    return CohortArchitectureReplay(
        fixture.fixture_id,
        checks,
        all(item.passed for item in checks),
        addressed(body, "cohort-replay"),
    )


__all__ = ["CohortArchitectureReplay", "replay_cohort_architecture_fixture"]
