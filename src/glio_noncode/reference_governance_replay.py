"""Deterministic replay floors for the Domain 04 C09–C12 evidence plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .reference_governance_fixture_eval import (
    ReferenceGovernanceEvaluationReport,
    evaluate_reference_governance_fixture,
)
from .reference_governance_public_data import (
    REFERENCE_GOVERNANCE_CONTEXT_KEY,
    ReferenceGovernanceFixture,
    ReferenceGovernanceRole,
    default_reference_governance_fixture,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ReferenceGovernanceReplayExpectation:
    """Expected identities and state floors captured from a fixture evaluation."""

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
class ReferenceGovernanceReplayCheck:
    """One replay comparison."""

    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceGovernanceReplayReport:
    """Replay result with stable expectation and current evaluation addresses."""

    expectation: ReferenceGovernanceReplayExpectation
    current_evaluation_address: str
    checks: tuple[ReferenceGovernanceReplayCheck, ...]
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


def _check(check_id: str, passed: bool, detail: str) -> ReferenceGovernanceReplayCheck:
    body = {"check_id": check_id, "passed": passed, "detail": detail}
    return ReferenceGovernanceReplayCheck(check_id, passed, detail, _address(body))


def build_reference_governance_expectation(
    evaluation: ReferenceGovernanceEvaluationReport,
) -> ReferenceGovernanceReplayExpectation:
    """Capture only stable, sanitized replay expectations."""

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
    return ReferenceGovernanceReplayExpectation(**body, content_address=_address(body))


def replay_reference_governance_evaluation(
    evaluation: ReferenceGovernanceEvaluationReport,
    *,
    fixture: ReferenceGovernanceFixture | None = None,
) -> ReferenceGovernanceReplayReport:
    """Re-execute the fixture and compare identities, floors, and addresses."""

    selected = fixture or default_reference_governance_fixture()
    expectation = build_reference_governance_expectation(evaluation)
    current = evaluate_reference_governance_fixture(selected)
    checks: list[ReferenceGovernanceReplayCheck] = []

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
        current.context_key == REFERENCE_GOVERNANCE_CONTEXT_KEY == expectation.context_key,
        "exact context is replayed",
    )
    add(
        "record-order",
        tuple(item.record_id for item in current.receipts) == expectation.record_ids,
        "record order is deterministic",
    )
    current_states = tuple((item.record_id, item.adapter_state) for item in current.receipts)
    add(
        "states",
        current_states == expectation.expected_states,
        "adapter states match captured expectations",
    )
    current_issues = tuple((item.record_id, item.expected_issue_codes) for item in current.receipts)
    add(
        "issue-floors",
        current_issues == expectation.expected_issue_codes,
        "issue-code floors match captured expectations",
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
            "records" not in item.summary and "restrictions" not in item.summary
            for item in current.receipts
        ),
        "replay receipts remain sanitized",
    )
    add(
        "positive-state-floor",
        all(
            item.adapter_state == "supported"
            for item in current.receipts
            if item.role is ReferenceGovernanceRole.POSITIVE
        ),
        "every positive remains supported",
    )
    add(
        "control-review-floor",
        all(
            item.adapter_state != "supported"
            for item in current.receipts
            if item.role is ReferenceGovernanceRole.CONTROL
        ),
        "every control remains review-state",
    )
    body = {
        "expectation": expectation,
        "current_evaluation_address": current.content_address,
        "checks": checks,
    }
    return ReferenceGovernanceReplayReport(
        expectation, current.content_address, tuple(checks), _address(body)
    )


__all__ = [
    "ReferenceGovernanceReplayCheck",
    "ReferenceGovernanceReplayExpectation",
    "ReferenceGovernanceReplayReport",
    "build_reference_governance_expectation",
    "replay_reference_governance_evaluation",
]
