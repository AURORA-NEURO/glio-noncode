"""Independent audit for exact certificate-observatory replay receipts."""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_replay as replay_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = replay_model.VERSION + "-audit-v1"
BOUNDARY = replay_model.BOUNDARY + "_audit"
AUDIT_PREFIX = replay_model.REPLAY_PREFIX + "-audit"
FINDING_PREFIX = replay_model.REPLAY_PREFIX + "-audit-finding"
CHECK_IDS = ("exact-fields", "public-boundary", "package-address", "nested-addresses", "member-count", "member-vocabulary", "byte-equality", "projection-equality", "package-audit", "mapping-round-trip", "content-address", "deterministic-members", "path-free")


def _text(value: Any, field: str, maximum: int = replay_model.MAX_TEXT, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192, required=True)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 512, required=True)
    if "/" in value or "\\" in value or '"' in value or not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an unsupported address")
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


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    forbidden = {"agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"}
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and key.lower() not in forbidden and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return all(marker not in lowered for marker in ("c:\\", "d:\\", "/users/", "/home/", "\\users\\", "\\home\\"))
    return value is None or isinstance(value, (bool, int, float))


class RegistryFederationConsensusGateCertificateObservatoryReplayAuditFinding:
    FIELDS = ("ordinal", "check_id", "passed", "observed", "expected", "detail", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, observed: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal, self.check_id = _count(ordinal, "observatory replay audit finding ordinal", len(CHECK_IDS), positive=True), _label(check_id, "observatory replay audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("observatory replay audit check ID is unsupported")
        self.passed, self.observed, self.expected, self.detail = _bool(passed, "observatory replay audit result"), _text(observed, "observatory replay audit observed"), _text(expected, "observatory replay audit expected"), _text(detail, "observatory replay audit detail", required=True)
        self.content_address = _address(content_address, "observatory replay finding address", FINDING_PREFIX)
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("observatory replay finding address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("observatory replay finding crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryReplayAuditFinding:
        value = _mapping(value, "observatory replay audit finding")
        _strict(value, set(cls.FIELDS), "observatory replay audit finding")
        return cls(*(value[field] for field in cls.FIELDS))


def address_finding(value: RegistryFederationConsensusGateCertificateObservatoryReplayAuditFinding) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


class RegistryFederationConsensusGateCertificateObservatoryReplayAudit:
    FIELDS = ("replay_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, replay_address: str, checks: Sequence[RegistryFederationConsensusGateCertificateObservatoryReplayAuditFinding], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.replay_address = _address(replay_address, "audited observatory replay address", replay_model.REPLAY_PREFIX)
        self.checks = tuple(checks)
        if any(not isinstance(item, RegistryFederationConsensusGateCertificateObservatoryReplayAuditFinding) for item in self.checks):
            raise ValidationError("observatory replay audit checks must be typed")
        self.check_count, self.passed_count, self.failed_count = _count(check_count, "observatory replay audit check count", len(CHECK_IDS), positive=True), _count(passed_count, "observatory replay audit passed count", check_count), _count(failed_count, "observatory replay audit failed count", check_count)
        self.accepted = _bool(accepted, "observatory replay audit acceptance")
        if len(self.checks) != self.check_count or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != self.check_count - self.passed_count or self.accepted != (self.failed_count == 0):
            raise ValidationError("observatory replay audit counters are not conserved")
        self.content_address = _address(content_address, "observatory replay audit address", AUDIT_PREFIX)
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("observatory replay audit address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("observatory replay audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"replay_address": self.replay_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryReplayAudit:
        value = _mapping(value, "observatory replay audit")
        _strict(value, set(cls.FIELDS), "observatory replay audit")
        return cls(value["replay_address"], tuple(RegistryFederationConsensusGateCertificateObservatoryReplayAuditFinding.from_mapping(item) for item in value["checks"]), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusGateCertificateObservatoryReplayAudit) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, observed: Any, expected: Any, detail: str) -> RegistryFederationConsensusGateCertificateObservatoryReplayAuditFinding:
    provisional = RegistryFederationConsensusGateCertificateObservatoryReplayAuditFinding(ordinal, check_id, passed, str(observed), str(expected), detail, FINDING_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryReplayAuditFinding(provisional.ordinal, provisional.check_id, provisional.passed, provisional.observed, provisional.expected, provisional.detail, address_finding(provisional))


def audit_replay(value: replay_model.RegistryFederationConsensusGateCertificateObservatoryReplay) -> RegistryFederationConsensusGateCertificateObservatoryReplayAudit:
    value = replay_model.verify_replay(value)
    checks = (
        _finding(1, "exact-fields", set(value.to_dict()) == set(replay_model.RegistryFederationConsensusGateCertificateObservatoryReplay.FIELDS), tuple(sorted(value.to_dict())), replay_model.RegistryFederationConsensusGateCertificateObservatoryReplay.FIELDS, "replay fields are exact"),
        _finding(2, "public-boundary", _public(value.to_dict()), True, True, "replay is public and path-free"),
        _finding(3, "package-address", value.package_address.startswith(replay_model.package_model.PACKAGE_PREFIX + ":"), value.package_address, replay_model.package_model.PACKAGE_PREFIX + ":address", "package address is typed"),
        _finding(4, "nested-addresses", all(isinstance(value.to_dict()[field], str) and value.to_dict()[field] for field in ("observatory_address", "query_address", "report_address", "observatory_audit_address", "query_audit_address", "report_audit_address")), "nested addresses", "six stage addresses", "nested addresses are present"),
        _finding(5, "member-count", value.member_count == len(value.members) == len(replay_model.FILES), (value.member_count, len(value.members)), len(replay_model.FILES), "member count is conserved"),
        _finding(6, "member-vocabulary", value.members == replay_model.FILES, value.members, replay_model.FILES, "member vocabulary is exact"),
        _finding(7, "byte-equality", value.byte_equal, value.byte_equal, True, "all package bytes replay"),
        _finding(8, "projection-equality", value.projection_equal, value.projection_equal, True, "all package projections replay"),
        _finding(9, "package-audit", value.audit_accepted, value.audit_accepted, True, "nested package audit is accepted"),
        _finding(10, "mapping-round-trip", replay_model.replay_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "mapping replay", "original replay", "mapping conversion is lossless"),
        _finding(11, "content-address", replay_model.address_replay(value) == value.content_address, value.content_address, replay_model.address_replay(value), "replay address replays"),
        _finding(12, "deterministic-members", value.members == tuple(replay_model.FILES), value.members, replay_model.FILES, "member order is deterministic"),
        _finding(13, "path-free", _public(value.to_dict()), True, True, "replay has no local paths or attribution metadata"),
    )
    provisional = RegistryFederationConsensusGateCertificateObservatoryReplayAudit(value.content_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryReplayAudit(provisional.replay_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryReplayAudit:
    return verify_audit(RegistryFederationConsensusGateCertificateObservatoryReplayAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusGateCertificateObservatoryReplayAudit) -> RegistryFederationConsensusGateCertificateObservatoryReplayAudit:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryReplayAudit) or (not value.content_address.endswith(":pending") and address_audit(value) != value.content_address):
        raise ValidationError("observatory replay audit is not valid")
    return value


def audit_json(value: RegistryFederationConsensusGateCertificateObservatoryReplayAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusGateCertificateObservatoryReplayAudit) -> str:
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateObservatoryReplayAuditFinding.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in verify_audit(value).checks:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusGateCertificateObservatoryReplayAudit) -> str:
    value = verify_audit(value)
    lines = ["# Certificate Observatory Replay Audit", "", f"- Accepted: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}`", f"- Address: `{value.content_address}`", "", "| check | passed | detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryReplayAuditFinding.FIELDS), "properties": {field: {"type": "integer"} if field == "ordinal" else {"type": "boolean"} if field == "passed" else {"type": "string"} for field in RegistryFederationConsensusGateCertificateObservatoryReplayAuditFinding.FIELDS}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryReplayAudit.FIELDS), "properties": {"replay_address": {"type": "string"}, "checks": {"type": "array", "items": check_schema()}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "finding_prefix": FINDING_PREFIX, "check_ids": CHECK_IDS, "features": ("independent exact-replay checks", "member and byte equality validation", "nested package-audit validation", "content-address replay", "JSON CSV and Markdown exports"), "schemas": ("check", "audit")}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "FINDING_PREFIX", "RegistryFederationConsensusGateCertificateObservatoryReplayAudit", "RegistryFederationConsensusGateCertificateObservatoryReplayAuditFinding", "VERSION", "address_audit", "address_finding", "audit_csv", "audit_from_mapping", "audit_json", "audit_replay", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
