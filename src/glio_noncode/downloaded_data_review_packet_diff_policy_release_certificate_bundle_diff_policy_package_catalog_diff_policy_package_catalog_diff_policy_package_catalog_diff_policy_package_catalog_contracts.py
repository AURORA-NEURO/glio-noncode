"""Typed contracts for catalogs of packet-package policy handoff packages."""

# ruff: noqa: E501

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash
from .downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_contracts import (
    AUDIT_PREFIX,
    MANIFEST_PREFIX,
    PACKAGE_PREFIX,
    VERSION as PACKAGE_VERSION,
)
from .downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_contracts import DIFF_PREFIX, POLICY_PREFIX

VERSION = PACKAGE_PREFIX + "-catalog-v1"
BOUNDARY = "public_" + VERSION.replace("-", "_")
CATALOG_PREFIX = PACKAGE_PREFIX + "-catalog"
ENTRY_PREFIX = CATALOG_PREFIX + "-entry"
MAX_ENTRIES = 256
MAX_PACKAGE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_PACKAGE_BYTES = 256 * 1024 * 1024
MAX_TOTAL_MEMBER_BYTES = 256 * 1024 * 1024
ENTRY_FIELDS = (
    "ordinal", "entry_id", "package_id", "package_address", "manifest_address",
    "diff_address", "policy_address", "audit_address", "policy_state",
    "policy_accepted", "audit_accepted", "member_count", "member_byte_count",
    "package_byte_count", "content_address",
)
CATALOG_FIELDS = (
    "catalog_id", "version", "boundary", "entry_count", "accepted_count",
    "ready_count", "blocked_count", "total_package_bytes", "total_member_bytes",
    "entries", "content_address",
)


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str, maximum: int = 256) -> str:
    value = _text(value, field, maximum)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field)
    if value.endswith(":pending"):
        return value
    digest = value.rsplit(":", 1)[-1]
    if not value.startswith(prefix + ":") or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


@dataclass(frozen=True)
class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyPackageCatalogDiffPolicyPackageCatalogEntry:
    ordinal: int
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
    member_count: int
    member_byte_count: int
    package_byte_count: int
    content_address: str

    def __post_init__(self) -> None:
        _count(self.ordinal, "handoff package catalog entry ordinal", MAX_ENTRIES)
        _label(self.entry_id, "handoff package catalog entry ID")
        _label(self.package_id, "handoff package ID")
        _address(self.package_address, "handoff package address", PACKAGE_PREFIX)
        _address(self.manifest_address, "handoff package manifest address", MANIFEST_PREFIX)
        _address(self.diff_address, "handoff package diff address", DIFF_PREFIX)
        _address(self.policy_address, "handoff package policy address", POLICY_PREFIX)
        _address(self.audit_address, "handoff package audit address", AUDIT_PREFIX)
        if self.policy_state not in {"ready", "blocked"}:
            raise ValidationError("handoff package catalog policy state is unsupported")
        _bool(self.policy_accepted, "handoff package catalog policy acceptance")
        _bool(self.audit_accepted, "handoff package catalog audit acceptance")
        _count(self.member_count, "handoff package member count", 16)
        _count(self.member_byte_count, "handoff package member byte count", MAX_PACKAGE_BYTES)
        _count(self.package_byte_count, "handoff package byte count", MAX_PACKAGE_BYTES)
        _address(self.content_address, "handoff package catalog entry address", ENTRY_PREFIX)
        if not self.content_address.endswith(":pending") and address_entry(self) != self.content_address:
            raise ValidationError("handoff package catalog entry address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in ENTRY_FIELDS}


def address_entry(value: DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyPackageCatalogDiffPolicyPackageCatalogEntry) -> str:
    if not isinstance(value, DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyPackageCatalogDiffPolicyPackageCatalogEntry):
        raise ValidationError("handoff package catalog entry addressing requires its typed contract")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ENTRY_PREFIX)


