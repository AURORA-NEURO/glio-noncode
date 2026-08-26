"""Portable exact-byte handoffs for address-only storage lineage.

The packet contains a fixed set of graph, tabular, schema, capability,
observability, and review artifacts. It never copies local object payloads.
Writers are atomic; verifiers check every byte, path, identity, and public
boundary before offline hydration is allowed.
"""

from __future__ import annotations

import csv
import json
import os
import tempfile
from collections.abc import Iterable, Mapping
from io import StringIO
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .release_assurance_support import (
    artifact_address,
    canonical_payload,
    forbidden_keys,
    line_count,
    safe_relative_path,
)
from .serialization import canonical_json, content_hash
from .storage_lineage import (
    build_storage_lineage,
    storage_lineage_edges_csv,
    storage_lineage_json,
    storage_lineage_markdown,
    storage_lineage_nodes_csv,
    storage_lineage_capabilities,
    storage_lineage_schema,
    _as_graph,
)
from .storage_lineage_contracts import StorageLineageGraph
from .storage_lineage_observability import (
    build_storage_lineage_observability,
    storage_lineage_events_csv,
    storage_lineage_metrics_csv,
    storage_lineage_observability_capabilities,
    storage_lineage_observability_json,
    storage_lineage_observability_schema,
)
from .storage_lineage_observability_contracts import StorageLineageObservability
from .storage_lineage_packet_contracts import (
    STORAGE_LINEAGE_PACKET_ARTIFACT_COUNT,
    STORAGE_LINEAGE_PACKET_BOUNDARY,
    STORAGE_LINEAGE_PACKET_MAX_ARTIFACTS,
    STORAGE_LINEAGE_PACKET_PAYLOAD_COUNT,
    STORAGE_LINEAGE_PACKET_PAYLOAD_IDS,
    STORAGE_LINEAGE_PACKET_SCHEMA_VERSION,
    STORAGE_LINEAGE_PACKET_VERSION,
    StorageLineagePacket,
    StorageLineagePacketArtifact,
    StorageLineagePacketManifest,
    StorageLineagePacketOffline,
    StorageLineagePacketVerification,
)
from .storage_lineage_review import (
    build_storage_lineage_review_queue,
    storage_lineage_review_capabilities,
    storage_lineage_review_csv,
    storage_lineage_review_json,
    storage_lineage_review_schema,
)
from .storage_lineage_review_contracts import StorageLineageReviewQueue
from .runtime import CaseRuntime


def _artifact(
    artifact_id: str,
    relative_path: str,
    media_type: str,
    role: str,
    source_address: str,
    content: bytes,
) -> StorageLineagePacketArtifact:
    path = safe_relative_path(relative_path)
    if not artifact_id or not role or not source_address:
        raise ValidationError("lineage packet artifact metadata is incomplete")
    if not isinstance(content, bytes):
        raise ValidationError("lineage packet artifact content must be bytes")
    return StorageLineagePacketArtifact(
        artifact_id=artifact_id,
        relative_path=path,
        media_type=media_type,
        role=role,
        source_address=source_address,
        byte_count=len(content),
        line_count=line_count(content),
        content_address=artifact_address(content),
        content=content,
    )


def _graph_source(source: StorageLineageGraph | CaseRuntime | Mapping[str, Any]) -> StorageLineageGraph:
    """Normalize a live runtime or already serialized graph for packet work."""

    if isinstance(source, CaseRuntime):
        return build_storage_lineage(source)
    return _as_graph(source)


def _csv_bytes(headers: Iterable[str], rows: Iterable[Iterable[Any]]) -> bytes:
    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(tuple(headers))
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def _summary(graph: StorageLineageGraph, observation: StorageLineageObservability, queue: StorageLineageReviewQueue) -> dict[str, Any]:
    return {
        "graph_address": graph.content_address,
        "observability_address": observation.content_address,
        "review_address": queue.content_address,
        "root": graph.root,
        "node_count": graph.node_count,
        "edge_count": graph.edge_count,
        "object_node_count": graph.object_node_count,
        "root_count": graph.root_count,
        "missing_node_count": graph.missing_node_count,
        "orphan_node_count": graph.orphan_node_count,
        "max_depth": graph.max_depth,
        "connected": graph.connected,
        "event_count": len(observation.events),
        "metric_count": len(observation.metrics),
        "review_item_count": queue.item_count,
        "requires_attention": queue.requires_attention,
        "accepted": graph.accepted and observation.accepted and queue.accepted,
    }


