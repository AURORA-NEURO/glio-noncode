"""Append-only lineage graph for Domain 04 coordinate evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .reference_coordinate_fixture_eval import evaluate_reference_coordinate_fixture
from .reference_coordinate_public_data import ReferenceCoordinateFixtureCatalog
from .serialization import content_hash, jsonable, require_non_empty


class ReferenceCoordinateNodeKind(StrEnum):
    SOURCE = "source"
    FIXTURE = "fixture"
    RECORD = "record"
    RESULT = "result"


class ReferenceCoordinateEdgeKind(StrEnum):
    DECLARES = "declares"
    CONTAINS = "contains"
    PRODUCES = "produces"


@dataclass(frozen=True, slots=True)
class ReferenceCoordinateLineageNode:
    node_id: str
    kind: ReferenceCoordinateNodeKind
    label: str
    content_address: str
    attributes: dict[str, Any]

    def __post_init__(self) -> None:
        require_non_empty(self.node_id, "lineage node ID")
        require_non_empty(self.label, "lineage node label")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("lineage node must be addressed")
        forbidden = {"payload", "chain_text", "patient_id", "subject_id", "secret"}
        if any(key.lower() in forbidden for key in self.attributes):
            raise ValidationError("lineage node has a forbidden raw attribute")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceCoordinateLineageEdge:
    edge_id: str
    source_node_id: str
    target_node_id: str
    kind: ReferenceCoordinateEdgeKind
    content_address: str

    def __post_init__(self) -> None:
        for field in ("edge_id", "source_node_id", "target_node_id"):
            require_non_empty(str(getattr(self, field)), f"lineage edge {field}")
        if self.source_node_id == self.target_node_id:
            raise ValidationError("lineage edge cannot be self-referential")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("lineage edge must be addressed")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceCoordinateLineageAudit:
    state: str
    checks: tuple[dict[str, Any], ...]
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == "accepted" and all(bool(check["passed"]) for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check["check_id"] for check in self.checks if not bool(check["passed"]))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed": self.passed}


@dataclass(frozen=True, slots=True)
class ReferenceCoordinateLineageGraph:
    fixture_id: str
    context_key: str
    nodes: tuple[ReferenceCoordinateLineageNode, ...]
    edges: tuple[ReferenceCoordinateLineageEdge, ...]
    content_address: str

    def __post_init__(self) -> None:
        if not self.nodes:
            raise ValidationError("lineage graph requires nodes")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("lineage graph must be addressed")

    @property
    def node_ids(self) -> tuple[str, ...]:
        return tuple(node.node_id for node in self.nodes)

    def node(self, node_id: str) -> ReferenceCoordinateLineageNode:
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        raise ValidationError(f"unknown lineage node: {node_id}")

    def audit(self, catalog: ReferenceCoordinateFixtureCatalog) -> ReferenceCoordinateLineageAudit:
        checks: list[dict[str, Any]] = []

        def add(check_id: str, passed: bool, observed: Any, expected: Any, message: str) -> None:
            checks.append(
                {
                    "check_id": check_id,
                    "passed": bool(passed),
                    "observed": observed,
                    "expected": expected,
                    "message": message,
                }
            )

        node_ids = self.node_ids
        node_by_id = {node.node_id: node for node in self.nodes}
        add(
            "node-identity",
            len(set(node_ids)) == len(node_ids),
            node_ids,
            "unique node IDs",
            "node IDs are unique",
        )
        add(
            "edge-identity",
            len({edge.edge_id for edge in self.edges}) == len(self.edges),
            True,
            True,
            "edge IDs are unique",
        )
        add(
            "edge-targets",
            all(
                edge.source_node_id in node_by_id and edge.target_node_id in node_by_id
                for edge in self.edges
            ),
            True,
            True,
            "edges have valid endpoints",
        )
        add(
            "fixture-node",
            sum(node.kind == ReferenceCoordinateNodeKind.FIXTURE for node in self.nodes) == 1,
            sum(node.kind == ReferenceCoordinateNodeKind.FIXTURE for node in self.nodes),
            1,
            "one fixture root exists",
        )
        add(
            "source-floor",
            sum(node.kind == ReferenceCoordinateNodeKind.SOURCE for node in self.nodes)
            == len(catalog.source_receipts),
            sum(node.kind == ReferenceCoordinateNodeKind.SOURCE for node in self.nodes),
            len(catalog.source_receipts),
            "all source receipts have nodes",
        )
        add(
            "record-floor",
            sum(node.kind == ReferenceCoordinateNodeKind.RECORD for node in self.nodes)
            == len(catalog.records),
            sum(node.kind == ReferenceCoordinateNodeKind.RECORD for node in self.nodes),
            len(catalog.records),
            "all records have nodes",
        )
        add(
            "result-floor",
            sum(node.kind == ReferenceCoordinateNodeKind.RESULT for node in self.nodes)
            == len(catalog.records),
            sum(node.kind == ReferenceCoordinateNodeKind.RESULT for node in self.nodes),
            len(catalog.records),
            "all records have result nodes",
        )
        add(
            "context",
            all(
                node.attributes.get("context_key") in {None, self.context_key}
                for node in self.nodes
            ),
            True,
            True,
            "context is retained on contextual nodes",
        )
        add(
            "source-edges",
            all(
                any(
                    edge.kind == ReferenceCoordinateEdgeKind.DECLARES
                    and edge.source_node_id == f"source:{source.source_id}"
                    for edge in self.edges
                )
                for source in catalog.source_receipts
            ),
            True,
            True,
            "source declaration edges exist",
        )
        add(
            "record-edges",
            all(
                any(
                    edge.kind == ReferenceCoordinateEdgeKind.CONTAINS
                    and edge.target_node_id == f"record:{record.record_id}"
                    for edge in self.edges
                )
                for record in catalog.records
            ),
            True,
            True,
            "fixture contains every record",
        )
        add(
            "result-edges",
            all(
                any(
                    edge.kind == ReferenceCoordinateEdgeKind.PRODUCES
                    and edge.source_node_id == f"record:{record.record_id}"
                    for edge in self.edges
                )
                for record in catalog.records
            ),
            True,
            True,
            "every record produces a result",
        )
        add(
            "edge-count",
            len(self.edges) == len(catalog.source_receipts) + 2 * len(catalog.records),
            len(self.edges),
            len(catalog.source_receipts) + 2 * len(catalog.records),
            "typed edge count is conserved",
        )
        add(
            "source-addresses",
            all(node.content_address.startswith("sha256:") for node in self.nodes),
            True,
            True,
            "all nodes are addressed",
        )
        add(
            "edge-addresses",
            all(edge.content_address.startswith("sha256:") for edge in self.edges),
            True,
            True,
            "all edges are addressed",
        )
        add(
            "graph-address",
            self.content_address
            == content_hash(
                {
                    "fixture_id": self.fixture_id,
                    "context_key": self.context_key,
                    "nodes": self.nodes,
                    "edges": self.edges,
                }
            ),
            self.content_address,
            "sha256:<recomputed>",
            "graph address is deterministic",
        )
        state = "accepted" if all(bool(check["passed"]) for check in checks) else "review"
        body = {"state": state, "checks": checks, "graph_address": self.content_address}
        return ReferenceCoordinateLineageAudit(state, tuple(checks), content_hash(body))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
        }


def _node(
    node_id: str,
    kind: ReferenceCoordinateNodeKind,
    label: str,
    attributes: dict[str, Any],
) -> ReferenceCoordinateLineageNode:
    body = {"node_id": node_id, "kind": kind, "label": label, "attributes": attributes}
    return ReferenceCoordinateLineageNode(
        node_id=node_id,
        kind=kind,
        label=label,
        content_address=content_hash(body),
        attributes=attributes,
    )


def _edge(
    edge_id: str,
    source_node_id: str,
    target_node_id: str,
    kind: ReferenceCoordinateEdgeKind,
) -> ReferenceCoordinateLineageEdge:
    body = {
        "edge_id": edge_id,
        "source_node_id": source_node_id,
        "target_node_id": target_node_id,
        "kind": kind,
    }
    return ReferenceCoordinateLineageEdge(
        edge_id=edge_id,
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        kind=kind,
        content_address=content_hash(body),
    )


def build_reference_coordinate_lineage(
    catalog: ReferenceCoordinateFixtureCatalog,
) -> ReferenceCoordinateLineageGraph:
    """Build source -> fixture -> record -> sanitized result lineage."""

    evaluation = evaluate_reference_coordinate_fixture(catalog)
    nodes: list[ReferenceCoordinateLineageNode] = []
    edges: list[ReferenceCoordinateLineageEdge] = []
    for source in catalog.source_receipts:
        nodes.append(
            _node(
                f"source:{source.source_id}",
                ReferenceCoordinateNodeKind.SOURCE,
                source.title,
                {
                    "source_id": source.source_id,
                    "uri": source.uri,
                    "scope": source.scope,
                    "patient_level": source.patient_level,
                    "content_address": source.content_address,
                },
            )
        )
    fixture_node_id = f"fixture:{catalog.fixture_id}"
    nodes.append(
        _node(
            fixture_node_id,
            ReferenceCoordinateNodeKind.FIXTURE,
            catalog.fixture_id,
            {
                "fixture_id": catalog.fixture_id,
                "fixture_version": catalog.fixture_version,
                "context_key": catalog.context_key,
                "content_address": catalog.content_address,
            },
        )
    )
    for source in catalog.source_receipts:
        edges.append(
            _edge(
                f"declares:{source.source_id}",
                f"source:{source.source_id}",
                fixture_node_id,
                ReferenceCoordinateEdgeKind.DECLARES,
            )
        )
    for record in catalog.records:
        record_node_id = f"record:{record.record_id}"
        nodes.append(
            _node(
                record_node_id,
                ReferenceCoordinateNodeKind.RECORD,
                record.record_id,
                {
                    "record_id": record.record_id,
                    "operation": record.operation.value,
                    "role": record.role.value,
                    "expected_state": record.expected_state.value,
                    "context_key": record.context_key,
                    "source_ids": record.source_ids,
                    "content_address": record.content_address,
                },
            )
        )
        edges.append(
            _edge(
                f"contains:{record.record_id}",
                fixture_node_id,
                record_node_id,
                ReferenceCoordinateEdgeKind.CONTAINS,
            )
        )
    for receipt in evaluation.receipts:
        result_node_id = f"result:{receipt.record_id}"
        nodes.append(
            _node(
                result_node_id,
                ReferenceCoordinateNodeKind.RESULT,
                f"{receipt.operation.value}:{receipt.record_id}",
                {
                    "record_id": receipt.record_id,
                    "operation": receipt.operation.value,
                    "role": receipt.role.value,
                    "state": receipt.state.value,
                    "issue_codes": receipt.issue_codes,
                    "context_key": receipt.context_key,
                    "source_ids": receipt.source_ids,
                    "receipt_address": receipt.content_address,
                },
            )
        )
        edges.append(
            _edge(
                f"produces:{receipt.record_id}",
                f"record:{receipt.record_id}",
                result_node_id,
                ReferenceCoordinateEdgeKind.PRODUCES,
            )
        )
    body = {
        "fixture_id": catalog.fixture_id,
        "context_key": catalog.context_key,
        "nodes": tuple(nodes),
        "edges": tuple(edges),
    }
    return ReferenceCoordinateLineageGraph(
        fixture_id=catalog.fixture_id,
        context_key=catalog.context_key,
        nodes=tuple(nodes),
        edges=tuple(edges),
        content_address=content_hash(body),
    )


__all__ = [
    "ReferenceCoordinateEdgeKind",
    "ReferenceCoordinateLineageAudit",
    "ReferenceCoordinateLineageEdge",
    "ReferenceCoordinateLineageGraph",
    "ReferenceCoordinateLineageNode",
    "ReferenceCoordinateNodeKind",
    "build_reference_coordinate_lineage",
]
