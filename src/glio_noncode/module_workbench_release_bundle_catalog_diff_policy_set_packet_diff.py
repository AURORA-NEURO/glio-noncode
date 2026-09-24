"""Compare portable policy-set packets without source access."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_contracts as c
from ._safe_persistence import _validate_parent, atomic_write_bytes, read_bytes
from .errors import ValidationError
from .module_workbench_release_bundle_catalog_diff_policy_set_packet import (
    load_module_workbench_release_bundle_catalog_diff_policy_set_packet,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_contracts import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketVerification,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_contracts import (
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_BOUNDARY,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_DEFAULT_LIMIT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_MAX_LIMIT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_VERSION,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiff,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffChange,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffCheck,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffDirection,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffVerification,
    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff,
    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_change,
    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_check,
    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_verification,
)
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

_UTF8 = "utf-8"
_MAX_JSON_BYTES = 16 * 1024 * 1024
PacketDiffStateTransition = (
    c.ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffStateTransition
)


def _projection(
    packet_verification: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketVerification,
    gate: Any,
    audit: Any,
) -> dict[str, Any]:
    return {
        "packet_address": packet_verification.packet_address,
        "gate_address": gate.content_address,
        "audit_address": audit.content_address,
        "gate_accepted": gate.accepted,
        "audit_accepted": audit.accepted,
        "policy_count": len(gate.gates),
        "passed_policy_count": gate.passed_policy_count,
        "failed_policy_count": gate.failed_policy_count,
        "audit_check_count": len(audit.checks),
        "audit_passed_count": audit.passed_count,
        "audit_failed_count": audit.failed_count,
    }


def _direction(
    previous: Mapping[str, Any],
    current: Mapping[str, Any],
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffDirection:
    if previous == current:
        return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffDirection.UNCHANGED
    if not previous["gate_accepted"] and current["gate_accepted"]:
        return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffDirection.IMPROVED
    if previous["gate_accepted"] and not current["gate_accepted"]:
        return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffDirection.REGRESSED
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffDirection.CHANGED


def _transition(
    previous: Mapping[str, Any],
    current: Mapping[str, Any],
) -> PacketDiffStateTransition:
    if previous["gate_accepted"] and not current["gate_accepted"]:
        return PacketDiffStateTransition.ACCEPTED_TO_BLOCKED
    if not previous["gate_accepted"] and current["gate_accepted"]:
        return PacketDiffStateTransition.BLOCKED_TO_ACCEPTED
    if previous == current:
        return PacketDiffStateTransition.UNCHANGED
    return PacketDiffStateTransition.CHANGED


def _change(
    field_name: str,
    previous: Any,
    current: Any,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffChange:
    body = {"field_name": field_name, "previous": previous, "current": current}
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffChange(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffChange(
        **body,
        content_address=address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_change(
            provisional
        ),
    )


def build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff(
    previous: bytes | bytearray | str | Path,
    current: bytes | bytearray | str | Path,
    *,
    diff_id: str = (
        "glio-noncode-module-workbench-release-bundle-catalog-diff-policy-set-packet-diff"
    ),
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiff:
    """Compare two verified packets while preserving both packet addresses."""

    previous_verification = verify_module_workbench_release_bundle_catalog_diff_policy_set_packet(
        previous
    )
    current_verification = verify_module_workbench_release_bundle_catalog_diff_policy_set_packet(
        current
    )
    if not previous_verification.accepted or not current_verification.accepted:
        raise ValidationError("packet diff requires two accepted packet verifications")
    if previous_verification.packet_id != current_verification.packet_id:
        raise ValidationError("packet diff requires the same packet identity")
    previous_gate, previous_audit, _ = (
        load_module_workbench_release_bundle_catalog_diff_policy_set_packet(previous)
    )
    current_gate, current_audit, _ = (
        load_module_workbench_release_bundle_catalog_diff_policy_set_packet(current)
    )
    previous_projection = _projection(previous_verification, previous_gate, previous_audit)
    current_projection = _projection(current_verification, current_gate, current_audit)
    changes = tuple(
        _change(field_name, previous_projection[field_name], current_projection[field_name])
        for field_name in sorted(set(previous_projection) | set(current_projection))
        if previous_projection[field_name] != current_projection[field_name]
    )
    body = {
        "diff_id": diff_id,
        "packet_id": previous_verification.packet_id,
        "previous_packet_address": previous_verification.packet_address,
        "current_packet_address": current_verification.packet_address,
        "previous_gate_address": previous_gate.content_address,
        "current_gate_address": current_gate.content_address,
        "previous_audit_address": previous_audit.content_address,
        "current_audit_address": current_audit.content_address,
        "previous_accepted": previous_gate.accepted,
        "current_accepted": current_gate.accepted,
        "direction": _direction(previous_projection, current_projection),
        "state_transition": _transition(previous_projection, current_projection),
        "changes": changes,
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiff(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiff(
        **body,
        content_address=address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff(
            provisional
        ),
    )


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffCheck:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffCheck(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffCheck(
        **body,
        content_address=address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_check(
            provisional
        ),
    )


def verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiff,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffVerification:
    """Replay change addresses, direction, transition, order, and boundary."""

    if not isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiff):
        raise ValidationError("packet diff verification requires a typed diff")
    changes = value.changes
    replay_direction = (
        ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffDirection.UNCHANGED
        if not changes
        else (
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffDirection.IMPROVED
            if not value.previous_accepted and value.current_accepted
            else ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffDirection.REGRESSED
            if value.previous_accepted and not value.current_accepted
            else ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffDirection.CHANGED
        )
    )
    replay_transition = (
        PacketDiffStateTransition.BLOCKED_TO_ACCEPTED
        if not value.previous_accepted and value.current_accepted
        else PacketDiffStateTransition.ACCEPTED_TO_BLOCKED
        if value.previous_accepted and not value.current_accepted
        else PacketDiffStateTransition.UNCHANGED
        if not changes
        else PacketDiffStateTransition.CHANGED
    )
    checks = tuple(
        sorted(
            (
                _check(
                    "address-replay",
                    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff(
                        value
                    )
                    == value.content_address,
                    value.content_address,
                    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff(
                        value
                    ),
                    "packet diff address replays from the canonical projection",
                ),
                _check(
                    "change-addresses",
                    all(
                        address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_change(
                            item
                        )
                        == item.content_address
                        for item in changes
                    ),
                    "valid",
                    "valid",
                    "every field delta address replays",
                ),
                _check(
                    "change-count-conservation",
                    value.changed_count == len(changes),
                    value.changed_count,
                    len(changes),
                    "changed_count conserves every field delta",
                ),
                _check(
                    "direction-replay",
                    value.direction is replay_direction,
                    value.direction,
                    replay_direction,
                    "direction is derived from accepted-state movement and deltas",
                ),
                _check(
                    "field-order",
                    tuple(item.field_name for item in changes)
                    == tuple(sorted(item.field_name for item in changes)),
                    tuple(item.field_name for item in changes),
                    tuple(sorted(item.field_name for item in changes)),
                    "field deltas are sorted and unique",
                ),
                _check(
                    "public-boundary",
                    not _has_forbidden_key(value.to_dict()),
                    "clean" if not _has_forbidden_key(value.to_dict()) else "forbidden-key",
                    "clean",
                    "packet diff contains only public aggregate fields",
                ),
                _check(
                    "state-transition-replay",
                    value.state_transition is replay_transition,
                    value.state_transition,
                    replay_transition,
                    "state transition is derived from accepted-state movement and deltas",
                ),
            ),
            key=lambda item: item.check_id,
        )
    )
    body = {
        "diff_address": value.content_address,
        "previous_packet_address": value.previous_packet_address,
        "current_packet_address": value.current_packet_address,
        "checks": checks,
        "accepted": all(item.passed for item in checks),
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffVerification(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffVerification(
        **body,
        content_address=address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_verification(
            provisional
        ),
    )


def _change_from_mapping(
    value: Mapping[str, Any],
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffChange:
    result = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffChange(
        field_name=str(value.get("field_name", "")),
        previous=value.get("previous"),
        current=value.get("current"),
        content_address=str(value.get("content_address", "")),
    )
    if (
        address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_change(result)
        != result.content_address
    ):
        raise ValidationError("packet diff change address mismatch")
    return result


def _diff_from_mapping(
    value: Mapping[str, Any],
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiff:
    raw_changes = value.get("changes")
    if not isinstance(raw_changes, list) or any(
        not isinstance(item, Mapping) for item in raw_changes
    ):
        raise ValidationError("packet diff changes are invalid")
    result = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiff(
        diff_id=str(value.get("diff_id", "")),
        packet_id=str(value.get("packet_id", "")),
        previous_packet_address=str(value.get("previous_packet_address", "")),
        current_packet_address=str(value.get("current_packet_address", "")),
        previous_gate_address=str(value.get("previous_gate_address", "")),
        current_gate_address=str(value.get("current_gate_address", "")),
        previous_audit_address=str(value.get("previous_audit_address", "")),
        current_audit_address=str(value.get("current_audit_address", "")),
        previous_accepted=value.get("previous_accepted"),
        current_accepted=value.get("current_accepted"),
        direction=ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffDirection(
            str(value.get("direction", ""))
        ),
        state_transition=PacketDiffStateTransition(str(value.get("state_transition", ""))),
        changes=tuple(_change_from_mapping(item) for item in raw_changes),
        content_address=str(value.get("content_address", "")),
    )
    if (
        address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff(result)
        != result.content_address
    ):
        raise ValidationError("packet diff address mismatch")
    return result


def load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff(
    value: bytes | bytearray | str | Path | Mapping[str, Any],
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiff:
    if isinstance(value, Mapping):
        return _diff_from_mapping(value)
    raw = (
        bytes(value)
        if isinstance(value, (bytes, bytearray))
        else read_bytes(value, field="policy-set packet diff", max_bytes=_MAX_JSON_BYTES)
    )
    try:
        parsed = _strict_json_loads(raw.decode(_UTF8))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValidationError(f"cannot parse policy-set packet diff: {exc}") from exc
    if not isinstance(parsed, Mapping):
        raise ValidationError("policy-set packet diff must be a JSON object")
    if raw != (canonical_json(parsed) + "\n").encode(_UTF8):
        raise ValidationError("policy-set packet diff is not canonical JSON")
    return _diff_from_mapping(parsed)


def write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiff,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiff:
    if (
        address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff(value)
        != value.content_address
    ):
        raise ValidationError("packet diff address mismatch")
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("packet diff destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("packet diff destination is not a file")
    _validate_parent(path.parent, "packet diff destination")
    atomic_write_bytes(
        path,
        module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_json(value).encode(
            _UTF8
        ),
        field="packet diff destination",
    )
    return value


def query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiff
    | bytes
    | bytearray
    | str
    | Path
    | Mapping[str, Any],
    *,
    field_name: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_DEFAULT_LIMIT,
) -> dict[str, Any]:
    if (
        offset < 0
        or limit < 1
        or limit > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_MAX_LIMIT
    ):
        raise ValidationError("packet diff paging is invalid")
    diff = (
        value
        if isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiff)
        else load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff(value)
    )
    rows = [item.to_dict() for item in diff.changes]
    if field_name:
        rows = [item for item in rows if item["field_name"] == field_name]
    if text:
        rows = [item for item in rows if text.casefold() in canonical_json(item).casefold()]
    body = {
        "diff_address": diff.content_address,
        "previous_packet_address": diff.previous_packet_address,
        "current_packet_address": diff.current_packet_address,
        "direction": diff.direction,
        "state_transition": diff.state_transition,
        "field_name": field_name,
        "text": text,
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
    }
    return body | {
        "content_address": content_hash(
            body, prefix="module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-query"
        )
    }


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_json(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiff,
) -> str:
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_csv(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiff,
    *,
    field_name: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_DEFAULT_LIMIT,
) -> str:
    result = query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff(
        value, field_name=field_name, text=text, offset=offset, limit=limit
    )
    output = io.StringIO(newline="")
    fields = ("field_name", "previous", "current", "content_address")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(result["items"])
    return output.getvalue()


def render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_markdown(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiff,
) -> str:
    lines = [
        "# Module Workbench Release Bundle Catalog Diff Policy-Set Packet Diff",
        "",
        f"- Diff: `{value.content_address}`",
        f"- Packet: `{value.packet_id}`",
        "- Previous / current: "
        f"`{value.previous_packet_address}` / `{value.current_packet_address}`",
        f"- Direction: **{value.direction.value}**",
        f"- State transition: **{value.state_transition.value}**",
        f"- Changed fields: **{value.changed_count}**",
        "",
        "| Field | Previous | Current |",
        "| --- | --- | --- |",
    ]
    lines.extend(
        "| "
        f"`{item.field_name}` | `{canonical_json(item.previous)}` | "
        f"`{canonical_json(item.current)}` |"
        for item in value.changes
    )
    return "\n".join(lines) + "\n"


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_schema() -> dict[str, Any]:
    return {
        "version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_VERSION,
        "boundary": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_BOUNDARY,
        "resources": ["summary", "changes"],
        "directions": [
            item.value
            for item in ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffDirection
        ],
        "state_transitions": [item.value for item in PacketDiffStateTransition],
        "source_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_capabilities() -> dict[
    str, Any
]:
    operations = (
        "compare_verified_packets",
        "classify_improvement",
        "classify_regression",
        "replay_field_deltas",
        "query_changes",
        "export_json",
        "export_csv",
        "render_markdown",
        "verify_addresses",
    )
    return {
        "version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "source_free": True,
        "read_only": True,
    }


__all__ = [
    "build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff",
    "load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff",
    "module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_capabilities",
    "module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_csv",
    "module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_json",
    "module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_schema",
    "query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff",
    "render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_markdown",
    "verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff",
    "write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff",
]
