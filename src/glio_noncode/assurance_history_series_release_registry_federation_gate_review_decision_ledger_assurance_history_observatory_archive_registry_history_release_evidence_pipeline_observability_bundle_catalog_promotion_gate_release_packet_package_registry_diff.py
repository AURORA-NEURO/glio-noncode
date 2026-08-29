"""Deterministic evolution diffs and assurance for package registries."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry as registry_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = registry_model.VERSION + "-diff-v1"
BOUNDARY = registry_model.BOUNDARY + "_diff"
DIFF_PREFIX = registry_model.REGISTRY_PREFIX + "-diff"
ITEM_PREFIX = DIFF_PREFIX + "-item"
AUDIT_PREFIX = DIFF_PREFIX + "-audit"
DEFAULT_DIFF_ID = "glio-noncode-catalog-promotion-package-registry-diff"
STATES = ("unchanged", "changed", "expanded", "contracted")
CHANGES = ("added", "removed", "changed")
MAX_ITEMS = registry_model.MAX_ENTRIES * 2
MAX_TEXT = registry_model.MAX_TEXT
COMPARE_FIELDS = ("state", "decision", "accepted", "release_ready", "package_audit_state", "package_audit_accepted", "artifact_count", "file_count", "check_count", "passed_count", "failed_count", "action_count")
CHECK_IDS = ("exact-fields", "public-boundary", "input-addresses", "state-conservation", "entry-count-conservation", "item-conservation", "field-conservation", "item-addresses", "content-address", "mapping-round-trip", "path-free")


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 256)
    if ":" in value or "/" in value or "\\" in value or any(character.isspace() for character in value):
        raise ValidationError(f"{field} must be a stable path-free label")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 2048)
    if ":" not in value or value.startswith(("/", "\\")) or "\\" in value or not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an invalid public content address")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be a mapping")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    return registry_model._public(value)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffItem:
    """One package receipt addition, removal, or change."""

    FIELDS = ("ordinal", "package_id", "change", "left_entry_address", "right_entry_address", "changed_fields", "detail", "content_address")

    def __init__(self, ordinal: int, package_id: str, change: str, left_entry_address: str | None, right_entry_address: str | None, changed_fields: Sequence[str], detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "catalog promotion package registry diff item ordinal", MAX_ITEMS)
        if self.ordinal == 0:
            raise ValidationError("catalog promotion package registry diff item ordinal must be positive")
        self.package_id = _label(package_id, "catalog promotion package registry diff item package ID")
        if change not in CHANGES:
            raise ValidationError("catalog promotion package registry diff item change is unsupported")
        self.change = change
        self.left_entry_address = None if left_entry_address is None else _address(left_entry_address, "catalog promotion package registry diff item left entry address", registry_model.ENTRY_PREFIX)
        self.right_entry_address = None if right_entry_address is None else _address(right_entry_address, "catalog promotion package registry diff item right entry address", registry_model.ENTRY_PREFIX)
        self.changed_fields = tuple(_label(field, "catalog promotion package registry diff changed field") for field in changed_fields)
        self.detail = _text(detail, "catalog promotion package registry diff item detail", MAX_TEXT)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.change == "added" and (self.left_entry_address is not None or self.right_entry_address is None):
            raise ValidationError("added registry diff item must only have a right entry")
        if self.change == "removed" and (self.left_entry_address is None or self.right_entry_address is not None):
            raise ValidationError("removed registry diff item must only have a left entry")
        if self.change == "changed" and (self.left_entry_address is None or self.right_entry_address is None or not self.changed_fields):
            raise ValidationError("changed registry diff item must have both entries and changed fields")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "catalog promotion package registry diff item content address")
        elif address_item(self) != self.content_address:
            raise ValidationError("catalog promotion package registry diff item content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("catalog promotion package registry diff item crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffItem:
        value = _mapping(value, "catalog promotion package registry diff item")
        _strict(value, set(cls.FIELDS), "catalog promotion package registry diff item")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"catalog promotion package registry diff item is missing fields: {missing}")
        return cls(*(value[field] for field in cls.FIELDS))


def address_item(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffItem) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffItem):
        raise ValidationError("catalog promotion package registry diff item address requires a typed item")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ITEM_PREFIX)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiff:
    """A content-addressed comparison of two package registries."""

    FIELDS = ("diff_id", "left_registry_address", "right_registry_address", "state", "left_entry_count", "right_entry_count", "entry_count_delta", "added_package_ids", "removed_package_ids", "changed_package_ids", "changed_fields", "items", "content_address")

    def __init__(self, diff_id: str, left_registry_address: str, right_registry_address: str, state: str, left_entry_count: int, right_entry_count: int, entry_count_delta: int, added_package_ids: Sequence[str], removed_package_ids: Sequence[str], changed_package_ids: Sequence[str], changed_fields: Sequence[str], items: Sequence[RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffItem], content_address: str) -> None:
        self.diff_id = _label(diff_id, "catalog promotion package registry diff ID")
        self.left_registry_address = _address(left_registry_address, "catalog promotion package registry diff left registry address", registry_model.REGISTRY_PREFIX)
        self.right_registry_address = _address(right_registry_address, "catalog promotion package registry diff right registry address", registry_model.REGISTRY_PREFIX)
        if state not in STATES:
            raise ValidationError("catalog promotion package registry diff state is unsupported")
        self.state = state
        self.left_entry_count = _count(left_entry_count, "catalog promotion package registry diff left entry count", registry_model.MAX_ENTRIES)
        self.right_entry_count = _count(right_entry_count, "catalog promotion package registry diff right entry count", registry_model.MAX_ENTRIES)
        if not isinstance(entry_count_delta, int) or isinstance(entry_count_delta, bool) or entry_count_delta != self.right_entry_count - self.left_entry_count:
            raise ValidationError("catalog promotion package registry diff entry count delta is not conserved")
        self.entry_count_delta = entry_count_delta
        self.added_package_ids = tuple(_label(package_id, "catalog promotion package registry diff added package ID") for package_id in added_package_ids)
        self.removed_package_ids = tuple(_label(package_id, "catalog promotion package registry diff removed package ID") for package_id in removed_package_ids)
        self.changed_package_ids = tuple(_label(package_id, "catalog promotion package registry diff changed package ID") for package_id in changed_package_ids)
        self.changed_fields = tuple(_label(field, "catalog promotion package registry diff changed field") for field in changed_fields)
        self.items = tuple(items)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if len(self.items) > MAX_ITEMS or any(not isinstance(item, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffItem) for item in self.items):
            raise ValidationError("catalog promotion package registry diff items are outside their bound")
        if tuple(item.ordinal for item in self.items) != tuple(range(1, len(self.items) + 1)):
            raise ValidationError("catalog promotion package registry diff item ordinals are not canonical")
        if self.state == "unchanged" and (self.items or self.added_package_ids or self.removed_package_ids or self.changed_package_ids or self.changed_fields):
            raise ValidationError("unchanged registry diff cannot contain changes")
        if self.state == "expanded" and self.entry_count_delta <= 0:
            raise ValidationError("expanded registry diff must increase entry count")
        if self.state == "contracted" and self.entry_count_delta >= 0:
            raise ValidationError("contracted registry diff must reduce entry count")
        if self.state == "changed" and self.entry_count_delta != 0 and not self.items:
            raise ValidationError("changed registry diff must contain items")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "catalog promotion package registry diff content address")
        elif address_diff(self) != self.content_address:
            raise ValidationError("catalog promotion package registry diff content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("catalog promotion package registry diff crosses the public boundary")

    @property
    def added_count(self) -> int:
        return len(self.added_package_ids)

    @property
    def removed_count(self) -> int:
        return len(self.removed_package_ids)

    @property
    def changed_count(self) -> int:
        return len(self.changed_package_ids)

    def to_dict(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "left_registry_address": self.left_registry_address, "right_registry_address": self.right_registry_address, "state": self.state, "left_entry_count": self.left_entry_count, "right_entry_count": self.right_entry_count, "entry_count_delta": self.entry_count_delta, "added_package_ids": self.added_package_ids, "removed_package_ids": self.removed_package_ids, "changed_package_ids": self.changed_package_ids, "changed_fields": self.changed_fields, "items": tuple(item.to_dict() for item in self.items), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "left_registry_address": self.left_registry_address, "right_registry_address": self.right_registry_address, "state": self.state, "left_entry_count": self.left_entry_count, "right_entry_count": self.right_entry_count, "entry_count_delta": self.entry_count_delta, "added_count": self.added_count, "removed_count": self.removed_count, "changed_count": self.changed_count, "changed_fields": self.changed_fields, "item_count": len(self.items), "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiff:
        value = _mapping(value, "catalog promotion package registry diff")
        _strict(value, set(cls.FIELDS), "catalog promotion package registry diff")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"catalog promotion package registry diff is missing fields: {missing}")
        tuples = {field: tuple(value[field]) if isinstance(value[field], list) else value[field] for field in ("added_package_ids", "removed_package_ids", "changed_package_ids", "changed_fields")}
        items = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffItem.from_mapping(item) for item in _sequence(value["items"], "catalog promotion package registry diff items", MAX_ITEMS))
        return cls(value["diff_id"], value["left_registry_address"], value["right_registry_address"], value["state"], value["left_entry_count"], value["right_entry_count"], value["entry_count_delta"], tuples["added_package_ids"], tuples["removed_package_ids"], tuples["changed_package_ids"], tuples["changed_fields"], items, value["content_address"])


def address_diff(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiff) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiff):
        raise ValidationError("catalog promotion package registry diff address requires a typed diff")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


def _changed_fields(left: registry_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryEntry, right: registry_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryEntry) -> tuple[str, ...]:
    return tuple(field for field in COMPARE_FIELDS if getattr(left, field) != getattr(right, field))


def _item(ordinal: int, package_id: str, change: str, left: registry_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryEntry | None, right: registry_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryEntry | None, fields: Sequence[str]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffItem:
    changed = tuple(fields)
    detail = {"added": "package is present only in the right registry", "removed": "package is present only in the left registry", "changed": "package receipt fields changed"}[change]
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffItem(ordinal, package_id, change, left.content_address if left else None, right.content_address if right else None, changed, detail, "pending:catalog-promotion-package-registry-diff-item")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffItem(ordinal, package_id, change, left.content_address if left else None, right.content_address if right else None, changed, detail, address_item(provisional))


def build_diff(left: registry_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry, right: registry_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistry, *, diff_id: str = DEFAULT_DIFF_ID) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiff:
    left = registry_model.verify_registry(left)
    right = registry_model.verify_registry(right)
    left_by_id = {entry.package_id: entry for entry in left.entries}
    right_by_id = {entry.package_id: entry for entry in right.entries}
    package_ids = tuple(sorted(set(left_by_id) | set(right_by_id)))
    added = tuple(package_id for package_id in package_ids if package_id not in left_by_id)
    removed = tuple(package_id for package_id in package_ids if package_id not in right_by_id)
    changed = tuple(package_id for package_id in package_ids if package_id in left_by_id and package_id in right_by_id and _changed_fields(left_by_id[package_id], right_by_id[package_id]))
    items = tuple(_item(ordinal, package_id, "added", None, right_by_id[package_id], ()) if package_id in added else _item(ordinal, package_id, "removed", left_by_id[package_id], None, ()) if package_id in removed else _item(ordinal, package_id, "changed", left_by_id[package_id], right_by_id[package_id], _changed_fields(left_by_id[package_id], right_by_id[package_id])) for ordinal, package_id in enumerate((*added, *removed, *changed), 1))
    fields = tuple(sorted({field for item in items for field in item.changed_fields}))
    entry_delta = right.entry_count - left.entry_count
    state = "unchanged" if not items else "expanded" if entry_delta > 0 and not changed else "contracted" if entry_delta < 0 and not changed else "changed"
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiff(_label(diff_id, "catalog promotion package registry diff ID"), left.content_address, right.content_address, state, left.entry_count, right.entry_count, entry_delta, added, removed, changed, fields, items, "pending:catalog-promotion-package-registry-diff")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiff(provisional.diff_id, provisional.left_registry_address, provisional.right_registry_address, provisional.state, provisional.left_entry_count, provisional.right_entry_count, provisional.entry_count_delta, provisional.added_package_ids, provisional.removed_package_ids, provisional.changed_package_ids, provisional.changed_fields, provisional.items, address_diff(provisional))


def diff_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiff:
    return verify_diff(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiff.from_mapping(value))


def verify_diff(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiff) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiff:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiff):
        raise ValidationError("catalog promotion package registry diff verification requires a typed diff")
    value._validate()
    if address_diff(value) != value.content_address:
        raise ValidationError("catalog promotion package registry diff content address does not replay")
    return value


def diff_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiff) -> str:
    return canonical_json(verify_diff(value).to_dict())


def diff_csv(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiff) -> str:
    value = verify_diff(value)
    fields = ("ordinal", "package_id", "change", "left_entry_address", "right_entry_address", "changed_fields", "detail", "content_address")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.items:
        row = item.to_dict()
        row["changed_fields"] = canonical_json(row["changed_fields"])
        writer.writerow(row)
    return output.getvalue()


def render_diff_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiff) -> str:
    value = verify_diff(value)
    summary = value.summary()
    lines = ["# Catalog Promotion Package Registry Diff", "", f"- Diff: `{summary['diff_id']}`", f"- State: `{summary['state']}`", f"- Entries: `{summary['left_entry_count']}` → `{summary['right_entry_count']}`", f"- Added: `{summary['added_count']}`", f"- Removed: `{summary['removed_count']}`", f"- Changed: `{summary['changed_count']}`", f"- Content address: `{summary['content_address']}`", "", "| ordinal | package | change | changed fields | detail |", "| ---: | --- | --- | --- | --- |"]
    for item in value.items:
        detail = item.detail.replace("|", "\\|")
        lines.append(f"| {item.ordinal} | `{item.package_id}` | `{item.change}` | `{', '.join(item.changed_fields)}` | {detail} |")
    if not value.items:
        lines.append("| — | — | unchanged | — | No package receipt changed. |")
    return "\n".join(lines) + "\n"


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffAuditCheck:
    FIELDS = ("ordinal", "check_id", "passed", "severity", "detail", "evidence_address", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, severity: str, detail: str, evidence_address: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "catalog promotion package registry diff audit check ordinal", len(CHECK_IDS))
        if self.ordinal == 0 or check_id not in CHECK_IDS:
            raise ValidationError("catalog promotion package registry diff audit check identity is invalid")
        self.check_id = check_id
        if not isinstance(passed, bool):
            raise ValidationError("catalog promotion package registry diff audit check passed must be boolean")
        self.passed = passed
        self.severity = _text(severity, "catalog promotion package registry diff audit check severity", 32)
        self.detail = _text(detail, "catalog promotion package registry diff audit check detail", MAX_TEXT)
        self.evidence_address = _address(evidence_address, "catalog promotion package registry diff audit evidence address", DIFF_PREFIX)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "catalog promotion package registry diff audit check content address")
        elif address_check(self) != self.content_address:
            raise ValidationError("catalog promotion package registry diff audit check content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("catalog promotion package registry diff audit check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffAuditCheck:
        value = _mapping(value, "catalog promotion package registry diff audit check")
        _strict(value, set(cls.FIELDS), "catalog promotion package registry diff audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffAuditCheck) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffAuditCheck):
        raise ValidationError("catalog promotion package registry diff audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX + "-check")


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffAudit:
    FIELDS = ("diff_address", "state", "accepted", "check_count", "passed_count", "failed_count", "failed_check_ids", "checks", "content_address")

    def __init__(self, diff_address: str, state: str, accepted: bool, checks: Sequence[RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffAuditCheck], content_address: str) -> None:
        self.diff_address = _address(diff_address, "catalog promotion package registry diff audit diff address", DIFF_PREFIX)
        if state not in ("complete", "incomplete") or not isinstance(accepted, bool):
            raise ValidationError("catalog promotion package registry diff audit status is invalid")
        self.state = state
        self.accepted = accepted
        self.checks = tuple(checks)
        if len(self.checks) != len(CHECK_IDS):
            raise ValidationError("catalog promotion package registry diff audit check count is invalid")
        self.content_address = content_address
        self._validate()

    @property
    def check_count(self) -> int:
        return len(self.checks)

    @property
    def passed_count(self) -> int:
        return sum(check.passed for check in self.checks)

    @property
    def failed_count(self) -> int:
        return self.check_count - self.passed_count

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    def _validate(self) -> None:
        if tuple(check.ordinal for check in self.checks) != tuple(range(1, len(CHECK_IDS) + 1)) or tuple(check.check_id for check in self.checks) != CHECK_IDS or self.accepted != (self.failed_count == 0) or self.state != ("complete" if self.accepted else "incomplete"):
            raise ValidationError("catalog promotion package registry diff audit checks are not conserved")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "catalog promotion package registry diff audit content address")
        elif address_audit(self) != self.content_address:
            raise ValidationError("catalog promotion package registry diff audit content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("catalog promotion package registry diff audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_address": self.diff_address, "state": self.state, "accepted": self.accepted, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "failed_check_ids": self.failed_check_ids, "checks": tuple(check.to_dict() for check in self.checks), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffAudit:
        value = _mapping(value, "catalog promotion package registry diff audit")
        _strict(value, set(cls.FIELDS), "catalog promotion package registry diff audit")
        checks = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "catalog promotion package registry diff audit checks", len(CHECK_IDS)))
        return cls(value["diff_address"], value["state"], value["accepted"], checks, value["content_address"])


def address_audit(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffAudit) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffAudit):
        raise ValidationError("catalog promotion package registry diff audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _audit_check(ordinal: int, check_id: str, passed: bool, detail: str, evidence_address: str) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffAuditCheck:
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffAuditCheck(ordinal, check_id, passed, "blocking" if not passed else "informational", detail, evidence_address, "pending:catalog-promotion-package-registry-diff-audit-check")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffAuditCheck(ordinal, check_id, passed, provisional.severity, detail, evidence_address, address_check(provisional))


def audit_diff(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiff) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffAudit:
    value = verify_diff(value)
    checks = (
        _audit_check(1, "exact-fields", set(value.to_dict()) == set(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiff.FIELDS), "registry diff exposes exactly its declared fields", value.content_address),
        _audit_check(2, "public-boundary", _public(value.to_dict()), "registry diff contains no private transport metadata", value.content_address),
        _audit_check(3, "input-addresses", value.left_registry_address != value.right_registry_address or value.state == "unchanged", "registry input addresses identify both sides", value.content_address),
        _audit_check(4, "state-conservation", (value.state == "unchanged" and not value.items) or (value.state != "unchanged" and bool(value.items)), "diff state agrees with item presence", value.content_address),
        _audit_check(5, "entry-count-conservation", value.entry_count_delta == value.right_entry_count - value.left_entry_count, "entry count delta is conserved", value.content_address),
        _audit_check(6, "item-conservation", len(value.items) == value.added_count + value.removed_count + value.changed_count, "item count is conserved across change classes", value.content_address),
        _audit_check(7, "field-conservation", value.changed_fields == tuple(sorted({field for item in value.items for field in item.changed_fields})), "changed field inventory is conserved", value.content_address),
        _audit_check(8, "item-addresses", all(address_item(item) == item.content_address for item in value.items), "every diff item address replays", value.content_address),
        _audit_check(9, "content-address", address_diff(value) == value.content_address, "registry diff content address replays", value.content_address),
        _audit_check(10, "mapping-round-trip", diff_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "registry diff mapping round trip is stable", value.content_address),
        _audit_check(11, "path-free", _public(value.to_dict()), "registry diff remains path-free", value.content_address),
    )
    accepted = all(check.passed for check in checks)
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffAudit(value.content_address, "complete" if accepted else "incomplete", accepted, checks, "pending:catalog-promotion-package-registry-diff-audit")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffAudit(value.content_address, provisional.state, accepted, checks, address_audit(provisional))


def verify_audit(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffAudit) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffAudit:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffAudit):
        raise ValidationError("catalog promotion package registry diff audit verification requires a typed audit")
    value._validate()
    if address_audit(value) != value.content_address:
        raise ValidationError("catalog promotion package registry diff audit content address does not replay")
    return value


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffAudit:
    return verify_audit(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffAudit.from_mapping(value))


def audit_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def render_audit_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffAudit) -> str:
    value = verify_audit(value)
    lines = ["# Catalog Promotion Package Registry Diff Audit", "", f"- State: `{value.state}`", f"- Accepted: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}` passed", f"- Diff: `{value.diff_address}`", f"- Content address: `{value.content_address}`", "", "| ordinal | check | passed | severity | detail |", "| ---: | --- | --- | --- | --- |"]
    for check in value.checks:
        detail = check.detail.replace("|", "\\|")
        lines.append(f"| {check.ordinal} | `{check.check_id}` | `{check.passed}` | `{check.severity}` | {detail} |")
    return "\n".join(lines) + "\n"


def item_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffItem.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_ITEMS}, "package_id": {"type": "string"}, "change": {"type": "string", "enum": list(CHANGES)}, "left_entry_address": {"type": ["string", "null"]}, "right_entry_address": {"type": ["string", "null"]}, "changed_fields": {"type": "array", "items": {"type": "string"}}, "detail": {"type": "string", "maxLength": MAX_TEXT}, "content_address": {"type": "string", "pattern": "^" + ITEM_PREFIX + ":"}}}


def diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiff.FIELDS), "properties": {"diff_id": {"type": "string"}, "left_registry_address": {"type": "string"}, "right_registry_address": {"type": "string"}, "state": {"type": "string", "enum": list(STATES)}, "left_entry_count": {"type": "integer"}, "right_entry_count": {"type": "integer"}, "entry_count_delta": {"type": "integer"}, "added_package_ids": {"type": "array"}, "removed_package_ids": {"type": "array"}, "changed_package_ids": {"type": "array"}, "changed_fields": {"type": "array"}, "items": {"type": "array", "maxItems": MAX_ITEMS, "items": item_schema()}, "content_address": {"type": "string", "pattern": "^" + DIFF_PREFIX + ":"}}}


def audit_check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffAuditCheck.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": len(CHECK_IDS)}, "check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "severity": {"type": "string"}, "detail": {"type": "string"}, "evidence_address": {"type": "string"}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffAudit.FIELDS), "properties": {"diff_address": {"type": "string"}, "state": {"type": "string", "enum": ["complete", "incomplete"]}, "accepted": {"type": "boolean"}, "check_count": {"type": "integer", "const": len(CHECK_IDS)}, "passed_count": {"type": "integer"}, "failed_count": {"type": "integer"}, "failed_check_ids": {"type": "array"}, "checks": {"type": "array", "minItems": len(CHECK_IDS), "maxItems": len(CHECK_IDS)}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "diff_prefix": DIFF_PREFIX, "item_prefix": ITEM_PREFIX, "audit_prefix": AUDIT_PREFIX, "states": STATES, "changes": CHANGES, "compare_fields": COMPARE_FIELDS, "check_ids": CHECK_IDS, "limits": {"max_items": MAX_ITEMS}, "features": ("registry evolution comparison", "added removed changed package receipts", "changed field inventory", "content-addressed diff items", "independent diff audit", "JSON CSV and Markdown exports", "path-free public projection"), "schemas": ("item", "diff", "audit-check", "audit")}


__all__ = [
    "AUDIT_PREFIX", "BOUNDARY", "CHANGES", "CHECK_IDS", "COMPARE_FIELDS", "DEFAULT_DIFF_ID", "DIFF_PREFIX", "ITEM_PREFIX", "MAX_ITEMS", "MAX_TEXT", "STATES", "VERSION",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiff", "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffAudit", "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffAuditCheck", "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRegistryDiffItem",
    "address_audit", "address_check", "address_diff", "address_item", "audit_check_schema", "audit_from_mapping", "audit_json", "audit_schema", "audit_diff", "capabilities", "diff_csv", "diff_from_mapping", "diff_json", "diff_schema", "item_schema", "render_audit_markdown", "render_diff_markdown", "verify_audit", "verify_diff", "build_diff",
]
