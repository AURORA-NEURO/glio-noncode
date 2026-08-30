"""Bounded, content-addressed ingestion of structured downloaded data.

The catalog adapter deliberately stops at structural metadata.  This module
is the next explicit boundary: a caller chooses eligible members, the adapter
parses only the selected data formats, and the resulting records retain exact
source/member/row lineage.  Every limit is explicit, values are checked before
they cross the public boundary, and truncation is never silent.
"""

from __future__ import annotations

import ast
import csv
import io
import json
import math
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from . import downloaded_data_catalog as catalog_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash, hash_bytes

VERSION = "downloaded-data-ingestion-v1"
BOUNDARY = "public_downloaded_data_ingestion"
SOURCE_PREFIX = "glio-noncode-download-source"
SELECTION_PREFIX = "glio-noncode-download-selection"
INGEST_PREFIX = "glio-noncode-download-ingest"
RECORD_PREFIX = INGEST_PREFIX + "-record"
MAX_SELECTED_MEMBERS = 512
MAX_RECORDS = 100_000
MAX_TOTAL_RECORDS = 1_000_000
MAX_RECORD_BYTES = 2 * 1024 * 1024
MAX_VALUE_DEPTH = 12
MAX_VALUE_ITEMS = 50_000
MAX_VALUE_STRING = 1_000_000
MAX_IDENTIFIER = 256
OVERFLOW_POLICIES = ("reject", "truncate")
DATA_KINDS = ("json", "delimited", "yaml")
SUFFIXES = catalog_model.DATA_SUFFIXES
FORBIDDEN_PUBLIC_KEYS = frozenset(
    {
        "agent",
        "agent_id",
        "agent_name",
        "assistant",
        "assistant_id",
        "author",
        "language",
        "model",
        "model_id",
        "programming_language",
    }
)

