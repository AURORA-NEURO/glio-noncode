"""Deterministic response bands for lifecycle review work."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseReviewSla:
    rows: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_evidence_release_review_sla(queue: Any) -> EvidenceReleaseReviewSla:
    rows = tuple({"record_id": item["record_id"], "response_band": "same-day" if item["priority"] == "high" else "three-business-days", "escalation": item["priority"] == "high"} for item in queue.rows)
    body = {"rows": rows, "accepted": all("response_band" in item for item in rows)}
    return EvidenceReleaseReviewSla(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseReviewSla", "build_evidence_release_review_sla"]
