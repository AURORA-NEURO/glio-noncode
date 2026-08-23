"""Evidence matrix linking each row to sources, payload, output, and release state."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseEvidenceMatrix:
    cells: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_evidence_release_evidence_matrix(fixture: Any, evaluation: Any) -> EvidenceReleaseEvidenceMatrix:
    records = {row.record_id: row for row in fixture.records}
    cells = tuple({"record_id": execution.record_id, "source_count": len(records[execution.record_id].source_ids), "input_address": records[execution.record_id].content_address, "output_address": execution.content_address, "state": execution.observed_state.value, "closed": execution.content_address.startswith("sha256:")} for execution in evaluation.executions)
    body = {"cells": cells, "accepted": all(item["closed"] and item["source_count"] >= 2 for item in cells)}
    return EvidenceReleaseEvidenceMatrix(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseEvidenceMatrix", "build_evidence_release_evidence_matrix"]
