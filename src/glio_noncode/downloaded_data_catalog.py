"""Bounded cataloging of structured members in a downloaded ZIP data bundle.

The adapter is intentionally data-only.  It records safe member metadata and
small structural counts without importing, executing, or treating source code
and prose as product logic.  The output is a public, content-addressed
catalog that can be reviewed before any downstream model consumes it.
"""

from __future__ import annotations

import csv
import io
import json
import mimetypes
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from .errors import ValidationError
from .serialization import canonical_json, content_hash, hash_bytes

VERSION = "downloaded-data-catalog-v1"
BOUNDARY = "public_downloaded_data_catalog"
CATALOG_PREFIX = "glio-noncode-download-catalog"
MEMBER_PREFIX = CATALOG_PREFIX + "-member"
MAX_MEMBERS = 4096
MAX_MEMBER_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_FIELDS = 512
MAX_ROWS = 1_000_000
DATA_SUFFIXES = (".csv", ".json", ".jsonl", ".ndjson", ".tsv", ".yaml", ".yml")
EXCLUDED_DIRECTORY_NAMES = ("__pycache__", "source", "src", "tests", "05_agents", "10_starter_code")
CATALOG_FIELDS = ("catalog_id", "version", "boundary", "source_name", "source_size", "member_count", "included_count", "total_data_bytes", "json_count", "delimited_count", "yaml_count", "members", "content_address")
MEMBER_FIELDS = ("ordinal", "member_name", "suffix", "media_type", "byte_size", "digest", "data_kind", "shape", "record_count", "field_count", "fields", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
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
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
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
    forbidden = {"agent", "agent_id", "agent_name", "assistant", "assistant_id", "author", "language", "model", "model_id", "programming_language"}

    def walk(node: Any) -> bool:
        if isinstance(node, Mapping):
            return all(str(key).casefold() not in forbidden and walk(child) for key, child in node.items())
        if isinstance(node, (tuple, list)):
            return all(walk(child) for child in node)
        return True

    return walk(value)


def _regular_member(info: zipfile.ZipInfo) -> bool:
    name = info.filename
    parts = PurePosixPath(name).parts
    if info.is_dir() or info.flag_bits & 0x1 or not name or name.startswith("/") or "\\" in name or any(part in {"", ".", ".."} for part in parts):
        return False
    if info.create_system == 3 and (info.external_attr >> 16) & 0o170000 == 0o120000:
        return False
    return True


def _suffix(name: str) -> str:
    return Path(name).suffix.casefold()


def _data_kind(suffix: str) -> str:
    if suffix in {".csv", ".tsv"}:
        return "delimited"
    if suffix in {".json", ".jsonl", ".ndjson"}:
        return "json"
    if suffix in {".yaml", ".yml"}:
        return "yaml"
    return "other"


def _media_type(name: str) -> str:
    suffix = _suffix(name)
    return {".csv": "text/csv", ".tsv": "text/tab-separated-values", ".json": "application/json", ".jsonl": "application/x-ndjson", ".ndjson": "application/x-ndjson", ".yaml": "application/yaml", ".yml": "application/yaml"}.get(suffix, mimetypes.guess_type(name)[0] or "application/octet-stream")


def _included_name(name: str) -> bool:
    suffix = _suffix(name)
    if suffix not in DATA_SUFFIXES:
        return False
    parts = {part.casefold() for part in PurePosixPath(name).parts}
    return not any(item.casefold() in parts for item in EXCLUDED_DIRECTORY_NAMES)


def _decode_text(raw: bytes, name: str) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValidationError(f"downloaded data member {name} is not UTF-8") from error


def _bounded_fields(fields: Sequence[Any], name: str) -> tuple[str, ...]:
    values = tuple(_label(str(field), f"{name} field") for field in fields)
    if len(values) > MAX_FIELDS or len(set(values)) != len(values):
        raise ValidationError(f"downloaded data member {name} has too many or duplicate fields")
    return values


def _inspect_json(raw: bytes, name: str) -> tuple[str, str, int, int, tuple[str, ...]]:
    try:
        value = json.loads(_decode_text(raw, name))
    except (json.JSONDecodeError, ValidationError) as error:
        raise ValidationError(f"downloaded JSON member {name} is invalid") from error
    if isinstance(value, Mapping):
        fields = _bounded_fields(tuple(value), name)
        return "json", "object", 1, len(fields), fields
    if isinstance(value, list):
        if len(value) > MAX_ROWS:
            raise ValidationError(f"downloaded JSON member {name} has too many records")
        object_rows = tuple(item for item in value if isinstance(item, Mapping))
        fields = _bounded_fields(tuple(object_rows[0]) if object_rows else (), name)
        return "json", "array", len(value), len(fields), fields
    return "json", "scalar", 1, 0, ()


def _inspect_delimited(raw: bytes, name: str, suffix: str) -> tuple[str, str, int, int, tuple[str, ...]]:
    delimiter = "\t" if suffix == ".tsv" else ","
    stream = io.StringIO(_decode_text(raw, name), newline="")
    reader = csv.DictReader(stream, delimiter=delimiter)
    fields = _bounded_fields(reader.fieldnames or (), name)
    count = 0
    for _row in reader:
        count += 1
        if count > MAX_ROWS:
            raise ValidationError(f"downloaded delimited member {name} has too many records")
    return "delimited", "table", count, len(fields), fields


def _inspect_yaml(raw: bytes, name: str) -> tuple[str, str, int, int, tuple[str, ...]]:
    text = _decode_text(raw, name)
    non_empty = tuple(line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#"))
    if len(non_empty) > MAX_ROWS:
        raise ValidationError(f"downloaded YAML member {name} has too many records")
    keys = tuple(line.split(":", 1)[0].strip() for line in non_empty if ":" in line and not line.startswith((" ", "-")))
    fields = _bounded_fields(keys[:MAX_FIELDS], name)
    return "yaml", "document", 1 if non_empty else 0, len(fields), fields


def _inspect(raw: bytes, name: str, suffix: str) -> tuple[str, str, int, int, tuple[str, ...]]:
    if suffix in {".json", ".jsonl", ".ndjson"}:
        if suffix in {".jsonl", ".ndjson"}:
            lines = tuple(line for line in _decode_text(raw, name).splitlines() if line.strip())
            if len(lines) > MAX_ROWS:
                raise ValidationError(f"downloaded line-delimited member {name} has too many records")
            for line in lines:
                try:
                    json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValidationError(f"downloaded line-delimited member {name} is invalid") from error
            return "json", "lines", len(lines), 0, ()
        return _inspect_json(raw, name)
    if suffix in {".csv", ".tsv"}:
        return _inspect_delimited(raw, name, suffix)
    return _inspect_yaml(raw, name)


class DownloadedDataMember:
    """Public structural metadata for one eligible downloaded data member."""

    FIELDS = MEMBER_FIELDS

    def __init__(self, ordinal: int, member_name: str, suffix: str, media_type: str, byte_size: int, digest: str, data_kind: str, shape: str, record_count: int, field_count: int, fields: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "downloaded data member ordinal", MAX_MEMBERS, positive=True)
        self.member_name = _text(member_name, "downloaded data member name", 1024)
        if "\\" in self.member_name or self.member_name.startswith("/") or any(part in {"", ".", ".."} for part in PurePosixPath(self.member_name).parts):
            raise ValidationError("downloaded data member name must be a safe POSIX path")
        self.suffix = _label(suffix, "downloaded data member suffix")
        self.media_type = _label(media_type.replace("/", "-"), "downloaded data member media type")
        self.byte_size = _count(byte_size, "downloaded data member byte size", MAX_MEMBER_BYTES)
        self.digest = _address(digest, "downloaded data member digest", MEMBER_PREFIX)
        self.data_kind = _label(data_kind, "downloaded data member kind")
        self.shape = _label(shape, "downloaded data member shape")
        self.record_count = _count(record_count, "downloaded data member record count", MAX_ROWS)
        self.field_count = _count(field_count, "downloaded data member field count", MAX_FIELDS)
        self.fields = _bounded_fields(fields, "downloaded data member")
        if self.field_count != len(self.fields):
            raise ValidationError("downloaded data member field count does not replay")
        self.content_address = _address(content_address, "downloaded data member address", CATALOG_PREFIX + "-member") if not str(content_address).endswith(":pending") else _text(content_address, "downloaded data member address")
        self._validate()

    def _validate(self) -> None:
        if self.byte_size == 0 or not self.data_kind or not self.shape or not _public(self.to_dict()):
            raise ValidationError("downloaded data member is incomplete or crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_member(self) != self.content_address:
            raise ValidationError("downloaded data member address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field not in {"fields"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataMember:
        value = _mapping(value, "downloaded data member")
        _strict(value, set(cls.FIELDS), "downloaded data member")
        raw_media_type = str(value["media_type"]).replace("-", "/", 1) if "/" not in str(value["media_type"]) else value["media_type"]
        return cls(value["ordinal"], value["member_name"], value["suffix"], raw_media_type, value["byte_size"], value["digest"], value["data_kind"], value["shape"], value["record_count"], value["field_count"], value["fields"], value["content_address"])


def address_member(value: DownloadedDataMember) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=MEMBER_PREFIX)


class DownloadedDataCatalog:
    """Content-addressed structural catalog for one downloaded bundle."""

    FIELDS = CATALOG_FIELDS

    def __init__(self, catalog_id: str, version: str, boundary: str, source_name: str, source_size: int, member_count: int, included_count: int, total_data_bytes: int, json_count: int, delimited_count: int, yaml_count: int, members: Sequence[DownloadedDataMember], content_address: str) -> None:
        self.catalog_id = _label(catalog_id, "downloaded data catalog ID")
        self.version = _text(version, "downloaded data catalog version")
        self.boundary = _text(boundary, "downloaded data catalog boundary", 512)
        self.source_name = _text(source_name, "downloaded data source name", 1024)
        self.source_size = _count(source_size, "downloaded data source size", MAX_TOTAL_BYTES)
        self.member_count = _count(member_count, "downloaded data member count", MAX_MEMBERS)
        self.included_count = _count(included_count, "downloaded data included member count", MAX_MEMBERS)
        self.total_data_bytes = _count(total_data_bytes, "downloaded data byte count", MAX_TOTAL_BYTES)
        self.json_count = _count(json_count, "downloaded JSON count", MAX_MEMBERS)
        self.delimited_count = _count(delimited_count, "downloaded delimited count", MAX_MEMBERS)
        self.yaml_count = _count(yaml_count, "downloaded YAML count", MAX_MEMBERS)
        self.members = tuple(item if isinstance(item, DownloadedDataMember) else DownloadedDataMember.from_mapping(item) for item in _sequence(members, "downloaded data members", MAX_MEMBERS))
        self.content_address = _address(content_address, "downloaded data catalog address", CATALOG_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "downloaded data catalog address")
        self._validate()

    def _validate(self) -> None:
        if self.member_count != len(self.members) or self.included_count != self.member_count:
            raise ValidationError("downloaded data catalog member counts do not replay")
        if tuple(item.ordinal for item in self.members) != tuple(range(1, self.member_count + 1)) or len({item.member_name for item in self.members}) != self.member_count:
            raise ValidationError("downloaded data catalog member order is not canonical")
        if self.total_data_bytes != sum(item.byte_size for item in self.members) or self.json_count != sum(item.data_kind == "json" for item in self.members) or self.delimited_count != sum(item.data_kind == "delimited" for item in self.members) or self.yaml_count != sum(item.data_kind == "yaml" for item in self.members):
            raise ValidationError("downloaded data catalog aggregates do not replay")
        if self.source_size <= 0 or not _public(self.to_dict()):
            raise ValidationError("downloaded data catalog size or public boundary failed")
        if not self.content_address.endswith(":pending") and address_catalog(self) != self.content_address:
            raise ValidationError("downloaded data catalog address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"catalog_id": self.catalog_id, "version": self.version, "boundary": self.boundary, "source_name": self.source_name, "source_size": self.source_size, "member_count": self.member_count, "included_count": self.included_count, "total_data_bytes": self.total_data_bytes, "json_count": self.json_count, "delimited_count": self.delimited_count, "yaml_count": self.yaml_count, "members": tuple(item.to_dict() for item in self.members), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "members"}

    def member(self, member_name: str) -> DownloadedDataMember:
        member_name = _text(member_name, "downloaded data member lookup", 1024)
        for item in self.members:
            if item.member_name == member_name:
                return item
        raise ValidationError("downloaded data member was not found")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataCatalog:
        value = _mapping(value, "downloaded data catalog")
        _strict(value, set(cls.FIELDS), "downloaded data catalog")
        members = tuple(DownloadedDataMember.from_mapping(item) for item in _sequence(value["members"], "downloaded data members", MAX_MEMBERS))
        return cls(value["catalog_id"], value["version"], value["boundary"], value["source_name"], value["source_size"], value["member_count"], value["included_count"], value["total_data_bytes"], value["json_count"], value["delimited_count"], value["yaml_count"], members, value["content_address"])


def address_catalog(value: DownloadedDataCatalog) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CATALOG_PREFIX)


def build_catalog(source: str | Path | bytes, *, catalog_id: str = "glio-noncode-downloaded-data") -> DownloadedDataCatalog:
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
    if len(raw_zip) > MAX_TOTAL_BYTES:
        raise ValidationError("downloaded data source exceeds the total byte bound")
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw_zip), "r")
    except (OSError, zipfile.BadZipFile) as error:
        raise ValidationError("downloaded data source must be a ZIP archive") from error
    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise ValidationError("downloaded data source has too many members")
        if any(not _regular_member(info) for info in infos):
            raise ValidationError("downloaded data source contains an unsafe member")
        total_uncompressed = sum(info.file_size for info in infos)
        if total_uncompressed > MAX_TOTAL_BYTES or any(info.file_size > MAX_MEMBER_BYTES for info in infos):
            raise ValidationError("downloaded data source exceeds an uncompressed byte bound")
        members: list[DownloadedDataMember] = []
        for info in sorted(infos, key=lambda item: item.filename):
            if not _included_name(info.filename):
                continue
            raw = archive.read(info)
            suffix = _suffix(info.filename)
            data_kind, shape, record_count, field_count, fields = _inspect(raw, info.filename, suffix)
            body = {"ordinal": len(members) + 1, "member_name": info.filename, "suffix": suffix, "media_type": _media_type(info.filename), "byte_size": len(raw), "digest": hash_bytes(raw, prefix=MEMBER_PREFIX), "data_kind": data_kind, "shape": shape, "record_count": record_count, "field_count": field_count, "fields": fields}
            provisional = DownloadedDataMember(**body, content_address=MEMBER_PREFIX + ":pending")
            members.append(DownloadedDataMember(**body, content_address=address_member(provisional)))
    body = {"catalog_id": catalog_id, "version": VERSION, "boundary": BOUNDARY, "source_name": source_name, "source_size": len(raw_zip), "member_count": len(members), "included_count": len(members), "total_data_bytes": sum(item.byte_size for item in members), "json_count": sum(item.data_kind == "json" for item in members), "delimited_count": sum(item.data_kind == "delimited" for item in members), "yaml_count": sum(item.data_kind == "yaml" for item in members), "members": tuple(members)}
    provisional = DownloadedDataCatalog(**body, content_address=CATALOG_PREFIX + ":pending")
    return DownloadedDataCatalog(**body, content_address=address_catalog(provisional))


def catalog_from_mapping(value: Mapping[str, Any]) -> DownloadedDataCatalog:
    return verify_catalog(DownloadedDataCatalog.from_mapping(value))


def verify_catalog(value: DownloadedDataCatalog) -> DownloadedDataCatalog:
    if not isinstance(value, DownloadedDataCatalog):
        raise ValidationError("downloaded data catalog verification requires a typed catalog")
    value._validate()
    if not value.content_address.endswith(":pending") and address_catalog(value) != value.content_address:
        raise ValidationError("downloaded data catalog address verification failed")
    return value


def catalog_json(value: DownloadedDataCatalog) -> str:
    return canonical_json(verify_catalog(value).to_dict())


def catalog_csv(value: DownloadedDataCatalog) -> str:
    value = verify_catalog(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=DownloadedDataMember.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.members:
        row = item.to_dict()
        row["fields"] = ",".join(row["fields"])
        writer.writerow(row)
    return stream.getvalue()


def render_catalog_markdown(value: DownloadedDataCatalog) -> str:
    value = verify_catalog(value)
    lines = ["# Downloaded Data Catalog", "", f"- Source: `{value.source_name}`", f"- Source bytes: `{value.source_size}`", f"- Structured members: `{value.member_count}`", f"- Data bytes: `{value.total_data_bytes}`", f"- JSON members: `{value.json_count}`", f"- Delimited members: `{value.delimited_count}`", f"- YAML members: `{value.yaml_count}`", f"- Catalog address: `{value.content_address}`", "", "| # | member | kind | shape | records | fields | bytes |", "| ---: | --- | --- | --- | ---: | ---: | ---: |"]
    lines.extend(f"| {item.ordinal} | `{item.member_name}` | `{item.data_kind}` | `{item.shape}` | {item.record_count} | {item.field_count} | {item.byte_size} |" for item in value.members)
    return "\n".join(lines) + "\n"


def member_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(MEMBER_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "member_name": {"type": "string"}, "suffix": {"type": "string"}, "media_type": {"type": "string"}, "byte_size": {"type": "integer", "minimum": 1}, "digest": {"type": "string"}, "data_kind": {"enum": ["json", "delimited", "yaml"]}, "shape": {"type": "string"}, "record_count": {"type": "integer", "minimum": 0}, "field_count": {"type": "integer", "minimum": 0}, "fields": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def catalog_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(CATALOG_FIELDS), "properties": {"catalog_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "source_name": {"type": "string"}, "source_size": {"type": "integer", "minimum": 0}, "member_count": {"type": "integer", "minimum": 0}, "included_count": {"type": "integer", "minimum": 0}, "total_data_bytes": {"type": "integer", "minimum": 0}, "json_count": {"type": "integer", "minimum": 0}, "delimited_count": {"type": "integer", "minimum": 0}, "yaml_count": {"type": "integer", "minimum": 0}, "members": {"type": "array", "items": member_schema()}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "bounded": True, "content_addressed": True, "source_policy": "structured-data-members-only", "operations": ("build_catalog", "catalog_from_mapping", "catalog_json", "catalog_csv", "render_catalog_markdown", "verify_catalog"), "suffixes": DATA_SUFFIXES, "max_members": MAX_MEMBERS, "max_member_bytes": MAX_MEMBER_BYTES, "max_total_bytes": MAX_TOTAL_BYTES}


__all__ = ["BOUNDARY", "CATALOG_FIELDS", "CATALOG_PREFIX", "DATA_SUFFIXES", "DownloadedDataCatalog", "DownloadedDataMember", "MAX_MEMBER_BYTES", "MAX_MEMBERS", "MAX_TOTAL_BYTES", "MEMBER_FIELDS", "VERSION", "address_catalog", "address_member", "build_catalog", "capabilities", "catalog_csv", "catalog_from_mapping", "catalog_json", "catalog_schema", "member_schema", "render_catalog_markdown", "verify_catalog"]
