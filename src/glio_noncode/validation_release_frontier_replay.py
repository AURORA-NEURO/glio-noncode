"""Deterministic replay receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseEvaluation, ValidationReleaseFixture
from .validation_release_frontier_fixture_eval import evaluate_validation_release_fixture


@dataclass(frozen=True, slots=True)
class ValidationReleaseReplayReport:
    first_address: str
    second_address: str
    deterministic: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def replay_validation_release_evaluation(fixture: ValidationReleaseFixture, evaluation: ValidationReleaseEvaluation) -> ValidationReleaseReplayReport:
    second = evaluate_validation_release_fixture(fixture)
    body = {"first_address": evaluation.content_address, "second_address": second.content_address, "deterministic": evaluation.content_address == second.content_address, "accepted": second.accepted}
    return ValidationReleaseReplayReport(**body, content_address=content_hash(body))


__all__ = ["ValidationReleaseReplayReport", "replay_validation_release_evaluation"]
