"""Release certificates over independently audited release-gate packages.

An audit report explains whether a package is structurally trustworthy.  This
boundary turns that report into a separate release decision with an explicit
policy, addressed checks, and ready/held/blocked states.  The certificate is
derived only from public audit data and never records a local path, actor,
model, language, or mutable process metadata.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

from collections.abc import Mapping, Sequence
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_package_audit as audit_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = audit_model.VERSION + "-release-certificate-v1"
BOUNDARY = audit_model.BOUNDARY + "_release_certificate"
CERTIFICATE_PREFIX = audit_model.AUDIT_PREFIX + "-release-certificate"
POLICY_PREFIX = CERTIFICATE_PREFIX + "-policy"
CHECK_PREFIX = CERTIFICATE_PREFIX + "-check"
CHECK_IDS = (
    "minimum-checks",
    "audit-complete",
    "audit-accepted",
    "all-checks-passed",
    "manifest-address",
    "gate-address",
    "policy-address",
    "public-boundary",
    "content-address",
)
STATES = ("ready", "held", "blocked")
SEVERITIES = ("hold", "blocking")
MAX_CHECKS = len(CHECK_IDS)
DEFAULT_CERTIFICATE_ID = "glio-noncode-release-gate-package-audit-certificate"
DEFAULT_MINIMUM_CHECKS = audit_model.MAX_CHECKS


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
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


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _public(value: Any) -> bool:
    return audit_model._public(value)


class RegistryHistoryReleaseGatePackageAuditCertificatePolicy:
    """Public release requirements applied to one package audit."""

    def __init__(
        self,
        certificate_id: str = DEFAULT_CERTIFICATE_ID,
        minimum_checks: int = DEFAULT_MINIMUM_CHECKS,
        require_complete: bool = True,
        require_accepted: bool = True,
        require_all_checks_passed: bool = True,
        require_manifest_address: bool = True,
        require_gate_address: bool = True,
        require_policy_address: bool = True,
    ) -> None:
        self.certificate_id = _text(certificate_id, "package audit certificate ID", 128)
        self.minimum_checks = _count(minimum_checks, "package audit certificate minimum checks", audit_model.MAX_CHECKS + 1, positive=True)
        self.require_complete = _bool(require_complete, "package audit certificate completeness requirement")
        self.require_accepted = _bool(require_accepted, "package audit certificate acceptance requirement")
        self.require_all_checks_passed = _bool(require_all_checks_passed, "package audit certificate check requirement")
        self.require_manifest_address = _bool(require_manifest_address, "package audit certificate manifest requirement")
        self.require_gate_address = _bool(require_gate_address, "package audit certificate gate requirement")
        self.require_policy_address = _bool(require_policy_address, "package audit certificate policy requirement")
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("package audit certificate policy crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "certificate_id": self.certificate_id,
            "minimum_checks": self.minimum_checks,
            "require_complete": self.require_complete,
            "require_accepted": self.require_accepted,
            "require_all_checks_passed": self.require_all_checks_passed,
            "require_manifest_address": self.require_manifest_address,
            "require_gate_address": self.require_gate_address,
            "require_policy_address": self.require_policy_address,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseGatePackageAuditCertificatePolicy:
        value = _mapping(value, "package audit certificate policy")
        _strict(value, set(cls().to_dict()), "package audit certificate policy")
        return cls(**value)


def address_policy(value: RegistryHistoryReleaseGatePackageAuditCertificatePolicy) -> str:
    if not isinstance(value, RegistryHistoryReleaseGatePackageAuditCertificatePolicy):
        raise ValidationError("package audit certificate policy address requires a typed policy")
    return content_hash(value.to_dict(), prefix=POLICY_PREFIX)


class RegistryHistoryReleaseGatePackageAuditCertificateCheck:
    """One explicit release-certificate assertion."""

    def __init__(self, check_id: str, passed: bool, severity: str, detail: str, observed: Mapping[str, Any], evidence_address: str, content_address: str) -> None:
        self.check_id = _text(check_id, "package audit certificate check ID", 128)
        self.passed = _bool(passed, "package audit certificate check passed")
        self.severity = _text(severity, "package audit certificate check severity", 32)
        if self.severity not in SEVERITIES:
            raise ValidationError("package audit certificate check severity is invalid")
        self.detail = _text(detail, "package audit certificate check detail", 1024)
        self.observed = _json_value(dict(_mapping(observed, "package audit certificate observed values")))
        if not _public(self.observed):
            raise ValidationError("package audit certificate observed values cross the public boundary")
        self.evidence_address = _text(evidence_address, "package audit certificate evidence address", 2048)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "package audit certificate check content address")
        else:
            _address(self.content_address, "package audit certificate check content address", CHECK_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_check(self) != self.content_address):
            raise ValidationError("package audit certificate check address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"check_id": self.check_id, "passed": self.passed, "severity": self.severity, "detail": self.detail, "observed": self.observed, "evidence_address": self.evidence_address, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseGatePackageAuditCertificateCheck:
        value = _mapping(value, "package audit certificate check")
        _strict(value, {"check_id", "passed", "severity", "detail", "observed", "evidence_address", "content_address"}, "package audit certificate check")
        return cls(**value)


def address_check(value: RegistryHistoryReleaseGatePackageAuditCertificateCheck) -> str:
    if not isinstance(value, RegistryHistoryReleaseGatePackageAuditCertificateCheck):
        raise ValidationError("package audit certificate check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class RegistryHistoryReleaseGatePackageAuditCertificate:
    """A deterministic ready, held, or blocked package release certificate."""

    CHECK_IDS = CHECK_IDS

    def __init__(self, audit_address: str, manifest_address: str, gate_address: str, policy_address: str, policy: RegistryHistoryReleaseGatePackageAuditCertificatePolicy, state: str, accepted: bool, release_ready: bool, checks: Sequence[RegistryHistoryReleaseGatePackageAuditCertificateCheck], content_address: str) -> None:
        self.audit_address = _address(audit_address, "package audit certificate audit address", audit_model.AUDIT_PREFIX)
        self.manifest_address = _address(manifest_address, "package audit certificate manifest address", audit_model.package_model.MANIFEST_PREFIX)
        self.gate_address = _address(gate_address, "package audit certificate gate address", audit_model.gate_model.GATE_PREFIX)
        self.policy_address = _address(policy_address, "package audit certificate policy address", POLICY_PREFIX)
        self.policy = policy
        self.state = _text(state, "package audit certificate state", 32)
        self.accepted = _bool(accepted, "package audit certificate accepted")
        self.release_ready = _bool(release_ready, "package audit certificate release-ready")
        self.checks = tuple(checks)
        self.check_count = len(self.checks)
        self.passed_count = sum(check.passed for check in self.checks)
        self.failed_count = self.check_count - self.passed_count
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        if not isinstance(self.policy, RegistryHistoryReleaseGatePackageAuditCertificatePolicy):
            raise ValidationError("package audit certificate policy must be typed")
        if address_policy(self.policy) != self.policy_address:
            raise ValidationError("package audit certificate policy address does not reproduce")
        if self.state not in STATES:
            raise ValidationError("package audit certificate state is invalid")
        if tuple(check.check_id for check in self.checks) != CHECK_IDS or self.check_count != MAX_CHECKS:
            raise ValidationError("package audit certificate check set is invalid")
        if any(not isinstance(check, RegistryHistoryReleaseGatePackageAuditCertificateCheck) for check in self.checks):
            raise ValidationError("package audit certificate checks must be typed")
        _count(self.passed_count, "package audit certificate passed count", MAX_CHECKS)
        _count(self.failed_count, "package audit certificate failed count", MAX_CHECKS)
        if self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(check.passed for check in self.checks):
            raise ValidationError("package audit certificate counts are not conserved")
        expected_accepted = self.failed_count == 0
        blocking_failed = any(not check.passed and check.severity == "blocking" for check in self.checks)
        expected_state = "ready" if expected_accepted else ("blocked" if blocking_failed else "held")
        if self.accepted != expected_accepted or self.release_ready != expected_accepted or self.state != expected_state:
            raise ValidationError("package audit certificate decision is not derived from checks")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "package audit certificate content address")
        else:
            _address(self.content_address, "package audit certificate content address", CERTIFICATE_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_certificate(self) != self.content_address):
            raise ValidationError("package audit certificate address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {"audit_address": self.audit_address, "manifest_address": self.manifest_address, "gate_address": self.gate_address, "policy_address": self.policy_address, "policy": self.policy.to_dict(), "state": self.state, "accepted": self.accepted, "release_ready": self.release_ready, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "checks": tuple(check.to_dict() for check in self.checks), "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("audit_address", "manifest_address", "gate_address", "policy_address", "policy", "state", "accepted", "release_ready", "check_count", "passed_count", "failed_count", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryReleaseGatePackageAuditCertificate:
        value = _mapping(value, "package audit certificate")
        _strict(value, {"audit_address", "manifest_address", "gate_address", "policy_address", "policy", "state", "accepted", "release_ready", "check_count", "passed_count", "failed_count", "checks", "content_address"}, "package audit certificate")
        checks = tuple(RegistryHistoryReleaseGatePackageAuditCertificateCheck.from_mapping(item) for item in _sequence(value["checks"], "package audit certificate checks", MAX_CHECKS))
        result = cls(value["audit_address"], value["manifest_address"], value["gate_address"], value["policy_address"], RegistryHistoryReleaseGatePackageAuditCertificatePolicy.from_mapping(_mapping(value["policy"], "package audit certificate policy")), value["state"], value["accepted"], value["release_ready"], checks, value["content_address"])
        if result.check_count != value["check_count"] or result.passed_count != value["passed_count"] or result.failed_count != value["failed_count"]:
            raise ValidationError("package audit certificate derived counts are not conserved")
        return result


def address_certificate(value: RegistryHistoryReleaseGatePackageAuditCertificate) -> str:
    if not isinstance(value, RegistryHistoryReleaseGatePackageAuditCertificate):
        raise ValidationError("package audit certificate address requires a typed certificate")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CERTIFICATE_PREFIX)


def _check(check_id: str, passed: bool, severity: str, detail: str, observed: Mapping[str, Any], evidence: str) -> RegistryHistoryReleaseGatePackageAuditCertificateCheck:
    provisional = RegistryHistoryReleaseGatePackageAuditCertificateCheck(check_id, passed, severity, detail, observed, evidence, "pending:check")
    return RegistryHistoryReleaseGatePackageAuditCertificateCheck(check_id, passed, severity, detail, observed, evidence, address_check(provisional))


def evaluate_audit(value: audit_model.RegistryHistoryReleaseGatePackageAudit, policy: RegistryHistoryReleaseGatePackageAuditCertificatePolicy | None = None) -> RegistryHistoryReleaseGatePackageAuditCertificate:
    """Evaluate one verified package audit under a typed certificate policy."""

    audit_model.verify_audit(value)
    selected_policy = policy or RegistryHistoryReleaseGatePackageAuditCertificatePolicy()
    if not isinstance(selected_policy, RegistryHistoryReleaseGatePackageAuditCertificatePolicy):
        raise ValidationError("package audit certificate requires a typed policy")
    policy_address = address_policy(selected_policy)
    checks = (
        _check("minimum-checks", value.check_count >= selected_policy.minimum_checks, "hold", "audit contains the minimum required number of fixed checks", {"actual": value.check_count, "minimum": selected_policy.minimum_checks}, value.content_address),
        _check("audit-complete", not selected_policy.require_complete or value.complete, "blocking", "package audit reports complete structural verification", {"required": selected_policy.require_complete, "complete": value.complete}, value.content_address),
        _check("audit-accepted", not selected_policy.require_accepted or value.accepted, "blocking", "package audit is accepted by every package-integrity check", {"required": selected_policy.require_accepted, "accepted": value.accepted}, value.content_address),
        _check("all-checks-passed", not selected_policy.require_all_checks_passed or value.passed_count == value.check_count, "blocking", "every package-audit check passed", {"required": selected_policy.require_all_checks_passed, "passed": value.passed_count, "checks": value.check_count}, value.content_address),
        _check("manifest-address", not selected_policy.require_manifest_address or _address(value.manifest_address, "certificate manifest evidence address", audit_model.package_model.MANIFEST_PREFIX) == value.manifest_address, "blocking", "audit manifest address uses the public package namespace", {"required": selected_policy.require_manifest_address, "valid": True}, value.manifest_address),
        _check("gate-address", not selected_policy.require_gate_address or _address(value.gate_address, "certificate gate evidence address", audit_model.gate_model.GATE_PREFIX) == value.gate_address, "blocking", "audit gate address uses the public gate namespace", {"required": selected_policy.require_gate_address, "valid": True}, value.gate_address),
        _check("policy-address", not selected_policy.require_policy_address or _address(value.policy_address, "certificate policy evidence address", audit_model.gate_model.POLICY_PREFIX) == value.policy_address, "blocking", "audit policy address uses the public policy namespace", {"required": selected_policy.require_policy_address, "valid": True}, value.policy_address),
        _check("public-boundary", _public(value.to_dict()) and _public(selected_policy.to_dict()), "blocking", "audit and certificate policy contain only public fields", {"audit_public": _public(value.to_dict()), "policy_public": _public(selected_policy.to_dict())}, value.content_address),
        _check("content-address", audit_model.address_audit(value) == value.content_address and address_policy(selected_policy) == policy_address, "blocking", "audit and certificate policy addresses reproduce", {"audit_address_reproduces": audit_model.address_audit(value) == value.content_address, "policy_address_reproduces": address_policy(selected_policy) == policy_address}, value.content_address),
    )
    accepted = all(check.passed for check in checks)
    blocking_failed = any(not check.passed and check.severity == "blocking" for check in checks)
    state = "ready" if accepted else ("blocked" if blocking_failed else "held")
    body = {"audit_address": value.content_address, "manifest_address": value.manifest_address, "gate_address": value.gate_address, "policy_address": policy_address, "policy": selected_policy, "state": state, "accepted": accepted, "release_ready": accepted, "checks": checks}
    provisional = RegistryHistoryReleaseGatePackageAuditCertificate(**body, content_address="pending:certificate")
    return RegistryHistoryReleaseGatePackageAuditCertificate(**body, content_address=address_certificate(provisional))


def certificate_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryReleaseGatePackageAuditCertificate:
    return RegistryHistoryReleaseGatePackageAuditCertificate.from_mapping(value)


def verify_certificate(value: RegistryHistoryReleaseGatePackageAuditCertificate) -> RegistryHistoryReleaseGatePackageAuditCertificate:
    if not isinstance(value, RegistryHistoryReleaseGatePackageAuditCertificate):
        raise ValidationError("package audit certificate verification requires a typed certificate")
    value._validate()
    return value


def certificate_json(value: RegistryHistoryReleaseGatePackageAuditCertificate) -> str:
    verify_certificate(value)
    return canonical_json(value.to_dict())


def render_certificate_markdown(value: RegistryHistoryReleaseGatePackageAuditCertificate) -> str:
    verify_certificate(value)
    lines = ["# Assurance History Observatory Archive Registry History Release Gate Package Audit Release Certificate", "", f"- State: `{value.state}`", f"- Accepted: `{str(value.accepted).lower()}`", f"- Audit: `{value.audit_address}`", f"- Manifest: `{value.manifest_address}`", f"- Gate: `{value.gate_address}`", f"- Policy: `{value.policy.certificate_id}`", f"- Checks: `{value.passed_count}` passed, `{value.failed_count}` failed", f"- Content address: `{value.content_address}`", "", "| Check | Passed | Severity | Detail |", "| --- | --- | --- | --- |"]
    lines.extend(f"| `{check.check_id}` | `{str(check.passed).lower()}` | `{check.severity}` | {check.detail} |" for check in value.checks)
    return "\n".join(lines) + "\n"


def policy_schema() -> dict[str, Any]:
    fields = {"certificate_id": {"type": "string", "minLength": 1, "maxLength": 128}, "minimum_checks": {"type": "integer", "minimum": 1, "maximum": audit_model.MAX_CHECKS + 1}, "require_complete": {"type": "boolean"}, "require_accepted": {"type": "boolean"}, "require_all_checks_passed": {"type": "boolean"}, "require_manifest_address": {"type": "boolean"}, "require_gate_address": {"type": "boolean"}, "require_policy_address": {"type": "boolean"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def check_schema() -> dict[str, Any]:
    fields = {"check_id": {"type": "string", "minLength": 1, "maxLength": 128}, "passed": {"type": "boolean"}, "severity": {"type": "string", "enum": list(SEVERITIES)}, "detail": {"type": "string", "minLength": 1, "maxLength": 1024}, "observed": {"type": "object", "additionalProperties": True}, "evidence_address": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def certificate_schema() -> dict[str, Any]:
    fields = {"audit_address": {"type": "string", "pattern": "^" + audit_model.AUDIT_PREFIX + ":"}, "manifest_address": {"type": "string", "pattern": "^" + audit_model.package_model.MANIFEST_PREFIX + ":"}, "gate_address": {"type": "string", "pattern": "^" + audit_model.gate_model.GATE_PREFIX + ":"}, "policy_address": {"type": "string", "pattern": "^" + POLICY_PREFIX + ":"}, "policy": policy_schema(), "state": {"type": "string", "enum": list(STATES)}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "check_count": {"type": "integer", "minimum": MAX_CHECKS, "maximum": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS, "items": check_schema()}, "content_address": {"type": "string", "pattern": "^" + CERTIFICATE_PREFIX + ":"}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "checks": CHECK_IDS, "states": STATES, "severities": SEVERITIES, "limits": {"max_checks": MAX_CHECKS, "max_audit_checks": audit_model.MAX_CHECKS}, "defaults": {"minimum_checks": DEFAULT_MINIMUM_CHECKS}, "features": ("typed public certificate policy", "independent audit dependency", "ready held and blocked decision states", "addressed certificate checks", "audit namespace validation", "content-address replay", "path-free JSON and Markdown projection"), "schemas": ("policy", "check", "certificate")}


__all__ = [
    "BOUNDARY",
    "CERTIFICATE_PREFIX",
    "CHECK_IDS",
    "CHECK_PREFIX",
    "DEFAULT_CERTIFICATE_ID",
    "DEFAULT_MINIMUM_CHECKS",
    "MAX_CHECKS",
    "POLICY_PREFIX",
    "SEVERITIES",
    "STATES",
    "VERSION",
    "RegistryHistoryReleaseGatePackageAuditCertificate",
    "RegistryHistoryReleaseGatePackageAuditCertificateCheck",
    "RegistryHistoryReleaseGatePackageAuditCertificatePolicy",
    "address_certificate",
    "address_check",
    "address_policy",
    "capabilities",
    "certificate_from_mapping",
    "certificate_json",
    "certificate_schema",
    "check_schema",
    "evaluate_audit",
    "policy_schema",
    "render_certificate_markdown",
    "verify_certificate",
]
