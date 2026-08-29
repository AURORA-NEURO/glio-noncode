"""Deterministic transitions between quorum consensus receipts."""

# ruff: noqa: E501, I001

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus as consensus_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry_federation as federation_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = consensus_model.VERSION + "-diff-v1"
BOUNDARY = consensus_model.BOUNDARY + "_diff"
DIFF_PREFIX = federation_model.FEDERATION_PREFIX + "-consensus-diff"
ITEM_PREFIX = federation_model.FEDERATION_PREFIX + "-consensus-diff-item"
DEFAULT_DIFF_ID = "consensus-transition"
MAX_ITEMS = consensus_model.MAX_PACKAGES * 4 + consensus_model.MAX_PACKAGES * consensus_model.MAX_PEERS * 2 + consensus_model.MAX_ACTIONS + 8
CHECK_IDS = ("exact-fields", "public-boundary", "input-addresses", "item-conservation", "category-conservation", "field-conservation", "item-addresses", "state-conservation", "acceptance-conservation", "content-address", "mapping-round-trip", "path-free")


def _text(value: Any, field: str, maximum: int = 32768, *, required: bool = False) -> str:
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


def _optional_label(value: Any, field: str) -> str:
    return "" if value == "" else _label(value, field)


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
    result = tuple(_label(item, field) for item in _sequence(value, field, maximum))
    if len(set(result)) != len(result):
        raise ValidationError(f"{field} must be unique")
    return tuple(sorted(result))


def _addresses(value: Any, field: str, maximum: int) -> tuple[str, ...]:
    result = tuple(_address(item, field) for item in _sequence(value, field, maximum))
    if len(set(result)) != len(result):
        raise ValidationError(f"{field} must be unique")
    return tuple(sorted(result))


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


class RegistryFederationConsensusDiffItem:
    """One package, candidate, action, or receipt transition."""

    FIELDS = ("ordinal", "item_id", "category", "change", "package_id", "kind", "left_value", "right_value", "changed_fields", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, item_id: str, category: str, change: str, package_id: str, kind: str, left_value: str, right_value: str, changed_fields: Sequence[str], evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "consensus diff item ordinal", MAX_ITEMS, positive=True)
        self.item_id = _label(item_id, "consensus diff item ID")
        self.category = _label(category, "consensus diff category")
        if self.category not in {"package", "candidate", "action", "receipt"}:
            raise ValidationError("consensus diff category is unsupported")
        if change not in {"added", "removed", "changed"}:
            raise ValidationError("consensus diff change is unsupported")
        self.change = change
        self.package_id = _optional_label(package_id, "consensus diff package ID")
        self.kind = _optional_label(kind, "consensus diff kind")
        self.left_value = _text(left_value, "consensus diff left value")
        self.right_value = _text(right_value, "consensus diff right value")
        self.changed_fields = _labels(changed_fields, "consensus diff changed fields", 64)
        self.evidence_addresses = _addresses(evidence_addresses, "consensus diff evidence addresses", 32)
        if not self.evidence_addresses:
            raise ValidationError("consensus diff item evidence is required")
        self.content_address = _address(content_address, "consensus diff item content address", ITEM_PREFIX)
        if not self.content_address.endswith(":pending") and address_item(self) != self.content_address:
            raise ValidationError("consensus diff item content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("consensus diff item crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "item_id": self.item_id, "category": self.category, "change": self.change, "package_id": self.package_id, "kind": self.kind, "left_value": self.left_value, "right_value": self.right_value, "changed_fields": self.changed_fields, "evidence_addresses": self.evidence_addresses, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusDiffItem:
        value = _mapping(value, "consensus diff item")
        _strict(value, set(cls.FIELDS), "consensus diff item")
        return cls(value["ordinal"], value["item_id"], value["category"], value["change"], value["package_id"], value["kind"], value["left_value"], value["right_value"], value["changed_fields"], value["evidence_addresses"], value["content_address"])


def address_item(value: RegistryFederationConsensusDiffItem) -> str:
    if not isinstance(value, RegistryFederationConsensusDiffItem):
        raise ValidationError("consensus diff item address requires a typed item")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ITEM_PREFIX)


