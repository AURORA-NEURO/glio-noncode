"""Address-only lineage graph for a cross-run portfolio release."""

from __future__ import annotations

from collections import defaultdict, deque
from enum import StrEnum
from typing import Any

from .module_fabric_support import contains_private_key
from .portfolio_release_contracts import PortfolioReleaseBundle
from .run_workspace import _has_forbidden_key
from .serialization import content_hash

PORTFOLIO_RELEASE_LINEAGE_VERSION = "portfolio-release-lineage-v1"


class PortfolioLineageNodeKind(StrEnum):
    """Node classes in the public handoff graph."""

    RELEASE = "release"
    MEMBER = "member"
    ARTIFACT = "artifact"
    CHECK = "check"


class PortfolioLineageEdgeKind(StrEnum):
    """Directed relationships retained in the address-only graph."""

    CONTAINS_MEMBER = "contains_member"
    CONTAINS_ARTIFACT = "contains_artifact"
    MEMBER_ARTIFACT = "member_artifact"
    ASSERTS = "asserts"


class PortfolioLineageNode:
    """One public graph node with no artifact payload."""

    __slots__ = ("node_id", "kind", "address", "run_id", "label", "content_address")

    def __init__(
        self,
        node_id: str,
        kind: PortfolioLineageNodeKind,
        address: str,
        run_id: str | None,
        label: str,
        content_address: str,
    ) -> None:
        self.node_id = node_id
        self.kind = kind
        self.address = address
        self.run_id = run_id
        self.label = label
        self.content_address = content_address

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "kind": self.kind.value,
            "address": self.address,
            "run_id": self.run_id,
            "label": self.label,
            "content_address": self.content_address,
        }


class PortfolioLineageEdge:
    """One directed edge between two declared graph nodes."""

    __slots__ = ("edge_id", "source_id", "target_id", "kind", "ordinal", "content_address")

    def __init__(
        self,
        edge_id: str,
        source_id: str,
        target_id: str,
        kind: PortfolioLineageEdgeKind,
        ordinal: int,
        content_address: str,
    ) -> None:
        self.edge_id = edge_id
        self.source_id = source_id
        self.target_id = target_id
        self.kind = kind
        self.ordinal = ordinal
        self.content_address = content_address

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "kind": self.kind.value,
            "ordinal": self.ordinal,
            "content_address": self.content_address,
        }


