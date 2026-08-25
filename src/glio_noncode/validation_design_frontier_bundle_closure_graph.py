"""Relationship graph for the D13 closure handoff."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_design_frontier_bundle_closure_support import all_rows
from .validation_design_frontier_bundle_contracts import ValidationDesignBundle

VALIDATION_DESIGN_CLOSURE_GRAPH_VERSION = "validation-design-closure-graph-v1"


@dataclass(frozen=True, slots=True)
class ValidationDesignClosureGraphEdge:
    edge_id: str
    source: str
    target: str
    relation: str
    address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationDesignClosureGraphReport:
    version: str
    bundle_id: str
    nodes: tuple[str, ...]
    edges: tuple[ValidationDesignClosureGraphEdge, ...]
    connected_component_count: int
    accepted: bool
    content_address: str

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "node_count": self.node_count,
            "edge_count": self.edge_count,
        }


def _edge(
    source: str, target: str, relation: str, ordinal: int
) -> ValidationDesignClosureGraphEdge:
    body = {"source": source, "target": target, "relation": relation, "ordinal": ordinal}
    return ValidationDesignClosureGraphEdge(
        edge_id=f"edge-{ordinal:04d}",
        source=source,
        target=target,
        relation=relation,
        address=content_hash(body, prefix="validation-design-closure-graph-edge"),
    )


def _components(nodes: tuple[str, ...], edges: tuple[ValidationDesignClosureGraphEdge, ...]) -> int:
    neighbors = {node: set() for node in nodes}
    for edge in edges:
        neighbors.setdefault(edge.source, set()).add(edge.target)
        neighbors.setdefault(edge.target, set()).add(edge.source)
    remaining = set(nodes)
    count = 0
    while remaining:
        count += 1
        stack = [remaining.pop()]
        while stack:
            node = stack.pop()
            for neighbor in neighbors.get(node, ()):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    stack.append(neighbor)
    return count


def build_validation_design_closure_graph(
    bundle: ValidationDesignBundle,
) -> ValidationDesignClosureGraphReport:
    """Build a deterministic graph without copying payload bytes."""

    rows = all_rows(bundle)
    nodes: set[str] = {"bundle", "fixture", "evaluation", "runtime", "release"}
    edges: list[ValidationDesignClosureGraphEdge] = []
    ordinal = 1

    def add(source: str, target: str, relation: str) -> None:
        nonlocal ordinal
        nodes.update((source, target))
        edges.append(_edge(source, target, relation, ordinal))
        ordinal += 1

    add("bundle", "fixture", "publishes_fixture")
    add("bundle", "evaluation", "publishes_evaluation")
    add("bundle", "runtime", "publishes_runtime")
    add("bundle", "release", "publishes_release")
    for row in rows["artifacts"]:
        artifact = f"artifact:{row.get('artifact_id')}"
        add("bundle", artifact, "contains_artifact")
    for row in rows["sources"]:
        source = f"source:{row.get('source_id')}"
        add("fixture", source, "declares_source")
    for row in rows["records"]:
        record = f"record:{row.get('record_id')}"
        add("fixture", record, "contains_record")
        add(record, f"execution:{row.get('record_id')}", "evaluates_to")
        for source_id in row.get("source_ids", ()):
            add(record, f"source:{source_id}", "cites_source")
        add(f"operation:{row.get('operation')}", record, "groups_record")
    for row in rows["checks"]:
        check = f"check:{row.get('check_id')}"
        add("evaluation", check, "contains_check")
        add(f"record:{row.get('record_id')}", check, "has_check")
    for row in rows["stages"]:
        stage = f"stage:{row.get('stage_id')}"
        add("runtime", stage, "contains_stage")
    for row in rows["planes"]:
        plane = f"plane:{row.get('plane_id')}"
        add("runtime", plane, "contains_plane")
    for row in rows["operations"]:
        add("fixture", f"operation:{row.get('operation')}", "declares_operation")
    for row in rows["reviews"]:
        add(f"record:{row.get('record_id')}", f"review:{row.get('ordinal')}", "routes_review")
    edge_values = tuple(edges)
    node_values = tuple(sorted(nodes))
    accepted = (
        bundle.accepted
        and bool(edge_values)
        and _components(node_values, edge_values) == 1
        and len({item.edge_id for item in edge_values}) == len(edge_values)
    )
    body = {
        "version": VALIDATION_DESIGN_CLOSURE_GRAPH_VERSION,
        "bundle_id": bundle.bundle_id,
        "nodes": node_values,
        "edges": edge_values,
        "connected_component_count": _components(node_values, edge_values),
        "accepted": accepted,
    }
    return ValidationDesignClosureGraphReport(
        version=VALIDATION_DESIGN_CLOSURE_GRAPH_VERSION,
        bundle_id=bundle.bundle_id,
        nodes=node_values,
        edges=edge_values,
        connected_component_count=body["connected_component_count"],
        accepted=accepted,
        content_address=content_hash(body, prefix="validation-design-closure-graph"),
    )


def audit_validation_design_closure_graph(
    report: ValidationDesignClosureGraphReport,
) -> tuple[dict[str, Any], ...]:
    checks = [
        {
            "check_id": "graph-version",
            "passed": report.version == VALIDATION_DESIGN_CLOSURE_GRAPH_VERSION,
            "observed": report.version,
            "required": VALIDATION_DESIGN_CLOSURE_GRAPH_VERSION,
        },
        {
            "check_id": "graph-nodes",
            "passed": report.node_count > 100,
            "observed": report.node_count,
            "required": ">100",
        },
        {
            "check_id": "graph-edges",
            "passed": report.edge_count > 200,
            "observed": report.edge_count,
            "required": ">200",
        },
        {
            "check_id": "graph-addresses",
            "passed": all(
                item.address.startswith("validation-design-closure-graph-edge:")
                for item in report.edges
            ),
            "observed": report.edge_count,
            "required": report.edge_count,
        },
        {
            "check_id": "graph-edge-identities",
            "passed": len({item.edge_id for item in report.edges}) == report.edge_count,
            "observed": len({item.edge_id for item in report.edges}),
            "required": report.edge_count,
        },
        {
            "check_id": "graph-connected",
            "passed": report.connected_component_count == 1,
            "observed": report.connected_component_count,
            "required": 1,
        },
        {
            "check_id": "graph-accepted",
            "passed": report.accepted,
            "observed": report.accepted,
            "required": True,
        },
    ]
    return tuple(checks)


def export_validation_design_closure_graph_csv(report: ValidationDesignClosureGraphReport) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("edge_id", "source", "target", "relation", "address"))
    for edge in report.edges:
        writer.writerow((edge.edge_id, edge.source, edge.target, edge.relation, edge.address))
    return output.getvalue()


__all__ = [
    "VALIDATION_DESIGN_CLOSURE_GRAPH_VERSION",
    "ValidationDesignClosureGraphEdge",
    "ValidationDesignClosureGraphReport",
    "audit_validation_design_closure_graph",
    "build_validation_design_closure_graph",
    "export_validation_design_closure_graph_csv",
]
