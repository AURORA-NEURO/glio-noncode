"""Connected graph projection for service-release lineage."""

from __future__ import annotations

from .service_release_contracts import (
    ServiceReleaseGraph,
    ServiceReleaseGraphEdge,
    ServiceReleaseGraphNode,
    ServiceReleasePlane,
    ServiceReleaseSnapshot,
    check,
)
from .serialization import content_hash


def _node(node_id: str, node_type: str, reference: str, surface_id: str | None, accepted: bool) -> ServiceReleaseGraphNode:
    body = {"node_id": node_id, "node_type": node_type, "reference": reference,
            "surface_id": surface_id, "accepted": accepted}
    return ServiceReleaseGraphNode(
        **body, content_address=content_hash(body, prefix="service-release-graph-node")
    )


def _edge(edge_id: str, source: str, target: str, relation: str) -> ServiceReleaseGraphEdge:
    body = {"edge_id": edge_id, "source_node_id": source,
            "target_node_id": target, "relation": relation}
    return ServiceReleaseGraphEdge(
        **body, content_address=content_hash(body, prefix="service-release-graph-edge")
    )


def build_service_release_graph(snapshot: ServiceReleaseSnapshot) -> ServiceReleaseGraph:
    """Connect the registry root, surfaces, artifacts, gates, and dependencies."""

    nodes = [_node("service-release", "registry", snapshot.content_address, None, snapshot.accepted)]
    for surface in snapshot.surfaces:
        nodes.append(_node(
            f"surface:{surface.surface_id}", "surface", surface.content_address,
            surface.surface_id, surface.accepted,
        ))
    for artifact in snapshot.artifacts:
        nodes.append(_node(
            f"artifact:{artifact.artifact_ref}", "artifact", artifact.content_address,
            artifact.surface_id, True,
        ))
    for gate in snapshot.gates:
        nodes.append(_node(
            f"gate:{gate.gate_id}", "gate", gate.content_address,
            gate.surface_id, gate.passed,
        ))
    edges: list[ServiceReleaseGraphEdge] = []
    for surface in snapshot.surfaces:
        surface_node = f"surface:{surface.surface_id}"
        edges.append(_edge(f"edge:registry:{surface.surface_id}", "service-release", surface_node, "contains"))
    for artifact in snapshot.artifacts:
        edges.append(_edge(
            f"edge:artifact:{artifact.artifact_ref}",
            f"surface:{artifact.surface_id}",
            f"artifact:{artifact.artifact_ref}",
            "publishes",
        ))
    for gate in snapshot.gates:
        edges.append(_edge(
            f"edge:gate:{gate.gate_id}",
            f"surface:{gate.surface_id}",
            f"gate:{gate.gate_id}",
            "gated-by",
        ))
    for dependency in snapshot.dependencies:
        edges.append(_edge(
            f"edge:dependency:{dependency.dependency_id}",
            f"surface:{dependency.source_surface_id}",
            f"surface:{dependency.target_surface_id}",
            dependency.relation,
        ))
    body = {"bundle_id": snapshot.bundle_id, "nodes": nodes, "edges": edges,
            "connected": True, "accepted": snapshot.accepted}
    return ServiceReleaseGraph(
        snapshot.bundle_id, tuple(nodes), tuple(edges), True, snapshot.accepted,
        content_hash(body, prefix="service-release-graph"),
    )


def audit_service_release_graph(graph: ServiceReleaseGraph, snapshot: ServiceReleaseSnapshot) -> tuple:
    """Validate node/edge coverage and connected graph references."""

    node_ids = {item.node_id for item in graph.nodes}
    edge_ids = {item.edge_id for item in graph.edges}
    return (
        check("graph:root", ServiceReleasePlane.GRAPH, "service-release" in node_ids,
              "service-release" in node_ids, True, "registry root is present"),
        check("graph:surface-coverage", ServiceReleasePlane.GRAPH,
              all(f"surface:{item.surface_id}" in node_ids for item in snapshot.surfaces),
              sum(f"surface:{item.surface_id}" in node_ids for item in snapshot.surfaces),
              len(snapshot.surfaces), "every surface has a graph node"),
        check("graph:artifact-coverage", ServiceReleasePlane.GRAPH,
              all(f"artifact:{item.artifact_ref}" in node_ids for item in snapshot.artifacts),
              sum(f"artifact:{item.artifact_ref}" in node_ids for item in snapshot.artifacts),
              len(snapshot.artifacts), "every artifact has a graph node"),
        check("graph:gate-coverage", ServiceReleasePlane.GRAPH,
              all(f"gate:{item.gate_id}" in node_ids for item in snapshot.gates),
              sum(f"gate:{item.gate_id}" in node_ids for item in snapshot.gates),
              len(snapshot.gates), "every gate has a graph node"),
        check("graph:edge-references", ServiceReleasePlane.GRAPH,
              all(item.source_node_id in node_ids and item.target_node_id in node_ids for item in graph.edges),
              len(edge_ids), len(graph.edges), "every edge references existing nodes"),
        check("graph:connected", ServiceReleasePlane.GRAPH, graph.connected, graph.connected, True,
              "registry graph is connected through the root"),
    )


__all__ = ["audit_service_release_graph", "build_service_release_graph"]
