"""Public contracts for the registry-store promotion gate.

The store records what happened.  The gate records whether a particular store
state is eligible for a named release action.  A gate is a deterministic,
addressed review projection: it contains checks, severities, decision state,
and source addresses, but no source attestation payloads or local attribution.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_VERSION = (
    "release-assurance-attestation-registry-store-gate-v1"
)
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_SCHEMA_VERSION = (
    "release-assurance-attestation-registry-store-gate-schema-v1"
)
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PLAN_VERSION = (
    "release-assurance-attestation-registry-store-gate-plan-v1"
)
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_DIFF_VERSION = (
    "release-assurance-attestation-registry-store-gate-diff-v1"
)
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_BOUNDARY = (
    "public_longitudinal_release_registry_store_gate"
)
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_MAX_CHECKS = 64
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_DEFAULT_LIMIT = 50
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_MAX_LIMIT = 500
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_EXPECTED_CHECK_COUNT = 20
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_SEVERITIES = (
    "none",
    "moderate",
    "high",
    "critical",
)


def _text(value: Any, field: str, *, maximum: int = 240) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    result = str(value).strip()
    if not result:
        raise ValidationError(f"{field} must not be empty")
    if len(result) > maximum:
        raise ValidationError(f"{field} exceeds the maximum length")
    return result


def _optional_text(value: Any, field: str, *, maximum: int = 240) -> str | None:
    if value is None:
        return None
    return _text(value, field, maximum=maximum)


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return {str(key): item for key, item in value.items()}


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _int(value: Any, field: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be an integer")
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"{field} must be an integer") from exc
    if result < minimum or (maximum is not None and result > maximum):
        bound = f"between {minimum} and {maximum}" if maximum is not None else f"at least {minimum}"
        raise ValidationError(f"{field} must be {bound}")
    return result


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(dict(body), prefix=prefix)


class ReleaseAssuranceAttestationRegistryStoreGateState(StrEnum):
    READY = "ready"
    HOLD = "hold"
    BLOCKED = "blocked"


class ReleaseAssuranceAttestationRegistryStoreGateDecision(StrEnum):
    PROMOTE = "promote"
    RETAIN = "retain"
    BLOCK_RELEASE = "block-release"


class ReleaseAssuranceAttestationRegistryStoreGateSeverity(StrEnum):
    NONE = "none"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationRegistryStoreGatePolicy:
    """Rules for deciding whether a store may cross a release boundary."""

    gate_id: str
    store_id: str
    registry_id: str
    require_accepted: bool = True
    require_audit: bool = True
    require_packet: bool = True
    require_no_rejections: bool = True
    require_baseline_continuity: bool = True
    max_entries: int = 256
    max_operations: int = 1024
    content_address: str = ""

    def _body(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "store_id": self.store_id,
            "registry_id": self.registry_id,
            "require_accepted": self.require_accepted,
            "require_audit": self.require_audit,
            "require_packet": self.require_packet,
            "require_no_rejections": self.require_no_rejections,
            "require_baseline_continuity": self.require_baseline_continuity,
            "max_entries": self.max_entries,
            "max_operations": self.max_operations,
        }

    def __post_init__(self) -> None:
        _text(self.gate_id, "gate_policy.gate_id", maximum=180)
        _text(self.store_id, "gate_policy.store_id", maximum=180)
        _text(self.registry_id, "gate_policy.registry_id", maximum=180)
        for field in (
            "require_accepted",
            "require_audit",
            "require_packet",
            "require_no_rejections",
            "require_baseline_continuity",
        ):
            _bool(getattr(self, field), f"gate_policy.{field}")
        _int(self.max_entries, "gate_policy.max_entries", minimum=1, maximum=256)
        _int(self.max_operations, "gate_policy.max_operations", minimum=1, maximum=4096)
        expected = _address(
            self._body(), "release-assurance-attestation-registry-store-gate-policy"
        )
        if self.content_address and self.content_address != expected:
            raise ValidationError("gate policy content address does not reconcile")
        object.__setattr__(self, "content_address", expected)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(
        cls, value: Mapping[str, Any]
    ) -> ReleaseAssuranceAttestationRegistryStoreGatePolicy:
        body = _mapping(value, "gate policy")
        allowed = {
            "gate_id",
            "store_id",
            "registry_id",
            "require_accepted",
            "require_audit",
            "require_packet",
            "require_no_rejections",
            "require_baseline_continuity",
            "max_entries",
            "max_operations",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"gate policy contains unsupported fields: {sorted(unknown)}")
        return cls(
            gate_id=_text(body.get("gate_id"), "gate_policy.gate_id", maximum=180),
            store_id=_text(body.get("store_id"), "gate_policy.store_id", maximum=180),
            registry_id=_text(body.get("registry_id"), "gate_policy.registry_id", maximum=180),
            require_accepted=_bool(body.get("require_accepted"), "gate_policy.require_accepted"),
            require_audit=_bool(body.get("require_audit"), "gate_policy.require_audit"),
            require_packet=_bool(body.get("require_packet"), "gate_policy.require_packet"),
            require_no_rejections=_bool(
                body.get("require_no_rejections"), "gate_policy.require_no_rejections"
            ),
            require_baseline_continuity=_bool(
                body.get("require_baseline_continuity"), "gate_policy.require_baseline_continuity"
            ),
            max_entries=_int(
                body.get("max_entries"), "gate_policy.max_entries", minimum=1, maximum=256
            ),
            max_operations=_int(
                body.get("max_operations"), "gate_policy.max_operations", minimum=1, maximum=4096
            ),
            content_address=_text(body.get("content_address"), "gate_policy.content_address"),
        )


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationRegistryStoreGateCheck:
    """One named promotion-gate check."""

    check_id: str
    category: str
    severity: ReleaseAssuranceAttestationRegistryStoreGateSeverity
    passed: bool
    observed: Any
    expected: Any
    detail: str
    content_address: str = ""

    def _body(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "category": self.category,
            "severity": self.severity,
            "passed": self.passed,
            "observed": self.observed,
            "expected": self.expected,
            "detail": self.detail,
        }

    def __post_init__(self) -> None:
        _text(self.check_id, "gate_check.check_id", maximum=180)
        _text(self.category, "gate_check.category", maximum=120)
        if not isinstance(self.severity, ReleaseAssuranceAttestationRegistryStoreGateSeverity):
            raise ValidationError("gate check severity is invalid")
        _bool(self.passed, "gate_check.passed")
        _text(self.detail, "gate_check.detail", maximum=500)
        object.__setattr__(self, "observed", jsonable(self.observed))
        object.__setattr__(self, "expected", jsonable(self.expected))
        expected = _address(self._body(), "release-assurance-attestation-registry-store-gate-check")
        if self.content_address and self.content_address != expected:
            raise ValidationError("gate check content address does not reconcile")
        object.__setattr__(self, "content_address", expected)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(
        cls, value: Mapping[str, Any]
    ) -> ReleaseAssuranceAttestationRegistryStoreGateCheck:
        body = _mapping(value, "gate check")
        allowed = {
            "check_id",
            "category",
            "severity",
            "passed",
            "observed",
            "expected",
            "detail",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"gate check contains unsupported fields: {sorted(unknown)}")
        try:
            severity = ReleaseAssuranceAttestationRegistryStoreGateSeverity(body.get("severity"))
        except ValueError as exc:
            raise ValidationError("gate check severity is invalid") from exc
        return cls(
            check_id=_text(body.get("check_id"), "gate_check.check_id", maximum=180),
            category=_text(body.get("category"), "gate_check.category", maximum=120),
            severity=severity,
            passed=_bool(body.get("passed"), "gate_check.passed"),
            observed=body.get("observed"),
            expected=body.get("expected"),
            detail=_text(body.get("detail"), "gate_check.detail", maximum=500),
            content_address=_text(body.get("content_address"), "gate_check.content_address"),
        )


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationRegistryStoreGateDiff:
    diff_version: str
    baseline_store_id: str
    candidate_store_id: str
    baseline_address: str
    candidate_address: str
    baseline_registry_address: str
    candidate_registry_address: str
    added_entry_count: int
    removed_entry_count: int
    changed_entry_count: int
    added_operation_count: int
    removed_operation_count: int
    changed_head: bool
    continuous: bool
    identical: bool
    accepted: bool
    content_address: str = ""

    def _body(self) -> dict[str, Any]:
        return {
            "diff_version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_DIFF_VERSION,
            "baseline_store_id": self.baseline_store_id,
            "candidate_store_id": self.candidate_store_id,
            "baseline_address": self.baseline_address,
            "candidate_address": self.candidate_address,
            "baseline_registry_address": self.baseline_registry_address,
            "candidate_registry_address": self.candidate_registry_address,
            "added_entry_count": self.added_entry_count,
            "removed_entry_count": self.removed_entry_count,
            "changed_entry_count": self.changed_entry_count,
            "added_operation_count": self.added_operation_count,
            "removed_operation_count": self.removed_operation_count,
            "changed_head": self.changed_head,
            "continuous": self.continuous,
            "identical": self.identical,
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        if self.diff_version != RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_DIFF_VERSION:
            raise ValidationError("gate diff version is invalid")
        _text(self.baseline_store_id, "gate_diff.baseline_store_id", maximum=180)
        _text(self.candidate_store_id, "gate_diff.candidate_store_id", maximum=180)
        for field in (
            "baseline_address",
            "candidate_address",
            "baseline_registry_address",
            "candidate_registry_address",
        ):
            _text(getattr(self, field), f"gate_diff.{field}")
        for field in (
            "added_entry_count",
            "removed_entry_count",
            "changed_entry_count",
            "added_operation_count",
            "removed_operation_count",
        ):
            _int(getattr(self, field), f"gate_diff.{field}", minimum=0)
        for field in ("changed_head", "continuous", "identical", "accepted"):
            _bool(getattr(self, field), f"gate_diff.{field}")
        expected = _address(self._body(), "release-assurance-attestation-registry-store-gate-diff")
        if self.content_address and self.content_address != expected:
            raise ValidationError("gate diff content address does not reconcile")
        object.__setattr__(self, "content_address", expected)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationRegistryStoreGate:
    """Addressed promotion decision for one store state."""

    gate_version: str
    schema_version: str
    gate_id: str
    store_id: str
    registry_id: str
    baseline_store_address: str | None
    candidate_store_address: str
    policy: ReleaseAssuranceAttestationRegistryStoreGatePolicy
    checks: tuple[ReleaseAssuranceAttestationRegistryStoreGateCheck, ...]
    state: ReleaseAssuranceAttestationRegistryStoreGateState
    decision: ReleaseAssuranceAttestationRegistryStoreGateDecision
    packet_verified: bool
    accepted: bool
    content_address: str

    @property
    def boundary(self) -> str:
        return RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_BOUNDARY

    @property
    def check_count(self) -> int:
        return len(self.checks)

    @property
    def passed_check_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    @property
    def critical_failure_count(self) -> int:
        return sum(
            not item.passed
            and item.severity is ReleaseAssuranceAttestationRegistryStoreGateSeverity.CRITICAL
            for item in self.checks
        )

    def _body(self) -> dict[str, Any]:
        return {
            "gate_version": self.gate_version,
            "schema_version": self.schema_version,
            "gate_id": self.gate_id,
            "store_id": self.store_id,
            "registry_id": self.registry_id,
            "baseline_store_address": self.baseline_store_address,
            "candidate_store_address": self.candidate_store_address,
            "policy": self.policy.to_dict(),
            "checks": tuple(item.to_dict() for item in self.checks),
            "state": self.state,
            "decision": self.decision,
            "packet_verified": self.packet_verified,
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        if self.gate_version != RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_VERSION:
            raise ValidationError("store gate version is invalid")
        if self.schema_version != RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_SCHEMA_VERSION:
            raise ValidationError("store gate schema version is invalid")
        _text(self.gate_id, "gate.gate_id", maximum=180)
        _text(self.store_id, "gate.store_id", maximum=180)
        _text(self.registry_id, "gate.registry_id", maximum=180)
        _optional_text(self.baseline_store_address, "gate.baseline_store_address")
        _text(self.candidate_store_address, "gate.candidate_store_address")
        if self.policy.store_id != self.store_id or self.policy.registry_id != self.registry_id:
            raise ValidationError("gate policy and gate identity do not reconcile")
        if (
            not self.checks
            or len(self.checks) > RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_MAX_CHECKS
        ):
            raise ValidationError("gate check count is outside its contract")
        if not isinstance(self.state, ReleaseAssuranceAttestationRegistryStoreGateState):
            raise ValidationError("gate state is invalid")
        if not isinstance(self.decision, ReleaseAssuranceAttestationRegistryStoreGateDecision):
            raise ValidationError("gate decision is invalid")
        _bool(self.packet_verified, "gate.packet_verified")
        _bool(self.accepted, "gate.accepted")
        expected = _address(self._body(), "release-assurance-attestation-registry-store-gate")
        if expected != self.content_address:
            raise ValidationError("gate content address does not reconcile")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            self._body()
            | {
                "boundary": self.boundary,
                "check_count": self.check_count,
                "passed_check_count": self.passed_check_count,
                "failed_check_ids": self.failed_check_ids,
                "critical_failure_count": self.critical_failure_count,
                "content_address": self.content_address,
            }
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ReleaseAssuranceAttestationRegistryStoreGate:
        body = _mapping(value, "store gate")
        allowed = {
            "gate_version",
            "schema_version",
            "gate_id",
            "store_id",
            "registry_id",
            "baseline_store_address",
            "candidate_store_address",
            "policy",
            "checks",
            "state",
            "decision",
            "packet_verified",
            "accepted",
            "content_address",
            "boundary",
            "check_count",
            "passed_check_count",
            "failed_check_ids",
            "critical_failure_count",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"store gate contains unsupported fields: {sorted(unknown)}")
        raw_checks = body.get("checks")
        if not isinstance(raw_checks, (list, tuple)):
            raise ValidationError("store gate checks must be an array")
        try:
            state = ReleaseAssuranceAttestationRegistryStoreGateState(body.get("state"))
            decision = ReleaseAssuranceAttestationRegistryStoreGateDecision(body.get("decision"))
        except ValueError as exc:
            raise ValidationError("store gate enum value is invalid") from exc
        gate = cls(
            gate_version=_text(body.get("gate_version"), "gate.gate_version"),
            schema_version=_text(body.get("schema_version"), "gate.schema_version"),
            gate_id=_text(body.get("gate_id"), "gate.gate_id", maximum=180),
            store_id=_text(body.get("store_id"), "gate.store_id", maximum=180),
            registry_id=_text(body.get("registry_id"), "gate.registry_id", maximum=180),
            baseline_store_address=_optional_text(
                body.get("baseline_store_address"), "gate.baseline_store_address"
            ),
            candidate_store_address=_text(
                body.get("candidate_store_address"), "gate.candidate_store_address"
            ),
            policy=ReleaseAssuranceAttestationRegistryStoreGatePolicy.from_mapping(
                _mapping(body.get("policy"), "gate.policy")
            ),
            checks=tuple(
                ReleaseAssuranceAttestationRegistryStoreGateCheck.from_mapping(item)
                for item in raw_checks
            ),
            state=state,
            decision=decision,
            packet_verified=_bool(body.get("packet_verified"), "gate.packet_verified"),
            accepted=_bool(body.get("accepted"), "gate.accepted"),
            content_address=_text(body.get("content_address"), "gate.content_address"),
        )
        if body.get("boundary") not in (
            None,
            RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_BOUNDARY,
        ):
            raise ValidationError("store gate boundary is invalid")
        if body.get("check_count") != gate.check_count:
            raise ValidationError("store gate check count does not reconcile")
        if body.get("passed_check_count") != gate.passed_check_count:
            raise ValidationError("store gate passed check count does not reconcile")
        if tuple(body.get("failed_check_ids", ())) != gate.failed_check_ids:
            raise ValidationError("store gate failed check IDs do not reconcile")
        if body.get("critical_failure_count") != gate.critical_failure_count:
            raise ValidationError("store gate critical failure count does not reconcile")
        return gate


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationRegistryStoreGatePlan:
    """A preflight plan for appending and promoting a candidate attestation."""

    plan_version: str
    gate_id: str
    store_id: str
    registry_id: str
    current_store_address: str
    expected_head_address: str
    candidate_attestation_id: str
    candidate_attestation_address: str
    proposed_action: str
    gate_address: str
    accepted: bool
    content_address: str

    def _body(self) -> dict[str, Any]:
        return {
            "plan_version": self.plan_version,
            "gate_id": self.gate_id,
            "store_id": self.store_id,
            "registry_id": self.registry_id,
            "current_store_address": self.current_store_address,
            "expected_head_address": self.expected_head_address,
            "candidate_attestation_id": self.candidate_attestation_id,
            "candidate_attestation_address": self.candidate_attestation_address,
            "proposed_action": self.proposed_action,
            "gate_address": self.gate_address,
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        if self.plan_version != RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PLAN_VERSION:
            raise ValidationError("store gate plan version is invalid")
        for field in (
            "gate_id",
            "store_id",
            "registry_id",
            "current_store_address",
            "expected_head_address",
            "candidate_attestation_id",
            "candidate_attestation_address",
            "proposed_action",
            "gate_address",
        ):
            _text(getattr(self, field), f"gate_plan.{field}", maximum=220)
        _bool(self.accepted, "gate_plan.accepted")
        expected = _address(self._body(), "release-assurance-attestation-registry-store-gate-plan")
        if expected != self.content_address:
            raise ValidationError("store gate plan content address does not reconcile")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationRegistryStoreGateQueryResult:
    gate_id: str
    resource: str
    filters: dict[str, Any]
    total: int
    offset: int
    limit: int
    items: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"has_more": self.has_more}


__all__ = [
    name
    for name in globals()
    if name.startswith("RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE")
    or name.startswith("ReleaseAssuranceAttestationRegistryStoreGate")
]
