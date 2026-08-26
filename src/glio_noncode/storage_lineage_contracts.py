"""Public contracts for the address-only local storage lineage graph.

The storage audit already establishes integrity and reachability. These
contracts make the relationship structure inspectable while keeping object
payloads outside the public projection. Nodes carry only addresses, relative
paths, counts, and state. Edges carry only typed references and field names.
Every value is content-addressed and rejects private or attribution metadata at
the consumer boundary.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

STORAGE_LINEAGE_VERSION = "storage-lineage-v1"
STORAGE_LINEAGE_SCHEMA_VERSION = "storage-lineage-schema-v1"
STORAGE_LINEAGE_BOUNDARY = "public_storage_lineage"
STORAGE_LINEAGE_MAX_NODES = 100_000
STORAGE_LINEAGE_MAX_EDGES = 200_000
STORAGE_LINEAGE_DEFAULT_LIMIT = 50
STORAGE_LINEAGE_MAX_LIMIT = 500
STORAGE_LINEAGE_NODE_KINDS = (
    "run",
    "batch",
    "object",
    "missing",
    "orphan",
)
STORAGE_LINEAGE_EDGE_KINDS = ("root", "reference", "missing-reference")
STORAGE_LINEAGE_RESOURCES = ("nodes", "edges")


def _text(value: Any, field: str, *, maximum: int = 500) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    result = str(value).strip()
    if not result:
        raise ValidationError(f"{field} must not be empty")
    if len(result) > maximum:
        raise ValidationError(f"{field} exceeds the maximum length")
    return result


def _optional_text(value: Any, field: str, *, maximum: int = 500) -> str | None:
    if value is None:
        return None
    return _text(value, field, maximum=maximum)


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return {str(key): item for key, item in value.items()}


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _int(value: Any, field: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be an integer")
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"{field} must be an integer") from exc
    if result < minimum or (maximum is not None and result > maximum):
        bound = f"between {minimum} and {maximum}" if maximum is not None else f"at least {minimum}"
        raise ValidationError(f"{field} must be {bound}")
    return result


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(dict(body), prefix=prefix)


def _tuple_text(value: Any, field: str, *, maximum: int = 500) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValidationError(f"{field} must be an array")
    result = tuple(_text(item, f"{field}[]", maximum=maximum) for item in value)
    if result != tuple(sorted(set(result))):
        raise ValidationError(f"{field} must be sorted and unique")
    return result


class StorageLineageNodeKind(StrEnum):
    RUN = "run"
    BATCH = "batch"
    OBJECT = "object"
    MISSING = "missing"
    ORPHAN = "orphan"


class StorageLineageEdgeKind(StrEnum):
    ROOT = "root"
    REFERENCE = "reference"
    MISSING_REFERENCE = "missing-reference"


@dataclass(frozen=True, slots=True)
class StorageLineageNode:
    """One address-only node in the storage provenance graph."""

    node_id: str
    kind: StorageLineageNodeKind
    address: str | None
    path: str | None
    accepted: bool
    root: bool
    referenced: bool
    depth: int
    in_degree: int
    out_degree: int
    content_address: str

    def _body(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "kind": self.kind,
            "address": self.address,
            "path": self.path,
            "accepted": self.accepted,
            "root": self.root,
            "referenced": self.referenced,
            "depth": self.depth,
            "in_degree": self.in_degree,
            "out_degree": self.out_degree,
        }

    def __post_init__(self) -> None:
        _text(self.node_id, "storage_lineage_node.node_id", maximum=240)
        if not isinstance(self.kind, StorageLineageNodeKind):
            raise ValidationError("storage lineage node kind is invalid")
        _optional_text(self.address, "storage_lineage_node.address", maximum=180)
        _optional_text(self.path, "storage_lineage_node.path", maximum=500)
        _bool(self.accepted, "storage_lineage_node.accepted")
        _bool(self.root, "storage_lineage_node.root")
        _bool(self.referenced, "storage_lineage_node.referenced")
        _int(self.depth, "storage_lineage_node.depth", minimum=0)
        _int(self.in_degree, "storage_lineage_node.in_degree", minimum=0)
        _int(self.out_degree, "storage_lineage_node.out_degree", minimum=0)
        expected = _address(self._body(), "storage-lineage-node")
        if expected != self.content_address:
            raise ValidationError("storage lineage node content address does not reconcile")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StorageLineageNode:
        body = _mapping(value, "storage lineage node")
        allowed = {
            "node_id",
            "kind",
            "address",
            "path",
            "accepted",
            "root",
            "referenced",
            "depth",
            "in_degree",
            "out_degree",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(
                f"storage lineage node contains unsupported fields: {sorted(unknown)}"
            )
        try:
            kind = StorageLineageNodeKind(body.get("kind"))
        except ValueError as exc:
            raise ValidationError("storage lineage node enum value is invalid") from exc
        return cls(
            node_id=_text(body.get("node_id"), "storage_lineage_node.node_id", maximum=240),
            kind=kind,
            address=_optional_text(body.get("address"), "storage_lineage_node.address", maximum=180),
            path=_optional_text(body.get("path"), "storage_lineage_node.path", maximum=500),
            accepted=_bool(body.get("accepted"), "storage_lineage_node.accepted"),
            root=_bool(body.get("root"), "storage_lineage_node.root"),
            referenced=_bool(body.get("referenced"), "storage_lineage_node.referenced"),
            depth=_int(body.get("depth"), "storage_lineage_node.depth", minimum=0),
            in_degree=_int(body.get("in_degree"), "storage_lineage_node.in_degree", minimum=0),
            out_degree=_int(body.get("out_degree"), "storage_lineage_node.out_degree", minimum=0),
            content_address=_text(
                body.get("content_address"), "storage_lineage_node.content_address"
            ),
        )


@dataclass(frozen=True, slots=True)
class StorageLineageEdge:
    """One typed relationship between graph nodes."""

    edge_id: str
    source_id: str
    target_id: str
    kind: StorageLineageEdgeKind
    field: str
    accepted: bool
    content_address: str

    def _body(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "kind": self.kind,
            "field": self.field,
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        _text(self.edge_id, "storage_lineage_edge.edge_id", maximum=240)
        _text(self.source_id, "storage_lineage_edge.source_id", maximum=240)
        _text(self.target_id, "storage_lineage_edge.target_id", maximum=240)
        if not isinstance(self.kind, StorageLineageEdgeKind):
            raise ValidationError("storage lineage edge kind is invalid")
        _text(self.field, "storage_lineage_edge.field", maximum=180)
        _bool(self.accepted, "storage_lineage_edge.accepted")
        expected = _address(self._body(), "storage-lineage-edge")
        if expected != self.content_address:
            raise ValidationError("storage lineage edge content address does not reconcile")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StorageLineageEdge:
        body = _mapping(value, "storage lineage edge")
        allowed = {
            "edge_id",
            "source_id",
            "target_id",
            "kind",
            "field",
            "accepted",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(
                f"storage lineage edge contains unsupported fields: {sorted(unknown)}"
            )
        try:
            kind = StorageLineageEdgeKind(body.get("kind"))
        except ValueError as exc:
            raise ValidationError("storage lineage edge enum value is invalid") from exc
        return cls(
            edge_id=_text(body.get("edge_id"), "storage_lineage_edge.edge_id", maximum=240),
            source_id=_text(body.get("source_id"), "storage_lineage_edge.source_id", maximum=240),
            target_id=_text(body.get("target_id"), "storage_lineage_edge.target_id", maximum=240),
            kind=kind,
            field=_text(body.get("field"), "storage_lineage_edge.field", maximum=180),
            accepted=_bool(body.get("accepted"), "storage_lineage_edge.accepted"),
            content_address=_text(
                body.get("content_address"), "storage_lineage_edge.content_address"
            ),
        )


@dataclass(frozen=True, slots=True)
class StorageLineageGraph:
    """Closed storage graph derived from one store-wide audit."""

    root: str
    audit_address: str
    nodes: tuple[StorageLineageNode, ...]
    edges: tuple[StorageLineageEdge, ...]
    root_node_ids: tuple[str, ...]
    missing_addresses: tuple[str, ...]
    orphan_addresses: tuple[str, ...]
    accepted: bool
    content_address: str

    @property
    def boundary(self) -> str:
        return STORAGE_LINEAGE_BOUNDARY

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    @property
    def object_node_count(self) -> int:
        return sum(item.kind in {StorageLineageNodeKind.OBJECT, StorageLineageNodeKind.ORPHAN} for item in self.nodes)

    @property
    def root_count(self) -> int:
        return len(self.root_node_ids)

    @property
    def missing_node_count(self) -> int:
        return sum(item.kind is StorageLineageNodeKind.MISSING for item in self.nodes)

    @property
    def orphan_node_count(self) -> int:
        return sum(item.kind is StorageLineageNodeKind.ORPHAN for item in self.nodes)

    @property
    def max_depth(self) -> int:
        return max((item.depth for item in self.nodes), default=0)

    @property
    def connected(self) -> bool:
        if not self.nodes:
            return True
        adjacency: dict[str, set[str]] = {item.node_id: set() for item in self.nodes}
        for edge in self.edges:
            adjacency[edge.source_id].add(edge.target_id)
        reachable = set(self.root_node_ids)
        pending = list(sorted(self.root_node_ids, reverse=True))
        while pending:
            source = pending.pop()
            for target in sorted(adjacency[source], reverse=True):
                if target not in reachable:
                    reachable.add(target)
                    pending.append(target)
        return reachable == {item.node_id for item in self.nodes}

    def _body(self) -> dict[str, Any]:
        return {
            "storage_lineage_version": STORAGE_LINEAGE_VERSION,
            "root": self.root,
            "audit_address": self.audit_address,
            "nodes": tuple(item.to_dict() for item in self.nodes),
            "edges": tuple(item.to_dict() for item in self.edges),
            "root_node_ids": self.root_node_ids,
            "missing_addresses": self.missing_addresses,
            "orphan_addresses": self.orphan_addresses,
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        _text(self.root, "storage_lineage.root", maximum=500)
        _text(self.audit_address, "storage_lineage.audit_address", maximum=180)
        if len(self.nodes) > STORAGE_LINEAGE_MAX_NODES:
            raise ValidationError("storage lineage node count exceeds its contract")
        if len(self.edges) > STORAGE_LINEAGE_MAX_EDGES:
            raise ValidationError("storage lineage edge count exceeds its contract")
        node_ids = tuple(item.node_id for item in self.nodes)
        edge_ids = tuple(item.edge_id for item in self.edges)
        if node_ids != tuple(sorted(node_ids)) or len(set(node_ids)) != len(node_ids):
            raise ValidationError("storage lineage nodes must be sorted and unique")
        if edge_ids != tuple(sorted(edge_ids)) or len(set(edge_ids)) != len(edge_ids):
            raise ValidationError("storage lineage edges must be sorted and unique")
        node_set = set(node_ids)
        if any(item.source_id not in node_set or item.target_id not in node_set for item in self.edges):
            raise ValidationError("storage lineage edge endpoint is not present")
        if tuple(sorted(set(self.root_node_ids))) != self.root_node_ids:
            raise ValidationError("storage lineage root node IDs must be sorted and unique")
        if not set(self.root_node_ids).issubset(node_set):
            raise ValidationError("storage lineage root node is not present")
        for field in ("missing_addresses", "orphan_addresses"):
            values = tuple(getattr(self, field))
            if values != tuple(sorted(set(values))):
                raise ValidationError(f"storage lineage {field} must be sorted and unique")
            for value in values:
                _text(value, f"storage_lineage.{field}", maximum=180)
        _bool(self.accepted, "storage_lineage.accepted")
        expected = _address(self._body(), "storage-lineage")
        if expected != self.content_address:
            raise ValidationError("storage lineage content address does not reconcile")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            self._body()
            | {
                "boundary": self.boundary,
                "node_count": self.node_count,
                "edge_count": self.edge_count,
                "object_node_count": self.object_node_count,
                "root_count": self.root_count,
                "missing_node_count": self.missing_node_count,
                "orphan_node_count": self.orphan_node_count,
                "max_depth": self.max_depth,
                "connected": self.connected,
                "content_address": self.content_address,
            }
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StorageLineageGraph:
        body = _mapping(value, "storage lineage graph")
        allowed = {
            "storage_lineage_version",
            "root",
            "audit_address",
            "nodes",
            "edges",
            "root_node_ids",
            "missing_addresses",
            "orphan_addresses",
            "accepted",
            "boundary",
            "node_count",
            "edge_count",
            "object_node_count",
            "root_count",
            "missing_node_count",
            "orphan_node_count",
            "max_depth",
            "connected",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(
                f"storage lineage graph contains unsupported fields: {sorted(unknown)}"
            )
        if body.get("storage_lineage_version") != STORAGE_LINEAGE_VERSION:
            raise ValidationError("storage lineage graph version is invalid")
        raw_nodes = body.get("nodes")
        raw_edges = body.get("edges")
        if not isinstance(raw_nodes, (list, tuple)) or not isinstance(raw_edges, (list, tuple)):
            raise ValidationError("storage lineage nodes and edges must be arrays")
        raw_roots = body.get("root_node_ids")
        raw_missing = body.get("missing_addresses")
        raw_orphans = body.get("orphan_addresses")
        if not isinstance(raw_roots, (list, tuple)):
            raise ValidationError("storage lineage root node IDs must be an array")
        if not isinstance(raw_missing, (list, tuple)) or not isinstance(raw_orphans, (list, tuple)):
            raise ValidationError("storage lineage address lists must be arrays")
        result = cls(
            root=_text(body.get("root"), "storage_lineage.root", maximum=500),
            audit_address=_text(body.get("audit_address"), "storage_lineage.audit_address", maximum=180),
            nodes=tuple(StorageLineageNode.from_mapping(item) for item in raw_nodes),
            edges=tuple(StorageLineageEdge.from_mapping(item) for item in raw_edges),
            root_node_ids=tuple(_text(item, "storage_lineage.root_node_ids", maximum=240) for item in raw_roots),
            missing_addresses=tuple(_text(item, "storage_lineage.missing_addresses", maximum=180) for item in raw_missing),
            orphan_addresses=tuple(_text(item, "storage_lineage.orphan_addresses", maximum=180) for item in raw_orphans),
            accepted=_bool(body.get("accepted"), "storage_lineage.accepted"),
            content_address=_text(body.get("content_address"), "storage_lineage.content_address"),
        )
        if body.get("boundary") not in (None, STORAGE_LINEAGE_BOUNDARY):
            raise ValidationError("storage lineage boundary is invalid")
        derived = {
            "node_count": result.node_count,
            "edge_count": result.edge_count,
            "object_node_count": result.object_node_count,
            "root_count": result.root_count,
            "missing_node_count": result.missing_node_count,
            "orphan_node_count": result.orphan_node_count,
            "max_depth": result.max_depth,
            "connected": result.connected,
        }
        for field, expected in derived.items():
            if body.get(field) != expected:
                raise ValidationError(f"storage lineage {field} does not reconcile")
        return result


@dataclass(frozen=True, slots=True)
class StorageLineageQueryResult:
    """Bounded addressable page over lineage nodes or edges."""

    resource: str
    filters: dict[str, Any]
    total: int
    offset: int
    limit: int
    items: tuple[dict[str, Any], ...]
    graph_address: str
    accepted: bool
    content_address: str

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"has_more": self.has_more}


@dataclass(frozen=True, slots=True)
class StorageLineageDiff:
    """Structural diff between two addressed lineage graphs."""

    baseline_address: str
    candidate_address: str
    added_node_ids: tuple[str, ...]
    removed_node_ids: tuple[str, ...]
    changed_node_ids: tuple[str, ...]
    added_edge_ids: tuple[str, ...]
    removed_edge_ids: tuple[str, ...]
    changed_edge_ids: tuple[str, ...]
    root_set_changed: bool
    missing_set_changed: bool
    orphan_set_changed: bool
    accepted: bool
    content_address: str

    def _body(self) -> dict[str, Any]:
        return {
            "storage_lineage_diff_version": "storage-lineage-diff-v1",
            "baseline_address": self.baseline_address,
            "candidate_address": self.candidate_address,
            "added_node_ids": self.added_node_ids,
            "removed_node_ids": self.removed_node_ids,
            "changed_node_ids": self.changed_node_ids,
            "added_edge_ids": self.added_edge_ids,
            "removed_edge_ids": self.removed_edge_ids,
            "changed_edge_ids": self.changed_edge_ids,
            "root_set_changed": self.root_set_changed,
            "missing_set_changed": self.missing_set_changed,
            "orphan_set_changed": self.orphan_set_changed,
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        _text(self.baseline_address, "storage_lineage_diff.baseline_address", maximum=180)
        _text(self.candidate_address, "storage_lineage_diff.candidate_address", maximum=180)
        for field in (
            "added_node_ids",
            "removed_node_ids",
            "changed_node_ids",
            "added_edge_ids",
            "removed_edge_ids",
            "changed_edge_ids",
        ):
            values = tuple(getattr(self, field))
            if values != tuple(sorted(set(values))):
                raise ValidationError(f"storage lineage diff {field} must be sorted and unique")
        for field in ("root_set_changed", "missing_set_changed", "orphan_set_changed", "accepted"):
            _bool(getattr(self, field), f"storage_lineage_diff.{field}")
        expected = _address(self._body(), "storage-lineage-diff")
        if expected != self.content_address:
            raise ValidationError("storage lineage diff content address does not reconcile")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StorageLineageDiff:
        body = _mapping(value, "storage lineage diff")
        allowed = {
            "storage_lineage_diff_version", "baseline_address", "candidate_address",
            "added_node_ids", "removed_node_ids", "changed_node_ids", "added_edge_ids",
            "removed_edge_ids", "changed_edge_ids", "root_set_changed", "missing_set_changed",
            "orphan_set_changed", "accepted", "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"storage lineage diff contains unsupported fields: {sorted(unknown)}")
        if body.get("storage_lineage_diff_version") != "storage-lineage-diff-v1":
            raise ValidationError("storage lineage diff version is invalid")
        return cls(
            baseline_address=_text(body.get("baseline_address"), "storage_lineage_diff.baseline_address", maximum=180),
            candidate_address=_text(body.get("candidate_address"), "storage_lineage_diff.candidate_address", maximum=180),
            added_node_ids=_tuple_text(body.get("added_node_ids"), "storage_lineage_diff.added_node_ids", maximum=320),
            removed_node_ids=_tuple_text(body.get("removed_node_ids"), "storage_lineage_diff.removed_node_ids", maximum=320),
            changed_node_ids=_tuple_text(body.get("changed_node_ids"), "storage_lineage_diff.changed_node_ids", maximum=320),
            added_edge_ids=_tuple_text(body.get("added_edge_ids"), "storage_lineage_diff.added_edge_ids", maximum=320),
            removed_edge_ids=_tuple_text(body.get("removed_edge_ids"), "storage_lineage_diff.removed_edge_ids", maximum=320),
            changed_edge_ids=_tuple_text(body.get("changed_edge_ids"), "storage_lineage_diff.changed_edge_ids", maximum=320),
            root_set_changed=_bool(body.get("root_set_changed"), "storage_lineage_diff.root_set_changed"),
            missing_set_changed=_bool(body.get("missing_set_changed"), "storage_lineage_diff.missing_set_changed"),
            orphan_set_changed=_bool(body.get("orphan_set_changed"), "storage_lineage_diff.orphan_set_changed"),
            accepted=_bool(body.get("accepted"), "storage_lineage_diff.accepted"),
            content_address=_text(body.get("content_address"), "storage_lineage_diff.content_address", maximum=180),
        )


__all__ = [
    name
    for name in globals()
    if name.startswith("STORAGE_LINEAGE") or name.startswith("StorageLineage")
]
