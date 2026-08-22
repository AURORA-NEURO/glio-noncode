"""Replay expectations for deterministic Domain 09 topology evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_frontier_fixture_eval import (
    TopologyFrontierEvaluationReport,
    evaluate_topology_frontier_fixture,
)
from .topology_frontier_public_data import (
    TopologyFrontierFixture,
    default_topology_frontier_fixture,
)


@dataclass(frozen=True, slots=True)
class TopologyFrontierReplayCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyFrontierReplayReport:
    fixture_id: str
    expected_address: str
    replay_address: str
    expected_states: tuple[tuple[str, str], ...]
    replay_states: tuple[tuple[str, str], ...]
    expected_receipt_addresses: tuple[tuple[str, str], ...]
    replay_receipt_addresses: tuple[tuple[str, str], ...]
    checks: tuple[TopologyFrontierReplayCheck, ...]
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


def _state_map(report: TopologyFrontierEvaluationReport) -> tuple[tuple[str, str], ...]:
    return tuple((item.record_id, item.adapter_state) for item in report.receipts)


def _address_map(report: TopologyFrontierEvaluationReport) -> tuple[tuple[str, str], ...]:
    return tuple((item.record_id, item.content_address) for item in report.receipts)


def replay_topology_frontier_evaluation(
    evaluation: TopologyFrontierEvaluationReport,
    *,
    fixture: TopologyFrontierFixture | None = None,
) -> TopologyFrontierReplayReport:
    selected = fixture or default_topology_frontier_fixture()
    replay = evaluate_topology_frontier_fixture(selected)
    expected_states = _state_map(evaluation)
    replay_states = _state_map(replay)
    expected_addresses = _address_map(evaluation)
    replay_addresses = _address_map(replay)
    checks: list[TopologyFrontierReplayCheck] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "passed": passed, "detail": detail}
        checks.append(TopologyFrontierReplayCheck(**body, content_address=content_hash(body)))

    add("fixture-id-replay", evaluation.fixture_id == replay.fixture_id == selected.fixture_id, "fixture identity replay")
    add("fixture-version-replay", selected.fixture_version == replay.fixture_version, "fixture version replay")
    add("context-replay", evaluation.context_key == replay.context_key == selected.context_key, "context replay")
    add("state-replay", expected_states == replay_states, "adapter states replay")
    add("receipt-address-replay", expected_addresses == replay_addresses, "receipt addresses replay")
    add("evaluation-address-replay", evaluation.content_address == replay.content_address, "evaluation address replay")
    add("expected-accepted-replay", evaluation.accepted == replay.accepted, "evaluation acceptance replay")
    add("record-count-replay", len(evaluation.receipts) == len(replay.receipts) == len(selected.records), "record count replay")
    body = {
        "fixture_id": selected.fixture_id,
        "expected_address": evaluation.content_address,
        "replay_address": replay.content_address,
        "expected_states": expected_states,
        "replay_states": replay_states,
        "expected_receipt_addresses": expected_addresses,
        "replay_receipt_addresses": replay_addresses,
        "checks": checks,
    }
    return TopologyFrontierReplayReport(
        selected.fixture_id,
        evaluation.content_address,
        replay.content_address,
        expected_states,
        replay_states,
        expected_addresses,
        replay_addresses,
        tuple(checks),
        content_hash(body),
    )


__all__ = [
    "TopologyFrontierReplayCheck",
    "TopologyFrontierReplayReport",
    "replay_topology_frontier_evaluation",
]
