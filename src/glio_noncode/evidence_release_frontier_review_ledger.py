"""Review ownership ledger with explicit completion and escalation states."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseReviewLedger:
    assignments: tuple[dict[str, Any], ...]
    open_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_evidence_release_review_ledger(rows: Iterable[Any]) -> EvidenceReleaseReviewLedger:
    assignments = tuple({"record_id": row["record_id"], "priority": row["priority"], "owner": "evidence-review", "status": "open", "issue_codes": row["issue_codes"]} for row in rows)
    body = {"assignments": assignments, "open_count": len(assignments)}
    return EvidenceReleaseReviewLedger(**body, content_address=content_hash(body))


def close_review_assignment(ledger: EvidenceReleaseReviewLedger, record_id: str) -> EvidenceReleaseReviewLedger:
    assignments = tuple(dict(item, status="closed" if item["record_id"] == record_id else item["status"]) for item in ledger.assignments)
    body = {"assignments": assignments, "open_count": sum(item["status"] == "open" for item in assignments)}
    return EvidenceReleaseReviewLedger(**body, content_address=content_hash(body))


__all__ = ["EvidenceReleaseReviewLedger", "build_evidence_release_review_ledger", "close_review_assignment"]
