"""Independent integrity audit for peer-agreement matrices."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from . import registry_federation_matrix as matrix_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry_federation as federation_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = matrix_model.VERSION + "-audit-v1"
BOUNDARY = matrix_model.BOUNDARY + "_audit"
AUDIT_PREFIX = federation_model.FEDERATION_PREFIX + "-matrix-audit"
FINDING_PREFIX = federation_model.FEDERATION_PREFIX + "-matrix-audit-finding"
MAX_CHECKS = len(matrix_model.CHECK_IDS)
MAX_TEXT = federation_model.MAX_TEXT
CHECK_IDS = matrix_model.CHECK_IDS


def _text(value: Any, field: str, maximum: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 192)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 512)
    if not value.startswith(prefix + ":") or "/" in value or "\\" in value:
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


class RegistryFederationMatrixAuditFinding:
    """One independently recomputed matrix invariant."""

    FIELDS = ("ordinal", "check_id", "passed", "observed", "expected", "detail", "content_address")

    def __init__(self, ordinal: int, check_id: str, passed: bool, observed: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "matrix audit finding ordinal", MAX_CHECKS, positive=True)
        self.check_id = _label(check_id, "matrix audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("matrix audit check ID is unsupported")
        self.passed = _bool(passed, "matrix audit finding result")
        self.observed = _text(observed, "matrix audit observed value")
        self.expected = _text(expected, "matrix audit expected value")
        self.detail = _text(detail, "matrix audit detail")
        self.content_address = _address(content_address, "matrix audit finding address", FINDING_PREFIX)
        if not self.content_address.endswith(":pending") and address_finding(self) != self.content_address:
            raise ValidationError("matrix audit finding address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("matrix audit finding crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationMatrixAuditFinding:
        value = _mapping(value, "matrix audit finding")
        _strict(value, set(cls.FIELDS), "matrix audit finding")
        return cls(*(value[field] for field in cls.FIELDS))


def address_finding(value: RegistryFederationMatrixAuditFinding) -> str:
    if not isinstance(value, RegistryFederationMatrixAuditFinding):
        raise ValidationError("matrix finding address requires a typed finding")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


class RegistryFederationMatrixAudit:
    """Audit receipt whose result is separate from matrix state."""

    FIELDS = ("matrix_address", "federation_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")

    def __init__(self, matrix_address: str, federation_address: str, checks: Sequence[RegistryFederationMatrixAuditFinding], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.matrix_address = _address(matrix_address, "matrix audit matrix address", matrix_model.MATRIX_PREFIX)
        self.federation_address = _address(federation_address, "matrix audit federation address", federation_model.FEDERATION_PREFIX)
        self.checks = tuple(checks)
        if len(self.checks) > MAX_CHECKS or any(not isinstance(item, RegistryFederationMatrixAuditFinding) for item in self.checks):
            raise ValidationError("matrix audit checks are outside the bound")
        self.check_count = _count(check_count, "matrix audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "matrix audit passed count", self.check_count)
        self.failed_count = _count(failed_count, "matrix audit failed count", self.check_count)
        self.accepted = _bool(accepted, "matrix audit acceptance")
        if self.check_count != len(self.checks) or tuple(item.ordinal for item in self.checks) != tuple(range(1, self.check_count + 1)) or len({item.check_id for item in self.checks}) != self.check_count:
            raise ValidationError("matrix audit check ordering is not conserved")
        if self.passed_count != sum(item.passed for item in self.checks) or self.failed_count != sum(not item.passed for item in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("matrix audit counters are not conserved")
        if self.check_count != MAX_CHECKS or tuple(item.check_id for item in self.checks) != CHECK_IDS:
            raise ValidationError("matrix audit does not cover the complete check set")
        self.content_address = _address(content_address, "matrix audit content address", AUDIT_PREFIX)
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("matrix audit content address does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("matrix audit crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"matrix_address": self.matrix_address, "federation_address": self.federation_address, "checks": tuple(item.to_dict() for item in self.checks), "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {key: value for key, value in self.to_dict().items() if key != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryFederationMatrixAudit:
        value = _mapping(value, "matrix audit")
        _strict(value, set(cls.FIELDS), "matrix audit")
        checks = tuple(value["checks"]) if isinstance(value["checks"], list) else value["checks"]
        return cls(value["matrix_address"], value["federation_address"], tuple(RegistryFederationMatrixAuditFinding.from_mapping(item) for item in checks), value["check_count"], value["passed_count"], value["failed_count"], value["accepted"], value["content_address"])


def address_audit(value: RegistryFederationMatrixAudit) -> str:
    if not isinstance(value, RegistryFederationMatrixAudit):
        raise ValidationError("matrix audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _finding(ordinal: int, check_id: str, passed: bool, observed: Any, expected: Any, detail: str) -> RegistryFederationMatrixAuditFinding:
    provisional = RegistryFederationMatrixAuditFinding(ordinal, check_id, passed, str(observed), str(expected), detail, FINDING_PREFIX + ":pending")
    return RegistryFederationMatrixAuditFinding(provisional.ordinal, provisional.check_id, provisional.passed, provisional.observed, provisional.expected, provisional.detail, address_finding(provisional))


def _audit_checks(value: matrix_model.RegistryFederationMatrix) -> tuple[RegistryFederationMatrixAuditFinding, ...]:
    observations = value.observations
    expected_pairs = len(value.peer_ids) * (len(value.peer_ids) - 1) // 2
    actual_pairs = tuple((item.left_peer_id, item.right_peer_id) for item in observations)
    matching = sum(item.state == "consistent" for item in observations)
    divergent = sum(item.state == "conflicted" for item in observations)
    matching_packages = sum(item.matching_package_count for item in observations)
    divergent_packages = sum(item.divergent_package_count for item in observations)
    left_only = sum(item.left_only_count for item in observations)
    right_only = sum(item.right_only_count for item in observations)
    checks: list[RegistryFederationMatrixAuditFinding] = []
    checks.append(_finding(1, "exact-fields", set(value.to_dict()) == set(matrix_model.RegistryFederationMatrix.FIELDS), sorted(value.to_dict()), matrix_model.RegistryFederationMatrix.FIELDS, "matrix exposes the exact public field set"))
    checks.append(_finding(2, "public-boundary", _public(value.to_dict()), True, True, "matrix values remain public and path-free"))
    checks.append(_finding(3, "federation-conservation", bool(value.federation_address.startswith(federation_model.FEDERATION_PREFIX + ":")), value.federation_address, "federation address", "matrix points to one federation receipt"))
    checks.append(_finding(4, "peer-conservation", len(value.peer_ids) >= 1 and len(set(value.peer_ids)) == len(value.peer_ids), len(value.peer_ids), "one or more unique peers", "peer IDs are unique and non-empty"))
    checks.append(_finding(5, "pair-conservation", value.pair_count == expected_pairs and set(actual_pairs) == set(__import__("itertools").combinations(value.peer_ids, 2)), value.pair_count, expected_pairs, "every unordered peer pair appears exactly once"))
    checks.append(_finding(6, "observation-conservation", len(observations) == value.pair_count and all(item.left_peer_id < item.right_peer_id for item in observations), len(observations), value.pair_count, "observations cover the declared pair count"))
    checks.append(_finding(7, "ordinal-conservation", tuple(item.ordinal for item in observations) == tuple(range(1, value.pair_count + 1)), tuple(item.ordinal for item in observations), tuple(range(1, value.pair_count + 1)), "observation ordinals are contiguous"))
    checks.append(_finding(8, "package-conservation", all(len(item.package_ids) == item.common_package_count + item.left_only_count + item.right_only_count for item in observations), sum(len(item.package_ids) for item in observations), "per-observation unions", "package unions equal common plus one-sided observations"))
    expected_ratio = matrix_model._comparison_ratio(matching_packages, divergent_packages, left_only, right_only)
    checks.append(_finding(9, "count-conservation", value.matching_pair_count == matching and value.divergent_pair_count == divergent, (value.matching_pair_count, value.divergent_pair_count), (matching, divergent), "pair state counters equal recomputed states"))
    checks.append(_finding(10, "ratio-conservation", value.agreement_ratio == expected_ratio and all(item.agreement_ratio == matrix_model._comparison_ratio(item.matching_package_count, item.divergent_package_count, item.left_only_count, item.right_only_count) for item in observations), value.agreement_ratio, expected_ratio, "global and pair ratios are deterministically recomputed"))
    checks.append(_finding(11, "state-conservation", value.state == ("consistent" if divergent == 0 else "conflicted") and all(item.state == ("consistent" if item.divergent_package_count + item.left_only_count + item.right_only_count == 0 else "conflicted") for item in observations), value.state, "consistent or conflicted", "matrix state follows pair differences"))
    checks.append(_finding(12, "evidence-conservation", all(item.evidence_addresses and tuple(sorted(set(item.evidence_addresses))) == item.evidence_addresses for item in observations), sum(bool(item.evidence_addresses) for item in observations), len(observations), "every pair carries canonical evidence addresses"))
    checks.append(_finding(13, "address-conservation", all(matrix_model.address_observation(item) == item.content_address for item in observations), "replayed observation addresses", "stored observation addresses", "each observation content address replays"))
    checks.append(_finding(14, "mapping-round-trip", matrix_model.matrix_from_mapping(value.to_dict()).to_dict() == value.to_dict(), "canonical mapping", "original matrix", "mapping conversion preserves the matrix"))
    checks.append(_finding(15, "content-address", matrix_model.address_matrix(value) == value.content_address, value.content_address, matrix_model.address_matrix(value), "matrix content address replays"))
    checks.append(_finding(16, "path-free", all("/" not in address and "\\" not in address for item in observations for address in item.evidence_addresses), "path-free evidence", True, "evidence addresses contain no filesystem paths"))
    return tuple(checks)


def audit_matrix(value: matrix_model.RegistryFederationMatrix) -> RegistryFederationMatrixAudit:
    value = matrix_model.verify_matrix(value)
    checks = _audit_checks(value)
    provisional = RegistryFederationMatrixAudit(value.content_address, value.federation_address, checks, len(checks), sum(item.passed for item in checks), sum(not item.passed for item in checks), all(item.passed for item in checks), AUDIT_PREFIX + ":pending")
    return RegistryFederationMatrixAudit(provisional.matrix_address, provisional.federation_address, provisional.checks, provisional.check_count, provisional.passed_count, provisional.failed_count, provisional.accepted, address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryFederationMatrixAudit:
    return verify_audit(RegistryFederationMatrixAudit.from_mapping(value))


def verify_audit(value: RegistryFederationMatrixAudit) -> RegistryFederationMatrixAudit:
    if not isinstance(value, RegistryFederationMatrixAudit) or (not value.content_address.endswith(":pending") and address_audit(value) != value.content_address):
        raise ValidationError("matrix audit is not valid")
    return value


def audit_json(value: RegistryFederationMatrixAudit) -> str:
    return canonical_json(verify_audit(value).to_dict())


def audit_csv(value: RegistryFederationMatrixAudit) -> str:
    value = verify_audit(value)
    return "ordinal,check_id,passed,observed,expected,detail,content_address\n" + "".join(f"{item.ordinal},{item.check_id},{str(item.passed).lower()},{item.observed},{item.expected},{item.detail},{item.content_address}\n" for item in value.checks)


def render_audit_markdown(value: RegistryFederationMatrixAudit) -> str:
    value = verify_audit(value)
    lines = ["# Package Registry Federation Matrix Audit", "", f"- Accepted: `{value.accepted}`", f"- Passed: `{value.passed_count}/{value.check_count}`", f"- Audit address: `{value.content_address}`", "", "| check | result | detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | `{item.passed}` | {item.detail} |" for item in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationMatrixAuditFinding.FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"type": "string"}, "passed": {"type": "boolean"}, "observed": {"type": "string"}, "expected": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + FINDING_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False, "required": list(RegistryFederationMatrixAudit.FIELDS), "properties": {"matrix_address": {"type": "string", "pattern": "^" + matrix_model.MATRIX_PREFIX + ":"}, "federation_address": {"type": "string", "pattern": "^" + federation_model.FEDERATION_PREFIX + ":"}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS, "items": check_schema()}, "check_count": {"type": "integer", "minimum": MAX_CHECKS, "maximum": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "finding_prefix": FINDING_PREFIX, "check_ids": CHECK_IDS, "features": ("independent pair conservation", "ratio recomputation", "state recomputation", "evidence address checks", "mapping and content-address checks", "JSON CSV and Markdown exports"), "schemas": ("check", "audit")}


__all__ = ["AUDIT_PREFIX", "BOUNDARY", "CHECK_IDS", "FINDING_PREFIX", "RegistryFederationMatrixAudit", "RegistryFederationMatrixAuditFinding", "VERSION", "address_audit", "address_finding", "audit_csv", "audit_from_mapping", "audit_json", "audit_matrix", "audit_schema", "capabilities", "check_schema", "render_audit_markdown", "verify_audit"]
