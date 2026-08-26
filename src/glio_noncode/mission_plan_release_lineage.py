"""Address graph for portable public mission-plan releases.

Lineage makes the relationship between a release and its verified projections
explicit: the release contains a manifest, public receipt, integrity checks,
workflow steps, and exact-byte artifacts.  Every node and edge is addressed,
ordered deterministically, and represented without raw request or internal
routing metadata.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .mission_plan_release import (
    MissionPlanOfflineRelease,
    MissionPlanReleaseBundle,
    build_mission_plan_release,
    load_mission_plan_release,
)
from .mission_runtime_public import MissionPlanPublicReceipt
from .serialization import canonical_json, content_hash, jsonable


MISSION_PLAN_RELEASE_LINEAGE_VERSION = "mission-plan-release-lineage-v1"
MISSION_PLAN_RELEASE_LINEAGE_SCHEMA_VERSION = "mission-plan-release-lineage-schema-v1"
MISSION_PLAN_RELEASE_LINEAGE_CAPABILITIES_VERSION = "mission-plan-release-lineage-capabilities-v1"
MISSION_PLAN_RELEASE_LINEAGE_MAX_NODES = 512
MISSION_PLAN_RELEASE_LINEAGE_MAX_EDGES = 1024


def _text(value: Any, field: str) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    normalized = str(value).strip()
    if not normalized:
        raise ValidationError(f"{field} must not be empty")
    return normalized


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseLineageNode:
    """One addressed release graph node."""

    node_id: str
    node_type: str
    content_address: str
    ordinal: int

    def __post_init__(self) -> None:
        _text(self.node_id, "node_id")
        _text(self.node_type, "node_type")
        _text(self.content_address, "node.content_address")
        if self.ordinal <= 0:
            raise ValidationError("lineage node ordinal must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseLineageEdge:
    """One directed relationship between release nodes."""

    edge_id: str
    source_node_id: str
    target_node_id: str
    relationship: str
    ordinal: int
    content_address: str

    def __post_init__(self) -> None:
        for value, field in (
            (self.edge_id, "edge_id"),
            (self.source_node_id, "source_node_id"),
            (self.target_node_id, "target_node_id"),
            (self.relationship, "relationship"),
            (self.content_address, "edge.content_address"),
        ):
            _text(value, field)
        if self.source_node_id == self.target_node_id:
            raise ValidationError("lineage edge cannot point to itself")
        if self.ordinal <= 0:
            raise ValidationError("lineage edge ordinal must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseLineage:
    """Addressed release lineage graph."""

    lineage_version: str
    release_id: str
    plan_id: str
    plan_address: str
    root_node_id: str
    nodes: tuple[MissionPlanReleaseLineageNode, ...]
    edges: tuple[MissionPlanReleaseLineageEdge, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if self.lineage_version != MISSION_PLAN_RELEASE_LINEAGE_VERSION:
            raise ValidationError("lineage version is invalid")
        _text(self.release_id, "lineage.release_id")
        _text(self.plan_id, "lineage.plan_id")
        _text(self.plan_address, "lineage.plan_address")
        _text(self.root_node_id, "lineage.root_node_id")
        if len(self.nodes) > MISSION_PLAN_RELEASE_LINEAGE_MAX_NODES:
            raise ValidationError("lineage node count exceeds the bound")
        if len(self.edges) > MISSION_PLAN_RELEASE_LINEAGE_MAX_EDGES:
            raise ValidationError("lineage edge count exceeds the bound")
        node_ids = [item.node_id for item in self.nodes]
        edge_ids = [item.edge_id for item in self.edges]
        if len(node_ids) != len(set(node_ids)) or len(edge_ids) != len(set(edge_ids)):
            raise ValidationError("lineage IDs must be unique")
        if self.root_node_id not in node_ids:
            raise ValidationError("lineage root node is missing")
        node_set = set(node_ids)
        if any(
            edge.source_node_id not in node_set or edge.target_node_id not in node_set
            for edge in self.edges
        ):
            raise ValidationError("lineage edge refers to an unknown node")
        if tuple(item.ordinal for item in self.nodes) != tuple(range(1, len(self.nodes) + 1)):
            raise ValidationError("lineage node ordinals must be contiguous")
        if tuple(item.ordinal for item in self.edges) != tuple(range(1, len(self.edges) + 1)):
            raise ValidationError("lineage edge ordinals must be contiguous")

    def to_dict(self) -> dict[str, Any]:
        body = {
            "lineage_version": self.lineage_version,
            "release_id": self.release_id,
            "plan_id": self.plan_id,
            "plan_address": self.plan_address,
            "root_node_id": self.root_node_id,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "nodes": self.nodes,
            "edges": self.edges,
            "accepted": self.accepted,
        }
        return jsonable(body | {"content_address": self.content_address})


def _node(node_id: str, node_type: str, address: str, ordinal: int) -> MissionPlanReleaseLineageNode:
    body = {
        "node_id": node_id,
        "node_type": node_type,
        "content_address": address,
        "ordinal": ordinal,
    }
    return MissionPlanReleaseLineageNode(**body)


def _edge(
    edge_id: str,
    source_node_id: str,
    target_node_id: str,
    relationship: str,
    ordinal: int,
) -> MissionPlanReleaseLineageEdge:
    body = {
        "edge_id": edge_id,
        "source_node_id": source_node_id,
        "target_node_id": target_node_id,
        "relationship": relationship,
        "ordinal": ordinal,
    }
    return MissionPlanReleaseLineageEdge(
        **body,
        content_address=content_hash(body, prefix="mission-plan-release-lineage-edge"),
    )


def _as_bundle(
    value: MissionPlanReleaseBundle | MissionPlanOfflineRelease | MissionPlanPublicReceipt | Mapping[str, Any] | str | Path,
) -> MissionPlanReleaseBundle:
    if isinstance(value, MissionPlanReleaseBundle):
        return value
    if isinstance(value, MissionPlanOfflineRelease):
        # The verified manifest is sufficient to reconstruct metadata, but
        # bytes are deliberately not reread into the lineage graph.
        artifacts = tuple(
            _artifact_metadata(row)
            for row in value.manifest.get("artifacts", ())
            if isinstance(row, Mapping)
        )
        return MissionPlanReleaseBundle(
            release_id=value.release_id,
            plan_id=value.plan_id,
            plan_address=value.plan_address,
            state=value.receipt.state.value,
            accepted=value.accepted,
            receipt=value.receipt,
            checks=value.checks,
            artifacts=artifacts,
            manifest=value.manifest,
            content_address=value.content_address,
        )
    if isinstance(value, MissionPlanPublicReceipt):
        return build_mission_plan_release(value)
    if isinstance(value, (str, Path)):
        return _as_bundle(load_mission_plan_release(value))
    body = dict(value)
    if isinstance(body.get("receipt"), Mapping):
        return build_mission_plan_release(
            MissionPlanPublicReceipt.from_mapping(body["receipt"]),
            release_id=None if body.get("release_id") is None else str(body["release_id"]),
        )
    if "content_address" in body:
        return build_mission_plan_release(MissionPlanPublicReceipt.from_mapping(body))
    from .mission_runtime_public import build_public_mission_plan

    return build_mission_plan_release(build_public_mission_plan(body))


def _artifact_metadata(row: Mapping[str, Any]):
    filename = _text(row.get("filename"), "artifact.filename")
    # Offline lineage intentionally retains no payload.  A zero-length
    # placeholder cannot satisfy the artifact dataclass's byte checks, so the
    # verified loader path is represented through a small metadata-only proxy.
    return _LineageArtifact(
        filename=filename,
        content_address=_text(row.get("content_address"), "artifact.content_address"),
    )


@dataclass(frozen=True, slots=True)
class _LineageArtifact:
    filename: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {"filename": self.filename, "content_address": self.content_address}


def build_mission_plan_release_lineage(
    value: MissionPlanReleaseBundle | MissionPlanOfflineRelease | MissionPlanPublicReceipt | Mapping[str, Any] | str | Path,
) -> MissionPlanReleaseLineage:
    """Build a deterministic release lineage graph."""

    bundle = _as_bundle(value)
    root = f"release:{bundle.release_id}"
    plan = f"plan:{bundle.plan_id}"
    manifest = f"manifest:{bundle.manifest.get('manifest_address', '')}"
    nodes: list[MissionPlanReleaseLineageNode] = [
        _node(root, "release", bundle.content_address, 1),
        _node(plan, "public-plan", bundle.plan_address, 2),
        _node(manifest, "manifest", str(bundle.manifest.get("manifest_address", "")), 3),
    ]
    step_ids: list[str] = []
    for step in bundle.receipt.steps:
        node_id = f"step:{step.step_id}"
        step_ids.append(node_id)
        nodes.append(
            _node(
                node_id,
                "workflow-step",
                content_hash(step.to_dict(), prefix="mission-plan-release-step"),
                len(nodes) + 1,
            )
        )
    check_ids: list[str] = []
    for check in bundle.checks:
        node_id = f"check:{check.check_id}"
        check_ids.append(node_id)
        nodes.append(_node(node_id, "integrity-check", check.content_address, len(nodes) + 1))
    artifact_ids: list[str] = []
    for artifact in sorted(bundle.artifacts, key=lambda item: item.filename):
        node_id = f"artifact:{artifact.filename}"
        artifact_ids.append(node_id)
        nodes.append(
            _node(node_id, "artifact", artifact.content_address, len(nodes) + 1)
        )
    edges: list[MissionPlanReleaseLineageEdge] = []

    def add(source: str, target: str, relationship: str) -> None:
        edges.append(_edge(f"edge-{len(edges) + 1:04d}", source, target, relationship, len(edges) + 1))

    add(root, plan, "publishes")
    add(root, manifest, "contains")
    for node_id in step_ids:
        add(plan, node_id, "contains")
    for node_id in check_ids:
        add(root, node_id, "checks")
    for node_id in artifact_ids:
        add(root, node_id, "contains")
    add("artifact:mission-plan.json", plan, "serializes")
    for node_id in check_ids:
        add("artifact:release-checks.json", node_id, "serializes")
    for artifact in artifact_ids:
        add(manifest, artifact, "lists")
    body = {
        "lineage_version": MISSION_PLAN_RELEASE_LINEAGE_VERSION,
        "release_id": bundle.release_id,
        "plan_id": bundle.plan_id,
        "plan_address": bundle.plan_address,
        "root_node_id": root,
        "nodes": nodes,
        "edges": edges,
        "accepted": bundle.accepted,
    }
    return MissionPlanReleaseLineage(
        **body,
        content_address=content_hash(body, prefix="mission-plan-release-lineage"),
    )


def mission_plan_release_lineage_json(value: MissionPlanReleaseLineage) -> str:
    """Render lineage as canonical JSON."""

    return canonical_json(value.to_dict()) + "\n"


def mission_plan_release_lineage_nodes_csv(value: MissionPlanReleaseLineage) -> str:
    """Render lineage nodes as deterministic CSV."""

    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("ordinal", "node_id", "node_type", "content_address"))
    for node in value.nodes:
        writer.writerow((node.ordinal, node.node_id, node.node_type, node.content_address))
    return output.getvalue()


def mission_plan_release_lineage_edges_csv(value: MissionPlanReleaseLineage) -> str:
    """Render lineage edges as deterministic CSV."""

    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("ordinal", "edge_id", "source_node_id", "target_node_id", "relationship", "content_address"))
    for edge in value.edges:
        writer.writerow(
            (edge.ordinal, edge.edge_id, edge.source_node_id, edge.target_node_id, edge.relationship, edge.content_address)
        )
    return output.getvalue()


def mission_plan_release_lineage_markdown(value: MissionPlanReleaseLineage) -> str:
    """Render lineage as a compact node/edge review."""

    lines = [
        "# Mission plan release lineage",
        "",
        f"- Release: `{value.release_id}`",
        f"- Nodes: `{len(value.nodes)}`",
        f"- Edges: `{len(value.edges)}`",
        f"- Accepted: `{value.accepted}`",
        "",
        "| Node | Type | Address |",
        "| --- | --- | --- |",
    ]
    lines.extend(
        f"| `{node.node_id}` | `{node.node_type}` | `{node.content_address}` |"
        for node in value.nodes
    )
    lines.extend(("", "| Edge | Relationship | Source → Target |", "| --- | --- | --- |"))
    lines.extend(
        f"| `{edge.edge_id}` | `{edge.relationship}` | `{edge.source_node_id}` → `{edge.target_node_id}` |"
        for edge in value.edges
    )
    return "\n".join(lines) + "\n"


def mission_plan_release_lineage_export_payloads(value: MissionPlanReleaseLineage) -> dict[str, str]:
    """Return deterministic JSON, Markdown, node CSV, and edge CSV artifacts."""

    return {
        "mission-plan-release-lineage.json": mission_plan_release_lineage_json(value),
        "mission-plan-release-lineage.md": mission_plan_release_lineage_markdown(value),
        "mission-plan-release-lineage-nodes.csv": mission_plan_release_lineage_nodes_csv(value),
        "mission-plan-release-lineage-edges.csv": mission_plan_release_lineage_edges_csv(value),
    }


def mission_plan_release_lineage_schema() -> dict[str, Any]:
    """Return the lineage graph contract."""

    return {
        "version": MISSION_PLAN_RELEASE_LINEAGE_SCHEMA_VERSION,
        "lineage_version": MISSION_PLAN_RELEASE_LINEAGE_VERSION,
        "node_types": ["release", "public-plan", "manifest", "workflow-step", "integrity-check", "artifact"],
        "relationships": ["publishes", "contains", "checks", "serializes", "lists"],
        "max_nodes": MISSION_PLAN_RELEASE_LINEAGE_MAX_NODES,
        "max_edges": MISSION_PLAN_RELEASE_LINEAGE_MAX_EDGES,
        "address_required": True,
        "boundary": {
            "routing_metadata": False,
            "producer_metadata": False,
            "model_metadata": False,
            "programming_language_metadata": False,
            "raw_request_payload": False,
        },
    }


def mission_plan_release_lineage_capabilities() -> dict[str, Any]:
    """Return lineage graph capabilities."""

    return {
        "version": MISSION_PLAN_RELEASE_LINEAGE_CAPABILITIES_VERSION,
        "addressed_nodes": True,
        "addressed_edges": True,
        "release_to_artifact_links": True,
        "receipt_to_step_links": True,
        "check_to_artifact_links": True,
        "deterministic_order": True,
        "json_export": True,
        "markdown_export": True,
        "csv_export": True,
        "read_only": True,
    }


__all__ = [
    "MISSION_PLAN_RELEASE_LINEAGE_CAPABILITIES_VERSION",
    "MISSION_PLAN_RELEASE_LINEAGE_MAX_EDGES",
    "MISSION_PLAN_RELEASE_LINEAGE_MAX_NODES",
    "MISSION_PLAN_RELEASE_LINEAGE_SCHEMA_VERSION",
    "MISSION_PLAN_RELEASE_LINEAGE_VERSION",
    "MissionPlanReleaseLineage",
    "MissionPlanReleaseLineageEdge",
    "MissionPlanReleaseLineageNode",
    "build_mission_plan_release_lineage",
    "mission_plan_release_lineage_capabilities",
    "mission_plan_release_lineage_edges_csv",
    "mission_plan_release_lineage_export_payloads",
    "mission_plan_release_lineage_json",
    "mission_plan_release_lineage_markdown",
    "mission_plan_release_lineage_nodes_csv",
    "mission_plan_release_lineage_schema",
]
