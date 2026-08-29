"""Independent assurance checks for durable promotion release packages."""

from __future__ import annotations

# ruff: noqa: E501, I001

from collections.abc import Mapping
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate as gate_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_audit as gate_audit_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet as packet_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package as package_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = package_model.VERSION + "-audit-v1"
BOUNDARY = package_model.BOUNDARY + "_audit"
AUDIT_PREFIX = package_model.PACKAGE_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
STATES = ("complete", "incomplete")
CHECK_IDS = ("exact-fields", "public-boundary", "manifest-address", "artifact-conservation", "artifact-byte-addresses", "gate-replay", "gate-audit-replay", "packet-replay", "linkage", "actions-replay", "package-address", "mapping-round-trip")
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


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAuditCheck:
    """One independent package integrity assertion."""

    FIELDS = ("check_id", "passed", "detail", "evidence_address", "content_address")

    def __init__(self, check_id: str, passed: bool, detail: str, evidence_address: str, content_address: str) -> None:
        self.check_id = _text(check_id, "observability bundle catalog promotion package audit check ID", 128)
        if self.check_id not in CHECK_IDS:
            raise ValidationError("observability bundle catalog promotion package audit check ID is unsupported")
        if not isinstance(passed, bool):
            raise ValidationError("observability bundle catalog promotion package audit passed flag must be boolean")
        self.passed = passed
        self.detail = _text(detail, "observability bundle catalog promotion package audit check detail", MAX_TEXT)
        self.evidence_address = _address(evidence_address, "observability bundle catalog promotion package audit evidence address")
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "observability bundle catalog promotion package audit check content address")
        else:
            _address(self.content_address, "observability bundle catalog promotion package audit check content address", CHECK_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_check(self) != self.content_address):
            raise ValidationError("observability bundle catalog promotion package audit check is not public or addressed")

    def to_dict(self) -> dict[str, Any]:
        return {"check_id": self.check_id, "passed": self.passed, "detail": self.detail, "evidence_address": self.evidence_address, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAuditCheck:
        value = _mapping(value, "observability bundle catalog promotion package audit check")
        _strict(value, set(cls.FIELDS), "observability bundle catalog promotion package audit check")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog promotion package audit check is missing fields: {missing}")
        return cls(value["check_id"], value["passed"], value["detail"], value["evidence_address"], value["content_address"])


def address_check(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAuditCheck) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAuditCheck):
        raise ValidationError("observability bundle catalog promotion package audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAudit:
    """A fixed twelve-check package assurance result."""

    FIELDS = ("package_address", "manifest_address", "actions_address", "state", "complete", "accepted", "check_count", "passed_count", "failed_count", "checks", "content_address")

    def __init__(self, package_address: str, manifest_address: str, actions_address: str, state: str, complete: bool, accepted: bool, check_count: int, passed_count: int, failed_count: int, checks: tuple[RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAuditCheck, ...], content_address: str) -> None:
        self.package_address = _address(package_address, "observability bundle catalog promotion package audit package address", package_model.PACKAGE_PREFIX)
        self.manifest_address = _address(manifest_address, "observability bundle catalog promotion package audit manifest address", package_model.MANIFEST_PREFIX)
        self.actions_address = _address(actions_address, "observability bundle catalog promotion package audit actions address", package_model.ACTIONS_PREFIX)
        if state not in STATES:
            raise ValidationError("observability bundle catalog promotion package audit state is unsupported")
        self.state = state
        if not isinstance(complete, bool) or not isinstance(accepted, bool):
            raise ValidationError("observability bundle catalog promotion package audit flags must be boolean")
        self.complete = complete
        self.accepted = accepted
        self.check_count = _count(check_count, "observability bundle catalog promotion package audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "observability bundle catalog promotion package audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "observability bundle catalog promotion package audit failed count", MAX_CHECKS)
        if len(checks) != self.check_count:
            raise ValidationError("observability bundle catalog promotion package audit check count does not match checks")
        self.checks = tuple(checks)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.check_count != MAX_CHECKS or self.passed_count + self.failed_count != self.check_count or tuple(check.check_id for check in self.checks) != CHECK_IDS or any(not isinstance(check, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAuditCheck) for check in self.checks):
            raise ValidationError("observability bundle catalog promotion package audit checks are not conserved")
        expected_complete = self.failed_count == 0
        if self.complete != expected_complete or self.state != ("complete" if expected_complete else "incomplete") or self.accepted != expected_complete:
            raise ValidationError("observability bundle catalog promotion package audit state is not derived")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "observability bundle catalog promotion package audit content address")
        else:
            _address(self.content_address, "observability bundle catalog promotion package audit content address", AUDIT_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_audit(self) != self.content_address):
            raise ValidationError("observability bundle catalog promotion package audit is not public or addressed")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) if field != "checks" else tuple(check.to_dict() for check in self.checks) for field in self.FIELDS}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAudit:
        value = _mapping(value, "observability bundle catalog promotion package audit")
        _strict(value, set(cls.FIELDS), "observability bundle catalog promotion package audit")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog promotion package audit is missing fields: {missing}")
        checks = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "observability bundle catalog promotion package audit checks"))
        return cls(value["package_address"], value["manifest_address"], value["actions_address"], value["state"], value["complete"], value["accepted"], value["check_count"], value["passed_count"], value["failed_count"], checks, value["content_address"])


