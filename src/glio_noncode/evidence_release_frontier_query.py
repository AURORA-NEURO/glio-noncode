"""Deterministic query view over execution state and issue codes."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseQueryResult:
    query: str
    rows: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def query_evidence_release(evaluation: Any, query: str) -> EvidenceReleaseQueryResult:
    rows = tuple({"record_id": item.record_id, "operation": item.operation.value, "state": item.observed_state.value, "issues": item.issue_codes} for item in evaluation.executions if query in {item.observed_state.value, item.operation.value} or query in item.issue_codes)
    body = {"query": query, "rows": rows, "accepted": all("record_id" in item for item in rows)}
    return EvidenceReleaseQueryResult(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseQueryResult", "query_evidence_release"]
