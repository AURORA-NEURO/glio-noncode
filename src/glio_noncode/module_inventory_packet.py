"""Build, write, verify, and load the module inventory offline packet."""

from __future__ import annotations

import csv
import io
import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from .errors import ValidationError
from .module_inventory import build_module_inventory
from .module_inventory_audit import audit_module_inventory
from .module_inventory_contracts import ModuleInventory
from .module_inventory_exports import (
    module_inventory_dependencies_csv,
    module_inventory_indexes_csv,
    module_inventory_json,
    module_inventory_modules_csv,
    module_inventory_summary,
    module_inventory_symbols_csv,
)
from .module_inventory_graph import build_module_inventory_graph
from .module_inventory_packet_contracts import (
    MODULE_INVENTORY_PACKET_ARTIFACT_COUNT,
    MODULE_INVENTORY_PACKET_ARTIFACT_PREFIX,
    MODULE_INVENTORY_PACKET_BOUNDARY,
    MODULE_INVENTORY_PACKET_MANIFEST,
    MODULE_INVENTORY_PACKET_VERSION,
    ModuleInventoryPacket,
    ModuleInventoryPacketArtifact,
    ModuleInventoryPacketArtifactKind,
    ModuleInventoryPacketCheck,
    ModuleInventoryPacketCheckPlane,
    ModuleInventoryPacketState,
    ModuleInventoryPacketVerification,
)
from .module_inventory_runtime import module_inventory_runtime_json, run_module_inventory
from .run_workspace import _has_forbidden_key
from .serialization import canonical_json, hash_bytes, jsonable

_JSON = "application/json"
_CSV = "text/csv"


def _safe_path(value: str) -> bool:
    if not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return (
        not path.is_absolute()
        and bool(path.parts)
        and all(part not in {"", ".", ".."} for part in path.parts)
    )


def _atomic_write(path: Path, payload: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _json_text(value: Any) -> str:
    projected = jsonable(value)
    if _has_forbidden_key(projected):
        raise ValidationError("module inventory packet crosses the public boundary")
    return canonical_json(projected) + "\n"


def _csv_text(rows: list[Mapping[str, Any]], fields: tuple[str, ...]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                field: ";".join(str(item) for item in row.get(field, ()))
                if isinstance(row.get(field), (list, tuple))
                else row.get(field, "")
                for field in fields
            }
        )
    return output.getvalue()


def _artifact(
    artifact_id: str,
    relative_path: str,
    kind: ModuleInventoryPacketArtifactKind,
    media_type: str,
    text: str,
) -> ModuleInventoryPacketArtifact:
    if not _safe_path(relative_path):
        raise ValidationError(f"unsafe module inventory packet path: {relative_path}")
    encoded = text.encode("utf-8")
    return ModuleInventoryPacketArtifact(
        artifact_id=artifact_id,
        relative_path=relative_path,
        media_type=media_type,
        kind=kind,
        byte_count=len(encoded),
        line_count=len(text.splitlines()),
        content_address=hash_bytes(encoded, prefix=MODULE_INVENTORY_PACKET_ARTIFACT_PREFIX),
        payload=text,
    )


