"""Explicit public graph projection for D14 closure resources."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence_lifecycle_frontier_offline_closure_contracts import (
    EvidenceLifecycleClosureCheck,
    EvidenceLifecycleClosureGraphEdge,
    EvidenceLifecycleClosureGraphReport,
    evidence_lifecycle_closure_check,
)
from .evidence_lifecycle_frontier_offline_closure_support import all_rows
from .evidence_lifecycle_frontier_offline_contracts import EvidenceLifecycleOfflineBundle
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleClosureGraphAudit:
    bundle_id: str
    checks: tuple[EvidenceLifecycleClosureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed_count": sum(item.passed for item in self.checks),
            "failed_count": sum(not item.passed for item in self.checks),
        }


def _edge(
    edge_id: str, source: str, target: str, relation: str, address: str
) -> EvidenceLifecycleClosureGraphEdge:
    evidence = {
        "edge_id": edge_id,
        "source": source,
        "target": target,
        "relation": relation,
        "evidence_address": address,
    }
    body = evidence | {
        "address": content_hash(evidence, prefix="evidence-lifecycle-closure-graph-edge")
    }
    body.pop("evidence_address")
    return EvidenceLifecycleClosureGraphEdge(**body)


def build_evidence_lifecycle_closure_graph(
    bundle: EvidenceLifecycleOfflineBundle,
) -> EvidenceLifecycleClosureGraphReport:
    rows = all_rows(bundle)
    root = f"bundle:{bundle.bundle_id}"
    nodes: set[str] = {root}
    edges: list[EvidenceLifecycleClosureGraphEdge] = []

    def connect(edge_id: str, source: str, target: str, relation: str, address: str = "") -> None:
        nodes.update((source, target))
        edges.append(_edge(edge_id, source, target, relation, address or bundle.content_address))

    for row in rows["artifacts"]:
        artifact = f"artifact:{row.get('artifact_id')}"
        connect(
            f"root-artifact-{row.get('artifact_id')}",
            root,
            artifact,
            "contains",
            str(row.get("content_address")),
        )
    artifact_nodes = {
        str(row.get("artifact_id")): f"artifact:{row.get('artifact_id')}"
        for row in rows["artifacts"]
    }
    for resource, resource_rows in rows.items():
        if resource in {"artifacts", "states"}:
            continue
        for ordinal, row in enumerate(resource_rows, start=1):
            identifier = (
                row.get("record_id")
                or row.get("check_id")
                or row.get("source_id")
                or row.get("event_id")
                or row.get("stage_id")
                or row.get("edge_id")
                or row.get("item_id")
                or row.get("scenario_id")
                or row.get("operation")
                or row.get("state")
                or ordinal
            )
            node = f"{resource}:{identifier}"
            artifact_id = {
                "records": "fixture",
                "executions": "evaluation",
                "checks": "evaluation",
                "sources": "fixture",
                "events": "observability",
                "stages": "runtime",
                "edges": "lineage",
                "queue": "review-queue",
                "reviews": "review",
                "scenarios": "scenario-matrix",
                "operations": "catalog",
            }.get(resource, "bundle")
            connect(
                f"artifact-{resource}-{ordinal}",
                artifact_nodes.get(artifact_id, root),
                node,
                f"projects_{resource[:-1] if resource.endswith('s') else resource}",
                str(row.get("content_address", "")),
            )
    for row in rows["records"]:
        record = f"records:{row.get('record_id')}"
        for relation, resource, identifier in (
            ("executes", "executions", row.get("record_id")),
            ("queued", "queue", row.get("record_id")),
            ("reviewed", "reviews", row.get("record_id")),
        ):
            target = f"{resource}:{identifier}"
            connect(
                f"record-{relation}-{identifier}",
                record,
                target,
                relation,
                str(row.get("content_address", "")),
            )
    for row in rows["checks"]:
        if row.get("record_id"):
            connect(
                f"record-check-{row.get('check_id')}",
                f"records:{row.get('record_id')}",
                f"checks:{row.get('check_id')}",
                "evaluated_by",
                str(row.get("content_address", "")),
            )
    lineage_rows = rows["edges"]
    for row in lineage_rows:
        edge_node = f"edges:{row.get('edge_id')}"
        parent = f"lineage-node:{row.get('parent_id')}"
        child = f"lineage-node:{row.get('child_id')}"
        connect(
            f"lineage-edge-parent-{row.get('edge_id')}",
            edge_node,
            parent,
            "has_parent",
            str(row.get("content_address", "")),
        )
        connect(
            f"lineage-edge-child-{row.get('edge_id')}",
            edge_node,
            child,
            "has_child",
            str(row.get("content_address", "")),
        )
        connect(
            f"lineage-{row.get('edge_id')}",
            parent,
            child,
            str(row.get("relation", "lineage")),
            str(row.get("content_address", "")),
        )
    node_tuple = tuple(sorted(nodes))
    edge_tuple = tuple(edges)
    parent = {node: node for node in node_tuple}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for item in edge_tuple:
        left, right = find(item.source), find(item.target)
        if left != right:
            parent[left] = right
    components = len({find(node) for node in node_tuple})
    body = {
        "bundle_id": bundle.bundle_id,
        "nodes": node_tuple,
        "edges": edge_tuple,
        "connected_component_count": components,
        "accepted": bool(node_tuple) and components == 1,
    }
    return EvidenceLifecycleClosureGraphReport(
        **body, content_address=content_hash(body, prefix="evidence-lifecycle-closure-graph")
    )


def audit_evidence_lifecycle_closure_graph(
    graph: EvidenceLifecycleClosureGraphReport,
) -> EvidenceLifecycleClosureGraphAudit:
    checks = (
        evidence_lifecycle_closure_check(
            "graph-accepted",
            "graph",
            graph.accepted,
            graph.accepted,
            True,
            "graph projection is accepted",
        ),
        evidence_lifecycle_closure_check(
            "graph-nodes",
            "graph",
            len(graph.nodes) > 300,
            len(graph.nodes),
            ">300",
            "graph exposes the full closure resource surface",
        ),
        evidence_lifecycle_closure_check(
            "graph-edges",
            "graph",
            len(graph.edges) > len(graph.nodes),
            len(graph.edges),
            f">{len(graph.nodes)}",
            "graph carries joins and lineage",
        ),
        evidence_lifecycle_closure_check(
            "graph-components",
            "graph",
            graph.connected_component_count == 1,
            graph.connected_component_count,
            1,
            "all public resources are connected",
        ),
        evidence_lifecycle_closure_check(
            "graph-edge-addresses",
            "graph",
            all(
                item.address.startswith("evidence-lifecycle-closure-graph-edge:")
                for item in graph.edges
            ),
            len(graph.edges),
            len(graph.edges),
            "graph edges are addressed",
        ),
        evidence_lifecycle_closure_check(
            "graph-unique-edges",
            "graph",
            len({item.address for item in graph.edges}) == len(graph.edges),
            len({item.address for item in graph.edges}),
            len(graph.edges),
            "graph edges are unique",
        ),
        evidence_lifecycle_closure_check(
            "graph-root",
            "graph",
            any(node.startswith("bundle:") for node in graph.nodes),
            True,
            True,
            "graph retains root bundle node",
        ),
        evidence_lifecycle_closure_check(
            "graph-artifacts",
            "graph",
            sum(node.startswith("artifact:") for node in graph.nodes) == 21,
            sum(node.startswith("artifact:") for node in graph.nodes),
            21,
            "graph retains artifact nodes",
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {"bundle_id": graph.bundle_id, "checks": checks, "accepted": accepted}
    return EvidenceLifecycleClosureGraphAudit(
        bundle_id=graph.bundle_id,
        checks=checks,
        accepted=accepted,
        content_address=content_hash(body, prefix="evidence-lifecycle-closure-graph-audit"),
    )


def export_evidence_lifecycle_closure_graph_csv(graph: EvidenceLifecycleClosureGraphReport) -> str:
    lines = ["edge_id,source,target,relation,address"]
    lines.extend(
        f"{item.edge_id},{item.source},{item.target},{item.relation},{item.address}"
        for item in graph.edges
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "EvidenceLifecycleClosureGraphAudit",
    "audit_evidence_lifecycle_closure_graph",
    "build_evidence_lifecycle_closure_graph",
    "export_evidence_lifecycle_closure_graph_csv",
]