SELECTION_FIELDS = (
    "selection_id",
    "version",
    "boundary",
    "catalog_address",
    "member_names",
    "suffixes",
    "data_kinds",
    "record_limit",
    "overflow_policy",
    "content_address",
)
LINEAGE_FIELDS = (
    "source_address",
    "catalog_address",
    "selection_address",
    "member_address",
    "member_name",
    "member_ordinal",
    "source_row",
)
RECORD_FIELDS = (
    "ordinal",
    "record_id",
    "data_kind",
    "shape",
    "fields",
    "value_size",
    "lineage",
    "value",
    "content_address",
)
INGEST_FIELDS = (
    "batch_id",
    "version",
    "boundary",
    "source_name",
    "source_address",
    "catalog_address",
    "selection",
    "selected_member_count",
    "available_record_count",
    "record_count",
    "dropped_record_count",
    "truncated",
    "complete",
    "state",
    "records",
    "content_address",
)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if (
        not isinstance(value, str)
        or len(value) > maximum
        or (required and not value)
        or any(ord(char) < 32 and char not in "\n\t" for char in value)
    ):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, MAX_IDENTIFIER)
    if (
        value.strip() != value
        or any(char.isspace() for char in value)
        or "/" in value
        or "\\" in value
        or '"' in value
    ):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or ":" not in value:
        raise ValidationError(f"{field} must be a public content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    lower = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum:
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
        return all(str(key).casefold() not in FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


def _key(value: Any, field: str) -> str:
    value = _text(value, field, MAX_IDENTIFIER)
    if not value or value.strip() != value or any(ord(char) < 32 for char in value):
        raise ValidationError(f"{field} is not a valid public field")
    if value.casefold() in FORBIDDEN_PUBLIC_KEYS:
        raise ValidationError(f"{field} crosses the public boundary")
    return value


def _validated_value(value: Any, field: str = "value", depth: int = 0) -> Any:
    if depth > MAX_VALUE_DEPTH:
        raise ValidationError(f"{field} exceeds the value nesting bound")
    if value is None or isinstance(value, bool) or isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValidationError(f"{field} contains a non-finite number")
        return value
    if isinstance(value, str):
        return _text(value, field, MAX_VALUE_STRING, required=False)
    if isinstance(value, Mapping):
        if len(value) > MAX_VALUE_ITEMS:
            raise ValidationError(f"{field} contains too many object members")
        result: dict[str, Any] = {}
        for raw_key, child in value.items():
            key = _key(str(raw_key), f"{field} key")
            if key in result:
                raise ValidationError(f"{field} contains duplicate keys")
            result[key] = _validated_value(child, f"{field}.{key}", depth + 1)
        return result
    if isinstance(value, (tuple, list)):
        if len(value) > MAX_VALUE_ITEMS:
            raise ValidationError(f"{field} contains too many array members")
        return [_validated_value(child, f"{field}[{index}]", depth + 1) for index, child in enumerate(value)]
    raise ValidationError(f"{field} contains an unsupported value type")


def _fields(value: Any, fallback: Sequence[str] = ()) -> tuple[str, ...]:
    if isinstance(value, Mapping):
        names = tuple(_key(str(item), "record field") for item in value)
    else:
        names = tuple(_key(item, "record field") for item in fallback)
    if len(names) > catalog_model.MAX_FIELDS or len(set(names)) != len(names):
        raise ValidationError("record fields are too numerous or duplicated")
    return names


def _safe_member_name(value: Any, field: str = "member name") -> str:
    value = _text(value, field, 1024)
    parts = PurePosixPath(value).parts
    if (
        not value
        or value.startswith("/")
        or "\\" in value
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise ValidationError(f"{field} must be a safe POSIX path")
    return value


def _labels(value: Any, field: str, allowed: Sequence[str]) -> tuple[str, ...]:
    values = tuple(_label(item, field) for item in _sequence(value, field, len(allowed)))
    if len(set(values)) != len(values) or any(item not in allowed for item in values):
        raise ValidationError(f"{field} contains an unsupported or duplicate value")
    if values != tuple(sorted(values)):
        raise ValidationError(f"{field} must be sorted canonically")
    return values


def _parse_constant(value: str) -> Any:
    raise ValidationError(f"JSON contains unsupported constant {value}")


def _decode(raw: bytes, name: str) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValidationError(f"downloaded member {name} is not UTF-8") from error


def _parse_json(raw: bytes, name: str) -> Any:
    try:
        return json.loads(_decode(raw, name), parse_constant=_parse_constant)
    except (json.JSONDecodeError, ValidationError) as error:
        raise ValidationError(f"downloaded JSON member {name} is invalid") from error


def _yaml_scalar(value: str, name: str) -> Any:
    token = value.strip()
    if not token:
        return None
    if token in {"null", "Null", "NULL", "~"}:
        return None
    if token in {"true", "True", "TRUE"}:
        return True
    if token in {"false", "False", "FALSE"}:
        return False
    if token[0:1] in {"'", '"'} and token[-1:] == token[0]:
        try:
            return ast.literal_eval(token)
        except (SyntaxError, ValueError) as error:
            raise ValidationError(f"YAML member {name} has an invalid quoted scalar") from error
    if token.startswith(("[", "{")):
        try:
            return json.loads(token, parse_constant=_parse_constant)
        except (json.JSONDecodeError, ValidationError):
            try:
                return ast.literal_eval(token)
            except (SyntaxError, ValueError) as error:
                raise ValidationError(f"YAML member {name} has an invalid inline value") from error
    try:
        if token.lstrip("-").isdigit():
            return int(token)
        if any(char in token for char in ".eE"):
            number = float(token)
            if math.isfinite(number):
                return number
    except ValueError:
        pass
    return token


def _yaml_lines(text: str, name: str) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if "\t" in raw_line[: len(raw_line) - len(raw_line.lstrip())]:
            raise ValidationError(f"YAML member {name} uses tabs for indentation")
        content = raw_line.lstrip(" ")
        if content in {"---", "..."}:
            continue
        result.append((len(raw_line) - len(content), content))
    return result


def _parse_yaml_block(lines: list[tuple[int, str]], index: int, indent: int, name: str) -> tuple[Any, int]:
    if index >= len(lines) or lines[index][0] < indent:
        return None, index
    is_list = lines[index][0] == indent and lines[index][1].startswith("- ")
    container: list[Any] | dict[str, Any] = [] if is_list else {}
    while index < len(lines):
        current_indent, content = lines[index]
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ValidationError(f"YAML member {name} has inconsistent indentation")
        if is_list:
            if not content.startswith("- "):
                raise ValidationError(f"YAML member {name} mixes mapping and sequence entries")
            item_text = content[2:].strip()
            if not item_text:
                child, index = _parse_yaml_block(lines, index + 1, lines[index + 1][0], name) if index + 1 < len(lines) and lines[index + 1][0] > indent else (None, index + 1)
                container.append(child)
                continue
            if ":" in item_text and not item_text.startswith(('"', "'")):
                raw_key, raw_value = item_text.split(":", 1)
                item: dict[str, Any] = {_key(raw_key.strip(), "YAML field"): _yaml_scalar(raw_value, name)}
                index += 1
                if index < len(lines) and lines[index][0] > indent:
                    child, index = _parse_yaml_block(lines, index, lines[index][0], name)
                    if isinstance(child, Mapping):
                        item.update(child)
                    else:
                        raise ValidationError(f"YAML member {name} has an invalid list mapping")
                container.append(item)
                continue
            container.append(_yaml_scalar(item_text, name))
            index += 1
            continue
        if ":" not in content or content.startswith(("- ", "-")):
            raise ValidationError(f"YAML member {name} has an invalid mapping entry")
        raw_key, raw_value = content.split(":", 1)
        key = _key(raw_key.strip(), "YAML field")
        if key in container:
            raise ValidationError(f"YAML member {name} repeats field {key}")
        index += 1
        if raw_value.strip():
            indicator = raw_value.strip()
            if indicator.startswith(("|", ">")):
                block_lines: list[str] = []
                while index < len(lines) and lines[index][0] > indent:
                    block_lines.append(lines[index][1])
                    index += 1
                container[key] = ("\n" if indicator.startswith("|") else " ").join(block_lines)
            else:
                container[key] = _yaml_scalar(raw_value, name)
        elif index < len(lines) and lines[index][0] > indent:
            child, index = _parse_yaml_block(lines, index, lines[index][0], name)
            container[key] = child
        else:
            container[key] = None
    return container, index


def _parse_yaml(raw: bytes, name: str) -> Any:
    lines = _yaml_lines(_decode(raw, name), name)
    if not lines:
        return None
    value, index = _parse_yaml_block(lines, 0, lines[0][0], name)
    if index != len(lines):
        raise ValidationError(f"YAML member {name} could not be fully parsed")
    return value


def _parse_member(raw: bytes, name: str, suffix: str) -> list[tuple[int, str, tuple[str, ...], Any]]:
    if suffix == ".json":
        value = _validated_value(_parse_json(raw, name), name)
        if isinstance(value, list):
            return [(index, "array", _fields(item), item) for index, item in enumerate(value, 1)]
        return [(1, "object" if isinstance(value, Mapping) else "scalar", _fields(value), value)]
    if suffix in {".jsonl", ".ndjson"}:
        rows: list[tuple[int, str, tuple[str, ...], Any]] = []
        for line_number, line in enumerate(_decode(raw, name).splitlines(), 1):
            if not line.strip():
                continue
            value = _validated_value(_parse_json(line.encode("utf-8"), name), name)
            rows.append((line_number, "line", _fields(value), value))
        return rows
    if suffix in {".csv", ".tsv"}:
        delimiter = "\t" if suffix == ".tsv" else ","
        reader = csv.DictReader(io.StringIO(_decode(raw, name), newline=""), delimiter=delimiter)
        header = tuple(reader.fieldnames or ())
        fields = _fields({field: None for field in header})
        rows = []
        for row in reader:
            if None in row:
                raise ValidationError(f"downloaded delimited member {name} has extra columns")
            value = _validated_value(dict(row), name)
            rows.append((reader.line_num, "table", fields, value))
        return rows
    if suffix in {".yaml", ".yml"}:
        value = _validated_value(_parse_yaml(raw, name), name)
        if value is None:
            return []
        return [(1, "document", _fields(value), value)]
    raise ValidationError(f"downloaded member {name} has an unsupported suffix")


class DownloadedDataSelection:
    """Explicit member and record bounds applied to one catalog."""

    FIELDS = SELECTION_FIELDS

    def __init__(
        self,
        selection_id: str,
        version: str,
        boundary: str,
        catalog_address: str,
        member_names: Sequence[str],
        suffixes: Sequence[str],
        data_kinds: Sequence[str],
        record_limit: int,
        overflow_policy: str,
        content_address: str,
    ) -> None:
        self.selection_id = _label(selection_id, "downloaded data selection ID")
        self.version = _text(version, "downloaded data selection version")
        self.boundary = _text(boundary, "downloaded data selection boundary", 512)
        self.catalog_address = _address(catalog_address, "selection catalog address", catalog_model.CATALOG_PREFIX)
        self.member_names = tuple(_safe_member_name(item, "selection member name") for item in _sequence(member_names, "selection member names", MAX_SELECTED_MEMBERS))
        if len(set(self.member_names)) != len(self.member_names) or self.member_names != tuple(sorted(self.member_names)):
            raise ValidationError("selection member names must be unique and sorted")
        self.suffixes = _labels(suffixes, "selection suffixes", SUFFIXES)
        self.data_kinds = _labels(data_kinds, "selection data kinds", DATA_KINDS)
        self.record_limit = _count(record_limit, "selection record limit", MAX_RECORDS, positive=True)
        self.overflow_policy = _label(overflow_policy, "selection overflow policy")
        if self.overflow_policy not in OVERFLOW_POLICIES:
            raise ValidationError("selection overflow policy is unsupported")
        self.content_address = _address(content_address, "selection address", SELECTION_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "selection address")
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("selection crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_selection(self) != self.content_address:
            raise ValidationError("selection address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "member_names"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataSelection:
        value = _mapping(value, "downloaded data selection")
        _strict(value, set(cls.FIELDS), "downloaded data selection")
        return cls(
            value["selection_id"],
            value["version"],
            value["boundary"],
            value["catalog_address"],
            value["member_names"],
            value["suffixes"],
            value["data_kinds"],
            value["record_limit"],
            value["overflow_policy"],
            value["content_address"],
        )


def address_selection(value: DownloadedDataSelection) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=SELECTION_PREFIX)


def selection_from_mapping(value: Mapping[str, Any]) -> DownloadedDataSelection:
    return DownloadedDataSelection.from_mapping(value)


def build_selection(
    catalog: catalog_model.DownloadedDataCatalog,
    *,
    selection_id: str = "glio-noncode-downloaded-data-selection",
    member_names: Sequence[str] = (),
    suffixes: Sequence[str] = (),
    data_kinds: Sequence[str] = (),
    record_limit: int = MAX_RECORDS,
    overflow_policy: str = "reject",
) -> DownloadedDataSelection:
    if not isinstance(catalog, catalog_model.DownloadedDataCatalog):
        raise ValidationError("selection requires a typed downloaded data catalog")
    names = tuple(sorted({_safe_member_name(item, "selection member name") for item in member_names}))
    selected_catalog_names = {item.member_name for item in catalog.members}
    if any(item not in selected_catalog_names for item in names):
        raise ValidationError("selection names must refer to eligible catalog members")
    normalized_suffixes = tuple(sorted({_label(item, "selection suffix") for item in suffixes}))
    normalized_kinds = tuple(sorted({_label(item, "selection data kind") for item in data_kinds}))
    if any(item not in SUFFIXES for item in normalized_suffixes) or any(item not in DATA_KINDS for item in normalized_kinds):
        raise ValidationError("selection contains an unsupported format")
    body = {
        "selection_id": selection_id,
        "version": VERSION,
        "boundary": BOUNDARY,
        "catalog_address": catalog.content_address,
        "member_names": names,
        "suffixes": normalized_suffixes,
        "data_kinds": normalized_kinds,
        "record_limit": record_limit,
        "overflow_policy": overflow_policy,
    }
    provisional = DownloadedDataSelection(**body, content_address=SELECTION_PREFIX + ":pending")
    return DownloadedDataSelection(**body, content_address=address_selection(provisional))


class DownloadedDataLineage:
    """Exact public source location for one ingested record."""

    FIELDS = LINEAGE_FIELDS

    def __init__(self, source_address: str, catalog_address: str, selection_address: str, member_address: str, member_name: str, member_ordinal: int, source_row: int) -> None:
        self.source_address = _address(source_address, "record source address", SOURCE_PREFIX)
        self.catalog_address = _address(catalog_address, "record catalog address", catalog_model.CATALOG_PREFIX)
        self.selection_address = _address(selection_address, "record selection address", SELECTION_PREFIX)
        self.member_address = _address(member_address, "record member address", catalog_model.MEMBER_PREFIX)
        self.member_name = _safe_member_name(member_name, "record member name")
        self.member_ordinal = _count(member_ordinal, "record member ordinal", catalog_model.MAX_MEMBERS, positive=True)
        self.source_row = _count(source_row, "record source row", MAX_RECORDS, positive=True)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("record lineage crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataLineage:
        value = _mapping(value, "downloaded data lineage")
        _strict(value, set(cls.FIELDS), "downloaded data lineage")
        return cls(*(value[field] for field in cls.FIELDS))


class DownloadedDataRecord:
    """One bounded value plus its member and source-row lineage."""

    FIELDS = RECORD_FIELDS

    def __init__(self, ordinal: int, record_id: str, data_kind: str, shape: str, fields: Sequence[str], value_size: int, lineage: DownloadedDataLineage | Mapping[str, Any], value: Any, content_address: str) -> None:
        self.ordinal = _count(ordinal, "record ordinal", MAX_RECORDS, positive=True)
        self.record_id = _label(record_id, "record ID")
        self.data_kind = _label(data_kind, "record data kind")
        if self.data_kind not in DATA_KINDS:
            raise ValidationError("record data kind is unsupported")
        self.shape = _label(shape, "record shape")
        self.fields = tuple(_key(item, "record field") for item in _sequence(fields, "record fields", catalog_model.MAX_FIELDS))
        if len(set(self.fields)) != len(self.fields):
            raise ValidationError("record fields are duplicated")
        self.value = _validated_value(value)
        expected_size = len(canonical_json(self.value).encode("utf-8"))
        self.value_size = _count(value_size, "record value size", MAX_RECORD_BYTES)
        if self.value_size != expected_size or expected_size > MAX_RECORD_BYTES:
            raise ValidationError("record value size does not replay")
        self.lineage = lineage if isinstance(lineage, DownloadedDataLineage) else DownloadedDataLineage.from_mapping(lineage)
        self.content_address = _address(content_address, "record address", RECORD_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "record address")
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("record crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_record(self) != self.content_address:
            raise ValidationError("record address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "record_id": self.record_id,
            "data_kind": self.data_kind,
            "shape": self.shape,
            "fields": self.fields,
            "value_size": self.value_size,
            "lineage": self.lineage.to_dict(),
            "value": self.value,
            "content_address": self.content_address,
        }

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "value"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataRecord:
        value = _mapping(value, "downloaded data record")
        _strict(value, set(cls.FIELDS), "downloaded data record")
        return cls(value["ordinal"], value["record_id"], value["data_kind"], value["shape"], value["fields"], value["value_size"], value["lineage"], value["value"], value["content_address"])


def address_record(value: DownloadedDataRecord) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RECORD_PREFIX)


class DownloadedDataIngestBatch:
    """Replayable output of one selected downloaded-data ingestion."""

    FIELDS = INGEST_FIELDS

    def __init__(self, batch_id: str, version: str, boundary: str, source_name: str, source_address: str, catalog_address: str, selection: DownloadedDataSelection | Mapping[str, Any], selected_member_count: int, available_record_count: int, record_count: int, dropped_record_count: int, truncated: bool, complete: bool, state: str, records: Sequence[DownloadedDataRecord | Mapping[str, Any]], content_address: str) -> None:
        self.batch_id = _label(batch_id, "downloaded data batch ID")
        self.version = _text(version, "downloaded data batch version")
        self.boundary = _text(boundary, "downloaded data batch boundary", 512)
        self.source_name = _text(source_name, "downloaded data source name", 1024)
        self.source_address = _address(source_address, "downloaded data source address", SOURCE_PREFIX)
        self.catalog_address = _address(catalog_address, "downloaded data catalog address", catalog_model.CATALOG_PREFIX)
        self.selection = selection if isinstance(selection, DownloadedDataSelection) else DownloadedDataSelection.from_mapping(selection)
        if self.selection.catalog_address != self.catalog_address:
            raise ValidationError("batch selection and catalog addresses do not match")
        self.selected_member_count = _count(selected_member_count, "selected member count", MAX_SELECTED_MEMBERS)
        self.available_record_count = _count(available_record_count, "available record count", MAX_TOTAL_RECORDS)
        self.record_count = _count(record_count, "record count", MAX_RECORDS)
        self.dropped_record_count = _count(dropped_record_count, "dropped record count", MAX_TOTAL_RECORDS)
        self.truncated = _bool(truncated, "batch truncation")
        self.complete = _bool(complete, "batch completeness")
        self.state = _label(state, "batch state")
        if self.state not in {"complete", "truncated"}:
            raise ValidationError("batch state is unsupported")
        self.records = tuple(item if isinstance(item, DownloadedDataRecord) else DownloadedDataRecord.from_mapping(item) for item in _sequence(records, "downloaded data records", MAX_RECORDS))
        self.content_address = _address(content_address, "downloaded data batch address", INGEST_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "downloaded data batch address")
        self._validate()

    def _validate(self) -> None:
        if self.selected_member_count == 0 or self.record_count != len(self.records) or self.available_record_count != self.record_count + self.dropped_record_count:
            raise ValidationError("batch counts do not replay")
        if self.truncated != (self.dropped_record_count > 0) or self.complete != (not self.truncated) or self.state != ("truncated" if self.truncated else "complete"):
            raise ValidationError("batch truncation state does not replay")
        if tuple(item.ordinal for item in self.records) != tuple(range(1, self.record_count + 1)):
            raise ValidationError("batch record ordinals are not canonical")
        if len({item.record_id for item in self.records}) != self.record_count or not _public(self.to_dict()):
            raise ValidationError("batch records are not unique or public")
        if not self.content_address.endswith(":pending") and address_batch(self) != self.content_address:
            raise ValidationError("batch address does not replay")

    @property
    def accepted(self) -> bool:
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "version": self.version,
            "boundary": self.boundary,
            "source_name": self.source_name,
            "source_address": self.source_address,
            "catalog_address": self.catalog_address,
            "selection": self.selection.to_dict(),
            "selected_member_count": self.selected_member_count,
            "available_record_count": self.available_record_count,
            "record_count": self.record_count,
            "dropped_record_count": self.dropped_record_count,
            "truncated": self.truncated,
            "complete": self.complete,
            "state": self.state,
            "records": tuple(item.to_dict() for item in self.records),
            "content_address": self.content_address,
        }

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "records"}

    def record(self, record_id: str) -> DownloadedDataRecord:
        record_id = _label(record_id, "record lookup ID")
        for item in self.records:
            if item.record_id == record_id:
                return item
        raise ValidationError("downloaded data record was not found")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataIngestBatch:
        value = _mapping(value, "downloaded data ingest batch")
        _strict(value, set(cls.FIELDS), "downloaded data ingest batch")
        return cls(value["batch_id"], value["version"], value["boundary"], value["source_name"], value["source_address"], value["catalog_address"], value["selection"], value["selected_member_count"], value["available_record_count"], value["record_count"], value["dropped_record_count"], value["truncated"], value["complete"], value["state"], value["records"], value["content_address"])


def address_batch(value: DownloadedDataIngestBatch) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=INGEST_PREFIX)


def _read_source(source: str | Path | bytes) -> tuple[bytes, str, str]:
    if isinstance(source, bytes):
        raw_zip = source
        source_name = "downloaded-bytes.zip"
    else:
        path = Path(source)
        if path.is_symlink() or not path.is_file():
            raise ValidationError("downloaded data source must be a regular file")
        source_name = path.name
        try:
            raw_zip = path.read_bytes()
        except OSError as error:
            raise ValidationError("downloaded data source could not be read") from error
    if len(raw_zip) > catalog_model.MAX_TOTAL_BYTES:
        raise ValidationError("downloaded data source exceeds the total byte bound")
    return raw_zip, source_name, hash_bytes(raw_zip, prefix=SOURCE_PREFIX)


def _selected_members(catalog: catalog_model.DownloadedDataCatalog, selection: DownloadedDataSelection) -> tuple[catalog_model.DownloadedDataMember, ...]:
    selected = tuple(
        item
        for item in catalog.members
        if (not selection.member_names or item.member_name in selection.member_names)
        and (not selection.suffixes or item.suffix in selection.suffixes)
        and (not selection.data_kinds or item.data_kind in selection.data_kinds)
    )
    if not selected:
        raise ValidationError("selection did not identify any eligible catalog member")
    if len(selected) > MAX_SELECTED_MEMBERS:
        raise ValidationError("selection identifies too many members")
    return selected


def build_ingest(
    source: str | Path | bytes,
    *,
    catalog: catalog_model.DownloadedDataCatalog | None = None,
    selection: DownloadedDataSelection | Mapping[str, Any] | None = None,
    selection_id: str = "glio-noncode-downloaded-data-selection",
    member_names: Sequence[str] = (),
    suffixes: Sequence[str] = (),
    data_kinds: Sequence[str] = (),
    record_limit: int = MAX_RECORDS,
    overflow_policy: str = "reject",
    batch_id: str = "glio-noncode-downloaded-data-ingest",
) -> DownloadedDataIngestBatch:
    raw_zip, source_name, source_address = _read_source(source)
    resolved_catalog = catalog if catalog is not None else catalog_model.build_catalog(raw_zip)
    if not isinstance(resolved_catalog, catalog_model.DownloadedDataCatalog):
        raise ValidationError("ingestion requires a typed downloaded data catalog")
    resolved_selection = (
        build_selection(resolved_catalog, selection_id=selection_id, member_names=member_names, suffixes=suffixes, data_kinds=data_kinds, record_limit=record_limit, overflow_policy=overflow_policy)
        if selection is None
        else selection if isinstance(selection, DownloadedDataSelection) else DownloadedDataSelection.from_mapping(selection)
    )
    if resolved_selection.catalog_address != resolved_catalog.content_address:
        raise ValidationError("ingestion selection does not belong to the source catalog")
    selected = _selected_members(resolved_catalog, resolved_selection)
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw_zip), "r")
    except (OSError, zipfile.BadZipFile) as error:
        raise ValidationError("downloaded data source must be a ZIP archive") from error
    parsed: list[tuple[catalog_model.DownloadedDataMember, int, str, tuple[str, ...], Any]] = []
    with archive:
        info_by_name = {info.filename: info for info in archive.infolist()}
        for member in selected:
            info = info_by_name.get(member.member_name)
            if info is None or not catalog_model._regular_member(info):
                raise ValidationError("catalog member is not present as a regular archive member")
            raw = archive.read(info)
            if len(raw) != member.byte_size or hash_bytes(raw, prefix=catalog_model.MEMBER_PREFIX) != member.digest:
                raise ValidationError(f"downloaded member {member.member_name} changed after cataloging")
            for source_row, shape, fields, value in _parse_member(raw, member.member_name, member.suffix):
                parsed.append((member, source_row, shape, fields, value))
                if len(parsed) > MAX_TOTAL_RECORDS:
                    raise ValidationError("ingestion source contains too many records")
    available = len(parsed)
    if available > resolved_selection.record_limit and resolved_selection.overflow_policy == "reject":
        raise ValidationError("selected records exceed the explicit ingestion limit")
    emitted = parsed[: resolved_selection.record_limit]
    dropped = available - len(emitted)
    records: list[DownloadedDataRecord] = []
    for ordinal, (member, source_row, shape, fields, value) in enumerate(emitted, 1):
        lineage_body = {
            "source_address": source_address,
            "catalog_address": resolved_catalog.content_address,
            "selection_address": resolved_selection.content_address,
            "member_address": member.content_address,
            "member_name": member.member_name,
            "member_ordinal": member.ordinal,
            "source_row": source_row,
        }
        lineage = DownloadedDataLineage(**lineage_body)
        record_body = {
            "ordinal": ordinal,
            "record_id": f"m{member.ordinal:04d}-r{source_row:08d}",
            "data_kind": member.data_kind,
            "shape": shape,
            "fields": fields,
            "value_size": len(canonical_json(value).encode("utf-8")),
            "lineage": lineage,
            "value": value,
        }
        provisional = DownloadedDataRecord(**record_body, content_address=RECORD_PREFIX + ":pending")
        records.append(DownloadedDataRecord(**record_body, content_address=address_record(provisional)))
    body = {
        "batch_id": batch_id,
        "version": VERSION,
        "boundary": BOUNDARY,
        "source_name": source_name,
        "source_address": source_address,
        "catalog_address": resolved_catalog.content_address,
        "selection": resolved_selection,
        "selected_member_count": len(selected),
        "available_record_count": available,
        "record_count": len(records),
        "dropped_record_count": dropped,
        "truncated": dropped > 0,
        "complete": dropped == 0,
        "state": "truncated" if dropped else "complete",
        "records": records,
    }
    provisional = DownloadedDataIngestBatch(**body, content_address=INGEST_PREFIX + ":pending")
    return DownloadedDataIngestBatch(**body, content_address=address_batch(provisional))


