"""Addressed transition diffs for package-registry federation receipts."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry_federation as federation_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = federation_model.VERSION + "-diff-v1"
BOUNDARY = federation_model.BOUNDARY + "_diff"
DIFF_PREFIX = federation_model.FEDERATION_PREFIX + "-diff"
ITEM_PREFIX = federation_model.FEDERATION_PREFIX + "-diff-item"
DEFAULT_DIFF_ID = "federation-transition"
MAX_ITEMS = federation_model.MAX_PEERS * 16 + federation_model.MAX_PACKAGES * federation_model.MAX_PEERS * 2 + federation_model.MAX_CONFLICTS + federation_model.MAX_ACTIONS + 64
CHECK_IDS = ("exact-fields", "public-boundary", "input-addresses", "item-conservation", "category-conservation", "field-conservation", "item-addresses", "state-conservation", "content-address", "mapping-round-trip", "path-free")


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192)
    if not value or value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _optional_label(value: Any, field: str) -> str:
    return "" if value == "" else _label(value, field)


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field)
    if not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
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
    addresses = tuple(_text(item, field) for item in _sequence(value, field, maximum))
    if len(set(addresses)) != len(addresses) or any("/" in address or "\\" in address for address in addresses):
        raise ValidationError(f"{field} must contain unique path-free addresses")
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
        return "agent" not in value.lower() and "/" not in value and "\\" not in value
    return value is None or isinstance(value, (bool, int, float))


class RegistryFederationDiffItem:
    """One peer, package, conflict, or action transition."""

    FIELDS = ("ordinal", "item_id", "category", "change", "peer_id", "package_id", "left_value", "right_value", "changed_fields", "evidence_addresses", "content_address")

    def __init__(self, ordinal: int, item_id: str, category: str, change: str, peer_id: str, package_id: str, left_value: str, right_value: str, changed_fields: Sequence[str], evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "diff item ordinal", MAX_ITEMS, positive=True)
        self.item_id = _label(item_id, "diff item ID")
        self.category = _label(category, "diff category")
        if self.category not in {"peer", "package", "conflict", "action", "federation"}:
            raise ValidationError("diff category is unsupported")
        if change not in {"added", "removed", "changed"}:
            raise ValidationError("diff change is unsupported")
        self.change = change
        self.peer_id = _optional_label(peer_id, "diff peer ID")
        self.package_id = _optional_label(package_id, "diff package ID")
        self.left_value = _text(left_value, "diff left value", 4096)
        self.right_value = _text(right_value, "diff right value", 4096)
        self.changed_fields = _labels(changed_fields, "diff changed fields", 32)
        self.evidence_addresses = _addresses(evidence_addresses, "diff evidence addresses", 16)
        if not self.evidence_addresses:
            raise ValidationError("diff item evidence is required")
        self.content_address = _address(content_address, "diff item content address", ITEM_PREFIX)
        if not self.content_address.endswith(":pending") and address_item(self) != self.content_address:
            raise ValidationError("diff item content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("diff item crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "item_id": self.item_id, "category": self.category, "change": self.change, "peer_id": self.peer_id, "package_id": self.package_id, "left_value": self.left_value, "right_value": self.right_value, "changed_fields": self.changed_fields, "evidence_addresses": self.evidence_addresses, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationDiffItem:
        value = _mapping(value, "federation diff item")
        _strict(value, set(cls.FIELDS), "federation diff item")
        fields = tuple(value["changed_fields"]) if isinstance(value["changed_fields"], list) else value["changed_fields"]
        evidence = tuple(value["evidence_addresses"]) if isinstance(value["evidence_addresses"], list) else value["evidence_addresses"]
        return cls(value["ordinal"], value["item_id"], value["category"], value["change"], value["peer_id"], value["package_id"], value["left_value"], value["right_value"], fields, evidence, value["content_address"])


def address_item(value: RegistryFederationDiffItem) -> str:
    if not isinstance(value, RegistryFederationDiffItem):
        raise ValidationError("diff item address requires a typed item")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ITEM_PREFIX)


class RegistryFederationDiff:
    """A deterministic transition between two federation receipts."""

    FIELDS = ("diff_id", "left_federation_address", "right_federation_address", "left_state", "right_state", "left_decision", "right_decision", "added_peer_count", "removed_peer_count", "changed_peer_count", "changed_package_count", "changed_conflict_count", "changed_action_count", "items", "item_count", "content_address")

    def __init__(self, diff_id: str, left_federation_address: str, right_federation_address: str, left_state: str, right_state: str, left_decision: str, right_decision: str, added_peer_count: int, removed_peer_count: int, changed_peer_count: int, changed_package_count: int, changed_conflict_count: int, changed_action_count: int, items: Sequence[RegistryFederationDiffItem], item_count: int, content_address: str) -> None:
        self.diff_id = _label(diff_id, "diff ID")
        self.left_federation_address = _address(left_federation_address, "left federation address", federation_model.FEDERATION_PREFIX)
        self.right_federation_address = _address(right_federation_address, "right federation address", federation_model.FEDERATION_PREFIX)
        self.left_state = _label(left_state, "left federation state")
        self.right_state = _label(right_state, "right federation state")
        self.left_decision = _label(left_decision, "left federation decision")
        self.right_decision = _label(right_decision, "right federation decision")
        self.added_peer_count = _count(added_peer_count, "added peer count", federation_model.MAX_PEERS)
        self.removed_peer_count = _count(removed_peer_count, "removed peer count", federation_model.MAX_PEERS)
        self.changed_peer_count = _count(changed_peer_count, "changed peer count", federation_model.MAX_PEERS)
        self.changed_package_count = _count(changed_package_count, "changed package count", federation_model.MAX_PACKAGES * federation_model.MAX_PEERS)
        self.changed_conflict_count = _count(changed_conflict_count, "changed conflict count", federation_model.MAX_CONFLICTS)
        self.changed_action_count = _count(changed_action_count, "changed action count", federation_model.MAX_ACTIONS)
        self.items = tuple(items)
        self.item_count = _count(item_count, "diff item count", MAX_ITEMS)
        self.content_address = _address(content_address, "diff content address", DIFF_PREFIX)
        if len(self.items) != self.item_count or tuple(item.ordinal for item in self.items) != tuple(range(1, self.item_count + 1)) or any(not isinstance(item, RegistryFederationDiffItem) for item in self.items):
            raise ValidationError("diff items are not canonical")
        if not self.content_address.endswith(":pending") and address_diff(self) != self.content_address:
            raise ValidationError("diff content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("diff crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "left_federation_address": self.left_federation_address, "right_federation_address": self.right_federation_address, "left_state": self.left_state, "right_state": self.right_state, "left_decision": self.left_decision, "right_decision": self.right_decision, "added_peer_count": self.added_peer_count, "removed_peer_count": self.removed_peer_count, "changed_peer_count": self.changed_peer_count, "changed_package_count": self.changed_package_count, "changed_conflict_count": self.changed_conflict_count, "changed_action_count": self.changed_action_count, "items": tuple(item.to_dict() for item in self.items), "item_count": self.item_count, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "items"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationDiff:
        value = _mapping(value, "federation diff")
        _strict(value, set(cls.FIELDS), "federation diff")
        items = tuple(value["items"]) if isinstance(value["items"], list) else value["items"]
        return cls(value["diff_id"], value["left_federation_address"], value["right_federation_address"], value["left_state"], value["right_state"], value["left_decision"], value["right_decision"], value["added_peer_count"], value["removed_peer_count"], value["changed_peer_count"], value["changed_package_count"], value["changed_conflict_count"], value["changed_action_count"], tuple(RegistryFederationDiffItem.from_mapping(item) for item in items), value["item_count"], value["content_address"])


def address_diff(value: RegistryFederationDiff) -> str:
    if not isinstance(value, RegistryFederationDiff):
        raise ValidationError("diff address requires a typed diff")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


def _changed(left: Mapping[str, Any], right: Mapping[str, Any], fields: Sequence[str]) -> tuple[str, ...]:
    return tuple(field for field in fields if left.get(field) != right.get(field))


def _item(ordinal: int, item_id: str, category: str, change: str, peer_id: str, package_id: str, left_value: Any, right_value: Any, changed_fields: Sequence[str], evidence: Sequence[str]) -> RegistryFederationDiffItem:
    provisional = RegistryFederationDiffItem(ordinal, item_id, category, change, peer_id, package_id, "" if left_value is None else canonical_json(left_value) if not isinstance(left_value, str) else left_value, "" if right_value is None else canonical_json(right_value) if not isinstance(right_value, str) else right_value, changed_fields, evidence, ITEM_PREFIX + ":pending")
    return RegistryFederationDiffItem(provisional.ordinal, provisional.item_id, provisional.category, provisional.change, provisional.peer_id, provisional.package_id, provisional.left_value, provisional.right_value, provisional.changed_fields, provisional.evidence_addresses, address_item(provisional))


def _peer_map(value: federation_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation) -> dict[str, dict[str, Any]]:
    return {peer.peer_id: peer.to_dict() for peer in value.peers}


def _package_map(value: federation_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation) -> dict[tuple[str, str], dict[str, Any]]:
    return {(peer.peer_id, package_id): {"package_id": package_id, "package_address": address, "peer_state": peer.peer_state} for peer in value.peers for package_id, address in zip(peer.package_ids, peer.package_addresses, strict=True)}


def _conflict_map(value: federation_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation) -> dict[str, dict[str, Any]]:
    return {conflict.package_id: conflict.to_dict() for conflict in value.reconciliation.conflicts}


def _action_map(value: federation_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation) -> dict[str, dict[str, Any]]:
    return {action.action_id: action.to_dict() for action in value.actions}


def build_diff(left: federation_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation, right: federation_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederation, *, diff_id: str = DEFAULT_DIFF_ID) -> RegistryFederationDiff:
    left = federation_model.verify_federation(left)
    right = federation_model.verify_federation(right)
    items: list[RegistryFederationDiffItem] = []
    ordinal = 1
    left_peers, right_peers = _peer_map(left), _peer_map(right)
    for peer_id in sorted(set(left_peers) | set(right_peers)):
        before, after = left_peers.get(peer_id), right_peers.get(peer_id)
        if before is None:
            items.append(_item(ordinal, f"peer-{peer_id}", "peer", "added", peer_id, "", None, after, tuple(after), (right.content_address, after["content_address"]))); ordinal += 1
        elif after is None:
            items.append(_item(ordinal, f"peer-{peer_id}", "peer", "removed", peer_id, "", before, None, tuple(before), (left.content_address, before["content_address"]))); ordinal += 1
        else:
            fields = _changed(before, after, federation_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryFederationPeer.FIELDS)
            if fields:
                items.append(_item(ordinal, f"peer-{peer_id}", "peer", "changed", peer_id, "", before, after, fields, (left.content_address, right.content_address, before["content_address"], after["content_address"]))); ordinal += 1
    left_packages, right_packages = _package_map(left), _package_map(right)
    for key in sorted(set(left_packages) | set(right_packages)):
        before, after = left_packages.get(key), right_packages.get(key)
        peer_id, package_id = key
        if before is None:
            items.append(_item(ordinal, f"package-{peer_id}-{package_id}", "package", "added", peer_id, package_id, None, after, tuple(after), (left.content_address, right.content_address, after["package_address"]))); ordinal += 1
        elif after is None:
            items.append(_item(ordinal, f"package-{peer_id}-{package_id}", "package", "removed", peer_id, package_id, before, None, tuple(before), (left.content_address, right.content_address, before["package_address"]))); ordinal += 1
        elif before != after:
            items.append(_item(ordinal, f"package-{peer_id}-{package_id}", "package", "changed", peer_id, package_id, before, after, _changed(before, after, tuple(before)), (left.content_address, right.content_address, before["package_address"], after["package_address"]))); ordinal += 1
    for category, before_map, after_map, key_name in (("conflict", _conflict_map(left), _conflict_map(right), "package_id"), ("action", _action_map(left), _action_map(right), "action_id")):
        for key in sorted(set(before_map) | set(after_map)):
            before, after = before_map.get(key), after_map.get(key)
            if before is None:
                items.append(_item(ordinal, f"{category}-{key}", category, "added", "", before.get("package_id", "") if before else after.get("package_id", ""), None, after, tuple(after), (left.content_address, right.content_address, after["content_address"]))); ordinal += 1
            elif after is None:
                items.append(_item(ordinal, f"{category}-{key}", category, "removed", "", before.get("package_id", ""), before, None, tuple(before), (left.content_address, right.content_address, before["content_address"]))); ordinal += 1
            elif before != after:
                fields = _changed(before, after, tuple(before))
                items.append(_item(ordinal, f"{category}-{key}", category, "changed", "", before.get("package_id", ""), before, after, fields, (left.content_address, right.content_address, before["content_address"], after["content_address"]))); ordinal += 1
    counts = {category: sum(item.category == category for item in items) for category in ("peer", "package", "conflict", "action")}
    added_peers = sum(item.category == "peer" and item.change == "added" for item in items)
    removed_peers = sum(item.category == "peer" and item.change == "removed" for item in items)
    changed_peers = sum(item.category == "peer" and item.change == "changed" for item in items)
    provisional = RegistryFederationDiff(diff_id, left.content_address, right.content_address, left.state, right.state, left.decision, right.decision, added_peers, removed_peers, changed_peers, counts["package"], counts["conflict"], counts["action"], tuple(items), len(items), DIFF_PREFIX + ":pending")
    return RegistryFederationDiff(provisional.diff_id, provisional.left_federation_address, provisional.right_federation_address, provisional.left_state, provisional.right_state, provisional.left_decision, provisional.right_decision, provisional.added_peer_count, provisional.removed_peer_count, provisional.changed_peer_count, provisional.changed_package_count, provisional.changed_conflict_count, provisional.changed_action_count, provisional.items, provisional.item_count, address_diff(provisional))


def diff_from_mapping(value: Mapping[str, Any]) -> RegistryFederationDiff:
    return verify_diff(RegistryFederationDiff.from_mapping(value))


def verify_diff(value: RegistryFederationDiff) -> RegistryFederationDiff:
    if not isinstance(value, RegistryFederationDiff) or (not value.content_address.endswith(":pending") and address_diff(value) != value.content_address):
        raise ValidationError("federation diff is not valid")
    return value


def diff_json(value: RegistryFederationDiff) -> str:
    return canonical_json(verify_diff(value).to_dict())


def diff_csv(value: RegistryFederationDiff) -> str:
    value = verify_diff(value)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=("ordinal", "item_id", "category", "change", "peer_id", "package_id", "left_value", "right_value", "changed_fields", "evidence_addresses", "content_address"), lineterminator="\n")
    writer.writeheader()
    for item in value.items:
        row = item.to_dict()
        row["changed_fields"] = "|".join(item.changed_fields)
        row["evidence_addresses"] = "|".join(item.evidence_addresses)
        writer.writerow(row)
    return stream.getvalue()


def render_diff_markdown(value: RegistryFederationDiff) -> str:
    value = verify_diff(value)
    lines = ["# Package Registry Federation Diff", "", f"- Diff: `{value.diff_id}`", f"- Left: `{value.left_state}/{value.left_decision}`", f"- Right: `{value.right_state}/{value.right_decision}`", f"- Items: `{value.item_count}`", f"- Diff address: `{value.content_address}`", "", "| ordinal | category | change | peer | package | fields |", "| ---: | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.category}` | `{item.change}` | `{item.peer_id}` | `{item.package_id}` | `{','.join(item.changed_fields)}` |" for item in value.items)
    return "\n".join(lines) + "\n"


def item_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationDiffItem.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "item_id": {"type": "string"}, "category": {"type": "string"}, "change": {"type": "string"}, "peer_id": {"type": "string"}, "package_id": {"type": "string"}, "left_value": {"type": "string"}, "right_value": {"type": "string"}, "changed_fields": {"type": "array", "items": {"type": "string"}}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string", "pattern": "^" + ITEM_PREFIX + ":"}}}


def diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationDiff.FIELDS), "properties": {"diff_id": {"type": "string"}, "left_federation_address": {"type": "string"}, "right_federation_address": {"type": "string"}, "left_state": {"type": "string"}, "right_state": {"type": "string"}, "left_decision": {"type": "string"}, "right_decision": {"type": "string"}, "added_peer_count": {"type": "integer", "minimum": 0}, "removed_peer_count": {"type": "integer", "minimum": 0}, "changed_peer_count": {"type": "integer", "minimum": 0}, "changed_package_count": {"type": "integer", "minimum": 0}, "changed_conflict_count": {"type": "integer", "minimum": 0}, "changed_action_count": {"type": "integer", "minimum": 0}, "items": {"type": "array", "items": item_schema()}, "item_count": {"type": "integer", "minimum": 0}, "content_address": {"type": "string", "pattern": "^" + DIFF_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "diff_prefix": DIFF_PREFIX, "item_prefix": ITEM_PREFIX, "check_ids": CHECK_IDS, "limits": {"max_items": MAX_ITEMS}, "features": ("peer transition diff", "package observation diff", "conflict and action diff", "address-linked evidence", "JSON CSV and Markdown exports"), "schemas": ("item", "diff")}


__all__ = ["BOUNDARY", "CHECK_IDS", "DEFAULT_DIFF_ID", "DIFF_PREFIX", "ITEM_PREFIX", "MAX_ITEMS", "VERSION", "RegistryFederationDiff", "RegistryFederationDiffItem", "address_diff", "address_item", "build_diff", "capabilities", "diff_csv", "diff_from_mapping", "diff_json", "diff_schema", "item_schema", "render_diff_markdown", "verify_diff"]
