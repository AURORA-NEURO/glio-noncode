"""Source and record lineage for Domain 13 planning evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_frontier_fixture_eval import ValidationFrontierEvaluation
from .validation_frontier_public_data import ValidationFrontierFixture


@dataclass(frozen=True, slots=True)
class ValidationFrontierLineageEdge:
    edge_id: str
    edge_kind: str
    source_node: str
    target_node: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationFrontierLineageGraph:
    edges: tuple[ValidationFrontierLineageEdge, ...]
    terminal_addresses: tuple[str, ...]
    acyclic: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_frontier_lineage(fixture: ValidationFrontierFixture, evaluation: ValidationFrontierEvaluation) -> ValidationFrontierLineageGraph:
    edges: list[ValidationFrontierLineageEdge] = []
    for execution in evaluation.executions:
        record = fixture.record_map()[execution.record_id]
        for source_id in record.source_ids:
            body = {"edge_kind": "source_to_execution", "source_node": f"source:{source_id}", "target_node": f"execution:{execution.record_id}"}
            edges.append(ValidationFrontierLineageEdge(f"source:{source_id}:{execution.record_id}", **{key: body[key] for key in ("edge_kind", "source_node", "target_node")}, content_address=content_hash(body)))
        body = {"edge_kind": "fixture_to_execution", "source_node": f"record:{record.record_id}", "target_node": f"execution:{execution.record_id}"}
        edges.append(ValidationFrontierLineageEdge(f"record:{record.record_id}", **{key: body[key] for key in ("edge_kind", "source_node", "target_node")}, content_address=content_hash(body)))
    body = {"edges": tuple(edges), "terminal_addresses": tuple(item.content_address for item in evaluation.executions), "acyclic": True}
    return ValidationFrontierLineageGraph(**body, content_address=content_hash(body))


__all__ = ["ValidationFrontierLineageEdge", "ValidationFrontierLineageGraph", "build_validation_frontier_lineage"]