def address_audit(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAudit) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAudit):
        raise ValidationError("observability bundle catalog promotion package audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, detail: str, evidence_address: str) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAuditCheck:
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAuditCheck(check_id, passed, detail, evidence_address, "pending:observability-bundle-catalog-promotion-package-audit-check")


def _package_checks(value: package_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage) -> tuple[RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAuditCheck, ...]:
    payload = package_model.package_bytes(value)
    artifact_names = tuple(artifact["name"] for artifact in value.manifest["artifacts"])
    artifact_receipts = all(artifact == package_model._artifact(name, payload[name]) for artifact, name in zip(value.manifest["artifacts"], package_model.ARTIFACT_FILES, strict=True))
    checks = (
        _check("exact-fields", set(value.to_dict()) == set(package_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage.FIELDS), "package projection exposes exactly its declared fields" if set(value.to_dict()) == set(package_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage.FIELDS) else "package projection field set differs from its contract", value.content_address),
        _check("public-boundary", _public(value.to_dict()), "package projection contains no private path or agent metadata" if _public(value.to_dict()) else "package projection crosses the public boundary", value.content_address),
        _check("manifest-address", content_hash(value.manifest | {"manifest_address": None}, prefix=package_model.MANIFEST_PREFIX) == value.manifest_address, "manifest content address replays" if content_hash(value.manifest | {"manifest_address": None}, prefix=package_model.MANIFEST_PREFIX) == value.manifest_address else "manifest content address does not replay", value.manifest_address),
        _check("artifact-conservation", value.artifact_count == package_model.MAX_ARTIFACTS and tuple(value.manifest["files"]) == package_model.ARTIFACT_FILES and artifact_names == package_model.ARTIFACT_FILES, "manifest artifact inventory is conserved" if value.artifact_count == package_model.MAX_ARTIFACTS and tuple(value.manifest["files"]) == package_model.ARTIFACT_FILES and artifact_names == package_model.ARTIFACT_FILES else "manifest artifact inventory is not conserved", value.manifest_address),
        _check("artifact-byte-addresses", artifact_receipts, "all artifact byte receipts replay" if artifact_receipts else "one or more artifact byte receipts do not replay", value.manifest_address),
        _check("gate-replay", gate_model.address_gate(value.gate) == value.gate_address, "gate content address replays" if gate_model.address_gate(value.gate) == value.gate_address else "gate content address does not replay", value.gate_address),
        _check("gate-audit-replay", gate_audit_model.address_audit(value.gate_audit) == value.gate_audit_address, "gate-audit content address replays" if gate_audit_model.address_audit(value.gate_audit) == value.gate_audit_address else "gate-audit content address does not replay", value.gate_audit_address),
        _check("packet-replay", packet_model.address_packet(value.packet) == value.packet_address, "release packet content address replays" if packet_model.address_packet(value.packet) == value.packet_address else "release packet content address does not replay", value.packet_address),
        _check("linkage", value.gate_audit.gate_address == value.gate_address and value.packet.gate_address == value.gate_address and value.packet.gate_audit_address == value.gate_audit_address and value.actions_document["packet_address"] == value.packet_address, "nested package documents are linked" if value.gate_audit.gate_address == value.gate_address and value.packet.gate_address == value.gate_address and value.packet.gate_audit_address == value.gate_audit_address and value.actions_document["packet_address"] == value.packet_address else "nested package document linkage is inconsistent", value.content_address),
        _check("actions-replay", package_model.address_actions(value.actions_document) == value.actions_address and tuple(value.actions) == tuple(action.to_dict() for action in value.packet.actions), "action document address and rows replay" if package_model.address_actions(value.actions_document) == value.actions_address and tuple(value.actions) == tuple(action.to_dict() for action in value.packet.actions) else "action document address or rows do not replay", value.actions_address),
        _check("package-address", package_model.address_package(value) == value.content_address, "package content address replays" if package_model.address_package(value) == value.content_address else "package content address does not replay", value.content_address),
        _check("mapping-round-trip", package_model.package_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "package mapping round trip is stable", value.content_address),
    )
    addressed = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAuditCheck(check.check_id, check.passed, check.detail, check.evidence_address, address_check(check)) for check in checks)
    return addressed


