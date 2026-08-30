"""Bounded structural profiling for an ingested downloaded-data batch.

The ingestion boundary preserves the source values so that they can be
replayed exactly.  This module adds a separate, value-free inspection plane:
it counts shapes, value types, field presence, serialized sizes, and bounded
distinct-value estimates without copying source values into the profile.  A
profile is therefore useful for deciding what a download contains while
remaining a public structural summary rather than an interpretation engine.
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-v1"
BOUNDARY = "public_downloaded_data_profile"
PROFILE_PREFIX = "glio-noncode-download-profile"
TYPE_PREFIX = PROFILE_PREFIX + "-type"
SHAPE_PREFIX = PROFILE_PREFIX + "-shape"
FIELD_PREFIX = PROFILE_PREFIX + "-field"
MEMBER_PREFIX = PROFILE_PREFIX + "-member"
VALUE_DIGEST_PREFIX = PROFILE_PREFIX + "-value-digest"
MAX_MEMBERS = ingestion_model.MAX_SELECTED_MEMBERS
MAX_RECORDS = ingestion_model.MAX_RECORDS
MAX_TOTAL_RECORDS = ingestion_model.MAX_TOTAL_RECORDS
MAX_FIELDS = 50_000
MAX_DISTINCT_VALUES = 4_096
MAX_TYPE_COUNTS = 7
MAX_SHAPE_COUNTS = 16
VALUE_TYPES = ("null", "boolean", "integer", "number", "string", "array", "object")
SHAPES = ("object", "array", "scalar", "line", "table", "document")

TYPE_COUNT_FIELDS = ("value_type", "count", "content_address")
SHAPE_COUNT_FIELDS = ("shape", "count", "content_address")
FIELD_PROFILE_FIELDS = (
    "field_name",
    "observed_count",
    "missing_count",
    "null_count",
    "type_counts",
    "distinct_value_count",
    "distinct_truncated",
    "min_value_size",
    "max_value_size",
    "content_address",
)
MEMBER_PROFILE_FIELDS = (
    "member_name",
    "member_address",
    "member_ordinal",
    "data_kind",
    "record_count",
    "shape_counts",
    "field_count",
    "fields",
    "content_address",
)
PROFILE_FIELDS = (
    "profile_id",
    "version",
    "boundary",
    "batch_address",
    "record_count",
    "member_count",
    "field_count",
    "total_value_bytes",
    "type_counts",
    "members",
    "fields",
    "content_address",
)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, ingestion_model.MAX_IDENTIFIER, required=True)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048, required=True)
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


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


def _value_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, Mapping):
        return "object"
    if isinstance(value, (tuple, list)):
        return "array"
    raise ValidationError("profile encountered an unsupported value type")


def _replayed_or_pending(value: Any, field: str, prefix: str) -> str:
    if isinstance(value, str) and value.endswith(":pending"):
        return _text(value, field)
    return _address(value, field, prefix)


class DownloadedDataTypeCount:
    """Count of one JSON-compatible value type."""

    FIELDS = TYPE_COUNT_FIELDS

    def __init__(self, value_type: str, count: int, content_address: str) -> None:
        self.value_type = _label(value_type, "profile value type")
        if self.value_type not in VALUE_TYPES:
            raise ValidationError("profile value type is unsupported")
        self.count = _count(count, "profile type count", MAX_TOTAL_RECORDS)
        self.content_address = _replayed_or_pending(content_address, "profile type address", TYPE_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("profile type count crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_type_count(self) != self.content_address:
            raise ValidationError("profile type count address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataTypeCount:
        value = _mapping(value, "profile type count")
        _strict(value, set(cls.FIELDS), "profile type count")
        return cls(value["value_type"], value["count"], value["content_address"])


def address_type_count(value: DownloadedDataTypeCount) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=TYPE_PREFIX)


class DownloadedDataShapeCount:
    """Count of one parser shape within one archive member."""

    FIELDS = SHAPE_COUNT_FIELDS

    def __init__(self, shape: str, count: int, content_address: str) -> None:
        self.shape = _label(shape, "profile shape")
        if self.shape not in SHAPES:
            raise ValidationError("profile shape is unsupported")
        self.count = _count(count, "profile shape count", MAX_RECORDS)
        self.content_address = _replayed_or_pending(content_address, "profile shape address", SHAPE_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("profile shape count crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_shape_count(self) != self.content_address:
            raise ValidationError("profile shape count address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataShapeCount:
        value = _mapping(value, "profile shape count")
        _strict(value, set(cls.FIELDS), "profile shape count")
        return cls(value["shape"], value["count"], value["content_address"])


def address_shape_count(value: DownloadedDataShapeCount) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=SHAPE_PREFIX)


class DownloadedDataFieldProfile:
    """Value-free field presence, type, size, and bounded-cardinality summary."""

    FIELDS = FIELD_PROFILE_FIELDS

    def __init__(self, field_name: str, observed_count: int, missing_count: int, null_count: int, type_counts: Sequence[DownloadedDataTypeCount | Mapping[str, Any]], distinct_value_count: int, distinct_truncated: bool, min_value_size: int, max_value_size: int, content_address: str) -> None:
        self.field_name = ingestion_model._key(field_name, "profile field name")
        self.observed_count = _count(observed_count, "profile observed count", MAX_TOTAL_RECORDS)
        self.missing_count = _count(missing_count, "profile missing count", MAX_TOTAL_RECORDS)
        self.null_count = _count(null_count, "profile null count", MAX_TOTAL_RECORDS)
        self.type_counts = tuple(item if isinstance(item, DownloadedDataTypeCount) else DownloadedDataTypeCount.from_mapping(item) for item in _sequence(type_counts, "profile field type counts", MAX_TYPE_COUNTS))
        self.distinct_value_count = _count(distinct_value_count, "profile distinct value count", MAX_DISTINCT_VALUES)
        self.distinct_truncated = _bool(distinct_truncated, "profile distinct truncation")
        self.min_value_size = _count(min_value_size, "profile minimum value size", ingestion_model.MAX_RECORD_BYTES)
        self.max_value_size = _count(max_value_size, "profile maximum value size", ingestion_model.MAX_RECORD_BYTES)
        self.content_address = _replayed_or_pending(content_address, "profile field address", FIELD_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if tuple(item.value_type for item in self.type_counts) != VALUE_TYPES:
            raise ValidationError("profile field type counts are not canonical")
        if sum(item.count for item in self.type_counts) != self.observed_count or self.null_count != self.type_counts[0].count:
            raise ValidationError("profile field counts do not conserve observations")
        if self.missing_count and self.missing_count + self.observed_count > MAX_TOTAL_RECORDS:
            raise ValidationError("profile field total count exceeds bound")
        if self.observed_count == 0 and (self.distinct_value_count or self.distinct_truncated or self.min_value_size or self.max_value_size):
            raise ValidationError("empty profile field has value statistics")
        if self.min_value_size > self.max_value_size or (self.observed_count and self.min_value_size == 0):
            raise ValidationError("profile field size range does not replay")
        if self.distinct_truncated and self.distinct_value_count != MAX_DISTINCT_VALUES:
            raise ValidationError("truncated distinct profile must retain its cap")
        if not _public(self.to_dict()):
            raise ValidationError("profile field crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_field(self) != self.content_address:
            raise ValidationError("profile field address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "observed_count": self.observed_count,
            "missing_count": self.missing_count,
            "null_count": self.null_count,
            "type_counts": tuple(item.to_dict() for item in self.type_counts),
            "distinct_value_count": self.distinct_value_count,
            "distinct_truncated": self.distinct_truncated,
            "min_value_size": self.min_value_size,
            "max_value_size": self.max_value_size,
            "content_address": self.content_address,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataFieldProfile:
        value = _mapping(value, "profile field")
        _strict(value, set(cls.FIELDS), "profile field")
        return cls(*(value[field] for field in cls.FIELDS))


def address_field(value: DownloadedDataFieldProfile) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FIELD_PREFIX)


class DownloadedDataMemberProfile:
    """Structural profile for one selected archive member."""

    FIELDS = MEMBER_PROFILE_FIELDS

    def __init__(self, member_name: str, member_address: str, member_ordinal: int, data_kind: str, record_count: int, shape_counts: Sequence[DownloadedDataShapeCount | Mapping[str, Any]], field_count: int, fields: Sequence[DownloadedDataFieldProfile | Mapping[str, Any]], content_address: str) -> None:
        self.member_name = ingestion_model._safe_member_name(member_name, "profile member name")
        self.member_address = _address(member_address, "profile member address", "glio-noncode-download-catalog-member")
        self.member_ordinal = _count(member_ordinal, "profile member ordinal", MAX_MEMBERS, positive=True)
        self.data_kind = _label(data_kind, "profile member data kind")
        if self.data_kind not in ingestion_model.DATA_KINDS:
            raise ValidationError("profile member data kind is unsupported")
        self.record_count = _count(record_count, "profile member record count", MAX_RECORDS)
        self.shape_counts = tuple(item if isinstance(item, DownloadedDataShapeCount) else DownloadedDataShapeCount.from_mapping(item) for item in _sequence(shape_counts, "profile member shape counts", MAX_SHAPE_COUNTS))
        self.field_count = _count(field_count, "profile member field count", MAX_FIELDS)
        self.fields = tuple(item if isinstance(item, DownloadedDataFieldProfile) else DownloadedDataFieldProfile.from_mapping(item) for item in _sequence(fields, "profile member fields", MAX_FIELDS))
        self.content_address = _replayed_or_pending(content_address, "profile member address", MEMBER_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if tuple(item.shape for item in self.shape_counts) != tuple(shape for shape in SHAPES if any(item.shape == shape for item in self.shape_counts)):
            raise ValidationError("profile member shape counts are not canonical")
        if sum(item.count for item in self.shape_counts) != self.record_count or self.field_count != len(self.fields):
            raise ValidationError("profile member aggregates do not replay")
        if tuple(item.field_name for item in self.fields) != tuple(sorted(item.field_name for item in self.fields)) or len({item.field_name for item in self.fields}) != len(self.fields):
            raise ValidationError("profile member fields are not unique and sorted")
        if any(item.observed_count > self.record_count or item.missing_count + item.observed_count != self.record_count for item in self.fields):
            raise ValidationError("profile member field presence counts do not replay")
        if not _public(self.to_dict()):
            raise ValidationError("profile member crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_member(self) != self.content_address:
            raise ValidationError("profile member address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {
            "member_name": self.member_name,
            "member_address": self.member_address,
            "member_ordinal": self.member_ordinal,
            "data_kind": self.data_kind,
            "record_count": self.record_count,
            "shape_counts": tuple(item.to_dict() for item in self.shape_counts),
            "field_count": self.field_count,
            "fields": tuple(item.to_dict() for item in self.fields),
            "content_address": self.content_address,
        }

    def field(self, field_name: str) -> DownloadedDataFieldProfile:
        field_name = ingestion_model._key(field_name, "profile field lookup")
        for item in self.fields:
            if item.field_name == field_name:
                return item
        raise ValidationError("profile field was not found")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataMemberProfile:
        value = _mapping(value, "profile member")
        _strict(value, set(cls.FIELDS), "profile member")
        return cls(*(value[field] for field in cls.FIELDS))


def address_member(value: DownloadedDataMemberProfile) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MEMBER_PREFIX)


class DownloadedDataProfile:
    """Content-addressed value-free structural profile of one ingestion batch."""

    FIELDS = PROFILE_FIELDS

    def __init__(self, profile_id: str, version: str, boundary: str, batch_address: str, record_count: int, member_count: int, field_count: int, total_value_bytes: int, type_counts: Sequence[DownloadedDataTypeCount | Mapping[str, Any]], members: Sequence[DownloadedDataMemberProfile | Mapping[str, Any]], fields: Sequence[DownloadedDataFieldProfile | Mapping[str, Any]], content_address: str) -> None:
        self.profile_id = _label(profile_id, "profile ID")
        self.version = _text(version, "profile version", required=True)
        self.boundary = _text(boundary, "profile boundary", 512, required=True)
        self.batch_address = _address(batch_address, "profile batch address", ingestion_model.INGEST_PREFIX)
        self.record_count = _count(record_count, "profile record count", MAX_RECORDS)
        self.member_count = _count(member_count, "profile member count", MAX_MEMBERS)
        self.field_count = _count(field_count, "profile field count", MAX_FIELDS)
        self.total_value_bytes = _count(total_value_bytes, "profile total value bytes", MAX_TOTAL_RECORDS * ingestion_model.MAX_RECORD_BYTES)
        self.type_counts = tuple(item if isinstance(item, DownloadedDataTypeCount) else DownloadedDataTypeCount.from_mapping(item) for item in _sequence(type_counts, "profile type counts", MAX_TYPE_COUNTS))
        self.members = tuple(item if isinstance(item, DownloadedDataMemberProfile) else DownloadedDataMemberProfile.from_mapping(item) for item in _sequence(members, "profile members", MAX_MEMBERS))
        self.fields = tuple(item if isinstance(item, DownloadedDataFieldProfile) else DownloadedDataFieldProfile.from_mapping(item) for item in _sequence(fields, "profile fields", MAX_FIELDS))
        self.content_address = _replayed_or_pending(content_address, "profile address", PROFILE_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("profile version or boundary is not current")
        if tuple(item.value_type for item in self.type_counts) != VALUE_TYPES or sum(item.count for item in self.type_counts) != self.record_count:
            raise ValidationError("profile type totals do not replay")
        if self.member_count != len(self.members) or self.field_count != len(self.fields) or sum(item.record_count for item in self.members) != self.record_count:
            raise ValidationError("profile member or field totals do not replay")
        if tuple(item.member_ordinal for item in self.members) != tuple(sorted(item.member_ordinal for item in self.members)) or len({item.member_name for item in self.members}) != self.member_count:
            raise ValidationError("profile members are not unique and ordered")
        if tuple(item.field_name for item in self.fields) != tuple(sorted(item.field_name for item in self.fields)) or len({item.field_name for item in self.fields}) != self.field_count:
            raise ValidationError("profile fields are not unique and ordered")
        if not _public(self.to_dict()):
            raise ValidationError("profile crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_profile(self) != self.content_address:
            raise ValidationError("profile address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "version": self.version,
            "boundary": self.boundary,
            "batch_address": self.batch_address,
            "record_count": self.record_count,
            "member_count": self.member_count,
            "field_count": self.field_count,
            "total_value_bytes": self.total_value_bytes,
            "type_counts": tuple(item.to_dict() for item in self.type_counts),
            "members": tuple(item.to_dict() for item in self.members),
            "fields": tuple(item.to_dict() for item in self.fields),
            "content_address": self.content_address,
        }

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"type_counts", "members", "fields"}}

    def member(self, member_name: str) -> DownloadedDataMemberProfile:
        member_name = ingestion_model._safe_member_name(member_name, "profile member lookup")
        for item in self.members:
            if item.member_name == member_name:
                return item
        raise ValidationError("profile member was not found")

    def field(self, field_name: str) -> DownloadedDataFieldProfile:
        field_name = ingestion_model._key(field_name, "profile field lookup")
        for item in self.fields:
            if item.field_name == field_name:
                return item
        raise ValidationError("profile field was not found")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfile:
        value = _mapping(value, "downloaded data profile")
        _strict(value, set(cls.FIELDS), "downloaded data profile")
        return cls(*(value[field] for field in cls.FIELDS))


def address_profile(value: DownloadedDataProfile) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=PROFILE_PREFIX)


def _new_accumulator() -> dict[str, Any]:
    return {"observed": 0, "null": 0, "types": Counter(), "distinct": set(), "truncated": False, "min": 0, "max": 0}


def _add_value(accumulator: dict[str, Any], value: Any) -> None:
    kind = _value_type(value)
    size = len(canonical_json(value).encode("utf-8"))
    accumulator["observed"] += 1
    accumulator["types"][kind] += 1
    if kind == "null":
        accumulator["null"] += 1
    if not accumulator["truncated"]:
        accumulator["distinct"].add(content_hash(value, prefix=VALUE_DIGEST_PREFIX))
        if len(accumulator["distinct"]) > MAX_DISTINCT_VALUES:
            accumulator["distinct"] = set(list(accumulator["distinct"])[:MAX_DISTINCT_VALUES])
            accumulator["truncated"] = True
    accumulator["min"] = size if accumulator["observed"] == 1 else min(accumulator["min"], size)
    accumulator["max"] = max(accumulator["max"], size)


def _type_counts(counter: Counter[str]) -> tuple[DownloadedDataTypeCount, ...]:
    result = []
    for value_type in VALUE_TYPES:
        body = {"value_type": value_type, "count": counter[value_type], "content_address": TYPE_PREFIX + ":pending"}
        provisional = DownloadedDataTypeCount(**body)
        result.append(DownloadedDataTypeCount(**(body | {"content_address": address_type_count(provisional)})))
    return tuple(result)


def _shape_counts(counter: Counter[str]) -> tuple[DownloadedDataShapeCount, ...]:
    result = []
    for shape in SHAPES:
        if not counter[shape]:
            continue
        body = {"shape": shape, "count": counter[shape], "content_address": SHAPE_PREFIX + ":pending"}
        provisional = DownloadedDataShapeCount(**body)
        result.append(DownloadedDataShapeCount(**(body | {"content_address": address_shape_count(provisional)})))
    return tuple(result)


def _field_profile(field_name: str, accumulator: dict[str, Any], total_records: int) -> DownloadedDataFieldProfile:
    body = {
        "field_name": field_name,
        "observed_count": accumulator["observed"],
        "missing_count": total_records - accumulator["observed"],
        "null_count": accumulator["null"],
        "type_counts": _type_counts(accumulator["types"]),
        "distinct_value_count": len(accumulator["distinct"]),
        "distinct_truncated": accumulator["truncated"],
        "min_value_size": accumulator["min"],
        "max_value_size": accumulator["max"],
        "content_address": FIELD_PREFIX + ":pending",
    }
    provisional = DownloadedDataFieldProfile(**body)
    return DownloadedDataFieldProfile(**(body | {"content_address": address_field(provisional)}))


def _record_field_values(record: ingestion_model.DownloadedDataRecord) -> tuple[tuple[str, Any], ...]:
    if not isinstance(record.value, Mapping):
        return ()
    return tuple((field_name, record.value[field_name]) for field_name in record.fields if field_name in record.value)


def build_profile(batch: ingestion_model.DownloadedDataIngestBatch, *, profile_id: str = "glio-noncode-downloaded-data-profile") -> DownloadedDataProfile:
    """Build a value-free profile from a typed ingestion batch."""

    if not isinstance(batch, ingestion_model.DownloadedDataIngestBatch):
        raise ValidationError("profile requires a typed downloaded data ingestion batch")
    member_records: dict[str, list[ingestion_model.DownloadedDataRecord]] = {}
    member_meta: dict[str, tuple[str, str, int]] = {}
    global_fields: dict[str, dict[str, Any]] = {}
    total_types: Counter[str] = Counter()
    total_value_bytes = 0
    for record in batch.records:
        member_key = record.lineage.member_address
        member_records.setdefault(member_key, []).append(record)
        metadata = (record.lineage.member_name, member_key, record.lineage.member_ordinal)
        if member_key in member_meta and member_meta[member_key] != metadata:
            raise ValidationError("batch member lineage is inconsistent")
        member_meta[member_key] = metadata
        total_types[_value_type(record.value)] += 1
        total_value_bytes += record.value_size
        for field_name, value in _record_field_values(record):
            global_fields.setdefault(field_name, _new_accumulator())
            _add_value(global_fields[field_name], value)
    member_profiles = []
    for member_key in sorted(member_records, key=lambda key: member_meta[key][2]):
        records = member_records[member_key]
        member_name, _, member_ordinal = member_meta[member_key]
        shapes = Counter(record.shape for record in records)
        member_fields: dict[str, dict[str, Any]] = {}
        for record in records:
            for field_name, value in _record_field_values(record):
                member_fields.setdefault(field_name, _new_accumulator())
                _add_value(member_fields[field_name], value)
        fields = tuple(_field_profile(name, member_fields[name], len(records)) for name in sorted(member_fields))
        body = {
            "member_name": member_name,
            "member_address": member_key,
            "member_ordinal": member_ordinal,
            "data_kind": records[0].data_kind,
            "record_count": len(records),
            "shape_counts": _shape_counts(shapes),
            "field_count": len(fields),
            "fields": fields,
            "content_address": MEMBER_PREFIX + ":pending",
        }
        provisional = DownloadedDataMemberProfile(**body)
        member_profiles.append(DownloadedDataMemberProfile(**(body | {"content_address": address_member(provisional)})))
    fields = tuple(_field_profile(name, global_fields[name], batch.record_count) for name in sorted(global_fields))
    body = {
        "profile_id": profile_id,
        "version": VERSION,
        "boundary": BOUNDARY,
        "batch_address": batch.content_address,
        "record_count": batch.record_count,
        "member_count": len(member_profiles),
        "field_count": len(fields),
        "total_value_bytes": total_value_bytes,
        "type_counts": _type_counts(total_types),
        "members": tuple(member_profiles),
        "fields": fields,
        "content_address": PROFILE_PREFIX + ":pending",
    }
    provisional = DownloadedDataProfile(**body)
    return DownloadedDataProfile(**(body | {"content_address": address_profile(provisional)}))


def profile_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfile:
    return DownloadedDataProfile.from_mapping(value)


def profile_json(value: DownloadedDataProfile) -> str:
    return canonical_json(DownloadedDataProfile.from_mapping(value.to_dict()).to_dict())


def profile_csv(value: DownloadedDataProfile) -> str:
    value = DownloadedDataProfile.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(("profile_address", "field_name", "observed_count", "missing_count", "null_count", "distinct_value_count", "distinct_truncated", "min_value_size", "max_value_size", "type_counts_json", "content_address"))
    for item in value.fields:
        writer.writerow((value.content_address, item.field_name, item.observed_count, item.missing_count, item.null_count, item.distinct_value_count, item.distinct_truncated, item.min_value_size, item.max_value_size, canonical_json(tuple(entry.to_dict() for entry in item.type_counts)), item.content_address))
    return stream.getvalue()


def render_profile_markdown(value: DownloadedDataProfile) -> str:
    value = DownloadedDataProfile.from_mapping(value.to_dict())
    lines = [
        "# Downloaded Data Structural Profile",
        "",
        f"- Profile: `{value.profile_id}`",
        f"- Batch: `{value.batch_address}`",
        f"- Records: `{value.record_count}`",
        f"- Members: `{value.member_count}`",
        f"- Fields: `{value.field_count}`",
        f"- Value bytes: `{value.total_value_bytes}`",
        f"- Address: `{value.content_address}`",
        "",
        "## Members",
        "",
        "| ordinal | member | kind | records | fields |",
        "| ---: | --- | --- | ---: | ---: |",
    ]
    lines.extend(f"| {item.member_ordinal} | `{item.member_name}` | `{item.data_kind}` | {item.record_count} | {item.field_count} |" for item in value.members)
    lines.extend(("", "## Fields", "", "| field | observed | missing | null | distinct | min bytes | max bytes |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"))
    lines.extend(f"| `{item.field_name}` | {item.observed_count} | {item.missing_count} | {item.null_count} | {item.distinct_value_count}{'+' if item.distinct_truncated else ''} | {item.min_value_size} | {item.max_value_size} |" for item in value.fields)
    return "\n".join(lines) + "\n"


def type_count_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile type count", "type": "object", "additionalProperties": False, "required": list(TYPE_COUNT_FIELDS), "properties": {"value_type": {"enum": list(VALUE_TYPES)}, "count": {"type": "integer", "minimum": 0}, "content_address": {"type": "string"}}}


def shape_count_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile shape count", "type": "object", "additionalProperties": False, "required": list(SHAPE_COUNT_FIELDS), "properties": {"shape": {"enum": list(SHAPES)}, "count": {"type": "integer", "minimum": 0}, "content_address": {"type": "string"}}}


def field_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data field profile", "type": "object", "additionalProperties": False, "required": list(FIELD_PROFILE_FIELDS), "properties": {"field_name": {"type": "string"}, "observed_count": {"type": "integer", "minimum": 0}, "missing_count": {"type": "integer", "minimum": 0}, "null_count": {"type": "integer", "minimum": 0}, "type_counts": {"type": "array", "items": type_count_schema(), "minItems": len(VALUE_TYPES), "maxItems": len(VALUE_TYPES)}, "distinct_value_count": {"type": "integer", "minimum": 0, "maximum": MAX_DISTINCT_VALUES}, "distinct_truncated": {"type": "boolean"}, "min_value_size": {"type": "integer", "minimum": 0}, "max_value_size": {"type": "integer", "minimum": 0}, "content_address": {"type": "string"}}}


def member_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data member profile", "type": "object", "additionalProperties": False, "required": list(MEMBER_PROFILE_FIELDS), "properties": {"member_name": {"type": "string"}, "member_address": {"type": "string"}, "member_ordinal": {"type": "integer", "minimum": 1}, "data_kind": {"enum": list(ingestion_model.DATA_KINDS)}, "record_count": {"type": "integer", "minimum": 0}, "shape_counts": {"type": "array", "items": shape_count_schema()}, "field_count": {"type": "integer", "minimum": 0}, "fields": {"type": "array", "items": field_schema()}, "content_address": {"type": "string"}}}


def profile_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data structural profile", "type": "object", "additionalProperties": False, "required": list(PROFILE_FIELDS), "properties": {"profile_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "batch_address": {"type": "string"}, "record_count": {"type": "integer", "minimum": 0}, "member_count": {"type": "integer", "minimum": 0}, "field_count": {"type": "integer", "minimum": 0}, "total_value_bytes": {"type": "integer", "minimum": 0}, "type_counts": {"type": "array", "items": type_count_schema(), "minItems": len(VALUE_TYPES), "maxItems": len(VALUE_TYPES)}, "members": {"type": "array", "items": member_schema()}, "fields": {"type": "array", "items": field_schema()}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "formats": ingestion_model.DATA_KINDS, "value_types": VALUE_TYPES, "shapes": SHAPES, "operations": ("build_profile", "profile_from_mapping", "profile_json", "profile_csv", "render_profile_markdown"), "limits": {"max_members": MAX_MEMBERS, "max_records": MAX_RECORDS, "max_fields": MAX_FIELDS, "max_distinct_values": MAX_DISTINCT_VALUES}}


__all__ = [
    "BOUNDARY", "FIELD_PROFILE_FIELDS", "MAX_DISTINCT_VALUES", "MAX_FIELDS", "MAX_MEMBERS", "PROFILE_FIELDS", "PROFILE_PREFIX", "SHAPES", "TYPE_COUNT_FIELDS", "VALUE_TYPES", "VERSION",
    "DownloadedDataFieldProfile", "DownloadedDataMemberProfile", "DownloadedDataProfile", "DownloadedDataShapeCount", "DownloadedDataTypeCount",
    "address_field", "address_member", "address_profile", "address_shape_count", "address_type_count", "build_profile", "capabilities", "field_schema", "member_schema", "profile_csv", "profile_from_mapping", "profile_json", "profile_schema", "render_profile_markdown", "shape_count_schema", "type_count_schema",
]
