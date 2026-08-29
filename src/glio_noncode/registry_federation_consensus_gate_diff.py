"""Deterministic transition diffs for consensus release-gate receipts."""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus_gate as gate_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = gate_model.VERSION + "-diff-v1"
BOUNDARY = gate_model.BOUNDARY + "_diff"
DIFF_PREFIX = gate_model.GATE_PREFIX + "-diff"
ITEM_PREFIX = gate_model.GATE_PREFIX + "-diff-item"
MAX_TEXT = gate_model.MAX_TEXT
MAX_ITEMS = gate_model.MAX_CHECKS + 8
CHANGES = ("added", "removed", "changed")
RESOURCES = ("policy", "checks", "disposition", "receipt")
DEFAULT_DIFF_ID = "consensus-gate-diff"


def _text(value: Any, field: str, maximum: int = MAX_TEXT, *, required: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 192, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, optional: bool = False) -> str:
    if optional and value == "":
        return ""
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
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _labels(value: Any, field: str, maximum: int) -> tuple[str, ...]:
    labels = tuple(_label(item, field) for item in _sequence(value, field, maximum))
    if len(set(labels)) != len(labels):
        raise ValidationError(f"{field} must be unique")
    return tuple(sorted(labels))


def _addresses(value: Any, field: str, maximum: int) -> tuple[str, ...]:
    addresses = tuple(_address(item, field) for item in _sequence(value, field, maximum))
    if len(set(addresses)) != len(addresses):
        raise ValidationError(f"{field} must be unique")
    return tuple(sorted(addresses))


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        return "agent" not in value.lower() and "/" not in value and "\\" not in value and '"' not in value
    return value is None or isinstance(value, (bool, int, float))


def _hash_value(value: Any) -> str:
    return content_hash({"value": value}, prefix=ITEM_PREFIX + "-value")


def _without_address(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "content_address"}


class RegistryFederationConsensusGateDiffItem:
    FIELDS = ("ordinal", "resource", "item_id", "change", "left_value", "right_value", "changed_fields", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, resource: str, item_id: str, change: str, left_value: str, right_value: str, changed_fields: Sequence[str], evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "gate diff item ordinal", MAX_ITEMS, positive=True)
        self.resource = _label(resource, "gate diff item resource")
        if self.resource not in RESOURCES:
            raise ValidationError("gate diff item resource is unsupported")
        self.item_id = _label(item_id, "gate diff item ID")
        if change not in CHANGES:
            raise ValidationError("gate diff change is unsupported")
        self.change = change
        self.left_value = _address(left_value, "gate diff left value", ITEM_PREFIX + "-value", optional=True)
        self.right_value = _address(right_value, "gate diff right value", ITEM_PREFIX + "-value", optional=True)
        if change == "added" and (self.left_value or not self.right_value):
            raise ValidationError("added diff item values are not conserved")
        if change == "removed" and (not self.left_value or self.right_value):
            raise ValidationError("removed diff item values are not conserved")
        if change == "changed" and (not self.left_value or not self.right_value or self.left_value == self.right_value):
            raise ValidationError("changed diff item values are not conserved")
        self.changed_fields = _labels(changed_fields, "gate diff changed fields", 32)
        self.evidence_addresses = _addresses(evidence_addresses, "gate diff evidence addresses", 16)
        if not self.evidence_addresses:
            raise ValidationError("gate diff items require evidence")
        self.content_address = _address(content_address, "gate diff item content address", ITEM_PREFIX)
        if not self.content_address.endswith(":pending") and address_item(self) != self.content_address:
            raise ValidationError("gate diff item content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("gate diff item crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateDiffItem:
        value = _mapping(value, "gate diff item")
        _strict(value, set(cls.FIELDS), "gate diff item")
        return cls(*(value[field] for field in cls.FIELDS))


def address_item(value: RegistryFederationConsensusGateDiffItem) -> str:
    if not isinstance(value, RegistryFederationConsensusGateDiffItem):
        raise ValidationError("gate diff item address requires a typed item")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ITEM_PREFIX)


