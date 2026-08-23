"""Release diff summary suitable for a change-control review."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence_release_frontier_diff import diff_evidence_release_evaluations
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseReleaseDiff:
    before_address: str
    after_address: str
    changed_record_ids: tuple[str, ...]
    requires_review: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_evidence_release_release_diff(before: Any, after: Any) -> EvidenceReleaseReleaseDiff:
    difference = diff_evidence_release_evaluations(before, after)
    changed = difference.added_ids + difference.removed_ids + difference.changed_states
    body = {"before_address": before.content_address, "after_address": after.content_address, "changed_record_ids": tuple(sorted(set(changed))), "requires_review": bool(changed)}
    return EvidenceReleaseReleaseDiff(**body, content_address=content_hash(body))


__all__ = ["EvidenceReleaseReleaseDiff", "build_evidence_release_release_diff"]
