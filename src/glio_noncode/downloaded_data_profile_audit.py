"""Independent conservation audit for downloaded-data structural profiles."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile as profile_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-audit-v1"
BOUNDARY = "public_downloaded_data_profile_audit"
AUDIT_PREFIX = "glio-noncode-download-profile-audit"
CHECK_IDS = (
    "exact-fields",
    "public-boundary",
    "batch-linkage",
    "type-count-conservation",
    "member-count-conservation",
    "member-record-conservation",
    "shape-count-conservation",
    "field-count-conservation",
    "field-presence-conservation",
    "nested-addresses",
    "content-address",
    "mapping-round-trip",
)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("profile_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")


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


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
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


class DownloadedDataProfileAuditCheck:
    """One independently recomputable profile conservation check."""

    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "profile audit check ordinal", len(CHECK_IDS))
        if not self.ordinal:
            raise ValidationError("profile audit check ordinal must be positive")
        self.check_id = _label(check_id, "profile audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("profile audit check ID is unsupported")
        self.passed = _bool(passed, "profile audit check result")
        self.detail = _text(detail, "profile audit detail", 2048)
        self.evidence_addresses = tuple(_address(item, "profile audit evidence address") for item in _sequence(evidence_addresses, "profile audit evidence", 16))
        self.content_address = _address(content_address, "profile audit check address", AUDIT_PREFIX + "-check") if not str(content_address).endswith(":pending") else _text(content_address, "profile audit check address")
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("profile audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("profile audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileAuditCheck:
        value = _mapping(value, "profile audit check")
        _strict(value, set(cls.FIELDS), "profile audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX + "-check")


class DownloadedDataProfileAudit:
    """Fixed-check audit for a value-free structural profile."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, profile_address: str, checks: Sequence[DownloadedDataProfileAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.profile_address = _address(profile_address, "profile audit profile address", profile_model.PROFILE_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileAuditCheck) else DownloadedDataProfileAuditCheck.from_mapping(item) for item in _sequence(checks, "profile audit checks", len(CHECK_IDS)))
        self.check_count = _count(check_count, "profile audit check count", len(CHECK_IDS))
        self.passed_count = _count(passed_count, "profile audit passed count", len(CHECK_IDS))
        self.failed_count = _count(failed_count, "profile audit failed count", len(CHECK_IDS))
        self.accepted = _bool(accepted, "profile audit acceptance")
        self.content_address = _address(content_address, "profile audit address", AUDIT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "profile audit address")
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != len(CHECK_IDS) or tuple(item.ordinal for item in self.checks) != tuple(range(1, len(CHECK_IDS) + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0) or not _public(self.to_dict()):
            raise ValidationError("profile audit aggregates or public boundary do not replay")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("profile audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"profile_address": self.profile_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    def check(self, check_id: str) -> DownloadedDataProfileAuditCheck:
        check_id = _label(check_id, "profile audit lookup ID")
        for item in self.checks:
            if item.check_id == check_id:
                return item
        raise ValidationError("profile audit check was not found")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileAudit:
        value = _mapping(value, "profile audit")
        _strict(value, set(cls.FIELDS), "profile audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataProfileAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "detail": detail, "evidence_addresses": tuple(evidence)[:16]}
    provisional = DownloadedDataProfileAuditCheck(**body, content_address=AUDIT_PREFIX + "-check:pending")
    return DownloadedDataProfileAuditCheck(**body, content_address=address_check(provisional))


def _all_nested_addresses(profile: profile_model.DownloadedDataProfile) -> bool:
    if profile_model.address_profile(profile) != profile.content_address:
        return False
    for type_count in profile.type_counts:
        if profile_model.address_type_count(type_count) != type_count.content_address:
            return False
    for field in profile.fields:
        if profile_model.address_field(field) != field.content_address:
            return False
        if any(profile_model.address_type_count(item) != item.content_address for item in field.type_counts):
            return False
    for member in profile.members:
        if profile_model.address_member(member) != member.content_address:
            return False
        if any(profile_model.address_shape_count(item) != item.content_address for item in member.shape_counts):
            return False
        if any(profile_model.address_field(item) != item.content_address for item in member.fields):
            return False
        if any(profile_model.address_type_count(item) != item.content_address for field in member.fields for item in field.type_counts):
            return False
    return True


def audit_profile(value: profile_model.DownloadedDataProfile) -> DownloadedDataProfileAudit:
    """Run all fixed profile checks without needing the source values."""

    if not isinstance(value, profile_model.DownloadedDataProfile):
        raise ValidationError("profile audit requires a typed downloaded data profile")
    evidence = (value.content_address, value.batch_address)
    global_fields = {item.field_name: item for item in value.fields}
    member_fields = {field.field_name: field for member in value.members for field in member.fields}
    member_field_observed: dict[str, int] = {}
    member_record_total = sum(member.record_count for member in value.members)
    for member in value.members:
        for field in member.fields:
            member_field_observed[field.field_name] = member_field_observed.get(field.field_name, 0) + field.observed_count
    member_field_missing = {
        name: member_record_total - observed
        for name, observed in member_field_observed.items()
    }
    checks = (
        _check(1, "exact-fields", set(value.to_dict()) == set(profile_model.PROFILE_FIELDS), "profile exposes exactly its declared public fields", evidence),
        _check(2, "public-boundary", _public(value.to_dict()), "profile and nested projections contain no forbidden attribution keys", evidence),
        _check(3, "batch-linkage", value.batch_address.startswith(ingestion_model.INGEST_PREFIX + ":"), "profile retains the ingestion batch address", (value.batch_address,)),
        _check(4, "type-count-conservation", tuple(item.value_type for item in value.type_counts) == profile_model.VALUE_TYPES and sum(item.count for item in value.type_counts) == value.record_count, "profile value-type counts conserve every ingested record", (value.content_address,)),
        _check(5, "member-count-conservation", len(value.members) == value.member_count and len({item.member_name for item in value.members}) == value.member_count and sum(item.record_count for item in value.members) == value.record_count, "member identities and record counts conserve the batch", tuple(item.content_address for item in value.members)),
        _check(6, "member-record-conservation", all(sum(item.count for item in member.shape_counts) == member.record_count for member in value.members), "member shape counts conserve every member record", tuple(item.content_address for item in value.members)),
        _check(7, "shape-count-conservation", all(tuple(item.shape for item in member.shape_counts) == tuple(shape for shape in profile_model.SHAPES if any(entry.shape == shape for entry in member.shape_counts)) for member in value.members), "member shape projections are ordered and complete", tuple(item.content_address for item in value.members)),
        _check(8, "field-count-conservation", len(value.fields) == value.field_count and len({item.field_name for item in value.fields}) == value.field_count and set(global_fields) == set(member_fields), "global and member field inventories conserve the same field union", tuple(item.content_address for item in value.fields)),
        _check(9, "field-presence-conservation", all(global_fields[name].observed_count == member_field_observed.get(name, -1) and global_fields[name].missing_count == member_field_missing.get(name, -1) for name in global_fields), "global field presence counts equal the member projections", tuple(item.content_address for item in value.fields)),
        _check(10, "nested-addresses", _all_nested_addresses(value), "nested type, shape, field, member, and profile addresses replay", evidence),
        _check(11, "content-address", profile_model.address_profile(value) == value.content_address, "profile content address replays from its public projection", (value.content_address,)),
        _check(12, "mapping-round-trip", profile_model.profile_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "typed profile mapping round-trips without projection drift", evidence),
    )
    body = {"profile_address": value.content_address, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks)}
    provisional = DownloadedDataProfileAudit(**body, content_address=AUDIT_PREFIX + ":pending")
    return DownloadedDataProfileAudit(**body, content_address=address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileAudit:
    return DownloadedDataProfileAudit.from_mapping(value)


def audit_json(value: DownloadedDataProfileAudit) -> str:
    return canonical_json(DownloadedDataProfileAudit.from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataProfileAudit) -> str:
    value = DownloadedDataProfileAudit.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] if field != "evidence_addresses" else ";".join(item.evidence_addresses) for field in CHECK_FIELDS) for item in value.checks)
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataProfileAudit) -> str:
    value = DownloadedDataProfileAudit.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Audit", "", f"- Profile: `{value.profile_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"profile_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema(), "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS)}, "check_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "version": VERSION, "check_ids": CHECK_IDS, "operations": ("audit_profile", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "limits": {"max_checks": len(CHECK_IDS)}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "DownloadedDataProfileAudit", "DownloadedDataProfileAuditCheck", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_profile", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
