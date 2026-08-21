"""Deterministic replay floors for Domain 05 C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .atlas_alpha_evidence_fixture_eval import (
    AtlasAlphaEvidenceEvaluationReport,
    evaluate_atlas_alpha_evidence_fixture,
)
from .atlas_alpha_evidence_public_data import (
    ATLAS_ALPHA_EVIDENCE_CONTEXT_KEY,
    AtlasAlphaEvidenceFixture,
    AtlasAlphaEvidenceRole,
    default_atlas_alpha_evidence_fixture,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceReplayExpectation:
    """Stable fixture identity, state, issue, and count floors."""

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
class AtlasAlphaEvidenceReplayCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceReplayReport:
    expectation: AtlasAlphaEvidenceReplayExpectation
    current_evaluation_address: str
    checks: tuple[AtlasAlphaEvidenceReplayCheck, ...]
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


def _check(check_id: str, passed: bool, detail: str) -> AtlasAlphaEvidenceReplayCheck:
    body = {"check_id": check_id, "passed": passed, "detail": detail}
    return AtlasAlphaEvidenceReplayCheck(check_id, passed, detail, content_hash(body))


def build_atlas_alpha_evidence_expectation(
    evaluation: AtlasAlphaEvidenceEvaluationReport,
) -> AtlasAlphaEvidenceReplayExpectation:
    body = {
        "fixture_id": evaluation.fixture_id,
        "fixture_version": evaluation.fixture_version,
        "context_key": evaluation.context_key,
        "evaluation_address": evaluation.content_address,
        "record_ids": tuple(item.record_id for item in evaluation.receipts),
        "expected_states": tuple(
            (item.record_id, item.expected_state) for item in evaluation.receipts
        ),
        "expected_issue_codes": tuple(
            (item.record_id, item.expected_issue_codes) for item in evaluation.receipts
        ),
        "positive_count": evaluation.positive_count,
        "control_count": evaluation.control_count,
    }
    return AtlasAlphaEvidenceReplayExpectation(**body, content_address=content_hash(body))


def replay_atlas_alpha_evidence_evaluation(
    evaluation: AtlasAlphaEvidenceEvaluationReport,
    *,
    fixture: AtlasAlphaEvidenceFixture | None = None,
) -> AtlasAlphaEvidenceReplayReport:
    """Re-execute and compare state, issue, role, identity, and sanitation floors."""

    selected = fixture or default_atlas_alpha_evidence_fixture()
    expectation = build_atlas_alpha_evidence_expectation(evaluation)
    current = evaluate_atlas_alpha_evidence_fixture(selected)
    checks: list[AtlasAlphaEvidenceReplayCheck] = []

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
        current.context_key == ATLAS_ALPHA_EVIDENCE_CONTEXT_KEY == expectation.context_key,
        "exact context is replayed",
    )
    add(
        "record-order",
        tuple(item.record_id for item in current.receipts) == expectation.record_ids,
        "record order is deterministic",
    )
    add(
        "states",
        tuple((item.record_id, item.adapter_state) for item in current.receipts)
        == tuple((item.record_id, item.adapter_state) for item in evaluation.receipts),
        "adapter states match",
    )
    add(
        "issue-floors",
        tuple((item.record_id, item.expected_issue_codes) for item in current.receipts)
        == expectation.expected_issue_codes,
        "issue floors match",
    )
    add(
        "positive-floor",
        current.positive_count == expectation.positive_count == 4,
        "positive floor is stable",
    )
    add(
        "control-floor",
        current.control_count == expectation.control_count == 12,
        "control floor is stable",
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
            not {"input_text", "payload", "records"} & set(item.summary)
            for item in current.receipts
        ),
        "replay receipts remain sanitized",
    )
    add(
        "positive-state-floor",
        all(
            item.adapter_state == "supported"
            for item in current.receipts
            if item.role is AtlasAlphaEvidenceRole.POSITIVE
        ),
        "positive states remain supported",
    )
    add(
        "control-review-floor",
        all(
            item.adapter_state != "supported"
            for item in current.receipts
            if item.role is AtlasAlphaEvidenceRole.CONTROL
        ),
        "controls remain review states",
    )
    body = {
        "expectation": expectation,
        "current_evaluation_address": current.content_address,
        "checks": checks,
    }
    return AtlasAlphaEvidenceReplayReport(
        expectation, current.content_address, tuple(checks), content_hash(body)
    )


__all__ = [
    "AtlasAlphaEvidenceReplayCheck",
    "AtlasAlphaEvidenceReplayExpectation",
    "AtlasAlphaEvidenceReplayReport",
    "build_atlas_alpha_evidence_expectation",
    "replay_atlas_alpha_evidence_evaluation",
]