class RegistryFederationConsensusGateDiff:
    FIELDS = ("diff_id", "left", "right", "items", "item_count", "added_count", "removed_count", "changed_count", "left_state", "right_state", "left_decision", "right_decision", "left_accepted", "right_accepted", "content_address")

    def __init__(self, diff_id: str, left: gate_model.RegistryFederationConsensusGate, right: gate_model.RegistryFederationConsensusGate, items: Sequence[RegistryFederationConsensusGateDiffItem], item_count: int, added_count: int, removed_count: int, changed_count: int, left_state: str, right_state: str, left_decision: str, right_decision: str, left_accepted: bool, right_accepted: bool, content_address: str) -> None:
        self.diff_id = _label(diff_id, "gate diff ID")
        if not isinstance(left, gate_model.RegistryFederationConsensusGate) or not isinstance(right, gate_model.RegistryFederationConsensusGate):
            raise ValidationError("gate diff members must be typed")
        self.left = gate_model.verify_gate(left)
        self.right = gate_model.verify_gate(right)
        self.items = tuple(items)
        if any(not isinstance(item, RegistryFederationConsensusGateDiffItem) for item in self.items) or len(self.items) > MAX_ITEMS:
            raise ValidationError("gate diff items are outside the bound")
        self.item_count = _count(item_count, "gate diff item count", MAX_ITEMS)
        self.added_count = _count(added_count, "gate diff added count", self.item_count)
        self.removed_count = _count(removed_count, "gate diff removed count", self.item_count)
        self.changed_count = _count(changed_count, "gate diff changed count", self.item_count)
        if len(self.items) != self.item_count or tuple(item.ordinal for item in self.items) != tuple(range(1, self.item_count + 1)) or self.added_count != sum(item.change == "added" for item in self.items) or self.removed_count != sum(item.change == "removed" for item in self.items) or self.changed_count != sum(item.change == "changed" for item in self.items):
            raise ValidationError("gate diff counters are not conserved")
        if left_state not in gate_model.GATE_STATES or right_state not in gate_model.GATE_STATES or left_decision not in gate_model.GATE_DECISIONS or right_decision not in gate_model.GATE_DECISIONS:
            raise ValidationError("gate diff dispositions are unsupported")
        self.left_state, self.right_state = left_state, right_state
        self.left_decision, self.right_decision = left_decision, right_decision
        self.left_accepted, self.right_accepted = _bool(left_accepted, "gate diff left acceptance"), _bool(right_accepted, "gate diff right acceptance")
        if (self.left_state, self.left_decision, self.left_accepted) != (self.left.state, self.left.decision, self.left.accepted) or (self.right_state, self.right_decision, self.right_accepted) != (self.right.state, self.right.decision, self.right.accepted):
            raise ValidationError("gate diff receipt dispositions do not replay")
        self.content_address = _address(content_address, "gate diff content address", DIFF_PREFIX)
        if not self.content_address.endswith(":pending") and address_diff(self) != self.content_address:
            raise ValidationError("gate diff content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("gate diff crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "left": self.left.to_dict(), "right": self.right.to_dict(), "items": tuple(item.to_dict() for item in self.items), "item_count": self.item_count, "added_count": self.added_count, "removed_count": self.removed_count, "changed_count": self.changed_count, "left_state": self.left_state, "right_state": self.right_state, "left_decision": self.left_decision, "right_decision": self.right_decision, "left_accepted": self.left_accepted, "right_accepted": self.right_accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key not in {"left", "right", "items"}}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateDiff:
        value = _mapping(value, "consensus gate diff")
        _strict(value, set(cls.FIELDS), "consensus gate diff")
        return cls(value["diff_id"], gate_model.gate_from_mapping(value["left"]), gate_model.gate_from_mapping(value["right"]), tuple(RegistryFederationConsensusGateDiffItem.from_mapping(item) for item in value["items"]), value["item_count"], value["added_count"], value["removed_count"], value["changed_count"], value["left_state"], value["right_state"], value["left_decision"], value["right_decision"], value["left_accepted"], value["right_accepted"], value["content_address"])