class PortfolioReleaseLineage:
    """Immutable graph projection for one portfolio bundle."""

    __slots__ = (
        "release_id",
        "release_address",
        "nodes",
        "edges",
        "accepted",
        "content_address",
    )

    def __init__(
        self,
        release_id: str,
        release_address: str,
        nodes: tuple[PortfolioLineageNode, ...],
        edges: tuple[PortfolioLineageEdge, ...],
        accepted: bool,
        content_address: str,
    ) -> None:
        self.release_id = release_id
        self.release_address = release_address
        self.nodes = nodes
        self.edges = edges
        self.accepted = accepted
        self.content_address = content_address

    @property
    def node_count(self) -> int:
        """Return the number of graph nodes."""

        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        """Return the number of graph edges."""

        return len(self.edges)

    @property
    def member_count(self) -> int:
        """Return the number of run member nodes."""

        return sum(item.kind is PortfolioLineageNodeKind.MEMBER for item in self.nodes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "lineage_version": PORTFOLIO_RELEASE_LINEAGE_VERSION,
            "release_id": self.release_id,
            "release_address": self.release_address,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "member_count": self.member_count,
            "nodes": [item.to_dict() for item in self.nodes],
            "edges": [item.to_dict() for item in self.edges],
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _node(
    node_id: str,
    kind: PortfolioLineageNodeKind,
    address: str,
    run_id: str | None,
    label: str,
) -> PortfolioLineageNode:
    """Create an addressed node from public metadata."""

    body = {
        "node_id": node_id,
        "kind": kind.value,
        "address": address,
        "run_id": run_id,
        "label": label,
    }
    return PortfolioLineageNode(
        node_id=node_id,
        kind=kind,
        address=address,
        run_id=run_id,
        label=label,
        content_address=content_hash(body, prefix="portfolio-lineage-node"),
    )


def _edge(
    edge_id: str,
    source_id: str,
    target_id: str,
    kind: PortfolioLineageEdgeKind,
    ordinal: int,
) -> PortfolioLineageEdge:
    """Create an addressed edge from stable graph identities."""

    body = {
        "edge_id": edge_id,
        "source_id": source_id,
        "target_id": target_id,
        "kind": kind.value,
        "ordinal": ordinal,
    }
    return PortfolioLineageEdge(
        edge_id=edge_id,
        source_id=source_id,
        target_id=target_id,
        kind=kind,
        ordinal=ordinal,
        content_address=content_hash(body, prefix="portfolio-lineage-edge"),
    )


def _is_acyclic(nodes: tuple[PortfolioLineageNode, ...], edges: tuple[PortfolioLineageEdge, ...]) -> bool:
    """Check directed acyclicity using Kahn's deterministic topological pass."""

    node_ids = {item.node_id for item in nodes}
    outgoing: dict[str, list[str]] = defaultdict(list)
    indegree = {item: 0 for item in node_ids}
    for edge in edges:
        if edge.source_id not in node_ids or edge.target_id not in node_ids:
            return False
        outgoing[edge.source_id].append(edge.target_id)
        indegree[edge.target_id] += 1
    queue = deque(sorted(item for item, degree in indegree.items() if degree == 0))
    visited = 0
    while queue:
        current = queue.popleft()
        visited += 1
        for target in sorted(outgoing.get(current, ())):
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    return visited == len(node_ids)


def build_portfolio_release_lineage(
    bundle: PortfolioReleaseBundle,
    *,
    run_id: str | None = None,
) -> PortfolioReleaseLineage:
    """Build a deterministic release → member → artifact/check graph."""

    selected_members = tuple(
        item for item in bundle.members if run_id is None or item.run_id == str(run_id).strip()
    )
    member_ids = {item.run_id for item in selected_members}
    selected_artifacts = tuple(
        item
        for item in bundle.artifacts
        if item.member_run_id is None or item.member_run_id in member_ids
    )
    nodes: list[PortfolioLineageNode] = [
        _node(
            f"release:{bundle.release_id}",
            PortfolioLineageNodeKind.RELEASE,
            bundle.content_address,
            None,
            bundle.release_id,
        )
    ]
    edges: list[PortfolioLineageEdge] = []
    ordinal = 0
    root_id = nodes[0].node_id
    for member in sorted(selected_members, key=lambda item: item.run_id):
        member_node_id = f"member:{member.run_id}"
        nodes.append(
            _node(
                member_node_id,
                PortfolioLineageNodeKind.MEMBER,
                member.content_address,
                member.run_id,
                member.case_id,
            )
        )
        edges.append(_edge(f"edge-{ordinal:05d}", root_id, member_node_id, PortfolioLineageEdgeKind.CONTAINS_MEMBER, ordinal))
        ordinal += 1
    selected_artifact_ids = {item.artifact_id for item in selected_artifacts}
    for artifact in sorted(selected_artifacts, key=lambda item: item.artifact_id):
        artifact_node_id = f"artifact:{artifact.artifact_id}"
        nodes.append(
            _node(
                artifact_node_id,
                PortfolioLineageNodeKind.ARTIFACT,
                artifact.content_address,
                artifact.member_run_id,
                artifact.relative_path,
            )
        )
        source_id = (
            f"member:{artifact.member_run_id}"
            if artifact.member_run_id in member_ids
            else root_id
        )
        edge_kind = (
            PortfolioLineageEdgeKind.MEMBER_ARTIFACT
            if artifact.member_run_id in member_ids
            else PortfolioLineageEdgeKind.CONTAINS_ARTIFACT
        )
        edges.append(_edge(f"edge-{ordinal:05d}", source_id, artifact_node_id, edge_kind, ordinal))
        ordinal += 1
    for check in sorted(bundle.checks, key=lambda item: item.check_id):
        check_node_id = f"check:{check.check_id}"
        nodes.append(
            _node(
                check_node_id,
                PortfolioLineageNodeKind.CHECK,
                check.content_address,
                None,
                check.detail,
            )
        )
        edges.append(_edge(f"edge-{ordinal:05d}", root_id, check_node_id, PortfolioLineageEdgeKind.ASSERTS, ordinal))
        ordinal += 1
    node_tuple = tuple(sorted(nodes, key=lambda item: item.node_id))
    edge_tuple = tuple(sorted(edges, key=lambda item: (item.ordinal, item.edge_id)))
    unique_ids = len({item.node_id for item in node_tuple}) == len(node_tuple)
    unique_edges = len({item.edge_id for item in edge_tuple}) == len(edge_tuple)
    boundary_safe = not _has_forbidden_key({"nodes": [item.to_dict() for item in node_tuple], "edges": [item.to_dict() for item in edge_tuple]}) and not contains_private_key({"nodes": [item.to_dict() for item in node_tuple], "edges": [item.to_dict() for item in edge_tuple]})
    accepted = bool(selected_members) and unique_ids and unique_edges and _is_acyclic(node_tuple, edge_tuple) and boundary_safe and selected_artifact_ids.issuperset({artifact.artifact_id for artifact in selected_artifacts})
    body = {
        "lineage_version": PORTFOLIO_RELEASE_LINEAGE_VERSION,
        "release_id": bundle.release_id,
        "release_address": bundle.content_address,
        "nodes": [item.to_dict() for item in node_tuple],
        "edges": [item.to_dict() for item in edge_tuple],
        "accepted": accepted,
    }
    return PortfolioReleaseLineage(
        release_id=bundle.release_id,
        release_address=bundle.content_address,
        nodes=node_tuple,
        edges=edge_tuple,
        accepted=accepted,
        content_address=content_hash(body, prefix="portfolio-release-lineage"),
    )


def lineage_descendants(
    lineage: PortfolioReleaseLineage,
    node_id: str,
) -> tuple[PortfolioLineageNode, ...]:
    """Return deterministic downstream nodes from one graph identity."""

    by_id = {item.node_id: item for item in lineage.nodes}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for edge in lineage.edges:
        outgoing[edge.source_id].append(edge.target_id)
    if node_id not in by_id:
        return ()
    queue = deque(sorted(outgoing.get(node_id, ())))
    seen: set[str] = set()
    result: list[PortfolioLineageNode] = []
    while queue:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        if current in by_id:
            result.append(by_id[current])
        queue.extend(sorted(outgoing.get(current, ())))
    return tuple(sorted(result, key=lambda item: item.node_id))


def lineage_for_run(
    lineage: PortfolioReleaseLineage,
    run_id: str,
) -> dict[str, Any]:
    """Return a bounded run-focused lineage projection."""

    member_id = f"member:{str(run_id).strip()}"
    member = next((item for item in lineage.nodes if item.node_id == member_id), None)
    descendants = lineage_descendants(lineage, member_id)
    body = {
        "run_id": str(run_id).strip(),
        "member": member.to_dict() if member else None,
        "descendants": [item.to_dict() for item in descendants],
        "accepted": member is not None and lineage.accepted,
    }
    return body | {"content_address": content_hash(body, prefix="portfolio-release-run-lineage")}


__all__ = [
    "PORTFOLIO_RELEASE_LINEAGE_VERSION",
    "PortfolioLineageEdge",
    "PortfolioLineageEdgeKind",
    "PortfolioLineageNode",
    "PortfolioLineageNodeKind",
    "PortfolioReleaseLineage",
    "build_portfolio_release_lineage",
    "lineage_descendants",
    "lineage_for_run",
]
