"""Typed contracts for end-to-end downloaded-data review runs."""

# ruff: noqa: E501

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash

VERSION = "downloaded-data-review-packet-diff-policy-run-v1"
BOUNDARY = "public_downloaded_data_review_packet_diff_policy_run"
RUN_PREFIX = "glio-noncode-download-review-packet-diff-policy-run"
PACKET_PREFIX = "glio-noncode-download-review-packet"
DIFF_PREFIX = "glio-noncode-download-review-packet-diff"
POLICY_PREFIX = "glio-noncode-download-review-packet-diff-policy"
POLICY_AUDIT_PREFIX = POLICY_PREFIX + "-audit"
PACKAGE_PREFIX = POLICY_PREFIX + "-package"
PACKAGE_AUDIT_PREFIX = PACKAGE_PREFIX + "-audit"
PROFILES = ("strict", "release")
STATES = ("ready", "blocked")
RUN_FIELDS = (
    "run_id", "version", "boundary", "profile", "packet_id", "left_packet_address", "right_packet_address",
    "left_packet_byte_count", "right_packet_byte_count", "diff_address", "diff_item_count", "diff_changed_count",
    "policy_address", "policy_check_count", "policy_passed_count", "policy_failed_count", "policy_accepted",
    "policy_state", "policy_audit_address", "policy_audit_accepted", "package_address", "package_byte_count",
    "package_audit_address", "package_audit_check_count", "package_audit_passed_count", "package_audit_accepted", "content_address",
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


def _count(value: Any, field: str, maximum: int = 8192) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its count bound")
    return value


@dataclass(frozen=True)
class DownloadedDataReviewPacketDiffPolicyRun:
    """One addressed receipt for a complete source-to-decision run."""

    run_id: str
    version: str
    boundary: str
    profile: str
    packet_id: str
    left_packet_address: str
    right_packet_address: str
    left_packet_byte_count: int
    right_packet_byte_count: int
    diff_address: str
    diff_item_count: int
    diff_changed_count: int
    policy_address: str
    policy_check_count: int
    policy_passed_count: int
    policy_failed_count: int
    policy_accepted: bool
    policy_state: str
    policy_audit_address: str
    policy_audit_accepted: bool
    package_address: str
    package_byte_count: int
    package_audit_address: str
    package_audit_check_count: int
    package_audit_passed_count: int
    package_audit_accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _label(self.run_id, "review run ID")
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("review run identity is not current")
        if self.profile not in PROFILES:
            raise ValidationError("review run profile is unsupported")
        _label(self.packet_id, "review run packet ID")
        _address(self.left_packet_address, "review run left packet address", PACKET_PREFIX)
        _address(self.right_packet_address, "review run right packet address", PACKET_PREFIX)
        _count(self.left_packet_byte_count, "review run left packet byte count", 32 * 1024 * 1024)
        _count(self.right_packet_byte_count, "review run right packet byte count", 32 * 1024 * 1024)
        _address(self.diff_address, "review run diff address", DIFF_PREFIX)
        _count(self.diff_item_count, "review run diff item count")
        _count(self.diff_changed_count, "review run diff changed count")
        _address(self.policy_address, "review run policy address", POLICY_PREFIX)
        _count(self.policy_check_count, "review run policy check count", 32)
        _count(self.policy_passed_count, "review run policy passed count", 32)
        _count(self.policy_failed_count, "review run policy failed count", 32)
        if not isinstance(self.policy_accepted, bool) or self.policy_state not in STATES:
            raise ValidationError("review run policy decision is invalid")
        _address(self.policy_audit_address, "review run policy audit address", POLICY_AUDIT_PREFIX)
        if not isinstance(self.policy_audit_accepted, bool):
            raise ValidationError("review run policy audit acceptance must be boolean")
        _address(self.package_address, "review run package address", PACKAGE_PREFIX)
        _count(self.package_byte_count, "review run package byte count", 32 * 1024 * 1024)
        _address(self.package_audit_address, "review run package audit address", PACKAGE_AUDIT_PREFIX)
        _count(self.package_audit_check_count, "review run package audit check count", 32)
        _count(self.package_audit_passed_count, "review run package audit passed count", 32)
        if not isinstance(self.package_audit_accepted, bool):
            raise ValidationError("review run package audit acceptance must be boolean")
        _address(self.content_address, "review run address", RUN_PREFIX)
        self._validate_aggregates()

    def _validate_aggregates(self) -> None:
        if self.diff_changed_count > self.diff_item_count:
            raise ValidationError("review run diff counts do not conserve items")
        if self.policy_passed_count + self.policy_failed_count != self.policy_check_count:
            raise ValidationError("review run policy counts do not conserve checks")
        if self.policy_accepted != (self.policy_failed_count == 0) or self.policy_state != ("ready" if self.policy_accepted else "blocked"):
            raise ValidationError("review run policy state does not replay acceptance")
        if self.package_audit_passed_count > self.package_audit_check_count:
            raise ValidationError("review run package audit counts do not conserve checks")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in RUN_FIELDS}

    def summary(self) -> dict[str, Any]:
        return self.to_dict()

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> DownloadedDataReviewPacketDiffPolicyRun:
        if not isinstance(value, dict) or set(value) != set(RUN_FIELDS):
            raise ValidationError("downloaded-data review run fields are not exact")
        return cls(*(value[field] for field in RUN_FIELDS))


def address_run(value: DownloadedDataReviewPacketDiffPolicyRun) -> str:
    if not isinstance(value, DownloadedDataReviewPacketDiffPolicyRun):
        raise ValidationError("review run addressing requires its typed contract")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RUN_PREFIX)


def run_schema() -> dict[str, Any]:
    integer_fields = {"left_packet_byte_count", "right_packet_byte_count", "diff_item_count", "diff_changed_count", "policy_check_count", "policy_passed_count", "policy_failed_count", "package_byte_count", "package_audit_check_count", "package_audit_passed_count"}
    boolean_fields = {"policy_accepted", "policy_audit_accepted", "package_audit_accepted"}
    properties: dict[str, Any] = {}
    for field in RUN_FIELDS:
        properties[field] = {"type": "integer"} if field in integer_fields else {"type": "boolean"} if field in boolean_fields else {"type": "string"}
    properties["version"] = {"const": VERSION}
    properties["boundary"] = {"const": BOUNDARY}
    properties["profile"] = {"enum": list(PROFILES)}
    properties["policy_state"] = {"enum": list(STATES)}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data review packet diff policy run", "type": "object", "additionalProperties": False, "required": list(RUN_FIELDS), "properties": properties}


def capabilities() -> dict[str, Any]:
    return {
        "version": VERSION,
        "boundary": BOUNDARY,
        "profiles": PROFILES,
        "states": STATES,
        "source_free_receipt": True,
        "builds_packets_diff_policy_and_package": True,
        "independent_package_audit": True,
        "content_addressed": True,
        "bounded": True,
    }


__all__ = ["BOUNDARY", "PACKAGE_PREFIX", "PROFILES", "RUN_FIELDS", "RUN_PREFIX", "STATES", "VERSION", "DownloadedDataReviewPacketDiffPolicyRun", "address_run", "capabilities", "run_schema"]
