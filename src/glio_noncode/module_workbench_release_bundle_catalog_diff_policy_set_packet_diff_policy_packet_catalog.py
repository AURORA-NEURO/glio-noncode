"""Build, verify, persist, and query a source-free packet review catalog."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ._safe_persistence import _validate_parent, atomic_write_bytes, read_bytes
from .errors import ValidationError
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet import (
    load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_value,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_contracts import (
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_BOUNDARY,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DEFAULT_LIMIT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_FORMAT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_MAX_BYTES,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_MAX_CHECKS,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_MAX_ENTRIES,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_MAX_LIMIT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_PREFIX,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_VERSION,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalog,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheck,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheckPlane,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogEntry,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogState,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogVerification,
    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog,
    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_check,
    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_entry,
    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_verification,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_contracts import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacket,
)
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

_UTF8 = "utf-8"


def _read_catalog(value: bytes | bytearray | str | Path) -> bytes:
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
    elif isinstance(value, (str, Path)):
        raw = read_bytes(
            value,
            field="packet review catalog",
            max_bytes=MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_MAX_BYTES,
        )
    else:
        raise ValidationError("packet review catalog input must be bytes or a path")
    if len(raw) > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_MAX_BYTES:
        raise ValidationError("packet review catalog exceeds byte limit")
    return raw


def _document(body: Mapping[str, Any]) -> bytes:
    return (canonical_json(body) + "\n").encode(_UTF8)


def _logical_body(body: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(body)
    for key in ("catalog_address", "catalog_byte_count", "content_address"):
        result.pop(key, None)
    return result


def _entry(
    ordinal: int,
    verification: Any,
    gate: Any,
    audit: Any,
    packet_byte_count: int,
    member_count: int,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogEntry:
    body = {
        "packet_id": verification.packet_id,
        "packet_address": verification.packet_address,
        "packet_content_address": verification.content_address,
        "packet_diff_address": verification.packet_diff_address,
        "policy_gate_address": verification.policy_gate_address,
        "policy_audit_address": verification.policy_audit_address,
        "packet_byte_count": packet_byte_count,
        "member_count": member_count,
        "verification_entry_count": verification.entry_count,
        "verification_check_count": len(verification.checks),
        "verification_failed_count": verification.failed_count,
        "policy_gate_accepted": gate.accepted,
        "policy_audit_accepted": audit.accepted,
        "packet_accepted": verification.accepted,
        "ordinal": ordinal,
        "state": (
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogState.ACCEPTED
            if verification.accepted
            else ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogState.BLOCKED
        ),
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogEntry(
        **body, content_address="pending"
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogEntry(
        **body,
        content_address=address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_entry(
            provisional
        ),
    )


def _verified_packet(
    value: Any,
) -> tuple[
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogEntry,
    Any,
    Any,
    Any,
]:
    if isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacket):
        verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_value(
            value
        )
        raw = value.packet_bytes
    else:
        raw = _read_packet_reference(value)
    verification = verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(
        raw
    )
    if not verification.accepted:
        raise ValidationError("packet catalog requires structurally accepted packets")
    _diff, gate, audit, _review = load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(
        raw
    )
    entry = _entry(
        0,
        verification,
        gate,
        audit,
        len(raw),
        verification.entry_count,
    )
    return entry, verification, gate, audit


def _read_packet_reference(value: Any) -> bytes:
    if isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacket):
        return value.packet_bytes
    if isinstance(value, (bytes, bytearray, str, Path)):
        return bytes(value) if isinstance(value, (bytes, bytearray)) else read_bytes(
            value,
            field="packet review packet",
            max_bytes=MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_MAX_BYTES,
        )
    raise ValidationError("packet catalog entries must be packet bytes, paths, or typed packets")


def build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog(
    packets: Sequence[Any],
    *,
    catalog_id: str = (
        "glio-noncode-module-workbench-release-bundle-catalog-diff-policy-set-"
        "packet-diff-policy-packet-catalog"
    ),
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalog:
    """Aggregate verified packet descriptors without retaining packet ZIP payloads."""

    if not isinstance(catalog_id, str) or not catalog_id.strip():
        raise ValidationError("packet review catalog ID is required")
    if isinstance(packets, (str, bytes, bytearray)) or not isinstance(packets, Sequence):
        raise ValidationError("packet review catalog packets must be a sequence")
    maximum = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_MAX_ENTRIES
    if not packets or len(packets) > maximum:
        raise ValidationError("packet review catalog packet count is outside the supported range")
    loaded = tuple(_verified_packet(value) for value in packets)
    raw_entries = tuple(item[0] for item in loaded)
    packet_ids = tuple(item.packet_id for item in raw_entries)
    packet_addresses = tuple(item.packet_address for item in raw_entries)
    if len(set(packet_ids)) != len(packet_ids):
        raise ValidationError("packet review catalog packet IDs must be unique")
    if len(set(packet_addresses)) != len(packet_addresses):
        raise ValidationError("packet review catalog packet addresses must be unique")
    entries = tuple(
        _entry(index, verification, gate, audit, len(_read_packet_reference(value)), verification.entry_count)
        for index, (value, (_unused, verification, gate, audit)) in enumerate(
            zip(packets, loaded, strict=True)
        )
    )
    accepted_count = sum(item.packet_accepted for item in entries)
    blocked_count = len(entries) - accepted_count
    gate_blocked_count = sum(not item.policy_gate_accepted for item in entries)
    audit_rejected_count = sum(not item.policy_audit_accepted for item in entries)
    accepted = blocked_count == 0
    state = (
        ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogState.ACCEPTED
        if accepted
        else ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogState.BLOCKED
    )
    body: dict[str, Any] = {
        "catalog_id": catalog_id,
        "version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_VERSION,
        "boundary": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_BOUNDARY,
        "catalog_format": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_FORMAT,
        "catalog_address": "pending",
        "catalog_byte_count": 0,
        "total_packet_bytes": sum(item.packet_byte_count for item in entries),
        "entry_count": len(entries),
        "accepted_count": accepted_count,
        "blocked_count": blocked_count,
        "policy_gate_blocked_count": gate_blocked_count,
        "policy_audit_rejected_count": audit_rejected_count,
        "entries": entries,
        "state": state,
        "accepted": accepted,
        "content_address": "pending",
    }
    body["catalog_address"] = content_hash(
        _logical_body(body),
        prefix=MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_PREFIX,
    )
    for _ in range(8):
        raw = _document(body)
        if len(raw) != body["catalog_byte_count"]:
            body["catalog_byte_count"] = len(raw)
            continue
        provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalog(
            **body, catalog_bytes=raw
        )
        address = address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog(
            provisional
        )
        if body["content_address"] != address:
            body["content_address"] = address
            continue
        return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalog(
            **body, catalog_bytes=raw
        )
    raise ValidationError("packet review catalog address sizing did not converge")


def write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalog,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalog:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_value(
        value
    )
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("packet review catalog destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("packet review catalog destination is not a file")
    _validate_parent(path.parent, "packet review catalog destination")
    atomic_write_bytes(path, value.catalog_bytes, field="packet review catalog destination")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _entry_from_mapping(value: Mapping[str, Any]) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogEntry:
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogEntry(
        packet_id=str(value.get("packet_id", "")),
        packet_address=str(value.get("packet_address", "")),
        packet_content_address=str(value.get("packet_content_address", "")),
        packet_diff_address=str(value.get("packet_diff_address", "")),
        policy_gate_address=str(value.get("policy_gate_address", "")),
        policy_audit_address=str(value.get("policy_audit_address", "")),
        packet_byte_count=value.get("packet_byte_count"),
        member_count=value.get("member_count"),
        verification_entry_count=value.get("verification_entry_count"),
        verification_check_count=value.get("verification_check_count"),
        verification_failed_count=value.get("verification_failed_count"),
        policy_gate_accepted=value.get("policy_gate_accepted"),
        policy_audit_accepted=value.get("policy_audit_accepted"),
        packet_accepted=value.get("packet_accepted"),
        ordinal=value.get("ordinal"),
        state=ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogState(
            str(value.get("state"))
        ),
        content_address=str(value.get("content_address", "")),
    )


def _catalog_from_mapping(
    payload: Mapping[str, Any], raw: bytes
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalog:
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list):
        raise ValidationError("packet review catalog entries are invalid")
    entries = tuple(_entry_from_mapping(_mapping(item, "packet review catalog entry")) for item in raw_entries)
    result = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalog(
        catalog_id=str(payload.get("catalog_id", "")),
        version=str(payload.get("version", "")),
        boundary=str(payload.get("boundary", "")),
        catalog_format=str(payload.get("catalog_format", "")),
        catalog_address=str(payload.get("catalog_address", "")),
        catalog_byte_count=payload.get("catalog_byte_count"),
        total_packet_bytes=payload.get("total_packet_bytes"),
        entry_count=payload.get("entry_count"),
        accepted_count=payload.get("accepted_count"),
        blocked_count=payload.get("blocked_count"),
        policy_gate_blocked_count=payload.get("policy_gate_blocked_count"),
        policy_audit_rejected_count=payload.get("policy_audit_rejected_count"),
        entries=entries,
        state=ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogState(
            str(payload.get("state"))
        ),
        accepted=payload.get("accepted"),
        content_address=str(payload.get("content_address", "")),
        catalog_bytes=raw,
    )
    return result


def _check(
    check_id: str,
    plane: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheck(
        **body, content_address="pending"
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheck(
        **body,
        content_address=address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_check(
            provisional
        ),
    )


def _verification(
    catalog_id: str,
    catalog_address: str,
    entry_count: int,
    accepted_count: int,
    blocked_count: int,
    checks: Sequence[ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheck],
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogVerification:
    ordered = tuple(sorted(checks, key=lambda item: item.check_id))
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogVerification(
        catalog_id=catalog_id,
        catalog_address=catalog_address,
        entry_count=entry_count,
        accepted_count=accepted_count,
        blocked_count=blocked_count,
        checks=ordered,
        accepted=all(item.passed for item in ordered),
        content_address="pending",
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogVerification(
        catalog_id=catalog_id,
        catalog_address=catalog_address,
        entry_count=entry_count,
        accepted_count=accepted_count,
        blocked_count=blocked_count,
        checks=ordered,
        accepted=all(item.passed for item in ordered),
        content_address=address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_verification(
            provisional
        ),
    )


def verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog(
    value: bytes | bytearray | str | Path,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogVerification:
    """Verify canonical catalog structure without reopening any packet ZIP."""

    raw = _read_catalog(value)
    payload: Mapping[str, Any] = {}
    parse_ok = False
    canonical_ok = False
    try:
        parsed = _strict_json_loads(raw.decode(_UTF8))
        if isinstance(parsed, Mapping):
            payload = parsed
            parse_ok = True
            canonical_ok = raw == _document(parsed)
    except (UnicodeDecodeError, ValueError):
        pass
    catalog_id = str(payload.get("catalog_id", "unavailable"))
    catalog_address = str(payload.get("catalog_address", "unavailable"))
    entry_count = payload.get("entry_count", 0)
    if not isinstance(entry_count, int) or isinstance(entry_count, bool) or entry_count < 0:
        entry_count = 0
    entry_count = min(entry_count, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_MAX_ENTRIES)
    raw_entries = payload.get("entries") if isinstance(payload, Mapping) else None
    parsed_entries: tuple[ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogEntry, ...] = ()
    entry_error = ""
    if isinstance(raw_entries, list):
        try:
            parsed_entries = tuple(_entry_from_mapping(_mapping(item, "packet review catalog entry")) for item in raw_entries)
        except (TypeError, ValueError, ValidationError) as exc:
            entry_error = str(exc)
    else:
        entry_error = "entries must be a list"
    accepted_count = payload.get("accepted_count", 0)
    blocked_count = payload.get("blocked_count", 0)
    if not isinstance(accepted_count, int) or isinstance(accepted_count, bool) or accepted_count < 0:
        accepted_count = 0
    if not isinstance(blocked_count, int) or isinstance(blocked_count, bool) or blocked_count < 0:
        blocked_count = 0
    accepted_count = min(accepted_count, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_MAX_ENTRIES)
    blocked_count = min(blocked_count, MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_MAX_ENTRIES)
    checks = [
        _check("canonical-json", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheckPlane.STRUCTURE, canonical_ok, "canonical" if canonical_ok else "noncanonical", "canonical UTF-8 JSON", "catalog bytes use the one canonical JSON representation"),
        _check("catalog-parse", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheckPlane.STRUCTURE, parse_ok, "object" if parse_ok else "invalid", "object", "catalog parses as a JSON object"),
        _check("entry-shape", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheckPlane.ENTRIES, not entry_error, entry_error or "valid", "valid", "every catalog entry is reconstructable from public fields"),
        _check("entry-count", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheckPlane.ENTRIES, len(parsed_entries) == entry_count and entry_count > 0, len(parsed_entries), entry_count, "entry rows conserve the declared bounded count"),
        _check("ordinal-order", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheckPlane.ENTRIES, tuple(item.ordinal for item in parsed_entries) == tuple(range(len(parsed_entries))), tuple(item.ordinal for item in parsed_entries), list(range(len(parsed_entries))), "entries are ordered by contiguous ordinals"),
        _check("unique-packet-addresses", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheckPlane.LINEAGE, len({item.packet_address for item in parsed_entries}) == len(parsed_entries), len({item.packet_address for item in parsed_entries}), len(parsed_entries), "packet binary addresses are unique"),
        _check("unique-packet-ids", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheckPlane.LINEAGE, len({item.packet_id for item in parsed_entries}) == len(parsed_entries), len({item.packet_id for item in parsed_entries}), len(parsed_entries), "packet IDs are unique"),
        _check("entry-addresses", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheckPlane.LINEAGE, all(address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_entry(item) == item.content_address for item in parsed_entries), "replayable" if all(address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_entry(item) == item.content_address for item in parsed_entries) else "mismatch", "replayable", "each entry content address replays from its canonical projection"),
        _check("acceptance-counts", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheckPlane.STATE, accepted_count + blocked_count == entry_count and (not parsed_entries or accepted_count == sum(item.packet_accepted for item in parsed_entries)), (accepted_count, blocked_count), entry_count, "accepted and blocked packet counts conserve the entries"),
        _check("accepted-state", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheckPlane.STATE, payload.get("accepted") == (blocked_count == 0) and payload.get("state") == ("accepted" if blocked_count == 0 else "blocked"), {"accepted": payload.get("accepted"), "state": payload.get("state")}, {"accepted": blocked_count == 0, "state": "accepted" if blocked_count == 0 else "blocked"}, "catalog state conserves packet acceptance"),
        _check("byte-conservation", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheckPlane.BYTES, (not parsed_entries) or payload.get("total_packet_bytes") == sum(item.packet_byte_count for item in parsed_entries), payload.get("total_packet_bytes"), sum(item.packet_byte_count for item in parsed_entries), "aggregate packet byte count conserves every entry"),
        _check("member-counts", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheckPlane.STRUCTURE, all(item.member_count == 5 for item in parsed_entries), tuple(item.member_count for item in parsed_entries), 5, "every cataloged packet retains the exact five-member contract"),
        _check("audit-gate-conservation", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheckPlane.STATE, all((not item.packet_accepted) or item.policy_audit_accepted for item in parsed_entries), "valid" if all((not item.packet_accepted) or item.policy_audit_accepted for item in parsed_entries) else "invalid", "valid", "accepted packets retain accepted independent audits"),
        _check("gate-blocked-count", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheckPlane.STATE, payload.get("policy_gate_blocked_count") == sum(not item.policy_gate_accepted for item in parsed_entries), payload.get("policy_gate_blocked_count"), sum(not item.policy_gate_accepted for item in parsed_entries), "blocked policy-gate evidence is conserved"),
        _check("audit-rejected-count", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheckPlane.STATE, payload.get("policy_audit_rejected_count") == sum(not item.policy_audit_accepted for item in parsed_entries), payload.get("policy_audit_rejected_count"), sum(not item.policy_audit_accepted for item in parsed_entries), "rejected independent-audit evidence is conserved"),
        _check("catalog-address", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheckPlane.LINEAGE, parse_ok and content_hash(_logical_body(payload), prefix=MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_PREFIX) == payload.get("catalog_address"), payload.get("catalog_address"), "replayable", "catalog address replays from public logical fields"),
        _check("public-boundary", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogCheckPlane.PUBLIC, not _has_forbidden_key(payload), "clean" if not _has_forbidden_key(payload) else "forbidden-key", "clean", "catalog contains only public aggregate fields"),
    ]
    return _verification(catalog_id, catalog_address, entry_count, accepted_count, blocked_count, checks)


def verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_value(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalog,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalog:
    if not isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalog):
        raise ValidationError("typed packet review catalog verification requires a catalog")
    verification = verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog(
        value.catalog_bytes
    )
    if not verification.accepted:
        raise ValidationError("packet review catalog verification failed")
    if address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog(value) != value.content_address:
        raise ValidationError("packet review catalog descriptor address mismatch")
    return value


def load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog(
    value: bytes | bytearray | str | Path,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalog:
    verification = verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog(value)
    if not verification.accepted:
        raise ValidationError("cannot load malformed packet review catalog")
    raw = _read_catalog(value)
    try:
        parsed = _strict_json_loads(raw.decode(_UTF8))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValidationError(f"cannot parse packet review catalog: {exc}") from exc
    if not isinstance(parsed, Mapping):
        raise ValidationError("packet review catalog must be a JSON object")
    return _catalog_from_mapping(parsed, raw)


def query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog(
    value: bytes | bytearray | str | Path,
    *,
    resource: str = "summary",
    state: str | None = None,
    policy_gate_accepted: bool | None = None,
    policy_audit_accepted: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DEFAULT_LIMIT,
) -> dict[str, Any]:
    if resource not in {"entries", "summary", "lineage"}:
        raise ValidationError("packet review catalog resource is invalid")
    if offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_MAX_LIMIT:
        raise ValidationError("packet review catalog paging is invalid")
    catalog = load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog(value)
    if state is not None:
        try:
            selected_state = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogState(state)
        except ValueError as exc:
            raise ValidationError("packet review catalog state filter is invalid") from exc
    else:
        selected_state = None
    if resource == "summary":
        rows: list[dict[str, Any]] = [catalog.to_dict(include_entries=False)]
    else:
        candidates = catalog.entries
        if selected_state is not None:
            candidates = tuple(item for item in candidates if item.state is selected_state)
        if policy_gate_accepted is not None:
            candidates = tuple(item for item in candidates if item.policy_gate_accepted == policy_gate_accepted)
        if policy_audit_accepted is not None:
            candidates = tuple(item for item in candidates if item.policy_audit_accepted == policy_audit_accepted)
        if text:
            needle = text.casefold()
            candidates = tuple(item for item in candidates if needle in canonical_json(item.to_dict()).casefold())
        if resource == "entries":
            rows = [item.to_dict() for item in candidates]
        else:
            rows = [
                {
                    "ordinal": item.ordinal,
                    "packet_id": item.packet_id,
                    "packet_address": item.packet_address,
                    "packet_content_address": item.packet_content_address,
                    "packet_diff_address": item.packet_diff_address,
                    "policy_gate_address": item.policy_gate_address,
                    "policy_audit_address": item.policy_audit_address,
                    "state": item.state,
                    "packet_accepted": item.packet_accepted,
                    "policy_gate_accepted": item.policy_gate_accepted,
                    "policy_audit_accepted": item.policy_audit_accepted,
                }
                for item in candidates
            ]
    body = {
        "catalog_id": catalog.catalog_id,
        "catalog_address": catalog.catalog_address,
        "resource": resource,
        "state": state,
        "policy_gate_accepted": policy_gate_accepted,
        "policy_audit_accepted": policy_audit_accepted,
        "text": text,
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix=MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_PREFIX + "-query",
        )
    }


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_json(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalog,
) -> str:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_value(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_csv(
    value: bytes | bytearray | str | Path,
    *,
    state: str | None = None,
    policy_gate_accepted: bool | None = None,
    policy_audit_accepted: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DEFAULT_LIMIT,
) -> str:
    result = query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog(
        value,
        resource="entries",
        state=state,
        policy_gate_accepted=policy_gate_accepted,
        policy_audit_accepted=policy_audit_accepted,
        text=text,
        offset=offset,
        limit=limit,
    )
    output = io.StringIO(newline="")
    fields = (
        "ordinal",
        "packet_id",
        "packet_address",
        "packet_diff_address",
        "policy_gate_address",
        "policy_audit_address",
        "packet_byte_count",
        "policy_gate_accepted",
        "policy_audit_accepted",
        "packet_accepted",
        "state",
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(result["items"])
    return output.getvalue()


def render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_markdown(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalog,
) -> str:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_value(value)
    lines = [
        f"# {value.catalog_id}",
        "",
        f"- State: `{value.state.value}`",
        f"- Packets: `{value.entry_count}`",
        f"- Accepted: `{value.accepted_count}`",
        f"- Blocked: `{value.blocked_count}`",
        f"- Policy gates blocked: `{value.policy_gate_blocked_count}`",
        f"- Independent audits rejected: `{value.policy_audit_rejected_count}`",
        f"- Catalog address: `{value.catalog_address}`",
        "",
        "| Ordinal | Packet | State | Gate | Audit | Bytes | Packet address |",
        "|---:|---|---|---|---|---:|---|",
    ]
    lines.extend(
        f"| {item.ordinal} | `{item.packet_id}` | `{item.state.value}` | `{item.policy_gate_accepted}` | `{item.policy_audit_accepted}` | {item.packet_byte_count} | `{item.packet_address}` |"
        for item in value.entries
    )
    return "\n".join(lines) + "\n"


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_schema() -> dict[str, Any]:
    return {
        "version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_VERSION,
        "boundary": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_BOUNDARY,
        "format": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_FORMAT,
        "maximum_entries": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_MAX_ENTRIES,
        "maximum_checks": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_MAX_CHECKS,
        "maximum_bytes": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_MAX_BYTES,
        "resources": ["entries", "summary", "lineage"],
        "filters": ["state", "policy_gate_accepted", "policy_audit_accepted", "text"],
        "source_free": True,
        "retains_packet_payloads": False,
        "preserves_blocked_gate_evidence": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_capabilities() -> dict[str, Any]:
    operations = (
        "build_catalog",
        "verify_canonical_json",
        "verify_unique_packet_ids",
        "verify_unique_packet_addresses",
        "verify_entry_addresses",
        "verify_lineage_addresses",
        "verify_state_conservation",
        "verify_byte_conservation",
        "verify_public_boundary",
        "load_source_free",
        "query_entries",
        "query_lineage",
        "filter_state",
        "filter_policy_gate",
        "filter_policy_audit",
        "filter_text",
        "export_json",
        "export_csv",
        "render_markdown",
    )
    return {
        "version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "source_free": True,
        "read_only": True,
        "payload_free": True,
    }


__all__ = [
    "build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog",
    "load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog",
    "module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_capabilities",
    "module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_csv",
    "module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_json",
    "module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_schema",
    "query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog",
    "render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_markdown",
    "verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog",
    "verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_value",
    "write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog",
]
