"""Independent assurance checks for observability-bundle catalog reports."""

from __future__ import annotations

# ruff: noqa: E501, I001

from collections.abc import Mapping, Sequence
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_report as report_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = report_model.VERSION + "-audit-v1"
BOUNDARY = report_model.BOUNDARY + "_audit"
AUDIT_PREFIX = report_model.REPORT_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
STATES = ("complete", "incomplete")
CHECK_IDS = (
    "exact-fields",
    "public-boundary",
    "catalog-address",
    "row-conservation",
    "denominator-conservation",
    "ratio-conservation",
    "artifact-conservation",
    "state-distributions",
    "label-partitions",
    "row-addresses",
    "content-address",
    "mapping-round-trip",
)
MAX_CHECKS = len(CHECK_IDS)
EXPECTED_FIELDS = report_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReport.FIELDS


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if ":" not in value or value.startswith(("/", "\\")) or "\\" in value:
        raise ValidationError(f"{field} has an invalid public namespace")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an invalid public namespace")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be a mapping")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    return report_model._public(value)


def _safe_address(value: Any, prefix: str, fallback: str) -> str:
    try:
        return _address(value, "audit evidence address", prefix)
    except (ValidationError, TypeError, ValueError):
        return fallback


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditCheck:
    """One fixed report invariant with an addressed evidence receipt."""

    FIELDS = ("check_id", "passed", "detail", "evidence_address", "content_address")

    def __init__(self, check_id: str, passed: bool, detail: str, evidence_address: str, content_address: str) -> None:
        self.check_id = _text(check_id, "observability bundle catalog report audit check ID", 64)
        self.passed = _bool(passed, "observability bundle catalog report audit check passed")
        self.detail = _text(detail, "observability bundle catalog report audit check detail", 1024)
        self.evidence_address = _text(evidence_address, "observability bundle catalog report audit evidence address", 2048)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS:
            raise ValidationError("observability bundle catalog report audit check ID is unsupported")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "observability bundle catalog report audit check content address")
        else:
            _address(self.content_address, "observability bundle catalog report audit check content address", CHECK_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_check(self) != self.content_address):
            raise ValidationError("observability bundle catalog report audit check address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"check_id": self.check_id, "passed": self.passed, "detail": self.detail, "evidence_address": self.evidence_address, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditCheck:
        value = _mapping(value, "observability bundle catalog report audit check")
        _strict(value, set(cls.FIELDS), "observability bundle catalog report audit check")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog report audit check is missing fields: {missing}")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditCheck) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditCheck):
        raise ValidationError("observability bundle catalog report audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAudit:
    """Addressed independent report assurance with failure-visible checks."""

    FIELDS = ("report_address", "catalog_address", "state", "complete", "accepted", "check_count", "passed_count", "failed_count", "checks", "content_address")

    def __init__(self, report_address: str, catalog_address: str, state: str, complete: bool, accepted: bool, checks: Sequence[RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditCheck], content_address: str) -> None:
        self.report_address = _address(report_address, "observability bundle catalog report audit report address", report_model.REPORT_PREFIX)
        self.catalog_address = _address(catalog_address, "observability bundle catalog report audit catalog address", report_model.catalog_model.CATALOG_PREFIX)
        self.state = _text(state, "observability bundle catalog report audit state", 32)
        self.complete = _bool(complete, "observability bundle catalog report audit complete")
        self.accepted = _bool(accepted, "observability bundle catalog report audit accepted")
        self.checks = tuple(checks)
        self.check_count = len(self.checks)
        self.passed_count = sum(check.passed for check in self.checks)
        self.failed_count = self.check_count - self.passed_count
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if tuple(check.check_id for check in self.checks) != CHECK_IDS or any(not isinstance(check, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditCheck) for check in self.checks):
            raise ValidationError("observability bundle catalog report audit checks are not canonical")
        if self.check_count != MAX_CHECKS or self.passed_count + self.failed_count != MAX_CHECKS:
            raise ValidationError("observability bundle catalog report audit check counts are not conserved")
        if self.state not in STATES or self.complete != (self.failed_count == 0) or self.accepted != self.complete:
            raise ValidationError("observability bundle catalog report audit state is not derived")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "observability bundle catalog report audit content address")
        else:
            _address(self.content_address, "observability bundle catalog report audit content address", AUDIT_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_audit(self) != self.content_address):
            raise ValidationError("observability bundle catalog report audit address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"report_address": self.report_address, "catalog_address": self.catalog_address, "state": self.state, "complete": self.complete, "accepted": self.accepted, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "checks": tuple(check.to_dict() for check in self.checks), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in self.FIELDS if key != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAudit:
        value = _mapping(value, "observability bundle catalog report audit")
        _strict(value, set(cls.FIELDS), "observability bundle catalog report audit")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"observability bundle catalog report audit is missing fields: {missing}")
        checks = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "observability bundle catalog report audit checks", MAX_CHECKS))
        result = cls(value["report_address"], value["catalog_address"], value["state"], value["complete"], value["accepted"], checks, value["content_address"])
        if result.check_count != value["check_count"] or result.passed_count != value["passed_count"] or result.failed_count != value["failed_count"]:
            raise ValidationError("observability bundle catalog report audit counts do not reconcile")
        return result


