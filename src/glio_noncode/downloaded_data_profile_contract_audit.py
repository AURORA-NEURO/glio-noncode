"""Independent conservation audit for value-free downloaded-data contracts."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile as profile_model
from . import downloaded_data_profile_contract as contract_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-audit-v1"
BOUNDARY = "public_downloaded_data_profile_contract_audit"
AUDIT_PREFIX = "glio-noncode-download-profile-contract-audit"
CHECK_IDS = (
    "exact-fields",
    "public-boundary",
    "profile-linkage",
    "type-conservation",
    "member-conservation",
    "field-conservation",
    "field-state-conservation",
    "member-field-linkage",
    "member-stat-conservation",
    "nested-addresses",
    "content-address",
    "mapping-round-trip",
)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("contract_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")


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


class DownloadedDataProfileContractAuditCheck:
    """One independently recomputable contract conservation check."""

    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "contract audit check ordinal", len(CHECK_IDS))
        if not self.ordinal:
            raise ValidationError("contract audit check ordinal must be positive")
        self.check_id = _label(check_id, "contract audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("contract audit check ID is unsupported")
        self.passed = _bool(passed, "contract audit check result")
        self.detail = _text(detail, "contract audit detail", 2048)
        self.evidence_addresses = tuple(_address(item, "contract audit evidence address") for item in _sequence(evidence_addresses, "contract audit evidence", 16))
        self.content_address = _address(content_address, "contract audit check address", AUDIT_PREFIX + "-check") if not str(content_address).endswith(":pending") else _text(content_address, "contract audit check address")
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("contract audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("contract audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractAuditCheck:
        value = _mapping(value, "contract audit check")
        _strict(value, set(cls.FIELDS), "contract audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX + "-check")


class DownloadedDataProfileContractAudit:
    """Fixed-check audit for an inferred value-free contract."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, contract_address: str, checks: Sequence[DownloadedDataProfileContractAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.contract_address = _address(contract_address, "contract audit contract address", contract_model.CONTRACT_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractAuditCheck) else DownloadedDataProfileContractAuditCheck.from_mapping(item) for item in _sequence(checks, "contract audit checks", len(CHECK_IDS)))
        self.check_count = _count(check_count, "contract audit check count", len(CHECK_IDS))
        self.passed_count = _count(passed_count, "contract audit passed count", len(CHECK_IDS))
        self.failed_count = _count(failed_count, "contract audit failed count", len(CHECK_IDS))
        self.accepted = _bool(accepted, "contract audit acceptance")
        self.content_address = _address(content_address, "contract audit address", AUDIT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "contract audit address")
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != len(CHECK_IDS) or tuple(item.ordinal for item in self.checks) != tuple(range(1, len(CHECK_IDS) + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0) or not _public(self.to_dict()):
            raise ValidationError("contract audit aggregates or public boundary do not replay")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("contract audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"contract_address": self.contract_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    def check(self, check_id: str) -> DownloadedDataProfileContractAuditCheck:
        check_id = _label(check_id, "contract audit lookup ID")
        for item in self.checks:
            if item.check_id == check_id:
                return item
        raise ValidationError("contract audit check was not found")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractAudit:
        value = _mapping(value, "contract audit")
        _strict(value, set(cls.FIELDS), "contract audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataProfileContractAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "detail": detail, "evidence_addresses": tuple(evidence)[:16]}
    provisional = DownloadedDataProfileContractAuditCheck(**body, content_address=AUDIT_PREFIX + "-check:pending")
    return DownloadedDataProfileContractAuditCheck(**body, content_address=address_check(provisional))


def _type_replays(value: contract_model.DownloadedDataProfileContract) -> bool:
    for entry in value.types:
        field_rows = tuple(field for field in value.fields if any(item.value_type == entry.value_type and item.count for item in field.type_counts))
        member_addresses = {address for field in field_rows for address in field.member_addresses}
        observed = sum(next(item.count for item in field.type_counts if item.value_type == entry.value_type) for field in value.fields)
        if entry.field_count != len(field_rows) or entry.member_count != len(member_addresses) or entry.observed_count != observed:
            return False
    return True


def _member_links(value: contract_model.DownloadedDataProfileContract) -> bool:
    fields = {field.field_name: field for field in value.fields}
    members = {member.member_address: member for member in value.members}
    for member in value.members:
        if any(name not in fields or member.member_address not in fields[name].member_addresses for name in member.field_names):
            return False
    for field in value.fields:
        if any(address not in members or field.field_name not in members[address].field_names for address in field.member_addresses):
            return False
    return True


def audit_contract(value: contract_model.DownloadedDataProfileContract) -> DownloadedDataProfileContractAudit:
    """Run fixed contract checks without reading source values."""

    if not isinstance(value, contract_model.DownloadedDataProfileContract):
        raise ValidationError("contract audit requires a typed downloaded data profile contract")
    evidence = (value.content_address, value.profile_address)
    fields = {field.field_name: field for field in value.fields}
    checks = (
        _check(1, "exact-fields", set(value.to_dict()) == set(contract_model.CONTRACT_FIELDS), "contract exposes exactly its declared public fields", evidence),
        _check(2, "public-boundary", _public(value.to_dict()), "contract and nested projections contain no forbidden attribution keys", evidence),
        _check(3, "profile-linkage", value.profile_address.startswith(profile_model.PROFILE_PREFIX + ":"), "contract retains the structural profile address", (value.profile_address,)),
        _check(4, "type-conservation", tuple(item.value_type for item in value.types) == profile_model.VALUE_TYPES and _type_replays(value), "type rows conserve field-level observations, coverage, and canonical order", tuple(item.content_address for item in value.types)),
        _check(5, "member-conservation", len(value.members) == value.member_count and sum(item.record_count for item in value.members) == value.record_count and len({item.member_ordinal for item in value.members}) == value.member_count and tuple(item.member_ordinal for item in value.members) == tuple(sorted(item.member_ordinal for item in value.members)), "member rows conserve records, unique source ordinals, and declared count", tuple(item.content_address for item in value.members)),
        _check(6, "field-conservation", len(value.fields) == value.field_count and tuple(item.field_name for item in value.fields) == tuple(sorted(fields)) and all(item.observed_count + item.missing_count == value.record_count for item in value.fields), "field rows conserve the profile record domain and sorted field union", tuple(item.content_address for item in value.fields)),
        _check(7, "field-state-conservation", value.required_field_count == sum(item.required for item in value.fields) and value.optional_field_count == sum(not item.required for item in value.fields) and value.sparse_field_count == sum(item.state == "sparse" for item in value.fields) and value.mixed_type_field_count == sum(item.state == "mixed" for item in value.fields), "required, optional, sparse, and mixed aggregates replay every field state", evidence),
        _check(8, "member-field-linkage", _member_links(value), "member field inventories and field member addresses are exact inverses", evidence),
        _check(9, "member-stat-conservation", all(member.required_field_count == len(member.required_field_names) and member.optional_field_count == len(member.optional_field_names) and member.mixed_type_field_count == len(member.mixed_type_field_names) and set(member.required_field_names).union(member.optional_field_names) == set(member.field_names) and not set(member.required_field_names).intersection(member.optional_field_names) for member in value.members), "member-local required, optional, and mixed inventories replay their counts", tuple(item.content_address for item in value.members)),
        _check(10, "nested-addresses", all(contract_model.address_type(item) == item.content_address for item in value.types) and all(contract_model.address_field(item) == item.content_address for item in value.fields) and all(contract_model.address_member(item) == item.content_address for item in value.members), "nested type, field, and member addresses replay", evidence),
        _check(11, "content-address", contract_model.address_contract(value) == value.content_address, "contract content address replays from its public projection", (value.content_address,)),
        _check(12, "mapping-round-trip", contract_model.contract_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "typed contract mapping round-trips without projection drift", evidence),
    )
    body = {"contract_address": value.content_address, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks)}
    provisional = DownloadedDataProfileContractAudit(**body, content_address=AUDIT_PREFIX + ":pending")
    return DownloadedDataProfileContractAudit(**body, content_address=address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractAudit:
    return DownloadedDataProfileContractAudit.from_mapping(value)


def audit_json(value: DownloadedDataProfileContractAudit) -> str:
    return canonical_json(DownloadedDataProfileContractAudit.from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataProfileContractAudit) -> str:
    value = DownloadedDataProfileContractAudit.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] if field != "evidence_addresses" else ";".join(item.evidence_addresses) for field in CHECK_FIELDS) for item in value.checks)
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataProfileContractAudit) -> str:
    value = DownloadedDataProfileContractAudit.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Audit", "", f"- Contract: `{value.contract_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"contract_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema(), "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS)}, "check_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "check_ids": CHECK_IDS, "operations": ("audit_contract", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "limits": {"max_checks": len(CHECK_IDS)}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "DownloadedDataProfileContractAudit", "DownloadedDataProfileContractAuditCheck", "address_audit", "address_check", "audit_contract", "audit_csv", "audit_from_mapping", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
