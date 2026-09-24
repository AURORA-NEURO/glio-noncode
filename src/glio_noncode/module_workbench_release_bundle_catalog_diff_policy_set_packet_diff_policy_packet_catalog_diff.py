"""Compare packet review catalogs without reading packet payloads."""

# ruff: noqa: E501, F403, F405

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._safe_persistence import _validate_parent, atomic_write_bytes, read_bytes
from .errors import ValidationError
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog import (
    load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_value,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_contracts import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalog,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogEntry,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_contracts import *
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

_UTF8 = "utf-8"
_MAX_JSON_BYTES = 16 * 1024 * 1024
_PUBLIC_ENTRY_FIELDS = ("packet_address", "packet_content_address", "packet_diff_address", "policy_gate_address", "policy_audit_address", "packet_byte_count", "member_count", "verification_entry_count", "verification_check_count", "verification_failed_count", "policy_gate_accepted", "policy_audit_accepted", "packet_accepted", "state")


def _catalog(value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalog | bytes | bytearray | str | Path) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalog:
    if isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalog):
        verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_value(value)
        return value
    return load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog(value)


def _entry_fields(entry: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogEntry) -> dict[str, Any]:
    body = entry.to_dict()
    return {field: body[field] for field in _PUBLIC_ENTRY_FIELDS}


def _addressed_change(body: dict[str, Any]) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffChange:
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffChange(**body, content_address="pending")
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffChange(**body, content_address=address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_change(provisional))


def _change(ordinal: int, packet_id: str, kind: Any, direction: Any, transition: Any, previous: Any, current: Any, changed_fields: tuple[str, ...], detail: str) -> Any:
    body = {"packet_id": packet_id, "ordinal": ordinal, "kind": kind, "direction": direction, "state_transition": transition, "previous_entry_address": previous.content_address if previous else None, "current_entry_address": current.content_address if current else None, "previous_packet_address": previous.packet_address if previous else None, "current_packet_address": current.packet_address if current else None, "previous_state": previous.state.value if previous else None, "current_state": current.state.value if current else None, "changed_fields": tuple(sorted(changed_fields)), "detail": detail}
    return _addressed_change(body)


def _aggregate_direction(changes: tuple[Any, ...]) -> Any:
    directions = {item.direction for item in changes}
    if not directions or directions == {ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffDirection.UNCHANGED}:
        return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffDirection.UNCHANGED
    if directions == {ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffDirection.IMPROVED}:
        return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffDirection.IMPROVED
    if directions == {ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffDirection.REGRESSED}:
        return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffDirection.REGRESSED
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffDirection.CHANGED


def _aggregate_transition(previous: Any, current: Any, changes: tuple[Any, ...]) -> Any:
    if previous.accepted and not current.accepted:
        return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffStateTransition.ACCEPTED_TO_BLOCKED
    if not previous.accepted and current.accepted:
        return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffStateTransition.BLOCKED_TO_ACCEPTED
    if not changes or all(item.state_transition is ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffStateTransition.UNCHANGED for item in changes):
        return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffStateTransition.UNCHANGED
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffStateTransition.CHANGED


