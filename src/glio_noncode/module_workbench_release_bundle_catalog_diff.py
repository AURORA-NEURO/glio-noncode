"""Compare release-bundle catalogs without source or bundle payload access."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._safe_persistence import _validate_parent, atomic_write_bytes, read_bytes
from .errors import ValidationError
from .module_workbench_release_bundle_catalog import (
    load_module_workbench_release_bundle_catalog,
    verify_module_workbench_release_bundle_catalog_value,
)
from .module_workbench_release_bundle_catalog_contracts import (
    ModuleWorkbenchReleaseBundleCatalog,
    ModuleWorkbenchReleaseBundleCatalogEntry,
)
from .module_workbench_release_bundle_catalog_diff_contracts import (
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_BOUNDARY,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_DEFAULT_LIMIT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_MAX_CHANGES,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_MAX_LIMIT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_QUERY_PREFIX,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_VERSION,
    ModuleWorkbenchReleaseBundleCatalogDiff,
    ModuleWorkbenchReleaseBundleCatalogDiffChange,
    ModuleWorkbenchReleaseBundleCatalogDiffChangeKind,
    ModuleWorkbenchReleaseBundleCatalogDiffCheck,
    ModuleWorkbenchReleaseBundleCatalogDiffCheckPlane,
    ModuleWorkbenchReleaseBundleCatalogDiffDirection,
    ModuleWorkbenchReleaseBundleCatalogDiffStateTransition,
    ModuleWorkbenchReleaseBundleCatalogDiffVerification,
    address_module_workbench_release_bundle_catalog_diff,
    address_module_workbench_release_bundle_catalog_diff_change,
    address_module_workbench_release_bundle_catalog_diff_check,
    address_module_workbench_release_bundle_catalog_diff_verification,
)
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

_UTF8 = "utf-8"
_MAX_JSON_BYTES = 16 * 1024 * 1024


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    return value


def _catalog_context(
    value: ModuleWorkbenchReleaseBundleCatalog | bytes | bytearray | str | Path,
) -> ModuleWorkbenchReleaseBundleCatalog:
    if isinstance(value, ModuleWorkbenchReleaseBundleCatalog):
        verify_module_workbench_release_bundle_catalog_value(value)
        return value
    return load_module_workbench_release_bundle_catalog(value)


def _change(
    ordinal: int,
    bundle_id: str,
    kind: ModuleWorkbenchReleaseBundleCatalogDiffChangeKind,
    direction: ModuleWorkbenchReleaseBundleCatalogDiffDirection,
    state_transition: ModuleWorkbenchReleaseBundleCatalogDiffStateTransition,
    previous: ModuleWorkbenchReleaseBundleCatalogEntry | None,
    current: ModuleWorkbenchReleaseBundleCatalogEntry | None,
    changed_fields: tuple[str, ...],
    detail: str,
) -> ModuleWorkbenchReleaseBundleCatalogDiffChange:
    body = {
        "bundle_id": bundle_id,
        "ordinal": ordinal,
        "kind": kind,
        "direction": direction,
        "state_transition": state_transition,
        "previous_entry_address": previous.content_address if previous else None,
        "current_entry_address": current.content_address if current else None,
        "previous_bundle_address": previous.bundle_address if previous else None,
        "current_bundle_address": current.bundle_address if current else None,
        "previous_state": previous.state.value if previous else None,
        "current_state": current.state.value if current else None,
        "changed_fields": tuple(sorted(changed_fields)),
        "detail": detail,
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffChange(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffChange(
        **body,
        content_address=address_module_workbench_release_bundle_catalog_diff_change(provisional),
    )


def _entry_fields(entry: ModuleWorkbenchReleaseBundleCatalogEntry) -> dict[str, Any]:
    body = entry.to_dict()
    body.pop("ordinal", None)
    body.pop("content_address", None)
    return body


def _aggregate_direction(
    changes: tuple[ModuleWorkbenchReleaseBundleCatalogDiffChange, ...],
) -> ModuleWorkbenchReleaseBundleCatalogDiffDirection:
    directions = {item.direction for item in changes}
    if not directions or directions == {ModuleWorkbenchReleaseBundleCatalogDiffDirection.UNCHANGED}:
        return ModuleWorkbenchReleaseBundleCatalogDiffDirection.UNCHANGED
    if directions == {ModuleWorkbenchReleaseBundleCatalogDiffDirection.IMPROVED}:
        return ModuleWorkbenchReleaseBundleCatalogDiffDirection.IMPROVED
    if directions == {ModuleWorkbenchReleaseBundleCatalogDiffDirection.REGRESSED}:
        return ModuleWorkbenchReleaseBundleCatalogDiffDirection.REGRESSED
    return ModuleWorkbenchReleaseBundleCatalogDiffDirection.CHANGED


def _aggregate_transition(
    previous: ModuleWorkbenchReleaseBundleCatalog,
    current: ModuleWorkbenchReleaseBundleCatalog,
    changes: tuple[ModuleWorkbenchReleaseBundleCatalogDiffChange, ...],
) -> ModuleWorkbenchReleaseBundleCatalogDiffStateTransition:
    if previous.accepted and not current.accepted:
        return ModuleWorkbenchReleaseBundleCatalogDiffStateTransition.ACCEPTED_TO_BLOCKED
    if not previous.accepted and current.accepted:
        return ModuleWorkbenchReleaseBundleCatalogDiffStateTransition.BLOCKED_TO_ACCEPTED
    if not changes or all(
        item.state_transition is ModuleWorkbenchReleaseBundleCatalogDiffStateTransition.UNCHANGED
        for item in changes
    ):
        return ModuleWorkbenchReleaseBundleCatalogDiffStateTransition.UNCHANGED
    return ModuleWorkbenchReleaseBundleCatalogDiffStateTransition.CHANGED


def build_module_workbench_release_bundle_catalog_diff(
    previous: ModuleWorkbenchReleaseBundleCatalog | bytes | bytearray | str | Path,
    current: ModuleWorkbenchReleaseBundleCatalog | bytes | bytearray | str | Path,
    *,
    diff_id: str = "glio-noncode-module-workbench-release-bundle-catalog-diff",
) -> ModuleWorkbenchReleaseBundleCatalogDiff:
    """Classify bundle references by stable bundle ID and retain field deltas."""

    _text(diff_id, "diff_id")
    previous_catalog = _catalog_context(previous)
    current_catalog = _catalog_context(current)
    previous_map = {item.bundle_id: item for item in previous_catalog.entries}
    current_map = {item.bundle_id: item for item in current_catalog.entries}
    bundle_ids = tuple(sorted(set(previous_map) | set(current_map)))
    if len(bundle_ids) > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_MAX_CHANGES:
        raise ValidationError("catalog diff change limit exceeded")
    changes: list[ModuleWorkbenchReleaseBundleCatalogDiffChange] = []
    for ordinal, bundle_id in enumerate(bundle_ids):
        before = previous_map.get(bundle_id)
        after = current_map.get(bundle_id)
        if before is None:
            changes.append(
                _change(
                    ordinal,
                    bundle_id,
                    ModuleWorkbenchReleaseBundleCatalogDiffChangeKind.ADDED,
                    ModuleWorkbenchReleaseBundleCatalogDiffDirection.CHANGED,
                    ModuleWorkbenchReleaseBundleCatalogDiffStateTransition.ADDED,
                    None,
                    after,
                    ("bundle_added",),
                    "bundle entered the candidate catalog",
                )
            )
            continue
        if after is None:
            changes.append(
                _change(
                    ordinal,
                    bundle_id,
                    ModuleWorkbenchReleaseBundleCatalogDiffChangeKind.REMOVED,
                    ModuleWorkbenchReleaseBundleCatalogDiffDirection.CHANGED,
                    ModuleWorkbenchReleaseBundleCatalogDiffStateTransition.REMOVED,
                    before,
                    None,
                    ("bundle_removed",),
                    "bundle is absent from the candidate catalog",
                )
            )
            continue
        changed_fields = tuple(
            sorted(
                field
                for field, previous_value in _entry_fields(before).items()
                if previous_value != _entry_fields(after).get(field)
            )
        )
        if not changed_fields:
            kind = ModuleWorkbenchReleaseBundleCatalogDiffChangeKind.UNCHANGED
            direction = ModuleWorkbenchReleaseBundleCatalogDiffDirection.UNCHANGED
            transition = ModuleWorkbenchReleaseBundleCatalogDiffStateTransition.UNCHANGED
            detail = "bundle reference is unchanged"
        elif not before.accepted and after.accepted:
            kind = ModuleWorkbenchReleaseBundleCatalogDiffChangeKind.CHANGED
            direction = ModuleWorkbenchReleaseBundleCatalogDiffDirection.IMPROVED
            transition = ModuleWorkbenchReleaseBundleCatalogDiffStateTransition.BLOCKED_TO_ACCEPTED
            detail = "bundle changed from blocked to accepted"
        elif before.accepted and not after.accepted:
            kind = ModuleWorkbenchReleaseBundleCatalogDiffChangeKind.CHANGED
            direction = ModuleWorkbenchReleaseBundleCatalogDiffDirection.REGRESSED
            transition = ModuleWorkbenchReleaseBundleCatalogDiffStateTransition.ACCEPTED_TO_BLOCKED
            detail = "bundle changed from accepted to blocked"
        else:
            kind = ModuleWorkbenchReleaseBundleCatalogDiffChangeKind.CHANGED
            direction = ModuleWorkbenchReleaseBundleCatalogDiffDirection.CHANGED
            transition = ModuleWorkbenchReleaseBundleCatalogDiffStateTransition.CHANGED
            detail = "bundle reference fields changed"
        changes.append(
            _change(
                ordinal,
                bundle_id,
                kind,
                direction,
                transition,
                before,
                after,
                changed_fields,
                detail,
            )
        )
    frozen_changes = tuple(changes)
    body = {
        "diff_id": diff_id,
        "previous_catalog_address": previous_catalog.catalog_address,
        "current_catalog_address": current_catalog.catalog_address,
        "previous_catalog_content_address": previous_catalog.content_address,
        "current_catalog_content_address": current_catalog.content_address,
        "previous_catalog_state": previous_catalog.state.value,
        "current_catalog_state": current_catalog.state.value,
        "changes": frozen_changes,
        "added_count": sum(
            item.kind is ModuleWorkbenchReleaseBundleCatalogDiffChangeKind.ADDED
            for item in frozen_changes
        ),
        "changed_count": sum(
            item.kind is ModuleWorkbenchReleaseBundleCatalogDiffChangeKind.CHANGED
            for item in frozen_changes
        ),
        "removed_count": sum(
            item.kind is ModuleWorkbenchReleaseBundleCatalogDiffChangeKind.REMOVED
            for item in frozen_changes
        ),
        "unchanged_count": sum(
            item.kind is ModuleWorkbenchReleaseBundleCatalogDiffChangeKind.UNCHANGED
            for item in frozen_changes
        ),
        "direction": _aggregate_direction(frozen_changes),
        "state_transition": _aggregate_transition(
            previous_catalog, current_catalog, frozen_changes
        ),
        "accepted": True,
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogDiff(**body, content_address="pending")
    return ModuleWorkbenchReleaseBundleCatalogDiff(
        **body,
        content_address=address_module_workbench_release_bundle_catalog_diff(provisional),
    )


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _change_from_mapping(
    value: Mapping[str, Any],
) -> ModuleWorkbenchReleaseBundleCatalogDiffChange:
    return ModuleWorkbenchReleaseBundleCatalogDiffChange(
        bundle_id=str(value.get("bundle_id", "")),
        ordinal=value.get("ordinal"),
        kind=ModuleWorkbenchReleaseBundleCatalogDiffChangeKind(str(value.get("kind"))),
        direction=ModuleWorkbenchReleaseBundleCatalogDiffDirection(str(value.get("direction"))),
        state_transition=ModuleWorkbenchReleaseBundleCatalogDiffStateTransition(
            str(value.get("state_transition"))
        ),
        previous_entry_address=value.get("previous_entry_address"),
        current_entry_address=value.get("current_entry_address"),
        previous_bundle_address=value.get("previous_bundle_address"),
        current_bundle_address=value.get("current_bundle_address"),
        previous_state=value.get("previous_state"),
        current_state=value.get("current_state"),
        changed_fields=tuple(value.get("changed_fields", ())),
        detail=str(value.get("detail", "")),
        content_address=str(value.get("content_address", "")),
    )


def module_workbench_release_bundle_catalog_diff_from_mapping(
    value: Mapping[str, Any],
) -> ModuleWorkbenchReleaseBundleCatalogDiff:
    raw_changes = value.get("changes")
    if not isinstance(raw_changes, list):
        raise ValidationError("catalog diff changes are invalid")
    changes = tuple(
        _change_from_mapping(_mapping(item, "catalog diff change")) for item in raw_changes
    )
    result = ModuleWorkbenchReleaseBundleCatalogDiff(
        diff_id=str(value.get("diff_id", "")),
        previous_catalog_address=str(value.get("previous_catalog_address", "")),
        current_catalog_address=str(value.get("current_catalog_address", "")),
        previous_catalog_content_address=str(value.get("previous_catalog_content_address", "")),
        current_catalog_content_address=str(value.get("current_catalog_content_address", "")),
        previous_catalog_state=str(value.get("previous_catalog_state", "")),
        current_catalog_state=str(value.get("current_catalog_state", "")),
        changes=changes,
        added_count=value.get("added_count"),
        changed_count=value.get("changed_count"),
        removed_count=value.get("removed_count"),
        unchanged_count=value.get("unchanged_count"),
        direction=ModuleWorkbenchReleaseBundleCatalogDiffDirection(str(value.get("direction"))),
        state_transition=ModuleWorkbenchReleaseBundleCatalogDiffStateTransition(
            str(value.get("state_transition"))
        ),
        accepted=value.get("accepted"),
        content_address=str(value.get("content_address", "")),
    )
    verify_module_workbench_release_bundle_catalog_diff_value(result)
    return result


def load_module_workbench_release_bundle_catalog_diff(
    value: Mapping[str, Any] | bytes | bytearray | str | Path,
) -> ModuleWorkbenchReleaseBundleCatalogDiff:
    if isinstance(value, Mapping):
        return module_workbench_release_bundle_catalog_diff_from_mapping(value)
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
    else:
        raw = read_bytes(value, field="release bundle catalog diff", max_bytes=_MAX_JSON_BYTES)
    try:
        parsed = _strict_json_loads(raw.decode(_UTF8))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValidationError(f"cannot parse release bundle catalog diff: {exc}") from exc
    if not isinstance(parsed, Mapping):
        raise ValidationError("release bundle catalog diff must be a JSON object")
    if raw != (canonical_json(parsed) + "\n").encode(_UTF8):
        raise ValidationError("release bundle catalog diff is not canonical JSON")
    return module_workbench_release_bundle_catalog_diff_from_mapping(parsed)


def _check(
    check_id: str,
    plane: ModuleWorkbenchReleaseBundleCatalogDiffCheckPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleWorkbenchReleaseBundleCatalogDiffCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffCheck(**body, content_address="pending")
    return ModuleWorkbenchReleaseBundleCatalogDiffCheck(
        **body,
        content_address=address_module_workbench_release_bundle_catalog_diff_check(provisional),
    )


def _verification(
    diff_id: str,
    previous_address: str,
    current_address: str,
    change_count: int,
    checks: list[ModuleWorkbenchReleaseBundleCatalogDiffCheck],
) -> ModuleWorkbenchReleaseBundleCatalogDiffVerification:
    ordered = tuple(sorted(checks, key=lambda item: item.check_id))
    body = {
        "diff_id": diff_id,
        "previous_catalog_address": previous_address,
        "current_catalog_address": current_address,
        "change_count": change_count,
        "checks": ordered,
        "accepted": bool(ordered) and all(item.passed for item in ordered),
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffVerification(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffVerification(
        **body,
        content_address=address_module_workbench_release_bundle_catalog_diff_verification(
            provisional
        ),
    )


def _verification_failure(detail: str) -> ModuleWorkbenchReleaseBundleCatalogDiffVerification:
    return _verification(
        "unavailable",
        "unavailable",
        "unavailable",
        0,
        [
            _check(
                "input-readable",
                ModuleWorkbenchReleaseBundleCatalogDiffCheckPlane.INPUT,
                False,
                detail,
                "readable and canonical",
                "comparison input could not be loaded",
            )
        ],
    )


def verify_module_workbench_release_bundle_catalog_diff(
    value: ModuleWorkbenchReleaseBundleCatalogDiff
    | Mapping[str, Any]
    | bytes
    | bytearray
    | str
    | Path,
) -> ModuleWorkbenchReleaseBundleCatalogDiffVerification:
    if not isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiff):
        try:
            value = load_module_workbench_release_bundle_catalog_diff(value)
        except ValidationError as exc:
            return _verification_failure(str(exc))
    checks: list[ModuleWorkbenchReleaseBundleCatalogDiffCheck] = []
    checks.append(
        _check(
            "input-addresses",
            ModuleWorkbenchReleaseBundleCatalogDiffCheckPlane.INPUT,
            bool(value.previous_catalog_address and value.current_catalog_address),
            (value.previous_catalog_address, value.current_catalog_address),
            "two catalog addresses",
            "both baseline and candidate catalogs retain addresses",
        )
    )
    ids = tuple(item.bundle_id for item in value.changes)
    checks.append(
        _check(
            "unique-bundles",
            ModuleWorkbenchReleaseBundleCatalogDiffCheckPlane.CHANGES,
            len(ids) == len(set(ids)),
            sorted({item for item in ids if ids.count(item) > 1}),
            [],
            "bundle identities are classified exactly once",
        )
    )
    address_failures = [
        item.bundle_id
        for item in value.changes
        if address_module_workbench_release_bundle_catalog_diff_change(item) != item.content_address
    ]
    checks.append(
        _check(
            "change-addresses",
            ModuleWorkbenchReleaseBundleCatalogDiffCheckPlane.ADDRESS,
            not address_failures,
            address_failures,
            [],
            "every field-level change has a replayable address",
        )
    )
    counts_ok = (
        value.added_count + value.changed_count + value.removed_count + value.unchanged_count
        == len(value.changes)
    )
    checks.append(
        _check(
            "count-conservation",
            ModuleWorkbenchReleaseBundleCatalogDiffCheckPlane.CHANGES,
            counts_ok,
            len(value.changes),
            value.added_count + value.changed_count + value.removed_count + value.unchanged_count,
            "added, changed, removed, and unchanged counts conserve all identities",
        )
    )
    checks.append(
        _check(
            "direction-replay",
            ModuleWorkbenchReleaseBundleCatalogDiffCheckPlane.CHANGES,
            value.direction is _aggregate_direction(value.changes),
            value.direction.value,
            _aggregate_direction(value.changes).value,
            "aggregate direction is derived from change directions",
        )
    )
    transition = value.state_transition
    state_transition_ok = transition in set(ModuleWorkbenchReleaseBundleCatalogDiffStateTransition)
    checks.append(
        _check(
            "state-transition",
            ModuleWorkbenchReleaseBundleCatalogDiffCheckPlane.CHANGES,
            state_transition_ok,
            transition.value,
            "valid transition",
            "aggregate catalog state transition is explicit",
        )
    )
    checks.append(
        _check(
            "diff-address",
            ModuleWorkbenchReleaseBundleCatalogDiffCheckPlane.ADDRESS,
            address_module_workbench_release_bundle_catalog_diff(value) == value.content_address,
            "conserved",
            "conserved",
            "comparison descriptor address replays from public fields",
        )
    )
    public_ok = not _has_forbidden_key(value.to_dict())
    checks.append(
        _check(
            "public-boundary",
            ModuleWorkbenchReleaseBundleCatalogDiffCheckPlane.PUBLIC,
            public_ok,
            "clean" if public_ok else "forbidden-or-invalid",
            "clean",
            "comparison contains only public source-free evidence",
        )
    )
    return _verification(
        value.diff_id,
        value.previous_catalog_address,
        value.current_catalog_address,
        len(value.changes),
        checks,
    )


def verify_module_workbench_release_bundle_catalog_diff_value(
    value: ModuleWorkbenchReleaseBundleCatalogDiff,
) -> ModuleWorkbenchReleaseBundleCatalogDiff:
    if not isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiff):
        raise ValidationError("typed catalog diff verification requires a diff")
    if address_module_workbench_release_bundle_catalog_diff(value) != value.content_address:
        raise ValidationError("catalog diff descriptor address mismatch")
    return value


def module_workbench_release_bundle_catalog_diff_json(
    value: ModuleWorkbenchReleaseBundleCatalogDiff,
) -> str:
    verify_module_workbench_release_bundle_catalog_diff_value(value)
    return canonical_json(value.to_dict()) + "\n"


def write_module_workbench_release_bundle_catalog_diff(
    value: ModuleWorkbenchReleaseBundleCatalogDiff,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> ModuleWorkbenchReleaseBundleCatalogDiff:
    verify_module_workbench_release_bundle_catalog_diff_value(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("catalog diff destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("catalog diff destination is not a file")
    _validate_parent(path.parent, "catalog diff destination")
    atomic_write_bytes(
        path,
        module_workbench_release_bundle_catalog_diff_json(value).encode(_UTF8),
        field="catalog diff destination",
    )
    return value


def query_module_workbench_release_bundle_catalog_diff(
    value: ModuleWorkbenchReleaseBundleCatalogDiff
    | Mapping[str, Any]
    | bytes
    | bytearray
    | str
    | Path,
    *,
    kind: str | None = None,
    direction: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_DEFAULT_LIMIT,
) -> dict[str, Any]:
    if offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_MAX_LIMIT:
        raise ValidationError("catalog diff paging is invalid")
    if kind is not None and kind not in {
        item.value for item in ModuleWorkbenchReleaseBundleCatalogDiffChangeKind
    }:
        raise ValidationError("catalog diff kind filter is invalid")
    if direction is not None and direction not in {
        item.value for item in ModuleWorkbenchReleaseBundleCatalogDiffDirection
    }:
        raise ValidationError("catalog diff direction filter is invalid")
    diff = (
        value
        if isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiff)
        else load_module_workbench_release_bundle_catalog_diff(value)
    )
    verify_module_workbench_release_bundle_catalog_diff_value(diff)
    rows = [item.to_dict() for item in diff.changes]
    if kind is not None:
        rows = [item for item in rows if item.get("kind") == kind]
    if direction is not None:
        rows = [item for item in rows if item.get("direction") == direction]
    if text:
        rows = [item for item in rows if text.casefold() in canonical_json(item).casefold()]
    body = {
        "diff_address": diff.content_address,
        "previous_catalog_address": diff.previous_catalog_address,
        "current_catalog_address": diff.current_catalog_address,
        "kind": kind,
        "direction": direction,
        "text": text,
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
    }
    return body | {
        "content_address": content_hash(
            body, prefix=MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_QUERY_PREFIX
        )
    }


def module_workbench_release_bundle_catalog_diff_csv(
    value: ModuleWorkbenchReleaseBundleCatalogDiff,
    *,
    kind: str | None = None,
    direction: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_MAX_LIMIT,
) -> str:
    result = query_module_workbench_release_bundle_catalog_diff(
        value,
        kind=kind,
        direction=direction,
        text=text,
        offset=offset,
        limit=limit,
    )
    output = io.StringIO(newline="")
    fields = tuple(sorted({key for row in result["items"] for key in row}))
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(result["items"])
    return output.getvalue()


def render_module_workbench_release_bundle_catalog_diff_markdown(
    value: ModuleWorkbenchReleaseBundleCatalogDiff,
) -> str:
    verify_module_workbench_release_bundle_catalog_diff_value(value)
    lines = [
        "# Module Workbench Release Bundle Catalog Diff",
        "",
        f"- Diff: `{value.diff_id}`",
        f"- Previous catalog: `{value.previous_catalog_address}`",
        f"- Current catalog: `{value.current_catalog_address}`",
        "- Added / changed / removed / unchanged: **"
        f"{value.added_count} / {value.changed_count} / "
        f"{value.removed_count} / {value.unchanged_count}**",
        f"- Direction: `{value.direction.value}`",
        f"- State transition: `{value.state_transition.value}`",
        "",
        "| Bundle | Kind | Direction | Transition | Changed fields |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| `{item.bundle_id}` | `{item.kind.value}` | `{item.direction.value}` "
        f"| `{item.state_transition.value}` | `{', '.join(item.changed_fields)}` |"
        for item in value.changes
    )
    return "\n".join(lines) + "\n"


def module_workbench_release_bundle_catalog_diff_schema() -> dict[str, Any]:
    return {
        "version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_VERSION,
        "boundary": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_BOUNDARY,
        "change_kinds": [item.value for item in ModuleWorkbenchReleaseBundleCatalogDiffChangeKind],
        "directions": [item.value for item in ModuleWorkbenchReleaseBundleCatalogDiffDirection],
        "state_transitions": [
            item.value for item in ModuleWorkbenchReleaseBundleCatalogDiffStateTransition
        ],
        "max_changes": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_MAX_CHANGES,
        "max_checks": 16,
        "source_free": True,
        "path_free": True,
        "timestamp_free": True,
        "payload_free": True,
    }


def module_workbench_release_bundle_catalog_diff_capabilities() -> dict[str, Any]:
    operations = (
        "compare_catalogs",
        "classify_added_changed_removed_unchanged",
        "retain_field_level_deltas",
        "derive_direction",
        "derive_state_transition",
        "verify_change_addresses",
        "query_changes",
        "filter_kind",
        "filter_direction",
        "export_json",
        "export_csv",
        "export_markdown",
    )
    return {
        "version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "source_free": True,
        "path_free": True,
        "timestamp_free": True,
        "payload_free": True,
    }


__all__ = [
    "build_module_workbench_release_bundle_catalog_diff",
    "load_module_workbench_release_bundle_catalog_diff",
    "module_workbench_release_bundle_catalog_diff_capabilities",
    "module_workbench_release_bundle_catalog_diff_csv",
    "module_workbench_release_bundle_catalog_diff_from_mapping",
    "module_workbench_release_bundle_catalog_diff_json",
    "module_workbench_release_bundle_catalog_diff_schema",
    "query_module_workbench_release_bundle_catalog_diff",
    "render_module_workbench_release_bundle_catalog_diff_markdown",
    "verify_module_workbench_release_bundle_catalog_diff",
    "verify_module_workbench_release_bundle_catalog_diff_value",
    "write_module_workbench_release_bundle_catalog_diff",
]