def _payloads(
    graph: StorageLineageGraph,
    observation: StorageLineageObservability | None = None,
    queue: StorageLineageReviewQueue | None = None,
) -> tuple[tuple[str, str, str, str, bytes], ...]:
    observation = observation or build_storage_lineage_observability(graph)
    queue = queue or build_storage_lineage_review_queue(graph)
    return (
        ("graph-json", "lineage/graph.json", "application/json", "graph", (storage_lineage_json(graph) + "\n").encode("utf-8")),
        ("nodes-csv", "lineage/nodes.csv", "text/csv", "nodes", storage_lineage_nodes_csv(graph).encode("utf-8")),
        ("edges-csv", "lineage/edges.csv", "text/csv", "edges", storage_lineage_edges_csv(graph).encode("utf-8")),
        ("summary-json", "lineage/summary.json", "application/json", "summary", canonical_payload(_summary(graph, observation, queue))),
        ("schema-json", "lineage/schema.json", "application/json", "schema", canonical_payload(storage_lineage_schema())),
        ("capabilities-json", "lineage/capabilities.json", "application/json", "capabilities", canonical_payload(storage_lineage_capabilities())),
        ("observability-json", "lineage/observability.json", "application/json", "observability", (storage_lineage_observability_json(observation) + "\n").encode("utf-8")),
        ("events-csv", "lineage/events.csv", "text/csv", "events", storage_lineage_events_csv(observation).encode("utf-8")),
        ("review-queue-json", "lineage/review-queue.json", "application/json", "review", (storage_lineage_review_json(queue) + "\n").encode("utf-8")),
        ("review-csv", "lineage/review.csv", "text/csv", "review-table", storage_lineage_review_csv(queue).encode("utf-8")),
    )


def storage_lineage_packet_artifact_payloads(
    source: StorageLineageGraph | CaseRuntime | Mapping[str, Any],
) -> dict[str, bytes]:
    """Return exact fixed payload bytes keyed by artifact ID."""

    graph = _graph_source(source)
    return {artifact_id: content for artifact_id, _path, _media, _role, content in _payloads(graph)}


def build_storage_lineage_packet(
    source: StorageLineageGraph | CaseRuntime | Mapping[str, Any],
    *,
    packet_id: str = "glio-noncode-storage-lineage-packet",
) -> StorageLineagePacket:
    """Build a fixed graph packet without copying source object payloads."""

    graph = _graph_source(source)
    if not packet_id.strip():
        raise ValidationError("storage lineage packet ID must not be empty")
    observation = build_storage_lineage_observability(graph)
    queue = build_storage_lineage_review_queue(graph)
    values = _payloads(graph, observation, queue)
    if len(values) != STORAGE_LINEAGE_PACKET_PAYLOAD_COUNT:
        raise ValidationError("storage lineage packet payload denominator is not closed")
    artifacts = tuple(
        _artifact(artifact_id, path, media_type, role, graph.content_address, content)
        for artifact_id, path, media_type, role, content in values
    )
    if tuple(item.artifact_id for item in artifacts) != STORAGE_LINEAGE_PACKET_PAYLOAD_IDS:
        raise ValidationError("storage lineage packet payload IDs are not closed")
    metadata = tuple(item.metadata_dict() for item in artifacts)
    manifest_body = {
        "version": STORAGE_LINEAGE_PACKET_VERSION,
        "schema_version": STORAGE_LINEAGE_PACKET_SCHEMA_VERSION,
        "packet_id": packet_id,
        "graph_address": graph.content_address,
        "observability_address": observation.content_address,
        "review_address": queue.content_address,
        "artifact_count": STORAGE_LINEAGE_PACKET_ARTIFACT_COUNT,
        "payload_artifact_count": len(artifacts),
        "artifacts": metadata,
        "accepted": graph.accepted and observation.accepted and queue.accepted,
    }
    manifest = StorageLineagePacketManifest(
        **manifest_body,
        content_address=content_hash(manifest_body, prefix="storage-lineage-packet-manifest"),
    )
    body = {
        "packet_id": packet_id,
        "graph_address": graph.content_address,
        "observability_address": observation.content_address,
        "review_address": queue.content_address,
        "artifacts": metadata,
        "manifest": manifest.to_dict(),
        "accepted": manifest.accepted,
    }
    return StorageLineagePacket(
        packet_id=packet_id,
        graph_address=graph.content_address,
        observability_address=observation.content_address,
        review_address=queue.content_address,
        artifacts=artifacts,
        manifest=manifest,
        accepted=manifest.accepted,
        content_address=content_hash(body, prefix="storage-lineage-packet"),
    )


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        temporary = Path(temporary_name)
        if temporary.exists():
            temporary.unlink()


