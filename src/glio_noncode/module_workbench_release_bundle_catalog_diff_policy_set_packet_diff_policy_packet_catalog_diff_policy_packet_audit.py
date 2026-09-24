"""Independently audit portable catalog-diff policy review packets."""

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
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_json,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy import (
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_json,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit import (
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit_json,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet import (
    _PACKET_PREFIX,
    load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet,
    query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet,
    render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_markdown,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit_contracts import *
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_contracts import *
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_contracts import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacket,
    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_verification,
)
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash, hash_bytes

_UTF8 = "utf-8"
_MAX_JSON_BYTES = 16 * 1024 * 1024
_FIXED_ATTRIBUTES = 0o100644 << 16
_MEMBER_PREFIX = _PACKET_PREFIX + "-member-bytes"


def _raw(value: Any) -> bytes:
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
    elif isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacket):
        raw = value.packet_bytes
    else:
        raw = read_bytes(value, field="catalog-diff policy packet audit", max_bytes=MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_MAX_BYTES)
    if len(raw) > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_MAX_BYTES:
        raise ValidationError("catalog-diff policy packet audit input exceeds byte limit")
    return raw


def _parts(raw: bytes) -> tuple[tuple[zipfile.ZipInfo, bytes], ...]:
    try:
        with zipfile.ZipFile(io.BytesIO(raw), mode="r") as archive:
            return tuple((info, archive.read(info)) for info in archive.infolist())
    except (OSError, KeyError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise ValidationError(f"cannot read catalog-diff policy packet audit ZIP: {exc}") from exc


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> Any:
    body = {"check_id": check_id, "passed": bool(passed), "observed": observed, "required": required, "detail": detail}
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketAuditCheck(**body, content_address="pending")
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketAuditCheck(**body, content_address=address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit_check(provisional))


def _receipt(packet_id: str, packet_address: str, entry_count: int, verification_address: str, checks: list[Any]) -> Any:
    ordered = tuple(sorted(checks, key=lambda item: item.check_id))
    body = {"packet_id": packet_id or "unavailable", "packet_address": packet_address or "unavailable", "entry_count": entry_count, "verification_address": verification_address or "unavailable", "checks": ordered, "accepted": bool(ordered) and all(item.passed for item in ordered)}
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketAudit(**body, content_address="pending")
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketAudit(**body, content_address=address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit(provisional))


def audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(value: Any) -> Any:
    """Recompute transport, member, lineage, nested, and public invariants."""
    try:
        raw = _raw(value)
        parts = _parts(raw)
        infos = tuple(info for info, _payload in parts)
        bodies = {info.filename: payload for info, payload in parts}
        expected = (MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_MANIFEST, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_DIFF, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_GATE, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_AUDIT, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_REVIEW)
        manifest = _strict_json_loads(bodies[expected[0]].decode(_UTF8))
        if not isinstance(manifest, Mapping):
            raise ValidationError("catalog-diff policy packet manifest is not an object")
        diff, gate, policy_audit, review = load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(raw)
        verification = verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(raw)
        packet_address = hash_bytes(raw, prefix=_PACKET_PREFIX)
        descriptors = tuple(manifest.get("members", ()))
        member_replay = all(isinstance(item, Mapping) and item.get("relative_path") in bodies and item.get("byte_count") == len(bodies[item.get("relative_path")]) and item.get("byte_address") == hash_bytes(bodies[item.get("relative_path")], prefix=_MEMBER_PREFIX) for item in descriptors)
        nested_canonical = bodies[expected[1]] == module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_json(diff).encode(_UTF8) and bodies[expected[2]] == module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_json(gate).encode(_UTF8) and bodies[expected[3]] == module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit_json(policy_audit).encode(_UTF8)
        review_replay = bodies[expected[4]].decode(_UTF8) == render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_markdown(raw)
        checks = [_check("audit-address-replay", address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_verification(verification) == verification.content_address, verification.content_address, "replayable", "verification address is independently recomputable"), _check("audit-admission", verification.accepted, verification.accepted, True, "packet verification must be accepted before audit admission"), _check("canonical-members", bodies[expected[0]] == (canonical_json(manifest) + "\n").encode(_UTF8) and tuple(info.filename for info in infos) == expected, tuple(info.filename for info in infos), expected, "ZIP member order and manifest bytes are canonical"), _check("fixed-metadata", all(info.date_time == (1980, 1, 1, 0, 0, 0) and info.compress_type == zipfile.ZIP_STORED and info.external_attr == _FIXED_ATTRIBUTES for info in infos), "fixed" if all(info.date_time == (1980, 1, 1, 0, 0, 0) and info.compress_type == zipfile.ZIP_STORED and info.external_attr == _FIXED_ATTRIBUTES for info in infos) else "drift", "fixed", "ZIP metadata is deterministic"), _check("member-count-conservation", len(infos) == MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_MAX_ENTRIES and verification.entry_count == len(infos), len(infos), MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_MAX_ENTRIES, "transport entry count conserves the exact packet contract"), _check("member-descriptor-replay", len(descriptors) == len(expected) - 1 and member_replay, len(descriptors), len(expected) - 1, "manifest member descriptors replay payload byte counts and addresses"), _check("member-order-replay", tuple((item.get("ordinal"), item.get("relative_path")) for item in descriptors if isinstance(item, Mapping)) == tuple((index, name) for index, name in enumerate(expected[1:], 1)), tuple((item.get("ordinal"), item.get("relative_path")) for item in descriptors if isinstance(item, Mapping)), tuple((index, name) for index, name in enumerate(expected[1:], 1)), "manifest ordinals and paths are conserved"), _check("nested-address-lineage", manifest.get("catalog_diff_address") == diff.content_address and manifest.get("policy_gate_address") == gate.content_address and manifest.get("policy_audit_address") == policy_audit.content_address and verification.catalog_diff_address == diff.content_address and verification.policy_gate_address == gate.content_address and verification.policy_audit_address == policy_audit.content_address, "conserved", "conserved", "nested and verification addresses agree"), _check("nested-canonical-bytes", nested_canonical, "canonical" if nested_canonical else "drift", "canonical", "nested public JSON members reload to exact canonical bytes"), _check("nested-audit-admission", policy_audit.accepted, policy_audit.accepted, True, "independent nested policy audit is accepted"), _check("review-replay", review_replay, "replayed" if review_replay else "drift", "replayed", "review Markdown regenerates exactly"), _check("packet-byte-address", packet_address == verification.packet_address, packet_address, verification.packet_address, "packet bytes retain their deterministic address"), _check("query-conservation", query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(raw, resource="members")["total"] == len(expected), len(expected), len(expected), "member query reports every packet member"), _check("public-boundary", not _has_forbidden_key({"manifest": manifest, "diff": diff.to_dict(), "gate": gate.to_dict(), "audit": policy_audit.to_dict(), "verification": verification.to_dict()}), "clean", "clean", "packet audit projection contains only public aggregate evidence")]
        return _receipt(str(manifest.get("packet_id", "")), packet_address, len(infos), verification.content_address, checks)
    except (KeyError, UnicodeDecodeError, ValueError, ValidationError, zipfile.BadZipFile) as exc:
        return _receipt("unavailable", "unavailable", 0, "unavailable", [_check("input-readable", False, str(exc), "readable and canonical", "catalog-diff policy packet audit input could not be loaded")])


def verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit(value: Any) -> Any:
    if not isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketAudit):
        raise ValidationError("catalog-diff policy packet audit verification requires a typed audit")
    for check in value.checks:
        if address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit_check(check) != check.content_address:
            raise ValidationError(f"catalog-diff policy packet audit check address mismatch: {check.check_id}")
    if address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit(value) != value.content_address:
        raise ValidationError("catalog-diff policy packet audit address mismatch")
    return value


def _tupleize(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_tupleize(item) for item in value)
    if isinstance(value, Mapping):
        return {str(key): _tupleize(item) for key, item in value.items()}
    return value


def _check_from_mapping(value: Mapping[str, Any]) -> Any:
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketAuditCheck(check_id=str(value.get("check_id", "")), passed=value.get("passed"), observed=_tupleize(value.get("observed")), required=_tupleize(value.get("required")), detail=str(value.get("detail", "")), content_address=str(value.get("content_address", "")))


def _audit_from_mapping(value: Mapping[str, Any]) -> Any:
    raw_checks = value.get("checks")
    if not isinstance(raw_checks, list) or any(not isinstance(item, Mapping) for item in raw_checks):
        raise ValidationError("catalog-diff policy packet audit checks are invalid")
    result = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketAudit(packet_id=str(value.get("packet_id", "")), packet_address=str(value.get("packet_address", "")), entry_count=value.get("entry_count"), verification_address=str(value.get("verification_address", "")), checks=tuple(_check_from_mapping(item) for item in raw_checks), accepted=value.get("accepted"), content_address=str(value.get("content_address", "")))
    return verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit(result)


def load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit(value: bytes | bytearray | str | Path | Mapping[str, Any]) -> Any:
    if isinstance(value, Mapping):
        return _audit_from_mapping(value)
    raw = bytes(value) if isinstance(value, (bytes, bytearray)) else read_bytes(value, field="catalog-diff policy packet audit", max_bytes=_MAX_JSON_BYTES)
    try:
        parsed = _strict_json_loads(raw.decode(_UTF8))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValidationError(f"cannot parse catalog-diff policy packet audit: {exc}") from exc
    if not isinstance(parsed, Mapping) or raw != (canonical_json(parsed) + "\n").encode(_UTF8):
        raise ValidationError("catalog-diff policy packet audit must be canonical JSON object")
    return _audit_from_mapping(parsed)


def build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit_from_path(value: str | Path) -> Any:
    return audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(value)


def query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit(value: bytes | bytearray | str | Path | Mapping[str, Any], *, passed: bool | None = None, text: str | None = None, offset: int = 0, limit: int = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_AUDIT_DEFAULT_LIMIT) -> dict[str, Any]:
    if offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_AUDIT_MAX_LIMIT:
        raise ValidationError("catalog-diff policy packet audit paging is invalid")
    audit = value if isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketAudit) else load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit(value)
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit(audit)
    rows = list(audit.checks)
    if passed is not None:
        rows = [item for item in rows if item.passed is passed]
    if text:
        rows = [item for item in rows if text.casefold() in canonical_json(item.to_dict()).casefold()]
    body = {"packet_id": audit.packet_id, "packet_address": audit.packet_address, "audit_address": audit.content_address, "passed": passed, "text": text, "total": len(rows), "offset": offset, "limit": limit, "items": [item.to_dict() for item in rows[offset:offset + limit]], "accepted": audit.accepted}
    return body | {"content_address": content_hash(body, prefix="module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet-catalog-diff-policy-packet-audit-query")}


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit_json(value: Any) -> str:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit(value)
    return canonical_json(value.to_dict()) + "\n"