class RegistryFederationConsensusDiff:
    """A deterministic, addressed transition between two consensus receipts."""

    FIELDS = ("diff_id", "left_consensus_address", "right_consensus_address", "left_state", "right_state", "left_decision", "right_decision", "left_accepted", "right_accepted", "added_package_count", "removed_package_count", "changed_package_count", "added_candidate_count", "removed_candidate_count", "changed_candidate_count", "added_action_count", "removed_action_count", "changed_action_count", "items", "item_count", "content_address")

    def __init__(self, diff_id: str, left_consensus_address: str, right_consensus_address: str, left_state: str, right_state: str, left_decision: str, right_decision: str, left_accepted: bool, right_accepted: bool, added_package_count: int, removed_package_count: int, changed_package_count: int, added_candidate_count: int, removed_candidate_count: int, changed_candidate_count: int, added_action_count: int, removed_action_count: int, changed_action_count: int, items: Sequence[RegistryFederationConsensusDiffItem], item_count: int, content_address: str) -> None:
        self.diff_id = _label(diff_id, "consensus diff ID")
        self.left_consensus_address = _address(left_consensus_address, "left consensus address", consensus_model.CONSENSUS_PREFIX)
        self.right_consensus_address = _address(right_consensus_address, "right consensus address", consensus_model.CONSENSUS_PREFIX)
        if left_state not in consensus_model.STATES or right_state not in consensus_model.STATES or left_decision not in consensus_model.DECISIONS or right_decision not in consensus_model.DECISIONS:
            raise ValidationError("consensus diff disposition is unsupported")
        self.left_state, self.right_state = left_state, right_state
        self.left_decision, self.right_decision = left_decision, right_decision
        self.left_accepted = _bool(left_accepted, "left consensus acceptance")
        self.right_accepted = _bool(right_accepted, "right consensus acceptance")
        fields = ("added_package_count", "removed_package_count", "changed_package_count", "added_candidate_count", "removed_candidate_count", "changed_candidate_count", "added_action_count", "removed_action_count", "changed_action_count")
        maximums = (consensus_model.MAX_PACKAGES, consensus_model.MAX_PACKAGES, consensus_model.MAX_PACKAGES, consensus_model.MAX_PACKAGES * consensus_model.MAX_PEERS, consensus_model.MAX_PACKAGES * consensus_model.MAX_PEERS, consensus_model.MAX_PACKAGES * consensus_model.MAX_PEERS, consensus_model.MAX_ACTIONS, consensus_model.MAX_ACTIONS, consensus_model.MAX_ACTIONS)
        for field, item, maximum in zip(fields, (added_package_count, removed_package_count, changed_package_count, added_candidate_count, removed_candidate_count, changed_candidate_count, added_action_count, removed_action_count, changed_action_count), maximums, strict=True):
            setattr(self, field, _count(item, field, maximum))
        self.items = tuple(items)
        if not self.items:
            raise ValidationError("consensus diff requires at least one changed item")
        self.item_count = _count(item_count, "consensus diff item count", MAX_ITEMS, positive=True)
        if len(self.items) != self.item_count or tuple(item.ordinal for item in self.items) != tuple(range(1, self.item_count + 1)):
            raise ValidationError("consensus diff item ordering is not conserved")
        expected = {"package": (self.added_package_count, self.removed_package_count, self.changed_package_count), "candidate": (self.added_candidate_count, self.removed_candidate_count, self.changed_candidate_count), "action": (self.added_action_count, self.removed_action_count, self.changed_action_count)}
        for category, counts in expected.items():
            observed = tuple(sum(item.category == category and item.change == change for item in self.items) for change in ("added", "removed", "changed"))
            if observed != counts:
                raise ValidationError(f"consensus diff {category} counters are not conserved")
        self.content_address = _address(content_address, "consensus diff content address", DIFF_PREFIX)
        if not self.content_address.endswith(":pending") and address_diff(self) != self.content_address:
            raise ValidationError("consensus diff content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("consensus diff crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "left_consensus_address": self.left_consensus_address, "right_consensus_address": self.right_consensus_address, "left_state": self.left_state, "right_state": self.right_state, "left_decision": self.left_decision, "right_decision": self.right_decision, "left_accepted": self.left_accepted, "right_accepted": self.right_accepted, "added_package_count": self.added_package_count, "removed_package_count": self.removed_package_count, "changed_package_count": self.changed_package_count, "added_candidate_count": self.added_candidate_count, "removed_candidate_count": self.removed_candidate_count, "changed_candidate_count": self.changed_candidate_count, "added_action_count": self.added_action_count, "removed_action_count": self.removed_action_count, "changed_action_count": self.changed_action_count, "items": tuple(item.to_dict() for item in self.items), "item_count": self.item_count, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "items"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusDiff:
        value = _mapping(value, "consensus diff")
        _strict(value, set(cls.FIELDS), "consensus diff")
        return cls(value["diff_id"], value["left_consensus_address"], value["right_consensus_address"], value["left_state"], value["right_state"], value["left_decision"], value["right_decision"], value["left_accepted"], value["right_accepted"], value["added_package_count"], value["removed_package_count"], value["changed_package_count"], value["added_candidate_count"], value["removed_candidate_count"], value["changed_candidate_count"], value["added_action_count"], value["removed_action_count"], value["changed_action_count"], tuple(RegistryFederationConsensusDiffItem.from_mapping(item) for item in value["items"]), value["item_count"], value["content_address"])


def address_diff(value: RegistryFederationConsensusDiff) -> str:
    if not isinstance(value, RegistryFederationConsensusDiff):
        raise ValidationError("consensus diff address requires a typed diff")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


def _key_address(category: str, package_id: str, key: str) -> str:
    return content_hash({"category": category, "package_id": package_id, "key": key}, prefix=DIFF_PREFIX + "-key")


def _evidence(record: Mapping[str, Any] | None, fallback: Sequence[str]) -> tuple[str, ...]:
    values = set(fallback)
    if record is not None:
        values.update(str(item) for item in record.get("evidence_addresses", ()) if isinstance(item, str))
        if isinstance(record.get("content_address"), str):
            values.add(record["content_address"])
    return tuple(sorted(values))


def _object_item(category: str, package_id: str, kind: str, key: str, left: Mapping[str, Any] | None, right: Mapping[str, Any] | None, evidence: Sequence[str]) -> tuple[str, str, str, str, tuple[str, ...]] | None:
    if left is None and right is None:
        return None
    left_value = content_hash(left, prefix=DIFF_PREFIX + "-value") if left is not None else ""
    right_value = content_hash(right, prefix=DIFF_PREFIX + "-value") if right is not None else ""
    if left is not None and right is not None and left_value == right_value:
        return None
    change = "added" if left is None else "removed" if right is None else "changed"
    return (change, left_value, right_value, _key_address(category, package_id, key).split(":", 1)[-1][:40], tuple(sorted(set(evidence))))


def _append_object(items: list[RegistryFederationConsensusDiffItem], category: str, package_id: str, kind: str, key: str, left: Mapping[str, Any] | None, right: Mapping[str, Any] | None, evidence: Sequence[str]) -> None:
    result = _object_item(category, package_id, kind, key, left, right, evidence)
    if result is None:
        return
    change, left_value, right_value, token, addresses = result
    provisional = RegistryFederationConsensusDiffItem(len(items) + 1, f"{category}-{token}", category, change, package_id, kind, left_value, right_value, tuple(sorted(set(() if change != "changed" else tuple(field for field in set((left or {}) | (right or {})) if field != "content_address" and (left or {}).get(field) != (right or {}).get(field))))), addresses, ITEM_PREFIX + ":pending")
    items.append(RegistryFederationConsensusDiffItem(provisional.ordinal, provisional.item_id, provisional.category, provisional.change, provisional.package_id, provisional.kind, provisional.left_value, provisional.right_value, provisional.changed_fields, provisional.evidence_addresses, address_item(provisional)))


def build_diff(left: consensus_model.RegistryFederationConsensus, right: consensus_model.RegistryFederationConsensus, *, diff_id: str = DEFAULT_DIFF_ID) -> RegistryFederationConsensusDiff:
    left = consensus_model.verify_consensus(left)
    right = consensus_model.verify_consensus(right)
    items: list[RegistryFederationConsensusDiffItem] = []
    left_packages = {item.package_id: item for item in left.packages}
    right_packages = {item.package_id: item for item in right.packages}
    for package_id in sorted(set(left_packages) | set(right_packages)):
        left_package = left_packages.get(package_id)
        right_package = right_packages.get(package_id)
        left_record = left_package.to_dict() if left_package else None
        right_record = right_package.to_dict() if right_package else None
        _append_object(items, "package", package_id, "", package_id, left_record, right_record, (left.content_address, right.content_address))
        left_candidates = {(package_id, item.address): item for item in left_package.candidates} if left_package else {}
        right_candidates = {(package_id, item.address): item for item in right_package.candidates} if right_package else {}
        for key in sorted(set(left_candidates) | set(right_candidates)):
            left_candidate = left_candidates.get(key)
            right_candidate = right_candidates.get(key)
            _append_object(items, "candidate", package_id, "", key[1], left_candidate.to_dict() if left_candidate else None, right_candidate.to_dict() if right_candidate else None, (left.content_address, right.content_address))
    left_actions = {item.action_id: item for item in left.actions}
    right_actions = {item.action_id: item for item in right.actions}
    for action_id in sorted(set(left_actions) | set(right_actions)):
        left_action = left_actions.get(action_id)
        right_action = right_actions.get(action_id)
        package_id = (left_action or right_action).package_id
        _append_object(items, "action", package_id, (left_action or right_action).kind, action_id, left_action.to_dict() if left_action else None, right_action.to_dict() if right_action else None, (left.content_address, right.content_address))
    receipt_left = {"quorum": left.quorum, "state": left.state, "decision": left.decision, "accepted": left.accepted, "package_count": left.package_count, "selected_count": left.selected_count, "unresolved_count": left.unresolved_count, "action_count": left.action_count}
    receipt_right = {"quorum": right.quorum, "state": right.state, "decision": right.decision, "accepted": right.accepted, "package_count": right.package_count, "selected_count": right.selected_count, "unresolved_count": right.unresolved_count, "action_count": right.action_count}
    _append_object(items, "receipt", "", "", "receipt", receipt_left, receipt_right, (left.content_address, right.content_address))
    counts = {category: tuple(sum(item.category == category and item.change == change for item in items) for change in ("added", "removed", "changed")) for category in ("package", "candidate", "action")}
    provisional = RegistryFederationConsensusDiff(diff_id, left.content_address, right.content_address, left.state, right.state, left.decision, right.decision, left.accepted, right.accepted, *counts["package"], *counts["candidate"], *counts["action"], tuple(items), len(items), DIFF_PREFIX + ":pending")
    return RegistryFederationConsensusDiff(provisional.diff_id, provisional.left_consensus_address, provisional.right_consensus_address, provisional.left_state, provisional.right_state, provisional.left_decision, provisional.right_decision, provisional.left_accepted, provisional.right_accepted, provisional.added_package_count, provisional.removed_package_count, provisional.changed_package_count, provisional.added_candidate_count, provisional.removed_candidate_count, provisional.changed_candidate_count, provisional.added_action_count, provisional.removed_action_count, provisional.changed_action_count, provisional.items, provisional.item_count, address_diff(provisional))


def diff_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusDiff:
    return verify_diff(RegistryFederationConsensusDiff.from_mapping(value))


def verify_diff(value: RegistryFederationConsensusDiff) -> RegistryFederationConsensusDiff:
    if not isinstance(value, RegistryFederationConsensusDiff) or (not value.content_address.endswith(":pending") and address_diff(value) != value.content_address):
        raise ValidationError("consensus diff is not valid")
    return value


def diff_json(value: RegistryFederationConsensusDiff) -> str:
    return canonical_json(verify_diff(value).to_dict())


def diff_csv(value: RegistryFederationConsensusDiff) -> str:
    value = verify_diff(value)
    fields = ("ordinal", "item_id", "category", "change", "package_id", "kind", "left_value", "right_value", "changed_fields", "evidence_addresses", "content_address")
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.items:
        row = item.to_dict()
        row["changed_fields"] = "|".join(item.changed_fields)
        row["evidence_addresses"] = "|".join(item.evidence_addresses)
        writer.writerow(row)
    return stream.getvalue()


def render_diff_markdown(value: RegistryFederationConsensusDiff) -> str:
    value = verify_diff(value)
    lines = ["# Consensus Receipt Diff", "", f"- Left: `{value.left_consensus_address}`", f"- Right: `{value.right_consensus_address}`", f"- State: `{value.left_state}` → `{value.right_state}`", f"- Decision: `{value.left_decision}` → `{value.right_decision}`", f"- Accepted: `{value.left_accepted}` → `{value.right_accepted}`", f"- Items: `{value.item_count}`", "", "| item | category | change | package | kind |", "| --- | --- | --- | --- | --- |"]
    lines.extend(f"| `{item.item_id}` | `{item.category}` | `{item.change}` | `{item.package_id}` | `{item.kind}` |" for item in value.items)
    return "\n".join(lines) + "\n"


def item_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusDiffItem.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "item_id": {"type": "string"}, "category": {"type": "string"}, "change": {"type": "string"}, "package_id": {"type": "string"}, "kind": {"type": "string"}, "left_value": {"type": "string"}, "right_value": {"type": "string"}, "changed_fields": {"type": "array"}, "evidence_addresses": {"type": "array"}, "content_address": {"type": "string", "pattern": "^" + ITEM_PREFIX + ":"}}}


def diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusDiff.FIELDS), "properties": {"diff_id": {"type": "string"}, "left_consensus_address": {"type": "string"}, "right_consensus_address": {"type": "string"}, "left_state": {"type": "string"}, "right_state": {"type": "string"}, "left_decision": {"type": "string"}, "right_decision": {"type": "string"}, "left_accepted": {"type": "boolean"}, "right_accepted": {"type": "boolean"}, "added_package_count": {"type": "integer"}, "removed_package_count": {"type": "integer"}, "changed_package_count": {"type": "integer"}, "added_candidate_count": {"type": "integer"}, "removed_candidate_count": {"type": "integer"}, "changed_candidate_count": {"type": "integer"}, "added_action_count": {"type": "integer"}, "removed_action_count": {"type": "integer"}, "changed_action_count": {"type": "integer"}, "items": {"type": "array", "items": item_schema()}, "item_count": {"type": "integer"}, "content_address": {"type": "string", "pattern": "^" + DIFF_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "diff_prefix": DIFF_PREFIX, "item_prefix": ITEM_PREFIX, "check_ids": CHECK_IDS, "categories": ("package", "candidate", "action", "receipt"), "changes": ("added", "removed", "changed"), "limits": {"max_items": MAX_ITEMS}, "features": ("address-to-address consensus comparison", "package candidate transitions", "remediation action transitions", "receipt disposition transitions", "field-level change attribution", "JSON CSV and Markdown exports"), "schemas": ("item", "diff")}


__all__ = ["BOUNDARY", "CHECK_IDS", "DEFAULT_DIFF_ID", "DIFF_PREFIX", "ITEM_PREFIX", "MAX_ITEMS", "RegistryFederationConsensusDiff", "RegistryFederationConsensusDiffItem", "VERSION", "address_diff", "address_item", "build_diff", "capabilities", "diff_csv", "diff_from_mapping", "diff_json", "diff_schema", "item_schema", "render_diff_markdown", "verify_diff"]
