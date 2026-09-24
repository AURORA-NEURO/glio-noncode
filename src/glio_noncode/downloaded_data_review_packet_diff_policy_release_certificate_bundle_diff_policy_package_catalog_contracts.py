"""Typed contracts for source-free release-bundle policy packet catalogs."""

# ruff: noqa: E501

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash

VERSION = "downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-v1"
BOUNDARY = "public_downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog"
CATALOG_PREFIX = "glio-noncode-download-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog"
ENTRY_PREFIX = CATALOG_PREFIX + "-entry"
MAX_ENTRIES = 256
MAX_PACKAGE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_PACKAGE_BYTES = 256 * 1024 * 1024
ENTRY_FIELDS = (
    "ordinal", "entry_id", "package_id", "package_address", "diff_address", "policy_address", "audit_address",
    "policy_state", "policy_accepted", "audit_accepted", "member_count", "package_byte_count", "content_address",
)
CATALOG_FIELDS = (
    "catalog_id", "version", "boundary", "entry_count", "accepted_count", "ready_count", "blocked_count",
    "total_package_bytes", "entries", "content_address",
)


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 256)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 4096)
    if value.endswith(":pending"):
        return value
    if not value.startswith(prefix + ":") or len(value.rsplit(":", 1)[-1]) != 64 or any(char not in "0123456789abcdef" for char in value.rsplit(":", 1)[-1]):
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
class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogEntry:
    """A public descriptor for one portable review packet."""

    ordinal: int
    entry_id: str
    package_id: str
    package_address: str
    diff_address: str
    policy_address: str
    audit_address: str
    policy_state: str
    policy_accepted: bool
    audit_accepted: bool
    member_count: int
    package_byte_count: int
    content_address: str

    def __post_init__(self) -> None:
        _count(self.ordinal, "release packet catalog entry ordinal", MAX_ENTRIES)
        _label(self.entry_id, "release packet catalog entry ID")
        _label(self.package_id, "release packet catalog package ID")
        _address(self.package_address, "release packet catalog package address", "glio-noncode-download-review-packet-diff-policy-release-certificate-bundle-diff-policy-package")
        _address(self.diff_address, "release packet catalog diff address", "glio-noncode-download-review-packet-diff-policy-release-certificate-bundle-diff")
        _address(self.policy_address, "release packet catalog policy address", "glio-noncode-download-review-packet-diff-policy-release-certificate-bundle-diff-policy")
        _address(self.audit_address, "release packet catalog audit address", "glio-noncode-download-review-packet-diff-policy-release-certificate-bundle-diff-policy-audit")
        if self.policy_state not in {"ready", "blocked"}:
            raise ValidationError("release packet catalog policy state is unsupported")
        _bool(self.policy_accepted, "release packet catalog policy acceptance")
        _bool(self.audit_accepted, "release packet catalog audit acceptance")
        _count(self.member_count, "release packet catalog member count", 16)
        _count(self.package_byte_count, "release packet catalog package byte count", MAX_PACKAGE_BYTES)
        _address(self.content_address, "release packet catalog entry address", ENTRY_PREFIX)
        if not self.content_address.endswith(":pending") and address_entry(self) != self.content_address:
            raise ValidationError("release packet catalog entry address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in ENTRY_FIELDS}


def address_entry(value: DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogEntry) -> str:
    if not isinstance(value, DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogEntry):
        raise ValidationError("release packet catalog entry addressing requires its typed contract")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ENTRY_PREFIX)


