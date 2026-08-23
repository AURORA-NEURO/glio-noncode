"""Lineage joins from public source receipts to planning executions."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignLineage:
    fixture_id: str
    source_links: tuple[dict[str, Any], ...]
    record_links: tuple[dict[str, Any], ...]
    execution_links: tuple[dict[str, Any], ...]
    closed: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_validation_design_lineage(fixture: Any, evaluation: Any) -> ValidationDesignLineage:
    source_links = tuple({"source_id": source.source_id, "content_address": source.content_address} for source in fixture.sources)
    record_links = tuple({"record_id": record.record_id, "source_ids": record.source_ids, "record_address": record.content_address} for record in fixture.records)
    execution_links = tuple({"record_id": row.record_id, "execution_address": row.content_address} for row in evaluation.executions)
    closed = all(item["content_address"].startswith("sha256:") for item in source_links) and len(record_links) == len(execution_links) == len(fixture.records)
    body = {"fixture_id": fixture.fixture_id, "source_links": source_links, "record_links": record_links, "execution_links": execution_links, "closed": closed}
    return ValidationDesignLineage(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignLineage", "build_validation_design_lineage"]