def _check(
    check_id: str,
    plane: ModuleInventoryPacketCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleInventoryPacketCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    from .serialization import content_hash

    return ModuleInventoryPacketCheck(
        **body, content_address=content_hash(body, prefix="module-inventory-packet-check")
    )


def _packet_address(
    packet_id: str,
    inventory_address: str,
    runtime_address: str,
    state: ModuleInventoryPacketState,
    artifacts: tuple[ModuleInventoryPacketArtifact, ...],
    checks: tuple[ModuleInventoryPacketCheck, ...],
) -> str:
    from .serialization import content_hash

    body = {
        "packet_id": packet_id,
        "version": MODULE_INVENTORY_PACKET_VERSION,
        "boundary": MODULE_INVENTORY_PACKET_BOUNDARY,
        "inventory_address": inventory_address,
        "runtime_address": runtime_address,
        "state": state,
        "accepted": all(item.passed for item in checks),
        "artifacts": tuple(item.to_dict(include_payload=False) for item in artifacts),
        "checks": checks,
    }
    return content_hash(body, prefix="module-inventory-packet")


def _artifact_specs(
    inventory: ModuleInventory, runtime: Any
) -> tuple[ModuleInventoryPacketArtifact, ...]:
    graph = build_module_inventory_graph(inventory)
    audit = audit_module_inventory(inventory)
    graph_text = _json_text(graph.to_dict())
    capabilities = {
        "version": MODULE_INVENTORY_PACKET_VERSION,
        "artifact_count": MODULE_INVENTORY_PACKET_ARTIFACT_COUNT,
        "artifact_ids": [
            "inventory",
            "graph",
            "modules",
            "symbols",
            "dependencies",
            "indexes",
            "summary",
            "audit",
            "runtime",
            "capabilities",
        ],
        "offline": True,
        "read_only": True,
    }
    return (
        _artifact(
            "inventory",
            "inventory.json",
            ModuleInventoryPacketArtifactKind.INVENTORY,
            _JSON,
            module_inventory_json(inventory),
        ),
        _artifact(
            "graph", "graph.json", ModuleInventoryPacketArtifactKind.GRAPH, _JSON, graph_text
        ),
        _artifact(
            "modules",
            "modules.csv",
            ModuleInventoryPacketArtifactKind.MODULES,
            _CSV,
            module_inventory_modules_csv(inventory),
        ),
        _artifact(
            "symbols",
            "symbols.csv",
            ModuleInventoryPacketArtifactKind.SYMBOLS,
            _CSV,
            module_inventory_symbols_csv(inventory),
        ),
        _artifact(
            "dependencies",
            "dependencies.csv",
            ModuleInventoryPacketArtifactKind.DEPENDENCIES,
            _CSV,
            module_inventory_dependencies_csv(inventory),
        ),
        _artifact(
            "indexes",
            "indexes.csv",
            ModuleInventoryPacketArtifactKind.INDEXES,
            _CSV,
            module_inventory_indexes_csv(inventory),
        ),
        _artifact(
            "summary",
            "summary.json",
            ModuleInventoryPacketArtifactKind.SUMMARY,
            _JSON,
            _json_text(module_inventory_summary(inventory)),
        ),
        _artifact(
            "audit", "audit.json", ModuleInventoryPacketArtifactKind.AUDIT, _JSON, _json_text(audit)
        ),
        _artifact(
            "runtime",
            "runtime.json",
            ModuleInventoryPacketArtifactKind.RUNTIME,
            _JSON,
            module_inventory_runtime_json(runtime),
        ),
        _artifact(
            "capabilities",
            "capabilities.json",
            ModuleInventoryPacketArtifactKind.SUMMARY,
            _JSON,
            _json_text(capabilities),
        ),
    )


def build_module_inventory_packet(
    inventory: ModuleInventory | None = None,
    runtime: Any | None = None,
    *,
    packet_id: str = "glio-noncode-module-inventory-packet",
) -> ModuleInventoryPacket:
    """Build a fixed ten-artifact packet from one inventory snapshot."""

    selected = inventory or build_module_inventory()
    selected_runtime = runtime or run_module_inventory(inventory=selected)
    artifacts = _artifact_specs(selected, selected_runtime)
    checks = (
        _check(
            "artifact-count",
            ModuleInventoryPacketCheckPlane.MANIFEST,
            len(artifacts) == MODULE_INVENTORY_PACKET_ARTIFACT_COUNT,
            len(artifacts),
            MODULE_INVENTORY_PACKET_ARTIFACT_COUNT,
            "packet has the fixed artifact count",
        ),
        _check(
            "artifact-identities",
            ModuleInventoryPacketCheckPlane.MANIFEST,
            len({item.artifact_id for item in artifacts}) == len(artifacts),
            len({item.artifact_id for item in artifacts}),
            len(artifacts),
            "artifact identifiers are unique",
        ),
        _check(
            "artifact-paths",
            ModuleInventoryPacketCheckPlane.PATH,
            all(_safe_path(item.relative_path) for item in artifacts),
            "safe",
            "safe",
            "artifact paths are relative and safe",
        ),
        _check(
            "inventory-link",
            ModuleInventoryPacketCheckPlane.MANIFEST,
            selected_runtime.inventory_address == selected.content_address,
            selected_runtime.inventory_address,
            selected.content_address,
            "runtime points to the packaged inventory",
        ),
        _check(
            "payload-addresses",
            ModuleInventoryPacketCheckPlane.BYTES,
            all(
                item.payload is not None
                and hash_bytes(
                    item.payload.encode("utf-8"), prefix=MODULE_INVENTORY_PACKET_ARTIFACT_PREFIX
                )
                == item.content_address
                for item in artifacts
            ),
            "verified",
            "verified",
            "artifact addresses match exact UTF-8 bytes",
        ),
        _check(
            "public-boundary",
            ModuleInventoryPacketCheckPlane.PUBLIC,
            not _has_forbidden_key(
                {"artifacts": [item.to_dict(include_payload=True) for item in artifacts]}
            ),
            "clean",
            "clean",
            "packet artifact projection has no forbidden keys",
        ),
    )
    accepted = selected.accepted and all(item.passed for item in checks)
    state = ModuleInventoryPacketState.ACCEPTED if accepted else ModuleInventoryPacketState.BLOCKED
    address = _packet_address(
        packet_id,
        selected.content_address,
        selected_runtime.content_address,
        state,
        artifacts,
        checks,
    )
    return ModuleInventoryPacket(
        packet_id=packet_id,
        version=MODULE_INVENTORY_PACKET_VERSION,
        boundary=MODULE_INVENTORY_PACKET_BOUNDARY,
        inventory_address=selected.content_address,
        runtime_address=selected_runtime.content_address,
        state=state,
        accepted=accepted,
        artifacts=artifacts,
        checks=checks,
        content_address=address,
    )


def _manifest_text(packet: ModuleInventoryPacket) -> str:
    return _json_text(packet.to_dict(include_payloads=False))


def write_module_inventory_packet(
    packet: ModuleInventoryPacket,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> ModuleInventoryPacket:
    """Write all packet files atomically into a dedicated directory."""

    root = Path(destination)
    if root.exists() and not allow_existing:
        raise ValidationError("module inventory packet destination already exists")
    if root.exists() and not root.is_dir():
        raise ValidationError("module inventory packet destination is not a directory")
    root.mkdir(parents=True, exist_ok=True)
    _atomic_write(root / MODULE_INVENTORY_PACKET_MANIFEST, _manifest_text(packet).encode("utf-8"))
    for artifact in packet.artifacts:
        path = root.joinpath(*artifact.relative_path.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        if artifact.payload is None:
            raise ValidationError(f"packet artifact has no payload: {artifact.artifact_id}")
        _atomic_write(path, artifact.payload.encode("utf-8"))
    return packet


def _manifest_mapping(directory: str | Path) -> tuple[Path, Mapping[str, Any]]:
    root = Path(directory)
    try:
        raw = json.loads((root / MODULE_INVENTORY_PACKET_MANIFEST).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"cannot load module inventory packet manifest: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise ValidationError("module inventory packet manifest must be an object")
    return root, raw


def verify_module_inventory_packet(directory: str | Path) -> ModuleInventoryPacketVerification:
    """Verify paths, bytes, identities, and the public boundary."""

    root, manifest = _manifest_mapping(directory)
    packet_id = str(manifest.get("packet_id", "unknown"))
    checks: list[ModuleInventoryPacketCheck] = []
    raw_artifacts = manifest.get("artifacts", ())
    artifacts = (
        tuple(item for item in raw_artifacts if isinstance(item, Mapping))
        if isinstance(raw_artifacts, list)
        else ()
    )
    checks.append(
        _check(
            "manifest-shape",
            ModuleInventoryPacketCheckPlane.MANIFEST,
            isinstance(raw_artifacts, list),
            type(raw_artifacts).__name__,
            "array",
            "manifest artifact collection is an array",
        )
    )
    paths = tuple(str(item.get("relative_path", "")) for item in artifacts)
    checks.append(
        _check(
            "safe-paths",
            ModuleInventoryPacketCheckPlane.PATH,
            all(_safe_path(item) for item in paths),
            "safe",
            "safe",
            "manifest paths are safe",
        )
    )
    checks.append(
        _check(
            "artifact-count",
            ModuleInventoryPacketCheckPlane.MANIFEST,
            len(artifacts) == MODULE_INVENTORY_PACKET_ARTIFACT_COUNT,
            len(artifacts),
            MODULE_INVENTORY_PACKET_ARTIFACT_COUNT,
            "manifest has the fixed artifact count",
        )
    )
    checks.append(
        _check(
            "unique-paths",
            ModuleInventoryPacketCheckPlane.PATH,
            len(set(paths)) == len(paths),
            len(set(paths)),
            len(paths),
            "manifest paths are unique",
        )
    )
    expected_paths = set(paths) | {MODULE_INVENTORY_PACKET_MANIFEST}
    actual_paths = set()
    if root.exists() and root.is_dir():
        for path in root.rglob("*"):
            if path.is_file() and not path.is_symlink():
                actual_paths.add(path.relative_to(root).as_posix())
    checks.append(
        _check(
            "no-unexpected-files",
            ModuleInventoryPacketCheckPlane.PATH,
            actual_paths == expected_paths,
            sorted(actual_paths - expected_paths),
            sorted(expected_paths),
            "packet contains exactly the declared files",
        )
    )
    byte_failures: list[str] = []
    for item in artifacts:
        relative = str(item.get("relative_path", ""))
        if not _safe_path(relative):
            continue
        path = root.joinpath(*relative.split("/"))
        try:
            payload = path.read_bytes()
            actual_address = hash_bytes(payload, prefix=MODULE_INVENTORY_PACKET_ARTIFACT_PREFIX)
            if actual_address != item.get("content_address") or len(payload) != int(
                item.get("byte_count", -1)
            ):
                byte_failures.append(relative)
        except (OSError, ValueError):
            byte_failures.append(relative)
    checks.append(
        _check(
            "exact-bytes",
            ModuleInventoryPacketCheckPlane.BYTES,
            not byte_failures,
            byte_failures,
            [],
            "declared byte counts and addresses match files",
        )
    )
    checks.append(
        _check(
            "public-boundary",
            ModuleInventoryPacketCheckPlane.PUBLIC,
            not _has_forbidden_key(manifest),
            "clean",
            "clean",
            "manifest contains no forbidden public keys",
        )
    )
    accepted = all(item.passed for item in checks) and bool(manifest.get("accepted", False))
    from .serialization import content_hash

    body = {"packet_id": packet_id, "checks": tuple(checks), "accepted": accepted}
    return ModuleInventoryPacketVerification(
        packet_id=packet_id,
        checks=tuple(checks),
        accepted=accepted,
        content_address=content_hash(body, prefix="module-inventory-packet-verification"),
    )


def load_module_inventory_packet(
    directory: str | Path, *, include_payloads: bool = True
) -> ModuleInventoryPacket:
    """Load a verified packet and expose artifact bytes when requested."""

    verification = verify_module_inventory_packet(directory)
    if not verification.accepted:
        raise ValidationError("module inventory packet verification failed")
    root, manifest = _manifest_mapping(directory)
    artifacts: list[ModuleInventoryPacketArtifact] = []
    for raw in manifest.get("artifacts", ()):
        if not isinstance(raw, Mapping):
            raise ValidationError("packet artifacts must be objects")
        relative = str(raw.get("relative_path", ""))
        payload = None
        if include_payloads:
            payload = root.joinpath(*relative.split("/")).read_text(encoding="utf-8")
        artifacts.append(
            ModuleInventoryPacketArtifact(
                artifact_id=str(raw.get("artifact_id", "")),
                relative_path=relative,
                media_type=str(raw.get("media_type", "")),
                kind=ModuleInventoryPacketArtifactKind(str(raw.get("kind", "summary"))),
                byte_count=int(raw.get("byte_count", 0)),
                line_count=int(raw.get("line_count", 0)),
                content_address=str(raw.get("content_address", "")),
                payload=payload,
            )
        )
    raw_checks = manifest.get("checks", ())
    checks = tuple(
        _check(
            str(item.get("check_id", "manifest")),
            ModuleInventoryPacketCheckPlane(str(item.get("plane", "manifest"))),
            bool(item.get("passed", False)),
            item.get("observed"),
            item.get("required"),
            str(item.get("detail", "")),
        )
        for item in raw_checks
        if isinstance(item, Mapping)
    )
    return ModuleInventoryPacket(
        packet_id=str(manifest.get("packet_id", "")),
        version=str(manifest.get("version", "")),
        boundary=str(manifest.get("boundary", "")),
        inventory_address=str(manifest.get("inventory_address", "")),
        runtime_address=str(manifest.get("runtime_address", "")),
        state=ModuleInventoryPacketState(str(manifest.get("state", "blocked"))),
        accepted=bool(manifest.get("accepted", False)),
        artifacts=tuple(artifacts),
        checks=checks,
        content_address=str(manifest.get("content_address", "")),
    )


def module_inventory_packet_json(
    packet: ModuleInventoryPacket, *, include_payloads: bool = False
) -> str:
    return _json_text(packet.to_dict(include_payloads=include_payloads))


def module_inventory_packet_schema() -> dict[str, Any]:
    return {
        "version": MODULE_INVENTORY_PACKET_VERSION,
        "boundary": MODULE_INVENTORY_PACKET_BOUNDARY,
        "manifest": MODULE_INVENTORY_PACKET_MANIFEST,
        "artifact_count": MODULE_INVENTORY_PACKET_ARTIFACT_COUNT,
        "artifact_fields": [
            "artifact_id",
            "relative_path",
            "media_type",
            "kind",
            "byte_count",
            "line_count",
            "content_address",
        ],
        "verification_planes": [item.value for item in ModuleInventoryPacketCheckPlane],
        "safe_path_rule": (
            "relative POSIX paths with no empty, dot, parent, or backslash components"
        ),
        "write_rule": (
            "UTF-8 bytes are atomically replaced and exact addresses are verified before load"
        ),
    }


def module_inventory_packet_capabilities() -> dict[str, Any]:
    operations = (
        "build_packet",
        "write_packet",
        "verify_packet",
        "load_packet",
        "inspect_exact_bytes",
        "reject_unexpected_files",
        "export_offline_inventory",
    )
    return {
        "version": MODULE_INVENTORY_PACKET_VERSION,
        "boundary": MODULE_INVENTORY_PACKET_BOUNDARY,
        "operation_count": len(operations),
        "operations": list(operations),
        "artifact_count": MODULE_INVENTORY_PACKET_ARTIFACT_COUNT,
        "read_only_after_write": True,
    }


__all__ = [
    "build_module_inventory_packet",
    "load_module_inventory_packet",
    "module_inventory_packet_capabilities",
    "module_inventory_packet_json",
    "module_inventory_packet_schema",
    "verify_module_inventory_packet",
    "write_module_inventory_packet",
]
