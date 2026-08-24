"""Deterministic replay checks for D15 aggregate cases."""

from __future__ import annotations

from dataclasses import dataclass

from .workbench_architecture_contracts import WorkbenchArchitectureFixture, addressed
from .workbench_architecture_operations import evaluate_workbench_architecture_fixture
from .workbench_architecture_public_data import default_workbench_architecture_fixture


@dataclass(frozen=True, slots=True)
class WorkbenchArchitectureReplay:
    fixture_id: str
    first_address: str
    second_address: str
    case_count: int
    receipt_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, object]:
        return {
            "fixture_id": self.fixture_id,
            "first_address": self.first_address,
            "second_address": self.second_address,
            "case_count": self.case_count,
            "receipt_count": self.receipt_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def replay_workbench_architecture_fixture(
    fixture: WorkbenchArchitectureFixture | None = None,
) -> WorkbenchArchitectureReplay:
    selected = fixture or default_workbench_architecture_fixture()
    first = evaluate_workbench_architecture_fixture(selected)
    second = evaluate_workbench_architecture_fixture(selected)
    body = {
        "fixture_id": selected.fixture_id,
        "first_address": first.content_address,
        "second_address": second.content_address,
        "case_count": len(first.executions),
        "receipt_count": len(first.receipts),
        "accepted": first.accepted
        and second.accepted
        and first.content_address == second.content_address,
    }
    return WorkbenchArchitectureReplay(
        **body, content_address=addressed(body, "workbench-architecture-replay")
    )


def workbench_architecture_replay_summary(replay: WorkbenchArchitectureReplay) -> dict[str, object]:
    return {
        "fixture_id": replay.fixture_id,
        "accepted": replay.accepted,
        "case_count": replay.case_count,
        "receipt_count": replay.receipt_count,
        "stable": replay.first_address == replay.second_address,
    }


__all__ = [
    "WorkbenchArchitectureReplay",
    "replay_workbench_architecture_fixture",
    "workbench_architecture_replay_summary",
]
