"""Source-to-record-to-execution lineage for validation release planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseEvaluation, ValidationReleaseFixture


@dataclass(frozen=True, slots=True)
class ValidationReleaseLineageEdge:
    parent_id: str
    child_id: str
    relation: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseLineage:
    node_ids: tuple[str, ...]
    edges: tuple[ValidationReleaseLineageEdge, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_lineage(fixture: ValidationReleaseFixture, evaluation: ValidationReleaseEvaluation) -> ValidationReleaseLineage:
    nodes = [fixture.fixture_id]
    edges: list[ValidationReleaseLineageEdge] = []
    for source in fixture.sources:
        nodes.append(source.source_id)
        body = {"parent_id": source.source_id, "child_id": fixture.fixture_id, "relation": "source-receipt"}
        edges.append(ValidationReleaseLineageEdge(**body, content_address=content_hash(body)))
    for record, execution in zip(fixture.records, evaluation.executions, strict=True):
        nodes.extend((record.record_id, f"execution:{record.record_id}"))
        for parent, child, relation in ((fixture.fixture_id, record.record_id, "fixture-record"), (record.record_id, f"execution:{record.record_id}", "record-execution")):
            body = {"parent_id": parent, "child_id": child, "relation": relation}
            edges.append(ValidationReleaseLineageEdge(**body, content_address=content_hash(body)))
    return ValidationReleaseLineage(tuple(dict.fromkeys(nodes)), tuple(edges), content_hash((tuple(nodes), tuple(edges))))


def verify_validation_release_lineage(lineage: ValidationReleaseLineage) -> tuple[str, ...]:
    errors = []
    nodes = set(lineage.node_ids)
    for edge in lineage.edges:
        if edge.parent_id not in nodes or edge.child_id not in nodes:
            errors.append(f"missing-node:{edge.parent_id}:{edge.child_id}")
    return tuple(errors)


__all__ = ["ValidationReleaseLineage", "ValidationReleaseLineageEdge", "build_validation_release_lineage", "verify_validation_release_lineage"]
