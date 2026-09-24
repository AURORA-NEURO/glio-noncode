"""Typed contracts for source-free longitudinal release-bundle diffs."""

# ruff: noqa: E501

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash

VERSION = "downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-v1"
BOUNDARY = "public_downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff"
DIFF_PREFIX = "glio-noncode-download-review-packet-diff-policy-release-certificate-bundle-diff"
ITEM_PREFIX = DIFF_PREFIX + "-item"
BUNDLE_PREFIX = "glio-noncode-download-review-packet-diff-policy-release-certificate-bundle"
CHANGES = ("added", "removed", "changed", "unchanged")
DIRECTIONS = ("improved", "regressed", "changed", "unchanged")
STATE_TRANSITIONS = ("blocked-to-ready", "ready-to-blocked", "same-ready", "same-blocked")
RESOURCES = ("certificate", "run", "package", "audits", "members")
RESOURCE_FIELDS = {
    "certificate": ("profile", "policy_state", "policy_accepted", "release_state", "release_eligible"),
    "run": ("diff_item_count", "diff_changed_count", "policy_passed_count", "policy_failed_count", "package_byte_count"),
    "package": ("package_byte_count", "member_count", "package_address"),
    "audits": ("run_audit_accepted", "policy_audit_accepted", "package_audit_accepted", "certificate_audit_accepted"),
    "members": ("media_type", "byte_count", "byte_address", "content_address"),
}
ITEM_FIELDS = ("ordinal", "resource", "identity", "change", "changed_fields", "left_address", "right_address", "left_snapshot", "right_snapshot", "content_address")
DIFF_FIELDS = (
    "diff_id", "version", "boundary", "packet_id", "left_bundle_address", "right_bundle_address", "left_release_state", "right_release_state", "left_release_eligible", "right_release_eligible", "state_transition", "direction", "added_count", "removed_count", "changed_count", "unchanged_count", "items", "content_address",
)
MAX_ITEMS = 1024
MAX_LIMIT = 256


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 256)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > 4096 or (required and not value):
        raise ValidationError(f"{field} must be an address")
    if value and ("/" in value or "\\" in value or '"' in value or ":" not in value):
        raise ValidationError(f"{field} must be a content address")
    if prefix is not None and value and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int = MAX_ITEMS) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its count bound")
    return value


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError(f"{field} must be an object")
    return dict(value)


@dataclass(frozen=True)
class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffItem:
    """One value-free transition row between two release bundles."""

    ordinal: int
    resource: str
    identity: str
    change: str
    changed_fields: tuple[str, ...]
    left_address: str
    right_address: str
    left_snapshot: dict[str, Any]
    right_snapshot: dict[str, Any]
    content_address: str

    def __post_init__(self) -> None:
        _count(self.ordinal, "release bundle diff item ordinal")
        if self.ordinal < 1 or self.resource not in RESOURCES or self.change not in CHANGES:
            raise ValidationError("release bundle diff item identity is unsupported")
        _label(self.identity, "release bundle diff item identity")
        allowed = RESOURCE_FIELDS[self.resource]
        if tuple(self.changed_fields) != tuple(name for name in allowed if self.left_snapshot.get(name) != self.right_snapshot.get(name)):
            raise ValidationError("release bundle diff changed fields do not replay")
        if any(field not in allowed for field in self.changed_fields) or len(set(self.changed_fields)) != len(self.changed_fields):
            raise ValidationError("release bundle diff changed fields are unsupported or duplicated")
        _address(self.left_address, "release bundle diff left address", required=self.change != "added")
        _address(self.right_address, "release bundle diff right address", required=self.change != "removed")
        _mapping(self.left_snapshot, "release bundle diff left snapshot")
        _mapping(self.right_snapshot, "release bundle diff right snapshot")
        if self.change == "added" and (self.left_snapshot or self.left_address or not self.right_snapshot):
            raise ValidationError("added release bundle diff item has an invalid left side")
        if self.change == "removed" and (self.right_snapshot or self.right_address or not self.left_snapshot):
            raise ValidationError("removed release bundle diff item has an invalid right side")
        if self.change == "unchanged" and self.changed_fields:
            raise ValidationError("unchanged release bundle diff item has changed fields")
        if self.change == "changed" and not self.changed_fields:
            raise ValidationError("changed release bundle diff item has no changed fields")
        if self.content_address.endswith(":pending"):
            return
        _address(self.content_address, "release bundle diff item address", ITEM_PREFIX)
        if address_item(self) != self.content_address:
            raise ValidationError("release bundle diff item address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in ITEM_FIELDS}

    def summary(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in ITEM_FIELDS if field not in {"left_snapshot", "right_snapshot"}}

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffItem":
        if not isinstance(value, dict) or set(value) != set(ITEM_FIELDS):
            raise ValidationError("release bundle diff item fields are not exact")
        return cls(value["ordinal"], value["resource"], value["identity"], value["change"], tuple(value["changed_fields"]), value["left_address"], value["right_address"], value["left_snapshot"], value["right_snapshot"], value["content_address"])


def address_item(value: DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffItem) -> str:
    if not isinstance(value, DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffItem):
        raise ValidationError("release bundle diff item addressing requires its typed contract")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ITEM_PREFIX)