def address_diff(value: RegistryFederationConsensusGateDiff) -> str:
    if not isinstance(value, RegistryFederationConsensusGateDiff):
        raise ValidationError("gate diff address requires a typed diff")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


def _item(ordinal: int, resource: str, item_id: str, change: str, left: Any, right: Any, changed_fields: Sequence[str], evidence: Sequence[str]) -> RegistryFederationConsensusGateDiffItem:
    left_value = "" if left is None else _hash_value(left)
    right_value = "" if right is None else _hash_value(right)
    provisional = RegistryFederationConsensusGateDiffItem(ordinal, resource, item_id, change, left_value, right_value, changed_fields, evidence, ITEM_PREFIX + ":pending")
    return RegistryFederationConsensusGateDiffItem(provisional.ordinal, provisional.resource, provisional.item_id, provisional.change, provisional.left_value, provisional.right_value, provisional.changed_fields, provisional.evidence_addresses, address_item(provisional))


def _compare(ordinal: int, resource: str, item_id: str, left: Any, right: Any, evidence: Sequence[str]) -> RegistryFederationConsensusGateDiffItem | None:
    if left == right:
        return None
    if left is None:
        return _item(ordinal, resource, item_id, "added", left, right, ("value",), evidence)
    if right is None:
        return _item(ordinal, resource, item_id, "removed", left, right, ("value",), evidence)
    changed = tuple(sorted(key for key in set(left) | set(right) if left.get(key) != right.get(key))) if isinstance(left, Mapping) and isinstance(right, Mapping) else ("value",)
    return _item(ordinal, resource, item_id, "changed", left, right, changed or ("value",), evidence)


def build_diff(left: gate_model.RegistryFederationConsensusGate, right: gate_model.RegistryFederationConsensusGate, *, diff_id: str = "consensus-gate-transition") -> RegistryFederationConsensusGateDiff:
    left = gate_model.verify_gate(left)
    right = gate_model.verify_gate(right)
    evidence = (left.content_address, right.content_address)
    candidates: list[RegistryFederationConsensusGateDiffItem] = []
    left_policy = _without_address(left.policy.to_dict())
    right_policy = _without_address(right.policy.to_dict())
    item = _compare(len(candidates) + 1, "policy", left.policy.policy_id, left_policy, right_policy, evidence)
    if item:
        candidates.append(item)
    left_checks = {check.check_id: _without_address(check.to_dict()) for check in left.checks}
    right_checks = {check.check_id: _without_address(check.to_dict()) for check in right.checks}
    for check_id in sorted(set(left_checks) | set(right_checks)):
        item = _compare(len(candidates) + 1, "checks", check_id, left_checks.get(check_id), right_checks.get(check_id), evidence)
        if item:
            candidates.append(item)
    left_disposition = {"state": left.state, "decision": left.decision, "accepted": left.accepted, "passed_count": left.passed_count, "failed_count": left.failed_count}
    right_disposition = {"state": right.state, "decision": right.decision, "accepted": right.accepted, "passed_count": right.passed_count, "failed_count": right.failed_count}
    item = _compare(len(candidates) + 1, "disposition", "release-disposition", left_disposition, right_disposition, evidence)
    if item:
        candidates.append(item)
    left_receipt = {"runtime_id": left.runtime_id, "runtime_address": left.runtime_address, "consensus_id": left.consensus_id, "consensus_address": left.consensus_address}
    right_receipt = {"runtime_id": right.runtime_id, "runtime_address": right.runtime_address, "consensus_id": right.consensus_id, "consensus_address": right.consensus_address}
    item = _compare(len(candidates) + 1, "receipt", "receipt-links", left_receipt, right_receipt, evidence)
    if item:
        candidates.append(item)
    items = tuple(candidates)
    provisional = RegistryFederationConsensusGateDiff(diff_id, left, right, items, len(items), sum(item.change == "added" for item in items), sum(item.change == "removed" for item in items), sum(item.change == "changed" for item in items), left.state, right.state, left.decision, right.decision, left.accepted, right.accepted, DIFF_PREFIX + ":pending")
    return RegistryFederationConsensusGateDiff(provisional.diff_id, provisional.left, provisional.right, provisional.items, provisional.item_count, provisional.added_count, provisional.removed_count, provisional.changed_count, provisional.left_state, provisional.right_state, provisional.left_decision, provisional.right_decision, provisional.left_accepted, provisional.right_accepted, address_diff(provisional))


