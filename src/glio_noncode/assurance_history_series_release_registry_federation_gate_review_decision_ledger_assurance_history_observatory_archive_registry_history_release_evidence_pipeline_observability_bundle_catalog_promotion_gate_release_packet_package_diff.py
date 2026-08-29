"""Deterministic evolution diffs for persisted promotion release packages."""

from __future__ import annotations

# ruff: noqa: E501, I001

from collections.abc import Mapping
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package as package_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = package_model.VERSION + "-diff-v1"
BOUNDARY = package_model.BOUNDARY + "_diff"
DIFF_PREFIX = package_model.PACKAGE_PREFIX + "-diff"
ITEM_PREFIX = DIFF_PREFIX + "-item"
DEFAULT_DIFF_ID = "glio-noncode-observability-bundle-catalog-promotion-release-package-diff"
STATES = ("unchanged", "changed")
MAX_ITEMS = 64
MAX_TEXT = 4096
COMPARE_FIELDS = ("packet.state", "packet.decision", "packet.accepted", "packet.release_ready", "packet.check_count", "packet.passed_count", "packet.failed_count", "packet.blocking_failure_count", "packet.hold_failure_count", "packet.action_count", "packet.failed_check_ids", "manifest.artifact_count", "manifest.files")


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 256)
    if ":" in value or "/" in value or "\\" in value or any(character.isspace() for character in value):
        raise ValidationError(f"{field} must be a stable path-free label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if ":" not in value or value.startswith(("/", "\\")) or "\\" in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} must be a public content address")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be a mapping")
    return value


def _sequence(value: Any, field: str, maximum: int = MAX_ITEMS) -> tuple[Any, ...]:
    if not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    return package_model._public(value)


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _canonical(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return tuple(_canonical(item) for item in value)
    return value


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffItem:
    """One changed package projection field."""

    FIELDS = ("ordinal", "field", "before", "after", "content_address")

    def __init__(self, ordinal: int, field: str, before: Any, after: Any, content_address: str) -> None:
        self.ordinal = _count(ordinal, "observability bundle catalog promotion package diff item ordinal", MAX_ITEMS)
        if self.ordinal == 0:
            raise ValidationError("observability bundle catalog promotion package diff item ordinal must be positive")
        self.field = _text(field, "observability bundle catalog promotion package diff item field", 128)
        self.before = _canonical(before)
        self.after = _canonical(after)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "observability bundle catalog promotion package diff item content address")
        else:
            _address(self.content_address, "observability bundle catalog promotion package diff item content address", ITEM_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_item(self) != self.content_address):
            raise ValidationError("observability bundle catalog promotion package diff item is not public or addressed")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffItem:
        value = _mapping(value, "observability bundle catalog promotion package diff item")
        _strict(value, set(cls.FIELDS), "observability bundle catalog promotion package diff item")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog promotion package diff item is missing fields: {missing}")
        return cls(value["ordinal"], value["field"], value["before"], value["after"], value["content_address"])


