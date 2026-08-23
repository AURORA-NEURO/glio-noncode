"""Deterministic replay receipt for lifecycle execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence_release_frontier_fixture_eval import evaluate_evidence_release_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseReplayReport:
    first_address: str
    second_address: str
    deterministic: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def replay_evidence_release_evaluation(fixture: Any, evaluation: Any) -> EvidenceReleaseReplayReport:
    second = evaluate_evidence_release_fixture(fixture)
    body = {"first_address": evaluation.content_address, "second_address": second.content_address, "deterministic": evaluation.content_address == second.content_address}
    return EvidenceReleaseReplayReport(**body, content_address=content_hash(body))


__all__ = ["EvidenceReleaseReplayReport", "replay_evidence_release_evaluation"]
