"""Replay expectations for deterministic Domain 07 evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_frontier_fixture_eval import (
    ChromatinFrontierEvaluationReport,
    evaluate_chromatin_frontier_fixture,
)
from .chromatin_frontier_public_data import (
    ChromatinFrontierFixture,
    default_chromatin_frontier_fixture,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ChromatinFrontierReplayExpectation:
    fixture_id: str
    record_states: tuple[tuple[str, str], ...]
    receipt_addresses: tuple[tuple[str, str], ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.fixture_id, "fixture_id")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinFrontierReplayCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinFrontierReplayReport:
    fixture_id: str
    checks: tuple[ChromatinFrontierReplayCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.checks) and all(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "failed_check_ids": list(self.failed_check_ids),
        }


def build_chromatin_frontier_expectation(
    evaluation: ChromatinFrontierEvaluationReport,
) -> ChromatinFrontierReplayExpectation:
    body = {
        "fixture_id": evaluation.fixture_id,
        "record_states": tuple(
            (item.record_id, item.adapter_state) for item in evaluation.receipts
        ),
        "receipt_addresses": tuple(
            (item.record_id, item.content_address) for item in evaluation.receipts
        ),
    }
    return ChromatinFrontierReplayExpectation(**body, content_address=content_hash(body))


def replay_chromatin_frontier_evaluation(
    evaluation: ChromatinFrontierEvaluationReport,
    *,
    fixture: ChromatinFrontierFixture | None = None,
) -> ChromatinFrontierReplayReport:
    selected = fixture or default_chromatin_frontier_fixture()
    rerun = evaluate_chromatin_frontier_fixture(selected)
    expected = build_chromatin_frontier_expectation(evaluation)
    actual = build_chromatin_frontier_expectation(rerun)
    checks: list[ChromatinFrontierReplayCheck] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "passed": passed, "detail": detail}
        checks.append(ChromatinFrontierReplayCheck(**body, content_address=content_hash(body)))

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
    return ChromatinFrontierReplayReport(selected.fixture_id, tuple(checks), content_hash(body))


__all__ = [
    "ChromatinFrontierReplayCheck",
    "ChromatinFrontierReplayExpectation",
    "ChromatinFrontierReplayReport",
    "build_chromatin_frontier_expectation",
    "replay_chromatin_frontier_evaluation",
]