def diff_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateDiff:
    return verify_diff(RegistryFederationConsensusGateDiff.from_mapping(value))


def verify_diff(value: RegistryFederationConsensusGateDiff) -> RegistryFederationConsensusGateDiff:
    if not isinstance(value, RegistryFederationConsensusGateDiff) or (not value.content_address.endswith(":pending") and address_diff(value) != value.content_address):
        raise ValidationError("consensus gate diff is not valid")
    return value


def diff_json(value: RegistryFederationConsensusGateDiff) -> str:
    return canonical_json(verify_diff(value).to_dict())


def diff_csv(value: RegistryFederationConsensusGateDiff) -> str:
    value = verify_diff(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=RegistryFederationConsensusGateDiffItem.FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.items:
        row = item.to_dict()
        row["changed_fields"] = "|".join(item.changed_fields)
        row["evidence_addresses"] = "|".join(item.evidence_addresses)
        writer.writerow(row)
    return stream.getvalue()


def render_diff_markdown(value: RegistryFederationConsensusGateDiff) -> str:
    value = verify_diff(value)
    lines = ["# Consensus Release Gate Diff", "", f"- Diff: `{value.diff_id}`", f"- Left: `{value.left_state}/{value.left_decision}`", f"- Right: `{value.right_state}/{value.right_decision}`", f"- Items: `{value.item_count}`", f"- Address: `{value.content_address}`", "", "| resource | item | change | fields |", "| --- | --- | --- | --- |"]
    lines.extend(f"| `{item.resource}` | `{item.item_id}` | `{item.change}` | `{', '.join(item.changed_fields)}` |" for item in value.items)
    return "\n".join(lines) + "\n"


def item_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateDiffItem.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"type": "string"}, "item_id": {"type": "string"}, "change": {"type": "string", "enum": list(CHANGES)}, "left_value": {"type": "string"}, "right_value": {"type": "string"}, "changed_fields": {"type": "array", "items": {"type": "string"}}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string", "pattern": "^" + ITEM_PREFIX + ":"}}}


def diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateDiff.FIELDS), "properties": {"diff_id": {"type": "string"}, "left": gate_model.gate_schema(), "right": gate_model.gate_schema(), "items": {"type": "array", "items": item_schema()}, "item_count": {"type": "integer"}, "added_count": {"type": "integer"}, "removed_count": {"type": "integer"}, "changed_count": {"type": "integer"}, "left_state": {"type": "string"}, "right_state": {"type": "string"}, "left_decision": {"type": "string"}, "right_decision": {"type": "string"}, "left_accepted": {"type": "boolean"}, "right_accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + DIFF_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "diff_prefix": DIFF_PREFIX, "item_prefix": ITEM_PREFIX, "resources": RESOURCES, "changes": CHANGES, "features": ("policy transition attribution", "check-level diffs", "disposition diffs", "receipt-link diffs", "content-addressed value fingerprints", "JSON CSV and Markdown exports"), "limits": {"max_items": MAX_ITEMS}, "schemas": ("item", "diff")}


__all__ = ["BOUNDARY", "CHANGES", "DEFAULT_DIFF_ID", "DIFF_PREFIX", "ITEM_PREFIX", "MAX_ITEMS", "RESOURCES", "RegistryFederationConsensusGateDiff", "RegistryFederationConsensusGateDiffItem", "VERSION", "address_diff", "address_item", "build_diff", "capabilities", "diff_csv", "diff_from_mapping", "diff_json", "diff_schema", "item_schema", "render_diff_markdown", "verify_diff"]