def write_storage_lineage_packet(
    packet: StorageLineagePacket,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> Path:
    """Write all fixed files with atomic sibling replacement."""

    if not isinstance(packet, StorageLineagePacket):
        raise ValidationError("storage lineage packet writer requires a typed packet")
    root = Path(destination)
    if root.exists() and root.is_symlink():
        raise ValidationError("storage lineage packet destination must not be a symlink")
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()) and not allow_existing:
        raise ValidationError("storage lineage packet destination is not empty")
    for artifact in packet.artifacts:
        _atomic_write(root / safe_relative_path(artifact.relative_path), artifact.content)
    _atomic_write(root / "manifest.json", (canonical_json(packet.manifest.to_dict()) + "\n").encode("utf-8"))
    return root


def _read_manifest(directory: str | Path) -> tuple[Path, dict[str, Any], tuple[str, ...]]:
    root = Path(directory)
    path = root / "manifest.json"
    if not path.is_file() or path.is_symlink():
        return root, {}, ("manifest.json",)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return root, {}, ("manifest.json",)
    if not isinstance(value, dict):
        return root, {}, ("manifest.json",)
    body = {key: value.get(key) for key in (
        "version", "schema_version", "packet_id", "graph_address", "observability_address",
        "review_address", "artifact_count", "payload_artifact_count", "artifacts", "accepted",
    )}
    drift: list[str] = []
    if value.get("content_address") != content_hash(body, prefix="storage-lineage-packet-manifest"):
        drift.append("manifest.content_address")
    if value.get("version") != STORAGE_LINEAGE_PACKET_VERSION:
        drift.append("manifest.version")
    if value.get("schema_version") != STORAGE_LINEAGE_PACKET_SCHEMA_VERSION:
        drift.append("manifest.schema_version")
    try:
        StorageLineagePacketManifest.from_mapping(value)
    except ValidationError:
        drift.append("manifest.contract")
    return root, value, tuple(drift)


def _empty_verification(root: Path) -> StorageLineagePacketVerification:
    body = {
        "directory": str(root),
        "packet_id": "",
        "graph_address": "",
        "observability_address": "",
        "review_address": "",
        "checked_artifact_count": 0,
        "missing_paths": ("manifest.json",),
        "unexpected_paths": (),
        "unsafe_paths": (),
        "tampered_paths": (),
        "duplicate_paths": (),
        "manifest_drift": (),
        "boundary_violations": (),
        "accepted": False,
    }
    return StorageLineagePacketVerification(**body, content_address=content_hash(body, prefix="storage-lineage-packet-verification"))


