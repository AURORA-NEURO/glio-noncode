"""Independent audit of quorum-safe federation consensus receipts."""

from __future__ import annotations

import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_consensus as consensus_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry_federation as federation_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = consensus_model.VERSION + "-audit-v1"
BOUNDARY = consensus_model.BOUNDARY + "_audit"
AUDIT_PREFIX = federation_model.FEDERATION_PREFIX + "-consensus-audit"
FINDING_PREFIX = federation_model.FEDERATION_PREFIX + "-consensus-audit-finding"
MAX_CHECKS = len(consensus_model.CHECK_IDS)
MAX_PEERS = consensus_model.MAX_PEERS
MAX_TEXT = federation_model.MAX_TEXT
CHECK_IDS = consensus_model.CHECK_IDS


def _text(value: Any, field: str, maximum: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 512)
    if "/" in value or "\\" in value or '"' in value or prefix is not None and not value.startswith(prefix + ":"):
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


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    if isinstance(value, str):
        return "agent" not in value.lower() and "/" not in value and "\\" not in value and '"' not in value
    return value is None or isinstance(value, (bool, int, float))


class RegistryFederationConsensusAuditFinding:
    """One independently recomputed consensus invariant."""

    FIELDS = ("ordinal", "check_id", "passed", "observed", "expected", "detail", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, observed: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "consensus audit finding ordinal", MAX_CHECKS, positive=True)
        self.check_id = _label(check_id, "consensus audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("consensus audit check ID is unsupported")
        self.passed = _bool(passed, "consensus audit finding result")
        self.observed = _text(observed, "consensus audit observed value")
        self.expected = _text(expected, "consensus audit expected value")
        self.detail = _text(detail, "consensus audit finding detail")
        self.content_address = _address(content_address, "consensus finding address", FINDING_PREFIX)
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("consensus finding address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("consensus finding crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusAuditFinding:
        value = _mapping(value, "consensus audit finding")
        _strict(value, set(cls.FIELDS), "consensus audit finding")
        return cls(*(value[field] for field in cls.FIELDS))


def address_finding(value: RegistryFederationConsensusAuditFinding) -> str:
    if not isinstance(value, RegistryFederationConsensusAuditFinding):
        raise ValidationError("consensus finding address requires a typed finding")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


class RegistryFederationConsensusAudit:
    """A complete audit result; a rejected consensus can still be sound."""

    FIELDS = ("consensus_address", "federation_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, consensus_address: str, federation_address: str, checks: Sequence[RegistryFederationConsensusAuditFinding], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.consensus_address = _address(consensus_address, "consensus audit consensus address", consensus_model.CONSENSUS_PREFIX)
        self.federation_address = _address(federation_address, "consensus audit federation address", federation_model.FEDERATION_PREFIX)
        self.checks = tuple(checks)
        if len(self.checks) > MAX_CHECKS or any(not isinstance(item, RegistryFederationConsensusAuditFinding) for item in self.checks):
            raise ValidationError("consensus audit checks are outside the bound")
        self.check_count = _count(check_count, "consensus audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "consensus audit passed count", self.check_count)
        self.failed_count = _count(failed_count, "consensus audit failed count", self.check_count)
        self.accepted = _bool(accepted, "consensus audit acceptance")
        if self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or tuple(item.ordinal for item in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("consensus audit check coverage is not conserved")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("consensus audit counters are not conserved")
        self.content_address = _address(content_address, "consensus audit content address", AUDIT_PREFIX)
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("consensus audit content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("consensus audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"consensus_address": self.consensus_address, "federation_address": self.federation_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationConsensusAudit:
        value = _mapping(value, "consensus audit")
        _strict(value, set(cls.FIELDS), "consensus audit")
        checks = tuple(value["checks"]) if isinstance(value["checks"], list) else value["checks"]
        return cls(value["consensus_address"], value["federation_address"], tuple(RegistryFederationConsensusAuditFinding.from_mapping(item) for item in checks), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationConsensusAudit) -> str:
    if not isinstance(value, RegistryFederationConsensusAudit):
        raise ValidationError("consensus audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, observed: Any, expected: Any, detail: str) -> RegistryFederationConsensusAuditFinding:
    provisional = RegistryFederationConsensusAuditFinding(ordinal, check_id, passed, str(observed), str(expected), detail, FINDING_PREFIX + ":pending")
    return RegistryFederationConsensusAuditFinding(provisional.ordinal, provisional.check_id, provisional.passed, provisional.observed, provisional.expected, provisional.detail, address_finding(provisional))


def _audit_checks(value: consensus_model.RegistryFederationConsensus) -> tuple[RegistryFederationConsensusAuditFinding, ...]:
    packages = value.packages
    actions = value.actions
    selected = sum(item.resolution == "selected" for item in packages)
    unresolved = sum(item.resolution == "unresolved" for item in packages)
    resolvable = sum(item.resolution != "unresolved" for item in packages)
    expected_state = "conflicted" if any(item.candidate_count > 1 and item.resolution == "unresolved" for item in packages) else "degraded" if unresolved else "consistent"
    expected_decision = "accept" if value.accepted else "reject" if expected_state == "conflicted" else "review"
    checks: list[RegistryFederationConsensusAuditFinding] = []
    checks.append(_finding(1, "exact-fields", set(value.to_dict()) == set(consensus_model.RegistryFederationConsensus.FIELDS), sorted(value.to_dict()), consensus_model.RegistryFederationConsensus.FIELDS, "consensus exposes the exact public field set"))
    checks.append(_finding(2, "public-boundary", _public(value.to_dict()), True, True, "consensus values remain public and path-free"))
    checks.append(_finding(3, "federation-conservation", value.federation_address.startswith(federation_model.FEDERATION_PREFIX + ":"), value.federation_address, "federation address", "consensus points to one federation receipt"))
    checks.append(_finding(4, "quorum-conservation", 1 <= value.quorum <= MAX_PEERS, value.quorum, f"one through {MAX_PEERS}", "consensus quorum is bounded"))
    checks.append(_finding(5, "package-conservation", len(packages) == value.package_count and tuple(item.ordinal for item in packages) == tuple(range(1, value.package_count + 1)), len(packages), value.package_count, "packages are ordered and counted exactly once"))
    checks.append(_finding(6, "candidate-conservation", all(item.candidate_count == len(item.candidates) and len({candidate.address for candidate in item.candidates}) == item.candidate_count for item in packages), sum(item.candidate_count for item in packages), "per-package candidate sets", "candidate counts equal unique address candidates"))
    checks.append(_finding(7, "candidate-support-conservation", all(candidate.support_count == len(candidate.peer_ids) and candidate.support_count <= candidate.expected_peer_count and candidate.quorum == value.quorum for package in packages for candidate in package.candidates), "candidate support and quorum", "candidate peer support", "candidate support equals unique supporting peers"))
    checks.append(_finding(8, "selection-conservation", all(sum(candidate.selected for candidate in package.candidates) <= 1 and (not package.selected_address or any(candidate.selected and candidate.address == package.selected_address for candidate in package.candidates)) for package in packages), selected, "at most one selected candidate per package", "selected addresses are explicit and linked"))
    checks.append(_finding(9, "resolution-conservation", value.selected_count == selected and value.unresolved_count == unresolved and value.resolvable_count == resolvable and all(package.resolution == ("selected" if any(candidate.selected for candidate in package.candidates) else "unresolved" if package.candidates else "absent") for package in packages), (value.selected_count, value.unresolved_count, value.resolvable_count), (selected, unresolved, resolvable), "resolution counters follow package rows"))
    checks.append(_finding(10, "state-conservation", value.state == expected_state, value.state, expected_state, "state follows unresolved and contested package rows"))
    checks.append(_finding(11, "decision-conservation", value.decision == expected_decision, value.decision, expected_decision, "decision follows state and acceptance"))
    checks.append(_finding(12, "action-conservation", value.action_count == len(actions) and tuple(item.ordinal for item in actions) == tuple(range(1, value.action_count + 1)) and all(item.package_id in {package.package_id for package in packages} for item in actions), value.action_count, len(actions), "actions are ordered and reference known packages"))
    checks.append(_finding(13, "manifest-conservation", all(package.evidence_addresses for package in packages if package.candidate_count), sum(bool(package.evidence_addresses) for package in packages), value.package_count, "candidate-bearing packages carry evidence"))
    checks.append(_finding(14, "content-address", consensus_model.address_consensus(value) == value.content_address and all(consensus_model.address_package(package) == package.content_address for package in packages) and all(consensus_model.address_candidate(candidate) == candidate.content_address for package in packages for candidate in package.candidates) and all(consensus_model.address_action(action) == action.content_address for action in actions), value.content_address, "replayed consensus and nested addresses", "all content addresses replay"))
    checks.append(_finding(15, "mapping-round-trip", consensus_model.consensus_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "canonical mapping", "original consensus", "mapping replay preserves the complete receipt"))
    checks.append(_finding(16, "path-free", all("/" not in address and "\\" not in address for package in packages for address in package.evidence_addresses for _ in (0,)), "path-free evidence", True, "evidence addresses contain no filesystem paths"))
    return tuple(checks)


def audit_consensus(value: consensus_model.RegistryFederationConsensus) -> RegistryFederationConsensusAudit:
    value = consensus_model.verify_consensus(value)
    checks = _audit_checks(value)
    provisional = RegistryFederationConsensusAudit(value.content_address, value.federation_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationConsensusAudit(provisional.consensus_address, provisional.federation_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationConsensusAudit:
    return verify_audit(RegistryFederationConsensusAudit.from_mapping(value))


def verify_audit(value: RegistryFederationConsensusAudit) -> RegistryFederationConsensusAudit:
    if not isinstance(value, RegistryFederationConsensusAudit) or (not value.content_address.endswith(":pending") and address_audit(value) != value.content_address):
        raise ValidationError("consensus audit is not valid")
    return value


def audit_json(value: RegistryFederationConsensusAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationConsensusAudit) -> str:
    value = verify_audit(value)
    stream = io.StringIO()
    stream.write("ordinal,check_id,passed,observed,expected,detail,content_address\n")
    for item in value.checks:
        stream.write(f"{item.ordinal},{item.check_id},{str(item.passed).lower()},{item.observed},{item.expected},{item.detail},{item.content_address}\n")
    return stream.getvalue()


def render_audit_markdown(value: RegistryFederationConsensusAudit) -> str:
    value = verify_audit(value)
    lines = ["# Package Registry Federation Consensus Audit", "", f"- Accepted: `{value.accepted}`", f"- Passed: `{value.passed_count}/{value.check_count}`", f"- Audit address: `{value.content_address}`", "", "| check | result | detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusAuditFinding.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"type": "string"}, "passed": {"type": "boolean"}, "observed": {"type": "string"}, "expected": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + FINDING_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationConsensusAudit.FIELDS), "properties": {"consensus_address": {"type": "string", "pattern": "^" + consensus_model.CONSENSUS_PREFIX + ":"}, "federation_address": {"type": "string", "pattern": "^" + federation_model.FEDERATION_PREFIX + ":"}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS, "items": check_schema()}, "check_count": {"type": "integer", "minimum": MAX_CHECKS, "maximum": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "finding_prefix": FINDING_PREFIX, "check_ids": CHECK_IDS, "features": ("independent consensus counter checks", "candidate support verification", "selection and resolution recomputation", "action reference validation", "mapping and nested address replay", "JSON CSV and Markdown exports"), "schemas": ("check", "audit")}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "FINDING_PREFIX", "RegistryFederationConsensusAudit", "RegistryFederationConsensusAuditFinding", "VERSION", "address_audit", "address_finding", "audit_consensus", "audit_csv", "audit_from_mapping", "audit_json", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
