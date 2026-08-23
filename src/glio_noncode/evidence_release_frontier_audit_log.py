"""Append-only stage log with contiguous sequence checks."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseAuditLog:
    entries: tuple[dict[str, Any], ...]
    contiguous: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_evidence_release_audit_log(stage_ids: tuple[str, ...]) -> EvidenceReleaseAuditLog:
    entries = tuple({"sequence": index, "stage_id": stage_id, "event": "completed"} for index, stage_id in enumerate(stage_ids, start=1))
    body = {"entries": entries, "contiguous": tuple(item["sequence"] for item in entries) == tuple(range(1, len(entries) + 1))}
    return EvidenceReleaseAuditLog(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseAuditLog", "build_evidence_release_audit_log"]