def ingest_from_mapping(value: Mapping[str, Any]) -> DownloadedDataIngestBatch:
    return DownloadedDataIngestBatch.from_mapping(value)


def ingest_json(value: DownloadedDataIngestBatch) -> str:
    return canonical_json(value.to_dict())


def selection_json(value: DownloadedDataSelection) -> str:
    return canonical_json(value.to_dict())


def record_json(value: DownloadedDataRecord) -> str:
    return canonical_json(value.to_dict())


def ingest_csv(value: DownloadedDataIngestBatch) -> str:
    rows = [
        (
            item.ordinal,
            item.record_id,
            item.data_kind,
            item.shape,
            item.lineage.member_name,
            item.lineage.member_ordinal,
            item.lineage.source_row,
            ";".join(item.fields),
            item.value_size,
            canonical_json(item.value),
            item.content_address,
        )
        for item in value.records
    ]
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(("ordinal", "record_id", "data_kind", "shape", "member_name", "member_ordinal", "source_row", "fields", "value_size", "value_json", "content_address"))
    writer.writerows(rows)
    return stream.getvalue()


def render_selection_markdown(value: DownloadedDataSelection) -> str:
    value = DownloadedDataSelection.from_mapping(value.to_dict())
    return "\n".join(
        [
            "# Downloaded Data Selection",
            "",
            f"- Selection: `{value.selection_id}`",
            f"- Catalog: `{value.catalog_address}`",
            f"- Members: `{len(value.member_names) if value.member_names else 'all eligible'}`",
            f"- Record limit: `{value.record_limit}`",
            f"- Overflow policy: `{value.overflow_policy}`",
            f"- Address: `{value.content_address}`",
            "",
        ]
    )


