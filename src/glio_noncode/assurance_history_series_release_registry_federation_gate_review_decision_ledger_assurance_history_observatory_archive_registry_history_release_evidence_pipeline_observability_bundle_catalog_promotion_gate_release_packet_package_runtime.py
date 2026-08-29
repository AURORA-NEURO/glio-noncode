"""End-to-end execution boundary for catalog promotion release packages.

The runtime composes the verified catalog, diff, report, promotion gate, gate
audit, release packet, durable package, package assurance, and bounded query
contracts. It is deliberately path-free at its public boundary: directories
are inputs to execution only and never become part of a returned document.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_diff as catalog_diff_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog as catalog_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate as promotion_gate_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_audit as promotion_audit_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_report as report_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet as packet_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package as package_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_audit as package_audit_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_query as package_query_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = package_model.VERSION + "-runtime-v1"
BOUNDARY = package_model.BOUNDARY + "_runtime"
RUNTIME_PREFIX = package_model.PACKAGE_PREFIX + "-runtime"
DEFAULT_RUNTIME_ID = "glio-noncode-catalog-promotion-package-runtime"
DEFAULT_PACKAGE_ID = package_model.DEFAULT_PACKAGE_ID
DEFAULT_RESOURCE = "summary"
DEFAULT_LIMIT = package_query_model.DEFAULT_LIMIT
MAX_LIMIT = package_query_model.MAX_LIMIT
MAX_SOURCES = 64
MAX_LABEL = 256
MAX_TEXT = package_model.MAX_TEXT
RESOURCES = package_query_model.RESOURCES
FILES = package_model.FILES


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, MAX_LABEL)
    if ":" in value or "/" in value or "\\" in value or any(character.isspace() for character in value):
        raise ValidationError(f"{field} must be a stable path-free label")
    return value


def _optional_text(value: Any, field: str, maximum: int = 512) -> str | None:
    if value is None:
        return None
    return _text(value, field, maximum)


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be a boolean")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be a mapping")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    return package_model._public(value)


def _sources(value: Any, field: str) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, (list, tuple)) or not value or len(value) > MAX_SOURCES:
        raise ValidationError(f"{field} must contain between one and {MAX_SOURCES} sources")
    normalized: list[tuple[str, str]] = []
    labels: set[str] = set()
    for ordinal, item in enumerate(value, 1):
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValidationError(f"{field}[{ordinal}] must be a label and directory pair")
        label = _label(item[0], f"{field}[{ordinal}].label")
        directory = _text(item[1], f"{field}[{ordinal}].directory", 4096)
        if label in labels:
            raise ValidationError(f"{field} labels must be unique")
        labels.add(label)
        normalized.append((label, directory))
    return tuple(normalized)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntimeRequest:
    """Path-free execution options for one package runtime invocation."""

    FIELDS = ("runtime_id", "left_labels", "right_labels", "package_id", "resource", "source", "severity", "check_id", "text", "limit", "max_added")

    def __init__(self, runtime_id: str = DEFAULT_RUNTIME_ID, left_labels: Sequence[str] = ("baseline",), right_labels: Sequence[str] = ("candidate",), package_id: str = DEFAULT_PACKAGE_ID, resource: str = DEFAULT_RESOURCE, source: str | None = None, severity: str | None = None, check_id: str | None = None, text: str | None = None, limit: int = DEFAULT_LIMIT, max_added: int | None = None) -> None:
        self.runtime_id = _label(runtime_id, "catalog promotion package runtime ID")
        self.left_labels = tuple(_label(label, "catalog promotion package runtime left label") for label in left_labels)
        self.right_labels = tuple(_label(label, "catalog promotion package runtime right label") for label in right_labels)
        if not self.left_labels or not self.right_labels or len(self.left_labels) > MAX_SOURCES or len(self.right_labels) > MAX_SOURCES:
            raise ValidationError("catalog promotion package runtime labels are outside their bound")
        if len(set(self.left_labels)) != len(self.left_labels) or len(set(self.right_labels)) != len(self.right_labels):
            raise ValidationError("catalog promotion package runtime labels must be unique")
        self.package_id = _label(package_id, "catalog promotion package runtime package ID")
        if resource not in RESOURCES:
            raise ValidationError("catalog promotion package runtime resource is unsupported")
        self.resource = resource
        self.source = _optional_text(source, "catalog promotion package runtime source", 32)
        if self.source is not None and self.source not in packet_model.SOURCES:
            raise ValidationError("catalog promotion package runtime source is unsupported")
        self.severity = _optional_text(severity, "catalog promotion package runtime severity", 32)
        if self.severity is not None and self.severity not in promotion_gate_model.SEVERITIES:
            raise ValidationError("catalog promotion package runtime severity is unsupported")
        self.check_id = _optional_text(check_id, "catalog promotion package runtime check ID", 128)
        self.text = _optional_text(text, "catalog promotion package runtime text", MAX_TEXT)
        self.limit = _count(limit, "catalog promotion package runtime limit", MAX_LIMIT, positive=True)
        if max_added is not None:
            max_added = _count(max_added, "catalog promotion package runtime max added", promotion_gate_model.MAX_CHECKS)
        self.max_added = max_added
        if not _public(self.to_dict()):
            raise ValidationError("catalog promotion package runtime request crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntimeRequest:
        value = _mapping(value, "catalog promotion package runtime request")
        _strict(value, set(cls.FIELDS), "catalog promotion package runtime request")
        missing = [field for field in cls.FIELDS if field not in value]
        if missing:
            raise ValidationError(f"catalog promotion package runtime request is missing fields: {missing}")
        return cls(**value)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntime:
    """Complete, verified result of one catalog promotion package execution."""

    FIELDS = ("runtime_id", "request", "package", "audit", "query", "persisted", "files", "reload_verified", "content_address")

    def __init__(self, runtime_id: str, request: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntimeRequest, package: package_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage, audit: package_audit_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAudit, query: package_query_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQueryResult, persisted: bool, files: Sequence[str], reload_verified: bool, content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "catalog promotion package runtime ID")
        if not isinstance(request, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntimeRequest):
            raise ValidationError("catalog promotion package runtime request must be typed")
        self.request = request
        if not isinstance(package, package_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackage):
            raise ValidationError("catalog promotion package runtime package must be typed")
        self.package = package
        if not isinstance(audit, package_audit_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAudit):
            raise ValidationError("catalog promotion package runtime audit must be typed")
        self.audit = audit
        if not isinstance(query, package_query_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQueryResult):
            raise ValidationError("catalog promotion package runtime query must be typed")
        self.query = query
        self.persisted = _bool(persisted, "catalog promotion package runtime persisted")
        self.files = tuple(_label(name, "catalog promotion package runtime file") for name in files)
        if self.persisted and self.files != FILES:
            raise ValidationError("catalog promotion package runtime persisted file inventory is invalid")
        self.reload_verified = _bool(reload_verified, "catalog promotion package runtime reload verified")
        if self.persisted != self.reload_verified:
            raise ValidationError("catalog promotion package runtime persistence and reload status are inconsistent")
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        package_model.verify_package(self.package)
        package_audit_model.verify_audit(self.audit)
        package_query_model.verify_query(self.query)
        if self.audit.package_address != self.package.content_address or self.query.package_address != self.package.content_address:
            raise ValidationError("catalog promotion package runtime nested addresses are not linked")
        if self.query.query.resource != self.request.resource or self.query.query.limit != self.request.limit:
            raise ValidationError("catalog promotion package runtime query does not match its request")
        if not self.persisted and self.files:
            raise ValidationError("catalog promotion package runtime files must be empty before persistence")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "catalog promotion package runtime content address")
        elif address_runtime(self) != self.content_address:
            raise ValidationError("catalog promotion package runtime content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("catalog promotion package runtime crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "request": self.request.to_dict(), "package": self.package.to_dict(), "audit": self.audit.to_dict(), "query": self.query.to_dict(), "persisted": self.persisted, "files": self.files, "reload_verified": self.reload_verified, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "package_id": self.package.package_id, "package_address": self.package.content_address, "state": self.package.packet.state, "decision": self.package.packet.decision, "accepted": self.package.packet.accepted, "release_ready": self.package.packet.release_ready, "package_audit_state": self.audit.state, "package_audit_accepted": self.audit.accepted, "package_audit_passed_count": self.audit.passed_count, "package_audit_check_count": self.audit.check_count, "query_resource": self.query.query.resource, "query_total_count": self.query.total_count, "query_returned_count": self.query.returned_count, "persisted": self.persisted, "files": self.files, "reload_verified": self.reload_verified, "content_address": self.content_address}


def address_runtime(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntime) -> str:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntime):
        raise ValidationError("catalog promotion package runtime address requires a typed runtime")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RUNTIME_PREFIX)


def _catalogs(left_sources: Sequence[tuple[str, str]], right_sources: Sequence[tuple[str, str]], catalog_id: str) -> tuple[Any, Any]:
    left = catalog_model.build_catalog_from_directories(tuple(left_sources), catalog_id=catalog_id + "-left")
    right = catalog_model.build_catalog_from_directories(tuple(right_sources), catalog_id=catalog_id + "-right")
    return left, right


def _request_from_inputs(left_sources: Sequence[tuple[str, str]], right_sources: Sequence[tuple[str, str]], *, runtime_id: str, package_id: str, resource: str, source: str | None, severity: str | None, check_id: str | None, text: str | None, limit: int, max_added: int | None) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntimeRequest:
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntimeRequest(runtime_id=runtime_id, left_labels=tuple(label for label, _ in left_sources), right_labels=tuple(label for label, _ in right_sources), package_id=package_id, resource=resource, source=source, severity=severity, check_id=check_id, text=text, limit=limit, max_added=max_added)


def run_package_runtime(left_sources: Sequence[tuple[str, str]], right_sources: Sequence[tuple[str, str]], *, runtime_id: str = DEFAULT_RUNTIME_ID, package_id: str = DEFAULT_PACKAGE_ID, catalog_id: str = catalog_model.DEFAULT_CATALOG_ID, diff_id: str = catalog_diff_model.DEFAULT_DIFF_ID, report_id: str = report_model.DEFAULT_REPORT_ID, gate_id: str = promotion_gate_model.DEFAULT_GATE_ID, packet_id: str = packet_model.DEFAULT_PACKET_ID, resource: str = DEFAULT_RESOURCE, source: str | None = None, severity: str | None = None, check_id: str | None = None, text: str | None = None, limit: int = DEFAULT_LIMIT, max_added: int | None = None, destination: str | Path | None = None, overwrite: bool = False) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntime:
    left_sources = _sources(left_sources, "catalog promotion package runtime left sources")
    right_sources = _sources(right_sources, "catalog promotion package runtime right sources")
    request = _request_from_inputs(left_sources, right_sources, runtime_id=runtime_id, package_id=package_id, resource=resource, source=source, severity=severity, check_id=check_id, text=text, limit=limit, max_added=max_added)
    left_catalog, right_catalog = _catalogs(left_sources, right_sources, _label(catalog_id, "catalog promotion package runtime catalog ID"))
    change = catalog_diff_model.build_diff(left_catalog, right_catalog, diff_id=_label(diff_id, "catalog promotion package runtime diff ID"))
    report = report_model.build_report(right_catalog, report_id=_label(report_id, "catalog promotion package runtime report ID"))
    policy = None if max_added is None else promotion_gate_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionPolicy(max_added=max_added)
    gate = promotion_gate_model.build_promotion_gate(change, report, policy=policy, gate_id=_label(gate_id, "catalog promotion package runtime gate ID"))
    gate_audit = promotion_audit_model.audit_gate(gate)
    packet = packet_model.build_release_packet(gate, gate_audit, packet_id=_label(packet_id, "catalog promotion package runtime packet ID"))
    package = package_model.build_package(gate, gate_audit, packet, package_id=request.package_id)
    persisted = destination is not None
    reload_verified = False
    files: tuple[str, ...] = ()
    if destination is not None:
        package_model.write_package(package, destination, overwrite=overwrite)
        package = package_model.load_package(destination)
        package_model.verify_package(destination)
        files = package_model.FILES
        reload_verified = True
    audit = package_audit_model.audit_package(package)
    query = package_query_model.query_package(package, resource=request.resource, source=request.source, severity=request.severity, check_id=request.check_id, text=request.text, limit=request.limit)
    provisional = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntime(request.runtime_id, request, package, audit, query, persisted, files, reload_verified, "pending:catalog-promotion-package-runtime")
    return RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntime(request.runtime_id, request, package, audit, query, persisted, files, reload_verified, address_runtime(provisional))


def runtime_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntime:
    value = _mapping(value, "catalog promotion package runtime")
    _strict(value, set(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntime.FIELDS), "catalog promotion package runtime")
    missing = [field for field in RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntime.FIELDS if field not in value]
    if missing:
        raise ValidationError(f"catalog promotion package runtime is missing fields: {missing}")
    request = RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntimeRequest.from_mapping(_mapping(value["request"], "catalog promotion package runtime request"))
    package = package_model.package_from_mapping(_mapping(value["package"], "catalog promotion package runtime package"))
    audit = package_audit_model.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageAudit.from_mapping(_mapping(value["audit"], "catalog promotion package runtime audit"))
    query = package_query_model.query_result_from_mapping(_mapping(value["query"], "catalog promotion package runtime query"))
    files = tuple(value["files"]) if isinstance(value["files"], (list, tuple)) else value["files"]
    return verify_runtime(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntime(value["runtime_id"], request, package, audit, query, value["persisted"], files, value["reload_verified"], value["content_address"]))


def verify_runtime(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntime) -> RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntime:
    if not isinstance(value, RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntime):
        raise ValidationError("catalog promotion package runtime verification requires a typed runtime")
    value._validate()
    if address_runtime(value) != value.content_address:
        raise ValidationError("catalog promotion package runtime content address does not replay")
    return value


def runtime_json(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntime) -> str:
    return canonical_json(verify_runtime(value).to_dict())


def runtime_csv(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntime) -> str:
    value = verify_runtime(value)
    fields = ("runtime_id", "package_id", "state", "decision", "accepted", "release_ready", "package_audit_state", "package_audit_passed_count", "package_audit_check_count", "query_resource", "query_total_count", "query_returned_count", "persisted", "reload_verified", "content_address")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerow({field: value.summary().get(field, "") for field in fields})
    return output.getvalue()


def render_runtime_markdown(value: RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntime) -> str:
    value = verify_runtime(value)
    summary = value.summary()
    lines = ["# Catalog Promotion Package Runtime", "", f"- Runtime: `{summary['runtime_id']}`", f"- Package: `{summary['package_id']}`", f"- Decision: `{summary['decision']}`", f"- State: `{summary['state']}`", f"- Release ready: `{summary['release_ready']}`", f"- Package assurance: `{summary['package_audit_passed_count']}/{summary['package_audit_check_count']}` checks passed", f"- Query: `{summary['query_resource']}` returned `{summary['query_returned_count']}` of `{summary['query_total_count']}` records", f"- Persisted and reloaded: `{summary['reload_verified']}`", f"- Content address: `{summary['content_address']}`", "", "| file |", "| --- |"]
    lines.extend(f"| `{name}` |" for name in value.files)
    return "\n".join(lines) + "\n"


def request_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntimeRequest.FIELDS), "properties": {"runtime_id": {"type": "string"}, "left_labels": {"type": "array", "minItems": 1, "maxItems": MAX_SOURCES, "items": {"type": "string"}}, "right_labels": {"type": "array", "minItems": 1, "maxItems": MAX_SOURCES, "items": {"type": "string"}}, "package_id": {"type": "string"}, "resource": {"type": "string", "enum": list(RESOURCES)}, "source": {"type": ["string", "null"]}, "severity": {"type": ["string", "null"]}, "check_id": {"type": ["string", "null"]}, "text": {"type": ["string", "null"], "maxLength": MAX_TEXT}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}, "max_added": {"type": ["integer", "null"], "minimum": 0, "maximum": promotion_gate_model.MAX_CHECKS}}}


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntime.FIELDS), "properties": {"runtime_id": {"type": "string"}, "request": request_schema(), "package": package_model.package_schema(), "audit": package_audit_model.audit_schema(), "query": package_query_model.query_result_schema(), "persisted": {"type": "boolean"}, "files": {"type": "array", "items": {"type": "string", "enum": list(FILES)}}, "reload_verified": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + RUNTIME_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "runtime_prefix": RUNTIME_PREFIX, "default_runtime_id": DEFAULT_RUNTIME_ID, "resources": RESOURCES, "files": FILES, "limits": {"max_sources": MAX_SOURCES, "max_limit": MAX_LIMIT, "max_text": MAX_TEXT}, "features": ("catalog-to-package composition", "optional atomic persistence", "reload verification", "independent package assurance", "bounded package query", "path-free public runtime result", "JSON CSV and Markdown exports", "content-addressed runtime replay"), "schemas": ("request", "runtime", "package", "package-audit", "package-query")}


__all__ = [
    "BOUNDARY", "DEFAULT_LIMIT", "DEFAULT_PACKAGE_ID", "DEFAULT_RESOURCE", "DEFAULT_RUNTIME_ID", "FILES", "MAX_LABEL", "MAX_LIMIT", "MAX_SOURCES", "MAX_TEXT", "RESOURCES", "RUNTIME_PREFIX", "VERSION",
    "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntime", "RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntimeRequest",
    "address_runtime", "capabilities", "render_runtime_markdown", "request_schema", "run_package_runtime", "runtime_csv", "runtime_from_mapping", "runtime_json", "runtime_schema", "verify_runtime",
]