def build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff(previous: Any, current: Any, *, diff_id: str = "glio-noncode-module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet-catalog-diff") -> Any:
    """Classify packet IDs and compare only public catalog descriptors."""
    if not isinstance(diff_id, str) or not diff_id.strip():
        raise ValidationError("packet catalog diff ID is required")
    before_catalog = _catalog(previous)
    after_catalog = _catalog(current)
    before_map = {item.packet_id: item for item in before_catalog.entries}
    after_map = {item.packet_id: item for item in after_catalog.entries}
    packet_ids = tuple(sorted(set(before_map) | set(after_map)))
    if len(packet_ids) > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_MAX_CHANGES:
        raise ValidationError("packet catalog diff change limit exceeded")
    changes: list[Any] = []
    for ordinal, packet_id in enumerate(packet_ids):
        before, after = before_map.get(packet_id), after_map.get(packet_id)
        if before is None:
            changes.append(_change(ordinal, packet_id, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffChangeKind.ADDED, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffDirection.CHANGED, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffStateTransition.ADDED, None, after, ("packet_added",), "packet entered the candidate catalog"))
            continue
        if after is None:
            changes.append(_change(ordinal, packet_id, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffChangeKind.REMOVED, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffDirection.CHANGED, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffStateTransition.REMOVED, before, None, ("packet_removed",), "packet is absent from the candidate catalog"))
            continue
        before_fields, after_fields = _entry_fields(before), _entry_fields(after)
        changed_fields = tuple(sorted(field for field in _PUBLIC_ENTRY_FIELDS if before_fields[field] != after_fields[field]))
        if not changed_fields:
            changes.append(_change(ordinal, packet_id, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffChangeKind.UNCHANGED, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffDirection.UNCHANGED, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffStateTransition.UNCHANGED, before, after, (), "packet descriptor is unchanged"))
        elif not before.packet_accepted and after.packet_accepted:
            changes.append(_change(ordinal, packet_id, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffChangeKind.CHANGED, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffDirection.IMPROVED, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffStateTransition.BLOCKED_TO_ACCEPTED, before, after, changed_fields, "packet changed from blocked to accepted"))
        elif before.packet_accepted and not after.packet_accepted:
            changes.append(_change(ordinal, packet_id, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffChangeKind.CHANGED, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffDirection.REGRESSED, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffStateTransition.ACCEPTED_TO_BLOCKED, before, after, changed_fields, "packet changed from accepted to blocked"))
        else:
            changes.append(_change(ordinal, packet_id, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffChangeKind.CHANGED, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffDirection.CHANGED, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffStateTransition.CHANGED, before, after, changed_fields, "packet descriptor fields changed"))
    frozen = tuple(changes)
    body = {"diff_id": diff_id, "previous_catalog_address": before_catalog.catalog_address, "current_catalog_address": after_catalog.catalog_address, "previous_catalog_content_address": before_catalog.content_address, "current_catalog_content_address": after_catalog.content_address, "previous_catalog_state": before_catalog.state.value, "current_catalog_state": after_catalog.state.value, "changes": frozen, "added_count": sum(item.kind is ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffChangeKind.ADDED for item in frozen), "changed_count": sum(item.kind is ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffChangeKind.CHANGED for item in frozen), "removed_count": sum(item.kind is ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffChangeKind.REMOVED for item in frozen), "unchanged_count": sum(item.kind is ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffChangeKind.UNCHANGED for item in frozen), "direction": _aggregate_direction(frozen), "state_transition": _aggregate_transition(before_catalog, after_catalog, frozen), "accepted": True}
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiff(**body, content_address="pending")
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiff(**body, content_address=address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff(provisional))


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _change_from_mapping(value: Mapping[str, Any]) -> Any:
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffChange(packet_id=str(value.get("packet_id", "")), ordinal=value.get("ordinal"), kind=ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffChangeKind(str(value.get("kind"))), direction=ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffDirection(str(value.get("direction"))), state_transition=ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffStateTransition(str(value.get("state_transition"))), previous_entry_address=value.get("previous_entry_address"), current_entry_address=value.get("current_entry_address"), previous_packet_address=value.get("previous_packet_address"), current_packet_address=value.get("current_packet_address"), previous_state=value.get("previous_state"), current_state=value.get("current_state"), changed_fields=tuple(value.get("changed_fields", ())), detail=str(value.get("detail", "")), content_address=str(value.get("content_address", "")))


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_from_mapping(value: Mapping[str, Any]) -> Any:
    raw_changes = value.get("changes")
    if not isinstance(raw_changes, list):
        raise ValidationError("packet catalog diff changes are invalid")
    result = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiff(diff_id=str(value.get("diff_id", "")), previous_catalog_address=str(value.get("previous_catalog_address", "")), current_catalog_address=str(value.get("current_catalog_address", "")), previous_catalog_content_address=str(value.get("previous_catalog_content_address", "")), current_catalog_content_address=str(value.get("current_catalog_content_address", "")), previous_catalog_state=str(value.get("previous_catalog_state", "")), current_catalog_state=str(value.get("current_catalog_state", "")), changes=tuple(_change_from_mapping(_mapping(item, "packet catalog diff change")) for item in raw_changes), added_count=value.get("added_count"), changed_count=value.get("changed_count"), removed_count=value.get("removed_count"), unchanged_count=value.get("unchanged_count"), direction=ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffDirection(str(value.get("direction"))), state_transition=ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffStateTransition(str(value.get("state_transition"))), accepted=value.get("accepted"), content_address=str(value.get("content_address", "")))
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_value(result)
    return result