def write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit(value: Any, destination: str | Path, *, allow_existing: bool = False) -> Any:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("catalog-diff policy packet audit destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("catalog-diff policy packet audit destination is not a file")
    _validate_parent(path.parent, "catalog-diff policy packet audit destination")
    atomic_write_bytes(path, module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit_json(value).encode(_UTF8), field="catalog-diff policy packet audit destination")
    return value


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit_csv(value: Any, *, passed: bool | None = None, text: str | None = None, offset: int = 0, limit: int = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_AUDIT_DEFAULT_LIMIT) -> str:
    result = query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit(value, passed=passed, text=text, offset=offset, limit=limit)
    output = io.StringIO(newline="")
    fields = ("check_id", "passed", "observed", "required", "detail", "content_address")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(result["items"])
    return output.getvalue()


def render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit_markdown(value: Any) -> str:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit(value)
    lines = ["# Catalog Diff Policy Packet Audit", "", f"- Packet: `{value.packet_id}`", f"- Packet address: `{value.packet_address}`", f"- Accepted: **{str(value.accepted).lower()}**", f"- Passed / failed: **{value.passed_count} / {value.failed_count}**", "", "| Check | Passed | Detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | {str(item.passed).lower()} | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit_schema() -> dict[str, Any]:
    return {"version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_AUDIT_VERSION, "boundary": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_AUDIT_BOUNDARY, "maximum_checks": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_AUDIT_MAX_CHECKS, "independent": True, "source_free": True, "recomputes": ["ZIP members", "fixed metadata", "member descriptors", "nested lineage", "review replay", "public boundary"]}


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit_capabilities() -> dict[str, Any]:
    operations = ("audit_packet_transport", "audit_fixed_metadata", "audit_member_descriptors", "audit_nested_lineage", "audit_review_replay", "audit_public_boundary", "load_source_free", "query_checks", "export_json", "export_csv", "render_markdown")
    return {"version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_POLICY_PACKET_AUDIT_VERSION, "operation_count": len(operations), "operations": list(operations), "deterministic": True, "independent": True, "source_free": True, "read_only": True}


__all__ = [name for name in globals() if name.startswith("audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet") or name.startswith("build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit") or name.startswith("load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit") or name.startswith("module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit") or name.startswith("query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit") or name.startswith("render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit") or name.startswith("verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit") or name.startswith("write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit")]
