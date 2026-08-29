"""Independent integrity assurance for persisted promotion-package diffs."""

from __future__ import annotations

# ruff: noqa: E501, I001

from collections.abc import Mapping
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package as package_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = diff_model.VERSION + "-audit-v1"
BOUNDARY = diff_model.BOUNDARY + "_audit"
AUDIT_PREFIX = diff_model.DIFF_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
STATES = ("complete", "incomplete")
CHECK_IDS = ("exact-fields", "public-boundary", "input-addresses", "state-conservation", "action-count-conservation", "changed-field-conservation", "action-set-conservation", "item-addresses", "content-address", "mapping-round-trip", "decision-transition", "path-free")
MAX_CHECKS = len(CHECK_IDS)
MAX_TEXT = 4096


def _text(value: Any, field: str, maximum: int = 1024) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
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


def _sequence(value: Any, field: str) -> tuple[Any, ...]:
    if not isinstance(value, (list, tuple)) or len(value) > MAX_CHECKS:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    return package_model._public(value)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAuditCheck:
    """One independent persisted-package diff assertion."""

    FIELDS = ("check_id", "passed", "detail", "evidence_address", "content_address")

    def __init__(self, check_id: str, passed: bool, detail: str, evidence_address: str, content_address: str) -> None:
        self.check_id = _text(check_id, "observability bundle catalog promotion package diff audit check ID", 128)
        if self.check_id not in CHECK_IDS:
            raise ValidationError("observability bundle catalog promotion package diff audit check ID is unsupported")
        if not isinstance(passed, bool):
            raise ValidationError("observability bundle catalog promotion package diff audit passed flag must be boolean")
        self.passed = passed
        self.detail = _text(detail, "observability bundle catalog promotion package diff audit check detail", MAX_TEXT)
        self.evidence_address = _address(evidence_address, "observability bundle catalog promotion package diff audit evidence address")
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "observability bundle catalog promotion package diff audit check content address")
        else:
            _address(self.content_address, "observability bundle catalog promotion package diff audit check content address", CHECK_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_check(self) != self.content_address):
            raise ValidationError("observability bundle catalog promotion package diff audit check is not public or addressed")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAuditCheck:
        value = _mapping(value, "observability bundle catalog promotion package diff audit check")
        _strict(value, set(cls.FIELDS), "observability bundle catalog promotion package diff audit check")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog promotion package diff audit check is missing fields: {missing}")
        return cls(value["check_id"], value["passed"], value["detail"], value["evidence_address"], value["content_address"])


def address_check(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAuditCheck) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAuditCheck):
        raise ValidationError("observability bundle catalog promotion package diff audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAudit:
    """A fixed twelve-check audit over a persisted-package evolution diff."""

    FIELDS = ("diff_address", "state", "complete", "accepted", "check_count", "passed_count", "failed_count", "checks", "content_address")

    def __init__(self, diff_address: str, state: str, complete: bool, accepted: bool, check_count: int, passed_count: int, failed_count: int, checks: tuple[RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAuditCheck, ...], content_address: str) -> None:
        self.diff_address = _address(diff_address, "observability bundle catalog promotion package diff audit diff address", diff_model.DIFF_PREFIX)
        if state not in STATES:
            raise ValidationError("observability bundle catalog promotion package diff audit state is unsupported")
        self.state = state
        if not isinstance(complete, bool) or not isinstance(accepted, bool):
            raise ValidationError("observability bundle catalog promotion package diff audit flags must be boolean")
        self.complete = complete
        self.accepted = accepted
        self.check_count = _count(check_count, "observability bundle catalog promotion package diff audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "observability bundle catalog promotion package diff audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "observability bundle catalog promotion package diff audit failed count", MAX_CHECKS)
        if len(checks) != self.check_count:
            raise ValidationError("observability bundle catalog promotion package diff audit check count does not match checks")
        self.checks = tuple(checks)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.check_count != MAX_CHECKS or self.passed_count + self.failed_count != self.check_count or tuple(check.check_id for check in self.checks) != CHECK_IDS or any(not isinstance(check, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAuditCheck) for check in self.checks):
            raise ValidationError("observability bundle catalog promotion package diff audit checks are not conserved")
        expected_complete = self.failed_count == 0
        if self.complete != expected_complete or self.state != ("complete" if expected_complete else "incomplete") or self.accepted != expected_complete:
            raise ValidationError("observability bundle catalog promotion package diff audit state is not derived")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "observability bundle catalog promotion package diff audit content address")
        else:
            _address(self.content_address, "observability bundle catalog promotion package diff audit content address", AUDIT_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_audit(self) != self.content_address):
            raise ValidationError("observability bundle catalog promotion package diff audit is not public or addressed")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) if field != "checks" else tuple(check.to_dict() for check in self.checks) for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAudit:
        value = _mapping(value, "observability bundle catalog promotion package diff audit")
        _strict(value, set(cls.FIELDS), "observability bundle catalog promotion package diff audit")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog promotion package diff audit is missing fields: {missing}")
        checks = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "observability bundle catalog promotion package diff audit checks"))
        return cls(value["diff_address"], value["state"], value["complete"], value["accepted"], value["check_count"], value["passed_count"], value["failed_count"], checks, value["content_address"])


