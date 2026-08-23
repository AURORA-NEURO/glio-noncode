"""Source, input, output, and state evidence joins."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class WorkbenchReleaseEvidenceMatrix:
    cells: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_workbench_release_evidence_matrix(fixture: Any, evaluation: Any) -> WorkbenchReleaseEvidenceMatrix:
    records = {record.record_id: record for record in fixture.records}
    cells = tuple({"record_id": row.record_id, "source_count": len(records[row.record_id].source_ids), "input_address": records[row.record_id].content_address, "output_address": row.content_address, "state": row.observed_state.value} for row in evaluation.executions)
    body = {"cells": cells, "accepted": all(item["source_count"] >= 2 and item["output_address"].startswith("sha256:") for item in cells)}
    return WorkbenchReleaseEvidenceMatrix(**body, content_address=content_hash(body))

__all__ = ["WorkbenchReleaseEvidenceMatrix", "build_workbench_release_evidence_matrix"]
