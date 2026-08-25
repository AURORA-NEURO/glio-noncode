"""Queryable dependency graph for the aggregate closure."""

from __future__ import annotations

from .program_release_closure_contracts import (
    ProgramReleaseGraph,
    ProgramReleaseGraphEdge,
    ProgramReleaseGraphNode,
    ProgramReleaseSnapshot,
)
from .serialization import content_hash


def _node(node_id: str, node_type: str, reference: str) -> ProgramReleaseGraphNode:
    body = {"node_id": node_id, "node_type": node_type, "reference": reference}
    return ProgramReleaseGraphNode(
        **body, content_address=content_hash(body, prefix="program-release-graph-node")
    )


def _edge(edge_id: str, source: str, target: str, relation: str) -> ProgramReleaseGraphEdge:
    body = {"edge_id": edge_id, "source": source, "target": target, "relation": relation}
    return ProgramReleaseGraphEdge(
        **body, content_address=content_hash(body, prefix="program-release-graph-edge")
    )


def build_program_release_graph(snapshot: ProgramReleaseSnapshot) -> ProgramReleaseGraph:
    nodes = [_node("root:program-release", "root", snapshot.bundle_id)]
    edges: list[ProgramReleaseGraphEdge] = []
    for domain in snapshot.domains:
        node = _node(f"domain:{domain.domain_id}", "domain", domain.domain_id)
        nodes.append(node)
        edges.append(
            _edge(
                f"edge:root:domain:{domain.domain_id}",
                "root:program-release",
                node.node_id,
                "contains",
            )
        )
    for artifact in snapshot.artifacts:
        node = _node(f"artifact:{artifact.artifact_ref}", "artifact", artifact.artifact_ref)
        nodes.append(node)
        edges.append(
            _edge(
                f"edge:root:artifact:{artifact.artifact_ref}",
                "root:program-release",
                node.node_id,
                "publishes",
            )
        )
    for dependency in snapshot.dependencies:
        node = _node(
            f"dependency:{dependency.dependency_id}", "dependency", dependency.dependency_id
        )
        nodes.append(node)
        edges.extend(
            (
                _edge(
                    f"edge:root:{dependency.dependency_id}",
                    "root:program-release",
                    node.node_id,
                    "indexes",
                ),
                _edge(
                    f"edge:{dependency.dependency_id}:source",
                    node.node_id,
                    f"domain:{dependency.source_domain_id}",
                    "from",
                ),
                _edge(
                    f"edge:{dependency.dependency_id}:target",
                    node.node_id,
                    f"domain:{dependency.target_domain_id}",
                    "to",
                ),
            )
        )
    for gate in snapshot.gates:
        node = _node(f"gate:{gate.gate_id}", "gate", gate.gate_id)
        nodes.append(node)
        edges.extend(
            (
                _edge(
                    f"edge:root:{gate.gate_id}", "root:program-release", node.node_id, "evaluates"
                ),
                _edge(
                    f"edge:{gate.gate_id}:domain", node.node_id, f"domain:{gate.domain_id}", "for"
                ),
            )
        )
    return ProgramReleaseGraph(
        snapshot.bundle_id,
        tuple(nodes),
        tuple(edges),
        _components(nodes, edges),
        snapshot.accepted,
        content_hash(
            {
                "bundle_id": snapshot.bundle_id,
                "nodes": nodes,
                "edges": edges,
                "accepted": snapshot.accepted,
            },
            prefix="program-release-graph",
        ),
    )


def _components(nodes: list[ProgramReleaseGraphNode], edges: list[ProgramReleaseGraphEdge]) -> int:
    parents = {node.node_id: node.node_id for node in nodes}

    def find(value: str) -> str:
        while parents[value] != value:
            parents[value] = parents[parents[value]]
            value = parents[value]
        return value

    def union(left: str, right: str) -> None:
        parents[find(left)] = find(right)

    for edge in edges:
        union(edge.source, edge.target)
    return len({find(node.node_id) for node in nodes})


def audit_program_release_graph(
    graph: ProgramReleaseGraph, snapshot: ProgramReleaseSnapshot
) -> dict[str, object]:
    expected_nodes = (
        1
        + len(snapshot.domains)
        + len(snapshot.artifacts)
        + len(snapshot.dependencies)
        + len(snapshot.gates)
    )
    checks = {
        "accepted": graph.accepted,
        "node_count": len(graph.nodes) == expected_nodes,
        "edge_count": len(graph.edges) > len(graph.nodes),
        "node_unique": len({item.node_id for item in graph.nodes}) == len(graph.nodes),
        "edge_unique": len({item.edge_id for item in graph.edges}) == len(graph.edges),
        "connected": graph.connected_component_count == 1,
        "domain_nodes": sum(item.node_type == "domain" for item in graph.nodes)
        == len(snapshot.domains),
        "artifact_nodes": sum(item.node_type == "artifact" for item in graph.nodes)
        == len(snapshot.artifacts),
        "dependency_nodes": sum(item.node_type == "dependency" for item in graph.nodes)
        == len(snapshot.dependencies),
        "gate_nodes": sum(item.node_type == "gate" for item in graph.nodes) == len(snapshot.gates),
    }
    body = {"bundle_id": graph.bundle_id, "checks": checks, "accepted": all(checks.values())}
    body["content_address"] = content_hash(body, prefix="program-release-graph-audit")
    return body


__all__ = [
    name
    for name in globals()
    if name.startswith("build_program_release")
    or name.startswith("audit_program_release")
    or name.startswith("ProgramRelease")
]
