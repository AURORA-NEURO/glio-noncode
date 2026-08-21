"""Replay and content-address verification for Domain 06 C13-C16."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_frontier_fixture_eval import (
    SequenceFrontierEvaluationReport,
    evaluate_sequence_frontier_fixture,
)
from .sequence_frontier_public_data import (
    SequenceFrontierFixture,
    default_sequence_frontier_fixture,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class SequenceFrontierReplayExpectation:
    fixture_id: str
    record_states: tuple[tuple[str, str], ...]
    receipt_addresses: tuple[tuple[str, str], ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.fixture_id, "fixture_id")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceFrontierReplayCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceFrontierReplayReport:
    fixture_id: str
    checks: tuple[SequenceFrontierReplayCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.checks) and all(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def build_sequence_frontier_expectation(
    evaluation: SequenceFrontierEvaluationReport,
) -> SequenceFrontierReplayExpectation:
    body = {
        "fixture_id": evaluation.fixture_id,
        "record_states": tuple(
            (item.record_id, item.adapter_state) for item in evaluation.receipts
        ),
        "receipt_addresses": tuple(
            (item.record_id, item.content_address) for item in evaluation.receipts
        ),
    }
    return SequenceFrontierReplayExpectation(**body, content_address=content_hash(body))


def replay_sequence_frontier_evaluation(
    evaluation: SequenceFrontierEvaluationReport, *, fixture: SequenceFrontierFixture | None = None
) -> SequenceFrontierReplayReport:
    selected = fixture or default_sequence_frontier_fixture()
    rerun = evaluate_sequence_frontier_fixture(selected)
    expected = build_sequence_frontier_expectation(evaluation)
    actual = build_sequence_frontier_expectation(rerun)
    checks: list[SequenceFrontierReplayCheck] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "passed": passed, "detail": detail}
        checks.append(SequenceFrontierReplayCheck(**body, content_address=content_hash(body)))

    add(
        "fixture-identity",
        evaluation.fixture_id == selected.fixture_id,
        "fixture identity is retained",
    )
    add(
        "fixture-address",
        evaluation.catalog_address == rerun.catalog_address,
        "catalog address is stable",
    )
    add(
        "record-order",
        tuple(item.record_id for item in evaluation.receipts)
        == tuple(item.record_id for item in rerun.receipts),
        "receipt order is stable",
    )
    add("state-replay", expected.record_states == actual.record_states, "adapter states replay")
    add(
        "receipt-address-replay",
        expected.receipt_addresses == actual.receipt_addresses,
        "receipt addresses replay",
    )
    add(
        "check-count",
        len(evaluation.checks) == len(rerun.checks) == 120,
        "one hundred twenty checks replay",
    )
    add(
        "positive-count",
        evaluation.positive_count == rerun.positive_count == 4,
        "positive count replays",
    )
    add(
        "control-count",
        evaluation.control_count == rerun.control_count == 12,
        "control count replays",
    )
    body = {"fixture_id": selected.fixture_id, "checks": checks}
    return SequenceFrontierReplayReport(selected.fixture_id, tuple(checks), content_hash(body))


__all__ = [
    "SequenceFrontierReplayCheck",
    "SequenceFrontierReplayExpectation",
    "SequenceFrontierReplayReport",
    "build_sequence_frontier_expectation",
    "replay_sequence_frontier_evaluation",
]
