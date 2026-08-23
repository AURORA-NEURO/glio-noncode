"""Resilience probes for repeated replay and malformed control handling."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence_release_frontier_fixture_eval import evaluate_evidence_release_fixture
from .evidence_release_frontier_operations import evaluate_reclassification
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseResilienceReport:
    replay_addresses: tuple[str, ...]
    malformed_state: str
    stable: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_evidence_release_resilience(fixture: Any, *, repetitions: int = 3) -> EvidenceReleaseResilienceReport:
    runs = tuple(evaluate_evidence_release_fixture(fixture).content_address for _ in range(max(1, repetitions)))
    malformed = evaluate_reclassification({})
    body = {"replay_addresses": runs, "malformed_state": malformed.state.value, "stable": len(set(runs)) == 1 and malformed.state.value == "rejected"}
    return EvidenceReleaseResilienceReport(**body, content_address=content_hash(body))


__all__ = ["EvidenceReleaseResilienceReport", "evaluate_evidence_release_resilience"]
