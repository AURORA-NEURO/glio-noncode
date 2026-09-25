"""Build, verify, query, and persist source-free diffs of module612 catalogs."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_612 as catalog_model
from . import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_613_ct as contract_model
from ._safe_persistence import _validate_parent, atomic_write_text, read_text
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

VERSION = contract_model.VERSION
BOUNDARY = contract_model.BOUNDARY
DIFF_PREFIX = contract_model.DIFF_PREFIX
ITEM_PREFIX = contract_model.ITEM_PREFIX
CHANGES = contract_model.CHANGES
DIRECTIONS = contract_model.DIRECTIONS
POSTURES = contract_model.POSTURES
STATE_TRANSITIONS = contract_model.STATE_TRANSITIONS
SNAPSHOT_FIELDS = contract_model.SNAPSHOT_FIELDS
ITEM_FIELDS = contract_model.ITEM_FIELDS
DIFF_FIELDS = contract_model.DIFF_FIELDS
MAX_ITEMS = contract_model.MAX_ITEMS
MAX_LIMIT = contract_model.MAX_LIMIT
DEFAULT_DIFF_ID = DIFF_PREFIX


def _label(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 256 or value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _rows(catalog: Any) -> dict[str, tuple[dict[str, Any], str]]:
    return {item.entry_id: ({field: item.to_dict()[field] for field in SNAPSHOT_FIELDS}, item.content_address) for item in catalog.entries}


def _transition(left: str, right: str) -> str:
    return "same-" + left if left == right else f"{left}-to-{right}"


def _direction(left: Any, right: Any, active_changes: int) -> str:
    if active_changes == 0:
        return "unchanged"
    left_score = (left.accepted_count, left.ready_count, -left.blocked_count, left.entry_count)
    right_score = (right.accepted_count, right.ready_count, -right.blocked_count, right.entry_count)
    if right_score > left_score:
        return "improved"
    if right_score < left_score:
        return "regressed"
    return "changed"


def _item(ordinal: int, entry_id: str, left: Mapping[str, Any] | None, right: Mapping[str, Any] | None, left_address: str, right_address: str) -> contract_model.DiffItem:
    left_snapshot, right_snapshot = dict(left or {}), dict(right or {})
    changed_fields = tuple(field for field in SNAPSHOT_FIELDS if left_snapshot.get(field) != right_snapshot.get(field))
    change = "added" if left is None else "removed" if right is None else "unchanged" if not changed_fields else "changed"
    body = {"ordinal": ordinal, "entry_id": entry_id, "change": change, "changed_fields": changed_fields, "left_address": left_address if left is not None else "", "right_address": right_address if right is not None else "", "left_snapshot": left_snapshot, "right_snapshot": right_snapshot, "content_address": ITEM_PREFIX + ":pending"}
    provisional = contract_model.DiffItem(**body)
    return contract_model.DiffItem(**(body | {"content_address": contract_model.address_item(provisional)}))


def build_diff(left: Any, right: Any, *, diff_id: str = DEFAULT_DIFF_ID) -> contract_model.Diff:
    left_catalog, right_catalog = catalog_model.verify_catalog(left), catalog_model.verify_catalog(right)
    if left_catalog.catalog_id != right_catalog.catalog_id:
        raise ValidationError("module613 diff requires matching catalog IDs")
    left_rows, right_rows = _rows(left_catalog), _rows(right_catalog)
    entry_ids = sorted(set(left_rows) | set(right_rows))
    if len(entry_ids) > MAX_ITEMS:
        raise ValidationError("module613 diff item count exceeds its bound")
    items = tuple(_item(index, entry_id, left_rows[entry_id][0] if entry_id in left_rows else None, right_rows[entry_id][0] if entry_id in right_rows else None, left_rows[entry_id][1] if entry_id in left_rows else "", right_rows[entry_id][1] if entry_id in right_rows else "") for index, entry_id in enumerate(entry_ids, start=1))
    counts = {change: sum(item.change == change for item in items) for change in CHANGES}
    active = counts["added"] + counts["removed"] + counts["changed"]
    body = {"diff_id": _label(diff_id, "module613 diff ID"), "version": VERSION, "boundary": BOUNDARY, "catalog_id": left_catalog.catalog_id, "left_catalog_address": left_catalog.content_address, "right_catalog_address": right_catalog.content_address, "left_posture": left_catalog.state, "right_posture": right_catalog.state, "state_transition": _transition(left_catalog.state, right_catalog.state), "direction": _direction(left_catalog, right_catalog, active), "added_count": counts["added"], "removed_count": counts["removed"], "changed_count": counts["changed"], "unchanged_count": counts["unchanged"], "items": items, "content_address": DIFF_PREFIX + ":pending"}
    provisional = contract_model.Diff(**body)
    return contract_model.Diff(**(body | {"content_address": contract_model.address_diff(provisional)}))


def _item_from_mapping(value: Mapping[str, Any]) -> contract_model.DiffItem:
    if not isinstance(value, Mapping) or set(value) != set(ITEM_FIELDS):
        raise ValidationError("module613 diff item fields are not exact")
    return contract_model.DiffItem(value["ordinal"], value["entry_id"], value["change"], tuple(value["changed_fields"]), value["left_address"], value["right_address"], dict(value["left_snapshot"]), dict(value["right_snapshot"]), value["content_address"])


def _diff_from_mapping(value: Mapping[str, Any]) -> contract_model.Diff:
    if not isinstance(value, Mapping) or set(value) != set(DIFF_FIELDS):
        raise ValidationError("module613 diff fields are not exact")
    return contract_model.Diff(value["diff_id"], value["version"], value["boundary"], value["catalog_id"], value["left_catalog_address"], value["right_catalog_address"], value["left_posture"], value["right_posture"], value["state_transition"], value["direction"], value["added_count"], value["removed_count"], value["changed_count"], value["unchanged_count"], tuple(_item_from_mapping(item) for item in value["items"]), value["content_address"])


def verify_diff(value: Any) -> contract_model.Diff:
    diff = load_diff(value) if isinstance(value, (str, Path, bytes, bytearray)) else _diff_from_mapping(value) if isinstance(value, Mapping) else value
    if not isinstance(diff, contract_model.Diff) or contract_model.address_diff(diff) != diff.content_address or _has_forbidden_key(diff.to_dict()):
        raise ValidationError("module613 diff address or public boundary does not replay")
    return _diff_from_mapping(diff.to_dict())


def load_diff(value: bytes | bytearray | str | Path | Mapping[str, Any]) -> contract_model.Diff:
    raw = value if isinstance(value, Mapping) else _strict_json_loads(bytes(value).decode("utf-8")) if isinstance(value, (bytes, bytearray)) else _strict_json_loads(read_text(value, field="module613 diff", max_bytes=32 * 1024 * 1024))
    return _diff_from_mapping(raw)


def diff_json(value: Any) -> str:
    return canonical_json(verify_diff(value).to_dict()) + "\n"


def write_diff(value: Any, destination: str | Path, *, allow_existing: bool = False) -> contract_model.Diff:
    diff = verify_diff(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("module613 diff destination already exists")
    _validate_parent(path.parent, "module613 diff destination")
    atomic_write_text(path, diff_json(diff), field="module613 diff destination")
    return diff


def query_diff(value: Any, *, change: str = "", direction: str = "", state_transition: str = "", text: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    diff = verify_diff(value)
    change, direction, state_transition, text = (_text(change, "module613 change", 64, required=False), _text(direction, "module613 direction", 64, required=False), _text(state_transition, "module613 transition", 128, required=False), _text(text, "module613 text", required=False))
    if (change and change not in CHANGES) or (direction and direction not in DIRECTIONS) or (state_transition and state_transition not in STATE_TRANSITIONS) or not isinstance(offset, int) or offset < 0 or not isinstance(limit, int) or limit < 1 or limit > MAX_LIMIT:
        raise ValidationError("module613 query filters are invalid")
    matches = tuple(item for item in diff.items if (not change or item.change == change) and (not direction or diff.direction == direction) and (not state_transition or diff.state_transition == state_transition) and (not text or text.casefold() in " ".join((item.entry_id, item.change, *item.changed_fields)).casefold()))
    selected = matches[offset:offset + limit]
    result = {"diff_address": diff.content_address, "change": change, "direction": direction, "state_transition": state_transition, "text": text, "offset": offset, "limit": limit, "total": len(diff.items), "matched": len(matches), "returned": len(selected), "truncated": offset + len(selected) < len(matches), "items": tuple(item.to_dict() for item in selected)}
    return result | {"content_address": content_hash(result, prefix=DIFF_PREFIX + "-query")}


def diff_csv(value: Any, *, change: str = "", direction: str = "", state_transition: str = "", text: str = "", offset: int = 0, limit: int = 50) -> str:
    result = query_diff(value, change=change, direction=direction, state_transition=state_transition, text=text, offset=offset, limit=limit)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=("ordinal", "entry_id", "change", "changed_fields", "left_address", "right_address", "content_address"), lineterminator="\n")
    writer.writeheader()
    for item in result["items"]:
        writer.writerow({field: ",".join(item[field]) if field == "changed_fields" else item[field] for field in writer.fieldnames})
    return stream.getvalue()


def render_diff_markdown(value: Any) -> str:
    diff = verify_diff(value)
    lines = ["# Module613 Fixed Transport Catalog Diff", "", f"- Catalog ID: `{diff.catalog_id}`", f"- Direction: **{diff.direction}**", f"- State transition: **{diff.state_transition}**", f"- Added / removed / changed / unchanged: **{diff.added_count} / {diff.removed_count} / {diff.changed_count} / {diff.unchanged_count}**", f"- Diff address: `{diff.content_address}`", "", "| # | entry | change | fields |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.entry_id}` | `{item.change}` | {', '.join(item.changed_fields)} |" for item in diff.items)
    return "\n".join(lines) + "\n"


build_catalog_diff = build_diff
verify_catalog_diff = verify_diff
load_catalog_diff = load_diff
catalog_diff_json = diff_json
write_catalog_diff = write_diff
query_catalog_diff = query_diff
catalog_diff_csv = diff_csv
render_catalog_diff_markdown = render_diff_markdown
Diff = contract_model.Diff
DiffItem = contract_model.DiffItem
address_diff = contract_model.address_diff
address_item = contract_model.address_item
capabilities = contract_model.capabilities
diff_schema = contract_model.diff_schema
item_schema = contract_model.item_schema

__all__ = ["BOUNDARY", "CHANGES", "DEFAULT_DIFF_ID", "DIFF_FIELDS", "DIFF_PREFIX", "DIRECTIONS", "ITEM_FIELDS", "ITEM_PREFIX", "MAX_ITEMS", "MAX_LIMIT", "POSTURES", "SNAPSHOT_FIELDS", "STATE_TRANSITIONS", "VERSION", "build_catalog_diff", "build_diff", "capabilities", "catalog_diff_csv", "catalog_diff_json", "diff_csv", "diff_json", "diff_schema", "item_schema", "load_catalog_diff", "load_diff", "query_catalog_diff", "query_diff", "render_catalog_diff_markdown", "render_diff_markdown", "verify_catalog_diff", "verify_diff", "write_catalog_diff", "write_diff"]
