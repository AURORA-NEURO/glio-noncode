"""Typed contracts for catalogs of module603 policy-decision transports."""

# ruff: noqa: E501

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .downloaded_data_review_packet_fixed_transport_catalog_diff_policy_603_ct import PACKAGE_PREFIX as TRANSPORT_PREFIX, PAYLOAD_NAMES, VERSION as TRANSPORT_VERSION
from .errors import ValidationError
from .run_workspace import _has_forbidden_key
from .serialization import content_hash

VERSION = TRANSPORT_PREFIX + "-catalog-v1"
BOUNDARY = "public_" + VERSION.replace("-", "_")
CATALOG_PREFIX = TRANSPORT_PREFIX + "-catalog"
ENTRY_PREFIX = CATALOG_PREFIX + "-entry"
MAX_ENTRIES = 256
MAX_MEMBER_COUNT = len(PAYLOAD_NAMES)
MAX_PACKAGE_BYTES = 32 * 1024 * 1024
STATES = ("empty", "ready", "blocked", "mixed")
ENTRY_FIELDS = ("entry_id", "package_id", "package_address", "manifest_address", "diff_address", "policy_address", "audit_address", "policy_state", "policy_accepted", "audit_accepted", "package_byte_count", "member_count", "content_address")
CATALOG_FIELDS = ("catalog_id", "version", "boundary", "entry_count", "accepted_count", "ready_count", "blocked_count", "state", "entries", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field, 4096)
    if allow_pending and value.endswith(":pending"):
        return value
    digest = value.rsplit(":", 1)[-1]
    if ":" not in value or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a canonical content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _strict(value: dict[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


@dataclass(frozen=True)
class Entry:
    entry_id: str
    package_id: str
    package_address: str
    manifest_address: str
    diff_address: str
    policy_address: str
    audit_address: str
    policy_state: str
    policy_accepted: bool
    audit_accepted: bool
    package_byte_count: int
    member_count: int
    content_address: str

    def __post_init__(self) -> None:
        _label(self.entry_id, "module604 entry ID")
        _label(self.package_id, "module604 package ID")
        _address(self.package_address, "module604 package address", TRANSPORT_PREFIX)
        for field in ("manifest_address", "diff_address", "policy_address", "audit_address"):
            _address(getattr(self, field), f"module604 {field}")
        if self.policy_state not in {"ready", "blocked"} or not isinstance(self.policy_accepted, bool) or not isinstance(self.audit_accepted, bool):
            raise ValidationError("module604 entry decision fields are invalid")
        _count(self.package_byte_count, "module604 package byte count", MAX_PACKAGE_BYTES)
        _count(self.member_count, "module604 member count", MAX_MEMBER_COUNT)
        _address(self.content_address, "module604 entry address", ENTRY_PREFIX, allow_pending=True)
        if not self.content_address.endswith(":pending") and address_entry(self) != self.content_address:
            raise ValidationError("module604 entry address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in ENTRY_FIELDS}

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "Entry":
        _strict(value, set(ENTRY_FIELDS), "module604 entry")
        return cls(*(value[field] for field in ENTRY_FIELDS))


def address_entry(value: Entry) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ENTRY_PREFIX)


@dataclass(frozen=True)
class Catalog:
    catalog_id: str
    version: str
    boundary: str
    entry_count: int
    accepted_count: int
    ready_count: int
    blocked_count: int
    state: str
    entries: tuple[Entry, ...]
    content_address: str

    def __post_init__(self) -> None:
        _label(self.catalog_id, "module604 catalog ID")
        if self.version != VERSION or self.boundary != BOUNDARY or self.state not in STATES:
            raise ValidationError("module604 catalog identity or state is invalid")
        if not isinstance(self.entries, tuple) or len(self.entries) > MAX_ENTRIES or tuple(item.entry_id for item in self.entries) != tuple(sorted(item.entry_id for item in self.entries)) or len({item.entry_id for item in self.entries}) != len(self.entries) or len({item.package_address for item in self.entries}) != len(self.entries):
            raise ValidationError("module604 catalog entries are not canonical")
        for field in ("entry_count", "accepted_count", "ready_count", "blocked_count"):
            _count(getattr(self, field), f"module604 {field}", MAX_ENTRIES)
        if self.entry_count != len(self.entries) or self.accepted_count != sum(item.audit_accepted for item in self.entries) or self.ready_count != sum(item.policy_state == "ready" for item in self.entries) or self.blocked_count != sum(item.policy_state == "blocked" for item in self.entries):
            raise ValidationError("module604 catalog aggregates do not replay")
        expected = "empty" if not self.entries else "ready" if self.ready_count == self.entry_count else "blocked" if self.blocked_count == self.entry_count else "mixed"
        if self.state != expected or _has_forbidden_key(self.to_dict()):
            raise ValidationError("module604 catalog state or public boundary does not replay")
        _address(self.content_address, "module604 catalog address", CATALOG_PREFIX, allow_pending=True)
        if not self.content_address.endswith(":pending") and address_catalog(self) != self.content_address:
            raise ValidationError("module604 catalog address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: tuple(item.to_dict() for item in self.entries) if field == "entries" else getattr(self, field) for field in CATALOG_FIELDS}

    def summary(self) -> dict[str, Any]:
        return {field: value for field, value in self.to_dict().items() if field != "entries"}

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "Catalog":
        _strict(value, set(CATALOG_FIELDS), "module604 catalog")
        return cls(value["catalog_id"], value["version"], value["boundary"], value["entry_count"], value["accepted_count"], value["ready_count"], value["blocked_count"], value["state"], tuple(Entry.from_mapping(item) for item in value["entries"]), value["content_address"])


def address_catalog(value: Catalog) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CATALOG_PREFIX)


def entry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Module604 catalog entry", "type": "object", "additionalProperties": False, "required": list(ENTRY_FIELDS), "properties": {"policy_state": {"enum": ["ready", "blocked"]}, "policy_accepted": {"type": "boolean"}, "audit_accepted": {"type": "boolean"}, "package_byte_count": {"type": "integer"}, "member_count": {"type": "integer", "maximum": MAX_MEMBER_COUNT}, "content_address": {"type": "string"}}}


def catalog_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Module604 transport catalog", "type": "object", "additionalProperties": False, "required": list(CATALOG_FIELDS), "properties": {"version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "entry_count": {"type": "integer", "maximum": MAX_ENTRIES}, "entries": {"type": "array", "maxItems": MAX_ENTRIES}, "state": {"enum": list(STATES)}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "transport_version": TRANSPORT_VERSION, "source_free": True, "content_addressed": True, "deterministic": True, "max_entries": MAX_ENTRIES, "max_member_count": MAX_MEMBER_COUNT, "states": STATES, "policy_state_preserved": True, "operations": ("build_catalog", "verify_catalog", "write_catalog", "catalog_json", "catalog_csv", "render_catalog_markdown", "query_catalog")}


__all__ = ["BOUNDARY", "CATALOG_FIELDS", "CATALOG_PREFIX", "ENTRY_FIELDS", "ENTRY_PREFIX", "MAX_ENTRIES", "MAX_MEMBER_COUNT", "MAX_PACKAGE_BYTES", "STATES", "VERSION", "Catalog", "Entry", "address_catalog", "address_entry", "capabilities", "catalog_schema", "entry_schema"]
