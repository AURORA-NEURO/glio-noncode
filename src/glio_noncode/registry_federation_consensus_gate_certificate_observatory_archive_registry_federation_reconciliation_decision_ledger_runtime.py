"""Persisted decision-ledger runtime for reconciliation handoffs.

This module composes a verified reconciliation plan, its independent plan
audit, an explicit decision ledger, a ledger audit, a bounded query, and a
query audit.  It is the read-only closure that a separate executor or review
process can consume.  The runtime never edits a plan, a registry, or a source
archive; a new decision set produces a new content address.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import (
    registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_decision_ledger as ledger_model,
)
from . import (
    registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_decision_ledger_audit as ledger_audit_model,
)
from . import (
    registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_decision_ledger_query as query_model,
)
from . import (
    registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_decision_ledger_query_audit as query_audit_model,
)
from . import (
    registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_plan as plan_model,
)
from . import (
    registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_plan_audit as plan_audit_model,
)
from . import (
    registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_runtime as reconciliation_runtime_model,
)
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

VERSION = ledger_model.VERSION + "-runtime-v1"
BOUNDARY = ledger_model.BOUNDARY + "_runtime"
RUNTIME_PREFIX = ledger_model.LEDGER_PREFIX + "-runtime"
MANIFEST_PREFIX = RUNTIME_PREFIX + "-manifest"
ARTIFACT_PREFIX = RUNTIME_PREFIX + "-artifact"
DEFAULT_RUNTIME_ID = "consensus-certificate-observatory-archive-registry-federation-reconciliation-decision-ledger-runtime"
MANIFEST_NAME = "manifest.json"
RUNTIME_NAME = "runtime.json"
PLAN_NAME = "plan.json"
PLAN_AUDIT_NAME = "plan-audit.json"
LEDGER_NAME = "ledger.json"
LEDGER_AUDIT_NAME = "ledger-audit.json"
QUERY_NAME = "query.json"
QUERY_AUDIT_NAME = "query-audit.json"
FILES = (MANIFEST_NAME, RUNTIME_NAME, PLAN_NAME, PLAN_AUDIT_NAME, LEDGER_NAME, LEDGER_AUDIT_NAME, QUERY_NAME, QUERY_AUDIT_NAME)
MAX_DECISIONS = ledger_model.MAX_DECISIONS


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or ":" not in value:
        raise ValidationError(f"{field} must be a public content address")
    if prefix is not None and not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has the wrong address namespace")
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


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    return ledger_model._public(value)


class RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntime:
    """Complete persisted decision-ledger closure."""

    FIELDS = (
        "runtime_id",
        "version",
        "boundary",
        "plan",
        "plan_audit",
        "ledger",
        "ledger_audit",
        "query",
        "query_audit",
        "operation_count",
        "decision_count",
        "ledger_accepted",
        "accepted",
        "release_ready",
        "state",
        "content_address",
    )

    def __init__(self, runtime_id: str, version: str, boundary: str, plan: plan_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan, plan_audit: plan_audit_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlanAudit, ledger: ledger_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedger, ledger_audit: ledger_audit_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerAudit, query: query_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryResult, query_audit: query_audit_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerQueryAudit, operation_count: int, decision_count: int, ledger_accepted: bool, accepted: bool, release_ready: bool, state: str, content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "decision ledger runtime ID")
        self.version = _text(version, "decision ledger runtime version")
        self.boundary = _text(boundary, "decision ledger runtime boundary", 512)
        self.plan = plan_model.verify_plan(plan)
        self.plan_audit = plan_audit_model.verify_audit(plan_audit)
        self.ledger = ledger_model.verify_ledger(ledger)
        self.ledger_audit = ledger_audit_model.verify_audit(ledger_audit)
        self.query = query_model.verify_query_result(query)
        self.query_audit = query_audit_model.verify_audit(query_audit)
        self.operation_count = _count(operation_count, "decision ledger runtime operation count", MAX_DECISIONS, positive=True)
        self.decision_count = _count(decision_count, "decision ledger runtime decision count", MAX_DECISIONS, positive=True)
        self.ledger_accepted = _bool(ledger_accepted, "decision ledger runtime ledger acceptance")
        self.accepted = _bool(accepted, "decision ledger runtime acceptance")
        self.release_ready = _bool(release_ready, "decision ledger runtime release readiness")
        self.state = _label(state, "decision ledger runtime state")
        self.content_address = _address(content_address, "decision ledger runtime address", RUNTIME_PREFIX) if not str(content_address).endswith(":pending") else _text(content_address, "decision ledger runtime address")
        self._validate()

    def _validate(self) -> None:
        if self.operation_count != self.plan.operation_count or self.decision_count != self.ledger.decision_count or self.operation_count != self.decision_count:
            raise ValidationError("decision ledger runtime counts do not replay")
        if self.plan_audit.plan_address != self.plan.content_address or self.ledger.plan_address != self.plan.content_address or self.ledger_audit.plan_address != self.plan.content_address:
            raise ValidationError("decision ledger runtime plan links do not replay")
        if self.ledger_audit.ledger_address != self.ledger.content_address or self.query.query.ledger_address != self.ledger.content_address or self.query_audit.ledger_address != self.ledger.content_address:
            raise ValidationError("decision ledger runtime ledger links do not replay")
        if self.query_audit.result_address != self.query.content_address:
            raise ValidationError("decision ledger runtime query link does not replay")
        if self.ledger_accepted != self.ledger.accepted or self.accepted != (self.plan_audit.accepted and self.ledger_audit.accepted and self.query_audit.accepted) or self.release_ready != self.ledger.release_ready or self.state != self.ledger.state:
            raise ValidationError("decision ledger runtime outcome does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("decision ledger runtime crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_runtime(self) != self.content_address:
            raise ValidationError("decision ledger runtime address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_id": self.runtime_id,
            "version": self.version,
            "boundary": self.boundary,
            "plan": self.plan.to_dict(),
            "plan_audit": self.plan_audit.to_dict(),
            "ledger": self.ledger.to_dict(),
            "ledger_audit": self.ledger_audit.to_dict(),
            "query": self.query.to_dict(),
            "query_audit": self.query_audit.to_dict(),
            "operation_count": self.operation_count,
            "decision_count": self.decision_count,
            "ledger_accepted": self.ledger_accepted,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "state": self.state,
            "content_address": self.content_address,
        }

    def summary(self) -> dict[str, Any]:
        return {"runtime_id": self.runtime_id, "plan_id": self.plan.plan_id, "plan_address": self.plan.content_address, "ledger_id": self.ledger.ledger_id, "ledger_address": self.ledger.content_address, "operation_count": self.operation_count, "decision_count": self.decision_count, "pending_count": self.ledger.pending_count, "approved_count": self.ledger.approved_count, "held_count": self.ledger.held_count, "rejected_count": self.ledger.rejected_count, "deferred_count": self.ledger.deferred_count, "not_required_count": self.ledger.not_required_count, "ledger_accepted": self.ledger_accepted, "accepted": self.accepted, "release_ready": self.release_ready, "state": self.state, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntime:
        value = _mapping(value, "decision ledger runtime")
        _strict(value, set(cls.FIELDS), "decision ledger runtime")
        return cls(value["runtime_id"], value["version"], value["boundary"], plan_model.plan_from_mapping(value["plan"]), plan_audit_model.audit_from_mapping(value["plan_audit"]), ledger_model.ledger_from_mapping(value["ledger"]), ledger_audit_model.audit_from_mapping(value["ledger_audit"]), query_model.query_from_mapping(value["query"]), query_audit_model.audit_from_mapping(value["query_audit"]), value["operation_count"], value["decision_count"], value["ledger_accepted"], value["accepted"], value["release_ready"], value["state"], value["content_address"])


def address_runtime(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntime) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RUNTIME_PREFIX)


def build_runtime(plan: plan_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan, decisions: Sequence[Any] | Mapping[str, Any] | None = None, *, runtime_id: str = DEFAULT_RUNTIME_ID, ledger_id: str = ledger_model.DEFAULT_LEDGER_ID, resources: Sequence[str] = ("summary", "decisions"), limit: int = query_model.DEFAULT_LIMIT) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntime:
    plan = plan_model.verify_plan(plan)
    plan_audit = plan_audit_model.audit_plan(plan)
    ledger = ledger_model.build_ledger(plan, decisions, ledger_id=ledger_id)
    ledger_audit = ledger_audit_model.audit_ledger(ledger)
    query = query_model.query_ledger(ledger, resources=resources, limit=limit)
    query_audit = query_audit_model.audit_query(query)
    body = {"runtime_id": runtime_id, "version": VERSION, "boundary": BOUNDARY, "plan": plan, "plan_audit": plan_audit, "ledger": ledger, "ledger_audit": ledger_audit, "query": query, "query_audit": query_audit, "operation_count": plan.operation_count, "decision_count": ledger.decision_count, "ledger_accepted": ledger.accepted, "accepted": plan_audit.accepted and ledger_audit.accepted and query_audit.accepted, "release_ready": ledger.release_ready, "state": ledger.state}
    provisional = RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntime(**body, content_address=RUNTIME_PREFIX + ":pending")
    return RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntime(**body, content_address=address_runtime(provisional))


def _load_json_file(source: Path) -> Mapping[str, Any]:
    if source.is_symlink() or not source.is_file():
        raise ValidationError("decision ledger runtime plan source must be a regular file")
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("decision ledger runtime plan source JSON is invalid") from error
    return _mapping(value, "decision ledger runtime plan source JSON")


def load_plan_input(source: Any) -> plan_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan:
    """Load a plan JSON, a persisted decision runtime, or a prior plan runtime."""

    if isinstance(source, plan_model.RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationPlan):
        return plan_model.verify_plan(source)
    if isinstance(source, Mapping):
        value = _mapping(source, "decision ledger runtime plan input")
    else:
        path = Path(source)
        if path.is_symlink():
            raise ValidationError("decision ledger runtime plan input cannot be a symlink")
        if path.is_dir():
            plan_path = path / PLAN_NAME
            if plan_path.is_file():
                value = _load_json_file(plan_path)
            elif (path / reconciliation_runtime_model.RUNTIME_NAME).is_file():
                value = _load_json_file(path / reconciliation_runtime_model.RUNTIME_NAME)
            else:
                raise ValidationError("decision ledger runtime directory has no plan member")
        else:
            value = _load_json_file(path)
    if "plan_id" in value:
        return plan_model.plan_from_mapping(value)
    nested = value.get("plan")
    if isinstance(nested, Mapping):
        return plan_model.plan_from_mapping(nested)
    raise ValidationError("decision ledger runtime input is not a plan")


def run_runtime(plan_source: Any, decisions: Sequence[Any] | Mapping[str, Any] | None = None, *, runtime_id: str = DEFAULT_RUNTIME_ID, ledger_id: str = ledger_model.DEFAULT_LEDGER_ID, resources: Sequence[str] = ("summary", "decisions"), limit: int = query_model.DEFAULT_LIMIT, destination: str | Path | None = None, overwrite: bool = False) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntime:
    plan = load_plan_input(plan_source)
    value = build_runtime(plan, decisions, runtime_id=runtime_id, ledger_id=ledger_id, resources=resources, limit=limit)
    if destination is not None:
        write_runtime(value, destination, overwrite=overwrite)
    return value


def runtime_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntime:
    return verify_runtime(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntime.from_mapping(value))


def verify_runtime(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntime) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntime:
    if not isinstance(value, RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntime):
        raise ValidationError("decision ledger runtime verification requires a typed runtime")
    value._validate()
    if not value.content_address.endswith(":pending") and address_runtime(value) != value.content_address:
        raise ValidationError("decision ledger runtime address verification failed")
    return value


def runtime_json(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntime) -> str:
    return canonical_json(verify_runtime(value).to_dict())


def runtime_csv(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntime) -> str:
    value = verify_runtime(value)
    lines = ["field,value"]
    for key, field_value in value.summary().items():
        lines.append(f"{key},{json.dumps(field_value, ensure_ascii=False)}")
    return "\n".join(lines) + "\n"


def render_runtime_markdown(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntime) -> str:
    value = verify_runtime(value)
    lines = ["# Archive Registry Federation Reconciliation Decision Ledger Runtime", "", f"- State: `{value.state}`", f"- Accepted: `{value.accepted}`", f"- Ledger accepted: `{value.ledger_accepted}`", f"- Release ready: `{value.release_ready}`", f"- Operations: `{value.operation_count}`", f"- Pending: `{value.ledger.pending_count}`", f"- Approved: `{value.ledger.approved_count}`", f"- Held: `{value.ledger.held_count}`", f"- Rejected: `{value.ledger.rejected_count}`", f"- Deferred: `{value.ledger.deferred_count}`", f"- No disposition required: `{value.ledger.not_required_count}`", f"- Runtime address: `{value.content_address}`", "", ledger_model.render_ledger_markdown(value.ledger)]
    return "\n".join(lines) + "\n"


def _artifact(name: str, raw: bytes) -> dict[str, Any]:
    return {"name": name, "size": len(raw), "hash": hash_bytes(raw, prefix=ARTIFACT_PREFIX)}


def _payload(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntime) -> dict[str, bytes]:
    value = verify_runtime(value)
    return {RUNTIME_NAME: canonical_bytes(value.to_dict()), PLAN_NAME: canonical_bytes(value.plan.to_dict()), PLAN_AUDIT_NAME: canonical_bytes(value.plan_audit.to_dict()), LEDGER_NAME: canonical_bytes(value.ledger.to_dict()), LEDGER_AUDIT_NAME: canonical_bytes(value.ledger_audit.to_dict()), QUERY_NAME: canonical_bytes(value.query.to_dict()), QUERY_AUDIT_NAME: canonical_bytes(value.query_audit.to_dict())}


def manifest_document(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntime) -> dict[str, Any]:
    value = verify_runtime(value)
    payload = _payload(value)
    body = {"version": VERSION, "boundary": BOUNDARY, "runtime_id": value.runtime_id, "runtime_address": value.content_address, "files": FILES, "artifacts": tuple(_artifact(name, payload[name]) for name in FILES[1:])}
    return body | {"manifest_address": content_hash(body | {"manifest_address": None}, prefix=MANIFEST_PREFIX)}


def runtime_bytes(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntime) -> Mapping[str, bytes]:
    payload = _payload(value)
    return {MANIFEST_NAME: canonical_bytes(manifest_document(value)), **payload}


def _write_atomic_directory(destination: Path, payload: Mapping[str, bytes], *, overwrite: bool) -> Path:
    if destination.exists() and (destination.is_symlink() or not destination.is_dir() or (not overwrite and any(destination.iterdir()))):
        raise ValidationError("decision ledger runtime destination is not writable")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="decision-ledger-runtime-staging-", dir=str(destination.parent)))
    try:
        for name in FILES:
            (staging / name).write_bytes(payload[name])
        if destination.exists():
            backup = Path(tempfile.mkdtemp(prefix="decision-ledger-runtime-backup-", dir=str(destination.parent)))
            backup.rmdir()
            os.replace(destination, backup)
            try:
                os.replace(staging, destination)
            except Exception:
                os.replace(backup, destination)
                raise
            shutil.rmtree(backup)
        else:
            os.replace(staging, destination)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination


def write_runtime(value: RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntime, destination: str | Path, *, overwrite: bool = False) -> Path:
    return _write_atomic_directory(Path(destination), runtime_bytes(value), overwrite=overwrite)


def _read_directory(source: str | Path) -> dict[str, bytes]:
    path = Path(source)
    if path.is_symlink() or not path.is_dir():
        raise ValidationError("decision ledger runtime input must be a regular directory")
    names = tuple(item.name for item in path.iterdir())
    if set(names) != set(FILES) or len(names) != len(FILES):
        raise ValidationError("decision ledger runtime member set is not exact")
    result: dict[str, bytes] = {}
    for name in FILES:
        member = path / name
        if member.is_symlink() or not member.is_file():
            raise ValidationError("decision ledger runtime member must be a regular file")
        result[name] = member.read_bytes()
    return result


def load_runtime(source: str | Path) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntime:
    raw = _read_directory(source)
    try:
        decoded = {name: json.loads(value.decode("utf-8")) for name, value in raw.items()}
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError("decision ledger runtime contains invalid JSON") from error
    if any(canonical_bytes(decoded[name]) != raw[name] for name in FILES):
        raise ValidationError("decision ledger runtime contains non-canonical JSON")
    manifest = _mapping(decoded[MANIFEST_NAME], "decision ledger runtime manifest")
    _strict(manifest, {"version", "boundary", "runtime_id", "runtime_address", "files", "artifacts", "manifest_address"}, "decision ledger runtime manifest")
    if tuple(manifest["files"]) != FILES or manifest["manifest_address"] != content_hash(dict(manifest) | {"manifest_address": None}, prefix=MANIFEST_PREFIX):
        raise ValidationError("decision ledger runtime manifest does not replay")
    artifacts = _sequence(manifest["artifacts"], "decision ledger runtime artifacts", len(FILES) - 1)
    if len(artifacts) != len(FILES) - 1:
        raise ValidationError("decision ledger runtime artifact count does not replay")
    for item in artifacts:
        item = _mapping(item, "decision ledger runtime artifact")
        _strict(item, {"name", "size", "hash"}, "decision ledger runtime artifact")
        name = item["name"]
        if name not in FILES[1:] or item["size"] != len(raw[name]) or item["hash"] != hash_bytes(raw[name], prefix=ARTIFACT_PREFIX):
            raise ValidationError("decision ledger runtime artifact receipt does not replay")
    value = runtime_from_mapping(decoded[RUNTIME_NAME])
    if value.runtime_id != manifest["runtime_id"] or value.content_address != manifest["runtime_address"]:
        raise ValidationError("decision ledger runtime manifest links do not replay")
    expected = {PLAN_NAME: value.plan.to_dict(), PLAN_AUDIT_NAME: value.plan_audit.to_dict(), LEDGER_NAME: value.ledger.to_dict(), LEDGER_AUDIT_NAME: value.ledger_audit.to_dict(), QUERY_NAME: value.query.to_dict(), QUERY_AUDIT_NAME: value.query_audit.to_dict()}
    if any(raw[name] != canonical_bytes(body) for name, body in expected.items()):
        raise ValidationError("decision ledger runtime projections do not replay")
    return value


def verify_runtime_directory(source: str | Path) -> RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntime:
    return load_runtime(source)


def manifest_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": ["version", "boundary", "runtime_id", "runtime_address", "files", "artifacts", "manifest_address"], "properties": {"version": {"type": "string"}, "boundary": {"type": "string"}, "runtime_id": {"type": "string"}, "runtime_address": {"type": "string"}, "files": {"type": "array", "items": {"type": "string"}}, "artifacts": {"type": "array", "items": {"type": "object"}}, "manifest_address": {"type": "string"}}}


def runtime_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntime.FIELDS), "properties": {"runtime_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "plan": plan_model.plan_schema(), "plan_audit": plan_audit_model.audit_schema(), "ledger": ledger_model.ledger_schema(), "ledger_audit": ledger_audit_model.audit_schema(), "query": query_model.result_schema(), "query_audit": query_audit_model.audit_schema(), "operation_count": {"type": "integer", "minimum": 1}, "decision_count": {"type": "integer", "minimum": 1}, "ledger_accepted": {"type": "boolean"}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "state": {"enum": list(ledger_model.STATES)}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "public": True, "bounded": True, "content_addressed": True, "analysis_only": True, "non_mutating": True, "operations": ("run_runtime", "build_runtime", "load_plan_input", "runtime_from_mapping", "runtime_json", "runtime_csv", "render_runtime_markdown", "write_runtime", "load_runtime", "verify_runtime_directory"), "files": FILES, "max_decisions": MAX_DECISIONS}


__all__ = [
    "ARTIFACT_PREFIX",
    "BOUNDARY",
    "DEFAULT_RUNTIME_ID",
    "FILES",
    "LEDGER_AUDIT_NAME",
    "LEDGER_NAME",
    "MANIFEST_NAME",
    "MANIFEST_PREFIX",
    "MAX_DECISIONS",
    "PLAN_AUDIT_NAME",
    "PLAN_NAME",
    "QUERY_AUDIT_NAME",
    "QUERY_NAME",
    "RUNTIME_NAME",
    "RUNTIME_PREFIX",
    "VERSION",
    "RegistryFederationConsensusGateCertificateObservatoryArchiveRegistryFederationReconciliationDecisionLedgerRuntime",
    "address_runtime",
    "build_runtime",
    "capabilities",
    "load_plan_input",
    "load_runtime",
    "manifest_document",
    "manifest_schema",
    "render_runtime_markdown",
    "run_runtime",
    "runtime_bytes",
    "runtime_csv",
    "runtime_from_mapping",
    "runtime_json",
    "runtime_schema",
    "verify_runtime",
    "verify_runtime_directory",
    "write_runtime",
]
