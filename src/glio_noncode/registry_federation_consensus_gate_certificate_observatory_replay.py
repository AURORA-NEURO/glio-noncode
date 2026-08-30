"""Byte and projection replay receipts for certificate-observatory packages."""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory_package as package_model
from . import registry_federation_consensus_gate_certificate_observatory_package_audit as package_audit_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = package_model.VERSION + "-replay-v1"
BOUNDARY = package_model.BOUNDARY + "_replay"
REPLAY_PREFIX = package_model.PACKAGE_PREFIX + "-replay"
MAX_TEXT = package_model.observatory_model.MAX_TEXT
FILES = package_model.FILES


def _text(value: Any, field: str, maximum: int = MAX_TEXT, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
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


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


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


class RegistryFederationConsensusGateCertificateObservatoryReplay:
    """Addressed receipt proving an exact on-disk observatory replay."""

    FIELDS = ("package_address", "observatory_address", "query_address", "report_address", "observatory_audit_address", "query_audit_address", "report_audit_address", "member_count", "members", "byte_equal", "projection_equal", "audit_accepted", "content_address")

    def __init__(self, package_address: str, observatory_address: str, query_address: str, report_address: str, observatory_audit_address: str, query_audit_address: str, report_audit_address: str, member_count: int, members: Sequence[str], byte_equal: bool, projection_equal: bool, audit_accepted: bool, content_address: str) -> None:
        self.package_address = _address(package_address, "observatory replay package address", package_model.PACKAGE_PREFIX)
        self.observatory_address = _address(observatory_address, "observatory replay observatory address", package_model.observatory_model.OBSERVATORY_PREFIX)
        self.query_address = _address(query_address, "observatory replay query address", package_model.observatory_model.RESULT_PREFIX)
        self.report_address = _address(report_address, "observatory replay report address", package_model.report_model.REPORT_PREFIX)
        self.observatory_audit_address = _address(observatory_audit_address, "observatory replay observatory audit address", package_model.observatory_audit_model.AUDIT_PREFIX)
        self.query_audit_address = _address(query_audit_address, "observatory replay query audit address", package_model.query_audit_model.AUDIT_PREFIX)
        self.report_audit_address = _address(report_audit_address, "observatory replay report audit address", package_model.report_audit_model.AUDIT_PREFIX)
        self.member_count = _count(member_count, "observatory replay member count", len(FILES), positive=True)
        self.members = tuple(_text(item, "observatory replay member", 128, required=True) for item in _sequence(members, "observatory replay members", len(FILES)))
        if self.members != FILES or self.member_count != len(self.members):
            raise ValidationError("observatory replay member vocabulary is not exact")
        self.byte_equal, self.projection_equal, self.audit_accepted = _bool(byte_equal, "observatory replay byte equality"), _bool(projection_equal, "observatory replay projection equality"), _bool(audit_accepted, "observatory replay audit acceptance")
        self.content_address = _address(content_address, "observatory replay address", REPLAY_PREFIX)
        if not self.content_address.endswith(":pending") and address_replay(self) != self.content_address:
            raise ValidationError("observatory replay address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("observatory replay crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return self.to_dict()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryReplay:
        value = _mapping(value, "observatory replay")
        _strict(value, set(cls.FIELDS), "observatory replay")
        return cls(*(value[field] for field in cls.FIELDS))


def address_replay(value: RegistryFederationConsensusGateCertificateObservatoryReplay) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryReplay):
        raise ValidationError("observatory replay address requires a typed replay")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=REPLAY_PREFIX)


def replay_package(directory: str | Path) -> RegistryFederationConsensusGateCertificateObservatoryReplay:
    """Load, audit, and compare every canonical package member."""

    destination = Path(directory)
    value = package_model.load_package(destination)
    expected = package_model.package_bytes(value)
    actual = {name: (destination / name).read_bytes() for name in FILES}
    package_audit = package_audit_model.audit_package(value)
    provisional = RegistryFederationConsensusGateCertificateObservatoryReplay(value.content_address, value.observatory.content_address, value.query.content_address, value.report.content_address, value.observatory_audit.content_address, value.query_audit.content_address, value.report_audit.content_address, len(actual), tuple(actual), expected == actual, package_model.load_package(destination).to_dict() == value.to_dict(), package_audit.accepted, REPLAY_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryReplay(provisional.package_address, provisional.observatory_address, provisional.query_address, provisional.report_address, provisional.observatory_audit_address, provisional.query_audit_address, provisional.report_audit_address, provisional.member_count, provisional.members, provisional.byte_equal, provisional.projection_equal, provisional.audit_accepted, address_replay(provisional))


def replay_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryReplay:
    return verify_replay(RegistryFederationConsensusGateCertificateObservatoryReplay.from_mapping(value))


def verify_replay(value: RegistryFederationConsensusGateCertificateObservatoryReplay) -> RegistryFederationConsensusGateCertificateObservatoryReplay:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryReplay) or (not value.content_address.endswith(":pending") and address_replay(value) != value.content_address):
        raise ValidationError("observatory replay is not valid")
    return value


def replay_json(value: RegistryFederationConsensusGateCertificateObservatoryReplay) -> str:
    return canonical_json(verify_replay(value).to_dict())


def replay_csv(value: RegistryFederationConsensusGateCertificateObservatoryReplay) -> str:
    value = verify_replay(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=("member_count", "members", "byte_equal", "projection_equal", "audit_accepted", "content_address"), lineterminator="\n")
    writer.writeheader()
    writer.writerow({"member_count": value.member_count, "members": "|".join(value.members), "byte_equal": value.byte_equal, "projection_equal": value.projection_equal, "audit_accepted": value.audit_accepted, "content_address": value.content_address})
    return stream.getvalue()


def render_replay_markdown(value: RegistryFederationConsensusGateCertificateObservatoryReplay) -> str:
    value = verify_replay(value)
    lines = ["# Certificate Observatory Replay", "", f"- Package: `{value.package_address}`", f"- Members: `{value.member_count}`", f"- Byte equal: `{value.byte_equal}`", f"- Projection equal: `{value.projection_equal}`", f"- Package audit accepted: `{value.audit_accepted}`", f"- Address: `{value.content_address}`", "", "| member |", "| --- |"]
    lines.extend(f"| `{member}` |" for member in value.members)
    return "\n".join(lines) + "\n"


def replay_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryReplay.FIELDS), "properties": {"package_address": {"type": "string"}, "observatory_address": {"type": "string"}, "query_address": {"type": "string"}, "report_address": {"type": "string"}, "observatory_audit_address": {"type": "string"}, "query_audit_address": {"type": "string"}, "report_audit_address": {"type": "string"}, "member_count": {"type": "integer"}, "members": {"type": "array", "items": {"type": "string"}}, "byte_equal": {"type": "boolean"}, "projection_equal": {"type": "boolean"}, "audit_accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + REPLAY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "replay_prefix": REPLAY_PREFIX, "members": FILES, "features": ("exact package member loading", "byte-level projection comparison", "nested audit acceptance", "content-addressed replay receipts", "JSON CSV and Markdown exports"), "schemas": ("replay",)}


__all__ = ["BOUNDARY", "FILES", "REPLAY_PREFIX", "RegistryFederationConsensusGateCertificateObservatoryReplay", "VERSION", "address_replay", "capabilities", "replay_csv", "replay_from_mapping", "replay_json", "replay_package", "replay_schema", "render_replay_markdown", "verify_replay"]
