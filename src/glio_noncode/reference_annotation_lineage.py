"""Canonical source-to-result lineage graph for C05–C08."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .reference_annotation_fixture_eval import ReferenceAnnotationEvaluationReport
from .reference_annotation_public_data import (
    ReferenceAnnotationFixture,
    default_reference_annotation_fixture,
)
from .serialization import content_hash, jsonable, require_non_empty


class ReferenceAnnotationNodeKind(StrEnum):
    SOURCE = "source"
    FIXTURE = "fixture"
    RECORD = "record"
    RESULT = "result"


class ReferenceAnnotationEdgeKind(StrEnum):
    DECLARES = "declares"
    CONTAINS = "contains"
    PRODUCES = "produces"


@dataclass(frozen=True, slots=True)
class ReferenceAnnotationLineageNode:
    node_id: str
    kind: ReferenceAnnotationNodeKind
    content_address: str
    context_key: str
    attributes: dict[str, Any]

    def __post_init__(self) -> None:
        for name in ("node_id", "content_address", "context_key"):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceAnnotationLineageEdge:
    edge_id: str
    source_node: str
    target_node: str
    kind: ReferenceAnnotationEdgeKind
    context_key: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("edge_id", "source_node", "target_node", "context_key", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if self.source_node == self.target_node:
            raise ValidationError("annotation lineage cannot contain self edges")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceAnnotationLineageAudit:
    checks: tuple[dict[str, Any], ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(check["passed"] for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check["check_id"] for check in self.checks if not check["passed"])

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "failed_check_ids": list(self.failed_check_ids),
        }


@dataclass(frozen=True, slots=True)
class ReferenceAnnotationLineageGraph:
    graph_id: str
    context_key: str
    nodes: tuple[ReferenceAnnotationLineageNode, ...]
    edges: tuple[ReferenceAnnotationLineageEdge, ...]
    audit: ReferenceAnnotationLineageAudit
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"node_count": len(self.nodes), "edge_count": len(self.edges)}


def _address(body: Any) -> str:
    return content_hash(body)


def _node(
    node_id: str,
    kind: ReferenceAnnotationNodeKind,
    context_key: str,
    address: str,
    attributes: dict[str, Any],
) -> ReferenceAnnotationLineageNode:
    body = {
        "node_id": node_id,
        "kind": kind,
        "content_address": address,
        "context_key": context_key,
        "attributes": attributes,
    }
    return ReferenceAnnotationLineageNode(**body)


def _edge(
    source_node: str, target_node: str, kind: ReferenceAnnotationEdgeKind, context_key: str
) -> ReferenceAnnotationLineageEdge:
    body = {
        "edge_id": f"{source_node}:{kind.value}:{target_node}",
        "source_node": source_node,
        "target_node": target_node,
        "kind": kind,
        "context_key": context_key,
    }
    return ReferenceAnnotationLineageEdge(**body, content_address=_address(body))


def build_reference_annotation_lineage(
    report: ReferenceAnnotationEvaluationReport,
    *,
    fixture: ReferenceAnnotationFixture | None = None,
    graph_id: str = "reference-annotation-lineage",
) -> ReferenceAnnotationLineageGraph:
    selected = fixture or default_reference_annotation_fixture()
    nodes: list[ReferenceAnnotationLineageNode] = []
    edges: list[ReferenceAnnotationLineageEdge] = []
    fixture_node = _node(
        selected.fixture_id,
        ReferenceAnnotationNodeKind.FIXTURE,
        selected.context_key,
        selected.content_address,
        {"fixture_version": selected.fixture_version},
    )
    nodes.append(fixture_node)
    for source in selected.sources:
        node = _node(
            source.source_id,
            ReferenceAnnotationNodeKind.SOURCE,
            selected.context_key,
            source.content_address,
            {"uri": source.uri, "release": source.release},
        )
        nodes.append(node)
        edges.append(
            _edge(
                source.source_id,
                selected.fixture_id,
                ReferenceAnnotationEdgeKind.DECLARES,
                selected.context_key,
            )
        )
    receipt_by_id = {receipt.record_id: receipt for receipt in report.receipts}
    for record in selected.records:
        record_node = _node(
            record.record_id,
            ReferenceAnnotationNodeKind.RECORD,
            record.context_key,
            record.content_address,
            {"operation": record.operation, "role": record.role},
        )
        nodes.append(record_node)
        edges.append(
            _edge(
                selected.fixture_id,
                record.record_id,
                ReferenceAnnotationEdgeKind.CONTAINS,
                selected.context_key,
            )
        )
        for source_id in record.source_ids:
            edges.append(
                _edge(
                    source_id,
                    record.record_id,
                    ReferenceAnnotationEdgeKind.DECLARES,
                    selected.context_key,
                )
            )
        receipt = receipt_by_id.get(record.record_id)
        if receipt is not None:
            result_id = f"result:{receipt.record_id}"
            nodes.append(
                _node(
                    result_id,
                    ReferenceAnnotationNodeKind.RESULT,
                    receipt.context_key,
                    receipt.content_address,
                    {"state": receipt.resolution_state, "capability_id": receipt.capability_id},
                )
            )
            edges.append(
                _edge(
                    record.record_id,
                    result_id,
                    ReferenceAnnotationEdgeKind.PRODUCES,
                    selected.context_key,
                )
            )
    node_ids = [node.node_id for node in nodes]
    edge_ids = [edge.edge_id for edge in edges]
    checks: list[dict[str, Any]] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        checks.append(
            {
                "check_id": check_id,
                "passed": passed,
                "detail": detail,
                "content_address": _address(
                    {"check_id": check_id, "passed": passed, "detail": detail}
                ),
            }
        )

    add("node-identity", len(node_ids) == len(set(node_ids)), "lineage node identities are unique")
    add("edge-identity", len(edge_ids) == len(set(edge_ids)), "lineage edge identities are unique")
    add(
        "context-closure",
        all(node.context_key == selected.context_key for node in nodes)
        and all(edge.context_key == selected.context_key for edge in edges),
        "all lineage objects share fixture context",
    )
    add(
        "source-count",
        sum(node.kind is ReferenceAnnotationNodeKind.SOURCE for node in nodes)
        == len(selected.sources),
        "every source has one node",
    )
    add(
        "record-count",
        sum(node.kind is ReferenceAnnotationNodeKind.RECORD for node in nodes)
        == len(selected.records),
        "every record has one node",
    )
    add(
        "result-count",
        sum(node.kind is ReferenceAnnotationNodeKind.RESULT for node in nodes)
        == len(report.receipts),
        "every receipt has one result node",
    )
    add(
        "fixture-node",
        sum(node.node_id == selected.fixture_id for node in nodes) == 1,
        "fixture node is present once",
    )
    add(
        "source-edges",
        sum(
            edge.kind is ReferenceAnnotationEdgeKind.DECLARES
            and edge.target_node == selected.fixture_id
            for edge in edges
        )
        == len(selected.sources),
        "source declaration edges close over receipts",
    )
    add(
        "record-edges",
        sum(edge.kind is ReferenceAnnotationEdgeKind.CONTAINS for edge in edges)
        == len(selected.records),
        "fixture contains every record",
    )
    add(
        "result-edges",
        sum(edge.kind is ReferenceAnnotationEdgeKind.PRODUCES for edge in edges)
        == len(report.receipts),
        "records produce every result",
    )
    add(
        "edge-count",
        len(edges)
        == len(selected.sources)
        + len(selected.records)
        + len(report.receipts)
        + sum(len(record.source_ids) for record in selected.records),
        "edge count matches declared topology",
    )
    add(
        "address-preservation",
        all(node.content_address for node in nodes) and all(edge.content_address for edge in edges),
        "all graph elements retain addresses",
    )
    audit_body = {"checks": checks}
    audit = ReferenceAnnotationLineageAudit(tuple(checks), _address(audit_body))
    graph_body = {
        "graph_id": graph_id,
        "context_key": selected.context_key,
        "nodes": nodes,
        "edges": edges,
        "audit": audit,
    }
    return ReferenceAnnotationLineageGraph(
        graph_id, selected.context_key, tuple(nodes), tuple(edges), audit, _address(graph_body)
    )


__all__ = [
    "ReferenceAnnotationEdgeKind",
    "ReferenceAnnotationLineageAudit",
    "ReferenceAnnotationLineageEdge",
    "ReferenceAnnotationLineageGraph",
    "ReferenceAnnotationLineageNode",
    "ReferenceAnnotationNodeKind",
    "build_reference_annotation_lineage",
]
