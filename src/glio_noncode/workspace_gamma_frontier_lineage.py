"""Source-to-record-to-execution lineage for the collaboration frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_gamma_frontier_fixture_eval import GammaFrontierEvaluation
from .workspace_gamma_frontier_public_data import GammaFrontierFixture


@dataclass(frozen=True, slots=True)
class GammaFrontierLineageEdge:
    """One directed relationship between content-addressed nodes."""

    edge_id: str
    parent_address: str
    child_address: str
    relation: str
    record_id: str | None
    operation: str | None
    content_address: str

    def __post_init__(self) -> None:
        for name in ("edge_id", "parent_address", "child_address", "relation", "content_address"):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierLineageGraph:
    """Immutable lineage graph with parent/child lookup."""

    fixture_id: str
    nodes: tuple[str, ...]
    edges: tuple[GammaFrontierLineageEdge, ...]
    content_address: str

    def children_of(self, address: str) -> tuple[str, ...]:
        return tuple(edge.child_address for edge in self.edges if edge.parent_address == address)

    def parents_of(self, address: str) -> tuple[str, ...]:
        return tuple(edge.parent_address for edge in self.edges if edge.child_address == address)

    def edges_for_record(self, record_id: str) -> tuple[GammaFrontierLineageEdge, ...]:
        return tuple(edge for edge in self.edges if edge.record_id == record_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"node_count": len(self.nodes), "edge_count": len(self.edges)}


def _edge(
    index: int, parent: str, child: str, relation: str, record_id: str | None, operation: str | None
) -> GammaFrontierLineageEdge:
    body = {
        "edge_id": f"gamma-lineage-edge-{index:04d}",
        "parent_address": parent,
        "child_address": child,
        "relation": relation,
        "record_id": record_id,
        "operation": operation,
    }
    return GammaFrontierLineageEdge(**body, content_address=content_hash(body))


def build_gamma_frontier_lineage(
    fixture: GammaFrontierFixture, evaluation: GammaFrontierEvaluation
) -> GammaFrontierLineageGraph:
    """Connect source receipts, fixture rows, executions, and outputs."""

    nodes: set[str] = {fixture.content_address}
    edges: list[GammaFrontierLineageEdge] = []
    index = 1
    source_addresses = {item.source_id: item.content_address for item in fixture.sources}
    for source in fixture.sources:
        nodes.add(source.content_address)
        edges.append(
            _edge(
                index,
                source.content_address,
                fixture.content_address,
                "source_receipt_of_fixture",
                None,
                None,
            )
        )
        index += 1
    for record, execution in zip(fixture.records, evaluation.executions, strict=True):
        nodes.update((record.content_address, execution.content_address))
        for source_id in record.source_ids:
            if source_id in source_addresses:
                edges.append(
                    _edge(
                        index,
                        source_addresses[source_id],
                        record.content_address,
                        "source_receipt_of_record",
                        record.record_id,
                        record.operation.value,
                    )
                )
                index += 1
        edges.append(
            _edge(
                index,
                fixture.content_address,
                record.content_address,
                "fixture_contains_record",
                record.record_id,
                record.operation.value,
            )
        )
        index += 1
        edges.append(
            _edge(
                index,
                record.content_address,
                execution.content_address,
                "record_produces_execution",
                record.record_id,
                record.operation.value,
            )
        )
        index += 1
        for key, value in execution.output.items():
            if key in {"state", "issues", "policy_receipts"} or isinstance(value, (tuple, list)):
                address = content_hash(
                    {"execution": execution.content_address, "field": key, "value": value},
                    prefix="output",
                )
                nodes.add(address)
                edges.append(
                    _edge(
                        index,
                        execution.content_address,
                        address,
                        f"emits_{key}",
                        record.record_id,
                        record.operation.value,
                    )
                )
                index += 1
    ordered_nodes = tuple(sorted(nodes))
    body = {"fixture_id": fixture.fixture_id, "nodes": ordered_nodes, "edges": tuple(edges)}
    return GammaFrontierLineageGraph(**body, content_address=content_hash(body))


__all__ = ["GammaFrontierLineageEdge", "GammaFrontierLineageGraph", "build_gamma_frontier_lineage"]
