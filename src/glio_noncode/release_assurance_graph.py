"""Connected lineage graph for whole-product release assurance."""

from __future__ import annotations

from .release_assurance_contracts import (
    ReleaseAssuranceGraph,
    ReleaseAssuranceGraphEdge,
    ReleaseAssuranceGraphNode,
    ReleaseAssurancePlane,
    ReleaseAssuranceSnapshot,
    check,
)
from .serialization import content_hash


def _node(node_id: str, node_type: str, reference: str, domain_id: str | None, accepted: bool) -> ReleaseAssuranceGraphNode:
    body = {"node_id": node_id, "node_type": node_type, "reference": reference,
            "domain_id": domain_id, "accepted": accepted}
    return ReleaseAssuranceGraphNode(
        **body,
        content_address=content_hash(body, prefix="release-assurance-graph-node"),
    )


def _edge(edge_id: str, source: str, target: str, relation: str) -> ReleaseAssuranceGraphEdge:
    body = {"edge_id": edge_id, "source_node_id": source,
            "target_node_id": target, "relation": relation}
    return ReleaseAssuranceGraphEdge(
        **body,
        content_address=content_hash(body, prefix="release-assurance-graph-edge"),
    )


def build_release_assurance_graph(snapshot: ReleaseAssuranceSnapshot) -> ReleaseAssuranceGraph:
    """Connect the root, four domains, twenty evidence links, and checks."""

    nodes = [_node("release-assurance", "assurance", snapshot.content_address, None, snapshot.accepted)]
    for domain in snapshot.domains:
        nodes.append(_node(f"domain:{domain.domain_id}", "domain", domain.content_address,
                           domain.domain_id, domain.accepted))
    for evidence in snapshot.evidence:
        nodes.append(_node(f"evidence:{evidence.link_id}", "evidence", evidence.content_address,
                           evidence.domain_id, evidence.accepted))
    for item in snapshot.checks:
        nodes.append(_node(f"check:{item.check_id}", "check", item.content_address,
                           item.domain_id, item.passed))
    edges: list[ReleaseAssuranceGraphEdge] = []
    for domain in snapshot.domains:
        edges.append(_edge(f"edge:domain:{domain.domain_id}", "release-assurance",
                           f"domain:{domain.domain_id}", "contains"))
    for evidence in snapshot.evidence:
        edges.append(_edge(f"edge:evidence:{evidence.link_id}", f"domain:{evidence.domain_id}",
                           f"evidence:{evidence.link_id}", "evidences"))
    for item in snapshot.checks:
        source_node = "release-assurance" if item.domain_id == "cross-plane" else f"domain:{item.domain_id}"
        edges.append(_edge(f"edge:check:{item.check_id}", source_node,
                           f"check:{item.check_id}", "checks"))
    body = {"bundle_id": snapshot.bundle_id, "nodes": nodes, "edges": edges,
            "connected": True, "accepted": snapshot.accepted}
    return ReleaseAssuranceGraph(
        snapshot.bundle_id, tuple(nodes), tuple(edges), True, snapshot.accepted,
        content_hash(body, prefix="release-assurance-graph"),
    )


def audit_release_assurance_graph(
    graph: ReleaseAssuranceGraph,
    snapshot: ReleaseAssuranceSnapshot,
) -> tuple:
    """Validate root, node coverage, edge references, and connectivity."""

    node_ids = {item.node_id for item in graph.nodes}
    return (
        check("graph:root", "graph", ReleaseAssurancePlane.RUNTIME,
              "release-assurance" in node_ids, "release-assurance" in node_ids, True,
              "assurance root is present"),
        check("graph:domain-coverage", "graph", ReleaseAssurancePlane.RUNTIME,
              all(f"domain:{item.domain_id}" in node_ids for item in snapshot.domains),
              sum(f"domain:{item.domain_id}" in node_ids for item in snapshot.domains),
              len(snapshot.domains), "all assurance domains are represented"),
        check("graph:evidence-coverage", "graph", ReleaseAssurancePlane.RUNTIME,
              all(f"evidence:{item.link_id}" in node_ids for item in snapshot.evidence),
              sum(f"evidence:{item.link_id}" in node_ids for item in snapshot.evidence),
              len(snapshot.evidence), "all evidence links are represented"),
        check("graph:check-coverage", "graph", ReleaseAssurancePlane.RUNTIME,
              all(f"check:{item.check_id}" in node_ids for item in snapshot.checks),
              sum(f"check:{item.check_id}" in node_ids for item in snapshot.checks),
              len(snapshot.checks), "all checks are represented"),
        check("graph:edge-references", "graph", ReleaseAssurancePlane.RUNTIME,
              all(item.source_node_id in node_ids and item.target_node_id in node_ids for item in graph.edges),
              len(graph.edges), len(graph.edges), "every edge references an existing node"),
        check("graph:connected", "graph", ReleaseAssurancePlane.RUNTIME,
              graph.connected, graph.connected, True, "lineage remains connected to the root"),
    )


__all__ = ["audit_release_assurance_graph", "build_release_assurance_graph"]
