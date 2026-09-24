"""Build, verify, reload, and query packet-diff policy review packets."""

# The public function names intentionally mirror the full module boundary.
# ruff: noqa: E501

from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._safe_persistence import _validate_parent, atomic_write_bytes, read_bytes
from .errors import ValidationError
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff import (
    load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_json,
    render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_markdown,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_contracts import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiff,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy import (
    load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_gate,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_json,
    render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_markdown,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_gate,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit import (
    load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_json,
    render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_markdown,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_contracts import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAudit,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_contracts import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyGate,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_contracts import (
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_AUDIT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_BOUNDARY,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_DEFAULT_LIMIT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_DIFF,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_FORMAT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_GATE,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_MANIFEST,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_MAX_BYTES,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_MAX_CHECKS,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_MAX_ENTRIES,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_MAX_LIMIT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_REVIEW,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_VERSION,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacket,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCheck,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCheckPlane,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketMember,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketVerification,
    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet,
    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_check,
    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_member,
    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_verification,
)
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, hash_bytes

_UTF8 = "utf-8"
_PACKET_PREFIX = "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet"
_MEMBER_PREFIX = _PACKET_PREFIX + "-member-bytes"


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


def _zip_member(name: str) -> zipfile.ZipInfo:
    if name not in {
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_MANIFEST,
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_DIFF,
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_GATE,
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_AUDIT,
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_REVIEW,
    }:
        raise ValidationError(f"unsafe packet-diff policy packet member: {name}")
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
            field="packet-diff policy packet",
            max_bytes=MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_MAX_BYTES,
        )
    else:
        raise ValidationError("packet-diff policy packet input must be bytes or a path")
    if (
        len(raw)
        > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_MAX_BYTES
    ):
        raise ValidationError("packet-diff policy packet exceeds byte limit")
    return raw


def _member(
    member_id: str,
    relative_path: str,
    media_type: str,
    ordinal: int,
    payload: bytes,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketMember:
    body = {
        "member_id": member_id,
        "relative_path": relative_path,
        "media_type": media_type,
        "ordinal": ordinal,
        "byte_count": len(payload),
        "byte_address": hash_bytes(payload, prefix=_MEMBER_PREFIX),
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketMember(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketMember(
        **body,
        content_address=(
            address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_member(
                provisional
            )
        ),
    )


def _review_markdown(
    diff: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiff,
    gate: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyGate,
    audit: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAudit,
) -> str:
    lines = [
        "# Module Workbench Packet-Diff Policy Review Packet",
        "",
        f"- Packet diff: `{diff.content_address}`",
        f"- Policy gate: `{gate.content_address}`",
        f"- Independent policy audit: `{audit.content_address}`",
        f"- Direction: **{diff.direction.value}**",
        f"- State transition: **{diff.state_transition.value}**",
        f"- Policy accepted: **{str(gate.accepted).lower()}**",
        f"- Audit accepted: **{str(audit.accepted).lower()}**",
        "",
        "This packet is source-free, payload-free, timestamp-free, and deterministic.",
        "A blocked policy decision is retained as review evidence; packet admission requires the independent audit to pass.",
        "",
        "## Packet comparison",
        "",
        *render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_markdown(
            diff
        ).splitlines(),
        "",
        "## Policy decision",
        "",
        *render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_markdown(
            gate
        ).splitlines(),
        "",
        "## Independent audit",
        "",
        *render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_markdown(
            audit
        ).splitlines(),
    ]
    return "\n".join(lines) + "\n"


def _manifest_bytes(
    packet_id: str,
    diff: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiff,
    gate: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyGate,
    audit: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAudit,
    members: tuple[
        ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketMember,
        ...,
    ],
) -> bytes:
    body = {
        "version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_VERSION,
        "boundary": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_BOUNDARY,
        "packet_format": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_FORMAT,
        "packet_id": packet_id,
        "packet_diff_address": diff.content_address,
        "policy_gate_address": gate.content_address,
        "policy_audit_address": audit.content_address,
        "members": [item.to_dict() for item in members if item.ordinal > 0],
    }
    return (canonical_json(body) + "\n").encode(_UTF8)


def _packet_bytes(
    manifest_bytes: bytes,
    diff_bytes: bytes,
    gate_bytes: bytes,
    audit_bytes: bytes,
    review_bytes: bytes,
) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(
        output, mode="w", compression=zipfile.ZIP_STORED, allowZip64=False
    ) as handle:
        for name, payload in (
            (
                MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_MANIFEST,
                manifest_bytes,
            ),
            (
                MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_DIFF,
                diff_bytes,
            ),
            (
                MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_GATE,
                gate_bytes,
            ),
            (
                MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_AUDIT,
                audit_bytes,
            ),
            (
                MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_REVIEW,
                review_bytes,
            ),
        ):
            handle.writestr(_zip_member(name), payload)
    return output.getvalue()


def build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(
    diff: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiff,
    gate: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyGate,
    audit: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAudit,
    *,
    packet_id: str = (
        "glio-noncode-module-workbench-release-bundle-catalog-diff-policy-set-"
        "packet-diff-policy-packet"
    ),
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacket:
    """Build deterministic bytes while retaining blocked policy evidence."""

    if not isinstance(diff, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiff):
        raise ValidationError("packet-diff policy packet requires a typed packet diff")
    if not isinstance(gate, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyGate):
        raise ValidationError("packet-diff policy packet requires a typed policy gate")
    if not isinstance(audit, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAudit):
        raise ValidationError("packet-diff policy packet requires a typed policy audit")
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff(diff)
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_gate(gate)
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit(audit)
    if gate.diff_address != diff.content_address:
        raise ValidationError("packet-diff policy packet gate and diff addresses do not agree")
    if audit.policy_gate_address != gate.content_address:
        raise ValidationError("packet-diff policy packet audit and gate addresses do not agree")
    if audit.diff_address != diff.content_address:
        raise ValidationError("packet-diff policy packet audit and diff addresses do not agree")
    if not audit.accepted:
        raise ValidationError("packet-diff policy packet requires an accepted independent audit")
    diff_bytes = module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_json(
        diff
    ).encode(_UTF8)
    gate_bytes = module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_json(
        gate
    ).encode(_UTF8)
    audit_bytes = (
        module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_json(
            audit
        ).encode(_UTF8)
    )
    review_bytes = _review_markdown(diff, gate, audit).encode(_UTF8)
    payload_members = (
        _member(
            "packet-diff",
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_DIFF,
            "application/json",
            1,
            diff_bytes,
        ),
        _member(
            "policy-gate",
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_GATE,
            "application/json",
            2,
            gate_bytes,
        ),
        _member(
            "policy-audit",
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_AUDIT,
            "application/json",
            3,
            audit_bytes,
        ),
        _member(
            "review",
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_REVIEW,
            "text/markdown",
            4,
            review_bytes,
        ),
    )
    manifest_bytes = _manifest_bytes(packet_id, diff, gate, audit, payload_members)
    raw = _packet_bytes(manifest_bytes, diff_bytes, gate_bytes, audit_bytes, review_bytes)
    members = (
        _member(
            "manifest",
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_MANIFEST,
            "application/json",
            0,
            manifest_bytes,
        ),
        *payload_members,
    )
    if (
        len(raw)
        > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_MAX_BYTES
    ):
        raise ValidationError("packet-diff policy packet exceeds byte limit")
    body = {
        "packet_id": packet_id,
        "packet_diff_address": diff.content_address,
        "policy_gate_address": gate.content_address,
        "policy_audit_address": audit.content_address,
        "packet_address": hash_bytes(raw, prefix=_PACKET_PREFIX),
        "packet_byte_count": len(raw),
        "members": members,
        "packet_bytes": raw,
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacket(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacket(
        **body,
        content_address=(
            address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(
                provisional
            )
        ),
    )


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_bytes(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacket,
) -> bytes:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_value(
        value
    )
    return value.packet_bytes


def write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacket,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacket:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_value(
        value
    )
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("packet-diff policy packet destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("packet-diff policy packet destination is not a file")
    _validate_parent(path.parent, "packet-diff policy packet destination")
    atomic_write_bytes(path, value.packet_bytes, field="packet-diff policy packet destination")
    return value


def _zip_infos(raw: bytes) -> tuple[zipfile.ZipInfo, ...]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw), mode="r") as handle:
            return tuple(handle.infolist())
    except (OSError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise ValidationError(f"cannot read packet-diff policy packet ZIP: {exc}") from exc


def _read_members(raw: bytes) -> dict[str, bytes]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw), mode="r") as handle:
            return {info.filename: handle.read(info) for info in handle.infolist()}
    except (OSError, KeyError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise ValidationError(f"cannot read packet-diff policy packet members: {exc}") from exc


def _check(
    check_id: str,
    plane: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCheck(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCheck(
        **body,
        content_address=(
            address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_check(
                provisional
            )
        ),
    )


def _verification(
    packet_id: str,
    packet_address: str,
    diff_address: str,
    gate_address: str,
    audit_address: str,
    present_count: int,
    missing_count: int,
    checks: list[ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCheck],
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketVerification:
    ordered = tuple(sorted(checks, key=lambda item: item.check_id))
    if (
        len(ordered)
        > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_MAX_CHECKS
    ):
        raise ValidationError("packet-diff policy packet produced too many checks")
    body = {
        "packet_id": packet_id,
        "packet_address": packet_address,
        "packet_diff_address": diff_address,
        "policy_gate_address": gate_address,
        "policy_audit_address": audit_address,
        "entry_count": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_MAX_ENTRIES,
        "present_count": present_count,
        "missing_count": missing_count,
        "checks": ordered,
        "accepted": all(item.passed for item in ordered),
    }
    provisional = (
        ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketVerification(
            **body,
            content_address="pending",
        )
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketVerification(
        **body,
        content_address=(
            address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_verification(
                provisional
            )
        ),
    )


def verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(
    value: bytes | bytearray | str | Path,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketVerification:
    """Verify exact members, nested lineage, canonical bytes, and public boundary."""

    raw = _read_packet(value)
    packet_address = hash_bytes(raw, prefix=_PACKET_PREFIX)
    packet_id = "unavailable"
    diff_address = "unavailable"
    gate_address = "unavailable"
    audit_address = "unavailable"
    checks: list[ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCheck] = []
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
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCheckPlane.ZIP,
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
    checks.extend(
        (
            _check(
                "unique-members",
                ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCheckPlane.PATH,
                not duplicate_names,
                names if duplicate_names else (),
                "unique",
                "packet member names are unique",
            ),
            _check(
                "safe-paths",
                ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCheckPlane.PATH,
                not unsafe_names,
                unsafe_names,
                (),
                "packet member paths are traversal-free",
            ),
            _check(
                "regular-members",
                ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCheckPlane.ZIP,
                not special_names,
                special_names,
                (),
                "packet contains regular files only",
            ),
        )
    )
    members: dict[str, bytes] = {}
    if zip_ok:
        try:
            members = _read_members(raw)
        except ValidationError:
            members = {}
    manifest_raw = members.get(
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_MANIFEST,
        b"",
    )
    try:
        manifest = _strict_json_loads(manifest_raw.decode(_UTF8))
    except (UnicodeDecodeError, ValueError):
        manifest = None
    manifest_ok = isinstance(manifest, Mapping)
    checks.extend(
        (
            _check(
                "manifest-present",
                ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCheckPlane.MANIFEST,
                manifest_ok,
                "present" if manifest_ok else "missing-or-invalid",
                "present",
                "packet has a readable JSON manifest",
            ),
            _check(
                "manifest-canonical",
                ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCheckPlane.MANIFEST,
                manifest_ok and manifest_raw == (canonical_json(manifest) + "\n").encode(_UTF8),
                "canonical"
                if manifest_ok and manifest_raw == (canonical_json(manifest) + "\n").encode(_UTF8)
                else "non-canonical",
                "canonical",
                "manifest bytes are canonical UTF-8 JSON",
            ),
        )
    )
    expected_names = {
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_MANIFEST,
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_DIFF,
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_GATE,
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_AUDIT,
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_REVIEW,
    }
    checks.append(
        _check(
            "declared-members",
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCheckPlane.MANIFEST,
            set(names) == expected_names,
            {
                "missing": sorted(expected_names - set(names)),
                "extra": sorted(set(names) - expected_names),
            },
            {"missing": [], "extra": []},
            "packet contains the exact five-member allowlist",
        )
    )
    if manifest_ok:
        packet_id = str(manifest.get("packet_id", "unavailable"))
        diff_address = str(manifest.get("packet_diff_address", "unavailable"))
        gate_address = str(manifest.get("policy_gate_address", "unavailable"))
        audit_address = str(manifest.get("policy_audit_address", "unavailable"))
    manifest_format_ok = bool(
        manifest_ok
        and manifest.get("version")
        == MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_VERSION
        and manifest.get("boundary")
        == MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_BOUNDARY
        and manifest.get("packet_format")
        == MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_FORMAT
    )
    checks.append(
        _check(
            "manifest-format",
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCheckPlane.MANIFEST,
            manifest_format_ok,
            "valid" if manifest_format_ok else "invalid",
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_FORMAT,
            "manifest declares the current packet version, boundary, and format",
        )
    )
    diff: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiff | None = None
    gate: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyGate | None = None
    audit: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAudit | None = None
    try:
        diff = load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff(
            members.get(
                MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_DIFF,
                b"",
            )
        )
    except (ValidationError, OSError):
        pass
    try:
        gate = load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_gate(
            members.get(
                MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_GATE,
                b"",
            )
        )
    except (ValidationError, OSError):
        pass
    try:
        audit = load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit(
            members.get(
                MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_AUDIT,
                b"",
            )
        )
    except (ValidationError, OSError):
        pass
    checks.extend(
        (
            _check(
                "diff-valid",
                ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCheckPlane.DIFF,
                diff is not None,
                diff.content_address if diff else "invalid",
                "valid",
                "embedded packet diff reloads and verifies",
            ),
            _check(
                "policy-gate-valid",
                ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCheckPlane.POLICY,
                gate is not None,
                gate.content_address if gate else "invalid",
                "valid",
                "embedded policy gate reloads and verifies",
            ),
            _check(
                "policy-audit-valid",
                ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCheckPlane.AUDIT,
                audit is not None and audit.accepted,
                audit.content_address if audit else "invalid",
                "accepted",
                "embedded independent policy audit reloads and is accepted",
            ),
        )
    )
    lineage_ok = (
        diff is not None
        and gate is not None
        and audit is not None
        and gate.diff_address == diff.content_address
        and audit.diff_address == diff.content_address
        and audit.policy_gate_address == gate.content_address
        and diff.content_address == diff_address
        and gate.content_address == gate_address
        and audit.content_address == audit_address
    )
    checks.append(
        _check(
            "address-lineage",
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCheckPlane.BYTES,
            lineage_ok,
            {
                "diff": diff.content_address if diff else "invalid",
                "gate": gate.content_address if gate else "invalid",
                "audit": audit.content_address if audit else "invalid",
            },
            {"diff": diff_address, "gate": gate_address, "audit": audit_address},
            "manifest and nested packet-diff policy lineage agree",
        )
    )
    payload_rows = manifest.get("members") if manifest_ok else None
    payload_names = (
        tuple(item.get("relative_path") for item in payload_rows)
        if isinstance(payload_rows, list)
        and all(isinstance(item, Mapping) for item in payload_rows)
        else ()
    )
    expected_payload_names = (
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_DIFF,
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_GATE,
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_AUDIT,
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_REVIEW,
    )
    checks.append(
        _check(
            "manifest-payload",
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCheckPlane.MANIFEST,
            payload_names == expected_payload_names,
            payload_names,
            expected_payload_names,
            "manifest declares diff, gate, audit, and review in ordinal order",
        )
    )
    hash_ok = False
    if isinstance(payload_rows, list) and len(payload_rows) == len(expected_payload_names):
        actual = {name: members.get(name, b"") for name in expected_payload_names}
        hash_ok = all(
            isinstance(row, Mapping)
            and row.get("relative_path") in actual
            and row.get("byte_count") == len(actual[str(row.get("relative_path"))])
            and row.get("byte_address")
            == hash_bytes(actual[str(row.get("relative_path"))], prefix=_MEMBER_PREFIX)
            for row in payload_rows
        )
    checks.append(
        _check(
            "member-bytes",
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCheckPlane.BYTES,
            hash_ok,
            "valid" if hash_ok else "mismatch",
            "valid",
            "manifest member sizes and byte addresses replay",
        )
    )
    nested_bytes_ok = bool(
        diff is not None
        and gate is not None
        and audit is not None
        and members.get(
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_DIFF,
            b"",
        )
        == module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_json(diff).encode(
            _UTF8
        )
        and members.get(
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_GATE,
            b"",
        )
        == module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_json(
            gate
        ).encode(_UTF8)
        and members.get(
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_AUDIT,
            b"",
        )
        == module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_json(
            audit
        ).encode(_UTF8)
    )
    checks.append(
        _check(
            "nested-canonical-bytes",
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCheckPlane.BYTES,
            nested_bytes_ok,
            "canonical" if nested_bytes_ok else "mismatch",
            "canonical",
            "nested diff, gate, and audit bytes regenerate exactly",
        )
    )
    review_ok = False
    if diff is not None and gate is not None and audit is not None:
        review_ok = members.get(
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_REVIEW,
            b"",
        ).decode(_UTF8, errors="replace") == _review_markdown(diff, gate, audit)
    checks.append(
        _check(
            "review-replay",
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCheckPlane.REVIEW,
            review_ok,
            "replayed" if review_ok else "mismatch",
            "replayed",
            "review Markdown regenerates from embedded decisions",
        )
    )
    public_ok = bool(
        manifest_ok
        and diff is not None
        and gate is not None
        and audit is not None
        and not _has_forbidden_key(manifest)
        and not _has_forbidden_key(diff.to_dict())
        and not _has_forbidden_key(gate.to_dict())
        and not _has_forbidden_key(audit.to_dict())
    )
    checks.append(
        _check(
            "public-boundary",
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCheckPlane.PUBLIC,
            public_ok,
            "clean" if public_ok else "forbidden-or-invalid",
            "clean",
            "packet payloads contain only public aggregate fields",
        )
    )
    present_count = min(
        len(names),
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_MAX_ENTRIES,
    )
    missing_count = max(
        0,
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_MAX_ENTRIES
        - present_count,
    )
    return _verification(
        packet_id,
        packet_address,
        diff_address,
        gate_address,
        audit_address,
        present_count,
        missing_count,
        checks,
    )


def verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_value(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacket,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacket:
    if not isinstance(
        value,
        ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacket,
    ):
        raise ValidationError("typed packet-diff policy packet verification requires a packet")
    if hash_bytes(value.packet_bytes, prefix=_PACKET_PREFIX) != value.packet_address:
        raise ValidationError("packet-diff policy packet binary address mismatch")
    if (
        address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(
            value
        )
        != value.content_address
    ):
        raise ValidationError("packet-diff policy packet descriptor address mismatch")
    return value


def load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(
    value: bytes | bytearray | str | Path,
) -> tuple[
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiff,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyGate,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAudit,
    str,
]:
    verification = (
        verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(
            value
        )
    )
    if not verification.accepted:
        raise ValidationError("cannot load a blocked or malformed packet-diff policy packet")
    members = _read_members(_read_packet(value))
    diff = load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff(
        members[
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_DIFF
        ]
    )
    gate = load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_gate(
        members[
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_GATE
        ]
    )
    audit = load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit(
        members[
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_AUDIT
        ]
    )
    review = members[
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_REVIEW
    ].decode(_UTF8)
    return diff, gate, audit, review


def query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(
    value: bytes | bytearray | str | Path,
    *,
    resource: str = "summary",
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_DEFAULT_LIMIT,
) -> dict[str, Any]:
    resources = {
        "members",
        "summary",
        "manifest",
        "packet-diff",
        "policy-gate",
        "policy-audit",
        "review",
    }
    if resource not in resources:
        raise ValidationError("packet-diff policy packet resource is invalid")
    if (
        offset < 0
        or limit < 1
        or limit
        > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_MAX_LIMIT
    ):
        raise ValidationError("packet-diff policy packet paging is invalid")
    raw = _read_packet(value)
    verification = (
        verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(
            raw
        )
    )
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
        rows = [
            _strict_json_loads(
                members[
                    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_MANIFEST
                ].decode(_UTF8)
            )
        ]
    elif resource == "packet-diff":
        rows = [
            load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff(
                members[
                    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_DIFF
                ]
            ).to_dict()
        ]
    elif resource == "policy-gate":
        rows = [
            load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_gate(
                members[
                    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_GATE
                ]
            ).to_dict()
        ]
    elif resource == "policy-audit":
        rows = [
            load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit(
                members[
                    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_AUDIT
                ]
            ).to_dict()
        ]
    else:
        rows = [
            {
                "markdown": members[
                    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_REVIEW
                ].decode(_UTF8)
            }
        ]
    body = {
        "packet_address": verification.packet_address,
        "packet_diff_address": verification.packet_diff_address,
        "policy_gate_address": verification.policy_gate_address,
        "policy_audit_address": verification.policy_audit_address,
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


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_csv(
    value: bytes | bytearray | str | Path,
    *,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_DEFAULT_LIMIT,
) -> str:
    result = (
        query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(
            value, resource="members", offset=offset, limit=limit
        )
    )
    output = io.StringIO(newline="")
    fields = ("name", "byte_count", "byte_address")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(result["items"])
    return output.getvalue()


def render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_markdown(
    value: bytes | bytearray | str | Path,
) -> str:
    diff, gate, audit, review = (
        load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(
            value
        )
    )
    del review
    return _review_markdown(diff, gate, audit)


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_json(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacket,
) -> str:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_value(
        value
    )
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_VERSION,
        "boundary": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_BOUNDARY,
        "format": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_FORMAT,
        "members": [
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_MANIFEST,
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_DIFF,
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_GATE,
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_AUDIT,
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_REVIEW,
        ],
        "resources": [
            "members",
            "summary",
            "manifest",
            "packet-diff",
            "policy-gate",
            "policy-audit",
            "review",
        ],
        "blocked_gate_preserved": True,
        "independent_audit_required": True,
        "source_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_capabilities() -> (
    dict[str, Any]
):
    operations = (
        "build_packet",
        "verify_zip",
        "verify_exact_allowlist",
        "verify_manifest",
        "verify_packet_diff",
        "verify_policy_gate",
        "verify_policy_audit",
        "verify_address_lineage",
        "verify_member_bytes",
        "verify_nested_canonical_bytes",
        "verify_review_replay",
        "verify_public_boundary",
        "preserve_blocked_gate_evidence",
        "load_source_free",
        "query_members",
        "query_packet_diff",
        "query_policy_gate",
        "query_policy_audit",
        "query_review",
        "export_exact_bytes",
        "export_json",
        "export_csv",
        "render_markdown",
    )
    return {
        "version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "source_free": True,
        "read_only": True,
    }


__all__ = [
    "build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet",
    "load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet",
    "module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_bytes",
    "module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_capabilities",
    "module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_csv",
    "module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_json",
    "module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_schema",
    "query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet",
    "render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_markdown",
    "verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet",
    "verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_value",
    "write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet",
]
