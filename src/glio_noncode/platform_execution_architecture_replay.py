"""Deterministic replay for D16 aggregate execution."""

from __future__ import annotations

from dataclasses import dataclass

from .platform_execution_architecture_contracts import PlatformExecutionFixture, addressed
from .platform_execution_architecture_operations import evaluate_platform_execution_fixture
from .platform_execution_architecture_public_data import default_platform_execution_fixture


@dataclass(frozen=True, slots=True)
class PlatformExecutionReplay:
    fixture_id: str
    first_address: str
    second_address: str
    case_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, object]:
        return {
            "fixture_id": self.fixture_id,
            "first_address": self.first_address,
            "second_address": self.second_address,
            "case_count": self.case_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def replay_platform_execution_fixture(
    fixture: PlatformExecutionFixture | None = None,
) -> PlatformExecutionReplay:
    selected = fixture or default_platform_execution_fixture()
    first = evaluate_platform_execution_fixture(selected)
    second = evaluate_platform_execution_fixture(selected)
    body = {
        "fixture_id": selected.fixture_id,
        "first_address": first.content_address,
        "second_address": second.content_address,
        "case_count": len(first.executions),
        "accepted": first.accepted
        and second.accepted
        and first.content_address == second.content_address,
    }
    return PlatformExecutionReplay(
        **body, content_address=addressed(body, "platform-execution-replay")
    )


__all__ = ["PlatformExecutionReplay", "replay_platform_execution_fixture"]