@dataclass(frozen=True)
class DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiff:
    """Complete deterministic transition between two source-free bundles."""

    diff_id: str
    version: str
    boundary: str
    packet_id: str
    left_bundle_address: str
    right_bundle_address: str
    left_release_state: str
    right_release_state: str
    left_release_eligible: bool
    right_release_eligible: bool
    state_transition: str
    direction: str
    added_count: int
    removed_count: int
    changed_count: int
    unchanged_count: int
    items: tuple[DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffItem, ...]
    content_address: str

    def __post_init__(self) -> None:
        _label(self.diff_id, "release bundle diff ID")
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("release bundle diff identity is not current")
        _label(self.packet_id, "release bundle diff packet ID")
        _address(self.left_bundle_address, "release bundle diff left bundle address", BUNDLE_PREFIX)
        _address(self.right_bundle_address, "release bundle diff right bundle address", BUNDLE_PREFIX)
        for state in (self.left_release_state, self.right_release_state):
            if state not in {"ready", "blocked"}:
                raise ValidationError("release bundle diff release state is unsupported")
        if not isinstance(self.left_release_eligible, bool) or not isinstance(self.right_release_eligible, bool) or self.left_release_eligible != (self.left_release_state == "ready") or self.right_release_eligible != (self.right_release_state == "ready"):
            raise ValidationError("release bundle diff release eligibility does not replay")
        if self.state_transition not in STATE_TRANSITIONS or self.direction not in DIRECTIONS:
            raise ValidationError("release bundle diff transition is unsupported")
        self._validate_items()
        if self.content_address.endswith(":pending"):
            return
        _address(self.content_address, "release bundle diff address", DIFF_PREFIX)
        if address_diff(self) != self.content_address:
            raise ValidationError("release bundle diff address does not replay")

    def _validate_items(self) -> None:
        if not self.items or len(self.items) > MAX_ITEMS or tuple(item.ordinal for item in self.items) != tuple(range(1, len(self.items) + 1)) or len({(item.resource, item.identity) for item in self.items}) != len(self.items):
            raise ValidationError("release bundle diff item order or identity does not replay")
        counts = {change: sum(item.change == change for item in self.items) for change in CHANGES}
        if (self.added_count, self.removed_count, self.changed_count, self.unchanged_count) != tuple(counts[change] for change in CHANGES):
            raise ValidationError("release bundle diff counts do not replay")
        active = self.changed_count + self.added_count + self.removed_count > 0
        expected_direction = "unchanged" if not active else "improved" if not self.left_release_eligible and self.right_release_eligible else "regressed" if self.left_release_eligible and not self.right_release_eligible else "changed"
        expected_transition = "blocked-to-ready" if self.left_release_state == "blocked" and self.right_release_state == "ready" else "ready-to-blocked" if self.left_release_state == "ready" and self.right_release_state == "blocked" else "same-ready" if self.left_release_state == "ready" else "same-blocked"
        if self.direction != expected_direction or self.state_transition != expected_transition:
            raise ValidationError("release bundle diff direction or state transition does not replay")
        if self.left_bundle_address == self.right_bundle_address and active:
            raise ValidationError("identical release bundles cannot contain changes")

    def to_dict(self) -> dict[str, Any]:
        return {field: tuple(item.to_dict() for item in self.items) if field == "items" else getattr(self, field) for field in DIFF_FIELDS}

    def summary(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in DIFF_FIELDS if field != "items"}

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiff":
        if not isinstance(value, dict) or set(value) != set(DIFF_FIELDS):
            raise ValidationError("release bundle diff fields are not exact")
        return cls(value["diff_id"], value["version"], value["boundary"], value["packet_id"], value["left_bundle_address"], value["right_bundle_address"], value["left_release_state"], value["right_release_state"], value["left_release_eligible"], value["right_release_eligible"], value["state_transition"], value["direction"], value["added_count"], value["removed_count"], value["changed_count"], value["unchanged_count"], tuple(DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffItem.from_mapping(item) for item in value["items"]), value["content_address"])


def address_diff(value: DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiff) -> str:
    if not isinstance(value, DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiff):
        raise ValidationError("release bundle diff addressing requires its typed contract")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


def diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data release certificate bundle diff", "type": "object", "additionalProperties": False, "required": list(DIFF_FIELDS), "properties": {field: {"type": "array" if field == "items" else "boolean" if field in {"left_release_eligible", "right_release_eligible"} else "integer" if field.endswith("_count") else "string"} for field in DIFF_FIELDS}}


def item_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data release certificate bundle diff item", "type": "object", "additionalProperties": False, "required": list(ITEM_FIELDS), "properties": {field: {"type": "array" if field == "changed_fields" else "object" if field in {"left_snapshot", "right_snapshot"} else "integer" if field == "ordinal" else "string"} for field in ITEM_FIELDS}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "resources": RESOURCES, "changes": CHANGES, "directions": DIRECTIONS, "state_transitions": STATE_TRANSITIONS, "source_free": True, "content_addressed": True, "bounded": True}


__all__ = ["BOUNDARY", "CHANGES", "DIFF_FIELDS", "DIFF_PREFIX", "DIRECTIONS", "ITEM_FIELDS", "ITEM_PREFIX", "MAX_ITEMS", "MAX_LIMIT", "RESOURCES", "STATE_TRANSITIONS", "VERSION", "DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiff", "DownloadedDataReviewPacketDiffPolicyReleaseCertificateBundleDiffItem", "address_diff", "address_item", "capabilities", "diff_schema", "item_schema"]