def load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff(value: Mapping[str, Any] | bytes | bytearray | str | Path) -> Any:
    if isinstance(value, Mapping):
        return module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_from_mapping(value)
    raw = bytes(value) if isinstance(value, (bytes, bytearray)) else read_bytes(value, field="packet catalog diff", max_bytes=_MAX_JSON_BYTES)
    try:
        parsed = _strict_json_loads(raw.decode(_UTF8))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValidationError(f"cannot parse packet catalog diff: {exc}") from exc
    if not isinstance(parsed, Mapping) or raw != (canonical_json(parsed) + "\n").encode(_UTF8):
        raise ValidationError("packet catalog diff must be canonical JSON object")
    return module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_from_mapping(parsed)


def _check(check_id: str, plane: Any, passed: bool, observed: Any, required: Any, detail: str) -> Any:
    body = {"check_id": check_id, "plane": plane, "passed": bool(passed), "observed": observed, "required": required, "detail": detail}
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffCheck(**body, content_address="pending")
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffCheck(**body, content_address=address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_check(provisional))


def _verification(value: Any, checks: list[Any]) -> Any:
    ordered = tuple(sorted(checks, key=lambda item: item.check_id))
    body = {"diff_id": value.diff_id, "previous_catalog_address": value.previous_catalog_address, "current_catalog_address": value.current_catalog_address, "change_count": len(value.changes), "checks": ordered, "accepted": bool(ordered) and all(item.passed for item in ordered)}
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffVerification(**body, content_address="pending")
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffVerification(**body, content_address=address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_verification(provisional))


def verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff(value: Any) -> Any:
    if not isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiff):
        try:
            value = load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff(value)
        except ValidationError as exc:
            return _verification_failure(str(exc))
    checks = [_check("input-addresses", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffCheckPlane.INPUT, bool(value.previous_catalog_address and value.current_catalog_address), (value.previous_catalog_address, value.current_catalog_address), "two catalog addresses", "baseline and candidate catalogs retain addresses"), _check("unique-packets", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffCheckPlane.CHANGES, len({item.packet_id for item in value.changes}) == len(value.changes), [item.packet_id for item in value.changes], "unique packet identities", "packet identities are classified once"), _check("change-addresses", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffCheckPlane.ADDRESS, all(address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_change(item) == item.content_address for item in value.changes), "replayable" if all(address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_change(item) == item.content_address for item in value.changes) else "mismatch", "replayable", "each packet change retains a content address"), _check("count-conservation", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffCheckPlane.CHANGES, value.added_count + value.changed_count + value.removed_count + value.unchanged_count == len(value.changes), len(value.changes), value.added_count + value.changed_count + value.removed_count + value.unchanged_count, "classification counts conserve every packet"), _check("direction-replay", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffCheckPlane.CHANGES, value.direction is _aggregate_direction(value.changes), value.direction.value, _aggregate_direction(value.changes).value, "aggregate direction is derived from packet changes"), _check("state-transition", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffCheckPlane.CHANGES, value.state_transition in set(ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffStateTransition), value.state_transition.value, "valid transition", "aggregate catalog transition is explicit"), _check("diff-address", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffCheckPlane.ADDRESS, address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff(value) == value.content_address, "conserved", "conserved", "comparison address replays from public fields"), _check("public-boundary", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffCheckPlane.PUBLIC, not _has_forbidden_key(value.to_dict()), "clean" if not _has_forbidden_key(value.to_dict()) else "forbidden-key", "clean", "comparison contains only public source-free evidence")]
    return _verification(value, checks)


def _verification_failure(detail: str) -> Any:
    body = {"diff_id": "unavailable", "previous_catalog_address": "unavailable", "current_catalog_address": "unavailable", "change_count": 0, "checks": (_check("input-readable", ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffCheckPlane.INPUT, False, detail, "readable and canonical", "comparison input could not be loaded"),), "accepted": False}
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffVerification(**body, content_address="pending")
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffVerification(**body, content_address=address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_verification(provisional))


def verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_value(value: Any) -> Any:
    if not isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiff):
        raise ValidationError("typed packet catalog diff verification requires a diff")
    if address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff(value) != value.content_address:
        raise ValidationError("packet catalog diff address mismatch")
    return value


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_json(value: Any) -> str:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_value(value)
    return canonical_json(value.to_dict()) + "\n"


