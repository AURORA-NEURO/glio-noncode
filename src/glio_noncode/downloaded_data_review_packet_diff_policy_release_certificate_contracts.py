"""Typed contracts for source-free downloaded-data release certificates."""

# ruff: noqa: E501

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash

VERSION = "downloaded-data-review-packet-diff-policy-release-certificate-v1"
BOUNDARY = "public_downloaded_data_review_packet_diff_policy_release_certificate"
CERTIFICATE_PREFIX = "glio-noncode-download-review-packet-diff-policy-release-certificate"
RUN_PREFIX = "glio-noncode-download-review-packet-diff-policy-run"
PACKAGE_PREFIX = "glio-noncode-download-review-packet-diff-policy-package"
RUN_AUDIT_PREFIX = RUN_PREFIX + "-audit"
POLICY_PREFIX = "glio-noncode-download-review-packet-diff-policy"
POLICY_AUDIT_PREFIX = POLICY_PREFIX + "-audit"
PACKAGE_AUDIT_PREFIX = PACKAGE_PREFIX + "-audit"
PROFILES = ("strict", "release")
STATES = ("ready", "blocked")
CERTIFICATE_FIELDS = (
    "certificate_id", "version", "boundary", "run_id", "run_address", "package_address",
    "package_byte_count", "run_audit_address", "run_audit_accepted", "profile",
    "policy_address", "policy_state", "policy_accepted", "policy_audit_address",
    "policy_audit_accepted", "package_audit_address", "package_audit_accepted",
    "release_eligible", "release_state", "content_address",
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
    if not value.startswith(prefix + ":") or len(value.rsplit(":", 1)[-1]) != 64:
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int = 32 * 1024 * 1024) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its count bound")
    return value


@dataclass(frozen=True)
class DownloadedDataReviewPacketDiffPolicyReleaseCertificate:
    """A source-free, addressed release eligibility decision."""

    certificate_id: str
    version: str
    boundary: str
    run_id: str
    run_address: str
    package_address: str
    package_byte_count: int
    run_audit_address: str
    run_audit_accepted: bool
    profile: str
    policy_address: str
    policy_state: str
    policy_accepted: bool
    policy_audit_address: str
    policy_audit_accepted: bool
    package_audit_address: str
    package_audit_accepted: bool
    release_eligible: bool
    release_state: str
    content_address: str

    def __post_init__(self) -> None:
        _label(self.certificate_id, "release certificate ID")
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("release certificate identity is not current")
        _label(self.run_id, "release certificate run ID")
        _address(self.run_address, "release certificate run address", RUN_PREFIX)
        _address(self.package_address, "release certificate package address", PACKAGE_PREFIX)
        _count(self.package_byte_count, "release certificate package byte count")
        _address(self.run_audit_address, "release certificate run audit address", RUN_AUDIT_PREFIX)
        if not isinstance(self.run_audit_accepted, bool):
            raise ValidationError("release certificate run audit acceptance must be boolean")
        if self.profile not in PROFILES:
            raise ValidationError("release certificate profile is unsupported")
        _address(self.policy_address, "release certificate policy address", POLICY_PREFIX)
        if self.policy_state not in STATES or not isinstance(self.policy_accepted, bool):
            raise ValidationError("release certificate policy decision is invalid")
        _address(self.policy_audit_address, "release certificate policy audit address", POLICY_AUDIT_PREFIX)
        _address(self.package_audit_address, "release certificate package audit address", PACKAGE_AUDIT_PREFIX)
        for field in ("policy_audit_accepted", "package_audit_accepted", "release_eligible"):
            if not isinstance(getattr(self, field), bool):
                raise ValidationError(f"release certificate {field} must be boolean")
        if self.release_state not in STATES:
            raise ValidationError("release certificate release state is unsupported")
        self._validate_decision()
        _address(self.content_address, "release certificate address", CERTIFICATE_PREFIX)

    def _validate_decision(self) -> None:
        evidence_ready = self.run_audit_accepted and self.policy_accepted and self.policy_audit_accepted and self.package_audit_accepted and self.policy_state == "ready"
        if self.release_eligible != evidence_ready or self.release_state != ("ready" if evidence_ready else "blocked"):
            raise ValidationError("release certificate eligibility does not replay its evidence")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in CERTIFICATE_FIELDS}

    def summary(self) -> dict[str, Any]:
        return self.to_dict()

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "DownloadedDataReviewPacketDiffPolicyReleaseCertificate":
        if not isinstance(value, dict) or set(value) != set(CERTIFICATE_FIELDS):
            raise ValidationError("downloaded-data release certificate fields are not exact")
        return cls(*(value[field] for field in CERTIFICATE_FIELDS))


def address_certificate(value: DownloadedDataReviewPacketDiffPolicyReleaseCertificate) -> str:
    if not isinstance(value, DownloadedDataReviewPacketDiffPolicyReleaseCertificate):
        raise ValidationError("release certificate addressing requires its typed contract")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CERTIFICATE_PREFIX)


def certificate_schema() -> dict[str, Any]:
    integer_fields = {"package_byte_count"}
    boolean_fields = {"run_audit_accepted", "policy_accepted", "policy_audit_accepted", "package_audit_accepted", "release_eligible"}
    properties: dict[str, Any] = {}
    for field in CERTIFICATE_FIELDS:
        properties[field] = {"type": "integer"} if field in integer_fields else {"type": "boolean"} if field in boolean_fields else {"type": "string"}
    properties["version"] = {"const": VERSION}
    properties["boundary"] = {"const": BOUNDARY}
    properties["profile"] = {"enum": list(PROFILES)}
    properties["policy_state"] = {"enum": list(STATES)}
    properties["release_state"] = {"enum": list(STATES)}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data release certificate", "type": "object", "additionalProperties": False, "required": list(CERTIFICATE_FIELDS), "properties": properties}


def capabilities() -> dict[str, Any]:
    return {
        "version": VERSION,
        "boundary": BOUNDARY,
        "profiles": PROFILES,
        "states": STATES,
        "source_free": True,
        "requires_run_package_and_audit": True,
        "release_eligibility_is_conjunctive": True,
        "content_addressed": True,
        "bounded": True,
    }


__all__ = [
    "BOUNDARY", "CERTIFICATE_FIELDS", "CERTIFICATE_PREFIX", "PACKAGE_PREFIX", "PROFILES", "RUN_PREFIX", "STATES", "VERSION",
    "DownloadedDataReviewPacketDiffPolicyReleaseCertificate", "address_certificate", "capabilities", "certificate_schema",
]
