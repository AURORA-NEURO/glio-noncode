"""Build, verify, reload, and query packet-catalog diff review packets."""

# ruff: noqa: E501, F403, F405

from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._safe_persistence import _validate_parent, atomic_write_bytes, read_bytes
from .errors import ValidationError
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff import (
    load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_json,
    render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_markdown,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_contracts import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiff,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy import (
    load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_gate,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_json,
    render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_markdown,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_gate,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit import (
    load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit_json,
    render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit_markdown,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit_contracts import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyAudit,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_contracts import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyGate,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_contracts import *
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash, hash_bytes

_UTF8 = "utf-8"
_MAX_JSON_BYTES = 16 * 1024 * 1024
_PACKET_PREFIX = "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet-catalog-diff-policy-packet"
_MEMBER_PREFIX = _PACKET_PREFIX + "-member-bytes"


def _safe_member(value: str) -> bool:
    return isinstance(value, str) and bool(value) and "\\" not in value and ":" not in value and "\x00" not in value and not value.startswith("/") and all(part not in {"", ".", ".."} for part in value.split("/"))


def _zip_member(name: str) -> zipfile.ZipInfo:
    allowed = {MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_MANIFEST, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_DIFF, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_GATE, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_AUDIT, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_REVIEW}
    if name not in allowed:
        raise ValidationError(f"unsafe catalog-diff policy packet member: {name}")
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 0
    info.create_version = 20
    info.extract_version = 20
    info.flag_bits = 0
    info.external_attr = 0o100644 << 16
    info.extra = b""
    info.comment = b""
    return info


def _read_packet(value: bytes | bytearray | str | Path) -> bytes:
    raw = bytes(value) if isinstance(value, (bytes, bytearray)) else read_bytes(value, field="catalog-diff policy packet", max_bytes=MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_MAX_BYTES)
    if len(raw) > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_MAX_BYTES:
        raise ValidationError("catalog-diff policy packet exceeds byte limit")
    return raw


def _member(member_id: str, path: str, media_type: str, ordinal: int, payload: bytes) -> Any:
    body = {"member_id": member_id, "relative_path": path, "media_type": media_type, "ordinal": ordinal, "byte_count": len(payload), "byte_address": hash_bytes(payload, prefix=_MEMBER_PREFIX)}
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketMember(**body, content_address="pending")
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketMember(**body, content_address=address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_member(provisional))


def _review(diff: Any, gate: Any, audit: Any) -> str:
    diff = load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff(module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_json(diff).encode(_UTF8))
    gate = load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_gate(module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_json(gate).encode(_UTF8))
    audit = load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit(module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit_json(audit).encode(_UTF8))
    lines = ["# Packet Catalog Diff Policy Review Packet", "", f"- Catalog diff: `{diff.content_address}`", f"- Policy gate: `{gate.content_address}`", f"- Independent audit: `{audit.content_address}`", f"- Direction: **{diff.direction.value}**", f"- State transition: **{diff.state_transition.value}**", f"- Policy accepted: **{str(gate.accepted).lower()}**", f"- Audit accepted: **{str(audit.accepted).lower()}**", "", "This packet is source-free, payload-free, timestamp-free, and deterministic.", "A blocked policy decision is retained as review evidence; packet admission requires the independent audit to pass.", "", "## Catalog comparison", "", *render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_markdown(diff).splitlines(), "", "## Policy decision", "", *render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_markdown(gate).splitlines(), "", "## Independent audit", "", *render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit_markdown(audit).splitlines()]
    return "\n".join(lines) + "\n"


def _manifest(packet_id: str, diff: Any, gate: Any, audit: Any, members: tuple[Any, ...]) -> bytes:
    body = {"version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_VERSION, "boundary": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_BOUNDARY, "packet_format": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_FORMAT, "packet_id": packet_id, "catalog_diff_address": diff.content_address, "policy_gate_address": gate.content_address, "policy_audit_address": audit.content_address, "members": [item.to_dict() for item in members if item.ordinal > 0]}
    return (canonical_json(body) + "\n").encode(_UTF8)


def _zip_bytes(payloads: tuple[tuple[str, bytes], ...]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_STORED, allowZip64=False) as handle:
        for name, payload in payloads:
            handle.writestr(_zip_member(name), payload)
    return output.getvalue()


def build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(diff: Any, gate: Any, audit: Any, *, packet_id: str = "glio-noncode-module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet-catalog-diff-policy-packet") -> Any:
    if not isinstance(diff, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiff) or not isinstance(gate, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyGate) or not isinstance(audit, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyAudit):
        raise ValidationError("catalog-diff policy packet requires typed diff, gate, and audit")
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff(diff)
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_gate(gate)
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit(audit)
    if gate.diff_address != diff.content_address or audit.diff_address != diff.content_address or audit.policy_gate_address != gate.content_address:
        raise ValidationError("catalog-diff policy packet lineage does not conserve addresses")
    if not audit.accepted:
        raise ValidationError("catalog-diff policy packet requires an accepted independent audit")
    diff_bytes = module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_json(diff).encode(_UTF8)
    gate_bytes = module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_json(gate).encode(_UTF8)
    audit_bytes = module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit_json(audit).encode(_UTF8)
    review_bytes = _review(diff, gate, audit).encode(_UTF8)
    payload_members = (_member("catalog-diff", MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_DIFF, "application/json", 1, diff_bytes), _member("policy-gate", MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_GATE, "application/json", 2, gate_bytes), _member("policy-audit", MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_AUDIT, "application/json", 3, audit_bytes), _member("review", MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_REVIEW, "text/markdown", 4, review_bytes))
    manifest_bytes = _manifest(packet_id, diff, gate, audit, payload_members)
    raw = _zip_bytes(((MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_MANIFEST, manifest_bytes), (MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_DIFF, diff_bytes), (MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_GATE, gate_bytes), (MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_AUDIT, audit_bytes), (MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_REVIEW, review_bytes)))
    if len(raw) > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_MAX_BYTES:
        raise ValidationError("catalog-diff policy packet exceeds byte limit")
    members = (_member("manifest", MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_MANIFEST, "application/json", 0, manifest_bytes), *payload_members)
    body = {"packet_id": packet_id, "catalog_diff_address": diff.content_address, "policy_gate_address": gate.content_address, "policy_audit_address": audit.content_address, "packet_address": hash_bytes(raw, prefix=_PACKET_PREFIX), "packet_byte_count": len(raw), "members": members, "packet_bytes": raw}
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacket(**body, content_address="pending")
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacket(**body, content_address=address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(provisional))


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_bytes(value: Any) -> bytes:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_value(value)
    return value.packet_bytes


def verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_value(value: Any) -> Any:
    if not isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacket):
        raise ValidationError("typed catalog-diff policy packet verification requires a packet")
    if address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(value) != value.content_address:
        raise ValidationError("catalog-diff policy packet address mismatch")
    if hash_bytes(value.packet_bytes, prefix=_PACKET_PREFIX) != value.packet_address:
        raise ValidationError("catalog-diff policy packet byte address mismatch")
    return value


def write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(value: Any, destination: str | Path, *, allow_existing: bool = False) -> Any:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_value(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("catalog-diff policy packet destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("catalog-diff policy packet destination is not a file")
    _validate_parent(path.parent, "catalog-diff policy packet destination")
    atomic_write_bytes(path, value.packet_bytes, field="catalog-diff policy packet destination")
    return value


def _zip_payloads(raw: bytes) -> tuple[tuple[zipfile.ZipInfo, bytes], ...]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw), mode="r") as handle:
            return tuple((info, handle.read(info)) for info in handle.infolist())
    except (OSError, KeyError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise ValidationError(f"cannot read catalog-diff policy packet ZIP: {exc}") from exc


def _check(check_id: str, plane: Any, passed: bool, observed: Any, required: Any, detail: str) -> Any:
    body = {"check_id": check_id, "plane": plane, "passed": bool(passed), "observed": observed, "required": required, "detail": detail}
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketCheck(**body, content_address="pending")
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketCheck(**body, content_address=address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_check(provisional))


def _verification(packet_id: str, packet_address: str, diff_address: str, gate_address: str, audit_address: str, entry_count: int, checks: list[Any]) -> Any:
    ordered = tuple(sorted(checks, key=lambda item: item.check_id))
    body = {"packet_id": packet_id or "unavailable", "packet_address": packet_address or "unavailable", "catalog_diff_address": diff_address or "unavailable", "policy_gate_address": gate_address or "unavailable", "policy_audit_address": audit_address or "unavailable", "entry_count": entry_count, "present_count": entry_count, "missing_count": 0, "checks": ordered, "accepted": bool(ordered) and all(item.passed for item in ordered)}
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketVerification(**body, content_address="pending")
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketVerification(**body, content_address=address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_verification(provisional))


def verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(value: Any) -> Any:
    try:
        raw = value.packet_bytes if isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacket) else _read_packet(value)
        payloads = _zip_payloads(raw)
        infos = tuple(info for info, _payload in payloads)
        bodies = {info.filename: payload for info, payload in payloads}
        expected = (MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_MANIFEST, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_DIFF, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_GATE, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_AUDIT, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_REVIEW)
        manifest = _strict_json_loads(bodies[expected[0]].decode(_UTF8))
        if not isinstance(manifest, Mapping) or bodies[expected[0]] != (canonical_json(manifest) + "\n").encode(_UTF8):
            raise ValidationError("manifest is not canonical")
        diff = load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff(bodies[expected[1]])
        gate = load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_gate(bodies[expected[2]])
        audit = load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit(bodies[expected[3]])
        expected_members = tuple(manifest.get("members", ()))
        fixed_attributes = 0o100644 << 16
        fixed_metadata = all(info.date_time == (1980, 1, 1, 0, 0, 0) and info.compress_type == zipfile.ZIP_STORED and info.external_attr == fixed_attributes for info in infos)
        checks = [_check("zip-members", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketCheckPlane.ZIP, tuple(info.filename for info in infos) == expected, [info.filename for info in infos], expected, "ZIP members are exactly the canonical five entries"), _check("safe-paths", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketCheckPlane.PATH, all(_safe_member(info.filename) for info in infos), [info.filename for info in infos if not _safe_member(info.filename)], [], "member paths are safe relative paths"), _check("fixed-metadata", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketCheckPlane.ZIP, fixed_metadata, "fixed" if fixed_metadata else "drift", "fixed", "ZIP metadata is deterministic"), _check("manifest-lineage", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketCheckPlane.MANIFEST, manifest.get("catalog_diff_address") == diff.content_address and manifest.get("policy_gate_address") == gate.content_address and manifest.get("policy_audit_address") == audit.content_address, {"catalog_diff_address": manifest.get("catalog_diff_address"), "policy_gate_address": manifest.get("policy_gate_address"), "policy_audit_address": manifest.get("policy_audit_address")}, "nested addresses", "manifest retains all nested addresses"), _check("nested-lineage", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketCheckPlane.DIFF, gate.diff_address == diff.content_address and audit.diff_address == diff.content_address and audit.policy_gate_address == gate.content_address, "conserved" if gate.diff_address == diff.content_address and audit.diff_address == diff.content_address and audit.policy_gate_address == gate.content_address else "drift", "conserved", "nested diff, gate, and audit addresses agree"), _check("audit-admission", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketCheckPlane.AUDIT, audit.accepted, audit.accepted, True, "independent audit must be accepted for packet admission"), _check("member-descriptors", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketCheckPlane.MANIFEST, len(expected_members) == 4 and all(isinstance(item, Mapping) for item in expected_members), len(expected_members), 4, "manifest describes the four payload members"), _check("review-replay", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketCheckPlane.REVIEW, bodies[expected[4]].decode(_UTF8) == _review(diff, gate, audit), "replayed" if bodies[expected[4]].decode(_UTF8) == _review(diff, gate, audit) else "drift", "replayed", "review Markdown regenerates exactly"), _check("public-boundary", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketCheckPlane.PUBLIC, not _has_forbidden_key({"manifest": manifest, "diff": diff.to_dict(), "gate": gate.to_dict(), "audit": audit.to_dict()}), "clean", "clean", "packet contains only public aggregate evidence"), _check("packet-address", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketCheckPlane.BYTES, True, hash_bytes(raw, prefix=_PACKET_PREFIX), "replayable", "packet bytes have a deterministic address")]
        checks = checks
        return _verification(str(manifest.get("packet_id", "")), hash_bytes(raw, prefix=_PACKET_PREFIX), diff.content_address, gate.content_address, audit.content_address, len(expected), checks)
    except (KeyError, UnicodeDecodeError, ValueError, ValidationError, zipfile.BadZipFile) as exc:
        return _verification("unavailable", "unavailable", "unavailable", "unavailable", "unavailable", 0, [_check("input-readable", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketCheckPlane.ZIP, False, str(exc), "readable and canonical", "catalog-diff policy packet input could not be loaded")])


def load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(value: bytes | bytearray | str | Path) -> tuple[Any, Any, Any, str]:
    raw = _read_packet(value)
    payloads = dict((info.filename, payload) for info, payload in _zip_payloads(raw))
    names = (MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_DIFF, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_GATE, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_AUDIT, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_REVIEW)
    if any(name not in payloads for name in names):
        raise ValidationError("catalog-diff policy packet members are incomplete")
    verification = verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(raw)
    if not verification.accepted:
        raise ValidationError("catalog-diff policy packet verification failed")
    return (load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff(payloads[names[0]]), load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_gate(payloads[names[1]]), load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit(payloads[names[2]]), payloads[names[3]].decode(_UTF8))


def query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(value: Any, *, resource: str = "summary", offset: int = 0, limit: int = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_DEFAULT_LIMIT) -> dict[str, Any]:
    if resource not in {"members", "summary", "catalog-diff", "policy-gate", "policy-audit", "review"} or offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_MAX_LIMIT:
        raise ValidationError("catalog-diff policy packet query is invalid")
    if isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacket):
        verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_value(value)
        raw = value.packet_bytes
    else:
        raw = _read_packet(value)
        verification = verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(raw)
        if not verification.accepted:
            raise ValidationError("catalog-diff policy packet verification failed")
    payloads = dict((info.filename, payload) for info, payload in _zip_payloads(raw))
    if resource == "summary":
        body = {"resource": resource, "packet_address": hash_bytes(raw, prefix=_PACKET_PREFIX), "packet_byte_count": len(raw), "member_count": len(payloads), "accepted": True}
    elif resource == "members":
        rows = [{"relative_path": name, "byte_count": len(payload), "byte_address": hash_bytes(payload, prefix=_MEMBER_PREFIX)} for name, payload in payloads.items()]
        body = {"resource": resource, "total": len(rows), "offset": offset, "limit": limit, "items": rows[offset:offset + limit]}
    elif resource == "review":
        body = {"resource": resource, "text": payloads[MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_REVIEW].decode(_UTF8)}
    else:
        diff, gate, audit, review = load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(raw)
        selected = {"catalog-diff": diff.to_dict(), "policy-gate": gate.to_dict(), "policy-audit": audit.to_dict()}[resource]
        body = {"resource": resource, "item": selected}
    return body | {"content_address": content_hash(body, prefix="module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet-catalog-diff-policy-packet-query")}


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_json(value: Any) -> str:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_value(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_csv(value: Any, *, resource: str = "members", offset: int = 0, limit: int = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_DEFAULT_LIMIT) -> str:
    result = query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(value, resource=resource, offset=offset, limit=limit)
    rows = result.get("items", [])
    output = io.StringIO(newline="")
    fields = tuple(sorted({key for row in rows for key in row})) if rows else ("resource", "content_address")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_markdown(value: Any) -> str:
    diff, gate, audit, review = load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(value.packet_bytes if isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacket) else value)
    return review


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_schema() -> dict[str, Any]:
    return {"version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_VERSION, "boundary": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_BOUNDARY, "format": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_FORMAT, "members": [MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_MANIFEST, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_DIFF, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_GATE, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_AUDIT, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_REVIEW], "max_bytes": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_MAX_BYTES, "source_free": True, "path_free": True, "timestamp_free": True, "payload_free": True}


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_capabilities() -> dict[str, Any]:
    operations = ("build_zip", "verify_zip", "load_nested_diff", "load_nested_policy_gate", "load_nested_policy_audit", "query_members", "query_summary", "query_review", "export_json", "export_csv", "export_markdown", "verify_addresses", "verify_lineage", "verify_fixed_metadata")
    return {"version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_VERSION, "operation_count": len(operations), "operations": list(operations), "deterministic": True, "source_free": True, "payload_free": True, "read_only": True}


__all__ = [name for name in globals() if name.startswith("build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet") or name.startswith("load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet") or name.startswith("module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet") or name.startswith("query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet") or name.startswith("render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet") or name.startswith("verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet") or name.startswith("write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet")]