def render_record_markdown(value: DownloadedDataRecord) -> str:
    value = DownloadedDataRecord.from_mapping(value.to_dict())
    return "\n".join(
        [
            "# Downloaded Data Record",
            "",
            f"- Record: `{value.record_id}`",
            f"- Member: `{value.lineage.member_name}` row `{value.lineage.source_row}`",
            f"- Shape: `{value.shape}`",
            f"- Fields: `{', '.join(value.fields)}`",
            f"- Value bytes: `{value.value_size}`",
            f"- Address: `{value.content_address}`",
            "",
            "```json",
            canonical_json(value.value),
            "```",
            "",
        ]
    )


def render_ingest_markdown(value: DownloadedDataIngestBatch) -> str:
    value = DownloadedDataIngestBatch.from_mapping(value.to_dict())
    lines = [
        "# Downloaded Data Ingestion",
        "",
        f"- Batch: `{value.batch_id}`",
        f"- Source: `{value.source_name}`",
        f"- Selected members: `{value.selected_member_count}`",
        f"- Records: `{value.record_count}/{value.available_record_count}`",
        f"- State: `{value.state}`",
        f"- Complete: `{value.complete}`",
        f"- Address: `{value.content_address}`",
        "",
        "| ordinal | record | kind | member | row | address |",
        "| ---: | --- | --- | --- | ---: | --- |",
    ]
    lines.extend(f"| {item.ordinal} | `{item.record_id}` | `{item.data_kind}` | `{item.lineage.member_name}` | {item.lineage.source_row} | `{item.content_address}` |" for item in value.records)
    return "\n".join(lines) + "\n"


