"""Public source-to-record-to-execution lineage."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class WorkbenchReleaseLineage:
    source_to_records: dict[str, tuple[str, ...]]
    record_to_execution: dict[str, str]
    closed: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_workbench_release_lineage(fixture: Any, evaluation: Any) -> WorkbenchReleaseLineage:
    joins: dict[str, list[str]] = {source.source_id: [] for source in fixture.sources}
    for record in fixture.records:
        for source_id in record.source_ids:
            joins.setdefault(source_id, []).append(record.record_id)
    record_to_execution = {row.record_id: row.content_address for row in evaluation.executions}
    body = {"source_to_records": {key: tuple(sorted(value)) for key, value in sorted(joins.items())}, "record_to_execution": record_to_execution}
    closed = set(record_to_execution) == {record.record_id for record in fixture.records}
    return WorkbenchReleaseLineage(**body, closed=closed, content_address=content_hash(body | {"closed": closed}))

__all__ = ["WorkbenchReleaseLineage", "build_workbench_release_lineage"]
