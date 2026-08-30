"""Exact-byte snapshot package for certificate observatory handoffs."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory as observatory_model
from . import registry_federation_consensus_gate_certificate_observatory_audit as observatory_audit_model
from . import registry_federation_consensus_gate_certificate_observatory_query_audit as query_audit_model
from . import registry_federation_consensus_gate_certificate_observatory_report as report_model
from . import registry_federation_consensus_gate_certificate_observatory_report_audit as report_audit_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash


VERSION = report_model.VERSION + "-package-v1"
BOUNDARY = report_model.BOUNDARY + "_package"
PACKAGE_PREFIX = observatory_model.OBSERVATORY_PREFIX + "-package"
MANIFEST_NAME = "manifest.json"
PACKAGE_NAME = "package.json"
OBSERVATORY_NAME = "observatory.json"
QUERY_NAME = "query.json"
REPORT_NAME = "report.json"
OBSERVATORY_AUDIT_NAME = "observatory-audit.json"
QUERY_AUDIT_NAME = "query-audit.json"
REPORT_AUDIT_NAME = "report-audit.json"
FILES = (MANIFEST_NAME, PACKAGE_NAME, OBSERVATORY_NAME, QUERY_NAME, REPORT_NAME, OBSERVATORY_AUDIT_NAME, QUERY_AUDIT_NAME, REPORT_AUDIT_NAME)
CHECK_IDS = ("exact-fields", "public-boundary", "observatory-link", "query-link", "report-link", "observatory-audit-link", "query-audit-link", "report-audit-link", "member-vocabulary", "nested-addresses", "package-address", "mapping-round-trip", "projection-bytes", "content-address", "path-free")


def _text(value: Any, field: str, maximum: int = observatory_model.MAX_TEXT, *, required: bool = False) -> str:
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


class RegistryFederationConsensusGateCertificateObservatoryPackage:
    """One eight-file, independently auditable observatory snapshot."""

    FIELDS = ("package_id", "observatory", "query", "report", "observatory_audit", "query_audit", "report_audit", "content_address")

    def __init__(self, package_id: str, observatory: observatory_model.RegistryFederationConsensusGateCertificateObservatory, query: observatory_model.RegistryFederationConsensusGateCertificateObservatoryQueryResult, report: report_model.RegistryFederationConsensusGateCertificateObservatoryReport, observatory_audit: observatory_audit_model.RegistryFederationConsensusGateCertificateObservatoryAudit, query_audit: query_audit_model.RegistryFederationConsensusGateCertificateObservatoryQueryAudit, report_audit: report_audit_model.RegistryFederationConsensusGateCertificateObservatoryReportAudit, content_address: str) -> None:
        self.package_id = _label(package_id, "certificate observatory package ID")
        if not isinstance(observatory, observatory_model.RegistryFederationConsensusGateCertificateObservatory) or not isinstance(query, observatory_model.RegistryFederationConsensusGateCertificateObservatoryQueryResult) or not isinstance(report, report_model.RegistryFederationConsensusGateCertificateObservatoryReport) or not isinstance(observatory_audit, observatory_audit_model.RegistryFederationConsensusGateCertificateObservatoryAudit) or not isinstance(query_audit, query_audit_model.RegistryFederationConsensusGateCertificateObservatoryQueryAudit) or not isinstance(report_audit, report_audit_model.RegistryFederationConsensusGateCertificateObservatoryReportAudit):
            raise ValidationError("certificate observatory package members must be typed")
        self.observatory = observatory_model.verify_observatory(observatory)
        self.query = observatory_model.verify_query_result(query)
        self.report = report_model.verify_report(report)
        self.observatory_audit = observatory_audit_model.verify_audit(observatory_audit)
        self.query_audit = query_audit_model.verify_audit(query_audit)
        self.report_audit = report_audit_model.verify_audit(report_audit)
        if self.query.query.observatory_address != self.observatory.content_address or self.report.observatory_address != self.observatory.content_address or self.observatory_audit.observatory_address != self.observatory.content_address:
            raise ValidationError("certificate observatory package observatory links do not replay")
        if self.query_audit.query_address != self.query.query.content_address or self.query_audit.result_address != self.query.content_address:
            raise ValidationError("certificate observatory package query links do not replay")
        if self.report_audit.report_address != self.report.content_address:
            raise ValidationError("certificate observatory package report link does not replay")
        self.content_address = _address(content_address, "certificate observatory package content address", PACKAGE_PREFIX)
        if not self.content_address.endswith(":pending") and address_package(self) != self.content_address:
            raise ValidationError("certificate observatory package content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate observatory package crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"package_id": self.package_id, "observatory": self.observatory.to_dict(), "query": self.query.to_dict(), "report": self.report.to_dict(), "observatory_audit": self.observatory_audit.to_dict(), "query_audit": self.query_audit.to_dict(), "report_audit": self.report_audit.to_dict(), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {"package_id": self.package_id, "observatory_address": self.observatory.content_address, "query_address": self.query.content_address, "report_address": self.report.content_address, "observatory_audit_address": self.observatory_audit.content_address, "query_audit_address": self.query_audit.content_address, "report_audit_address": self.report_audit.content_address, "observation_count": self.observatory.observation_count, "acceptance_ratio": self.report.acceptance_ratio, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryPackage:
        value = _mapping(value, "certificate observatory package")
        _strict(value, set(cls.FIELDS), "certificate observatory package")
        return cls(value["package_id"], observatory_model.observatory_from_mapping(value["observatory"]), observatory_model.query_from_mapping(value["query"]), report_model.report_from_mapping(value["report"]), observatory_audit_model.audit_from_mapping(value["observatory_audit"]), query_audit_model.audit_from_mapping(value["query_audit"]), report_audit_model.audit_from_mapping(value["report_audit"]), value["content_address"])


def address_package(value: RegistryFederationConsensusGateCertificateObservatoryPackage) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryPackage):
        raise ValidationError("certificate observatory package address requires a typed package")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=PACKAGE_PREFIX)


def build_package(observatory: observatory_model.RegistryFederationConsensusGateCertificateObservatory, *, package_id: str = "consensus-certificate-observatory-package", query: observatory_model.RegistryFederationConsensusGateCertificateObservatoryQueryResult | None = None, report: report_model.RegistryFederationConsensusGateCertificateObservatoryReport | None = None, observatory_audit: observatory_audit_model.RegistryFederationConsensusGateCertificateObservatoryAudit | None = None, query_audit: query_audit_model.RegistryFederationConsensusGateCertificateObservatoryQueryAudit | None = None, report_audit: report_audit_model.RegistryFederationConsensusGateCertificateObservatoryReportAudit | None = None) -> RegistryFederationConsensusGateCertificateObservatoryPackage:
    observatory = observatory_model.verify_observatory(observatory)
    selected_query = observatory_model.query_observatory(observatory, limit=observatory_model.MAX_ROWS) if query is None else observatory_model.verify_query_result(query)
    selected_report = report_model.build_report(observatory) if report is None else report_model.verify_report(report)
    selected_observatory_audit = observatory_audit_model.audit_observatory(observatory) if observatory_audit is None else observatory_audit_model.verify_audit(observatory_audit)
    selected_query_audit = query_audit_model.audit_query(selected_query) if query_audit is None else query_audit_model.verify_audit(query_audit)
    selected_report_audit = report_audit_model.audit_report(selected_report) if report_audit is None else report_audit_model.verify_audit(report_audit)
    provisional = RegistryFederationConsensusGateCertificateObservatoryPackage(package_id, observatory, selected_query, selected_report, selected_observatory_audit, selected_query_audit, selected_report_audit, PACKAGE_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryPackage(provisional.package_id, provisional.observatory, provisional.query, provisional.report, provisional.observatory_audit, provisional.query_audit, provisional.report_audit, address_package(provisional))


def package_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryPackage:
    return verify_package(RegistryFederationConsensusGateCertificateObservatoryPackage.from_mapping(value))


def verify_package(value: RegistryFederationConsensusGateCertificateObservatoryPackage) -> RegistryFederationConsensusGateCertificateObservatoryPackage:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryPackage) or (not value.content_address.endswith(":pending") and address_package(value) != value.content_address):
        raise ValidationError("certificate observatory package is not valid")
    return value


def package_json(value: RegistryFederationConsensusGateCertificateObservatoryPackage) -> str:
    return canonical_json(verify_package(value).to_dict())


def _manifest(value: RegistryFederationConsensusGateCertificateObservatoryPackage) -> dict[str, Any]:
    body = {"version": VERSION, "boundary": BOUNDARY, "package_id": value.package_id, "files": FILES, "package_address": value.content_address, "observatory_address": value.observatory.content_address, "query_address": value.query.content_address, "report_address": value.report.content_address, "observatory_audit_address": value.observatory_audit.content_address, "query_audit_address": value.query_audit.content_address, "report_audit_address": value.report_audit.content_address}
    return body | {"manifest_address": content_hash(body | {"manifest_address": None}, prefix=PACKAGE_PREFIX + "-manifest")}


def package_bytes(value: RegistryFederationConsensusGateCertificateObservatoryPackage) -> dict[str, bytes]:
    value = verify_package(value)
    return {MANIFEST_NAME: canonical_bytes(_manifest(value)), PACKAGE_NAME: canonical_bytes(value.to_dict()), OBSERVATORY_NAME: canonical_bytes(value.observatory.to_dict()), QUERY_NAME: canonical_bytes(value.query.to_dict()), REPORT_NAME: canonical_bytes(value.report.to_dict()), OBSERVATORY_AUDIT_NAME: canonical_bytes(value.observatory_audit.to_dict()), QUERY_AUDIT_NAME: canonical_bytes(value.query_audit.to_dict()), REPORT_AUDIT_NAME: canonical_bytes(value.report_audit.to_dict())}


def _write_atomic(destination: Path, payload: Mapping[str, bytes], *, overwrite: bool) -> Path:
    if destination.exists() and (destination.is_symlink() or not destination.is_dir() or (not overwrite and any(destination.iterdir()))):
        raise ValidationError("certificate observatory package destination is not writable")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="certificate-observatory-package-staging-", dir=str(destination.parent)))
    try:
        for name in FILES:
            (staging / name).write_bytes(payload[name])
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(staging, destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination


def write_package(value: RegistryFederationConsensusGateCertificateObservatoryPackage, directory: str | Path, *, overwrite: bool = False) -> Path:
    return _write_atomic(Path(directory), package_bytes(value), overwrite=overwrite)


def load_package(directory: str | Path) -> RegistryFederationConsensusGateCertificateObservatoryPackage:
    source = Path(directory)
    if source.is_symlink() or not source.is_dir() or {item.name for item in source.iterdir()} != set(FILES) or any(item.is_symlink() or not item.is_file() for item in source.iterdir()):
        raise ValidationError("certificate observatory package directory does not contain exact canonical members")
    raw = {name: (source / name).read_bytes() for name in FILES}
    try:
        decoded = {name: json.loads(payload.decode("utf-8")) for name, payload in raw.items()}
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("certificate observatory package contains invalid JSON") from error
    if any(canonical_bytes(decoded[name]) != raw[name] for name in FILES):
        raise ValidationError("certificate observatory package member is not canonical JSON")
    value = package_from_mapping(decoded[PACKAGE_NAME])
    if canonical_bytes(decoded[MANIFEST_NAME]) != canonical_bytes(_manifest(value)):
        raise ValidationError("certificate observatory package manifest does not replay")
    projections = ((OBSERVATORY_NAME, value.observatory.to_dict()), (QUERY_NAME, value.query.to_dict()), (REPORT_NAME, value.report.to_dict()), (OBSERVATORY_AUDIT_NAME, value.observatory_audit.to_dict()), (QUERY_AUDIT_NAME, value.query_audit.to_dict()), (REPORT_AUDIT_NAME, value.report_audit.to_dict()))
    if any(canonical_bytes(decoded[name]) != canonical_bytes(expected) for name, expected in projections):
        raise ValidationError("certificate observatory package projections do not replay")
    return value


def verify_package_directory(directory: str | Path) -> RegistryFederationConsensusGateCertificateObservatoryPackage:
    return load_package(directory)


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["version", "boundary", "package_id", "files", "package_address", "observatory_address", "query_address", "report_address", "observatory_audit_address", "query_audit_address", "report_audit_address", "manifest_address"], "properties": {"version": {"type": "string"}, "boundary": {"type": "string"}, "package_id": {"type": "string"}, "files": {"type": "array"}, "package_address": {"type": "string"}, "observatory_address": {"type": "string"}, "query_address": {"type": "string"}, "report_address": {"type": "string"}, "observatory_audit_address": {"type": "string"}, "query_audit_address": {"type": "string"}, "report_audit_address": {"type": "string"}, "manifest_address": {"type": "string"}}}


def package_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryPackage.FIELDS), "properties": {"package_id": {"type": "string"}, "observatory": observatory_model.observatory_schema(), "query": observatory_model.result_schema(), "report": report_model.report_schema(), "observatory_audit": observatory_audit_model.audit_schema(), "query_audit": query_audit_model.audit_schema(), "report_audit": report_audit_model.audit_schema(), "content_address": {"type": "string", "pattern": "^" + PACKAGE_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "package_prefix": PACKAGE_PREFIX, "files": FILES, "check_ids": CHECK_IDS, "features": ("eight-file observatory snapshot", "atomic directory replacement", "canonical reload verification", "manifest and projection replay", "embedded observatory and report audits", "bounded query closure", "JSON export"), "schemas": ("manifest", "package")}


__all__ = ["BOUNDARY", "CHECK_IDS", "FILES", "MANIFEST_NAME", "OBSERVATORY_AUDIT_NAME", "OBSERVATORY_NAME", "PACKAGE_NAME", "PACKAGE_PREFIX", "QUERY_AUDIT_NAME", "QUERY_NAME", "REPORT_AUDIT_NAME", "REPORT_NAME", "RegistryFederationConsensusGateCertificateObservatoryPackage", "VERSION", "address_package", "build_package", "capabilities", "load_package", "manifest_schema", "package_bytes", "package_from_mapping", "package_json", "package_schema", "verify_package", "verify_package_directory", "write_package"]
