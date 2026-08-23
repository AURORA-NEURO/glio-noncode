"""Source-to-record-to-execution evidence matrix."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignEvidenceMatrix:
    rows: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_validation_design_evidence_matrix(fixture: Any, evaluation: Any) -> ValidationDesignEvidenceMatrix:
    source_ids = {source.source_id for source in fixture.sources}
    rows = tuple({"record_id": record.record_id, "operation": record.operation.value, "source_ids": record.source_ids, "source_join": bool(record.source_ids) and set(record.source_ids) <= source_ids, "execution_address": execution.content_address, "closed": execution.content_address.startswith("sha256:")} for record, execution in zip(fixture.records, evaluation.executions, strict=True))
    body = {"rows": rows, "accepted": len(rows) == len(fixture.records) and all(item["source_join"] and item["closed"] for item in rows)}
    return ValidationDesignEvidenceMatrix(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignEvidenceMatrix", "build_validation_design_evidence_matrix"]
