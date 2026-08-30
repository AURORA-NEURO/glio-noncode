"""Independent checks for downloaded structured-data catalogs."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_catalog as catalog_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = catalog_model.VERSION + "-audit-v1"
BOUNDARY = catalog_model.BOUNDARY + "_audit"
AUDIT_PREFIX = catalog_model.CATALOG_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("catalog-address", "member-order", "member-uniqueness", "member-count", "byte-count", "kind-count", "digest-shape", "source-size", "structural-bounds", "public-boundary", "catalog-replay", "source-policy")
MAX_CHECKS = len(CHECK_IDS)


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
    return catalog_model._public(value)


class DownloadedDataCatalogAuditCheck:
    FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "downloaded catalog audit ordinal", MAX_CHECKS)
        self.check_id = _label(check_id, "downloaded catalog audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("downloaded catalog audit check ID is unsupported")
        self.passed = _bool(passed, "downloaded catalog audit result")
        self.detail = _text(detail, "downloaded catalog audit detail")
        self.evidence_addresses = tuple(_text(item, "downloaded catalog audit evidence", 2048) for item in _sequence(evidence_addresses, "downloaded catalog audit evidence", catalog_model.MAX_MEMBERS + 1))
        self.content_address = _address(content_address, "downloaded catalog audit check address", CHECK_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "downloaded catalog audit check address")
        self._validate()

    def _validate(self) -> None:
        if not self.evidence_addresses or not _public(self.to_dict()):
            raise ValidationError("downloaded catalog audit check is incomplete or private")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("downloaded catalog audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataCatalogAuditCheck:
        value = _mapping(value, "downloaded catalog audit check")
        _strict(value, set(cls.FIELDS), "downloaded catalog audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataCatalogAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataCatalogAudit:
    FIELDS = ("catalog_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, catalog_address: str, checks: Sequence[DownloadedDataCatalogAuditCheck], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.catalog_address = _address(catalog_address, "downloaded catalog audit catalog address", catalog_model.CATALOG_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataCatalogAuditCheck) else DownloadedDataCatalogAuditCheck.from_mapping(item) for item in _sequence(checks, "downloaded catalog audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "downloaded catalog audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "downloaded catalog audit passed count", self.check_count)
        self.failed_count = _count(failed_count, "downloaded catalog audit failed count", self.check_count)
        self.accepted = _bool(accepted, "downloaded catalog audit acceptance")
        self.content_address = _address(content_address, "downloaded catalog audit address", AUDIT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "downloaded catalog audit address")
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.passed_count + self.failed_count != self.check_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("downloaded catalog audit counters are not conserved")
        if tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("downloaded catalog audit checks are not canonical")
        if not _public(self.to_dict()):
            raise ValidationError("downloaded catalog audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("downloaded catalog audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"catalog_address": self.catalog_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("catalog_address", "check_count", "passed_count", "failed_count", "accepted", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataCatalogAudit:
        value = _mapping(value, "downloaded catalog audit")
        _strict(value, set(cls.FIELDS), "downloaded catalog audit")
        checks = tuple(DownloadedDataCatalogAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "downloaded catalog audit checks", MAX_CHECKS))
        return cls(value["catalog_address"], checks, value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: DownloadedDataCatalogAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataCatalogAuditCheck:
    provisional = DownloadedDataCatalogAuditCheck(ordinal, check_id, passed, detail, evidence, CHECK_PREFIX + ":pending")
    return DownloadedDataCatalogAuditCheck(provisional.ordinal, provisional.check_id, provisional.passed, provisional.detail, provisional.evidence_addresses, address_check(provisional))


def audit_catalog(value: catalog_model.DownloadedDataCatalog) -> DownloadedDataCatalogAudit:
    value = catalog_model.verify_catalog(value)
    members = value.members
    evidence = tuple(item.content_address for item in members[:4]) or (value.content_address,)
    checks = (
        _check(1, "catalog-address", catalog_model.address_catalog(value) == value.content_address, "catalog content address replays", (value.content_address,)),
        _check(2, "member-order", tuple(item.ordinal for item in members) == tuple(range(1, value.member_count + 1)), "member ordinals are contiguous", evidence),
        _check(3, "member-uniqueness", len({item.member_name for item in members}) == value.member_count, "member names are unique", evidence),
        _check(4, "member-count", value.included_count == value.member_count == len(members), "member counts are conserved", (value.content_address,)),
        _check(5, "byte-count", value.total_data_bytes == sum(item.byte_size for item in members), "data byte total replays", evidence),
        _check(6, "kind-count", value.json_count == sum(item.data_kind == "json" for item in members) and value.delimited_count == sum(item.data_kind == "delimited" for item in members) and value.yaml_count == sum(item.data_kind == "yaml" for item in members), "data-kind counts replay", evidence),
        _check(7, "digest-shape", all(item.digest.startswith(catalog_model.MEMBER_PREFIX + ":") for item in members), "member digests use the public namespace", evidence),
        _check(8, "source-size", 0 < value.source_size <= catalog_model.MAX_TOTAL_BYTES, "source size remains within the source bound", (value.content_address,)),
        _check(9, "structural-bounds", all(item.byte_size <= catalog_model.MAX_MEMBER_BYTES and item.record_count <= catalog_model.MAX_ROWS and item.field_count <= catalog_model.MAX_FIELDS for item in members), "every member remains within structural bounds", evidence),
        _check(10, "public-boundary", _public(value.to_dict()), "catalog contains no prohibited private fields", (value.content_address,)),
        _check(11, "catalog-replay", catalog_model.catalog_from_mapping(value.to_dict()).content_address == value.content_address, "catalog mapping replay succeeds", (value.content_address,)),
        _check(12, "source-policy", all(item.suffix in catalog_model.DATA_SUFFIXES and item.data_kind in {"json", "delimited", "yaml"} for item in members), "only structured data suffixes are included", evidence),
    )
    provisional = DownloadedDataCatalogAudit(value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return DownloadedDataCatalogAudit(provisional.catalog_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataCatalogAudit:
    return verify_audit(DownloadedDataCatalogAudit.from_mapping(value))


def verify_audit(value: DownloadedDataCatalogAudit) -> DownloadedDataCatalogAudit:
    if not isinstance(value, DownloadedDataCatalogAudit):
        raise ValidationError("downloaded catalog audit verification requires a typed audit")
    value._validate()
    if not value.content_address.endswith(":pending") and address_audit(value) != value.content_address:
        raise ValidationError("downloaded catalog audit address verification failed")
    return value


def audit_json(value: DownloadedDataCatalogAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: DownloadedDataCatalogAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=DownloadedDataCatalogAuditCheck.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        row = item.to_dict()
        row["evidence_addresses"] = ",".join(row["evidence_addresses"])
        writer.writerow(row)
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataCatalogAudit) -> str:
    value = verify_audit(value)
    lines = ["# Downloaded Data Catalog Audit", "", f"- Passed: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Catalog: `{value.catalog_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(DownloadedDataCatalogAuditCheck.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(DownloadedDataCatalogAudit.FIELDS), "properties": {"catalog_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "independent": True, "operations": ("audit_catalog", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "verify_audit"), "check_ids": CHECK_IDS}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "CHECK_PREFIX", "DownloadedDataCatalogAudit", "DownloadedDataCatalogAuditCheck", "VERSION", "address_audit", "address_check", "audit_catalog", "audit_csv", "audit_from_mapping", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
