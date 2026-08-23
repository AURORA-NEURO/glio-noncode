"""Expected-versus-observed state reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseReconciliation:
    matched_records: tuple[str, ...]
    mismatched_records: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def reconcile_evidence_release(fixture: Any, evaluation: Any) -> EvidenceReleaseReconciliation:
    expected = {record.record_id: record.expected_state for record in fixture.records}
    matched = tuple(sorted(item.record_id for item in evaluation.executions if expected.get(item.record_id) == item.observed_state))
    mismatched = tuple(sorted(set(expected) - set(matched)))
    body = {"matched_records": matched, "mismatched_records": mismatched, "accepted": not mismatched}
    return EvidenceReleaseReconciliation(**body, content_address=content_hash(body))


__all__ = ["EvidenceReleaseReconciliation", "reconcile_evidence_release"]