def address_item(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffItem) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffItem):
        raise ValidationError("observability bundle catalog promotion package diff item address requires a typed item")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ITEM_PREFIX)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiff:
    """An addressed comparison between two persisted package projections."""

    FIELDS = ("diff_id", "left_package_address", "right_package_address", "left_packet_address", "right_packet_address", "state", "left_decision", "right_decision", "left_action_count", "right_action_count", "action_count_delta", "changed_fields", "action_added_ids", "action_removed_ids", "action_changed_ids", "items", "content_address")

    def __init__(self, diff_id: str, left_package_address: str, right_package_address: str, left_packet_address: str, right_packet_address: str, state: str, left_decision: str, right_decision: str, left_action_count: int, right_action_count: int, action_count_delta: int, changed_fields: tuple[str, ...], action_added_ids: tuple[str, ...], action_removed_ids: tuple[str, ...], action_changed_ids: tuple[str, ...], items: tuple[RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffItem, ...], content_address: str) -> None:
        self.diff_id = _label(diff_id, "observability bundle catalog promotion package diff ID")
        self.left_package_address = _address(left_package_address, "observability bundle catalog promotion package diff left package address", package_model.PACKAGE_PREFIX)
        self.right_package_address = _address(right_package_address, "observability bundle catalog promotion package diff right package address", package_model.PACKAGE_PREFIX)
        self.left_packet_address = _address(left_packet_address, "observability bundle catalog promotion package diff left packet address", package_model.packet_model.PACKET_PREFIX)
        self.right_packet_address = _address(right_packet_address, "observability bundle catalog promotion package diff right packet address", package_model.packet_model.PACKET_PREFIX)
        if state not in STATES:
            raise ValidationError("observability bundle catalog promotion package diff state is unsupported")
        self.state = state
        self.left_decision = _text(left_decision, "observability bundle catalog promotion package diff left decision", 32)
        self.right_decision = _text(right_decision, "observability bundle catalog promotion package diff right decision", 32)
        self.left_action_count = _count(left_action_count, "observability bundle catalog promotion package diff left action count", package_model.packet_model.MAX_ACTIONS)
        self.right_action_count = _count(right_action_count, "observability bundle catalog promotion package diff right action count", package_model.packet_model.MAX_ACTIONS)
        if isinstance(action_count_delta, bool) or not isinstance(action_count_delta, int) or abs(action_count_delta) > package_model.packet_model.MAX_ACTIONS:
            raise ValidationError("observability bundle catalog promotion package diff action count delta is outside its bound")
        self.action_count_delta = action_count_delta
        self.changed_fields = tuple(_text(field, "observability bundle catalog promotion package diff changed field", 128) for field in _sequence(changed_fields, "observability bundle catalog promotion package diff changed fields", len(COMPARE_FIELDS)))
        self.action_added_ids = tuple(_text(item, "observability bundle catalog promotion package diff added action ID", 128) for item in _sequence(action_added_ids, "observability bundle catalog promotion package diff added action IDs"))
        self.action_removed_ids = tuple(_text(item, "observability bundle catalog promotion package diff removed action ID", 128) for item in _sequence(action_removed_ids, "observability bundle catalog promotion package diff removed action IDs"))
        self.action_changed_ids = tuple(_text(item, "observability bundle catalog promotion package diff changed action ID", 128) for item in _sequence(action_changed_ids, "observability bundle catalog promotion package diff changed action IDs"))
        self.items = tuple(items)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.state != ("unchanged" if not self.changed_fields else "changed") or self.action_count_delta != self.right_action_count - self.left_action_count or tuple(item.ordinal for item in self.items) != tuple(range(1, len(self.items) + 1)) or len(self.items) != len(self.changed_fields) or tuple(item.field for item in self.items) != self.changed_fields or any(not isinstance(item, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffItem) for item in self.items):
            raise ValidationError("observability bundle catalog promotion package diff observations are not conserved")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "observability bundle catalog promotion package diff content address")
        else:
            _address(self.content_address, "observability bundle catalog promotion package diff content address", DIFF_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_diff(self) != self.content_address):
            raise ValidationError("observability bundle catalog promotion package diff is not public or addressed")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) if field != "items" else tuple(item.to_dict() for item in self.items) for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "items"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiff:
        value = _mapping(value, "observability bundle catalog promotion package diff")
        _strict(value, set(cls.FIELDS), "observability bundle catalog promotion package diff")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog promotion package diff is missing fields: {missing}")
        items = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffItem.from_mapping(item) for item in _sequence(value["items"], "observability bundle catalog promotion package diff items"))
        return cls(value["diff_id"], value["left_package_address"], value["right_package_address"], value["left_packet_address"], value["right_packet_address"], value["state"], value["left_decision"], value["right_decision"], value["left_action_count"], value["right_action_count"], value["action_count_delta"], tuple(value["changed_fields"]), tuple(value["action_added_ids"]), tuple(value["action_removed_ids"]), tuple(value["action_changed_ids"]), items, value["content_address"])


def address_diff(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiff) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiff):
        raise ValidationError("observability bundle catalog promotion package diff address requires a typed diff")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


def _field_value(value: package_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage, field: str) -> Any:
    if field.startswith("packet."):
        return value.packet.to_dict()[field.removeprefix("packet.")]
    return value.manifest[field.removeprefix("manifest.")]


def _action_map(value: package_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage) -> dict[str, str]:
    return {action.check_id: action.content_address for action in value.packet.actions}


def build_diff(left: package_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage, right: package_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage, *, diff_id: str = DEFAULT_DIFF_ID) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiff:
    if not isinstance(left, package_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage) or not isinstance(right, package_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage):
        raise ValidationError("observability bundle catalog promotion package diff requires typed packages")
    package_model.verify_package(left)
    package_model.verify_package(right)
    changes = tuple((field, _field_value(left, field), _field_value(right, field)) for field in COMPARE_FIELDS if _field_value(left, field) != _field_value(right, field))
    left_actions = _action_map(left)
    right_actions = _action_map(right)
    added = tuple(sorted(set(right_actions) - set(left_actions)))
    removed = tuple(sorted(set(left_actions) - set(right_actions)))
    changed = tuple(sorted(check_id for check_id in set(left_actions) & set(right_actions) if left_actions[check_id] != right_actions[check_id]))
    provisional_items = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffItem(index, field, before, after, "pending:observability-bundle-catalog-promotion-package-diff-item") for index, (field, before, after) in enumerate(changes, 1))
    items = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffItem(item.ordinal, item.field, item.before, item.after, address_item(item)) for item in provisional_items)
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiff(diff_id, left.content_address, right.content_address, left.packet_address, right.packet_address, "changed" if changes else "unchanged", left.packet.decision, right.packet.decision, left.packet.action_count, right.packet.action_count, right.packet.action_count - left.packet.action_count, tuple(field for field, _, _ in changes), added, removed, changed, items, "pending:observability-bundle-catalog-promotion-package-diff")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiff(provisional.diff_id, provisional.left_package_address, provisional.right_package_address, provisional.left_packet_address, provisional.right_packet_address, provisional.state, provisional.left_decision, provisional.right_decision, provisional.left_action_count, provisional.right_action_count, provisional.action_count_delta, provisional.changed_fields, provisional.action_added_ids, provisional.action_removed_ids, provisional.action_changed_ids, provisional.items, address_diff(provisional))


