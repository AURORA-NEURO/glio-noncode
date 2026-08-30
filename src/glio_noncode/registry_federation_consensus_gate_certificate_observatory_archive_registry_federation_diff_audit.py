"""Independent assurance for federation change sets."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = diff_model.VERSION + "-audit-v1"
BOUNDARY = diff_model.BOUNDARY + "_audit"
AUDIT_PREFIX = diff_model.DIFF_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("item-count", "item-order", "action-bound", "counter-replay", "transition-replay", "evidence", "address-replay", "public-boundary")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} must use its public address namespace")
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
    return diff_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffAuditCheck:
    FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "federation diff audit ordinal", len(CHECK_IDS))
        self.check_id = _label(check_id, "federation diff audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("federation diff audit check ID is unsupported")
        self.passed = _bool(passed, "federation diff audit result")
        self.detail = _text(detail, "federation diff audit detail")
        self.evidence_addresses = tuple(_text(item, "federation diff audit evidence", 2048) for item in _sequence(evidence_addresses, "federation diff audit evidence", diff_model.MAX_ITEMS + 2))
        self.content_address = _address(content_address, "federation diff audit check address", CHECK_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "federation diff audit check address")
        self._validate()

    def _validate(self) -> None:
        if not self.evidence_addresses or not _public(self.to_dict()):
            raise ValidationError("federation diff audit check is invalid")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("federation diff audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffAuditCheck":
        value = _mapping(value, "federation diff audit check")
        _strict(value, set(cls.FIELDS), "federation diff audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffAuditCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffAudit:
    FIELDS = ("diff_id", "diff_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, diff_id: str, diff_address: str, checks: Sequence[RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffAuditCheck], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.diff_id = _label(diff_id, "federation diff audit ID")
        self.diff_address = _address(diff_address, "federation diff audit diff address", diff_model.DIFF_PREFIX)
        self.checks = tuple(item if isinstance(item, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffAuditCheck) else RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffAuditCheck.from_mapping(item) for item in _sequence(checks, "federation diff audit checks", len(CHECK_IDS)))
        self.check_count = _count(check_count, "federation diff audit check count", len(CHECK_IDS))
        self.passed_count = _count(passed_count, "federation diff audit passed count", self.check_count)
        self.failed_count = _count(failed_count, "federation diff audit failed count", self.check_count)
        self.accepted = _bool(accepted, "federation diff audit acceptance")
        self.content_address = _address(content_address, "federation diff audit address", AUDIT_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "federation diff audit address")
        self._validate()

    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.passed_count + self.failed_count != self.check_count or self.accepted != (self.failed_count == 0) or tuple(item.ordinal for item in self.checks) != tuple(range(1, len(CHECK_IDS) + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("federation diff audit counters or order are invalid")
        if not _public(self.to_dict()):
            raise ValidationError("federation diff audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("federation diff audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "diff_address": self.diff_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("diff_id", "diff_address", "check_count", "passed_count", "failed_count", "accepted", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffAudit":
        value = _mapping(value, "federation diff audit")
        _strict(value, set(cls.FIELDS), "federation diff audit")
        return cls(value["diff_id"], value["diff_address"], tuple(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "federation diff audit checks", len(CHECK_IDS))), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffAuditCheck:
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffAuditCheck(ordinal, check_id, passed, detail, evidence, CHECK_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffAuditCheck(provisional.ordinal, provisional.check_id, provisional.passed, provisional.detail, provisional.evidence_addresses, address_check(provisional))


def audit_diff(value: diff_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiff) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffAudit:
    value = diff_model.verify_diff(value)
    evidence = tuple(item.content_address for item in value.items)
    derived = {action: sum(item.action == action for item in value.items) for action in diff_model.ACTIONS}
    checks = (
        _check(1, "item-count", value.item_count == len(value.items), "diff item count matches the item set", evidence or (value.content_address,)),
        _check(2, "item-order", tuple(item.ordinal for item in value.items) == tuple(range(1, value.item_count + 1)) and tuple(item.entry_id for item in value.items) == tuple(sorted(item.entry_id for item in value.items)), "diff items are ordered by entry ID", evidence or (value.content_address,)),
        _check(3, "action-bound", all(item.action in diff_model.ACTIONS for item in value.items), "every item uses a known action", evidence or (value.content_address,)),
        _check(4, "counter-replay", all(getattr(value, action + "_count") == derived[action] for action in ("added", "removed", "changed", "unchanged")), "action counters replay from the item set", (value.content_address,)),
        _check(5, "transition-replay", value.resolved_count <= value.changed_count and value.regressed_count <= value.changed_count, "transition counters are bounded by changed items", (value.content_address,)),
        _check(6, "evidence", all(item.evidence_addresses for item in value.items), "every change retains evidence", evidence or (value.content_address,)),
        _check(7, "address-replay", all(diff_model.address_item(item) == item.content_address for item in value.items), "item addresses replay", evidence or (value.content_address,)),
        _check(8, "public-boundary", _public(value.to_dict()), "diff contains only public data", (value.content_address,)),
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffAudit(value.diff_id, value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffAudit(provisional.diff_id, provisional.diff_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffAudit:
    return verify_audit(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffAudit) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffAudit):
        raise ValidationError("federation diff audit verification requires a typed audit")
    value._validate()
    if not value.content_address.endswith(":pending") and address_audit(value) != value.content_address:
        raise ValidationError("federation diff audit address verification failed")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffAuditCheck.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        row = item.to_dict()
        row["evidence_addresses"] = ",".join(row["evidence_addresses"])
        writer.writerow(row)
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffAudit) -> str:
    value = verify_audit(value)
    lines = ["# Archive Registry Federation Diff Audit", "", f"- Passed: `{value.passed_count}/{value.check_count}`", f"- Accepted: `{value.accepted}`", "", "| # | check | passed | detail |", "| ---: | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffAuditCheck.FIELDS), "properties": {"ordinal": {"type": "integer"}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array"}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffAudit.FIELDS), "properties": {"diff_id": {"type": "string"}, "diff_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "independent": True, "operations": ("audit_diff", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "verify_audit"), "check_ids": CHECK_IDS}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "CHECK_PREFIX", "VERSION", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffAudit", "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationDiffAuditCheck", "address_audit", "address_check", "audit_csv", "audit_diff", "audit_from_mapping", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
