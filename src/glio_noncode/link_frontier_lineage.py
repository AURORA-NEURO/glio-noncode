"""Content-addressed lineage for Domain 10 link evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_frontier_fixture_eval import LinkFrontierEvaluation
from .link_frontier_public_data import LinkFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkFrontierLineageNode:
    node_id: str
    node_kind: str
    content_address: str
    parent_ids: tuple[str, ...]
    label: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkFrontierLineageReport:
    fixture_id: str
    nodes: tuple[LinkFrontierLineageNode, ...]
    roots: tuple[str, ...]
    leaves: tuple[str, ...]
    valid: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"valid": self.valid}


def build_link_frontier_lineage(
    fixture: LinkFrontierFixture,
    evaluation: LinkFrontierEvaluation,
) -> LinkFrontierLineageReport:
    nodes: list[LinkFrontierLineageNode] = []
    fixture_node = LinkFrontierLineageNode(
        "fixture:" + fixture.fixture_id,
        "fixture",
        fixture.content_address,
        (),
        fixture.fixture_version,
    )
    nodes.append(fixture_node)
    for source in fixture.sources:
        nodes.append(
            LinkFrontierLineageNode(
                "source:" + source.source_id,
                "source",
                source.content_address,
                (fixture_node.node_id,),
                source.title,
            )
        )
    source_map = fixture.source_map()
    for record in fixture.records:
        parents = tuple("source:" + source_id for source_id in record.source_ids if source_id in source_map)
        nodes.append(LinkFrontierLineageNode("record:" + record.record_id, "record", record.content_address, parents, record.description))
    for execution in evaluation.executions:
        nodes.append(
            LinkFrontierLineageNode(
                "execution:" + execution.record_id,
                "execution",
                execution.content_address,
                ("record:" + execution.record_id,),
                execution.state,
            )
        )
    ids = {node.node_id for node in nodes}
    valid = all(parent in ids for node in nodes for parent in node.parent_ids) and len(ids) == len(nodes)
    child_ids = {parent for node in nodes for parent in node.parent_ids}
    roots = tuple(sorted(node.node_id for node in nodes if not node.parent_ids))
    leaves = tuple(sorted(node.node_id for node in nodes if node.node_id not in child_ids))
    body = {"fixture_id": fixture.fixture_id, "nodes": nodes, "roots": roots, "leaves": leaves, "valid": valid}
    return LinkFrontierLineageReport(**body, content_address=content_hash(body))


def verify_link_frontier_lineage(report: LinkFrontierLineageReport) -> tuple[str, ...]:
    ids = {node.node_id for node in report.nodes}
    failures: list[str] = []
    if not report.valid:
        failures.append("invalid_graph")
    if not report.roots:
        failures.append("missing_root")
    if any(parent not in ids for node in report.nodes for parent in node.parent_ids):
        failures.append("unresolved_parent")
    if len(ids) != len(report.nodes):
        failures.append("duplicate_node")
    return tuple(sorted(set(failures)))


__all__ = ["LinkFrontierLineageNode", "LinkFrontierLineageReport", "build_link_frontier_lineage", "verify_link_frontier_lineage"]