def _listed(manifest: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    rows = manifest.get("artifacts", ())
    if not isinstance(rows, list):
        return ()
    return tuple(item for item in rows if isinstance(item, dict))


def _symlinked(root: Path, relative_path: str) -> bool:
    if root.is_symlink():
        return True
    current = root
    for part in Path(relative_path).parts:
        current /= part
        if current.is_symlink():
            return True
    return False


def _text_boundary(payload: bytes) -> tuple[str, ...]:
    try:
        text = payload.decode("utf-8").casefold()
    except UnicodeDecodeError:
        return ("$invalid-utf8",)
    return tuple(f"$text:{token}" for token in ("agent", "assistant", "author", "email", "identity", "language", "model", "patient", "producer", "subject") if token in text)


def verify_storage_lineage_packet(directory: str | Path) -> StorageLineagePacketVerification:
    """Verify bytes, fixed paths, graph identity, and public metadata boundaries."""

    root, manifest, manifest_drift = _read_manifest(directory)
    if not manifest:
        return _empty_verification(root)
    missing: list[str] = []
    unexpected: list[str] = []
    unsafe: list[str] = []
    tampered: list[str] = []
    duplicate_paths: list[str] = []
    boundary: list[str] = []
    expected_paths: list[str] = []
    artifact_ids: list[str] = []
    listed = _listed(manifest)
    try:
        payload_count = int(manifest.get("payload_artifact_count"))
        artifact_count = int(manifest.get("artifact_count"))
    except (TypeError, ValueError, OverflowError):
        payload_count = -1
        artifact_count = -1
        manifest_drift = (*manifest_drift, "manifest.counts")
    if len(listed) != payload_count:
        manifest_drift = (*manifest_drift, "manifest.payload_artifact_count")
    if artifact_count != len(listed) + 1:
        manifest_drift = (*manifest_drift, "manifest.artifact_count")
    if len(listed) != STORAGE_LINEAGE_PACKET_PAYLOAD_COUNT:
        manifest_drift = (*manifest_drift, "manifest.payload_denominator")
    if len(listed) > STORAGE_LINEAGE_PACKET_MAX_ARTIFACTS:
        manifest_drift = (*manifest_drift, "manifest.max_artifacts")
    graph_payload: Mapping[str, Any] | None = None
    observation_payload: Mapping[str, Any] | None = None
    review_payload: Mapping[str, Any] | None = None
    for item in listed:
        artifact_id = str(item.get("artifact_id", ""))
        path_text = str(item.get("relative_path", ""))
        if artifact_id in artifact_ids:
            manifest_drift = (*manifest_drift, f"manifest.duplicate_artifact_id:{artifact_id}")
        artifact_ids.append(artifact_id)
        try:
            path = safe_relative_path(path_text)
        except ValidationError:
            unsafe.append(path_text)
            continue
        if path in expected_paths:
            duplicate_paths.append(path)
            manifest_drift = (*manifest_drift, f"manifest.duplicate_path:{path}")
        expected_paths.append(path)
        target = root / path
        if _symlinked(root, path):
            unsafe.append(path)
            continue
        if not target.is_file():
            missing.append(path)
            continue
        try:
            payload = target.read_bytes()
        except OSError:
            tampered.append(path)
            continue
        try:
            expected_bytes = int(item.get("byte_count", -1))
            expected_lines = int(item.get("line_count", -1))
        except (TypeError, ValueError, OverflowError):
            expected_bytes = -1
            expected_lines = -1
            manifest_drift = (*manifest_drift, f"manifest.counts:{path}")
        if len(payload) != expected_bytes or line_count(payload) != expected_lines or artifact_address(payload) != item.get("content_address"):
            tampered.append(path)
        if item.get("media_type") == "application/json":
            try:
                decoded = json.loads(payload.decode("utf-8"))
                boundary.extend(f"{path}:{value}" for value in forbidden_keys(decoded))
                if artifact_id == "graph-json" and isinstance(decoded, Mapping):
                    graph_payload = decoded
                if artifact_id == "observability-json" and isinstance(decoded, Mapping):
                    observation_payload = decoded
                if artifact_id == "review-queue-json" and isinstance(decoded, Mapping):
                    review_payload = decoded
            except (UnicodeError, json.JSONDecodeError):
                tampered.append(path)
        else:
            boundary.extend(f"{path}:{value}" for value in _text_boundary(payload))
    if tuple(artifact_ids) != STORAGE_LINEAGE_PACKET_PAYLOAD_IDS:
        manifest_drift = (*manifest_drift, "manifest.payload_ids")
    graph_ok = False
    observation_ok = False
    review_ok = False
    graph_address = str(manifest.get("graph_address", ""))
    observation_address = str(manifest.get("observability_address", ""))
    review_address = str(manifest.get("review_address", ""))
    if graph_payload is not None:
        try:
            graph = StorageLineageGraph.from_mapping(graph_payload)
            graph_ok = graph.content_address == graph_address
            if not graph_ok:
                manifest_drift = (*manifest_drift, "manifest.graph_identity")
        except ValidationError:
            tampered.append("lineage/graph.json")
    if observation_payload is not None:
        try:
            observation = StorageLineageObservability.from_mapping(observation_payload)
            observation_ok = observation.content_address == observation_address and observation.graph_address == graph_address
            if not observation_ok:
                manifest_drift = (*manifest_drift, "manifest.observability_identity")
        except ValidationError:
            tampered.append("lineage/observability.json")
    if review_payload is not None:
        try:
            queue = StorageLineageReviewQueue.from_mapping(review_payload)
            review_ok = queue.content_address == review_address and queue.graph_address == graph_address
            if not review_ok:
                manifest_drift = (*manifest_drift, "manifest.review_identity")
        except ValidationError:
            tampered.append("lineage/review-queue.json")
    actual_paths = sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file() or path.is_symlink())
    unexpected.extend(path for path in actual_paths if path not in sorted((*expected_paths, "manifest.json")))
    accepted = bool(
        manifest.get("accepted")
        and str(manifest.get("packet_id", ""))
        and graph_address
        and observation_address
        and review_address
        and len(listed) == STORAGE_LINEAGE_PACKET_PAYLOAD_COUNT
        and tuple(artifact_ids) == STORAGE_LINEAGE_PACKET_PAYLOAD_IDS
        and graph_ok
        and observation_ok
        and review_ok
        and not any((missing, unexpected, unsafe, tampered, duplicate_paths, boundary, manifest_drift))
    )
    body = {
        "directory": str(root),
        "packet_id": str(manifest.get("packet_id", "")),
        "graph_address": graph_address,
        "observability_address": observation_address,
        "review_address": review_address,
        "checked_artifact_count": len(listed),
        "missing_paths": tuple(sorted(set(missing))),
        "unexpected_paths": tuple(sorted(set(unexpected))),
        "unsafe_paths": tuple(sorted(set(unsafe))),
        "tampered_paths": tuple(sorted(set(tampered))),
        "duplicate_paths": tuple(sorted(set(duplicate_paths))),
        "manifest_drift": tuple(sorted(set(manifest_drift))),
        "boundary_violations": tuple(sorted(set(boundary))),
        "accepted": accepted,
    }
    return StorageLineagePacketVerification(**body, content_address=content_hash(body, prefix="storage-lineage-packet-verification"))


