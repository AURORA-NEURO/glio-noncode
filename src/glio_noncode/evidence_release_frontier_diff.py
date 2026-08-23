"""Content-addressed difference between two lifecycle evaluations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseDiff:
    added_ids: tuple[str, ...]
    removed_ids: tuple[str, ...]
    changed_states: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def diff_evidence_release_evaluations(before: Any, after: Any) -> EvidenceReleaseDiff:
    left = {item.record_id: item for item in before.executions}
    right = {item.record_id: item for item in after.executions}
    changed = tuple(sorted(key for key in set(left) & set(right) if left[key].observed_state != right[key].observed_state))
    body = {"added_ids": tuple(sorted(set(right) - set(left))), "removed_ids": tuple(sorted(set(left) - set(right))), "changed_states": changed, "accepted": True}
    return EvidenceReleaseDiff(**body, content_address=content_hash(body))


__all__ = ["EvidenceReleaseDiff", "diff_evidence_release_evaluations"]