def address_audit(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAudit) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAudit):
        raise ValidationError("observability bundle catalog report audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, detail: str, evidence_address: str) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditCheck:
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditCheck(check_id, passed, detail, evidence_address, "pending:observability-bundle-catalog-report-audit-check")


def _typed(document: Mapping[str, Any]) -> report_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReport | None:
    try:
        return report_model.report_from_mapping(document)
    except (ValidationError, KeyError, TypeError, ValueError):
        return None


def _audit_mapping(document: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAudit:
    fallback_report = report_model.REPORT_PREFIX + ":unresolved"
    fallback_catalog = report_model.catalog_model.CATALOG_PREFIX + ":unresolved"
    report_address = _safe_address(document.get("content_address"), report_model.REPORT_PREFIX, fallback_report)
    catalog_address = _safe_address(document.get("catalog_address"), report_model.catalog_model.CATALOG_PREFIX, fallback_catalog)
    typed = _typed(document)
    if typed is not None:
        report_address, catalog_address = typed.content_address, typed.catalog_address
    exact_fields = set(document) == set(EXPECTED_FIELDS)
    public_boundary = _public(document)
    catalog_address_check = False
    try:
        _address(document.get("catalog_address"), "catalog address", report_model.catalog_model.CATALOG_PREFIX)
        catalog_address_check = True
    except (ValidationError, TypeError, ValueError):
        pass
    row_conservation = denominator_conservation = ratio_conservation = artifact_conservation = state_distributions = label_partitions = row_addresses = content_address = mapping_round_trip = False
    if typed is not None:
        rows = typed.rows
        row_conservation = typed.entry_count == len(rows) and tuple(row.ordinal for row in rows) == tuple(range(1, typed.entry_count + 1)) and tuple(row.label for row in rows) == tuple(sorted(row.label for row in rows))
        denominator_conservation = typed.entry_count == typed.accepted_count + typed.rejected_count and typed.ready_count <= typed.accepted_count
        ratio_conservation = typed.acceptance_basis_points == report_model._basis_points(typed.accepted_count, typed.entry_count) and typed.readiness_basis_points == report_model._basis_points(typed.ready_count, typed.entry_count)
        artifact_conservation = typed.artifact_count == typed.entry_count * len(report_model.catalog_model.bundle_model.ARTIFACT_FILES) and typed.artifact_count_per_entry == (len(report_model.catalog_model.bundle_model.ARTIFACT_FILES) if typed.entry_count else 0)
        state_distributions = typed.entry_state_counts == report_model._distribution(tuple(row.state for row in rows), report_model.ENTRY_STATES, "entry states") and typed.pipeline_state_counts == report_model._distribution(tuple(row.pipeline_state for row in rows), report_model.PIPELINE_STATES, "pipeline states") and typed.observability_state_counts == report_model._distribution(tuple(row.observability_state for row in rows), report_model.OBSERVABILITY_STATES, "observability states") and typed.audit_state_counts == report_model._distribution(tuple(row.audit_state for row in rows), report_model.AUDIT_STATES, "audit states")
        label_partitions = typed.accepted_labels == tuple(sorted(row.label for row in rows if row.accepted)) and typed.ready_labels == tuple(sorted(row.label for row in rows if row.state == "ready")) and typed.rejected_labels == tuple(sorted(row.label for row in rows if not row.accepted))
        row_addresses = all(report_model.address_row(row) == row.content_address for row in rows)
        content_address = report_model.address_report(typed) == typed.content_address
        try:
            mapping_round_trip = report_model.report_from_mapping(typed.to_dict()).to_dict() == typed.to_dict()
        except (ValidationError, KeyError, TypeError, ValueError):
            pass
    checks = (
        _check("exact-fields", exact_fields, "report document contains exactly the declared public fields", report_address),
        _check("public-boundary", public_boundary, "report document contains no private, path, or attribution metadata", report_address),
        _check("catalog-address", catalog_address_check, "report retains a namespaced source catalog address", report_address),
        _check("row-conservation", row_conservation, "report rows conserve sorted catalog ordinals and labels", report_address),
        _check("denominator-conservation", denominator_conservation, "accepted, ready, and rejected totals reconcile", report_address),
        _check("ratio-conservation", ratio_conservation, "basis-point ratios derive from report denominators", report_address),
        _check("artifact-conservation", artifact_conservation, "artifact totals derive from the canonical artifact count", report_address),
        _check("state-distributions", state_distributions, "state distributions derive from row projections", report_address),
        _check("label-partitions", label_partitions, "accepted, ready, and rejected labels derive from rows", report_address),
        _check("row-addresses", row_addresses, "every report row address reproduces", report_address),
        _check("content-address", content_address, "report content address reproduces from its public projection", report_address),
        _check("mapping-round-trip", mapping_round_trip, "typed report mapping rehydrates without drift", report_address),
    )
    complete = all(check.passed for check in checks)
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAudit(report_address, catalog_address, "complete" if complete else "incomplete", complete, complete, tuple(check for check in checks), "pending:observability-bundle-catalog-report-audit")
    addressed_checks = tuple(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditCheck(check.check_id, check.passed, check.detail, check.evidence_address, address_check(check)) for check in provisional.checks)
    final = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAudit(report_address, catalog_address, provisional.state, provisional.complete, provisional.accepted, addressed_checks, "pending:observability-bundle-catalog-report-audit")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAudit(report_address, catalog_address, final.state, final.complete, final.accepted, final.checks, address_audit(final))


def audit_report(value: report_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReport) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAudit:
    if not isinstance(value, report_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReport):
        raise ValidationError("observability bundle catalog report audit requires a typed report")
    report_model.verify_report(value)
    return _audit_mapping(value.to_dict())


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAudit:
    value = _mapping(value, "observability bundle catalog report audit input")
    if "report_address" in value and "checks" in value:
        return verify_audit(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAudit.from_mapping(value))
    return _audit_mapping(value)


def verify_audit(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAudit) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAudit:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAudit):
        raise ValidationError("observability bundle catalog report audit verification requires a typed audit")
    value._validate()
    if address_audit(value) != value.content_address:
        raise ValidationError("observability bundle catalog report audit content address does not replay")
    return value


def audit_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def render_audit_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAudit) -> str:
    value = verify_audit(value)
    lines = ["# Assurance History Observatory Observability Bundle Catalog Report Audit", "", f"- State: `{value.state}`", f"- Complete: `{value.complete}`", f"- Passed: `{value.passed_count}`", f"- Failed: `{value.failed_count}`", f"- Report: `{value.report_address}`", f"- Content address: `{value.content_address}`", "", "| check | passed | detail | evidence |", "| --- | --- | --- | --- |"]
    lines.extend(f"| `{check.check_id}` | `{check.passed}` | {check.detail} | `{check.evidence_address}` |" for check in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditCheck.FIELDS), "properties": {"check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string", "minLength": 1, "maxLength": 1024}, "evidence_address": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAudit.FIELDS), "properties": {"report_address": {"type": "string", "pattern": "^" + report_model.REPORT_PREFIX + ":"}, "catalog_address": {"type": "string", "pattern": "^" + report_model.catalog_model.CATALOG_PREFIX + ":"}, "state": {"type": "string", "enum": list(STATES)}, "complete": {"type": "boolean"}, "accepted": {"type": "boolean"}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS, "items": check_schema()}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "checks": CHECK_IDS, "states": STATES, "limits": {"max_checks": MAX_CHECKS, "max_rows": report_model.MAX_ROWS}, "features": ("fixed aggregate-report assurance checks", "public namespace validation", "row and denominator conservation", "basis-point and artifact conservation", "state distribution and label partition checks", "nested row address replay", "failure-visible tamper diagnostics", "content-address replay", "mapping round-trip", "path-free JSON and Markdown output"), "schemas": ("check", "audit")}


__all__ = [
    "AUDIT_PREFIX",
    "BOUNDARY",
    "CHECK_IDS",
    "CHECK_PREFIX",
    "EXPECTED_FIELDS",
    "MAX_CHECKS",
    "STATES",
    "VERSION",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAudit",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportAuditCheck",
    "address_audit",
    "address_check",
    "audit_from_mapping",
    "audit_json",
    "audit_report",
    "audit_schema",
    "capabilities",
    "check_schema",
    "render_audit_markdown",
    "verify_audit",
]
