"""Independent conservation audit for value-free contract diffs."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract as contract_model
from . import downloaded_data_profile_contract_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-diff-audit-v1"
BOUNDARY = "public_downloaded_data_profile_contract_diff_audit"
AUDIT_PREFIX = "glio-noncode-download-profile-contract-diff-audit"
CHECK_IDS = (
    "exact-fields",
    "public-boundary",
    "contract-linkage",
    "item-conservation",
    "item-order",
    "field-conservation",
    "member-conservation",
    "type-conservation",
    "transition-conservation",
    "nested-addresses",
    "content-address",
    "mapping-round-trip",
)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("diff_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")


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


class DownloadedDataProfileContractDiffAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "contract diff audit check ordinal", len(CHECK_IDS))
        if not self.ordinal:
            raise ValidationError("contract diff audit check ordinal must be positive")
        self.check_id = _label(check_id, "contract diff audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("contract diff audit check ID is unsupported")
        self.passed = _bool(passed, "contract diff audit check result")
        self.detail = _text(detail, "contract diff audit detail", 2048)
        self.evidence_addresses = tuple(_address(item, "contract diff audit evidence address") for item in _sequence(evidence_addresses, "contract diff audit evidence", 16))
        self.content_address = _address(content_address, "contract diff audit check address", AUDIT_PREFIX + "-check") if not str(content_address).endswith(":pending") else _text(content_address, "contract diff audit check address")
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("contract diff audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("contract diff audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractDiffAuditCheck:
        value = _mapping(value, "contract diff audit check")
        _strict(value, set(cls.FIELDS), "contract diff audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractDiffAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX + "-check")


class DownloadedDataProfileContractDiffAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, diff_address: str, checks: Sequence[DownloadedDataProfileContractDiffAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.diff_address = _address(diff_address, "contract diff audit diff address", diff_model.DIFF_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractDiffAuditCheck) else DownloadedDataProfileContractDiffAuditCheck.from_mapping(item) for item in _sequence(checks, "contract diff audit checks", len(CHECK_IDS)))
        self.check_count = _count(check_count, "contract diff audit check count", len(CHECK_IDS))
        self.passed_count = _count(passed_count, "contract diff audit passed count", len(CHECK_IDS))
        self.failed_count = _count(failed_count, "contract diff audit failed count", len(CHECK_IDS))
        self.accepted = _bool(accepted, "contract diff audit acceptance")
        self.content_address = _address(content_address, "contract diff audit address", AUDIT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "contract diff audit address")
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != len(CHECK_IDS) or tuple(item.ordinal for item in self.checks) != tuple(range(1, len(CHECK_IDS) + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0) or not _public(self.to_dict()):
            raise ValidationError("contract diff audit aggregates or public boundary do not replay")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("contract diff audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_address": self.diff_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    def check(self, check_id: str) -> DownloadedDataProfileContractDiffAuditCheck:
        check_id = _label(check_id, "contract diff audit lookup ID")
        for item in self.checks:
            if item.check_id == check_id:
                return item
        raise ValidationError("contract diff audit check was not found")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractDiffAudit:
        value = _mapping(value, "contract diff audit")
        _strict(value, set(cls.FIELDS), "contract diff audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractDiffAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataProfileContractDiffAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "detail": detail, "evidence_addresses": tuple(evidence)[:16]}
    provisional = DownloadedDataProfileContractDiffAuditCheck(**body, content_address=AUDIT_PREFIX + "-check:pending")
    return DownloadedDataProfileContractDiffAuditCheck(**body, content_address=address_check(provisional))


def _expected_attributes(item: diff_model.DownloadedDataProfileContractDiffItem) -> tuple[str, ...]:
    if item.change in {"added", "removed"}:
        return ()
    return tuple(name for name in diff_model._attribute_names(item.resource) if item.left_snapshot.get(name) != item.right_snapshot.get(name))


def audit_diff(value: diff_model.DownloadedDataProfileContractDiff) -> DownloadedDataProfileContractDiffAudit:
    """Run fixed structural checks without access to source values."""

    if not isinstance(value, diff_model.DownloadedDataProfileContractDiff):
        raise ValidationError("contract diff audit requires a typed diff")
    counts = {resource: {change: sum(item.resource == resource and item.change == change for item in value.items) for change in diff_model.CHANGES} for resource in diff_model.RESOURCES}
    evidence = (value.content_address, value.left_contract_address, value.right_contract_address)
    checks = (
        _check(1, "exact-fields", set(value.to_dict()) == set(diff_model.DIFF_FIELDS), "diff exposes exactly its declared public fields", evidence),
        _check(2, "public-boundary", _public(value.to_dict()), "diff and nested snapshots contain no forbidden attribution keys", evidence),
        _check(3, "contract-linkage", value.left_contract_address.startswith(contract_model.CONTRACT_PREFIX + ":") and value.right_contract_address.startswith(contract_model.CONTRACT_PREFIX + ":"), "diff retains both contract addresses", (value.left_contract_address, value.right_contract_address)),
        _check(4, "item-conservation", len(value.items) == sum(sum(entry.values()) for entry in counts.values()) and len({(item.resource, item.identity) for item in value.items}) == len(value.items), "diff items conserve one transition per resource identity", (value.content_address,)),
        _check(5, "item-order", tuple(item.ordinal for item in value.items) == tuple(range(1, len(value.items) + 1)), "diff item ordinals are contiguous", (value.content_address,)),
        _check(6, "field-conservation", value.left_field_count == counts["fields"]["removed"] + counts["fields"]["changed"] + counts["fields"]["unchanged"] and value.right_field_count == counts["fields"]["added"] + counts["fields"]["changed"] + counts["fields"]["unchanged"], "field transitions conserve left and right field inventories", (value.left_contract_address, value.right_contract_address)),
        _check(7, "member-conservation", value.left_member_count == counts["members"]["removed"] + counts["members"]["changed"] + counts["members"]["unchanged"] and value.right_member_count == counts["members"]["added"] + counts["members"]["changed"] + counts["members"]["unchanged"], "member transitions conserve left and right member inventories", (value.left_contract_address, value.right_contract_address)),
        _check(8, "type-conservation", value.type_added_count + value.type_removed_count + value.type_changed_count + value.type_unchanged_count == len(tuple(item for item in value.items if item.resource == "types")), "type transitions conserve the canonical type inventory", (value.left_contract_address, value.right_contract_address)),
        _check(9, "transition-conservation", all(item.changed_attributes == _expected_attributes(item) for item in value.items), "changed attributes replay each pair of value-free snapshots", tuple(item.content_address for item in value.items)),
        _check(10, "nested-addresses", all((not item.left_snapshot or item.left_snapshot.get("content_address") == item.left_address) and (not item.right_snapshot or item.right_snapshot.get("content_address") == item.right_address) for item in value.items), "every snapshot address matches its transition side", tuple(item.content_address for item in value.items)),
        _check(11, "content-address", diff_model.address_diff(value) == value.content_address, "diff content address replays", (value.content_address,)),
        _check(12, "mapping-round-trip", diff_model.diff_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "typed diff mapping round-trips without projection drift", evidence),
    )
    body = {"diff_address": value.content_address, "checks": checks, "check_count": len(checks), "passed_count": sum(item.passed for item in checks), "failed_count": sum(not item.passed for item in checks), "accepted": all(item.passed for item in checks)}
    provisional = DownloadedDataProfileContractDiffAudit(**body, content_address=AUDIT_PREFIX + ":pending")
    return DownloadedDataProfileContractDiffAudit(**body, content_address=address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractDiffAudit:
    return DownloadedDataProfileContractDiffAudit.from_mapping(value)


def audit_json(value: DownloadedDataProfileContractDiffAudit) -> str:
    return canonical_json(DownloadedDataProfileContractDiffAudit.from_mapping(value.to_dict()).to_dict())


def audit_csv(value: DownloadedDataProfileContractDiffAudit) -> str:
    value = DownloadedDataProfileContractDiffAudit.from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] if field != "evidence_addresses" else ";".join(item.evidence_addresses) for field in CHECK_FIELDS) for item in value.checks)
    return stream.getvalue()


def render_audit_markdown(value: DownloadedDataProfileContractDiffAudit) -> str:
    value = DownloadedDataProfileContractDiffAudit.from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Diff Audit", "", f"- Diff: `{value.diff_address}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract diff audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract diff audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"diff_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema(), "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS)}, "check_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "check_ids": CHECK_IDS, "operations": ("audit_diff", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "limits": {"max_checks": len(CHECK_IDS)}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "DownloadedDataProfileContractDiffAudit", "DownloadedDataProfileContractDiffAuditCheck", "address_audit", "address_check", "audit_csv", "audit_diff", "audit_from_mapping", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