def audit_package(value: package_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAudit:
    if not isinstance(value, package_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage):
        raise ValidationError("observability bundle catalog promotion package audit requires a typed package")
    package_model.verify_package(value)
    checks = _package_checks(value)
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAudit(value.content_address, value.manifest_address, value.actions_address, "complete", True, True, MAX_CHECKS, sum(check.passed for check in checks), sum(not check.passed for check in checks), checks, "pending:observability-bundle-catalog-promotion-package-audit")
    state = "complete" if provisional.failed_count == 0 else "incomplete"
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAudit(value.content_address, value.manifest_address, value.actions_address, state, state == "complete", state == "complete", MAX_CHECKS, provisional.passed_count, provisional.failed_count, checks, address_audit(provisional))


def _diagnostic(message: str) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAudit:
    package_address = package_model.PACKAGE_PREFIX + ":invalid"
    manifest_address = package_model.MANIFEST_PREFIX + ":invalid"
    actions_address = package_model.ACTIONS_PREFIX + ":invalid"
    checks = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAuditCheck(check_id, False, "package mapping could not be verified: " + message[:MAX_TEXT - 48], package_address, "pending:observability-bundle-catalog-promotion-package-audit-check") for check_id in CHECK_IDS)
    addressed = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAuditCheck(check.check_id, check.passed, check.detail, check.evidence_address, address_check(check)) for check in checks)
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAudit(package_address, manifest_address, actions_address, "incomplete", False, False, MAX_CHECKS, 0, MAX_CHECKS, addressed, "pending:observability-bundle-catalog-promotion-package-audit")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAudit(package_address, manifest_address, actions_address, "incomplete", False, False, MAX_CHECKS, 0, MAX_CHECKS, addressed, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAudit:
    try:
        return audit_package(package_model.package_from_mapping(_mapping(value, "observability bundle catalog promotion package")))
    except (TypeError, ValueError, ValidationError) as error:
        return _diagnostic(str(error))


def verify_audit(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAudit) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAudit:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAudit):
        raise ValidationError("observability bundle catalog promotion package audit verification requires a typed audit")
    value._validate()
    if address_audit(value) != value.content_address:
        raise ValidationError("observability bundle catalog promotion package audit content address does not replay")
    return value


def audit_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def render_audit_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAudit) -> str:
    value = verify_audit(value)
    lines = ["# Assurance History Observatory Catalog Promotion Package Audit", "", f"- State: `{value.state}`", f"- Accepted: `{value.accepted}`", f"- Checks: `{value.passed_count}/{value.check_count}` passed", f"- Package: `{value.package_address}`", f"- Content address: `{value.content_address}`", "", "| check | passed | detail | evidence |", "| --- | --- | --- | --- |"]
    lines.extend(f"| `{check.check_id}` | {check.passed} | {check.detail} | `{check.evidence_address}` |" for check in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAuditCheck.FIELDS), "properties": {"check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string", "minLength": 1, "maxLength": MAX_TEXT}, "evidence_address": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAudit.FIELDS), "properties": {"package_address": {"type": "string", "pattern": "^" + package_model.PACKAGE_PREFIX + ":"}, "manifest_address": {"type": "string", "pattern": "^" + package_model.MANIFEST_PREFIX + ":"}, "actions_address": {"type": "string", "pattern": "^" + package_model.ACTIONS_PREFIX + ":"}, "state": {"type": "string", "enum": list(STATES)}, "complete": {"type": "boolean"}, "accepted": {"type": "boolean"}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS, "items": check_schema()}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "states": STATES, "check_ids": CHECK_IDS, "limits": {"max_checks": MAX_CHECKS}, "features": ("fixed package integrity checks", "manifest and artifact receipt replay", "nested gate audit packet replay", "linkage conservation", "mapping round-trip assurance", "failure-visible malformed mapping diagnostics", "path-free JSON and Markdown output"), "schemas": ("check", "audit")}


__all__ = [
    "AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "STATES", "VERSION",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAuditCheck", "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAudit",
    "address_audit", "address_check", "audit_from_mapping", "audit_json", "audit_package", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit",
]