def write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff(value: Any, destination: str | Path, *, allow_existing: bool = False) -> Any:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_value(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("packet catalog diff destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("packet catalog diff destination is not a file")
    _validate_parent(path.parent, "packet catalog diff destination")
    atomic_write_bytes(path, module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_json(value).encode(_UTF8), field="packet catalog diff destination")
    return value


def query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff(value: Any, *, kind: str | None = None, direction: str | None = None, state_transition: str | None = None, text: str | None = None, offset: int = 0, limit: int = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_DEFAULT_LIMIT) -> dict[str, Any]:
    if offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_MAX_LIMIT:
        raise ValidationError("packet catalog diff paging is invalid")
    valid_kind = {item.value for item in ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffChangeKind}
    valid_direction = {item.value for item in ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffDirection}
    valid_transition = {item.value for item in ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffStateTransition}
    if kind is not None and kind not in valid_kind or direction is not None and direction not in valid_direction or state_transition is not None and state_transition not in valid_transition:
        raise ValidationError("packet catalog diff filter is invalid")
    diff = value if isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiff) else load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff(value)
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_value(diff)
    rows = [item.to_dict() for item in diff.changes]
    if kind is not None:
        rows = [item for item in rows if item["kind"] == kind]
    if direction is not None:
        rows = [item for item in rows if item["direction"] == direction]
    if state_transition is not None:
        rows = [item for item in rows if item["state_transition"] == state_transition]
    if text:
        rows = [item for item in rows if text.casefold() in canonical_json(item).casefold()]
    body = {"diff_address": diff.content_address, "previous_catalog_address": diff.previous_catalog_address, "current_catalog_address": diff.current_catalog_address, "kind": kind, "direction": direction, "state_transition": state_transition, "text": text, "total": len(rows), "offset": offset, "limit": limit, "items": rows[offset:offset + limit]}
    return body | {"content_address": content_hash(body, prefix=MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_QUERY_PREFIX)}


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_csv(value: Any, **filters: Any) -> str:
    result = query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff(value, **filters)
    output = io.StringIO(newline="")
    fields = tuple(sorted({key for row in result["items"] for key in row}))
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(result["items"])
    return output.getvalue()


def render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_markdown(value: Any) -> str:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_value(value)
    lines = ["# Packet Review Catalog Diff", "", f"- Diff: `{value.diff_id}`", f"- Baseline catalog: `{value.previous_catalog_address}`", f"- Candidate catalog: `{value.current_catalog_address}`", f"- Added / changed / removed / unchanged: **{value.added_count} / {value.changed_count} / {value.removed_count} / {value.unchanged_count}**", f"- Direction: `{value.direction.value}`", f"- State transition: `{value.state_transition.value}`", "", "| Packet | Kind | Direction | Transition | Changed fields |", "| --- | --- | --- | --- | --- |"]
    lines.extend(f"| `{item.packet_id}` | `{item.kind.value}` | `{item.direction.value}` | `{item.state_transition.value}` | `{', '.join(item.changed_fields)}` |" for item in value.changes)
    return "\n".join(lines) + "\n"


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_schema() -> dict[str, Any]:
    return {"version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_VERSION, "boundary": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_BOUNDARY, "change_kinds": [item.value for item in ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffChangeKind], "directions": [item.value for item in ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffDirection], "state_transitions": [item.value for item in ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffStateTransition], "max_changes": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_MAX_CHANGES, "max_checks": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_MAX_CHECKS, "public_fields": list(_PUBLIC_ENTRY_FIELDS), "source_free": True, "path_free": True, "timestamp_free": True, "payload_free": True}


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_capabilities() -> dict[str, Any]:
    operations = ("compare_packet_catalogs", "classify_added_changed_removed_unchanged", "retain_packet_field_deltas", "derive_direction", "derive_state_transition", "verify_change_addresses", "query_changes", "filter_kind", "filter_direction", "filter_state_transition", "export_json", "export_csv", "export_markdown")
    return {"version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_CATALOG_DIFF_VERSION, "operation_count": len(operations), "operations": list(operations), "deterministic": True, "source_free": True, "path_free": True, "timestamp_free": True, "payload_free": True}


__all__ = [name for name in globals() if name.startswith("build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff") or name.startswith("load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff") or name.startswith("module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff") or name.startswith("query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff") or name.startswith("render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff") or name.startswith("verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff") or name.startswith("write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff")]
