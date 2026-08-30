"""Deterministic transition diffs for consensus gate certificates."""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate_certificate as certificate_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = certificate_model.VERSION + "-diff-v1"
BOUNDARY = certificate_model.BOUNDARY + "_diff"
DIFF_PREFIX = certificate_model.CERTIFICATE_PREFIX + "-diff"
ITEM_PREFIX = DIFF_PREFIX + "-item"
MAX_TEXT = certificate_model.MAX_TEXT
MAX_ITEMS = 64
DIFF_ACTIONS = ("unchanged", "changed")
DIFF_DIRECTIONS = ("unchanged", "improved", "regressed", "mixed")
DEFAULT_DIFF_ID = "consensus-certificate-diff"
FIELDS = (
    "certificate_id",
    "runtime_id",
    "runtime_address",
    "package_address",
    "gate_id",
    "gate_address",
    "audit_address",
    "query_address",
    "policy",
    "gate_state",
    "gate_decision",
    "certificate_state",
    "certificate_decision",
    "check_count",
    "passed_count",
    "failed_count",
    "blocking_check_ids",
    "evidence_addresses",
    "accepted",
)


def _text(value: Any, field: str, maximum: int = MAX_TEXT, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192, required=True)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 512, required=True)
    if "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
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


class RegistryFederationConsensusGateCertificateDiffItem:
    """One field-level certificate transition."""

    FIELDS = ("ordinal", "field", "action", "left_value", "right_value", "changed", "detail", "content_address")

    def __init__(self, ordinal: int, field: str, action: str, left_value: str, right_value: str, changed: bool, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "certificate diff item ordinal", MAX_ITEMS, positive=True)
        self.field = _label(field, "certificate diff field")
        if self.field not in FIELDS:
            raise ValidationError("certificate diff field is unsupported")
        if action not in DIFF_ACTIONS:
            raise ValidationError("certificate diff action is unsupported")
        self.action = action
        self.left_value = _text(left_value, "certificate diff left value", 4096)
        self.right_value = _text(right_value, "certificate diff right value", 4096)
        self.changed = _bool(changed, "certificate diff changed flag")
        if self.changed != (self.left_value != self.right_value) or self.action != ("changed" if self.changed else "unchanged"):
            raise ValidationError("certificate diff action is not conserved")
        self.detail = _text(detail, "certificate diff detail", required=True)
        self.content_address = _address(content_address, "certificate diff item address", ITEM_PREFIX)
        if not self.content_address.endswith(":pending") and address_item(self) != self.content_address:
            raise ValidationError("certificate diff item address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate diff item crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateDiffItem:
        value = _mapping(value, "certificate diff item")
        _strict(value, set(cls.FIELDS), "certificate diff item")
        return cls(*(value[field] for field in cls.FIELDS))


def address_item(value: RegistryFederationConsensusGateCertificateDiffItem) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateDiffItem):
        raise ValidationError("certificate diff item address requires a typed item")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ITEM_PREFIX)


