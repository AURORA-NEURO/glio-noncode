"""Content-addressed record transitions between downloaded-data batches."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-ingestion-diff-v1"
BOUNDARY = "public_downloaded_data_ingestion_diff"
DIFF_PREFIX = "glio-noncode-download-ingest-diff"
ITEM_PREFIX = DIFF_PREFIX + "-item"
CHANGES = ("added", "removed", "changed", "unchanged")
MAX_ITEMS = ingestion_model.MAX_RECORDS * 2
CHANGED_FIELDS = ("data_kind", "shape", "fields", "value")
DIFF_FIELDS = (
    "diff_id",
    "version",
    "boundary",
    "left_batch_address",
    "right_batch_address",
    "left_record_count",
    "right_record_count",
    "added_count",
    "removed_count",
    "changed_count",
    "unchanged_count",
    "items",
    "content_address",
)
ITEM_FIELDS = (
    "ordinal",
    "change",
    "record_key",
    "member_name",
    "source_row",
    "changed_fields",
    "left_record_address",
    "right_record_address",
    "left_value",
    "right_value",
    "content_address",
)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 256)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or ":" not in value:
        raise ValidationError(f"{field} must be a content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


def _key(value: Any) -> str:
    value = _text(value, "diff record key", 2048)
    if value.startswith("/") or "\\" in value:
        raise ValidationError("diff record key is not a safe public key")
    return value


class DownloadedDataIngestionDiffItem:
    """One added, removed, changed, or unchanged record transition."""

    FIELDS = ITEM_FIELDS

    def __init__(self, ordinal: int, change: str, record_key: str, member_name: str, source_row: int, changed_fields: Sequence[str], left_record_address: str, right_record_address: str, left_value: Any, right_value: Any, content_address: str) -> None:
        self.ordinal = _count(ordinal, "diff item ordinal", MAX_ITEMS)
        if self.ordinal == 0:
            raise ValidationError("diff item ordinal must be positive")
        self.change = _label(change, "diff item change")
        if self.change not in CHANGES:
            raise ValidationError("diff item change is unsupported")
        self.record_key = _key(record_key)
        self.member_name = ingestion_model._safe_member_name(member_name)
        self.source_row = _count(source_row, "diff item source row", ingestion_model.MAX_RECORDS, positive=True)
        self.changed_fields = tuple(_label(item, "diff changed field") for item in _sequence(changed_fields, "diff changed fields", len(CHANGED_FIELDS)))
        if len(set(self.changed_fields)) != len(self.changed_fields) or any(item not in CHANGED_FIELDS for item in self.changed_fields):
            raise ValidationError("diff changed fields are unsupported or duplicated")
        self.left_record_address = _address(left_record_address, "diff left record address", ingestion_model.RECORD_PREFIX) if left_record_address else ""
        self.right_record_address = _address(right_record_address, "diff right record address", ingestion_model.RECORD_PREFIX) if right_record_address else ""
        self.left_value = None if left_value is None else ingestion_model._validated_value(left_value, "diff left value")
        self.right_value = None if right_value is None else ingestion_model._validated_value(right_value, "diff right value")
        self.content_address = _address(content_address, "diff item address", ITEM_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "diff item address")
        self._validate()

    def _validate(self) -> None:
        if self.change == "added" and (self.left_record_address or self.left_value is not None or not self.right_record_address):
            raise ValidationError("added diff item has invalid left side")
        if self.change == "removed" and (not self.left_record_address or self.left_value is None or self.right_record_address or self.right_value is not None):
            raise ValidationError("removed diff item has invalid right side")
        if self.change == "changed" and (not self.left_record_address or not self.right_record_address or self.left_value is None or self.right_value is None or not self.changed_fields):
            raise ValidationError("changed diff item is incomplete")
        if self.change == "unchanged" and (not self.left_record_address or not self.right_record_address or self.left_value is not None or self.right_value is not None or self.changed_fields):
            raise ValidationError("unchanged diff item has transition fields")
        if self.change == "added" and self.right_value is None:
            raise ValidationError("added diff item must retain the right value")
        if not _public(self.to_dict()):
            raise ValidationError("diff item crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_item(self) != self.content_address:
            raise ValidationError("diff item address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"left_value", "right_value"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataIngestionDiffItem:
        value = _mapping(value, "downloaded ingestion diff item")
        _strict(value, set(cls.FIELDS), "downloaded ingestion diff item")
        return cls(*(value[field] for field in cls.FIELDS))


def address_item(value: DownloadedDataIngestionDiffItem) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ITEM_PREFIX)


class DownloadedDataIngestionDiff:
    """Complete deterministic transition between two ingestion batches."""

    FIELDS = DIFF_FIELDS

    def __init__(self, diff_id: str, version: str, boundary: str, left_batch_address: str, right_batch_address: str, left_record_count: int, right_record_count: int, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, items: Sequence[DownloadedDataIngestionDiffItem | Mapping[str, Any]], content_address: str) -> None:
        self.diff_id = _label(diff_id, "diff ID")
        self.version = _text(version, "diff version")
        self.boundary = _text(boundary, "diff boundary", 512)
        self.left_batch_address = _address(left_batch_address, "left batch address", ingestion_model.INGEST_PREFIX)
        self.right_batch_address = _address(right_batch_address, "right batch address", ingestion_model.INGEST_PREFIX)
        self.left_record_count = _count(left_record_count, "left record count", ingestion_model.MAX_RECORDS)
        self.right_record_count = _count(right_record_count, "right record count", ingestion_model.MAX_RECORDS)
        self.added_count = _count(added_count, "added count", MAX_ITEMS)
        self.removed_count = _count(removed_count, "removed count", MAX_ITEMS)
        self.changed_count = _count(changed_count, "changed count", MAX_ITEMS)
        self.unchanged_count = _count(unchanged_count, "unchanged count", MAX_ITEMS)
        self.items = tuple(item if isinstance(item, DownloadedDataIngestionDiffItem) else DownloadedDataIngestionDiffItem.from_mapping(item) for item in _sequence(items, "diff items", MAX_ITEMS))
        self.content_address = _address(content_address, "diff address", DIFF_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "diff address")
        self._validate()

    def _validate(self) -> None:
        if len(self.items) != self.added_count + self.removed_count + self.changed_count + self.unchanged_count or tuple(item.ordinal for item in self.items) != tuple(range(1, len(self.items) + 1)) or self.added_count != sum(item.change == "added" for item in self.items) or self.removed_count != sum(item.change == "removed" for item in self.items) or self.changed_count != sum(item.change == "changed" for item in self.items) or self.unchanged_count != sum(item.change == "unchanged" for item in self.items) or self.left_record_count != self.removed_count + self.changed_count + self.unchanged_count or self.right_record_count != self.added_count + self.changed_count + self.unchanged_count:
            raise ValidationError("diff counts or item order do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("diff crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_diff(self) != self.content_address:
            raise ValidationError("diff address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "version": self.version, "boundary": self.boundary, "left_batch_address": self.left_batch_address, "right_batch_address": self.right_batch_address, "left_record_count": self.left_record_count, "right_record_count": self.right_record_count, "added_count": self.added_count, "removed_count": self.removed_count, "changed_count": self.changed_count, "unchanged_count": self.unchanged_count, "items": tuple(item.to_dict() for item in self.items), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "items"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataIngestionDiff:
        value = _mapping(value, "downloaded ingestion diff")
        _strict(value, set(cls.FIELDS), "downloaded ingestion diff")
        return cls(*(value[field] for field in cls.FIELDS))


def address_diff(value: DownloadedDataIngestionDiff) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


def _record_key(record: ingestion_model.DownloadedDataRecord) -> str:
    return f"{record.lineage.member_name}#{record.lineage.source_row}"


def _changed_fields(left: ingestion_model.DownloadedDataRecord, right: ingestion_model.DownloadedDataRecord) -> tuple[str, ...]:
    return tuple(field for field in CHANGED_FIELDS if getattr(left, field) != getattr(right, field))


def _item(ordinal: int, change: str, key: str, left: ingestion_model.DownloadedDataRecord | None, right: ingestion_model.DownloadedDataRecord | None) -> DownloadedDataIngestionDiffItem:
    record = right or left
    if record is None:
        raise ValidationError("diff item requires at least one record")
    body = {"ordinal": ordinal, "change": change, "record_key": key, "member_name": record.lineage.member_name, "source_row": record.lineage.source_row, "changed_fields": _changed_fields(left, right) if left and right else (), "left_record_address": left.content_address if left else "", "right_record_address": right.content_address if right else "", "left_value": left.value if left and change == "changed" else None, "right_value": right.value if right and change in {"added", "changed"} else None}
    provisional = DownloadedDataIngestionDiffItem(**body, content_address=ITEM_PREFIX + ":pending")
    return DownloadedDataIngestionDiffItem(**body, content_address=address_item(provisional))


def build_diff(left: ingestion_model.DownloadedDataIngestBatch, right: ingestion_model.DownloadedDataIngestBatch, *, diff_id: str = "glio-noncode-downloaded-data-diff") -> DownloadedDataIngestionDiff:
    if not isinstance(left, ingestion_model.DownloadedDataIngestBatch) or not isinstance(right, ingestion_model.DownloadedDataIngestBatch):
        raise ValidationError("diff requires typed ingestion batches")
    left_map = {_record_key(record): record for record in left.records}
    right_map = {_record_key(record): record for record in right.records}
    if len(left_map) != len(left.records) or len(right_map) != len(right.records):
        raise ValidationError("diff inputs contain duplicate record keys")
    items: list[DownloadedDataIngestionDiffItem] = []
    for ordinal, key in enumerate(sorted(set(left_map) | set(right_map)), 1):
        before, after = left_map.get(key), right_map.get(key)
        change = "added" if before is None else "removed" if after is None else "changed" if _changed_fields(before, after) else "unchanged"
        items.append(_item(ordinal, change, key, before, after))
    body = {"diff_id": diff_id, "version": VERSION, "boundary": BOUNDARY, "left_batch_address": left.content_address, "right_batch_address": right.content_address, "left_record_count": left.record_count, "right_record_count": right.record_count, "added_count": sum(item.change == "added" for item in items), "removed_count": sum(item.change == "removed" for item in items), "changed_count": sum(item.change == "changed" for item in items), "unchanged_count": sum(item.change == "unchanged" for item in items), "items": tuple(items)}
    provisional = DownloadedDataIngestionDiff(**body, content_address=DIFF_PREFIX + ":pending")
    return DownloadedDataIngestionDiff(**body, content_address=address_diff(provisional))


def diff_from_mapping(value: Mapping[str, Any]) -> DownloadedDataIngestionDiff:
    return DownloadedDataIngestionDiff.from_mapping(value)


def diff_json(value: DownloadedDataIngestionDiff) -> str:
    return canonical_json(DownloadedDataIngestionDiff.from_mapping(value.to_dict()).to_dict())


def diff_csv(value: DownloadedDataIngestionDiff) -> str:
    value = DownloadedDataIngestionDiff.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(ITEM_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] if field not in {"changed_fields", "left_value", "right_value"} else (";".join(item.changed_fields) if field == "changed_fields" else canonical_json(item.to_dict()[field]) if item.to_dict()[field] is not None else "") for field in ITEM_FIELDS) for item in value.items)
    return stream.getvalue()


def render_diff_markdown(value: DownloadedDataIngestionDiff) -> str:
    value = DownloadedDataIngestionDiff.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Ingestion Diff", "", f"- Left batch: `{value.left_batch_address}`", f"- Right batch: `{value.right_batch_address}`", f"- Added: `{value.added_count}`", f"- Removed: `{value.removed_count}`", f"- Changed: `{value.changed_count}`", f"- Unchanged: `{value.unchanged_count}`", f"- Address: `{value.content_address}`", "", "| # | change | member | row | key |", "| ---: | --- | --- | ---: | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.change}` | `{item.member_name}` | {item.source_row} | `{item.record_key}` |" for item in value.items)
    return "\n".join(lines) + "\n"


def item_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data ingestion diff item", "type": "object", "additionalProperties": False, "required": list(ITEM_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "change": {"enum": list(CHANGES)}, "record_key": {"type": "string"}, "member_name": {"type": "string"}, "source_row": {"type": "integer", "minimum": 1}, "changed_fields": {"type": "array", "items": {"enum": list(CHANGED_FIELDS)}}, "left_record_address": {"type": "string"}, "right_record_address": {"type": "string"}, "left_value": {}, "right_value": {}, "content_address": {"type": "string"}}}


def diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data ingestion diff", "type": "object", "additionalProperties": False, "required": list(DIFF_FIELDS), "properties": {"diff_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "left_batch_address": {"type": "string"}, "right_batch_address": {"type": "string"}, "left_record_count": {"type": "integer", "minimum": 0}, "right_record_count": {"type": "integer", "minimum": 0}, "added_count": {"type": "integer", "minimum": 0}, "removed_count": {"type": "integer", "minimum": 0}, "changed_count": {"type": "integer", "minimum": 0}, "unchanged_count": {"type": "integer", "minimum": 0}, "items": {"type": "array", "items": item_schema()}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "version": VERSION, "changes": CHANGES, "changed_fields": CHANGED_FIELDS, "operations": ("build_diff", "diff_from_mapping", "diff_json", "diff_csv", "render_diff_markdown")}


__all__ = ["BOUNDARY", "CHANGED_FIELDS", "CHANGES", "DIFF_FIELDS", "DIFF_PREFIX", "ITEM_FIELDS", "DownloadedDataIngestionDiff", "DownloadedDataIngestionDiffItem", "address_diff", "address_item", "build_diff", "capabilities", "diff_csv", "diff_from_mapping", "diff_json", "diff_schema", "item_schema", "render_diff_markdown"]
