"""Independent audit of persisted registry-history release-gate packages.

The package loader is intentionally strict and fail-fast.  This companion
boundary inspects the raw three-file handoff as an independent evidence
surface, preserving a complete public diagnostic when a manifest, artifact,
receipt, or nested release decision is damaged.  The report never exposes an
input path or process metadata and can therefore be safely serialized,
queried, and handed to another verifier.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate as gate_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_package as package_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash


VERSION = package_model.VERSION + "-audit-v1"
BOUNDARY = package_model.BOUNDARY + "_audit"
AUDIT_PREFIX = package_model.PACKAGE_PREFIX + "-audit"
AUDIT_CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "exact-members",
    "canonical-json",
    "manifest-contract",
    "artifact-receipts",
    "gate-linkage",
    "policy-linkage",
    "nested-checks",
    "decision-projection",
    "public-boundary",
    "content-address",
    "mapping-round-trip",
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


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    return gate_model._public(value)


def _safe_address(value: Any, prefix: str, fallback: str) -> str:
    try:
        return _address(value, "package audit evidence address", prefix)
    except ValidationError:
        return fallback


class RegistryHistoryReleaseGatePackageAuditCheck:
    """One independently addressed assertion over a release-gate package."""

    def __init__(self, check_id: str, passed: bool, detail: str, evidence_address: str) -> None:
        self.check_id = _text(check_id, "release-gate package audit check ID", 128)
        self.passed = _bool(passed, "release-gate package audit check passed")
        self.detail = _text(detail, "release-gate package audit check detail", 1024)
        self.evidence_address = _text(evidence_address, "release-gate package audit evidence address", 2048)
        self.content_address = content_hash(
            {
                "check_id": self.check_id,
                "passed": self.passed,
                "detail": self.detail,
                "evidence_address": self.evidence_address,
            },
            prefix=AUDIT_CHECK_PREFIX,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "passed": self.passed,
            "detail": self.detail,
            "evidence_address": self.evidence_address,
            "content_address": self.content_address,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseGatePackageAuditCheck:
        value = _mapping(value, "release-gate package audit check")
        _strict(value, {"check_id", "passed", "detail", "evidence_address", "content_address"}, "release-gate package audit check")
        result = cls(value["check_id"], value["passed"], value["detail"], value["evidence_address"])
        if result.content_address != value["content_address"]:
            raise ValidationError("release-gate package audit check content address mismatch")
        return result


class RegistryHistoryReleaseGatePackageAudit:
    """Public complete or incomplete report for a raw release-gate package."""

    def __init__(
        self,
        manifest_address: str,
        gate_address: str,
        policy_address: str,
        state: str,
        complete: bool,
        accepted: bool,
        checks: Sequence[RegistryHistoryReleaseGatePackageAuditCheck],
        content_address: str,
    ) -> None:
        self.manifest_address = manifest_address
        self.gate_address = gate_address
        self.policy_address = policy_address
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
        _address(self.manifest_address, "release-gate package audit manifest address", package_model.MANIFEST_PREFIX)
        _address(self.gate_address, "release-gate package audit gate address", gate_model.GATE_PREFIX)
        _address(self.policy_address, "release-gate package audit policy address", gate_model.POLICY_PREFIX)
        if self.state not in STATES or self.complete != (self.state == "complete"):
            raise ValidationError("release-gate package audit state does not match completion")
        _bool(self.complete, "release-gate package audit complete")
        _bool(self.accepted, "release-gate package audit accepted")
        if tuple(check.check_id for check in self.checks) != CHECK_IDS or self.check_count != MAX_CHECKS:
            raise ValidationError("release-gate package audit check set is invalid")
        if any(not isinstance(check, RegistryHistoryReleaseGatePackageAuditCheck) for check in self.checks):
            raise ValidationError("release-gate package audit checks must be typed")
        _count(self.passed_count, "release-gate package audit passed count", MAX_CHECKS)
        _count(self.failed_count, "release-gate package audit failed count", MAX_CHECKS)
        if self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(check.passed for check in self.checks):
            raise ValidationError("release-gate package audit counts are not conserved")
        if self.complete != (self.failed_count == 0) or self.accepted != self.complete:
            raise ValidationError("release-gate package audit acceptance does not match checks")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "release-gate package audit content address")
        else:
            _address(self.content_address, "release-gate package audit content address", AUDIT_PREFIX)
        if not package_model._public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_audit(self) != self.content_address):
            raise ValidationError("release-gate package audit address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_address": self.manifest_address,
            "gate_address": self.gate_address,
            "policy_address": self.policy_address,
            "state": self.state,
            "complete": self.complete,
            "accepted": self.accepted,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "checks": tuple(check.to_dict() for check in self.checks),
            "content_address": self.content_address,
        }

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("manifest_address", "gate_address", "policy_address", "state", "complete", "accepted", "check_count", "passed_count", "failed_count", "content_address")}


def address_audit(value: RegistryHistoryReleaseGatePackageAudit) -> str:
    if not isinstance(value, RegistryHistoryReleaseGatePackageAudit):
        raise ValidationError("release-gate package audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, detail: str, evidence: str) -> RegistryHistoryReleaseGatePackageAuditCheck:
    return RegistryHistoryReleaseGatePackageAuditCheck(check_id, passed, detail, evidence)


def _read_directory(source: str | Path) -> tuple[dict[str, bytes], set[str], bool]:
    try:
        directory = Path(source)
        if directory.is_symlink() or not directory.is_dir():
            return {}, set(), False
        members = tuple(directory.iterdir())
        names = {item.name for item in members}
        if any(item.is_symlink() or not item.is_file() for item in members):
            return {}, names, False
        payload = {name: (directory / name).read_bytes() for name in package_model.FILES if (directory / name).is_file()}
        return payload, names, names == set(package_model.FILES) and set(payload) == set(package_model.FILES)
    except (OSError, ValueError):
        return {}, set(), False


def _decode_documents(payload: Mapping[str, bytes]) -> tuple[dict[str, Mapping[str, Any]], bool]:
    documents: dict[str, Mapping[str, Any]] = {}
    canonical = bool(payload) and set(payload) == set(package_model.FILES)
    for name in package_model.FILES:
        raw = payload.get(name)
        if raw is None:
            canonical = False
            continue
        try:
            document = json.loads(raw.decode("utf-8"))
            documents[name] = _mapping(document, f"release-gate package {name}")
            if canonical_bytes(document) != raw:
                canonical = False
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError):
            canonical = False
    return documents, canonical


def _typed_gate(document: Mapping[str, Any]) -> gate_model.RegistryHistoryReleaseGate | None:
    try:
        return gate_model.gate_from_mapping(document)
    except (ValidationError, KeyError, TypeError, ValueError):
        return None


def _typed_policy(document: Mapping[str, Any]) -> gate_model.RegistryHistoryReleasePolicy | None:
    try:
        return gate_model.RegistryHistoryReleasePolicy.from_mapping(document)
    except (ValidationError, KeyError, TypeError, ValueError):
        return None


def _manifest_contract(manifest: Mapping[str, Any]) -> bool:
    try:
        _strict(manifest, {"version", "boundary", "gate_address", "policy_address", "artifact_count", "files", "artifacts", "manifest_address"}, "release-gate package manifest")
        expected = content_hash(dict(manifest) | {"manifest_address": None}, prefix=package_model.MANIFEST_PREFIX)
        return (
            manifest.get("version") == package_model.VERSION
            and manifest.get("boundary") == package_model.BOUNDARY
            and manifest.get("artifact_count") == 2
            and manifest.get("files") == list(package_model.FILES[1:])
            and manifest.get("manifest_address") == expected
        )
    except (ValidationError, TypeError):
        return False


def _artifact_receipts(manifest: Mapping[str, Any], payload: Mapping[str, bytes]) -> bool:
    try:
        artifacts = manifest.get("artifacts")
        if not isinstance(artifacts, list) or len(artifacts) != len(package_model.FILES) - 1:
            return False
        for item in artifacts:
            item = _mapping(item, "release-gate package artifact receipt")
            name = item.get("name")
            if name not in package_model.FILES[1:] or name not in payload or dict(item) != package_model._artifact(name, payload[name]):
                return False
        return {item["name"] for item in artifacts} == set(package_model.FILES[1:])
    except (ValidationError, TypeError, KeyError):
        return False


def _audit_documents(payload: Mapping[str, bytes], documents: Mapping[str, Mapping[str, Any]], members_exact: bool) -> RegistryHistoryReleaseGatePackageAudit:
    manifest = documents.get(package_model.MANIFEST_NAME, {})
    policy_document = documents.get(package_model.POLICY_NAME, {})
    gate_document = documents.get(package_model.GATE_NAME, {})
    typed_gate = _typed_gate(gate_document)
    typed_policy = _typed_policy(policy_document)
    fallback_manifest = package_model.MANIFEST_PREFIX + ":unresolved"
    fallback_gate = gate_model.GATE_PREFIX + ":unresolved"
    fallback_policy = gate_model.POLICY_PREFIX + ":unresolved"
    manifest_address = _safe_address(manifest.get("manifest_address"), package_model.MANIFEST_PREFIX, fallback_manifest)
    gate_address = _safe_address(gate_document.get("content_address"), gate_model.GATE_PREFIX, fallback_gate)
    policy_address = _safe_address(policy_document.get("policy_address"), gate_model.POLICY_PREFIX, fallback_policy)
    if typed_gate is not None:
        gate_address = typed_gate.content_address
        policy_address = typed_gate.policy_address
    if typed_policy is not None and typed_gate is None:
        policy_address = gate_model.address_policy(typed_policy)

    canonical_ok = bool(payload) and set(payload) == set(package_model.FILES) and set(documents) == set(package_model.FILES) and all(canonical_bytes(documents[name]) == payload[name] for name in package_model.FILES)
    manifest_ok = _manifest_contract(manifest)
    receipt_ok = _artifact_receipts(manifest, payload)
    gate_linkage_ok = typed_gate is not None and manifest.get("gate_address") == typed_gate.content_address
    policy_linkage_ok = typed_gate is not None and typed_policy is not None and manifest.get("policy_address") == typed_gate.policy_address == gate_model.address_policy(typed_policy) and typed_gate.policy.to_dict() == typed_policy.to_dict()
    nested_checks_ok = typed_gate is not None and tuple(check.check_id for check in typed_gate.checks) == gate_model.CHECK_IDS and all(gate_model.address_check(check) == check.content_address for check in typed_gate.checks)
    decision_projection_ok = False
    if typed_gate is not None:
        expected_accepted = typed_gate.failed_count == 0
        blocking_failed = any(not check.passed and check.severity == "blocking" for check in typed_gate.checks)
        expected_state = "ready" if expected_accepted else ("blocked" if blocking_failed else "held")
        decision_projection_ok = typed_gate.accepted == expected_accepted and typed_gate.release_ready == expected_accepted and typed_gate.state == expected_state
    public_ok = all(package_model._public(document) for document in documents.values())
    content_ok = False
    if typed_gate is not None and payload.get(package_model.MANIFEST_NAME) is not None:
        expected_manifest = package_model._manifest(typed_gate, {package_model.POLICY_NAME: payload[package_model.POLICY_NAME], package_model.GATE_NAME: payload[package_model.GATE_NAME]})
        content_ok = gate_model.address_gate(typed_gate) == typed_gate.content_address and manifest.get("manifest_address") == expected_manifest["manifest_address"]
    mapping_round_trip_ok = False
    if typed_gate is not None and typed_policy is not None:
        try:
            mapping_round_trip_ok = gate_model.gate_from_mapping(typed_gate.to_dict()).to_dict() == typed_gate.to_dict() and gate_model.RegistryHistoryReleasePolicy.from_mapping(typed_policy.to_dict()).to_dict() == typed_policy.to_dict()
        except (ValidationError, KeyError, TypeError, ValueError):
            mapping_round_trip_ok = False

    checks = (
        _check("exact-members", members_exact, "release-gate package contains exactly the three declared files", manifest_address),
        _check("canonical-json", canonical_ok, "every release-gate artifact is canonical UTF-8 JSON", manifest_address),
        _check("manifest-contract", manifest_ok, "manifest version, boundary, file list, count, and address reproduce", manifest_address),
        _check("artifact-receipts", receipt_ok, "manifest artifact receipts reproduce the stored bytes", manifest_address),
        _check("gate-linkage", gate_linkage_ok, "manifest gate identity links to the typed gate projection", gate_address),
        _check("policy-linkage", policy_linkage_ok, "manifest and gate policy projections agree and address reproducibly", policy_address),
        _check("nested-checks", nested_checks_ok, "every nested gate check has its declared identity and address", gate_address),
        _check("decision-projection", decision_projection_ok, "gate state, acceptance, and readiness derive from its checks", gate_address),
        _check("public-boundary", public_ok, "all decoded package artifacts contain only public fields", manifest_address),
        _check("content-address", content_ok, "gate and manifest content addresses reproduce from package bytes", gate_address),
        _check("mapping-round-trip", mapping_round_trip_ok, "typed gate and policy mappings rehydrate without projection drift", gate_address),
    )
    complete = all(check.passed for check in checks)
    body = {"manifest_address": manifest_address, "gate_address": gate_address, "policy_address": policy_address, "state": "complete" if complete else "incomplete", "complete": complete, "accepted": complete, "checks": checks}
    provisional = RegistryHistoryReleaseGatePackageAudit(**body, content_address="pending:audit")
    return RegistryHistoryReleaseGatePackageAudit(**body, content_address=address_audit(provisional))


def audit_gate(value: gate_model.RegistryHistoryReleaseGate) -> RegistryHistoryReleaseGatePackageAudit:
    """Audit a typed gate after projecting it through the package boundary."""

    if not isinstance(value, gate_model.RegistryHistoryReleaseGate):
        raise ValidationError("release-gate package audit requires a typed gate")
    gate_model.verify_gate(value)
    payload = package_model.package_bytes(value)
    documents = {name: _mapping(json.loads(payload[name].decode("utf-8")), f"release-gate package {name}") for name in package_model.FILES}
    return _audit_documents(payload, documents, True)


def audit_package_directory(source: str | Path) -> RegistryHistoryReleaseGatePackageAudit:
    """Audit a raw release-gate package, including malformed states."""

    payload, names, members_exact = _read_directory(source)
    documents, _ = _decode_documents(payload)
    return _audit_documents(payload, documents, members_exact and names == set(package_model.FILES))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseGatePackageAudit:
    value = _mapping(value, "release-gate package audit")
    _strict(value, {"manifest_address", "gate_address", "policy_address", "state", "complete", "accepted", "check_count", "passed_count", "failed_count", "checks", "content_address"}, "release-gate package audit")
    checks = tuple(RegistryHistoryReleaseGatePackageAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "release-gate package audit checks", MAX_CHECKS))
    result = RegistryHistoryReleaseGatePackageAudit(value["manifest_address"], value["gate_address"], value["policy_address"], value["state"], value["complete"], value["accepted"], checks, value["content_address"])
    if result.check_count != value["check_count"] or result.passed_count != value["passed_count"] or result.failed_count != value["failed_count"]:
        raise ValidationError("release-gate package audit derived counts are not conserved")
    return result


def verify_audit(value: RegistryHistoryReleaseGatePackageAudit) -> RegistryHistoryReleaseGatePackageAudit:
    if not isinstance(value, RegistryHistoryReleaseGatePackageAudit):
        raise ValidationError("release-gate package audit verification requires a typed audit")
    value._validate()
    return value


def audit_json(value: RegistryHistoryReleaseGatePackageAudit) -> str:
    verify_audit(value)
    return canonical_json(value.to_dict())


def render_audit_markdown(value: RegistryHistoryReleaseGatePackageAudit) -> str:
    verify_audit(value)
    lines = [
        "# Assurance History Observatory Archive Registry History Release Gate Package Audit",
        "",
        f"- State: `{value.state}`",
        f"- Accepted: `{str(value.accepted).lower()}`",
        f"- Manifest: `{value.manifest_address}`",
        f"- Gate: `{value.gate_address}`",
        f"- Policy: `{value.policy_address}`",
        f"- Checks: `{value.passed_count}` passed, `{value.failed_count}` failed",
        f"- Content address: `{value.content_address}`",
        "",
        "| Check | Passed | Detail |",
        "| --- | --- | --- |",
    ]
    lines.extend(f"| `{check.check_id}` | `{str(check.passed).lower()}` | {check.detail} |" for check in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    fields = {"check_id": {"type": "string", "minLength": 1, "maxLength": 128}, "passed": {"type": "boolean"}, "detail": {"type": "string", "minLength": 1, "maxLength": 1024}, "evidence_address": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_CHECK_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def audit_schema() -> dict[str, Any]:
    fields = {"manifest_address": {"type": "string", "pattern": "^" + package_model.MANIFEST_PREFIX + ":"}, "gate_address": {"type": "string", "pattern": "^" + gate_model.GATE_PREFIX + ":"}, "policy_address": {"type": "string", "pattern": "^" + gate_model.POLICY_PREFIX + ":"}, "state": {"type": "string", "enum": list(STATES)}, "complete": {"type": "boolean"}, "accepted": {"type": "boolean"}, "check_count": {"type": "integer", "minimum": MAX_CHECKS, "maximum": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS, "items": check_schema()}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "checks": CHECK_IDS, "states": STATES, "limits": {"max_checks": MAX_CHECKS, "max_artifacts": 2}, "features": ("raw exact-member package audit", "canonical JSON audit", "manifest and artifact receipt replay", "gate and policy linkage audit", "nested decision check replay", "decision projection audit", "public-boundary audit", "damaged-package fail-closed report", "path-free JSON and Markdown projection"), "schemas": ("check", "audit")}


__all__ = [
    "AUDIT_CHECK_PREFIX",
    "AUDIT_PREFIX",
    "BOUNDARY",
    "CHECK_IDS",
    "MAX_CHECKS",
    "STATES",
    "VERSION",
    "RegistryHistoryReleaseGatePackageAudit",
    "RegistryHistoryReleaseGatePackageAuditCheck",
    "address_audit",
    "audit_from_mapping",
    "audit_gate",
    "audit_json",
    "audit_package_directory",
    "audit_schema",
    "capabilities",
    "check_schema",
    "render_audit_markdown",
    "verify_audit",
]