def diff_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiff:
    return verify_diff(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiff.from_mapping(_mapping(value, "observability bundle catalog promotion package diff")))


def verify_diff(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiff) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiff:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiff):
        raise ValidationError("observability bundle catalog promotion package diff verification requires a typed diff")
    value._validate()
    if address_diff(value) != value.content_address:
        raise ValidationError("observability bundle catalog promotion package diff content address does not replay")
    return value


def diff_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiff) -> str:
    return canonical_json(verify_diff(value).to_dict())


def diff_csv(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiff) -> str:
    value = verify_diff(value)
    fields = ("ordinal", "field", "before", "after", "content_address")
    rows = ["ordinal,field,before,after,content_address"]
    for item in value.items:
        rows.append(",".join(str(item.to_dict()[field]).replace(",", "\\,") for field in fields))
    return "\n".join(rows) + "\n"


def render_diff_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiff) -> str:
    value = verify_diff(value)
    lines = ["# Assurance History Observatory Catalog Promotion Release Package Diff", "", f"- State: `{value.state}`", f"- Left package: `{value.left_package_address}`", f"- Right package: `{value.right_package_address}`", f"- Decisions: `{value.left_decision}` → `{value.right_decision}`", f"- Action count delta: `{value.action_count_delta}`", f"- Added actions: `{len(value.action_added_ids)}`", f"- Removed actions: `{len(value.action_removed_ids)}`", f"- Changed actions: `{len(value.action_changed_ids)}`", f"- Content address: `{value.content_address}`", "", "| ordinal | field | before | after | item address |", "| ---: | --- | --- | --- | --- |"]
    if value.items:
        lines.extend(f"| {item.ordinal} | `{item.field}` | `{canonical_json(item.before)}` | `{canonical_json(item.after)}` | `{item.content_address}` |" for item in value.items)
    else:
        lines.append("| — | No changed fields | — | — | — |")
    return "\n".join(lines) + "\n"


def item_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffItem.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_ITEMS}, "field": {"type": "string", "maxLength": 128}, "before": {}, "after": {}, "content_address": {"type": "string", "pattern": "^" + ITEM_PREFIX + ":"}}}


def diff_schema() -> dict[str, Any]:
    properties: dict[str, Any] = {"diff_id": {"type": "string", "maxLength": 256}, "left_package_address": {"type": "string", "pattern": "^" + package_model.PACKAGE_PREFIX + ":"}, "right_package_address": {"type": "string", "pattern": "^" + package_model.PACKAGE_PREFIX + ":"}, "left_packet_address": {"type": "string", "pattern": "^" + package_model.packet_model.PACKET_PREFIX + ":"}, "right_packet_address": {"type": "string", "pattern": "^" + package_model.packet_model.PACKET_PREFIX + ":"}, "state": {"type": "string", "enum": list(STATES)}, "left_decision": {"type": "string"}, "right_decision": {"type": "string"}, "action_count_delta": {"type": "integer", "minimum": -package_model.packet_model.MAX_ACTIONS, "maximum": package_model.packet_model.MAX_ACTIONS}, "changed_fields": {"type": "array", "maxItems": len(COMPARE_FIELDS), "items": {"type": "string", "enum": list(COMPARE_FIELDS)}}, "action_added_ids": {"type": "array", "maxItems": package_model.packet_model.MAX_ACTIONS, "items": {"type": "string"}}, "action_removed_ids": {"type": "array", "maxItems": package_model.packet_model.MAX_ACTIONS, "items": {"type": "string"}}, "action_changed_ids": {"type": "array", "maxItems": package_model.packet_model.MAX_ACTIONS, "items": {"type": "string"}}, "items": {"type": "array", "maxItems": MAX_ITEMS, "items": item_schema()}, "content_address": {"type": "string", "pattern": "^" + DIFF_PREFIX + ":"}}
    for field in ("left_action_count", "right_action_count"):
        properties[field] = {"type": "integer", "minimum": 0, "maximum": package_model.packet_model.MAX_ACTIONS}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiff.FIELDS), "properties": properties}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "diff_prefix": DIFF_PREFIX, "item_prefix": ITEM_PREFIX, "states": STATES, "compare_fields": COMPARE_FIELDS, "limits": {"max_items": MAX_ITEMS, "max_actions": package_model.packet_model.MAX_ACTIONS}, "features": ("persisted package comparison", "decision and readiness transitions", "action addition removal and change detection", "field-level addressed items", "deterministic sorted observations", "path-free JSON CSV and Markdown output") , "schemas": ("item", "diff")}


__all__ = [
    "BOUNDARY", "COMPARE_FIELDS", "DEFAULT_DIFF_ID", "DIFF_PREFIX", "ITEM_PREFIX", "MAX_ITEMS", "STATES", "VERSION",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffItem", "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiff",
    "address_diff", "address_item", "build_diff", "capabilities", "diff_csv", "diff_from_mapping", "diff_json", "diff_schema", "item_schema", "render_diff_markdown", "verify_diff",
]