def load_storage_lineage_packet(directory: str | Path) -> StorageLineagePacketOffline:
    """Hydrate all address-only projections only after verification succeeds."""

    root, manifest, _drift = _read_manifest(directory)
    verification = verify_storage_lineage_packet(root)
    if not verification.accepted:
        raise ValidationError("storage lineage packet is not accepted")
    try:
        graph_payload = json.loads((root / "lineage" / "graph.json").read_text(encoding="utf-8"))
        observation_payload = json.loads((root / "lineage" / "observability.json").read_text(encoding="utf-8"))
        review_payload = json.loads((root / "lineage" / "review-queue.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError("storage lineage packet JSON payload is not valid") from exc
    graph = StorageLineageGraph.from_mapping(graph_payload)
    observation = StorageLineageObservability.from_mapping(observation_payload)
    queue = StorageLineageReviewQueue.from_mapping(review_payload)
    if (graph.content_address, observation.content_address, queue.content_address) != (manifest.get("graph_address"), manifest.get("observability_address"), manifest.get("review_address")):
        raise ValidationError("storage lineage packet source identity does not reconcile")
    body = {
        "packet_id": str(manifest.get("packet_id", "")),
        "graph": graph.to_dict(),
        "observability": observation.to_dict(),
        "review_queue": queue.to_dict(),
        "manifest": manifest,
        "verification": verification.to_dict(),
    }
    return StorageLineagePacketOffline(
        packet_id=str(manifest.get("packet_id", "")),
        graph=graph,
        observability=observation,
        review_queue=queue,
        manifest=manifest,
        verification=verification,
        content_address=content_hash(body, prefix="storage-lineage-packet-offline"),
    )


def storage_lineage_packet_json(packet: StorageLineagePacket, *, include_content: bool = False) -> str:
    if not isinstance(packet, StorageLineagePacket):
        raise ValidationError("storage lineage packet JSON requires a typed packet")
    return canonical_json(packet.to_dict(include_content=include_content))


def storage_lineage_packet_capabilities() -> dict[str, Any]:
    return {
        "version": STORAGE_LINEAGE_PACKET_VERSION,
        "schema_version": STORAGE_LINEAGE_PACKET_SCHEMA_VERSION,
        "boundary": STORAGE_LINEAGE_PACKET_BOUNDARY,
        "fixed_payload_count": True,
        "manifest_address": True,
        "atomic_write": True,
        "exact_byte_verification": True,
        "safe_path_verification": True,
        "symlink_rejection": True,
        "duplicate_path_detection": True,
        "unexpected_file_detection": True,
        "tamper_detection": True,
        "graph_identity_verification": True,
        "observability_identity_verification": True,
        "review_identity_verification": True,
        "boundary_scan": True,
        "offline_hydration": True,
        "source_payloads": False,
        "timestamp_free": True,
        "payload_ids": STORAGE_LINEAGE_PACKET_PAYLOAD_IDS,
        "payload_count": STORAGE_LINEAGE_PACKET_PAYLOAD_COUNT,
        "artifact_count": STORAGE_LINEAGE_PACKET_ARTIFACT_COUNT,
    }


def storage_lineage_packet_schema() -> dict[str, Any]:
    return {
        "version": STORAGE_LINEAGE_PACKET_SCHEMA_VERSION,
        "type": "object",
        "boundary": STORAGE_LINEAGE_PACKET_BOUNDARY,
        "required": (
            "packet_id", "graph_address", "observability_address", "review_address",
            "artifacts", "manifest", "accepted", "content_address",
        ),
        "payload_count": STORAGE_LINEAGE_PACKET_PAYLOAD_COUNT,
        "artifact_count": STORAGE_LINEAGE_PACKET_ARTIFACT_COUNT,
        "payload_ids": STORAGE_LINEAGE_PACKET_PAYLOAD_IDS,
        "artifact_roles": ("graph", "nodes", "edges", "summary", "schema", "capabilities", "observability", "events", "review", "review-table"),
        "manifest": {
            "type": "object",
            "required": (
                "version", "schema_version", "packet_id", "graph_address", "observability_address",
                "review_address", "artifact_count", "payload_artifact_count", "artifacts", "accepted", "content_address",
            ),
        },
        "verification": {
            "exact_bytes": True,
            "content_addresses": True,
            "graph_identity": True,
            "observability_identity": True,
            "review_identity": True,
            "safe_paths": True,
            "unexpected_paths": True,
            "public_boundary": True,
        },
        "source_payloads": False,
        "timestamp_free": True,
    }


__all__ = [
    name
    for name in globals()
    if name.startswith("STORAGE_LINEAGE_PACKET")
    or name.startswith("StorageLineagePacket")
    or name.startswith("build_storage_lineage_packet")
    or name.startswith("load_storage_lineage_packet")
    or name.startswith("storage_lineage_packet")
    or name.startswith("verify_storage_lineage_packet")
    or name.startswith("write_storage_lineage_packet")
]
