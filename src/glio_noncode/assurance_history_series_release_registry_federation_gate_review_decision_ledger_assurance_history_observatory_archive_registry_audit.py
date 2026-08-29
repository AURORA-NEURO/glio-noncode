"""Independent audit of persisted observatory archive registries.

The registry loader proves that a package can be rehydrated as a typed value.
This module adds an operator-facing audit that evaluates the raw five-file
package as a separate evidence surface. It reports structural, canonical
JSON, manifest, receipt, identity, linkage, metric, posture, public-boundary,
and verification results without exposing the input path.

An audit is deliberately useful for damaged packages. When a directory cannot
be loaded, the audit emits a valid public report with failed checks and stable
unresolved evidence addresses instead of turning a malformed package into an
unstructured exception. A complete audit means every check passed; it does
not imply that the registry's underlying observatories are scientifically or
clinically valid beyond their own contracts.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry as registry_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash


VERSION = registry_model.VERSION + "-audit-v1"
BOUNDARY = registry_model.BOUNDARY + "_audit"
AUDIT_PREFIX = registry_model.REGISTRY_PREFIX + "-audit"
AUDIT_CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "exact-members",
    "canonical-json",
    "manifest-contract",
    "artifact-receipts",
    "registry-linkage",
    "entry-linkage",
    "verification-linkage",
    "metrics-conservation",
    "posture-projection",
    "public-boundary",
    "content-address",
    "verification-checks",
)
STATES = ("complete", "incomplete")
MAX_CHECKS = len(CHECK_IDS)


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


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 2048)
    if ":" not in value or value.startswith(("/", "\\")) or "\\" in value or not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an invalid public namespace")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be a mapping")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _safe_address(value: Any, prefix: str, fallback: str) -> str:
    try:
        return _address(value, "evidence address", prefix)
    except ValidationError:
        return fallback


class RegistryAuditCheck:
    """One independently addressed assertion over a registry package."""

    def __init__(self, check_id: str, passed: bool, detail: str, evidence_address: str) -> None:
        self.check_id = _text(check_id, "registry audit check ID", 128)
        self.passed = _bool(passed, "registry audit check passed")
        self.detail = _text(detail, "registry audit check detail", 1024)
        self.evidence_address = _text(evidence_address, "registry audit check evidence address", 2048)
        self.content_address = content_hash({"check_id": self.check_id, "passed": self.passed, "detail": self.detail, "evidence_address": self.evidence_address}, prefix=AUDIT_CHECK_PREFIX)

    def to_dict(self) -> dict[str, Any]:
        return {"check_id": self.check_id, "passed": self.passed, "detail": self.detail, "evidence_address": self.evidence_address, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RegistryAuditCheck":
        value = _mapping(value, "registry audit check")
        _strict(value, {"check_id", "passed", "detail", "evidence_address", "content_address"}, "registry audit check")
        result = cls(value["check_id"], value["passed"], value["detail"], value["evidence_address"])
        if result.content_address != value["content_address"]:
            raise ValidationError("registry audit check content address mismatch")
        return result


class RegistryAudit:
    """Public report describing a complete or incomplete registry audit."""

    def __init__(self, registry_address: str, verification_address: str, state: str, complete: bool, accepted: bool, checks: Sequence[RegistryAuditCheck], content_address: str) -> None:
        self.registry_address = registry_address
        self.verification_address = verification_address
        self.state = state
        self.complete = complete
        self.accepted = accepted
        self.checks = tuple(checks)
        self.check_count = len(self.checks)
        self.passed_count = sum(check.passed for check in self.checks)
        self.failed_count = self.check_count - self.passed_count
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.registry_address, "registry audit registry address", registry_model.REGISTRY_PREFIX)
        _address(self.verification_address, "registry audit verification address", registry_model.REGISTRY_VERIFICATION_PREFIX)
        if self.state not in STATES or self.complete != (self.state == "complete"):
            raise ValidationError("registry audit state does not match completion")
        _bool(self.complete, "registry audit complete")
        _bool(self.accepted, "registry audit accepted")
        if tuple(check.check_id for check in self.checks) != CHECK_IDS or self.check_count != MAX_CHECKS:
            raise ValidationError("registry audit check set is invalid")
        _count(self.passed_count, "registry audit passed count", MAX_CHECKS)
        _count(self.failed_count, "registry audit failed count", MAX_CHECKS)
        if self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(check.passed for check in self.checks):
            raise ValidationError("registry audit counts are not conserved")
        if self.complete != (self.failed_count == 0) or self.accepted != self.complete:
            raise ValidationError("registry audit acceptance does not match checks")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "registry audit content address")
        else:
            _address(self.content_address, "registry audit content address", AUDIT_PREFIX)
        if not registry_model._public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_audit(self) != self.content_address):
            raise ValidationError("registry audit address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"registry_address": self.registry_address, "verification_address": self.verification_address, "state": self.state, "complete": self.complete, "accepted": self.accepted, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "checks": tuple(check.to_dict() for check in self.checks), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("registry_address", "verification_address", "state", "complete", "accepted", "check_count", "passed_count", "failed_count", "content_address")}


def address_audit(value: RegistryAudit) -> str:
    if not isinstance(value, RegistryAudit):
        raise ValidationError("registry audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, detail: str, evidence: str) -> RegistryAuditCheck:
    return RegistryAuditCheck(check_id, passed, detail, evidence)


def _object_documents(value: registry_model.ObservatoryArchiveRegistry) -> tuple[dict[str, bytes], dict[str, Mapping[str, Any]]]:
    if value._verification is None:
        raise ValidationError("registry audit requires an attached registry verification")
    payload = registry_model._registry_payload(value)
    manifest = registry_model._manifest(value, payload)
    payload = dict(payload)
    payload[registry_model.MANIFEST_NAME] = canonical_bytes(manifest)
    documents = {name: json.loads(payload[name].decode("utf-8")) for name in registry_model.FILES}
    return payload, documents


def _read_directory(source: str | Path) -> tuple[dict[str, bytes], set[str], bool]:
    try:
        directory = Path(source)
        if directory.is_symlink() or not directory.is_dir():
            return {}, set(), False
        members = tuple(directory.iterdir())
        names = {item.name for item in members}
        if any(item.is_symlink() or not item.is_file() for item in members):
            return {}, names, False
        payload = {name: (directory / name).read_bytes() for name in registry_model.FILES if (directory / name).is_file()}
        return payload, names, names == set(registry_model.FILES) and set(payload) == set(registry_model.FILES)
    except (OSError, ValueError):
        return {}, set(), False


def _decode_documents(payload: Mapping[str, bytes]) -> tuple[dict[str, Mapping[str, Any]], bool]:
    documents: dict[str, Mapping[str, Any]] = {}
    canonical = bool(payload) and set(payload) == set(registry_model.FILES)
    for name in registry_model.FILES:
        raw = payload.get(name)
        if raw is None:
            canonical = False
            continue
        try:
            document = json.loads(raw.decode("utf-8"))
            documents[name] = _mapping(document, f"registry {name}")
            if canonical_bytes(document) != raw:
                canonical = False
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError):
            canonical = False
    return documents, canonical


def _manifest_contract(manifest: Mapping[str, Any]) -> bool:
    try:
        _strict(manifest, {"version", "boundary", "registry_id", "registry_address", "verification_address", "artifact_count", "files", "artifacts", "manifest_address"}, "registry manifest")
        expected = content_hash(dict(manifest) | {"manifest_address": None}, prefix=registry_model.REGISTRY_MANIFEST_PREFIX)
        return manifest.get("version") == registry_model.VERSION and manifest.get("boundary") == registry_model.BOUNDARY and manifest.get("artifact_count") == len(registry_model.FILES) - 1 and manifest.get("files") == list(registry_model.FILES[1:]) and manifest.get("manifest_address") == expected
    except (ValidationError, TypeError):
        return False


def _artifact_receipts(manifest: Mapping[str, Any], payload: Mapping[str, bytes]) -> bool:
    try:
        artifacts = manifest.get("artifacts")
        if not isinstance(artifacts, list) or len(artifacts) != len(registry_model.FILES) - 1:
            return False
        for item in artifacts:
            item = _mapping(item, "registry artifact receipt")
            name = item.get("name")
            if name not in registry_model.FILES[1:] or name not in payload or dict(item) != registry_model._artifact(name, payload[name]):
                return False
        return {item["name"] for item in artifacts} == set(registry_model.FILES[1:])
    except (ValidationError, TypeError, KeyError):
        return False


def _typed_verification(document: Mapping[str, Any]) -> registry_model.RegistryVerification | None:
    try:
        checks = tuple(registry_model.RegistryVerificationCheck.from_mapping(item) for item in registry_model._sequence(document.get("checks"), "registry verification checks", MAX_CHECKS))
        return registry_model.RegistryVerification(document["verification_id"], document["registry_id"], document["registry_address"], document["state"], document["release_ready"], checks, document["content_address"])
    except (ValidationError, KeyError, TypeError):
        return None


def _audit_documents(payload: Mapping[str, bytes], documents: Mapping[str, Mapping[str, Any]], members_exact: bool) -> RegistryAudit:
    manifest = documents.get(registry_model.MANIFEST_NAME, {})
    registry_document = documents.get(registry_model.REGISTRY_NAME, {})
    entries_document = documents.get(registry_model.ENTRIES_NAME, {})
    verification_document = documents.get(registry_model.VERIFICATION_NAME, {})
    metrics_document = documents.get(registry_model.METRICS_NAME, {})
    typed_registry: registry_model.ObservatoryArchiveRegistry | None = None
    typed_verification: registry_model.RegistryVerification | None = None
    try:
        typed_registry = registry_model.registry_from_mapping(registry_document)
    except (ValidationError, KeyError, TypeError):
        pass
    typed_verification = _typed_verification(verification_document)
    fallback_registry = registry_model.REGISTRY_PREFIX + ":unresolved"
    fallback_verification = registry_model.REGISTRY_VERIFICATION_PREFIX + ":unresolved"
    registry_address = _safe_address(registry_document.get("content_address"), registry_model.REGISTRY_PREFIX, fallback_registry)
    verification_address = _safe_address(verification_document.get("content_address"), registry_model.REGISTRY_VERIFICATION_PREFIX, fallback_verification)
    if typed_registry is not None:
        registry_address = typed_registry.content_address
    if typed_verification is not None:
        verification_address = typed_verification.content_address

    canonical_ok = bool(payload) and set(payload) == set(registry_model.FILES) and set(documents) == set(registry_model.FILES) and all(canonical_bytes(documents[name]) == payload[name] for name in registry_model.FILES)
    manifest_ok = _manifest_contract(manifest)
    receipt_ok = _artifact_receipts(manifest, payload)
    registry_linkage_ok = typed_registry is not None and manifest.get("registry_id") == typed_registry.registry_id and manifest.get("registry_address") == typed_registry.content_address and manifest.get("verification_address") == typed_registry.verification_address and manifest.get("version") == typed_registry.version and manifest.get("boundary") == typed_registry.boundary
    entry_linkage_ok = typed_registry is not None and entries_document.get("version") == registry_model.VERSION and entries_document.get("boundary") == registry_model.BOUNDARY and entries_document.get("registry_id") == typed_registry.registry_id and entries_document.get("entry_count") == typed_registry.entry_count and canonical_bytes(entries_document.get("entries")) == canonical_bytes([entry.to_dict() for entry in typed_registry.entries])
    verification_linkage_ok = typed_registry is not None and typed_verification is not None and canonical_bytes(typed_verification.to_dict()) == canonical_bytes(verification_document) and typed_verification.registry_id == typed_registry.registry_id and typed_verification.registry_address == typed_registry.content_address and typed_registry.verification_address == typed_verification.content_address
    metrics_ok = typed_registry is not None and canonical_bytes(metrics_document) == canonical_bytes(typed_registry.metrics.to_dict()) and typed_registry.metrics.to_dict() == registry_model._metrics(typed_registry.entries).to_dict()
    posture_ok = typed_registry is not None and typed_registry.state == registry_model._aggregate_state(typed_registry.entries) and typed_registry.accepted == (bool(typed_registry.entries) and all(entry.accepted for entry in typed_registry.entries)) and typed_registry.release_ready == (bool(typed_registry.entries) and typed_registry.state == registry_model.RegistryState.READY.value and all(entry.release_ready for entry in typed_registry.entries))
    public_ok = all(registry_model._public(document) for document in documents.values())
    content_ok = typed_registry is not None and typed_verification is not None and registry_model.address_registry(typed_registry) == typed_registry.content_address and registry_model.address_verification(typed_verification) == typed_verification.content_address
    verification_checks_ok = False
    if typed_verification is not None and typed_registry is not None:
        verification_checks_ok = typed_verification.failed_count == 0 and typed_verification.check_count == len(registry_model.RegistryVerification.CHECK_IDS) and all(registry_model.address_entry(entry) == entry.content_address for entry in typed_registry.entries)
    checks = (
        _check("exact-members", members_exact, "registry directory contains exactly the five declared files", registry_address),
        _check("canonical-json", canonical_ok, "every registry artifact is canonical UTF-8 JSON", registry_address),
        _check("manifest-contract", manifest_ok, "manifest version, boundary, file list, count, and address reproduce", _safe_address(manifest.get("manifest_address"), registry_model.REGISTRY_MANIFEST_PREFIX, registry_address)),
        _check("artifact-receipts", receipt_ok, "manifest artifact receipts reproduce the stored bytes", registry_address),
        _check("registry-linkage", registry_linkage_ok, "manifest identity and addresses link to the registry", registry_address),
        _check("entry-linkage", entry_linkage_ok, "entry artifact identity and records link to the registry projection", registry_address),
        _check("verification-linkage", verification_linkage_ok, "verification identity and registry back-reference reproduce", verification_address),
        _check("metrics-conservation", metrics_ok, "metrics equal recomputed entry totals", registry_address),
        _check("posture-projection", posture_ok, "state, acceptance, and readiness are derived from entries", registry_address),
        _check("public-boundary", public_ok, "all decoded registry artifacts contain only public fields", registry_address),
        _check("content-address", content_ok, "registry and verification content addresses reproduce", registry_address),
        _check("verification-checks", verification_checks_ok, "all nested registry verification checks pass and reproduce", verification_address),
    )
    body = {"registry_address": registry_address, "verification_address": verification_address, "state": "complete" if all(check.passed for check in checks) else "incomplete", "complete": all(check.passed for check in checks), "accepted": all(check.passed for check in checks), "checks": checks}
    provisional = RegistryAudit(**body, content_address="pending:audit")
    return RegistryAudit(**body, content_address=address_audit(provisional))


def audit_registry(value: registry_model.ObservatoryArchiveRegistry) -> RegistryAudit:
    """Audit a typed registry with its attached verification artifact."""

    if not isinstance(value, registry_model.ObservatoryArchiveRegistry):
        raise ValidationError("registry audit requires a typed registry")
    registry_model.verify_registry(value)
    payload, documents = _object_documents(value)
    return _audit_documents(payload, documents, True)


def audit_registry_directory(source: str | Path) -> RegistryAudit:
    """Audit a raw registry directory, including malformed package states."""

    payload, names, members_exact = _read_directory(source)
    documents, _ = _decode_documents(payload)
    return _audit_documents(payload, documents, members_exact and names == set(registry_model.FILES))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryAudit:
    value = _mapping(value, "registry audit")
    _strict(value, {"registry_address", "verification_address", "state", "complete", "accepted", "check_count", "passed_count", "failed_count", "checks", "content_address"}, "registry audit")
    checks = tuple(RegistryAuditCheck.from_mapping(item) for item in registry_model._sequence(value["checks"], "registry audit checks", MAX_CHECKS))
    return RegistryAudit(value["registry_address"], value["verification_address"], value["state"], value["complete"], value["accepted"], checks, value["content_address"])


def verify_audit(value: RegistryAudit) -> RegistryAudit:
    if not isinstance(value, RegistryAudit):
        raise ValidationError("registry audit verification requires a typed audit")
    value._validate()
    return value


def audit_json(value: RegistryAudit) -> str:
    verify_audit(value)
    return canonical_json(value.to_dict())


def render_audit_markdown(value: RegistryAudit) -> str:
    verify_audit(value)
    lines = ["# Assurance history observatory archive registry audit", "", f"- State: `{value.state}`", f"- Accepted: `{str(value.accepted).lower()}`", f"- Registry: `{value.registry_address}`", f"- Verification: `{value.verification_address}`", f"- Checks: `{value.passed_count}` passed, `{value.failed_count}` failed", f"- Content address: `{value.content_address}`", "", "| Check | Passed | Detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{check.check_id}` | `{str(check.passed).lower()}` | {check.detail} |" for check in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    fields = {"check_id": {"type": "string", "minLength": 1, "maxLength": 128}, "passed": {"type": "boolean"}, "detail": {"type": "string", "minLength": 1, "maxLength": 1024}, "evidence_address": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_CHECK_PREFIX + ":"}}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def audit_schema() -> dict[str, Any]:
    fields = {"registry_address": {"type": "string"}, "verification_address": {"type": "string"}, "state": {"type": "string", "enum": list(STATES)}, "complete": {"type": "boolean"}, "accepted": {"type": "boolean"}, "check_count": {"type": "integer", "minimum": MAX_CHECKS, "maximum": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS, "items": check_schema()}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "checks": CHECK_IDS, "states": STATES, "features": ("raw exact-member audit", "canonical JSON audit", "manifest and artifact receipt replay", "registry entry and verification linkage audit", "conserved metric and posture audit", "public-boundary audit", "damaged-package fail-closed report", "addressed check receipts", "path-free JSON and Markdown projection"), "schemas": ("check", "audit")}


__all__ = [
    "AUDIT_CHECK_PREFIX",
    "AUDIT_PREFIX",
    "BOUNDARY",
    "CHECK_IDS",
    "MAX_CHECKS",
    "STATES",
    "VERSION",
    "RegistryAudit",
    "RegistryAuditCheck",
    "address_audit",
    "audit_from_mapping",
    "audit_json",
    "audit_registry",
    "audit_registry_directory",
    "audit_schema",
    "capabilities",
    "check_schema",
    "render_audit_markdown",
    "verify_audit",
]