class RegistryFederationConsensusGateCertificateDiff:
    """Addressed field comparison with acceptance-aware direction."""

    FIELDS = ("diff_id", "left_address", "right_address", "direction", "items", "item_count", "changed_count", "unchanged_count", "left_accepted", "right_accepted", "content_address")

    def __init__(self, diff_id: str, left_address: str, right_address: str, direction: str, items: Sequence[RegistryFederationConsensusGateCertificateDiffItem], item_count: int, changed_count: int, unchanged_count: int, left_accepted: bool, right_accepted: bool, content_address: str) -> None:
        self.diff_id = _label(diff_id, "certificate diff ID")
        self.left_address = _address(left_address, "certificate diff left address", certificate_model.CERTIFICATE_PREFIX)
        self.right_address = _address(right_address, "certificate diff right address", certificate_model.CERTIFICATE_PREFIX)
        if direction not in DIFF_DIRECTIONS:
            raise ValidationError("certificate diff direction is unsupported")
        self.direction = direction
        self.items = tuple(items)
        if any(not isinstance(item, RegistryFederationConsensusGateCertificateDiffItem) for item in self.items) or len(self.items) > MAX_ITEMS:
            raise ValidationError("certificate diff items are outside the bound")
        self.item_count = _count(item_count, "certificate diff item count", MAX_ITEMS, positive=True)
        self.changed_count = _count(changed_count, "certificate diff changed count", self.item_count)
        self.unchanged_count = _count(unchanged_count, "certificate diff unchanged count", self.item_count)
        self.left_accepted = _bool(left_accepted, "certificate diff left acceptance")
        self.right_accepted = _bool(right_accepted, "certificate diff right acceptance")
        if len(self.items) != self.item_count or tuple(item.ordinal for item in self.items) != tuple(range(1, self.item_count + 1)) or self.changed_count + self.unchanged_count != self.item_count or self.changed_count != sum(item.changed for item in self.items) or self.unchanged_count != sum(not item.changed for item in self.items):
            raise ValidationError("certificate diff counters are not conserved")
        if self.left_address == self.right_address and self.direction != "unchanged":
            raise ValidationError("identical certificates require unchanged direction")
        self.content_address = _address(content_address, "certificate diff address", DIFF_PREFIX)
        if not self.content_address.endswith(":pending") and address_diff(self) != self.content_address:
            raise ValidationError("certificate diff address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate diff crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "left_address": self.left_address, "right_address": self.right_address, "direction": self.direction, "items": tuple(item.to_dict() for item in self.items), "item_count": self.item_count, "changed_count": self.changed_count, "unchanged_count": self.unchanged_count, "left_accepted": self.left_accepted, "right_accepted": self.right_accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "items"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateDiff:
        value = _mapping(value, "consensus gate certificate diff")
        _strict(value, set(cls.FIELDS), "consensus gate certificate diff")
        return cls(value["diff_id"], value["left_address"], value["right_address"], value["direction"], tuple(RegistryFederationConsensusGateCertificateDiffItem.from_mapping(item) for item in value["items"]), value["item_count"], value["changed_count"], value["unchanged_count"], value["left_accepted"], value["right_accepted"], value["content_address"])


def address_diff(value: RegistryFederationConsensusGateCertificateDiff) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateDiff):
        raise ValidationError("certificate diff address requires a typed diff")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


def _encoded(value: Any) -> str:
    return canonical_json(value)


def _direction(left: certificate_model.RegistryFederationConsensusGateCertificate, right: certificate_model.RegistryFederationConsensusGateCertificate, changed: int) -> str:
    if not changed:
        return "unchanged"
    if not left.accepted and right.accepted:
        return "improved"
    if left.accepted and not right.accepted:
        return "regressed"
    return "mixed"


