"""Build, verify, reload, and query portable policy-set review packets."""

from __future__ import annotations

import io
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._safe_persistence import _validate_parent, atomic_write_bytes, read_bytes
from .errors import ValidationError
from .module_workbench_release_bundle_catalog_diff_policy_set import (
    load_module_workbench_release_bundle_catalog_diff_policy_set_gate,
    module_workbench_release_bundle_catalog_diff_policy_set_json,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_gate,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_audit import (
    load_module_workbench_release_bundle_catalog_diff_policy_set_audit,
    module_workbench_release_bundle_catalog_diff_policy_set_audit_json,
    render_module_workbench_release_bundle_catalog_diff_policy_set_audit_markdown,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_audit,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_audit_contracts import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAudit,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_contracts import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_contracts import (
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_AUDIT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_BOUNDARY,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DEFAULT_LIMIT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_FORMAT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_GATE,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MANIFEST,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MAX_BYTES,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MAX_CHECKS,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MAX_ENTRIES,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MAX_LIMIT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_REVIEW,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_VERSION,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacket,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketCheck,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketCheckPlane,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketMember,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketVerification,
    address_module_workbench_release_bundle_catalog_diff_policy_set_packet,
    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_check,
    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_member,
    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_verification,
)
from .run_workspace import _has_forbidden_key
from .serialization import (
    _strict_json_loads,
    canonical_json,
    hash_bytes,
)

_UTF8 = "utf-8"
_PACKET_PREFIX = "module-workbench-release-bundle-catalog-diff-policy-set-packet"
_MEMBER_PREFIX = _PACKET_PREFIX + "-member-bytes"
_CHECK_PREFIX = _PACKET_PREFIX + "-check"
_VERIFICATION_PREFIX = _PACKET_PREFIX + "-verification"


def _safe_member_name(value: str) -> bool:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or ":" in value
        or "\x00" in value
        or any(ord(char) < 32 for char in value)
        or value.startswith("/")
    ):
        return False
    return all(part not in {"", ".", ".."} for part in value.split("/"))


def _line_count(value: bytes) -> int:
    return value.count(b"\n")


def _zip_member(name: str) -> zipfile.ZipInfo:
    if name not in {
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MANIFEST,
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_GATE,
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_AUDIT,
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_REVIEW,
    }:
        raise ValidationError(f"unsafe policy-set packet member: {name}")
    info = zipfile.ZipInfo(filename=name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 0
    info.create_version = 20
    info.extract_version = 20
    info.flag_bits = 0
    info.external_attr = 0
    info.extra = b""
    info.comment = b""
    return info


def _read_packet(value: bytes | bytearray | str | Path) -> bytes:
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
    elif isinstance(value, (str, Path)):
        raw = read_bytes(
            value,
            field="policy-set packet",
            max_bytes=MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MAX_BYTES,
        )
    else:
        raise ValidationError("policy-set packet input must be bytes or a path")
    if len(raw) > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MAX_BYTES:
        raise ValidationError("policy-set packet exceeds byte limit")
    return raw


def _member(
    member_id: str,
    relative_path: str,
    media_type: str,
    ordinal: int,
    payload: bytes,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketMember:
    body = {
        "member_id": member_id,
        "relative_path": relative_path,
        "media_type": media_type,
        "ordinal": ordinal,
        "byte_count": len(payload),
        "byte_address": hash_bytes(payload, prefix=_MEMBER_PREFIX),
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketMember(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketMember(
        **body,
        content_address=address_module_workbench_release_bundle_catalog_diff_policy_set_packet_member(
            provisional
        ),
    )


def _review_markdown(
    gate: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate,
    audit: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAudit,
) -> str:
    lines = [
        "# Module Workbench Release Bundle Catalog Diff Policy-Set Packet",
        "",
        f"- Policy-set gate: `{gate.content_address}`",
        f"- Audit: `{audit.content_address}`",
        f"- Aggregate accepted: **{str(gate.accepted).lower()}**",
        f"- Independent audit accepted: **{str(audit.accepted).lower()}**",
        "",
        "This packet is source-free, payload-free, timestamp-free, and deterministic.",
        "",
        "## Policy-set decision",
        "",
        *render_module_workbench_release_bundle_catalog_diff_policy_set_audit_markdown(
            audit
        ).splitlines(),
    ]
    return "\n".join(lines) + "\n"


def _manifest_bytes(
    packet_id: str,
    gate: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate,
    audit: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAudit,
    members: tuple[ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketMember, ...],
) -> bytes:
    payload_members = [item.to_dict() for item in members if item.ordinal > 0]
    body = {
        "version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_VERSION,
        "boundary": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_BOUNDARY,
        "packet_format": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_FORMAT,
        "packet_id": packet_id,
        "policy_set_gate_address": gate.content_address,
        "audit_address": audit.content_address,
        "members": payload_members,
    }
    return (canonical_json(body) + "\n").encode(_UTF8)


def _packet_bytes(
    manifest_bytes: bytes,
    gate_bytes: bytes,
    audit_bytes: bytes,
    review_bytes: bytes,
) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(
        output, mode="w", compression=zipfile.ZIP_STORED, allowZip64=False
    ) as handle:
        handle.writestr(
            _zip_member(MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MANIFEST),
            manifest_bytes,
        )
        handle.writestr(
            _zip_member(MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_GATE),
            gate_bytes,
        )
        handle.writestr(
            _zip_member(MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_AUDIT),
            audit_bytes,
        )
        handle.writestr(
            _zip_member(MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_REVIEW),
            review_bytes,
        )
    return output.getvalue()


def build_module_workbench_release_bundle_catalog_diff_policy_set_packet(
    gate: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate,
    audit: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAudit,
    *,
    packet_id: str = "glio-noncode-module-workbench-release-bundle-catalog-diff-policy-set-packet",
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacket:
    """Build deterministic ZIP bytes while preserving blocked gate evidence."""

    if not isinstance(gate, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate):
        raise ValidationError("policy-set packet requires a typed policy-set gate")
    if not isinstance(audit, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAudit):
        raise ValidationError("policy-set packet requires a typed policy-set audit")
    verify_module_workbench_release_bundle_catalog_diff_policy_set_gate(gate)
    verify_module_workbench_release_bundle_catalog_diff_policy_set_audit(audit)
    if audit.policy_set_gate_address != gate.content_address:
        raise ValidationError("policy-set packet gate and audit addresses do not agree")
    gate_bytes = module_workbench_release_bundle_catalog_diff_policy_set_json(gate).encode(_UTF8)
    audit_bytes = module_workbench_release_bundle_catalog_diff_policy_set_audit_json(audit).encode(
        _UTF8
    )
    review_bytes = _review_markdown(gate, audit).encode(_UTF8)
    payload_members = (
        _member(
            "gate",
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_GATE,
            "application/json",
            1,
            gate_bytes,
        ),
        _member(
            "audit",
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_AUDIT,
            "application/json",
            2,
            audit_bytes,
        ),
        _member(
            "review",
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_REVIEW,
            "text/markdown",
            3,
            review_bytes,
        ),
    )
    manifest_bytes = _manifest_bytes(packet_id, gate, audit, payload_members)
    raw = _packet_bytes(manifest_bytes, gate_bytes, audit_bytes, review_bytes)
    members = (
        _member(
            "manifest",
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MANIFEST,
            "application/json",
            0,
            manifest_bytes,
        ),
        *payload_members,
    )
    if len(raw) > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MAX_BYTES:
        raise ValidationError("policy-set packet exceeds byte limit")
    body = {
        "packet_id": packet_id,
        "policy_set_gate_address": gate.content_address,
        "audit_address": audit.content_address,
        "packet_address": hash_bytes(raw, prefix=_PACKET_PREFIX),
        "packet_byte_count": len(raw),
        "members": members,
        "packet_bytes": raw,
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacket(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacket(
        **body,
        content_address=address_module_workbench_release_bundle_catalog_diff_policy_set_packet(
            provisional
        ),
    )


def module_workbench_release_bundle_catalog_diff_policy_set_packet_bytes(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacket,
) -> bytes:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_value(value)
    return value.packet_bytes


def write_module_workbench_release_bundle_catalog_diff_policy_set_packet(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacket,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacket:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_value(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("policy-set packet destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("policy-set packet destination is not a file")
    _validate_parent(path.parent, "policy-set packet destination")
    atomic_write_bytes(path, value.packet_bytes, field="policy-set packet destination")
    return value


def _zip_infos(raw: bytes) -> tuple[zipfile.ZipInfo, ...]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw), mode="r") as handle:
            return tuple(handle.infolist())
    except (OSError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise ValidationError(f"cannot read policy-set packet ZIP: {exc}") from exc


def _read_members(raw: bytes) -> dict[str, bytes]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw), mode="r") as handle:
            return {info.filename: handle.read(info) for info in handle.infolist()}
    except (OSError, KeyError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise ValidationError(f"cannot read policy-set packet members: {exc}") from exc


def _check(
    check_id: str,
    plane: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketCheck(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketCheck(
        **body,
        content_address=address_module_workbench_release_bundle_catalog_diff_policy_set_packet_check(
            provisional
        ),
    )


def _verification(
    packet_id: str,
    packet_address: str,
    gate_address: str,
    audit_address: str,
    present_count: int,
    missing_count: int,
    checks: list[ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketCheck],
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketVerification:
    ordered = tuple(sorted(checks, key=lambda item: item.check_id))
    if len(ordered) > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MAX_CHECKS:
        raise ValidationError("policy-set packet produced too many checks")
    body = {
        "packet_id": packet_id,
        "packet_address": packet_address,
        "policy_set_gate_address": gate_address,
        "audit_address": audit_address,
        "entry_count": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MAX_ENTRIES,
        "present_count": present_count,
        "missing_count": missing_count,
        "checks": ordered,
        "accepted": all(item.passed for item in ordered),
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketVerification(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketVerification(
        **body,
        content_address=address_module_workbench_release_bundle_catalog_diff_policy_set_packet_verification(
            provisional
        ),
    )


def verify_module_workbench_release_bundle_catalog_diff_policy_set_packet(
    value: bytes | bytearray | str | Path,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketVerification:
    """Verify exact members, canonical payloads, lineage, and public boundary."""

    raw = _read_packet(value)
    packet_address = hash_bytes(raw, prefix=_PACKET_PREFIX)
    packet_id = "unavailable"
    gate_address = "unavailable"
    audit_address = "unavailable"
    checks: list[ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketCheck] = []
    try:
        infos = _zip_infos(raw)
        zip_ok = True
        zip_detail = "ZIP members are readable"
    except ValidationError as exc:
        infos = ()
        zip_ok = False
        zip_detail = str(exc)
    checks.append(
        _check(
            "zip-readable",
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketCheckPlane.ZIP,
            zip_ok,
            zip_detail,
            "readable",
            "packet is a readable ZIP",
        )
    )
    names = tuple(info.filename for info in infos)
    duplicate_names = len(names) != len(set(names))
    unsafe_names = tuple(name for name in names if not _safe_member_name(name))
    special_names = tuple(name for name, info in zip(names, infos, strict=True) if info.is_dir())
    checks.append(
        _check(
            "unique-members",
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketCheckPlane.PATH,
            not duplicate_names,
            names if duplicate_names else (),
            "unique",
            "packet member names are unique",
        )
    )
    checks.append(
        _check(
            "safe-paths",
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketCheckPlane.PATH,
            not unsafe_names,
            unsafe_names,
            (),
            "packet member paths are traversal-free",
        )
    )
    checks.append(
        _check(
            "regular-members",
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketCheckPlane.ZIP,
            not special_names,
            special_names,
            (),
            "packet contains regular files only",
        )
    )
    members: dict[str, bytes] = {}
    if zip_ok:
        try:
            members = _read_members(raw)
        except ValidationError:
            members = {}
    manifest_raw = members.get(
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MANIFEST, b""
    )
    try:
        manifest = _strict_json_loads(manifest_raw.decode(_UTF8))
    except (UnicodeDecodeError, ValueError):
        manifest = None
    manifest_ok = isinstance(manifest, Mapping)
    checks.append(
        _check(
            "manifest-present",
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketCheckPlane.MANIFEST,
            manifest_ok,
            "present" if manifest_ok else "missing-or-invalid",
            "present",
            "packet has a readable JSON manifest",
        )
    )
    canonical_manifest = manifest_ok and manifest_raw == (canonical_json(manifest) + "\n").encode(
        _UTF8
    )
    checks.append(
        _check(
            "manifest-canonical",
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketCheckPlane.MANIFEST,
            canonical_manifest,
            "canonical" if canonical_manifest else "non-canonical",
            "canonical",
            "manifest bytes are canonical UTF-8 JSON",
        )
    )
    expected_names = {
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MANIFEST,
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_GATE,
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_AUDIT,
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_REVIEW,
    }
    checks.append(
        _check(
            "declared-members",
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketCheckPlane.MANIFEST,
            set(names) == expected_names,
            {
                "missing": sorted(expected_names - set(names)),
                "extra": sorted(set(names) - expected_names),
            },
            {"missing": [], "extra": []},
            "packet contains the exact four-member allowlist",
        )
    )
    if manifest_ok:
        packet_id = str(manifest.get("packet_id", "unavailable"))
        gate_address = str(manifest.get("policy_set_gate_address", "unavailable"))
        audit_address = str(manifest.get("audit_address", "unavailable"))
    gate: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate | None = None
    audit: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAudit | None = None
    gate_raw = members.get(MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_GATE, b"")
    audit_raw = members.get(
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_AUDIT, b""
    )
    try:
        gate = load_module_workbench_release_bundle_catalog_diff_policy_set_gate(gate_raw)
    except (ValidationError, OSError):
        pass
    try:
        audit = load_module_workbench_release_bundle_catalog_diff_policy_set_audit(audit_raw)
    except (ValidationError, OSError):
        pass
    checks.append(
        _check(
            "gate-valid",
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketCheckPlane.GATE,
            gate is not None,
            gate.content_address if gate else "invalid",
            "valid",
            "embedded policy-set gate reloads and verifies",
        )
    )
    checks.append(
        _check(
            "audit-valid",
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketCheckPlane.AUDIT,
            audit is not None and audit.accepted,
            audit.content_address if audit else "invalid",
            "accepted",
            "embedded independent audit reloads and is accepted",
        )
    )
    lineage_ok = (
        gate is not None
        and audit is not None
        and audit.policy_set_gate_address == gate.content_address
        and gate.content_address == gate_address
        and audit.content_address == audit_address
    )
    checks.append(
        _check(
            "address-lineage",
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketCheckPlane.BYTES,
            lineage_ok,
            {
                "gate": gate.content_address if gate else "invalid",
                "audit": audit.content_address if audit else "invalid",
            },
            {"gate": gate_address, "audit": audit_address},
            "manifest, gate, and audit addresses agree",
        )
    )
    payload_rows = manifest.get("members") if manifest_ok else None
    payload_names = (
        tuple(item.get("relative_path") for item in payload_rows)
        if isinstance(payload_rows, list)
        and all(isinstance(item, Mapping) for item in payload_rows)
        else ()
    )
    payload_ok = payload_names == (
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_GATE,
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_AUDIT,
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_REVIEW,
    )
    checks.append(
        _check(
            "manifest-payload",
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketCheckPlane.MANIFEST,
            payload_ok,
            payload_names,
            expected_names
            - {MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MANIFEST},
            "manifest declares gate, audit, and review in ordinal order",
        )
    )
    hash_ok = False
    if manifest_ok and isinstance(payload_rows, list):
        actual = {
            name: members.get(name, b"")
            for name in expected_names
            - {MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MANIFEST}
        }
        hash_ok = all(
            isinstance(row, Mapping)
            and row.get("byte_count") == len(actual.get(str(row.get("relative_path")), b""))
            and row.get("byte_address")
            == hash_bytes(actual.get(str(row.get("relative_path")), b""), prefix=_MEMBER_PREFIX)
            for row in payload_rows
        )
    checks.append(
        _check(
            "member-bytes",
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketCheckPlane.BYTES,
            hash_ok,
            "valid" if hash_ok else "mismatch",
            "valid",
            "manifest member sizes and byte addresses replay",
        )
    )
    review_ok = False
    if gate is not None and audit is not None:
        review_ok = members.get(
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_REVIEW, b""
        ).decode(_UTF8, errors="replace") == _review_markdown(gate, audit)
    checks.append(
        _check(
            "review-replay",
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketCheckPlane.BYTES,
            review_ok,
            "replayed" if review_ok else "mismatch",
            "replayed",
            "review Markdown is regenerated from embedded decisions",
        )
    )
    public_ok = bool(
        manifest_ok
        and gate is not None
        and audit is not None
        and not _has_forbidden_key(manifest)
        and not _has_forbidden_key(gate.to_dict())
        and not _has_forbidden_key(audit.to_dict())
    )
    checks.append(
        _check(
            "public-boundary",
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketCheckPlane.PUBLIC,
            public_ok,
            "clean" if public_ok else "forbidden-or-invalid",
            "clean",
            "packet payloads contain only public aggregate fields",
        )
    )
    present_count = min(
        len(names), MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MAX_ENTRIES
    )
    missing_count = max(
        0,
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MAX_ENTRIES - present_count,
    )
    return _verification(
        packet_id, packet_address, gate_address, audit_address, present_count, missing_count, checks
    )


def verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_value(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacket,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacket:
    if not isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacket):
        raise ValidationError("typed policy-set packet verification requires a packet")
    if hash_bytes(value.packet_bytes, prefix=_PACKET_PREFIX) != value.packet_address:
        raise ValidationError("policy-set packet binary address mismatch")
    if (
        address_module_workbench_release_bundle_catalog_diff_policy_set_packet(value)
        != value.content_address
    ):
        raise ValidationError("policy-set packet descriptor address mismatch")
    return value


def load_module_workbench_release_bundle_catalog_diff_policy_set_packet(
    value: bytes | bytearray | str | Path,
) -> tuple[
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAudit,
    str,
]:
    verification = verify_module_workbench_release_bundle_catalog_diff_policy_set_packet(value)
    if not verification.accepted:
        raise ValidationError("cannot load a blocked or malformed policy-set packet")
    members = _read_members(_read_packet(value))
    gate = load_module_workbench_release_bundle_catalog_diff_policy_set_gate(
        members[MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_GATE]
    )
    audit = load_module_workbench_release_bundle_catalog_diff_policy_set_audit(
        members[MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_AUDIT]
    )
    review = members[MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_REVIEW].decode(
        _UTF8
    )
    return gate, audit, review


def query_module_workbench_release_bundle_catalog_diff_policy_set_packet(
    value: bytes | bytearray | str | Path,
    *,
    resource: str = "summary",
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DEFAULT_LIMIT,
) -> dict[str, Any]:
    if resource not in {"members", "summary", "manifest", "gate", "audit", "review"}:
        raise ValidationError("policy-set packet resource is invalid")
    if (
        offset < 0
        or limit < 1
        or limit > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MAX_LIMIT
    ):
        raise ValidationError("policy-set packet paging is invalid")
    raw = _read_packet(value)
    verification = verify_module_workbench_release_bundle_catalog_diff_policy_set_packet(raw)
    members = _read_members(raw)
    if resource == "members":
        rows = [
            {
                "name": name,
                "byte_count": len(payload),
                "byte_address": hash_bytes(payload, prefix=_MEMBER_PREFIX),
            }
            for name, payload in sorted(members.items())
        ]
    elif resource == "summary":
        rows = [verification.to_dict()]
    elif resource == "manifest":
        parsed = _strict_json_loads(
            members[MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MANIFEST].decode(
                _UTF8
            )
        )
        rows = [parsed]
    elif resource == "gate":
        rows = [
            load_module_workbench_release_bundle_catalog_diff_policy_set_gate(
                members[MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_GATE]
            ).to_dict()
        ]
    elif resource == "audit":
        rows = [
            load_module_workbench_release_bundle_catalog_diff_policy_set_audit(
                members[MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_AUDIT]
            ).to_dict()
        ]
    else:
        rows = [
            {
                "markdown": members[
                    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_REVIEW
                ].decode(_UTF8)
            }
        ]
    body = {
        "packet_address": verification.packet_address,
        "resource": resource,
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "accepted": verification.accepted,
    }
    return body | {
        "content_address": hash_bytes(
            canonical_json(body).encode(_UTF8), prefix=_PACKET_PREFIX + "-query"
        )
    }


def module_workbench_release_bundle_catalog_diff_policy_set_packet_json(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacket,
) -> str:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_value(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_release_bundle_catalog_diff_policy_set_packet_schema() -> dict[str, Any]:
    return {
        "version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_VERSION,
        "boundary": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_BOUNDARY,
        "format": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_FORMAT,
        "members": [
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_MANIFEST,
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_GATE,
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_AUDIT,
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_REVIEW,
        ],
        "resources": ["members", "summary", "manifest", "gate", "audit", "review"],
        "source_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_release_bundle_catalog_diff_policy_set_packet_capabilities() -> dict[str, Any]:
    operations = (
        "build_packet",
        "verify_zip",
        "verify_manifest",
        "verify_gate",
        "verify_audit",
        "verify_member_bytes",
        "load_source_free",
        "query_members",
        "query_gate",
        "query_audit",
        "query_review",
        "export_exact_bytes",
    )
    return {
        "version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "source_free": True,
        "read_only": True,
    }


__all__ = [
    "build_module_workbench_release_bundle_catalog_diff_policy_set_packet",
    "load_module_workbench_release_bundle_catalog_diff_policy_set_packet",
    "module_workbench_release_bundle_catalog_diff_policy_set_packet_bytes",
    "module_workbench_release_bundle_catalog_diff_policy_set_packet_capabilities",
    "module_workbench_release_bundle_catalog_diff_policy_set_packet_json",
    "module_workbench_release_bundle_catalog_diff_policy_set_packet_schema",
    "query_module_workbench_release_bundle_catalog_diff_policy_set_packet",
    "verify_module_workbench_release_bundle_catalog_diff_policy_set_packet",
    "verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_value",
    "write_module_workbench_release_bundle_catalog_diff_policy_set_packet",
]