def address_audit(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAudit) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAudit):
        raise ValidationError("observability bundle catalog promotion package diff audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, detail: str, evidence_address: str) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAuditCheck:
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAuditCheck(check_id, passed, detail, evidence_address, "pending:observability-bundle-catalog-promotion-package-diff-audit-check")


def _action_ids(value: diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiff, field: str) -> tuple[str, ...]:
    return tuple(getattr(value, field))


def _diff_checks(value: diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiff) -> tuple[RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAuditCheck, ...]:
    item_fields = tuple(item.field for item in value.items)
    checks = (
        _check("exact-fields", set(value.to_dict()) == set(diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiff.FIELDS), "diff projection exposes exactly its declared fields", value.content_address),
        _check("public-boundary", _public(value.to_dict()), "diff projection is public and path-free", value.content_address),
        _check("input-addresses", value.left_package_address.startswith(package_model.PACKAGE_PREFIX + ":") and value.right_package_address.startswith(package_model.PACKAGE_PREFIX + ":") and value.left_packet_address.startswith(package_model.packet_model.PACKET_PREFIX + ":") and value.right_packet_address.startswith(package_model.packet_model.PACKET_PREFIX + ":"), "both diff inputs use public package and packet addresses", value.left_package_address),
        _check("state-conservation", value.state == ("unchanged" if not value.changed_fields else "changed"), "diff state is derived from changed fields", value.content_address),
        _check("action-count-conservation", value.action_count_delta == value.right_action_count - value.left_action_count, "action count delta is conserved", value.content_address),
        _check("changed-field-conservation", item_fields == value.changed_fields and len(value.items) == len(value.changed_fields), "changed fields and addressed items are conserved", value.content_address),
        _check("action-set-conservation", not (set(value.action_added_ids) & set(value.action_removed_ids)) and not (set(value.action_added_ids) & set(value.action_changed_ids)) and not (set(value.action_removed_ids) & set(value.action_changed_ids)), "added, removed, and changed action sets are disjoint", value.content_address),
        _check("item-addresses", all(diff_model.address_item(item) == item.content_address for item in value.items), "all changed item addresses replay", value.content_address),
        _check("content-address", diff_model.address_diff(value) == value.content_address, "diff content address replays", value.content_address),
        _check("mapping-round-trip", diff_model.diff_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "diff mapping round trip is stable", value.content_address),
        _check("decision-transition", isinstance(value.left_decision, str) and isinstance(value.right_decision, str), "decision transition labels are present", value.content_address),
        _check("path-free", _public(value.to_dict()), "diff evidence contains no local source path", value.content_address),
    )
    return tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAuditCheck(check.check_id, check.passed, check.detail, check.evidence_address, address_check(check)) for check in checks)


def audit_diff(value: diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiff) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAudit:
    if not isinstance(value, diff_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiff):
        raise ValidationError("observability bundle catalog promotion package diff audit requires a typed diff")
    diff_model.verify_diff(value)
    checks = _diff_checks(value)
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAudit(value.content_address, "complete", True, True, MAX_CHECKS, sum(check.passed for check in checks), sum(not check.passed for check in checks), checks, "pending:observability-bundle-catalog-promotion-package-diff-audit")
    state = "complete" if provisional.failed_count == 0 else "incomplete"
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAudit(value.content_address, state, state == "complete", state == "complete", MAX_CHECKS, provisional.passed_count, provisional.failed_count, checks, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAudit:
    try:
        return audit_diff(diff_model.diff_from_mapping(_mapping(value, "observability bundle catalog promotion package diff")))
    except (TypeError, ValueError, ValidationError) as error:
        fallback = diff_model.DIFF_PREFIX + ":invalid"
        checks = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAuditCheck(check_id, False, "diff mapping could not be verified: " + str(error)[:MAX_TEXT - 48], fallback, "pending:observability-bundle-catalog-promotion-package-diff-audit-check") for check_id in CHECK_IDS)
        addressed = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAuditCheck(check.check_id, check.passed, check.detail, check.evidence_address, address_check(check)) for check in checks)
        provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAudit(fallback, "incomplete", False, False, MAX_CHECKS, 0, MAX_CHECKS, addressed, "pending:observability-bundle-catalog-promotion-package-diff-audit")
        return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAudit(fallback, "incomplete", False, False, MAX_CHECKS, 0, MAX_CHECKS, addressed, address_audit(provisional))


def verify_audit(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAudit) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAudit:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAudit):
        raise ValidationError("observability bundle catalog promotion package diff audit verification requires a typed audit")
    value._validate()
    if address_audit(value) != value.content_address:
        raise ValidationError("observability bundle catalog promotion package diff audit content address does not replay")
    return value


def audit_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def render_audit_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAudit) -> str:
    value = verify_audit(value)
    lines = ["# Assurance History Observatory Catalog Promotion Package Diff Audit", "", f"- State: `{value.state}`", f"- Accepted: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}` passed", f"- Diff: `{value.diff_address}`", f"- Content address: `{value.content_address}`", "", "| check | passed | detail | evidence |", "| --- | --- | --- | --- |"]
    lines.extend(f"| `{check.check_id}` | {check.passed} | {check.detail} | `{check.evidence_address}` |" for check in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAuditCheck.FIELDS), "properties": {"check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string", "minLength": 1, "maxLength": MAX_TEXT}, "evidence_address": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAudit.FIELDS), "properties": {"diff_address": {"type": "string", "pattern": "^" + diff_model.DIFF_PREFIX + ":"}, "state": {"type": "string", "enum": list(STATES)}, "complete": {"type": "boolean"}, "accepted": {"type": "boolean"}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS, "items": check_schema()}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "states": STATES, "check_ids": CHECK_IDS, "limits": {"max_checks": MAX_CHECKS}, "features": ("fixed persisted-package diff assurance", "state and action-set conservation", "field-level item replay", "content-address replay", "mapping round-trip assurance", "malformed mapping diagnostics", "path-free JSON and Markdown output"), "schemas": ("check", "audit")}


__all__ = [
    "AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "STATES", "VERSION",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAuditCheck", "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageDiffAudit",
    "address_audit", "address_check", "audit_diff", "audit_from_mapping", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit",
]
