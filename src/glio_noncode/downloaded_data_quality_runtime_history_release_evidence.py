"""Portable release evidence assembled from a downloaded-data quality gate."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import downloaded_data_quality_runtime_history_release_gate as gate_model
from . import downloaded_data_quality_runtime_history_release_gate_audit as gate_audit_model
from . import downloaded_data_quality_runtime_history_release_gate_query as query_model
from . import downloaded_data_quality_runtime_history_release_gate_query_audit as query_audit_model
from ._safe_persistence import _validate_parent, read_text
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash


VERSION = gate_model.VERSION + "-evidence-v1"
BOUNDARY = gate_model.BOUNDARY + "_evidence"
EVIDENCE_PREFIX = gate_model.GATE_PREFIX + "-evidence"
MANIFEST_PREFIX = EVIDENCE_PREFIX + "-manifest"
SUMMARY_PREFIX = EVIDENCE_PREFIX + "-summary"
DEFAULT_EVIDENCE_ID = EVIDENCE_PREFIX
FILES = ("manifest.json", "evidence.json", "gate.json", "gate-audit.json", "query.json", "query-audit.json", "summary.json")
ARTIFACT_FILES = ("gate.json", "gate-audit.json", "query.json", "query-audit.json", "summary.json")
STATES = ("ready", "blocked")
MAX_EVIDENCE_BYTES = 64 * 1024 * 1024
MAX_FILES = 7
MANIFEST_FIELDS = ("evidence_id", "gate_id", "history_id", "version", "boundary", "files", "artifact_addresses", "content_address")
SUMMARY_FIELDS = (
    "evidence_id",
    "gate_id",
    "history_id",
    "gate_state",
    "release_ready",
    "gate_audit_accepted",
    "query_audit_accepted",
    "query_complete",
    "evidence_ready",
    "check_count",
    "passed_count",
    "row_count",
    "total_row_count",
    "resource_count",
    "content_address",
)
EVIDENCE_FIELDS = (
    "evidence_id",
    "gate_id",
    "history_id",
    "gate_address",
    "gate_audit_address",
    "query_address",
    "query_audit_address",
    "version",
    "boundary",
    "gate",
    "gate_audit",
    "query",
    "query_audit",
    "manifest",
    "summary",
    "content_address",
)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 4096)
    if value.startswith("pending:") or value.endswith(":pending"):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has the wrong address namespace")
    return value


def _count(value: Any, field: str, maximum: int, *, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return gate_model.history_model._public(value)


def _address_for(value: Any, prefix: str) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)


def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value)
    value._validate()
    return value


class EvidenceManifest:
    """Exact-file manifest for a release evidence package."""

    FIELDS = MANIFEST_FIELDS

    def __init__(self, evidence_id: str, gate_id: str, history_id: str, version: str, boundary: str, files: Sequence[str], artifact_addresses: Sequence[str], content_address: str) -> None:
        self.evidence_id = _label(evidence_id, "evidence manifest ID")
        self.gate_id = _label(gate_id, "evidence manifest gate ID")
        self.history_id = _label(history_id, "evidence manifest history ID")
        self.version = _text(version, "evidence manifest version", 1024)
        self.boundary = _text(boundary, "evidence manifest boundary", 2048)
        self.files = tuple(_text(item, "evidence manifest file", 128) for item in _sequence(files, "evidence manifest files", MAX_FILES))
        self.artifact_addresses = tuple(_address(item, "evidence manifest artifact address") for item in _sequence(artifact_addresses, "evidence manifest artifact addresses", MAX_FILES))
        self.content_address = _address(content_address, "evidence manifest address", MANIFEST_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.files != FILES or self.artifact_addresses and len(self.artifact_addresses) != len(ARTIFACT_FILES):
            raise ValidationError("evidence manifest file set is not canonical")
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("evidence manifest version or boundary is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, MANIFEST_PREFIX) != self.content_address:
            raise ValidationError("evidence manifest address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("evidence manifest crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "EvidenceManifest":
        value = _mapping(value, "evidence manifest")
        _strict(value, set(cls.FIELDS), "evidence manifest")
        return cls(*(value[field] for field in cls.FIELDS))


def address_manifest(value: EvidenceManifest) -> str:
    if not isinstance(value, EvidenceManifest):
        raise ValidationError("evidence manifest address requires a typed manifest")
    return _address_for(value, MANIFEST_PREFIX)


class EvidenceSummary:
    """Compact disposition and completeness projection for evidence."""

    FIELDS = SUMMARY_FIELDS

    def __init__(self, evidence_id: str, gate_id: str, history_id: str, gate_state: str, release_ready: bool, gate_audit_accepted: bool, query_audit_accepted: bool, query_complete: bool, evidence_ready: bool, check_count: int, passed_count: int, row_count: int, total_row_count: int, resource_count: int, content_address: str) -> None:
        self.evidence_id = _label(evidence_id, "evidence summary ID")
        self.gate_id = _label(gate_id, "evidence summary gate ID")
        self.history_id = _label(history_id, "evidence summary history ID")
        if gate_state not in STATES:
            raise ValidationError("evidence summary state is unsupported")
        self.gate_state = gate_state
        self.release_ready = _bool(release_ready, "evidence summary release readiness")
        self.gate_audit_accepted = _bool(gate_audit_accepted, "evidence summary gate audit acceptance")
        self.query_audit_accepted = _bool(query_audit_accepted, "evidence summary query audit acceptance")
        self.query_complete = _bool(query_complete, "evidence summary query completeness")
        self.evidence_ready = _bool(evidence_ready, "evidence summary readiness")
        self.check_count = _count(check_count, "evidence summary check count", gate_model.MAX_CHECKS)
        self.passed_count = _count(passed_count, "evidence summary passed count", gate_model.MAX_CHECKS)
        self.row_count = _count(row_count, "evidence summary row count", query_model.MAX_ROWS)
        self.total_row_count = _count(total_row_count, "evidence summary total row count", query_model.MAX_ROWS)
        self.resource_count = _count(resource_count, "evidence summary resource count", len(query_model.RESOURCES))
        self.content_address = _address(content_address, "evidence summary address", SUMMARY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.passed_count > self.check_count or self.row_count > self.total_row_count:
            raise ValidationError("evidence summary counters are inconsistent")
        expected = self.release_ready and self.gate_audit_accepted and self.query_audit_accepted and self.query_complete
        if self.evidence_ready != expected:
            raise ValidationError("evidence summary readiness does not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, SUMMARY_PREFIX) != self.content_address:
            raise ValidationError("evidence summary address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("evidence summary crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS[:-1]} | {"content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "EvidenceSummary":
        value = _mapping(value, "evidence summary")
        _strict(value, set(cls.FIELDS), "evidence summary")
        return cls(*(value[field] for field in cls.FIELDS))


def address_summary(value: EvidenceSummary) -> str:
    if not isinstance(value, EvidenceSummary):
        raise ValidationError("evidence summary address requires a typed summary")
    return _address_for(value, SUMMARY_PREFIX)


class ReleaseEvidence:
    """Canonical evidence package joining one gate and both independent audits."""

    FIELDS = EVIDENCE_FIELDS

    def __init__(self, evidence_id: str, gate_id: str, history_id: str, gate_address: str, gate_audit_address: str, query_address: str, query_audit_address: str, version: str, boundary: str, gate: Mapping[str, Any] | gate_model.ReleaseGate, gate_audit: Mapping[str, Any] | gate_audit_model.GateAudit, query: Mapping[str, Any] | query_model.GateQuery, query_audit: Mapping[str, Any] | query_audit_model.QueryAudit, manifest: Mapping[str, Any] | EvidenceManifest, summary: Mapping[str, Any] | EvidenceSummary, content_address: str) -> None:
        self.evidence_id = _label(evidence_id, "release evidence ID")
        self.gate_id = _label(gate_id, "release evidence gate ID")
        self.history_id = _label(history_id, "release evidence history ID")
        self.gate_address = _address(gate_address, "release evidence gate address", gate_model.GATE_PREFIX)
        self.gate_audit_address = _address(gate_audit_address, "release evidence gate audit address", gate_audit_model.AUDIT_PREFIX)
        self.query_address = _address(query_address, "release evidence query address", query_model.QUERY_PREFIX)
        self.query_audit_address = _address(query_audit_address, "release evidence query audit address", query_audit_model.AUDIT_PREFIX)
        self.version = _text(version, "release evidence version", 1024)
        self.boundary = _text(boundary, "release evidence boundary", 2048)
        self.gate = gate if isinstance(gate, gate_model.ReleaseGate) else gate_model.gate_from_mapping(_mapping(gate, "release evidence gate"))
        self.gate_audit = gate_audit if isinstance(gate_audit, gate_audit_model.GateAudit) else gate_audit_model.audit_from_mapping(_mapping(gate_audit, "release evidence gate audit"))
        self.query = query if isinstance(query, query_model.GateQuery) else query_model.query_from_mapping(_mapping(query, "release evidence query"))
        self.query_audit = query_audit if isinstance(query_audit, query_audit_model.QueryAudit) else query_audit_model.audit_from_mapping(_mapping(query_audit, "release evidence query audit"))
        self.manifest = manifest if isinstance(manifest, EvidenceManifest) else EvidenceManifest.from_mapping(_mapping(manifest, "release evidence manifest"))
        self.summary = summary if isinstance(summary, EvidenceSummary) else EvidenceSummary.from_mapping(_mapping(summary, "release evidence summary"))
        self.content_address = _address(content_address, "release evidence address", EVIDENCE_PREFIX)
        self._validate()

    def _validate(self) -> None:
        gate_model.verify_gate(self.gate)
        gate_audit_model.verify_audit(self.gate_audit)
        self.query._validate()
        query_audit_model.verify_audit(self.query_audit)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("release evidence version or boundary is unsupported")
        if (self.gate_id, self.history_id, self.gate_address) != (self.gate.gate_id, self.gate.history_id, self.gate.content_address):
            raise ValidationError("release evidence gate identity does not replay")
        if (self.gate_audit.gate_id, self.gate_audit.history_id, self.gate_audit.gate_address, self.gate_audit.history_address) != (self.gate.gate_id, self.gate.history_id, self.gate.content_address, self.gate.history_address):
            raise ValidationError("release evidence gate audit link does not replay")
        if (self.query.gate_id, self.query.history_id, self.query_address) != (self.gate.gate_id, self.gate.history_id, self.query.content_address):
            raise ValidationError("release evidence query link does not replay")
        if (self.query_audit.query_id, self.query_audit.gate_id, self.query_audit.history_id, self.query_audit.query_address, self.query_audit.gate_address) != (self.query.query_id, self.gate.gate_id, self.gate.history_id, self.query.content_address, self.gate.content_address):
            raise ValidationError("release evidence query audit link does not replay")
        expected_summary = (
            self.evidence_id,
            self.gate.gate_id,
            self.gate.history_id,
            self.gate.state,
            self.gate.release_ready,
            self.gate_audit.accepted,
            self.query_audit.accepted,
            not self.query.truncated and self.query.returned_count == self.query.total_count,
            self.summary.evidence_ready,
            self.gate.check_count,
            self.gate.passed_count,
            self.query.returned_count,
            self.query.total_count,
            len(self.query.resources),
        )
        actual_summary = tuple(getattr(self.summary, field) for field in SUMMARY_FIELDS[:-1])
        if actual_summary != expected_summary:
            raise ValidationError("release evidence summary does not replay")
        expected_manifest = (
            self.evidence_id,
            self.gate.gate_id,
            self.gate.history_id,
            VERSION,
            BOUNDARY,
            FILES,
            (self.gate.content_address, self.gate_audit.content_address, self.query.content_address, self.query_audit.content_address, self.summary.content_address),
        )
        actual_manifest = (self.manifest.evidence_id, self.manifest.gate_id, self.manifest.history_id, self.manifest.version, self.manifest.boundary, self.manifest.files, self.manifest.artifact_addresses)
        if actual_manifest != expected_manifest:
            raise ValidationError("release evidence manifest does not replay")
        if not self.content_address.startswith("pending:") and _address_for(self, EVIDENCE_PREFIX) != self.content_address:
            raise ValidationError("release evidence address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("release evidence crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "gate_id": self.gate_id,
            "history_id": self.history_id,
            "gate_address": self.gate_address,
            "gate_audit_address": self.gate_audit_address,
            "query_address": self.query_address,
            "query_audit_address": self.query_audit_address,
            "version": self.version,
            "boundary": self.boundary,
            "gate": self.gate.to_dict(),
            "gate_audit": self.gate_audit.to_dict(),
            "query": self.query.to_dict(),
            "query_audit": self.query_audit.to_dict(),
            "manifest": self.manifest.to_dict(),
            "summary": self.summary.to_dict(),
            "content_address": self.content_address,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ReleaseEvidence":
        value = _mapping(value, "release evidence")
        _strict(value, set(cls.FIELDS), "release evidence")
        return cls(*(value[field] for field in cls.FIELDS))


def address_evidence(value: ReleaseEvidence) -> str:
    if not isinstance(value, ReleaseEvidence):
        raise ValidationError("release evidence address requires a typed evidence package")
    return _address_for(value, EVIDENCE_PREFIX)


def build_evidence(gate: gate_model.ReleaseGate, gate_audit: gate_audit_model.GateAudit, query: query_model.GateQuery, query_audit: query_audit_model.QueryAudit, *, evidence_id: str = DEFAULT_EVIDENCE_ID) -> ReleaseEvidence:
    gate_model.verify_gate(gate)
    gate_audit_model.verify_audit(gate_audit)
    query._validate()
    query_audit_model.verify_audit(query_audit)
    evidence_id = _label(evidence_id, "release evidence ID")
    query_complete = not query.truncated and query.returned_count == query.total_count
    evidence_ready = gate.release_ready and gate_audit.accepted and query_audit.accepted and query_complete
    summary = EvidenceSummary(evidence_id, gate.gate_id, gate.history_id, gate.state, gate.release_ready, gate_audit.accepted, query_audit.accepted, query_complete, evidence_ready, gate.check_count, gate.passed_count, query.returned_count, query.total_count, len(query.resources), f"pending:{SUMMARY_PREFIX}")
    summary = _seal(summary, address_summary)
    manifest = EvidenceManifest(evidence_id, gate.gate_id, gate.history_id, VERSION, BOUNDARY, FILES, (gate.content_address, gate_audit.content_address, query.content_address, query_audit.content_address, summary.content_address), f"pending:{MANIFEST_PREFIX}")
    manifest = _seal(manifest, address_manifest)
    value = ReleaseEvidence(evidence_id, gate.gate_id, gate.history_id, gate.content_address, gate_audit.content_address, query.content_address, query_audit.content_address, VERSION, BOUNDARY, gate, gate_audit, query, query_audit, manifest, summary, f"pending:{EVIDENCE_PREFIX}")
    return _seal(value, address_evidence)


def verify_evidence(value: ReleaseEvidence) -> ReleaseEvidence:
    if not isinstance(value, ReleaseEvidence):
        raise ValidationError("release evidence verification requires a typed package")
    value._validate()
    return value


def evidence_from_mapping(value: Mapping[str, Any]) -> ReleaseEvidence:
    return ReleaseEvidence.from_mapping(value)


def evidence_json(value: ReleaseEvidence) -> str:
    return canonical_json(verify_evidence(value).to_dict())


def manifest_json(value: ReleaseEvidence) -> str:
    return canonical_json(verify_evidence(value).manifest.to_dict())


def summary_json(value: ReleaseEvidence) -> str:
    return canonical_json(verify_evidence(value).summary.to_dict())


def evidence_csv(value: ReleaseEvidence) -> str:
    value = verify_evidence(value)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=SUMMARY_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerow(value.summary.to_dict())
    return output.getvalue()


def render_evidence_markdown(value: ReleaseEvidence) -> str:
    value = verify_evidence(value)
    lines = [
        f"# Downloaded-data quality release evidence {value.evidence_id}",
        "",
        f"- State: {value.summary.gate_state}",
        f"- Release ready: {str(value.summary.release_ready).lower()}",
        f"- Evidence ready: {str(value.summary.evidence_ready).lower()}",
        f"- Gate audit accepted: {str(value.summary.gate_audit_accepted).lower()}",
        f"- Query audit accepted: {str(value.summary.query_audit_accepted).lower()}",
        f"- Query complete: {str(value.summary.query_complete).lower()}",
        f"- Checks: {value.summary.passed_count}/{value.summary.check_count}",
        f"- Query rows: {value.summary.row_count}/{value.summary.total_row_count}",
        f"- Resources: {value.summary.resource_count}",
        "",
        "## Artifact addresses",
        "",
        f"- Gate: `{value.gate_address}`",
        f"- Gate audit: `{value.gate_audit_address}`",
        f"- Query: `{value.query_address}`",
        f"- Query audit: `{value.query_audit_address}`",
    ]
    return "\n".join(lines) + "\n"


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(canonical_json(value), encoding="utf-8", newline="\n")


def persist_evidence(value: ReleaseEvidence, destination: str | Path, *, overwrite: bool = False) -> Path:
    value = verify_evidence(value)
    destination = Path(destination)
    _validate_parent(destination.parent, "release evidence destination")
    if destination.is_symlink() or (destination.exists() and (not destination.is_dir() or not overwrite)):
        raise ValidationError("release evidence destination exists or is not a directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".downloaded-data-quality-release-evidence-", dir=str(destination.parent)))
    documents = {
        "manifest.json": value.manifest.to_dict(),
        "evidence.json": value.to_dict(),
        "gate.json": value.gate.to_dict(),
        "gate-audit.json": value.gate_audit.to_dict(),
        "query.json": value.query.to_dict(),
        "query-audit.json": value.query_audit.to_dict(),
        "summary.json": value.summary.to_dict(),
    }
    try:
        for name in FILES:
            _write(temporary / name, documents[name])
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ValidationError("release evidence destination could not be written") from error
    return destination


def _read_json(path: Path) -> Mapping[str, Any]:
    try:
        value = _strict_json_loads(read_text(path, field="release evidence artifact"))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ValidationError("release evidence artifact is not valid JSON") from error
    return _mapping(value, "release evidence artifact")


def load_evidence(destination: str | Path) -> ReleaseEvidence:
    destination = Path(destination)
    _validate_parent(destination.parent, "release evidence input")
    if not destination.is_dir() or destination.is_symlink():
        raise ValidationError("release evidence source must be a regular directory")
    children = tuple(destination.iterdir())
    if tuple(sorted(item.name for item in children)) != tuple(sorted(FILES)) or any(item.is_symlink() or not item.is_file() for item in children):
        raise ValidationError("release evidence directory must contain the exact regular file set")
    documents = {name: _read_json(destination / name) for name in FILES}
    for name, document in documents.items():
        serialized = canonical_json(document)
        if read_text(destination / name, field="release evidence artifact") != serialized:
            raise ValidationError("release evidence artifact is not canonical")
        if len(serialized.encode("utf-8")) > MAX_EVIDENCE_BYTES:
            raise ValidationError("release evidence artifact exceeds its size bound")
    value = evidence_from_mapping(documents["evidence.json"])
    expected = {
        "manifest.json": value.manifest.to_dict(),
        "gate.json": value.gate.to_dict(),
        "gate-audit.json": value.gate_audit.to_dict(),
        "query.json": value.query.to_dict(),
        "query-audit.json": value.query_audit.to_dict(),
        "summary.json": value.summary.to_dict(),
    }
    if any(canonical_json(documents[name]) != canonical_json(expected[name]) for name in expected):
        raise ValidationError("release evidence component documents do not replay evidence.json")
    return value


def run_evidence(gate: gate_model.ReleaseGate, gate_audit: gate_audit_model.GateAudit, query: query_model.GateQuery, query_audit: query_audit_model.QueryAudit, *, evidence_id: str = DEFAULT_EVIDENCE_ID, destination: str | Path | None = None, overwrite: bool = False) -> ReleaseEvidence:
    value = build_evidence(gate, gate_audit, query, query_audit, evidence_id=evidence_id)
    if destination is not None:
        persist_evidence(value, destination, overwrite=overwrite)
    return value


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "EvidenceManifest", "type": "object", "additionalProperties": False, "required": list(MANIFEST_FIELDS), "properties": {field: {"type": "array" if field in ("files", "artifact_addresses") else "string"} for field in MANIFEST_FIELDS}}


def summary_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "EvidenceSummary", "type": "object", "additionalProperties": False, "required": list(SUMMARY_FIELDS), "properties": {"evidence_id": {"type": "string"}, "gate_id": {"type": "string"}, "history_id": {"type": "string"}, "gate_state": {"enum": list(STATES)}, "release_ready": {"type": "boolean"}, "gate_audit_accepted": {"type": "boolean"}, "query_audit_accepted": {"type": "boolean"}, "query_complete": {"type": "boolean"}, "evidence_ready": {"type": "boolean"}, "check_count": {"type": "integer"}, "passed_count": {"type": "integer"}, "row_count": {"type": "integer"}, "total_row_count": {"type": "integer"}, "resource_count": {"type": "integer"}, "content_address": {"type": "string"}}}


def evidence_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ReleaseEvidence", "type": "object", "additionalProperties": False, "required": list(EVIDENCE_FIELDS), "properties": {"evidence_id": {"type": "string"}, "gate_id": {"type": "string"}, "history_id": {"type": "string"}, "gate_address": {"type": "string"}, "gate_audit_address": {"type": "string"}, "query_address": {"type": "string"}, "query_audit_address": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "gate": {"type": "object"}, "gate_audit": {"type": "object"}, "query": {"type": "object"}, "query_audit": {"type": "object"}, "manifest": {"type": "object"}, "summary": {"type": "object"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "files": FILES, "artifact_files": ARTIFACT_FILES, "states": STATES, "max_evidence_bytes": MAX_EVIDENCE_BYTES, "features": ("gate and audit composition", "complete query evidence", "cross-artifact identity replay", "exact seven-file persistence", "canonical reload and tamper rejection", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}


__all__ = ["VERSION", "BOUNDARY", "EVIDENCE_PREFIX", "MANIFEST_PREFIX", "SUMMARY_PREFIX", "DEFAULT_EVIDENCE_ID", "FILES", "ARTIFACT_FILES", "STATES", "MAX_EVIDENCE_BYTES", "MAX_FILES", "MANIFEST_FIELDS", "SUMMARY_FIELDS", "EVIDENCE_FIELDS", "EvidenceManifest", "EvidenceSummary", "ReleaseEvidence", "address_manifest", "address_summary", "address_evidence", "build_evidence", "verify_evidence", "evidence_from_mapping", "evidence_json", "manifest_json", "summary_json", "evidence_csv", "render_evidence_markdown", "persist_evidence", "load_evidence", "run_evidence", "manifest_schema", "summary_schema", "evidence_schema", "capabilities"]
