"""Build, materialize, verify, and load exact-byte module-impact packets."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from .errors import ValidationError
from .module_impact import _as_inventory, build_module_impact_diff, build_module_impact_report
from .module_impact_audit import audit_module_impact
from .module_impact_contracts import ModuleImpactPolicy
from .module_impact_exports import (
    module_impact_diff_json,
    module_impact_gate_json,
    module_impact_report_json,
    render_module_impact_markdown,
)
from .module_impact_observability import (
    build_module_impact_observability,
    module_impact_observability_json,
)
from .module_impact_packet_contracts import (
    MODULE_IMPACT_PACKET_ARTIFACT_COUNT,
    MODULE_IMPACT_PACKET_ARTIFACT_PREFIX,
    MODULE_IMPACT_PACKET_BOUNDARY,
    MODULE_IMPACT_PACKET_MANIFEST,
    MODULE_IMPACT_PACKET_VERSION,
    ModuleImpactPacket,
    ModuleImpactPacketArtifact,
    ModuleImpactPacketArtifactKind,
    ModuleImpactPacketCheck,
    ModuleImpactPacketCheckPlane,
    ModuleImpactPacketState,
    ModuleImpactPacketVerification,
)
from .module_impact_policy import default_module_impact_policy, evaluate_module_impact_gate
from .module_impact_runtime import run_module_impact
from .module_impact_verification import build_module_impact_verification_plan
from .module_inventory_exports import module_inventory_json
from .run_workspace import _has_forbidden_key
from .serialization import canonical_json, content_hash, hash_bytes, jsonable

_JSON = "application/json"
_CSV = "text/csv"
_MARKDOWN = "text/markdown"


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
        raise ValidationError("module impact packet crosses the public boundary")
    return canonical_json(projected) + "\n"


def _artifact(
    artifact_id: str,
    relative_path: str,
    kind: ModuleImpactPacketArtifactKind,
    media_type: str,
    text: str,
) -> ModuleImpactPacketArtifact:
    if not _safe_path(relative_path):
        raise ValidationError(f"unsafe module impact packet path: {relative_path}")
    encoded = text.encode("utf-8")
    return ModuleImpactPacketArtifact(
        artifact_id=artifact_id,
        relative_path=relative_path,
        media_type=media_type,
        kind=kind,
        byte_count=len(encoded),
        line_count=len(text.splitlines()),
        content_address=hash_bytes(encoded, prefix=MODULE_IMPACT_PACKET_ARTIFACT_PREFIX),
        payload=text,
    )


def _check(
    check_id: str,
    plane: ModuleImpactPacketCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleImpactPacketCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ModuleImpactPacketCheck(
        **body, content_address=content_hash(body, prefix="module-impact-packet-check")
    )


def _packet_address(
    packet_id: str,
    left_address: str,
    right_address: str,
    diff_address: str,
    impact_address: str,
    gate_address: str,
    runtime_address: str,
    state: ModuleImpactPacketState,
    artifacts: tuple[ModuleImpactPacketArtifact, ...],
    checks: tuple[ModuleImpactPacketCheck, ...],
) -> str:
    body = {
        "packet_id": packet_id,
        "version": MODULE_IMPACT_PACKET_VERSION,
        "boundary": MODULE_IMPACT_PACKET_BOUNDARY,
        "left_inventory_address": left_address,
        "right_inventory_address": right_address,
        "diff_address": diff_address,
        "impact_address": impact_address,
        "gate_address": gate_address,
        "runtime_address": runtime_address,
        "state": state,
        "accepted": all(item.passed for item in checks),
        "artifacts": tuple(item.to_dict(include_payload=False) for item in artifacts),
        "checks": checks,
    }
    return content_hash(body, prefix="module-impact-packet")


def _artifact_specs(
    left: Any,
    right: Any,
    diff: Any,
    report: Any,
    plan: Any,
    gate: Any,
    runtime: Any,
    audit: Any,
    observability: Any,
) -> tuple[ModuleImpactPacketArtifact, ...]:
    return (
        _artifact(
            "left-inventory",
            "left-inventory.json",
            ModuleImpactPacketArtifactKind.LEFT_INVENTORY,
            _JSON,
            module_inventory_json(left),
        ),
        _artifact(
            "right-inventory",
            "right-inventory.json",
            ModuleImpactPacketArtifactKind.RIGHT_INVENTORY,
            _JSON,
            module_inventory_json(right),
        ),
        _artifact(
            "diff",
            "diff.json",
            ModuleImpactPacketArtifactKind.DIFF,
            _JSON,
            module_impact_diff_json(diff),
        ),
        _artifact(
            "impacts",
            "impacts.json",
            ModuleImpactPacketArtifactKind.IMPACTS,
            _JSON,
            module_impact_report_json(report),
        ),
        _artifact(
            "verification",
            "verification.json",
            ModuleImpactPacketArtifactKind.VERIFICATION,
            _JSON,
            _json_text(plan),
        ),
        _artifact(
            "gate",
            "gate.json",
            ModuleImpactPacketArtifactKind.GATE,
            _JSON,
            module_impact_gate_json(gate),
        ),
        _artifact(
            "audit", "audit.json", ModuleImpactPacketArtifactKind.AUDIT, _JSON, _json_text(audit)
        ),
        _artifact(
            "runtime",
            "runtime.json",
            ModuleImpactPacketArtifactKind.RUNTIME,
            _JSON,
            _json_text(runtime),
        ),
        _artifact(
            "observability",
            "observability.json",
            ModuleImpactPacketArtifactKind.OBSERVABILITY,
            _JSON,
            module_impact_observability_json(observability),
        ),
        _artifact(
            "summary",
            "summary.md",
            ModuleImpactPacketArtifactKind.SUMMARY,
            _MARKDOWN,
            render_module_impact_markdown(diff, report, plan, gate),
        ),
    )


def build_module_impact_packet(
    left: Any,
    right: Any,
    *,
    packet_id: str = "glio-noncode-module-impact-packet",
    policy: ModuleImpactPolicy | None = None,
) -> ModuleImpactPacket:
    """Build a ten-artifact packet from two typed inventories."""

    old = _as_inventory(left)
    new = _as_inventory(right)
    diff = build_module_impact_diff(old, new)
    report = build_module_impact_report(old, new, diff)
    plan = build_module_impact_verification_plan(diff, report)
    gate = evaluate_module_impact_gate(diff, report, plan, policy or default_module_impact_policy())
    runtime = run_module_impact(old, new, policy=gate.policy)
    audit = audit_module_impact(diff, report, plan, gate)
    observability = build_module_impact_observability(diff, report, plan, gate)
    checks = (
        _check(
            "artifact-count",
            ModuleImpactPacketCheckPlane.MANIFEST,
            True,
            MODULE_IMPACT_PACKET_ARTIFACT_COUNT,
            MODULE_IMPACT_PACKET_ARTIFACT_COUNT,
            "packet artifact count is fixed",
        ),
        _check(
            "input-addresses",
            ModuleImpactPacketCheckPlane.MANIFEST,
            old.content_address != new.content_address or diff.changed_summary_fields == (),
            (old.content_address, new.content_address),
            "two inventory addresses",
            "packet records both inventory inputs",
        ),
        _check(
            "closure-addresses",
            ModuleImpactPacketCheckPlane.MANIFEST,
            report.diff_address == diff.content_address
            and gate.diff_address == diff.content_address
            and runtime.diff_address == diff.content_address,
            True,
            True,
            "all closure artifacts reference the same diff",
        ),
        _check(
            "public-boundary",
            ModuleImpactPacketCheckPlane.PUBLIC,
            not _has_forbidden_key(
                {
                    "diff": diff.to_dict(include_rows=False),
                    "report": report.to_dict(include_rows=False),
                    "plan": plan.to_dict(include_rows=False),
                    "gate": gate.to_dict(),
                    "audit": audit.to_dict(),
                    "observability": observability.to_dict(),
                }
            ),
            True,
            True,
            "packet closure contains only public aggregate fields",
        ),
    )
    artifacts = _artifact_specs(old, new, diff, report, plan, gate, runtime, audit, observability)
    accepted = all(item.passed for item in checks) and audit.accepted
    state = ModuleImpactPacketState.ACCEPTED if accepted else ModuleImpactPacketState.BLOCKED
    address = _packet_address(
        packet_id,
        old.content_address,
        new.content_address,
        diff.content_address,
        report.content_address,
        gate.content_address,
        runtime.content_address,
        state,
        artifacts,
        checks,
    )
    return ModuleImpactPacket(
        packet_id=packet_id,
        version=MODULE_IMPACT_PACKET_VERSION,
        boundary=MODULE_IMPACT_PACKET_BOUNDARY,
        left_inventory_address=old.content_address,
        right_inventory_address=new.content_address,
        diff_address=diff.content_address,
        impact_address=report.content_address,
        gate_address=gate.content_address,
        runtime_address=runtime.content_address,
        state=state,
        accepted=accepted,
        artifacts=artifacts,
        checks=checks,
        content_address=address,
    )


def module_impact_packet_json(packet: ModuleImpactPacket) -> str:
    return canonical_json(packet.to_dict()) + "\n"


def write_module_impact_packet(
    packet: ModuleImpactPacket,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> Path:
    """Materialize a packet atomically; existing destinations are protected."""

    if not isinstance(packet, ModuleImpactPacket):
        raise ValidationError("packet writing requires a typed packet")
    target = Path(destination)
    if target.exists():
        if not allow_existing:
            raise ValidationError("module impact packet destination already exists")
        if not target.is_dir():
            raise ValidationError("module impact packet destination must be a directory")
    else:
        target.mkdir(parents=True, exist_ok=False)
    for artifact in packet.artifacts:
        _atomic_write(
            target / artifact.relative_path,
            artifact.payload.encode("utf-8") if artifact.payload is not None else b"",
        )
    manifest = {
        "packet_id": packet.packet_id,
        "version": packet.version,
        "boundary": packet.boundary,
        "left_inventory_address": packet.left_inventory_address,
        "right_inventory_address": packet.right_inventory_address,
        "diff_address": packet.diff_address,
        "impact_address": packet.impact_address,
        "gate_address": packet.gate_address,
        "runtime_address": packet.runtime_address,
        "state": packet.state,
        "accepted": packet.accepted,
        "packet_address": packet.content_address,
        "artifacts": [item.to_dict(include_payload=False) for item in packet.artifacts],
        "checks": [item.to_dict() for item in packet.checks],
    }
    _atomic_write(target / MODULE_IMPACT_PACKET_MANIFEST, (_json_text(manifest)).encode("utf-8"))
    return target


def _verification_check(
    check_id: str,
    plane: ModuleImpactPacketCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleImpactPacketCheck:
    return _check(check_id, plane, passed, observed, required, detail)


def verify_module_impact_packet(directory: str | Path) -> ModuleImpactPacketVerification:
    """Verify file names, exact bytes, manifest identities, and public shape."""

    target = Path(directory)
    manifest_path = target / MODULE_IMPACT_PACKET_MANIFEST
    if not target.exists() or not target.is_dir() or not manifest_path.is_file():
        raise ValidationError("module impact packet directory or manifest is missing")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("module impact packet manifest is unreadable") from exc
    packet_id = str(manifest.get("packet_id", "unknown"))
    raw_artifacts = manifest.get("artifacts", ())
    artifact_rows = [item for item in raw_artifacts if isinstance(item, Mapping)]
    checks: list[ModuleImpactPacketCheck] = []
    actual_files = []
    symlinks = []
    for path in target.rglob("*"):
        if path.is_symlink():
            symlinks.append(path.relative_to(target).as_posix())
        elif path.is_file():
            actual_files.append(path.relative_to(target).as_posix())
    expected_files = {MODULE_IMPACT_PACKET_MANIFEST} | {
        str(item.get("relative_path", "")) for item in artifact_rows
    }
    checks.append(
        _verification_check(
            "path-set",
            ModuleImpactPacketCheckPlane.PATH,
            not symlinks and set(actual_files) == expected_files,
            sorted(actual_files),
            sorted(expected_files),
            "packet contains exactly the manifest and declared artifacts",
        )
    )
    checks.append(
        _verification_check(
            "safe-paths",
            ModuleImpactPacketCheckPlane.PATH,
            all(_safe_path(str(item.get("relative_path", ""))) for item in artifact_rows),
            True,
            True,
            "artifact paths are relative and traversal-free",
        )
    )
    exact = True
    public = True
    observed_addresses: list[str] = []
    for row in artifact_rows:
        relative = str(row.get("relative_path", ""))
        path = target / relative
        try:
            data = path.read_bytes()
            text = data.decode("utf-8")
            expected_address = str(row.get("content_address", ""))
            actual_address = hash_bytes(data, prefix=MODULE_IMPACT_PACKET_ARTIFACT_PREFIX)
            observed_addresses.append(actual_address)
            row_ok = (
                actual_address == expected_address
                and len(data) == int(row.get("byte_count", -1))
                and len(text.splitlines()) == int(row.get("line_count", -1))
            )
            exact = exact and row_ok
            if row.get("media_type") == _JSON:
                public = public and not _has_forbidden_key(json.loads(text))
        except (OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
            exact = False
            public = False
    checks.append(
        _verification_check(
            "exact-bytes",
            ModuleImpactPacketCheckPlane.BYTES,
            exact,
            observed_addresses,
            [item.get("content_address") for item in artifact_rows],
            "artifact bytes match manifest addresses and counts",
        )
    )
    checks.append(
        _verification_check(
            "manifest-version",
            ModuleImpactPacketCheckPlane.MANIFEST,
            manifest.get("version") == MODULE_IMPACT_PACKET_VERSION
            and manifest.get("boundary") == MODULE_IMPACT_PACKET_BOUNDARY,
            {"version": manifest.get("version"), "boundary": manifest.get("boundary")},
            {"version": MODULE_IMPACT_PACKET_VERSION, "boundary": MODULE_IMPACT_PACKET_BOUNDARY},
            "manifest version and public boundary are supported",
        )
    )
    checks.append(
        _verification_check(
            "artifact-count",
            ModuleImpactPacketCheckPlane.MANIFEST,
            len(artifact_rows) == MODULE_IMPACT_PACKET_ARTIFACT_COUNT,
            len(artifact_rows),
            MODULE_IMPACT_PACKET_ARTIFACT_COUNT,
            "manifest declares the fixed artifact count",
        )
    )
    checks.append(
        _verification_check(
            "public-boundary",
            ModuleImpactPacketCheckPlane.PUBLIC,
            public and not _has_forbidden_key(manifest),
            public,
            True,
            "manifest and JSON artifacts contain no forbidden public keys",
        )
    )
    accepted = all(item.passed for item in checks)
    body = {"packet_id": packet_id, "checks": tuple(checks), "accepted": accepted}
    return ModuleImpactPacketVerification(
        **body, content_address=content_hash(body, prefix="module-impact-packet-verification")
    )


def load_module_impact_packet(directory: str | Path) -> ModuleImpactPacket:
    """Load a packet only after independent exact-byte verification."""

    verification = verify_module_impact_packet(directory)
    if not verification.accepted:
        raise ValidationError("module impact packet verification failed")
    target = Path(directory)
    manifest = json.loads((target / MODULE_IMPACT_PACKET_MANIFEST).read_text(encoding="utf-8"))
    artifacts = tuple(
        ModuleImpactPacketArtifact(
            **{
                key: row[key]
                for key in (
                    "artifact_id",
                    "relative_path",
                    "media_type",
                    "byte_count",
                    "line_count",
                    "content_address",
                )
            },
            kind=ModuleImpactPacketArtifactKind(str(row["kind"])),
            payload=(target / str(row["relative_path"])).read_text(encoding="utf-8"),
        )
        for row in manifest["artifacts"]
    )
    checks = tuple(
        ModuleImpactPacketCheck(
            **{
                key: row[key]
                for key in (
                    "check_id",
                    "passed",
                    "observed",
                    "required",
                    "detail",
                    "content_address",
                )
            },
            plane=ModuleImpactPacketCheckPlane(str(row["plane"])),
        )
        for row in manifest["checks"]
    )
    return ModuleImpactPacket(
        packet_id=str(manifest["packet_id"]),
        version=str(manifest["version"]),
        boundary=str(manifest["boundary"]),
        left_inventory_address=str(manifest["left_inventory_address"]),
        right_inventory_address=str(manifest["right_inventory_address"]),
        diff_address=str(manifest["diff_address"]),
        impact_address=str(manifest["impact_address"]),
        gate_address=str(manifest["gate_address"]),
        runtime_address=str(manifest["runtime_address"]),
        state=ModuleImpactPacketState(str(manifest["state"])),
        accepted=bool(manifest["accepted"]),
        artifacts=artifacts,
        checks=checks,
        content_address=str(manifest["packet_address"]),
    )


def module_impact_packet_schema() -> dict[str, Any]:
    return {
        "version": MODULE_IMPACT_PACKET_VERSION,
        "boundary": MODULE_IMPACT_PACKET_BOUNDARY,
        "artifact_count": MODULE_IMPACT_PACKET_ARTIFACT_COUNT,
        "required_files": [
            MODULE_IMPACT_PACKET_MANIFEST,
            "left-inventory.json",
            "right-inventory.json",
            "diff.json",
            "impacts.json",
            "verification.json",
            "gate.json",
            "audit.json",
            "runtime.json",
            "observability.json",
            "summary.md",
        ],
        "verification": [
            "exact_bytes",
            "safe_paths",
            "manifest_identity",
            "public_boundary",
            "tamper_detection",
        ],
        "offline": True,
        "read_only_verification": True,
    }


def module_impact_packet_capabilities() -> dict[str, Any]:
    operations = (
        "build_packet",
        "write_packet_atomically",
        "verify_exact_bytes",
        "load_verified_packet",
        "reject_symlinks",
        "detect_tampering",
        "export_diff",
        "export_impacts",
        "export_verification",
        "export_gate",
        "export_observability",
    )
    return {
        "version": MODULE_IMPACT_PACKET_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "artifact_count": MODULE_IMPACT_PACKET_ARTIFACT_COUNT,
        "exact_byte_artifacts": True,
        "independent_verification": True,
        "read_only_without_destination": True,
        "timestamp_free": True,
    }


__all__ = [
    "build_module_impact_packet",
    "load_module_impact_packet",
    "module_impact_packet_capabilities",
    "module_impact_packet_json",
    "module_impact_packet_schema",
    "verify_module_impact_packet",
    "write_module_impact_packet",
]
