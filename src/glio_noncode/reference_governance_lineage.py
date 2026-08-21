"""Sanitized source-to-result lineage for Domain 04 C09–C12."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .reference_governance_fixture_eval import ReferenceGovernanceEvaluationReport
from .reference_governance_public_data import ReferenceGovernanceFixture
from .serialization import content_hash, jsonable, require_non_empty


class ReferenceGovernanceNodeKind(StrEnum):
    """Node classes retained in the sanitized lineage graph."""

    SOURCE = "source"
    RECORD = "record"
    RECEIPT = "receipt"
    CHECK = "check"


class ReferenceGovernanceEdgeKind(StrEnum):
    """Directed relation classes between lineage nodes."""

    DECLARES = "declares"
    EXECUTES = "executes"
    VERIFIES = "verifies"


@dataclass(frozen=True, slots=True)
class ReferenceGovernanceLineageNode:
    """One node with a stable address and non-sensitive summary."""

    node_id: str
    kind: ReferenceGovernanceNodeKind
    label: str
    content_address: str
    attributes: dict[str, Any]

    def __post_init__(self) -> None:
        require_non_empty(self.node_id, "node_id")
        require_non_empty(self.label, "label")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceGovernanceLineageEdge:
    """One directed edge between existing node identities."""

    edge_id: str
    source_node_id: str
    target_node_id: str
    kind: ReferenceGovernanceEdgeKind
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceGovernanceLineageAudit:
    """Graph closure and sanitization audit."""

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
class ReferenceGovernanceLineageGraph:
    """Deterministic directed graph from public receipt to result checks."""

    fixture_id: str
    nodes: tuple[ReferenceGovernanceLineageNode, ...]
    edges: tuple[ReferenceGovernanceLineageEdge, ...]
    content_address: str

    def audit(
        self, evaluation: ReferenceGovernanceEvaluationReport
    ) -> ReferenceGovernanceLineageAudit:
        checks: list[tuple[str, bool, str]] = []
        node_ids = {node.node_id for node in self.nodes}
        edge_ids = {edge.edge_id for edge in self.edges}
        checks.append(("node-ids", len(node_ids) == len(self.nodes), "node identities are unique"))
        checks.append(("edge-ids", len(edge_ids) == len(self.edges), "edge identities are unique"))
        checks.append(
            (
                "edge-closure",
                all(
                    edge.source_node_id in node_ids and edge.target_node_id in node_ids
                    for edge in self.edges
                ),
                "every edge endpoint exists",
            )
        )
        checks.append(
            (
                "source-coverage",
                sum(node.kind is ReferenceGovernanceNodeKind.SOURCE for node in self.nodes) == 5,
                "five source nodes are retained",
            )
        )
        checks.append(
            (
                "record-coverage",
                sum(node.kind is ReferenceGovernanceNodeKind.RECORD for node in self.nodes)
                == len(evaluation.receipts),
                "one record node exists per receipt",
            )
        )
        checks.append(
            (
                "receipt-coverage",
                sum(node.kind is ReferenceGovernanceNodeKind.RECEIPT for node in self.nodes)
                == len(evaluation.receipts),
                "one receipt node exists per receipt",
            )
        )
        checks.append(
            (
                "check-coverage",
                sum(node.kind is ReferenceGovernanceNodeKind.CHECK for node in self.nodes)
                == len(evaluation.checks),
                "one check node exists per evaluation check",
            )
        )
        checks.append(
            (
                "fixture-id",
                self.fixture_id == evaluation.fixture_id,
                "graph and evaluation share fixture identity",
            )
        )
        checks.append(
            (
                "address",
                self.content_address
                == _address(
                    {"fixture_id": self.fixture_id, "nodes": self.nodes, "edges": self.edges}
                ),
                "graph address verifies",
            )
        )
        checks.append(
            (
                "sanitized",
                all(
                    "payload" not in node.attributes
                    and "records" not in node.attributes
                    and "restrictions" not in node.attributes
                    for node in self.nodes
                ),
                "graph nodes do not copy input collections",
            )
        )
        checks.append(
            (
                "positive-receipts",
                all(
                    node.attributes.get("state") == "supported"
                    for node in self.nodes
                    if node.kind is ReferenceGovernanceNodeKind.RECEIPT
                    and node.attributes.get("role") == "positive"
                ),
                "positive receipts remain supported",
            )
        )
        passed = all(item[1] for item in checks)
        body = {
            "passed": passed,
            "checks": checks,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
        }
        return ReferenceGovernanceLineageAudit(
            passed, tuple(checks), len(self.nodes), len(self.edges), _address(body)
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _address(body: Any) -> str:
    return content_hash(body)


def _node(
    node_id: str, kind: ReferenceGovernanceNodeKind, label: str, attributes: dict[str, Any]
) -> ReferenceGovernanceLineageNode:
    body = {"node_id": node_id, "kind": kind, "label": label, "attributes": attributes}
    return ReferenceGovernanceLineageNode(**body, content_address=_address(body))


def _edge(
    edge_id: str, source: str, target: str, kind: ReferenceGovernanceEdgeKind
) -> ReferenceGovernanceLineageEdge:
    body = {"edge_id": edge_id, "source_node_id": source, "target_node_id": target, "kind": kind}
    return ReferenceGovernanceLineageEdge(**body, content_address=_address(body))


def build_reference_governance_lineage(
    evaluation: ReferenceGovernanceEvaluationReport,
    *,
    fixture: ReferenceGovernanceFixture,
) -> ReferenceGovernanceLineageGraph:
    """Build a source-to-record-to-receipt-to-check graph."""

    nodes: list[ReferenceGovernanceLineageNode] = []
    edges: list[ReferenceGovernanceLineageEdge] = []
    source_map = fixture.source_map()
    for source in fixture.sources:
        nodes.append(
            _node(
                f"source:{source.source_id}",
                ReferenceGovernanceNodeKind.SOURCE,
                source.title,
                {
                    "source_id": source.source_id,
                    "uri": source.uri,
                    "release": source.release,
                    "license": source.license,
                },
            )
        )
    for record in fixture.records:
        nodes.append(
            _node(
                f"record:{record.record_id}",
                ReferenceGovernanceNodeKind.RECORD,
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
                        ReferenceGovernanceEdgeKind.DECLARES,
                    )
                )
    receipt_map = {receipt.record_id: receipt for receipt in evaluation.receipts}
    for receipt in evaluation.receipts:
        nodes.append(
            _node(
                f"receipt:{receipt.record_id}",
                ReferenceGovernanceNodeKind.RECEIPT,
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
                ReferenceGovernanceEdgeKind.EXECUTES,
            )
        )
    for check in evaluation.checks:
        check_id = f"{check.record_id}:{check.check_id}"
        nodes.append(
            _node(
                f"check:{check_id}",
                ReferenceGovernanceNodeKind.CHECK,
                check.check_id,
                {"check_id": check.check_id, "record_id": check.record_id, "passed": check.passed},
            )
        )
        target = (
            f"receipt:{check.record_id}"
            if check.record_id in receipt_map
            else f"source:{fixture.sources[0].source_id}"
        )
        edges.append(
            _edge(
                f"verifies:{check_id}",
                target,
                f"check:{check_id}",
                ReferenceGovernanceEdgeKind.VERIFIES,
            )
        )
    body = {"fixture_id": fixture.fixture_id, "nodes": nodes, "edges": edges}
    return ReferenceGovernanceLineageGraph(
        fixture.fixture_id, tuple(nodes), tuple(edges), _address(body)
    )


__all__ = [
    "ReferenceGovernanceEdgeKind",
    "ReferenceGovernanceLineageAudit",
    "ReferenceGovernanceLineageEdge",
    "ReferenceGovernanceLineageGraph",
    "ReferenceGovernanceLineageNode",
    "ReferenceGovernanceNodeKind",
    "build_reference_governance_lineage",
]