@dataclass(frozen=True)
class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyPackageCatalogDiffPolicyPackageCatalog:
    catalog_id: str
    version: str
    boundary: str
    entry_count: int
    accepted_count: int
    ready_count: int
    blocked_count: int
    total_package_bytes: int
    total_member_bytes: int
    entries: tuple[DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyPackageCatalogDiffPolicyPackageCatalogEntry, ...]
    content_address: str

    def __post_init__(self) -> None:
        _label(self.catalog_id, "handoff package catalog ID")
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("handoff package catalog identity is not current")
        _count(self.entry_count, "handoff package catalog entry count", MAX_ENTRIES)
        _count(self.accepted_count, "handoff package catalog accepted count", MAX_ENTRIES)
        _count(self.ready_count, "handoff package catalog ready count", MAX_ENTRIES)
        _count(self.blocked_count, "handoff package catalog blocked count", MAX_ENTRIES)
        _count(self.total_package_bytes, "handoff package catalog package byte total", MAX_TOTAL_PACKAGE_BYTES)
        _count(self.total_member_bytes, "handoff package catalog member byte total", MAX_TOTAL_MEMBER_BYTES)
        if len(self.entries) > MAX_ENTRIES or self.entry_count != len(self.entries) or tuple(item.ordinal for item in self.entries) != tuple(range(1, self.entry_count + 1)):
            raise ValidationError("handoff package catalog entries do not replay")
        if len({item.entry_id for item in self.entries}) != self.entry_count or len({item.package_id for item in self.entries}) != self.entry_count or len({item.package_address for item in self.entries}) != self.entry_count:
            raise ValidationError("handoff package catalog entries contain duplicate identities")
        if self.accepted_count != sum(item.policy_accepted and item.audit_accepted for item in self.entries) or self.ready_count != sum(item.policy_state == "ready" for item in self.entries) or self.blocked_count != sum(item.policy_state == "blocked" for item in self.entries) or self.total_package_bytes != sum(item.package_byte_count for item in self.entries) or self.total_member_bytes != sum(item.member_byte_count for item in self.entries):
            raise ValidationError("handoff package catalog aggregates do not replay")
        _address(self.content_address, "handoff package catalog address", CATALOG_PREFIX)
        if not self.content_address.endswith(":pending") and address_catalog(self) != self.content_address:
            raise ValidationError("handoff package catalog address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"catalog_id": self.catalog_id, "version": VERSION, "boundary": BOUNDARY, "entry_count": self.entry_count, "accepted_count": self.accepted_count, "ready_count": self.ready_count, "blocked_count": self.blocked_count, "total_package_bytes": self.total_package_bytes, "total_member_bytes": self.total_member_bytes, "entries": tuple(item.to_dict() for item in self.entries), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in CATALOG_FIELDS if field != "entries"}


def address_catalog(value: DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyPackageCatalogDiffPolicyPackageCatalog) -> str:
    if not isinstance(value, DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyPackageCatalogDiffPolicyPackageCatalog):
        raise ValidationError("handoff package catalog addressing requires its typed contract")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CATALOG_PREFIX)


def entry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded-data packet-package policy handoff catalog entry", "type": "object", "additionalProperties": False, "required": list(ENTRY_FIELDS), "properties": {field: {"type": "integer", "minimum": 0} if field in {"ordinal", "member_count", "member_byte_count", "package_byte_count"} else {"type": "boolean"} if field in {"policy_accepted", "audit_accepted"} else {"enum": ["ready", "blocked"]} if field == "policy_state" else {"type": "string"} for field in ENTRY_FIELDS}}


def catalog_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded-data packet-package policy handoff catalog", "type": "object", "additionalProperties": False, "required": list(CATALOG_FIELDS), "properties": {field: {"type": "array", "items": entry_schema(), "maxItems": MAX_ENTRIES} if field == "entries" else {"type": "integer", "minimum": 0} if field.endswith("count") or field.endswith("bytes") else {"const": VERSION} if field == "version" else {"const": BOUNDARY} if field == "boundary" else {"type": "string"} for field in CATALOG_FIELDS}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "source_free": True, "content_addressed": True, "bounded": True, "max_entries": MAX_ENTRIES, "max_package_bytes": MAX_PACKAGE_BYTES, "max_total_package_bytes": MAX_TOTAL_PACKAGE_BYTES, "max_total_member_bytes": MAX_TOTAL_MEMBER_BYTES, "operations": ("build_catalog", "catalog_from_mapping", "catalog_json", "catalog_csv", "render_catalog_markdown", "query_catalog", "verify_catalog")}


__all__ = ["BOUNDARY", "CATALOG_FIELDS", "CATALOG_PREFIX", "ENTRY_FIELDS", "ENTRY_PREFIX", "MAX_ENTRIES", "MAX_PACKAGE_BYTES", "MAX_TOTAL_MEMBER_BYTES", "MAX_TOTAL_PACKAGE_BYTES", "PACKAGE_VERSION", "VERSION", "DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyPackageCatalogDiffPolicyPackageCatalog", "DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogDiffPolicyPackageCatalogDiffPolicyPackageCatalogEntry", "address_catalog", "address_entry", "capabilities", "catalog_schema", "entry_schema"]
