"""Deterministic replay floors for the Domain 05 C01–C04 evidence plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .regulatory_atlas_fixture_eval import (
    RegulatoryAtlasEvaluationReport,
    evaluate_regulatory_atlas_fixture,
)
from .regulatory_atlas_public_data import (
    REGULATORY_ATLAS_CONTEXT_KEY,
    RegulatoryAtlasFixture,
    RegulatoryAtlasRole,
    default_regulatory_atlas_fixture,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class RegulatoryAtlasReplayExpectation:
    """Stable identities, states, issue floors, and count floors."""

    fixture_id: str
    fixture_version: str
    context_key: str
    evaluation_address: str
    record_ids: tuple[str, ...]
    expected_states: tuple[tuple[str, str], ...]
    expected_issue_codes: tuple[tuple[str, tuple[str, ...]], ...]
    positive_count: int
    control_count: int
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "fixture_id",
            "fixture_version",
            "context_key",
            "evaluation_address",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RegulatoryAtlasReplayCheck:
    """One replay comparison."""

    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RegulatoryAtlasReplayReport:
    """Replay result with stable expectation and current address."""

    expectation: RegulatoryAtlasReplayExpectation
    current_evaluation_address: str
    checks: tuple[RegulatoryAtlasReplayCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "failed_check_ids": list(self.failed_check_ids),
        }


def _address(body: Any) -> str:
    return content_hash(body)


def _check(check_id: str, passed: bool, detail: str) -> RegulatoryAtlasReplayCheck:
    body = {"check_id": check_id, "passed": passed, "detail": detail}
    return RegulatoryAtlasReplayCheck(check_id, passed, detail, _address(body))


def build_regulatory_atlas_expectation(
    evaluation: RegulatoryAtlasEvaluationReport,
) -> RegulatoryAtlasReplayExpectation:
    """Capture sanitized replay expectations from one evaluation."""

    body = {
        "fixture_id": evaluation.fixture_id,
        "fixture_version": evaluation.fixture_version,
        "context_key": evaluation.context_key,
        "evaluation_address": evaluation.content_address,
        "record_ids": tuple(receipt.record_id for receipt in evaluation.receipts),
        "expected_states": tuple(
            (receipt.record_id, receipt.expected_state) for receipt in evaluation.receipts
        ),
        "expected_issue_codes": tuple(
            (receipt.record_id, receipt.expected_issue_codes) for receipt in evaluation.receipts
        ),
        "positive_count": evaluation.positive_count,
        "control_count": evaluation.control_count,
    }
    return RegulatoryAtlasReplayExpectation(**body, content_address=_address(body))


def replay_regulatory_atlas_evaluation(
    evaluation: RegulatoryAtlasEvaluationReport,
    *,
    fixture: RegulatoryAtlasFixture | None = None,
) -> RegulatoryAtlasReplayReport:
    """Re-execute and compare identity, state, issue, role, and address floors."""

    selected = fixture or default_regulatory_atlas_fixture()
    expectation = build_regulatory_atlas_expectation(evaluation)
    current = evaluate_regulatory_atlas_fixture(selected)
    checks: list[RegulatoryAtlasReplayCheck] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        checks.append(_check(check_id, passed, detail))

    add("fixture-id", current.fixture_id == expectation.fixture_id, "fixture identity is stable")
    add(
        "fixture-version",
        current.fixture_version == expectation.fixture_version,
        "fixture version is stable",
    )
    add(
        "context",
        current.context_key == REGULATORY_ATLAS_CONTEXT_KEY == expectation.context_key,
        "exact atlas context is replayed",
    )
    add(
        "record-order",
        tuple(item.record_id for item in current.receipts) == expectation.record_ids,
        "record order is deterministic",
    )
    add(
        "states",
        tuple((item.record_id, item.adapter_state) for item in current.receipts)
        == expectation.expected_states,
        "adapter states match expectation",
    )
    add(
        "issue-floors",
        tuple((item.record_id, item.expected_issue_codes) for item in current.receipts)
        == expectation.expected_issue_codes,
        "issue-code floors match expectation",
    )
    add(
        "positive-floor",
        current.positive_count == expectation.positive_count == 4,
        "positive count is stable",
    )
    add(
        "control-floor",
        current.control_count == expectation.control_count == 12,
        "control count is stable",
    )
    add(
        "receipt-addresses",
        tuple(item.content_address for item in current.receipts)
        == tuple(item.content_address for item in evaluation.receipts),
        "receipt addresses are deterministic",
    )
    add(
        "evaluation-address",
        current.content_address == evaluation.content_address,
        "whole evaluation address is deterministic",
    )
    add(
        "source-free",
        all(
            not {"input_text", "records", "payload"} & set(item.summary)
            for item in current.receipts
        ),
        "replay receipts remain sanitized",
    )
    add(
        "positive-state-floor",
        all(
            item.adapter_state == "supported"
            for item in current.receipts
            if item.role is RegulatoryAtlasRole.POSITIVE
        ),
        "positive states remain supported",
    )
    add(
        "control-review-floor",
        all(
            item.adapter_state != "supported"
            for item in current.receipts
            if item.role is RegulatoryAtlasRole.CONTROL
        ),
        "controls remain review states",
    )
    body = {
        "expectation": expectation,
        "current_evaluation_address": current.content_address,
        "checks": checks,
    }
    return RegulatoryAtlasReplayReport(
        expectation, current.content_address, tuple(checks), _address(body)
    )


__all__ = [
    "RegulatoryAtlasReplayCheck",
    "RegulatoryAtlasReplayExpectation",
    "RegulatoryAtlasReplayReport",
    "build_regulatory_atlas_expectation",
    "replay_regulatory_atlas_evaluation",
]
