"""End-to-end runtime for building certificate observatory handoffs."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import registry_federation_consensus_gate_certificate_observatory as observatory_model
from . import registry_federation_consensus_gate_certificate_observatory_audit as observatory_audit_model
from . import registry_federation_consensus_gate_certificate_observatory_package as package_model
from . import registry_federation_consensus_gate_certificate_observatory_query_audit as query_audit_model
from . import registry_federation_consensus_gate_certificate_observatory_report as report_model
from . import registry_federation_consensus_gate_certificate_observatory_report_audit as report_audit_model
from . import registry_federation_consensus_gate_certificate_history as history_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = observatory_model.VERSION + "-runtime-v1"
BOUNDARY = observatory_model.BOUNDARY + "_runtime"
RUNTIME_PREFIX = observatory_model.OBSERVATORY_PREFIX + "-runtime"
MAX_TEXT = observatory_model.MAX_TEXT
MAX_INPUTS = observatory_model.MAX_HISTORIES


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
    value = _text(value, field, 512, required=not optional)
    if value and ("/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":"))):
        raise ValidationError(f"{field} has an unsupported address")
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


class RegistryFederationConsensusGateCertificateObservatoryRuntime:
    """Addressed composition of every certificate-observatory stage."""

    FIELDS = ("runtime_id", "observatory", "observatory_audit", "query", "query_audit", "report", "report_audit", "package_address", "persisted", "content_address")

    def __init__(self, runtime_id: str, observatory: observatory_model.RegistryFederationConsensusGateCertificateObservatory, observatory_audit: observatory_audit_model.RegistryFederationConsensusGateCertificateObservatoryAudit, query: observatory_model.RegistryFederationConsensusGateCertificateObservatoryQueryResult, query_audit: query_audit_model.RegistryFederationConsensusGateCertificateObservatoryQueryAudit, report: report_model.RegistryFederationConsensusGateCertificateObservatoryReport, report_audit: report_audit_model.RegistryFederationConsensusGateCertificateObservatoryReportAudit, package_address: str, persisted: bool, content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "certificate observatory runtime ID")
        self.observatory = observatory_model.verify_observatory(observatory)
        self.observatory_audit = observatory_audit_model.verify_audit(observatory_audit)
        self.query = observatory_model.verify_query_result(query)
        self.query_audit = query_audit_model.verify_audit(query_audit)
        self.report = report_model.verify_report(report)
        self.report_audit = report_audit_model.verify_audit(report_audit)
        if self.observatory_audit.observatory_address != self.observatory.content_address or self.query.query.observatory_address != self.observatory.content_address or self.query_audit.result_address != self.query.content_address or self.report.observatory_address != self.observatory.content_address or self.report_audit.report_address != self.report.content_address:
            raise ValidationError("certificate observatory runtime nested links are not conserved")
        self.package_address = _address(package_address, "certificate observatory runtime package address", package_model.PACKAGE_PREFIX, optional=True)
        self.persisted = _bool(persisted, "certificate observatory runtime persisted flag")
        if self.persisted != bool(self.package_address):
            raise ValidationError("certificate observatory runtime persistence is not conserved")
        self.content_address = _address(content_address, "certificate observatory runtime address", RUNTIME_PREFIX)
        if not self.content_address.endswith(":pending") and address_runtime(self) != self.content_address:
            raise ValidationError("certificate observatory runtime address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("certificate observatory runtime crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "observatory": self.observatory.to_dict(), "observatory_audit": self.observatory_audit.to_dict(), "query": self.query.to_dict(), "query_audit": self.query_audit.to_dict(), "report": self.report.to_dict(), "report_audit": self.report_audit.to_dict(), "package_address": self.package_address, "persisted": self.persisted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "observatory_address": self.observatory.content_address, "observatory_audit_address": self.observatory_audit.content_address, "query_address": self.query.content_address, "query_audit_address": self.query_audit.content_address, "report_address": self.report.content_address, "report_audit_address": self.report_audit.content_address, "package_address": self.package_address, "persisted": self.persisted, "content_address": self.content_address, "observation_count": self.observatory.observation_count, "stream_state": self.report.stream_state, "alert_count": self.report.alert_count}


def address_runtime(value: RegistryFederationConsensusGateCertificateObservatoryRuntime) -> str:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryRuntime):
        raise ValidationError("certificate observatory runtime address requires a typed runtime")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RUNTIME_PREFIX)


def _history(value: str | Path) -> history_model.RegistryFederationConsensusGateCertificateHistory:
    source = Path(value)
    if source.is_dir():
        return history_model.load_history(source)
    return history_model.history_from_mapping(json.loads(source.read_text(encoding="utf-8")))


def run_runtime(inputs: Sequence[str | Path], *, runtime_id: str = "consensus-certificate-observatory-runtime", observatory_id: str = "consensus-certificate-observatory", report_id: str = "consensus-certificate-observatory-report", package_id: str = "consensus-certificate-observatory-package", resources: Sequence[str] = observatory_model.DEFAULT_RESOURCES, limit: int = 100, destination: str | Path | None = None) -> RegistryFederationConsensusGateCertificateObservatoryRuntime:
    inputs = tuple(inputs)
    if not inputs or len(inputs) > MAX_INPUTS:
        raise ValidationError("certificate observatory runtime inputs are outside the bound")
    histories = tuple(_history(value) for value in inputs)
    observatory = observatory_model.build_observatory(histories, observatory_id=observatory_id)
    observatory_audit = observatory_audit_model.audit_observatory(observatory)
    query = observatory_model.query_observatory(observatory, resources=resources, limit=limit)
    query_audit = query_audit_model.audit_query(query)
    report = report_model.build_report(observatory, report_id=report_id)
    report_audit = report_audit_model.audit_report(report)
    package_address = ""
    persisted = False
    if destination is not None:
        package = package_model.build_package(observatory, query=query, report=report, observatory_audit=observatory_audit, query_audit=query_audit, report_audit=report_audit, package_id=package_id)
        package_model.write_package(package, destination)
        package_address, persisted = package.content_address, True
    provisional = RegistryFederationConsensusGateCertificateObservatoryRuntime(runtime_id, observatory, observatory_audit, query, query_audit, report, report_audit, package_address, persisted, RUNTIME_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryRuntime(provisional.runtime_id, provisional.observatory, provisional.observatory_audit, provisional.query, provisional.query_audit, provisional.report, provisional.report_audit, provisional.package_address, provisional.persisted, address_runtime(provisional))


def runtime_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryRuntime:
    value = _mapping(value, "certificate observatory runtime")
    _strict(value, set(RegistryFederationConsensusGateCertificateObservatoryRuntime.FIELDS), "certificate observatory runtime")
    return verify_runtime(RegistryFederationConsensusGateCertificateObservatoryRuntime(value["runtime_id"], observatory_model.observatory_from_mapping(value["observatory"]), observatory_audit_model.audit_from_mapping(value["observatory_audit"]), observatory_model.query_from_mapping(value["query"]), query_audit_model.audit_from_mapping(value["query_audit"]), report_model.report_from_mapping(value["report"]), report_audit_model.audit_from_mapping(value["report_audit"]), value["package_address"], value["persisted"], value["content_address"]))


def verify_runtime(value: RegistryFederationConsensusGateCertificateObservatoryRuntime) -> RegistryFederationConsensusGateCertificateObservatoryRuntime:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryRuntime) or (not value.content_address.endswith(":pending") and address_runtime(value) != value.content_address):
        raise ValidationError("certificate observatory runtime is not valid")
    return value


def runtime_json(value: RegistryFederationConsensusGateCertificateObservatoryRuntime) -> str:
    return canonical_json(verify_runtime(value).to_dict())


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryRuntime.FIELDS), "properties": {"runtime_id": {"type": "string"}, "observatory": observatory_model.observatory_schema(), "observatory_audit": observatory_audit_model.audit_schema(), "query": observatory_model.result_schema(), "query_audit": query_audit_model.audit_schema(), "report": report_model.report_schema(), "report_audit": report_audit_model.audit_schema(), "package_address": {"type": "string"}, "persisted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + RUNTIME_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "runtime_prefix": RUNTIME_PREFIX, "max_inputs": MAX_INPUTS, "features": ("history-directory loading", "aggregate and independent audit orchestration", "bounded query and health report", "optional exact package persistence", "content-addressed runtime summary", "path-free public serialization"), "schemas": ("runtime",)}


__all__ = ["BOUNDARY", "MAX_INPUTS", "RUNTIME_PREFIX", "RegistryFederationConsensusGateCertificateObservatoryRuntime", "VERSION", "address_runtime", "capabilities", "run_runtime", "runtime_from_mapping", "runtime_json", "runtime_schema", "verify_runtime"]
