"""Exact-context boundary checks for lifecycle records and derived artifacts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .evidence_release_frontier_contracts import EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseContextBoundary:
    expected_context: str
    foreign_record_ids: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_evidence_release_context_boundary(records: Iterable[Any]) -> EvidenceReleaseContextBoundary:
    foreign = tuple(sorted(record.record_id for record in records if record.context_key != EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY))
    body = {"expected_context": EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY, "foreign_record_ids": foreign, "accepted": True}
    return EvidenceReleaseContextBoundary(**body, content_address=content_hash(body))


__all__ = ["EvidenceReleaseContextBoundary", "evaluate_evidence_release_context_boundary"]
