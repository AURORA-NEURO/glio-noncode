"""Source-to-receipt lineage graph for the C13-C16 release frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .reference_release_frontier_fixture_eval import ReferenceReleaseEvaluation
from .reference_release_frontier_public_data import ReferenceReleaseFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ReferenceReleaseLineageNode:
    """A redacted lineage node with a stable address."""

    node_id: str
    node_kind: str
    content_address: str
    attributes: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseLineageEdge:
    """A typed parent-child relationship."""

    edge_id: str
    source_node_id: str
    target_node_id: str
    relation: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseLineageAudit:
    """Closure checks for graph references and redaction."""

    passed: bool
    node_count: int
    edge_count: int
    failed_check_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseLineageGraph:
    """Immutable graph connecting public sources to output receipts."""

    fixture_id: str
    nodes: tuple[ReferenceReleaseLineageNode, ...]
    edges: tuple[ReferenceReleaseLineageEdge, ...]
    content_address: str

    def node_map(self) -> dict[str, ReferenceReleaseLineageNode]:
        return {node.node_id: node for node in self.nodes}

    def audit(
        self, evaluation: ReferenceReleaseEvaluation | None = None
    ) -> ReferenceReleaseLineageAudit:
        node_ids = set(self.node_map())
        failures: list[str] = []
        if len(node_ids) != len(self.nodes):
            failures.append("duplicate-node")
        if any(
            edge.source_node_id not in node_ids or edge.target_node_id not in node_ids
            for edge in self.edges
        ):
            failures.append("dangling-edge")
        if any("payload" in node.attributes or "records" in node.attributes for node in self.nodes):
            failures.append("raw-payload")
        if any(not node.content_address.startswith("lineage-node:") for node in self.nodes):
            failures.append("node-address")
        if evaluation is not None:
            execution_ids = {f"execution:{item.record_id}" for item in evaluation.executions}
            if not execution_ids <= node_ids:
                failures.append("execution-closure")
        body = {
            "passed": not failures,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "failed_check_ids": tuple(failures),
        }
        return ReferenceReleaseLineageAudit(
            **body, content_address=content_hash(body, prefix="lineage-audit")
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"node_count": len(self.nodes), "edge_count": len(self.edges)}


def _node(node_id: str, node_kind: str, attributes: dict[str, Any]) -> ReferenceReleaseLineageNode:
    body = {"node_id": node_id, "node_kind": node_kind, "attributes": attributes}
    return ReferenceReleaseLineageNode(
        **body, content_address=content_hash(body, prefix="lineage-node")
    )


def _edge(index: int, source: str, target: str, relation: str) -> ReferenceReleaseLineageEdge:
    body = {
        "edge_id": f"edge:{index:04d}",
        "source_node_id": source,
        "target_node_id": target,
        "relation": relation,
    }
    return ReferenceReleaseLineageEdge(
        **body, content_address=content_hash(body, prefix="lineage-edge")
    )


def build_reference_release_lineage(
    fixture: ReferenceReleaseFixture,
    evaluation: ReferenceReleaseEvaluation,
) -> ReferenceReleaseLineageGraph:
    """Build a redacted graph with source, record, execution, and check nodes."""

    nodes: list[ReferenceReleaseLineageNode] = [
        _node(
            f"fixture:{fixture.fixture_id}",
            "fixture",
            {"fixture_id": fixture.fixture_id, "context_key": fixture.context_key},
        )
    ]
    edges: list[ReferenceReleaseLineageEdge] = []
    index = 1
    fixture_node = f"fixture:{fixture.fixture_id}"
    for source in fixture.sources:
        source_node = f"source:{source.source_id}"
        nodes.append(
            _node(
                source_node,
                "source",
                {
                    "source_id": source.source_id,
                    "release": source.release,
                    "uri": source.uri,
                    "license": source.license,
                    "scope": source.scope,
                },
            )
        )
        edges.append(_edge(index, fixture_node, source_node, "declares-source"))
        index += 1
    source_ids = {source.source_id for source in fixture.sources}
    for record in fixture.records:
        record_node = f"record:{record.record_id}"
        nodes.append(
            _node(
                record_node,
                "record",
                {
                    "record_id": record.record_id,
                    "operation": record.operation,
                    "role": record.role,
                    "expected_state": record.expected_state,
                    "source_count": len(record.source_ids),
                },
            )
        )
        edges.append(_edge(index, fixture_node, record_node, "declares-record"))
        index += 1
        for source_id in record.source_ids:
            if source_id in source_ids:
                edges.append(_edge(index, f"source:{source_id}", record_node, "supports-record"))
                index += 1
    for execution in evaluation.executions:
        record_node = f"record:{execution.record_id}"
        execution_node = f"execution:{execution.record_id}"
        nodes.append(
            _node(
                execution_node,
                "execution",
                {
                    "record_id": execution.record_id,
                    "operation": execution.operation,
                    "state": execution.state,
                    "issue_count": len(execution.issue_codes),
                },
            )
        )
        edges.append(_edge(index, record_node, execution_node, "executes"))
        index += 1
        for check in evaluation.checks:
            if check.record_id != execution.record_id:
                continue
            check_node = f"check:{check.check_id}"
            nodes.append(
                _node(
                    check_node,
                    "check",
                    {"check_id": check.check_id, "passed": check.passed, "detail": check.detail},
                )
            )
            edges.append(_edge(index, execution_node, check_node, "validated-by"))
            index += 1
        output_node = f"output:{execution.record_id}"
        nodes.append(
            _node(
                output_node,
                "output",
                {
                    "record_id": execution.record_id,
                    "state": execution.state,
                    "issue_count": len(execution.issue_codes),
                },
            )
        )
        edges.append(_edge(index, execution_node, output_node, "projects"))
        index += 1
        for issue_code in execution.issue_codes:
            issue_node = f"issue:{execution.record_id}:{issue_code}"
            nodes.append(
                _node(
                    issue_node,
                    "issue",
                    {"record_id": execution.record_id, "issue_code": issue_code},
                )
            )
            edges.append(_edge(index, execution_node, issue_node, "retains-issue"))
            index += 1
    body = {"fixture_id": fixture.fixture_id, "nodes": tuple(nodes), "edges": tuple(edges)}
    return ReferenceReleaseLineageGraph(
        **body, content_address=content_hash(body, prefix="release-lineage")
    )


__all__ = [
    "ReferenceReleaseLineageAudit",
    "ReferenceReleaseLineageEdge",
    "ReferenceReleaseLineageGraph",
    "ReferenceReleaseLineageNode",
    "build_reference_release_lineage",
]
