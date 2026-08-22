"""Replay and determinism receipts for the Domain 10 link frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_frontier_fixture_eval import LinkFrontierEvaluation, evaluate_link_frontier_fixture
from .link_frontier_public_data import LinkFrontierFixture, default_link_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkFrontierReplayRecord:
    record_id: str
    first_state: str
    second_state: str
    first_issue_codes: tuple[str, ...]
    second_issue_codes: tuple[str, ...]
    first_address: str
    second_address: str
    deterministic: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"deterministic": self.deterministic}


@dataclass(frozen=True, slots=True)
class LinkFrontierReplayReport:
    fixture_id: str
    first_evaluation_address: str
    second_evaluation_address: str
    records: tuple[LinkFrontierReplayRecord, ...]
    deterministic: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"deterministic": self.deterministic}


def replay_link_frontier_evaluation(
    fixture: LinkFrontierFixture | None = None,
    *,
    first: LinkFrontierEvaluation | None = None,
) -> LinkFrontierReplayReport:
    fixture = fixture or default_link_frontier_fixture()
    first = first or evaluate_link_frontier_fixture(fixture)
    second = evaluate_link_frontier_fixture(fixture)
    first_map = first.execution_map()
    second_map = second.execution_map()
    records: list[LinkFrontierReplayRecord] = []
    for record_id in sorted(first_map):
        left = first_map[record_id]
        right = second_map[record_id]
        body = {
            "record_id": record_id,
            "first_state": left.state,
            "second_state": right.state,
            "first_issue_codes": left.issue_codes,
            "second_issue_codes": right.issue_codes,
            "first_address": left.content_address,
            "second_address": right.content_address,
            "deterministic": left.to_dict() == right.to_dict(),
        }
        records.append(LinkFrontierReplayRecord(**body, content_address=content_hash(body)))
    deterministic = (
        first.to_dict() == second.to_dict()
        and all(item.deterministic for item in records)
    )
    body = {
        "fixture_id": fixture.fixture_id,
        "first_evaluation_address": first.content_address,
        "second_evaluation_address": second.content_address,
        "records": records,
        "deterministic": deterministic,
    }
    return LinkFrontierReplayReport(**body, content_address=content_hash(body))


__all__ = ["LinkFrontierReplayRecord", "LinkFrontierReplayReport", "replay_link_frontier_evaluation"]
