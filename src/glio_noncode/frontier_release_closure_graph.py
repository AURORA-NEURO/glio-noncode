"""Connected release graph joining D13-D16 domains, artifacts, gates, and order."""

from __future__ import annotations

from collections import defaultdict, deque

from .frontier_release_closure_bundle import FrontierReleaseSnapshot
from .frontier_release_closure_contracts import (
    FrontierReleaseClosureCheck,
    FrontierReleaseGraphEdge,
    FrontierReleaseGraphReport,
    frontier_release_closure_check,
)
from .serialization import content_hash


def _edge(source: str, target: str, relation: str, ordinal: int) -> FrontierReleaseGraphEdge:
    body = {
        "edge_id": f"{source}->{target}:{relation}:{ordinal:05d}",
        "source": source,
        "target": target,
        "relation": relation,
    }
    return FrontierReleaseGraphEdge(
        **body,
        content_address=content_hash(body, prefix="frontier-release-graph-edge"),
    )


def _components(nodes: tuple[str, ...], edges: tuple[FrontierReleaseGraphEdge, ...]) -> int:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        adjacency[edge.source].add(edge.target)
        adjacency[edge.target].add(edge.source)
    unseen = set(nodes)
    count = 0
    while unseen:
        count += 1
        start = unseen.pop()
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for neighbor in adjacency[current]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    queue.append(neighbor)
    return count


def build_frontier_release_graph(
    snapshot: FrontierReleaseSnapshot,
) -> FrontierReleaseGraphReport:
    nodes: set[str] = set()
    edges: list[FrontierReleaseGraphEdge] = []
    for domain in snapshot.domains:
        domain_node = f"domain:{domain.domain_id}"
        nodes.add(domain_node)
    for artifact in snapshot.artifacts:
        domain_node = f"domain:{artifact.domain_id}"
        artifact_node = f"artifact:{artifact.artifact_ref}"
        nodes.add(artifact_node)
        edges.append(_edge(domain_node, artifact_node, "domain_to_artifact", len(edges) + 1))
    for gate in snapshot.gates:
        domain_node = f"domain:{gate.domain_id}"
        gate_node = f"gate:{gate.gate_id}"
        nodes.add(gate_node)
        edges.append(_edge(domain_node, gate_node, "domain_to_gate", len(edges) + 1))
    for dependency in snapshot.dependencies:
        dependency_node = f"dependency:{dependency.dependency_id}"
        source_node = f"domain:{dependency.source_domain_id}"
        target_node = f"domain:{dependency.target_domain_id}"
        nodes.add(dependency_node)
        edges.append(_edge(source_node, dependency_node, "domain_to_dependency", len(edges) + 1))
        edges.append(_edge(dependency_node, target_node, "dependency_to_domain", len(edges) + 1))
    materialized_nodes = tuple(sorted(nodes))
    materialized_edges = tuple(edges)
    components = _components(materialized_nodes, materialized_edges)
    body = {
        "bundle_id": snapshot.bundle_id,
        "nodes": materialized_nodes,
        "edges": materialized_edges,
        "connected_component_count": components,
        "accepted": bool(snapshot.accepted and components == 1),
    }
    return FrontierReleaseGraphReport(
        **body,
        content_address=content_hash(body, prefix="frontier-release-graph"),
    )


def audit_frontier_release_graph(
    graph: FrontierReleaseGraphReport,
) -> tuple[FrontierReleaseClosureCheck, ...]:
    node_set = set(graph.nodes)
    checks = (
        frontier_release_closure_check(
            "graph-nodes",
            "graph",
            bool(graph.nodes),
            len(graph.nodes),
            ">0",
            "release graph has nodes",
        ),
        frontier_release_closure_check(
            "graph-edges",
            "graph",
            bool(graph.edges),
            len(graph.edges),
            ">0",
            "release graph has edges",
        ),
        frontier_release_closure_check(
            "graph-node-unique",
            "graph",
            len(graph.nodes) == len(node_set),
            len(node_set),
            len(graph.nodes),
            "graph node identities are unique",
        ),
        frontier_release_closure_check(
            "graph-edge-unique",
            "graph",
            len(graph.edges) == len({item.edge_id for item in graph.edges}),
            len({item.edge_id for item in graph.edges}),
            len(graph.edges),
            "graph edge identities are unique",
        ),
        frontier_release_closure_check(
            "graph-connected",
            "graph",
            graph.connected_component_count == 1,
            graph.connected_component_count,
            1,
            "domain release graph is connected",
        ),
        frontier_release_closure_check(
            "graph-endpoints",
            "graph",
            all(edge.source in node_set and edge.target in node_set for edge in graph.edges),
            sum(edge.source in node_set and edge.target in node_set for edge in graph.edges),
            len(graph.edges),
            "all edge endpoints exist",
        ),
        frontier_release_closure_check(
            "graph-addresses",
            "graph",
            all(edge.content_address for edge in graph.edges),
            sum(bool(edge.content_address) for edge in graph.edges),
            len(graph.edges),
            "all graph edges are addressed",
        ),
        frontier_release_closure_check(
            "graph-accepted",
            "graph",
            graph.accepted,
            graph.accepted,
            True,
            "graph release projection is accepted",
        ),
    )
    return checks


__all__ = ["audit_frontier_release_graph", "build_frontier_release_graph"]