@dataclass(frozen=True)
class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalog:
    """A bounded, source-free catalog of portable review packets."""

    catalog_id: str
    version: str
    boundary: str
    entry_count: int
    accepted_count: int
    ready_count: int
    blocked_count: int
    total_package_bytes: int
    entries: tuple[DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogEntry, ...]
    content_address: str

    def __post_init__(self) -> None:
        _label(self.catalog_id, "release packet catalog ID")
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("release packet catalog identity is not current")
        _count(self.entry_count, "release packet catalog entry count", MAX_ENTRIES)
        _count(self.accepted_count, "release packet catalog accepted count", MAX_ENTRIES)
        _count(self.ready_count, "release packet catalog ready count", MAX_ENTRIES)
        _count(self.blocked_count, "release packet catalog blocked count", MAX_ENTRIES)
        _count(self.total_package_bytes, "release packet catalog package byte total", MAX_TOTAL_PACKAGE_BYTES)
        if len(self.entries) > MAX_ENTRIES or self.entry_count != len(self.entries):
            raise ValidationError("release packet catalog entry counts do not replay")
        if tuple(item.ordinal for item in self.entries) != tuple(range(1, self.entry_count + 1)):
            raise ValidationError("release packet catalog entry order is not canonical")
        if len({item.entry_id for item in self.entries}) != self.entry_count or len({item.package_id for item in self.entries}) != self.entry_count or len({item.package_address for item in self.entries}) != self.entry_count:
            raise ValidationError("release packet catalog entries contain duplicate identities")
        if self.accepted_count != sum(item.policy_accepted and item.audit_accepted for item in self.entries):
            raise ValidationError("release packet catalog accepted count does not replay")
        if self.ready_count != sum(item.policy_state == "ready" for item in self.entries) or self.blocked_count != sum(item.policy_state == "blocked" for item in self.entries):
            raise ValidationError("release packet catalog state counts do not replay")
        if self.total_package_bytes != sum(item.package_byte_count for item in self.entries):
            raise ValidationError("release packet catalog byte total does not replay")
        _address(self.content_address, "release packet catalog address", CATALOG_PREFIX)
        if not self.content_address.endswith(":pending") and address_catalog(self) != self.content_address:
            raise ValidationError("release packet catalog address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"catalog_id": self.catalog_id, "version": self.version, "boundary": self.boundary, "entry_count": self.entry_count, "accepted_count": self.accepted_count, "ready_count": self.ready_count, "blocked_count": self.blocked_count, "total_package_bytes": self.total_package_bytes, "entries": tuple(item.to_dict() for item in self.entries), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in CATALOG_FIELDS if field != "entries"}


def address_catalog(value: DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalog) -> str:
    if not isinstance(value, DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalog):
        raise ValidationError("release packet catalog addressing requires its typed contract")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CATALOG_PREFIX)


def entry_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data release packet catalog entry", "type": "object", "additionalProperties": False, "required": list(ENTRY_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "entry_id": {"type": "string"}, "package_id": {"type": "string"}, "package_address": {"type": "string"}, "diff_address": {"type": "string"}, "policy_address": {"type": "string"}, "audit_address": {"type": "string"}, "policy_state": {"enum": ["ready", "blocked"]}, "policy_accepted": {"type": "boolean"}, "audit_accepted": {"type": "boolean"}, "member_count": {"type": "integer", "minimum": 0}, "package_byte_count": {"type": "integer", "minimum": 0}, "content_address": {"type": "string"}}}


def catalog_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data release packet catalog", "type": "object", "additionalProperties": False, "required": list(CATALOG_FIELDS), "properties": {"catalog_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "entry_count": {"type": "integer", "minimum": 0}, "accepted_count": {"type": "integer", "minimum": 0}, "ready_count": {"type": "integer", "minimum": 0}, "blocked_count": {"type": "integer", "minimum": 0}, "total_package_bytes": {"type": "integer", "minimum": 0}, "entries": {"type": "array", "items": entry_schema(), "maxItems": MAX_ENTRIES}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "source_free": True, "content_addressed": True, "bounded": True, "max_entries": MAX_ENTRIES, "max_package_bytes": MAX_PACKAGE_BYTES, "max_total_package_bytes": MAX_TOTAL_PACKAGE_BYTES, "operations": ("build_catalog", "catalog_from_mapping", "catalog_json", "catalog_csv", "render_catalog_markdown", "query_catalog", "verify_catalog")}


__all__ = ["BOUNDARY", "CATALOG_FIELDS", "CATALOG_PREFIX", "ENTRY_FIELDS", "ENTRY_PREFIX", "MAX_ENTRIES", "MAX_PACKAGE_BYTES", "MAX_TOTAL_PACKAGE_BYTES", "VERSION", "DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalog", "DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffPolicyPackageCatalogEntry", "address_catalog", "address_entry", "capabilities", "catalog_schema", "entry_schema"]
