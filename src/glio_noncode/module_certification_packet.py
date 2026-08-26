"""Build, write, verify, and load exact-byte certification packets."""

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
from .module_certification import module_certification_json
from .module_certification_audit import audit_module_certification
from .module_certification_contracts import (
    ModuleCertificationGate,
    ModuleCertificationMatrix,
    ModuleCertificationRuntime,
    ModuleCertificationTaskPlan,
)
from .module_certification_observability import (
    build_module_certification_observability,
    module_certification_observability_json,
)
from .module_certification_packet_contracts import (
    MODULE_CERTIFICATION_PACKET_ARTIFACT_COUNT,
    MODULE_CERTIFICATION_PACKET_ARTIFACT_PREFIX,
    MODULE_CERTIFICATION_PACKET_BOUNDARY,
    MODULE_CERTIFICATION_PACKET_MANIFEST,
    MODULE_CERTIFICATION_PACKET_VERSION,
    ModuleCertificationPacket,
    ModuleCertificationPacketArtifact,
    ModuleCertificationPacketArtifactKind,
    ModuleCertificationPacketCheck,
    ModuleCertificationPacketCheckPlane,
    ModuleCertificationPacketState,
    ModuleCertificationPacketVerification,
)
from .module_certification_policy import evaluate_module_certification_gate
from .module_certification_runtime import run_module_certification
from .module_certification_tasks import (
    build_module_certification_task_plan,
    module_certification_gaps_csv,
    module_certification_tasks_csv,
    module_certification_tasks_json,
)
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
    path.parent.mkdir(parents=True, exist_ok=True)
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
        raise ValidationError("certification packet crosses the public boundary")
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
    kind: ModuleCertificationPacketArtifactKind,
    media_type: str,
    text: str,
) -> ModuleCertificationPacketArtifact:
    if not _safe_path(relative_path):
        raise ValidationError(f"unsafe certification packet path: {relative_path}")
    encoded = text.encode("utf-8")
    return ModuleCertificationPacketArtifact(
        artifact_id=artifact_id,
        relative_path=relative_path,
        media_type=media_type,
        kind=kind,
        byte_count=len(encoded),
        line_count=len(text.splitlines()),
        content_address=hash_bytes(encoded, prefix=MODULE_CERTIFICATION_PACKET_ARTIFACT_PREFIX),
        payload=text,
    )


