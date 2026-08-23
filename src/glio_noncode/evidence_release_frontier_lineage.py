"""Source-to-record-to-execution lineage for release review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseLineage:
    source_to_records: dict[str, tuple[str, ...]]
    record_to_execution: dict[str, str]
    closed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_evidence_release_lineage(fixture: Any, evaluation: Any) -> EvidenceReleaseLineage:
    mapping: dict[str, list[str]] = {source.source_id: [] for source in fixture.sources}
    for record in fixture.records:
        for source_id in record.source_ids:
            mapping.setdefault(source_id, []).append(record.record_id)
    record_to_execution = {item.record_id: item.content_address for item in evaluation.executions}
    body = {"source_to_records": {key: tuple(sorted(value)) for key, value in sorted(mapping.items())}, "record_to_execution": record_to_execution}
    return EvidenceReleaseLineage(**body, closed=set(record_to_execution) == {record.record_id for record in fixture.records}, content_address=content_hash(body | {"closed": set(record_to_execution) == {record.record_id for record in fixture.records}}))


__all__ = ["EvidenceReleaseLineage", "build_evidence_release_lineage"]