def lineage_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Downloaded data lineage",
        "type": "object",
        "additionalProperties": False,
        "required": list(LINEAGE_FIELDS),
        "properties": {
            "source_address": {"type": "string"},
            "catalog_address": {"type": "string"},
            "selection_address": {"type": "string"},
            "member_address": {"type": "string"},
            "member_name": {"type": "string"},
            "member_ordinal": {"type": "integer", "minimum": 1},
            "source_row": {"type": "integer", "minimum": 1},
        },
    }


def record_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Downloaded data record",
        "type": "object",
        "additionalProperties": False,
        "required": list(RECORD_FIELDS),
        "properties": {
            "ordinal": {"type": "integer", "minimum": 1},
            "record_id": {"type": "string"},
            "data_kind": {"enum": list(DATA_KINDS)},
            "shape": {"type": "string"},
            "fields": {"type": "array", "items": {"type": "string"}},
            "value_size": {"type": "integer", "minimum": 0},
            "lineage": lineage_schema(),
            "value": {},
            "content_address": {"type": "string"},
        },
    }


def selection_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Downloaded data selection",
        "type": "object",
        "additionalProperties": False,
        "required": list(SELECTION_FIELDS),
        "properties": {
            "selection_id": {"type": "string"},
            "version": {"type": "string"},
            "boundary": {"type": "string"},
            "catalog_address": {"type": "string"},
            "member_names": {"type": "array", "items": {"type": "string"}},
            "suffixes": {"type": "array", "items": {"enum": list(SUFFIXES)}},
            "data_kinds": {"type": "array", "items": {"enum": list(DATA_KINDS)}},
            "record_limit": {"type": "integer", "minimum": 1},
            "overflow_policy": {"enum": list(OVERFLOW_POLICIES)},
            "content_address": {"type": "string"},
        },
    }


