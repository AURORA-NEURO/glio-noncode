"""Sanitized source-to-result lineage for Domain 05 C05–C08."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .molecular_atlas_fixture_eval import MolecularAtlasEvaluationReport
from .molecular_atlas_public_data import MolecularAtlasFixture
from .serialization import content_hash, jsonable, require_non_empty


class MolecularAtlasNodeKind(StrEnum):
    """Node classes retained in the lineage graph."""

    SOURCE = "source"
    RECORD = "record"
    RECEIPT = "receipt"
    CHECK = "check"


class MolecularAtlasEdgeKind(StrEnum):
    """Directed relation classes between lineage nodes."""

    DECLARES = "declares"
    EXECUTES = "executes"
    VERIFIES = "verifies"


@dataclass(frozen=True, slots=True)
class MolecularAtlasLineageNode:
    """One stable node with bounded, non-payload attributes."""

    node_id: str
    kind: MolecularAtlasNodeKind
    label: str
    content_address: str
    attributes: dict[str, Any]

    def __post_init__(self) -> None:
        require_non_empty(self.node_id, "molecular atlas lineage node id")
        require_non_empty(self.label, "molecular atlas lineage node label")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MolecularAtlasLineageEdge:
    """One directed edge whose endpoints must exist."""

    edge_id: str
    source_node_id: str
    target_node_id: str
    kind: MolecularAtlasEdgeKind
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MolecularAtlasLineageAudit:
    """Closure, coverage, address, and sanitization checks."""

    passed: bool
    checks: tuple[tuple[str, bool, str], ...]
    node_count: int
    edge_count: int
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check_id for check_id, passed, _ in self.checks if not passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_check_ids": list(self.failed_check_ids)}


@dataclass(frozen=True, slots=True)
class MolecularAtlasLineageGraph:
    """Deterministic source, record, receipt, and check graph."""

    fixture_id: str
    nodes: tuple[MolecularAtlasLineageNode, ...]
    edges: tuple[MolecularAtlasLineageEdge, ...]
    content_address: str

    def audit(self, evaluation: MolecularAtlasEvaluationReport) -> MolecularAtlasLineageAudit:
        node_ids = {node.node_id for node in self.nodes}
        edge_ids = {edge.edge_id for edge in self.edges}
        checks: list[tuple[str, bool, str]] = [
            ("node-ids", len(node_ids) == len(self.nodes), "node identities are unique"),
            ("edge-ids", len(edge_ids) == len(self.edges), "edge identities are unique"),
            (
                "edge-closure",
                all(
                    edge.source_node_id in node_ids and edge.target_node_id in node_ids
                    for edge in self.edges
                ),
                "every edge endpoint exists",
            ),
            (
                "source-coverage",
                sum(node.kind is MolecularAtlasNodeKind.SOURCE for node in self.nodes) == 5,
                "five public source nodes are retained",
            ),
            (
                "record-coverage",
                sum(node.kind is MolecularAtlasNodeKind.RECORD for node in self.nodes)
                == len(evaluation.receipts),
                "one record node exists per receipt",
            ),
            (
                "receipt-coverage",
                sum(node.kind is MolecularAtlasNodeKind.RECEIPT for node in self.nodes)
                == len(evaluation.receipts),
                "one receipt node exists per record",
            ),
            (
                "check-coverage",
                sum(node.kind is MolecularAtlasNodeKind.CHECK for node in self.nodes)
                == len(evaluation.checks),
                "one check node exists per evaluation check",
            ),
            (
                "fixture-id",
                self.fixture_id == evaluation.fixture_id,
                "graph and evaluation share fixture identity",
            ),
            (
                "address",
                self.content_address
                == _address(
                    {"fixture_id": self.fixture_id, "nodes": self.nodes, "edges": self.edges}
                ),
                "graph content address verifies",
            ),
            (
                "sanitized",
                all(
                    not {"payload", "input_text", "records", "restrictions"} & set(node.attributes)
                    for node in self.nodes
                ),
                "graph nodes do not copy payload collections",
            ),
            (
                "positive-receipts",
                all(
                    node.attributes.get("state") == "supported"
                    for node in self.nodes
                    if node.kind is MolecularAtlasNodeKind.RECEIPT
                    and node.attributes.get("role") == "positive"
                ),
                "positive receipts remain supported",
            ),
        ]
        passed = all(item[1] for item in checks)
        body = {
            "passed": passed,
            "checks": checks,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
        }
        return MolecularAtlasLineageAudit(
            passed, tuple(checks), len(self.nodes), len(self.edges), _address(body)
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _address(body: Any) -> str:
    return content_hash(body)


def _node(
    node_id: str, kind: MolecularAtlasNodeKind, label: str, attributes: dict[str, Any]
) -> MolecularAtlasLineageNode:
    body = {"node_id": node_id, "kind": kind, "label": label, "attributes": attributes}
    return MolecularAtlasLineageNode(**body, content_address=_address(body))


def _edge(
    edge_id: str, source: str, target: str, kind: MolecularAtlasEdgeKind
) -> MolecularAtlasLineageEdge:
    body = {"edge_id": edge_id, "source_node_id": source, "target_node_id": target, "kind": kind}
    return MolecularAtlasLineageEdge(**body, content_address=_address(body))


def build_molecular_atlas_lineage(
    evaluation: MolecularAtlasEvaluationReport,
    *,
    fixture: MolecularAtlasFixture,
) -> MolecularAtlasLineageGraph:
    """Build a graph without copying executable payloads into lineage."""

    nodes: list[MolecularAtlasLineageNode] = []
    edges: list[MolecularAtlasLineageEdge] = []
    source_map = fixture.source_map()
    for source in fixture.sources:
        nodes.append(
            _node(
                f"source:{source.source_id}",
                MolecularAtlasNodeKind.SOURCE,
                source.title,
                {
                    "source_id": source.source_id,
                    "uri": source.uri,
                    "release": source.release,
                    "scope": source.scope,
                },
            )
        )
    for record in fixture.records:
        nodes.append(
            _node(
                f"record:{record.record_id}",
                MolecularAtlasNodeKind.RECORD,
                record.record_id,
                {
                    "record_id": record.record_id,
                    "operation": record.operation,
                    "role": record.role,
                    "source_ids": record.source_ids,
                },
            )
        )
        for source_id in record.source_ids:
            if source_id in source_map:
                edges.append(
                    _edge(
                        f"declares:{source_id}:{record.record_id}",
                        f"source:{source_id}",
                        f"record:{record.record_id}",
                        MolecularAtlasEdgeKind.DECLARES,
                    )
                )
    receipt_ids = {receipt.record_id for receipt in evaluation.receipts}
    for receipt in evaluation.receipts:
        nodes.append(
            _node(
                f"receipt:{receipt.record_id}",
                MolecularAtlasNodeKind.RECEIPT,
                receipt.record_id,
                {
                    "record_id": receipt.record_id,
                    "operation": receipt.operation,
                    "role": receipt.role,
                    "state": receipt.adapter_state,
                    "primary_count": receipt.primary_count,
                    "secondary_count": receipt.secondary_count,
                    "content_address": receipt.content_address,
                },
            )
        )
        edges.append(
            _edge(
                f"executes:{receipt.record_id}",
                f"record:{receipt.record_id}",
                f"receipt:{receipt.record_id}",
                MolecularAtlasEdgeKind.EXECUTES,
            )
        )
    fallback = f"source:{fixture.sources[0].source_id}"
    for check in evaluation.checks:
        check_id = f"{check.record_id}:{check.check_id}"
        nodes.append(
            _node(
                f"check:{check_id}",
                MolecularAtlasNodeKind.CHECK,
                check.check_id,
                {"check_id": check.check_id, "record_id": check.record_id, "passed": check.passed},
            )
        )
        target = f"receipt:{check.record_id}" if check.record_id in receipt_ids else fallback
        edges.append(
            _edge(
                f"verifies:{check_id}", target, f"check:{check_id}", MolecularAtlasEdgeKind.VERIFIES
            )
        )
    body = {"fixture_id": fixture.fixture_id, "nodes": nodes, "edges": edges}
    return MolecularAtlasLineageGraph(
        fixture.fixture_id, tuple(nodes), tuple(edges), _address(body)
    )


__all__ = [
    "MolecularAtlasEdgeKind",
    "MolecularAtlasLineageAudit",
    "MolecularAtlasLineageEdge",
    "MolecularAtlasLineageGraph",
    "MolecularAtlasLineageNode",
    "MolecularAtlasNodeKind",
    "build_molecular_atlas_lineage",
]