def _check(
    check_id: str,
    plane: ModuleCertificationPacketCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleCertificationPacketCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    from .serialization import content_hash

    return ModuleCertificationPacketCheck(
        **body, content_address=content_hash(body, prefix="module-certification-packet-check")
    )


def _packet_address(
    packet_id: str,
    matrix_address: str,
    gate_address: str,
    runtime_address: str,
    state: ModuleCertificationPacketState,
    artifacts: tuple[ModuleCertificationPacketArtifact, ...],
    checks: tuple[ModuleCertificationPacketCheck, ...],
) -> str:
    from .serialization import content_hash

    body = {
        "packet_id": packet_id,
        "version": MODULE_CERTIFICATION_PACKET_VERSION,
        "boundary": MODULE_CERTIFICATION_PACKET_BOUNDARY,
        "matrix_address": matrix_address,
        "gate_address": gate_address,
        "runtime_address": runtime_address,
        "state": state,
        "accepted": all(item.passed for item in checks),
        "artifacts": tuple(item.to_dict(include_payload=False) for item in artifacts),
        "checks": checks,
    }
    return content_hash(body, prefix="module-certification-packet")


def _artifact_specs(
    matrix: ModuleCertificationMatrix,
    plan: ModuleCertificationTaskPlan,
    gate: ModuleCertificationGate,
    audit: Any,
    runtime: ModuleCertificationRuntime,
    observability: Any,
) -> tuple[ModuleCertificationPacketArtifact, ...]:
    checks = [
        {
            "module_id": row.module_id,
            "kind": check.kind.value,
            "state": check.state.value,
            "observed": check.observed,
            "required": check.required,
            "detail": check.detail,
            "content_address": check.content_address,
        }
        for row in matrix.rows
        for check in row.checks
    ]
    summary = {
        "version": MODULE_CERTIFICATION_PACKET_VERSION,
        "matrix_address": matrix.content_address,
        "gate_address": gate.content_address,
        "runtime_address": runtime.content_address,
        "module_count": matrix.module_count,
        "check_count": matrix.module_count * matrix.check_kind_count,
        "gap_count": matrix.gap_count,
        "task_count": plan.task_count,
        "certified_count": matrix.certified_count,
        "review_count": matrix.review_count,
        "blocked_count": matrix.blocked_count,
        "overall_percent": matrix.overall_percent,
        "accepted": matrix.accepted and plan.accepted and gate.accepted and audit.accepted,
    }
    return (
        _artifact(
            "matrix",
            "matrix.json",
            ModuleCertificationPacketArtifactKind.MATRIX,
            _JSON,
            module_certification_json(matrix),
        ),
        _artifact(
            "checks",
            "checks.csv",
            ModuleCertificationPacketArtifactKind.CHECKS,
            _CSV,
            _csv_text(
                checks,
                ("module_id", "kind", "state", "observed", "required", "detail", "content_address"),
            ),
        ),
        _artifact(
            "gaps",
            "gaps.csv",
            ModuleCertificationPacketArtifactKind.GAPS,
            _CSV,
            module_certification_gaps_csv(matrix),
        ),
        _artifact(
            "tasks",
            "tasks.json",
            ModuleCertificationPacketArtifactKind.TASKS,
            _JSON,
            module_certification_tasks_json(plan),
        ),
        _artifact(
            "tasks-table",
            "tasks.csv",
            ModuleCertificationPacketArtifactKind.TASKS_TABLE,
            _CSV,
            module_certification_tasks_csv(plan),
        ),
        _artifact(
            "gate", "gate.json", ModuleCertificationPacketArtifactKind.GATE, _JSON, _json_text(gate)
        ),
        _artifact(
            "audit",
            "audit.json",
            ModuleCertificationPacketArtifactKind.AUDIT,
            _JSON,
            _json_text(audit),
        ),
        _artifact(
            "runtime",
            "runtime.json",
            ModuleCertificationPacketArtifactKind.RUNTIME,
            _JSON,
            _json_text(runtime),
        ),
        _artifact(
            "observability",
            "observability.json",
            ModuleCertificationPacketArtifactKind.OBSERVABILITY,
            _JSON,
            module_certification_observability_json(observability),
        ),
        _artifact(
            "summary",
            "summary.json",
            ModuleCertificationPacketArtifactKind.SUMMARY,
            _JSON,
            _json_text(summary),
        ),
    )


def build_module_certification_packet(
    matrix: ModuleCertificationMatrix | None = None,
    plan: ModuleCertificationTaskPlan | None = None,
    gate: ModuleCertificationGate | None = None,
    runtime: ModuleCertificationRuntime | None = None,
    audit: Any | None = None,
    observability: Any | None = None,
    *,
    source_root: str | Path | None = None,
    test_root: str | Path | None = None,
    docs_root: str | Path | None = None,
    packet_id: str = "glio-noncode-module-certification-packet",
) -> ModuleCertificationPacket:
    """Build a fixed ten-artifact packet from one typed certification closure."""

    if matrix is None:
        runtime = runtime or run_module_certification(
            source_root,
            test_root=test_root,
            docs_root=docs_root,
        )
        from .module_certification import build_module_certification
        from .module_inventory import build_module_inventory

        inventory = build_module_inventory(source_root, test_root=test_root)
        matrix = build_module_certification(
            inventory, source_root=source_root, test_root=test_root, docs_root=docs_root
        )
    if not isinstance(matrix, ModuleCertificationMatrix):
        raise ValidationError("certification packet requires a typed matrix")
    plan = plan or build_module_certification_task_plan(matrix)
    gate = gate or evaluate_module_certification_gate(matrix, plan)
    runtime = runtime or run_module_certification(
        source_root,
        test_root=test_root,
        docs_root=docs_root,
        policy=gate.policy,
        runtime_id=f"{packet_id}-runtime",
    )
    if runtime.matrix_address != matrix.content_address:
        raise ValidationError("certification packet runtime does not reference the matrix")
    audit = audit or audit_module_certification(matrix, plan, gate, runtime)
    observability = observability or build_module_certification_observability(
        matrix, plan, gate, runtime
    )
    artifacts = _artifact_specs(matrix, plan, gate, audit, runtime, observability)
    checks = (
        _check(
            "artifact-count",
            ModuleCertificationPacketCheckPlane.MANIFEST,
            len(artifacts) == MODULE_CERTIFICATION_PACKET_ARTIFACT_COUNT,
            len(artifacts),
            MODULE_CERTIFICATION_PACKET_ARTIFACT_COUNT,
            "packet has the fixed artifact count",
        ),
        _check(
            "artifact-identities",
            ModuleCertificationPacketCheckPlane.MANIFEST,
            len({item.artifact_id for item in artifacts}) == len(artifacts),
            len({item.artifact_id for item in artifacts}),
            len(artifacts),
            "artifact identifiers are unique",
        ),
        _check(
            "artifact-paths",
            ModuleCertificationPacketCheckPlane.PATH,
            all(_safe_path(item.relative_path) for item in artifacts),
            "safe",
            "safe",
            "artifact paths are relative and safe",
        ),
        _check(
            "matrix-link",
            ModuleCertificationPacketCheckPlane.LINK,
            runtime.matrix_address == matrix.content_address,
            runtime.matrix_address,
            matrix.content_address,
            "runtime points to the packaged matrix",
        ),
        _check(
            "gate-link",
            ModuleCertificationPacketCheckPlane.LINK,
            gate.matrix_address == matrix.content_address
            and gate.plan_address == plan.content_address,
            (gate.matrix_address, gate.plan_address),
            (matrix.content_address, plan.content_address),
            "gate points to the packaged matrix and task plan",
        ),
        _check(
            "payload-addresses",
            ModuleCertificationPacketCheckPlane.BYTES,
            all(
                item.payload is not None
                and hash_bytes(
                    item.payload.encode("utf-8"), prefix=MODULE_CERTIFICATION_PACKET_ARTIFACT_PREFIX
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
            ModuleCertificationPacketCheckPlane.PUBLIC,
            not _has_forbidden_key(
                {"artifacts": [item.to_dict(include_payload=True) for item in artifacts]}
            ),
            "clean",
            "clean",
            "packet artifact projection has no forbidden keys",
        ),
    )
    accepted = (
        matrix.accepted
        and plan.accepted
        and gate.accepted
        and audit.accepted
        and all(item.passed for item in checks)
    )
    state = (
        ModuleCertificationPacketState.ACCEPTED
        if accepted
        else ModuleCertificationPacketState.BLOCKED
    )
    return ModuleCertificationPacket(
        packet_id=packet_id,
        version=MODULE_CERTIFICATION_PACKET_VERSION,
        boundary=MODULE_CERTIFICATION_PACKET_BOUNDARY,
        matrix_address=matrix.content_address,
        gate_address=gate.content_address,
        runtime_address=runtime.content_address,
        state=state,
        accepted=accepted,
        artifacts=artifacts,
        checks=checks,
        content_address=_packet_address(
            packet_id,
            matrix.content_address,
            gate.content_address,
            runtime.content_address,
            state,
            artifacts,
            checks,
        ),
    )


def _manifest_text(packet: ModuleCertificationPacket) -> str:
    return _json_text(packet.to_dict(include_payloads=False))


def write_module_certification_packet(
    packet: ModuleCertificationPacket,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> Path:
    """Write a packet atomically, refusing accidental overwrite by default."""

    if not isinstance(packet, ModuleCertificationPacket):
        raise ValidationError("certification packet writer requires a typed packet")
    target = Path(destination)
    if target.exists() and not allow_existing:
        raise ValidationError("certification packet destination already exists")
    target.mkdir(parents=True, exist_ok=True)
    for artifact in packet.artifacts:
        if artifact.payload is None:
            raise ValidationError(
                f"certification packet artifact has no payload: {artifact.artifact_id}"
            )
        _atomic_write(target / artifact.relative_path, artifact.payload.encode("utf-8"))
    _atomic_write(
        target / MODULE_CERTIFICATION_PACKET_MANIFEST, _manifest_text(packet).encode("utf-8")
    )
    return target


def _check_from_mapping(value: Mapping[str, Any]) -> ModuleCertificationPacketCheck:
    body = dict(value)
    body["plane"] = ModuleCertificationPacketCheckPlane(str(body["plane"]))
    return ModuleCertificationPacketCheck(**body)


def verify_module_certification_packet(
    directory: str | Path,
) -> ModuleCertificationPacketVerification:
    """Verify manifest, paths, exact bytes, links, packet address, and public shape."""

    target = Path(directory)
    manifest_path = target / MODULE_CERTIFICATION_PACKET_MANIFEST
    checks: list[ModuleCertificationPacketCheck] = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        packet_id = str(manifest["packet_id"])
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        packet_id = target.name or "unknown"
        checks.append(
            _check(
                "manifest-readable",
                ModuleCertificationPacketCheckPlane.MANIFEST,
                False,
                str(exc),
                True,
                "manifest is readable JSON",
            )
        )
        return ModuleCertificationPacketVerification(
            packet_id=packet_id,
            checks=tuple(checks),
            accepted=False,
            content_address=hash_bytes(
                canonical_json([item.to_dict() for item in checks]).encode("utf-8"),
                prefix="module-certification-packet-verification",
            ),
        )
    artifacts: list[ModuleCertificationPacketArtifact] = []
    for raw in manifest.get("artifacts", []):
        try:
            relative_path = str(raw["relative_path"])
            payload = (target / relative_path).read_text(encoding="utf-8")
            artifact = ModuleCertificationPacketArtifact(
                artifact_id=str(raw["artifact_id"]),
                relative_path=relative_path,
                media_type=str(raw["media_type"]),
                kind=ModuleCertificationPacketArtifactKind(str(raw["kind"])),
                byte_count=int(raw["byte_count"]),
                line_count=int(raw["line_count"]),
                content_address=str(raw["content_address"]),
                payload=payload,
            )
            artifacts.append(artifact)
        except (OSError, UnicodeDecodeError, KeyError, TypeError, ValueError) as exc:
            checks.append(
                _check(
                    f"artifact-{len(artifacts)}-read",
                    ModuleCertificationPacketCheckPlane.BYTES,
                    False,
                    str(exc),
                    True,
                    "manifest artifact can be read",
                )
            )
    paths = tuple(item.relative_path for item in artifacts)
    actual_paths = {
        item.relative_to(target).as_posix()
        for item in target.rglob("*")
        if item.is_file() and not item.is_symlink()
    }
    expected_paths = set(paths) | {MODULE_CERTIFICATION_PACKET_MANIFEST}
    checks.extend(
        (
            _check(
                "manifest-version-boundary",
                ModuleCertificationPacketCheckPlane.MANIFEST,
                manifest.get("version") == MODULE_CERTIFICATION_PACKET_VERSION
                and manifest.get("boundary") == MODULE_CERTIFICATION_PACKET_BOUNDARY,
                (manifest.get("version"), manifest.get("boundary")),
                (MODULE_CERTIFICATION_PACKET_VERSION, MODULE_CERTIFICATION_PACKET_BOUNDARY),
                "manifest version and public boundary match",
            ),
            _check(
                "manifest-artifact-count",
                ModuleCertificationPacketCheckPlane.MANIFEST,
                len(artifacts) == MODULE_CERTIFICATION_PACKET_ARTIFACT_COUNT,
                len(artifacts),
                MODULE_CERTIFICATION_PACKET_ARTIFACT_COUNT,
                "manifest lists the fixed artifact count",
            ),
            _check(
                "artifact-identities",
                ModuleCertificationPacketCheckPlane.MANIFEST,
                len({item.artifact_id for item in artifacts}) == len(artifacts),
                len({item.artifact_id for item in artifacts}),
                len(artifacts),
                "artifact identifiers are unique",
            ),
            _check(
                "artifact-paths",
                ModuleCertificationPacketCheckPlane.PATH,
                all(_safe_path(item.relative_path) for item in artifacts),
                "safe",
                "safe",
                "artifact paths are safe",
            ),
            _check(
                "no-unexpected-files",
                ModuleCertificationPacketCheckPlane.PATH,
                actual_paths == expected_paths,
                sorted(actual_paths - expected_paths),
                sorted(expected_paths),
                "packet contains exactly the declared files",
            ),
            _check(
                "artifact-bytes",
                ModuleCertificationPacketCheckPlane.BYTES,
                all(
                    item.payload is not None
                    and len(item.payload.encode("utf-8")) == item.byte_count
                    and len(item.payload.splitlines()) == item.line_count
                    for item in artifacts
                ),
                "verified",
                "verified",
                "artifact byte and line counts match",
            ),
            _check(
                "artifact-addresses",
                ModuleCertificationPacketCheckPlane.BYTES,
                all(
                    item.payload is not None
                    and hash_bytes(
                        item.payload.encode("utf-8"),
                        prefix=MODULE_CERTIFICATION_PACKET_ARTIFACT_PREFIX,
                    )
                    == item.content_address
                    for item in artifacts
                ),
                "verified",
                "verified",
                "artifact addresses match exact bytes",
            ),
            _check(
                "public-boundary",
                ModuleCertificationPacketCheckPlane.PUBLIC,
                not _has_forbidden_key(manifest),
                "clean",
                "clean",
                "manifest contains no forbidden public keys",
            ),
            _check(
                "manifest-links",
                ModuleCertificationPacketCheckPlane.LINK,
                all(
                    isinstance(manifest.get(field), str) and bool(manifest.get(field))
                    for field in ("matrix_address", "gate_address", "runtime_address")
                ),
                "present",
                "present",
                "manifest carries matrix, gate, and runtime addresses",
            ),
        )
    )
    raw_checks = manifest.get("checks", [])
    packet_checks: tuple[ModuleCertificationPacketCheck, ...] = ()
    try:
        if not isinstance(raw_checks, list):
            raise TypeError("manifest checks must be an array")
        packet_checks = tuple(_check_from_mapping(raw) for raw in raw_checks)
        checks.extend(packet_checks)
    except (KeyError, TypeError, ValueError) as exc:
        checks.append(
            _check(
                "manifest-checks",
                ModuleCertificationPacketCheckPlane.MANIFEST,
                False,
                str(exc),
                True,
                "manifest checks are typed",
            )
        )
    try:
        packet_address = _packet_address(
            packet_id,
            str(manifest["matrix_address"]),
            str(manifest["gate_address"]),
            str(manifest["runtime_address"]),
            ModuleCertificationPacketState(str(manifest["state"])),
            tuple(artifacts),
            packet_checks,
        )
        checks.append(
            _check(
                "packet-address",
                ModuleCertificationPacketCheckPlane.LINK,
                packet_address == manifest.get("content_address"),
                packet_address,
                manifest.get("content_address"),
                "packet content address matches manifest metadata and artifact addresses",
            )
        )
    except (KeyError, TypeError, ValueError) as exc:
        checks.append(
            _check(
                "packet-address",
                ModuleCertificationPacketCheckPlane.LINK,
                False,
                str(exc),
                True,
                "packet content address can be recomputed",
            )
        )
    accepted = bool(manifest.get("accepted")) and all(item.passed for item in checks)
    body = {
        "packet_id": packet_id,
        "checks": tuple(checks),
        "accepted": accepted,
    }
    return ModuleCertificationPacketVerification(
        **body,
        content_address=hash_bytes(
            canonical_json(jsonable(body)).encode("utf-8"),
            prefix="module-certification-packet-verification",
        ),
    )


def load_module_certification_packet(directory: str | Path) -> ModuleCertificationPacket:
    """Load a packet only after its exact-byte verification succeeds."""

    verification = verify_module_certification_packet(directory)
    if not verification.accepted:
        raise ValidationError("cannot load an unverified certification packet")
    target = Path(directory)
    manifest = json.loads(
        (target / MODULE_CERTIFICATION_PACKET_MANIFEST).read_text(encoding="utf-8")
    )
    artifacts = []
    for raw in manifest["artifacts"]:
        payload = (target / raw["relative_path"]).read_text(encoding="utf-8")
        artifacts.append(
            ModuleCertificationPacketArtifact(
                artifact_id=raw["artifact_id"],
                relative_path=raw["relative_path"],
                media_type=raw["media_type"],
                kind=ModuleCertificationPacketArtifactKind(raw["kind"]),
                byte_count=raw["byte_count"],
                line_count=raw["line_count"],
                content_address=raw["content_address"],
                payload=payload,
            )
        )
    checks = tuple(_check_from_mapping(raw) for raw in manifest["checks"])
    return ModuleCertificationPacket(
        packet_id=manifest["packet_id"],
        version=manifest["version"],
        boundary=manifest["boundary"],
        matrix_address=manifest["matrix_address"],
        gate_address=manifest["gate_address"],
        runtime_address=manifest["runtime_address"],
        state=ModuleCertificationPacketState(manifest["state"]),
        accepted=manifest["accepted"],
        artifacts=tuple(artifacts),
        checks=checks,
        content_address=manifest["content_address"],
    )


def module_certification_packet_json(packet: ModuleCertificationPacket) -> str:
    return canonical_json(packet.to_dict()) + "\n"


def module_certification_packet_schema() -> dict[str, Any]:
    return {
        "version": MODULE_CERTIFICATION_PACKET_VERSION,
        "boundary": MODULE_CERTIFICATION_PACKET_BOUNDARY,
        "manifest": MODULE_CERTIFICATION_PACKET_MANIFEST,
        "artifact_count": MODULE_CERTIFICATION_PACKET_ARTIFACT_COUNT,
        "artifact_fields": [
            "artifact_id",
            "relative_path",
            "media_type",
            "kind",
            "byte_count",
            "line_count",
            "content_address",
        ],
        "check_fields": [
            "check_id",
            "plane",
            "passed",
            "observed",
            "required",
            "detail",
            "content_address",
        ],
        "verification": ["manifest", "paths", "bytes", "links", "public_boundary"],
        "offline": True,
    }


def module_certification_packet_capabilities() -> dict[str, Any]:
    operations = (
        "build_matrix_artifact",
        "build_check_table",
        "build_gap_table",
        "build_task_artifact",
        "build_gate_artifact",
        "build_audit_artifact",
        "build_runtime_artifact",
        "build_observability_artifact",
        "build_summary_artifact",
        "write_exact_bytes",
        "verify_manifest",
        "verify_paths",
        "verify_byte_counts",
        "verify_byte_addresses",
        "verify_public_boundary",
        "load_verified_packet",
    )
    return {
        "version": MODULE_CERTIFICATION_PACKET_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "artifact_count": MODULE_CERTIFICATION_PACKET_ARTIFACT_COUNT,
        "offline": True,
        "read_only_verification": True,
        "atomic_write": True,
    }


__all__ = [
    "build_module_certification_packet",
    "load_module_certification_packet",
    "module_certification_packet_capabilities",
    "module_certification_packet_json",
    "module_certification_packet_schema",
    "verify_module_certification_packet",
    "write_module_certification_packet",
]