def build_diff(left: certificate_model.RegistryFederationConsensusGateCertificate, right: certificate_model.RegistryFederationConsensusGateCertificate, *, diff_id: str = DEFAULT_DIFF_ID) -> RegistryFederationConsensusGateCertificateDiff:
    """Compare two certificates without exposing source paths or raw records."""

    left = certificate_model.verify_certificate(left)
    right = certificate_model.verify_certificate(right)
    items: list[RegistryFederationConsensusGateCertificateDiffItem] = []
    left_map = left.to_dict()
    right_map = right.to_dict()
    for ordinal, field in enumerate(FIELDS, start=1):
        left_value = _encoded(left_map[field])
        right_value = _encoded(right_map[field])
        changed = left_value != right_value
        provisional = RegistryFederationConsensusGateCertificateDiffItem(ordinal, field, "changed" if changed else "unchanged", left_value, right_value, changed, f"certificate field {field} {'changed' if changed else 'is unchanged'}", ITEM_PREFIX + ":pending")
        items.append(RegistryFederationConsensusGateCertificateDiffItem(provisional.ordinal, provisional.field, provisional.action, provisional.left_value, provisional.right_value, provisional.changed, provisional.detail, address_item(provisional)))
    direction = _direction(left, right, sum(item.changed for item in items))
    provisional_diff = RegistryFederationConsensusGateCertificateDiff(diff_id, left.content_address, right.content_address, direction, items, len(items), sum(item.changed for item in items), sum(not item.changed for item in items), left.accepted, right.accepted, DIFF_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateDiff(provisional_diff.diff_id, provisional_diff.left_address, provisional_diff.right_address, provisional_diff.direction, provisional_diff.items, provisional_diff.item_count, provisional_diff.changed_count, provisional_diff.unchanged_count, provisional_diff.left_accepted, provisional_diff.right_accepted, address_diff(provisional_diff))


def diff_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateDiff:
    return verify_diff(RegistryFederationConsensusGateCertificateDiff.from_mapping(value))


def verify_diff(value: RegistryFederationConsensusGateCertificateDiff) -> RegistryFederationConsensusGateCertificateDiff:
    if not isinstance(value, RegistryFederationConsensusGateCertificateDiff) or (not value.content_address.endswith(":pending") and address_diff(value) != value.content_address):
        raise ValidationError("certificate diff is not valid")
    return value


def diff_json(value: RegistryFederationConsensusGateCertificateDiff) -> str:
    return canonical_json(verify_diff(value).to_dict())


def diff_csv(value: RegistryFederationConsensusGateCertificateDiff) -> str:
    value = verify_diff(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateCertificateDiffItem.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.items:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_diff_markdown(value: RegistryFederationConsensusGateCertificateDiff) -> str:
    value = verify_diff(value)
    lines = ["# Consensus Release Certificate Diff", "", f"- Direction: `{value.direction}`", f"- Changed: `{value.changed_count}/{value.item_count}`", f"- Left: `{value.left_address}`", f"- Right: `{value.right_address}`", f"- Address: `{value.content_address}`", "", "| field | action | left | right |", "| --- | --- | --- | --- |"]
    lines.extend(f"| `{item.field}` | `{item.action}` | `{item.left_value}` | `{item.right_value}` |" for item in value.items)
    return "\n".join(lines) + "\n"


def item_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateDiffItem.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "field": {"type": "string"}, "action": {"type": "string", "enum": list(DIFF_ACTIONS)}, "left_value": {"type": "string"}, "right_value": {"type": "string"}, "changed": {"type": "boolean"}, "detail": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + ITEM_PREFIX + ":"}}}


def diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateDiff.FIELDS), "properties": {"diff_id": {"type": "string"}, "left_address": {"type": "string"}, "right_address": {"type": "string"}, "direction": {"type": "string", "enum": list(DIFF_DIRECTIONS)}, "items": {"type": "array", "items": item_schema()}, "item_count": {"type": "integer"}, "changed_count": {"type": "integer"}, "unchanged_count": {"type": "integer"}, "left_accepted": {"type": "boolean"}, "right_accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + DIFF_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "diff_prefix": DIFF_PREFIX, "item_prefix": ITEM_PREFIX, "fields": FIELDS, "directions": DIFF_DIRECTIONS, "actions": DIFF_ACTIONS, "features": ("field-level certificate transitions", "acceptance-aware direction", "changed and unchanged counters", "content-addressed diff items", "JSON CSV and Markdown exports"), "schemas": ("item", "diff")}


__all__ = ["BOUNDARY", "DEFAULT_DIFF_ID", "DIFF_ACTIONS", "DIFF_DIRECTIONS", "DIFF_PREFIX", "FIELDS", "ITEM_PREFIX", "RegistryFederationConsensusGateCertificateDiff", "RegistryFederationConsensusGateCertificateDiffItem", "VERSION", "address_diff", "address_item", "build_diff", "capabilities", "diff_csv", "diff_from_mapping", "diff_json", "diff_schema", "item_schema", "render_diff_markdown", "verify_diff"]