def ingest_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Downloaded data ingestion batch",
        "type": "object",
        "additionalProperties": False,
        "required": list(INGEST_FIELDS),
        "properties": {
            "batch_id": {"type": "string"},
            "version": {"type": "string"},
            "boundary": {"type": "string"},
            "source_name": {"type": "string"},
            "source_address": {"type": "string"},
            "catalog_address": {"type": "string"},
            "selection": selection_schema(),
            "selected_member_count": {"type": "integer", "minimum": 0},
            "available_record_count": {"type": "integer", "minimum": 0},
            "record_count": {"type": "integer", "minimum": 0},
            "dropped_record_count": {"type": "integer", "minimum": 0},
            "truncated": {"type": "boolean"},
            "complete": {"type": "boolean"},
            "state": {"enum": ["complete", "truncated"]},
            "records": {"type": "array", "items": record_schema()},
            "content_address": {"type": "string"},
        },
    }


def capabilities() -> dict[str, Any]:
    return {
        "public": True,
        "independent": True,
        "version": VERSION,
        "formats": DATA_KINDS,
        "operations": (
            "build_selection",
            "selection_from_mapping",
            "build_ingest",
            "ingest_from_mapping",
            "ingest_json",
            "ingest_csv",
            "render_ingest_markdown",
        ),
        "limits": {
            "max_selected_members": MAX_SELECTED_MEMBERS,
            "max_records": MAX_RECORDS,
            "max_total_records": MAX_TOTAL_RECORDS,
            "max_value_depth": MAX_VALUE_DEPTH,
        },
    }


__all__ = [
    "BOUNDARY",
    "DATA_KINDS",
    "DownloadedDataIngestBatch",
    "DownloadedDataLineage",
    "DownloadedDataRecord",
    "DownloadedDataSelection",
    "INGEST_PREFIX",
    "LINEAGE_FIELDS",
    "MAX_RECORDS",
    "OVERFLOW_POLICIES",
    "RECORD_PREFIX",
    "SELECTION_PREFIX",
    "SOURCE_PREFIX",
    "VERSION",
    "address_batch",
    "address_record",
    "address_selection",
    "build_ingest",
    "build_selection",
    "capabilities",
    "ingest_csv",
    "ingest_from_mapping",
    "ingest_json",
    "ingest_schema",
    "lineage_schema",
    "record_json",
    "record_schema",
    "render_ingest_markdown",
    "render_record_markdown",
    "render_selection_markdown",
    "selection_json",
    "selection_schema",
]
