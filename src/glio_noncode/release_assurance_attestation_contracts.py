"""Typed contracts for the final cross-plane release attestation.

The attestation is deliberately narrower than the source systems it binds.
It carries public counters, states, and content addresses, never source rows,
workflow inputs, or execution payloads.  Each contract is immutable and its
address is derived from the canonical fields that are visible to consumers.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

RELEASE_ASSURANCE_ATTESTATION_VERSION = "release-assurance-attestation-v1"
RELEASE_ASSURANCE_ATTESTATION_SCHEMA_VERSION = "release-assurance-attestation-schema-v1"
RELEASE_ASSURANCE_ATTESTATION_POLICY_VERSION = "release-assurance-attestation-policy-v1"
RELEASE_ASSURANCE_ATTESTATION_RUNTIME_VERSION = "release-assurance-attestation-runtime-v1"
RELEASE_ASSURANCE_ATTESTATION_PACKET_VERSION = "release-assurance-attestation-packet-v1"
RELEASE_ASSURANCE_ATTESTATION_QUERY_VERSION = "release-assurance-attestation-query-v1"
RELEASE_ASSURANCE_ATTESTATION_DIFF_VERSION = "release-assurance-attestation-diff-v1"
RELEASE_ASSURANCE_ATTESTATION_OBSERVABILITY_VERSION = (
    "release-assurance-attestation-observability-v1"
)
RELEASE_ASSURANCE_ATTESTATION_BOUNDARY = "public_whole_product_release_attestation"
RELEASE_ASSURANCE_ATTESTATION_COMPONENT_IDS = (
    "release-assurance",
    "program-release-closure",
    "mission-plan-release-catalog-gate",
)
RELEASE_ASSURANCE_ATTESTATION_COMPONENT_COUNT = len(RELEASE_ASSURANCE_ATTESTATION_COMPONENT_IDS)
RELEASE_ASSURANCE_ATTESTATION_CHECKS_PER_COMPONENT = 6
RELEASE_ASSURANCE_ATTESTATION_CROSS_CHECK_COUNT = 8
RELEASE_ASSURANCE_ATTESTATION_CHECK_COUNT = (
    RELEASE_ASSURANCE_ATTESTATION_COMPONENT_COUNT
    * RELEASE_ASSURANCE_ATTESTATION_CHECKS_PER_COMPONENT
    + RELEASE_ASSURANCE_ATTESTATION_CROSS_CHECK_COUNT
)
RELEASE_ASSURANCE_ATTESTATION_RUNTIME_STAGE_TOTAL = 8
RELEASE_ASSURANCE_ATTESTATION_PACKET_PAYLOAD_COUNT = 7
RELEASE_ASSURANCE_ATTESTATION_PACKET_ARTIFACT_COUNT = (
    RELEASE_ASSURANCE_ATTESTATION_PACKET_PAYLOAD_COUNT + 1
)
RELEASE_ASSURANCE_ATTESTATION_MAX_PACKET_ARTIFACTS = 32
RELEASE_ASSURANCE_ATTESTATION_DEFAULT_LIMIT = 50
RELEASE_ASSURANCE_ATTESTATION_MAX_LIMIT = 500
RELEASE_ASSURANCE_ATTESTATION_RESOURCE_NAMES = ("components", "checks")


def _text(value: Any, field: str, *, maximum: int = 240) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    normalized = str(value).strip()
    if not normalized:
        raise ValidationError(f"{field} must not be empty")
    if len(normalized) > maximum:
        raise ValidationError(f"{field} exceeds the maximum length")
    return normalized


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return {str(key): item for key, item in value.items()}


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _int(value: Any, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"{field} must be an integer") from exc
    if parsed < minimum:
        raise ValidationError(f"{field} must be at least {minimum}")
    return parsed


def _float(value: Any, field: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"{field} must be numeric") from exc
    if parsed < 0 or parsed > 100:
        raise ValidationError(f"{field} must be between 0 and 100")
    return parsed


def _strings(value: Any, field: str, *, maximum: int = 64) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValidationError(f"{field} must be an array")
    result = tuple(_text(item, f"{field}[{index}]") for index, item in enumerate(value))
    if len(result) > maximum or len(result) != len(set(result)):
        raise ValidationError(f"{field} must be bounded and unique")
    return result


def _freeze(value: Any) -> Any:
    """Normalize JSON arrays so hydrated contracts equal in-memory contracts."""

    if isinstance(value, Mapping):
        return {str(key): _freeze(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationPolicy:
    """Explicit acceptance requirements for the cross-plane attestation."""

    policy_id: str = "default-release-assurance-attestation"
    require_runtime_accepted: bool = True
    require_program_release_accepted: bool = True
    require_catalog_gate_accepted: bool = True
    minimum_runtime_stage_count: int = RELEASE_ASSURANCE_ATTESTATION_RUNTIME_STAGE_TOTAL
    minimum_program_domain_count: int = 16
    minimum_catalog_entry_count: int = 1
    minimum_catalog_check_count: int = 1
    require_unique_component_addresses: bool = True
    require_all_checks_passed: bool = True
    required_component_ids: tuple[str, ...] = RELEASE_ASSURANCE_ATTESTATION_COMPONENT_IDS

    @property
    def content_address(self) -> str:
        return content_hash(self.to_dict(), prefix="release-assurance-attestation-policy")

    def __post_init__(self) -> None:
        _text(self.policy_id, "attestation_policy.policy_id", maximum=120)
        for field in (
            "minimum_runtime_stage_count",
            "minimum_program_domain_count",
            "minimum_catalog_entry_count",
            "minimum_catalog_check_count",
        ):
            _int(getattr(self, field), f"attestation_policy.{field}")
        for field in (
            "require_runtime_accepted",
            "require_program_release_accepted",
            "require_catalog_gate_accepted",
            "require_unique_component_addresses",
            "require_all_checks_passed",
        ):
            _bool(getattr(self, field), f"attestation_policy.{field}")
        if tuple(self.required_component_ids) != RELEASE_ASSURANCE_ATTESTATION_COMPONENT_IDS:
            raise ValidationError("attestation policy component IDs are not closed")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            {
                "policy_version": RELEASE_ASSURANCE_ATTESTATION_POLICY_VERSION,
                "policy_id": self.policy_id,
                "require_runtime_accepted": self.require_runtime_accepted,
                "require_program_release_accepted": self.require_program_release_accepted,
                "require_catalog_gate_accepted": self.require_catalog_gate_accepted,
                "minimum_runtime_stage_count": self.minimum_runtime_stage_count,
                "minimum_program_domain_count": self.minimum_program_domain_count,
                "minimum_catalog_entry_count": self.minimum_catalog_entry_count,
                "minimum_catalog_check_count": self.minimum_catalog_check_count,
                "require_unique_component_addresses": self.require_unique_component_addresses,
                "require_all_checks_passed": self.require_all_checks_passed,
                "required_component_ids": self.required_component_ids,
            }
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ReleaseAssuranceAttestationPolicy:
        body = _mapping(value, "attestation policy")
        allowed = set(cls().to_dict())
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(
                f"attestation policy contains unsupported fields: {sorted(unknown)}"
            )
        if (
            body.get("policy_version", RELEASE_ASSURANCE_ATTESTATION_POLICY_VERSION)
            != RELEASE_ASSURANCE_ATTESTATION_POLICY_VERSION
        ):
            raise ValidationError("attestation policy version is invalid")
        defaults = cls()
        bool_values = {
            field: _bool(body[field], f"attestation_policy.{field}")
            if field in body
            else getattr(defaults, field)
            for field in (
                "require_runtime_accepted",
                "require_program_release_accepted",
                "require_catalog_gate_accepted",
                "require_unique_component_addresses",
                "require_all_checks_passed",
            )
        }
        return cls(
            policy_id=str(body.get("policy_id", defaults.policy_id)),
            **bool_values,
            minimum_runtime_stage_count=_int(
                body.get("minimum_runtime_stage_count", defaults.minimum_runtime_stage_count),
                "attestation_policy.minimum_runtime_stage_count",
            ),
            minimum_program_domain_count=_int(
                body.get("minimum_program_domain_count", defaults.minimum_program_domain_count),
                "attestation_policy.minimum_program_domain_count",
            ),
            minimum_catalog_entry_count=_int(
                body.get("minimum_catalog_entry_count", defaults.minimum_catalog_entry_count),
                "attestation_policy.minimum_catalog_entry_count",
            ),
            minimum_catalog_check_count=_int(
                body.get("minimum_catalog_check_count", defaults.minimum_catalog_check_count),
                "attestation_policy.minimum_catalog_check_count",
            ),
            required_component_ids=_strings(
                body.get("required_component_ids", defaults.required_component_ids),
                "attestation_policy.required_component_ids",
            ),
        )


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationComponent:
    """Aggregate component row bound to one source plane."""

    component_id: str
    title: str
    source_address: str
    state: str
    observed_count: int
    expected_count: int
    readiness_percent: float
    dependency_ids: tuple[str, ...]
    limitations: tuple[str, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        _text(self.component_id, "attestation_component.component_id", maximum=96)
        _text(self.title, "attestation_component.title", maximum=180)
        _text(self.source_address, "attestation_component.source_address")
        _text(self.state, "attestation_component.state", maximum=48)
        _int(self.observed_count, "attestation_component.observed_count")
        _int(self.expected_count, "attestation_component.expected_count")
        if self.expected_count == 0:
            raise ValidationError("attestation component expected count must be positive")
        _float(self.readiness_percent, "attestation_component.readiness_percent")
        _strings(self.dependency_ids, "attestation_component.dependency_ids")
        _strings(self.limitations, "attestation_component.limitations")
        _text(self.content_address, "attestation_component.content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ReleaseAssuranceAttestationComponent:
        body = _mapping(value, "attestation component")
        allowed = {
            "component_id",
            "title",
            "source_address",
            "state",
            "observed_count",
            "expected_count",
            "readiness_percent",
            "dependency_ids",
            "limitations",
            "accepted",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(
                f"attestation component contains unsupported fields: {sorted(unknown)}"
            )
        component = cls(
            component_id=_text(
                body.get("component_id"), "attestation_component.component_id", maximum=96
            ),
            title=_text(body.get("title"), "attestation_component.title", maximum=180),
            source_address=_text(
                body.get("source_address"), "attestation_component.source_address"
            ),
            state=_text(body.get("state"), "attestation_component.state", maximum=48),
            observed_count=_int(body.get("observed_count"), "attestation_component.observed_count"),
            expected_count=_int(body.get("expected_count"), "attestation_component.expected_count"),
            readiness_percent=_float(
                body.get("readiness_percent"), "attestation_component.readiness_percent"
            ),
            dependency_ids=_strings(
                body.get("dependency_ids", ()), "attestation_component.dependency_ids"
            ),
            limitations=_strings(body.get("limitations", ()), "attestation_component.limitations"),
            accepted=_bool(body.get("accepted"), "attestation_component.accepted"),
            content_address=_text(
                body.get("content_address"), "attestation_component.content_address"
            ),
        )
        expected = content_hash(
            {key: item for key, item in component.to_dict().items() if key != "content_address"},
            prefix="release-assurance-attestation-component",
        )
        if expected != component.content_address:
            raise ValidationError("attestation component content address does not reconcile")
        return component


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationCheck:
    """One retained acceptance, conservation, or boundary check."""

    check_id: str
    component_id: str
    category: str
    passed: bool
    observed: Any
    expected: Any
    evidence_addresses: tuple[str, ...]
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ReleaseAssuranceAttestationCheck:
        body = _mapping(value, "attestation check")
        allowed = {
            "check_id",
            "component_id",
            "category",
            "passed",
            "observed",
            "expected",
            "evidence_addresses",
            "detail",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(
                f"attestation check contains unsupported fields: {sorted(unknown)}"
            )
        check = cls(
            check_id=_text(body.get("check_id"), "attestation_check.check_id", maximum=160),
            component_id=_text(
                body.get("component_id"), "attestation_check.component_id", maximum=96
            ),
            category=_text(body.get("category"), "attestation_check.category", maximum=64),
            passed=_bool(body.get("passed"), "attestation_check.passed"),
            observed=_freeze(body.get("observed")),
            expected=_freeze(body.get("expected")),
            evidence_addresses=_strings(
                body.get("evidence_addresses", ()), "attestation_check.evidence_addresses"
            ),
            detail=_text(body.get("detail"), "attestation_check.detail", maximum=360),
            content_address=_text(body.get("content_address"), "attestation_check.content_address"),
        )
        expected = content_hash(
            {key: item for key, item in check.to_dict().items() if key != "content_address"},
            prefix="release-assurance-attestation-check",
        )
        if expected != check.content_address:
            raise ValidationError("attestation check content address does not reconcile")
        return check


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestation:
    """Final public cross-plane release decision."""

    attestation_version: str
    schema_version: str
    attestation_id: str
    bundle_id: str
    run_id: str
    policy: ReleaseAssuranceAttestationPolicy
    components: tuple[ReleaseAssuranceAttestationComponent, ...]
    checks: tuple[ReleaseAssuranceAttestationCheck, ...]
    overall_percent: float
    accepted: bool
    content_address: str

    @property
    def boundary(self) -> str:
        return RELEASE_ASSURANCE_ATTESTATION_BOUNDARY

    @property
    def component_count(self) -> int:
        return len(self.components)

    @property
    def check_count(self) -> int:
        return len(self.checks)

    @property
    def passed_check_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def _body(self) -> dict[str, Any]:
        return {
            "attestation_version": self.attestation_version,
            "schema_version": self.schema_version,
            "attestation_id": self.attestation_id,
            "bundle_id": self.bundle_id,
            "run_id": self.run_id,
            "policy": self.policy,
            "components": self.components,
            "checks": self.checks,
            "overall_percent": self.overall_percent,
            "accepted": self.accepted,
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            self._body()
            | {
                "boundary": self.boundary,
                "component_count": self.component_count,
                "check_count": self.check_count,
                "passed_check_count": self.passed_check_count,
                "failed_check_ids": self.failed_check_ids,
            }
            | {"content_address": self.content_address}
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ReleaseAssuranceAttestation:
        body = _mapping(value, "release-assurance attestation")
        allowed = {
            "attestation_version",
            "schema_version",
            "attestation_id",
            "bundle_id",
            "run_id",
            "policy",
            "components",
            "checks",
            "overall_percent",
            "accepted",
            "content_address",
            "boundary",
            "component_count",
            "check_count",
            "passed_check_count",
            "failed_check_ids",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"attestation contains unsupported fields: {sorted(unknown)}")
        if body.get("attestation_version") != RELEASE_ASSURANCE_ATTESTATION_VERSION:
            raise ValidationError("attestation version is invalid")
        if body.get("schema_version") != RELEASE_ASSURANCE_ATTESTATION_SCHEMA_VERSION:
            raise ValidationError("attestation schema version is invalid")
        if body.get("boundary") not in (None, RELEASE_ASSURANCE_ATTESTATION_BOUNDARY):
            raise ValidationError("attestation boundary is invalid")
        raw_components = body.get("components")
        raw_checks = body.get("checks")
        if not isinstance(raw_components, (list, tuple)) or not isinstance(
            raw_checks, (list, tuple)
        ):
            raise ValidationError("attestation components and checks must be arrays")
        components = tuple(
            ReleaseAssuranceAttestationComponent.from_mapping(item) for item in raw_components
        )
        checks = tuple(ReleaseAssuranceAttestationCheck.from_mapping(item) for item in raw_checks)
        policy_value = body.get("policy")
        if not isinstance(policy_value, Mapping):
            raise ValidationError("attestation policy must be an object")
        attestation = cls(
            attestation_version=str(body.get("attestation_version")),
            schema_version=str(body.get("schema_version")),
            attestation_id=_text(
                body.get("attestation_id"), "attestation.attestation_id", maximum=120
            ),
            bundle_id=_text(body.get("bundle_id"), "attestation.bundle_id", maximum=160),
            run_id=_text(body.get("run_id"), "attestation.run_id", maximum=160),
            policy=ReleaseAssuranceAttestationPolicy.from_mapping(policy_value),
            components=components,
            checks=checks,
            overall_percent=_float(body.get("overall_percent"), "attestation.overall_percent"),
            accepted=_bool(body.get("accepted"), "attestation.accepted"),
            content_address=_text(body.get("content_address"), "attestation.content_address"),
        )
        if (
            body.get("component_count") != attestation.component_count
            or body.get("check_count") != attestation.check_count
        ):
            raise ValidationError("attestation counters do not reconcile")
        if body.get("passed_check_count") != attestation.passed_check_count:
            raise ValidationError("attestation passed-check counter does not reconcile")
        if tuple(body.get("failed_check_ids", ())) != attestation.failed_check_ids:
            raise ValidationError("attestation failed-check IDs do not reconcile")
        expected = content_hash(attestation._body(), prefix="release-assurance-attestation")
        if expected != attestation.content_address:
            raise ValidationError("attestation content address does not reconcile")
        return attestation


class ReleaseAssuranceAttestationRuntimeState(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationRuntimeStage:
    ordinal: int
    stage_id: str
    state: ReleaseAssuranceAttestationRuntimeState
    input_address: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationReplay:
    first_address: str
    second_address: str
    expected_address: str
    deterministic: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationRuntimeReport:
    run_id: str
    state: ReleaseAssuranceAttestationRuntimeState
    stages: tuple[ReleaseAssuranceAttestationRuntimeStage, ...]
    attestation: ReleaseAssuranceAttestation
    replay: ReleaseAssuranceAttestationReplay
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "stage_count": len(self.stages),
            "failed_stage_ids": tuple(
                item.stage_id
                for item in self.stages
                if item.state is ReleaseAssuranceAttestationRuntimeState.BLOCKED
            ),
        }


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationPacketArtifact:
    artifact_id: str
    relative_path: str
    media_type: str
    role: str
    source_address: str
    byte_count: int
    line_count: int
    content_address: str
    content: bytes
    required: bool = True

    def metadata_dict(self) -> dict[str, Any]:
        return jsonable(
            {
                "artifact_id": self.artifact_id,
                "relative_path": self.relative_path,
                "media_type": self.media_type,
                "role": self.role,
                "source_address": self.source_address,
                "byte_count": self.byte_count,
                "line_count": self.line_count,
                "content_address": self.content_address,
                "required": self.required,
            }
        )

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        body = self.metadata_dict()
        if include_content:
            body["content"] = self.content.decode("utf-8")
        return body


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationPacketManifest:
    version: str
    schema_version: str
    packet_id: str
    bundle_id: str
    run_id: str
    artifact_count: int
    payload_artifact_count: int
    artifacts: tuple[dict[str, Any], ...]
    source_addresses: tuple[tuple[str, str], ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationPacket:
    packet_id: str
    bundle_id: str
    run_id: str
    artifacts: tuple[ReleaseAssuranceAttestationPacketArtifact, ...]
    manifest: ReleaseAssuranceAttestationPacketManifest
    accepted: bool
    content_address: str

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "bundle_id": self.bundle_id,
            "run_id": self.run_id,
            "artifacts": [item.to_dict(include_content=include_content) for item in self.artifacts],
            "manifest": self.manifest.to_dict(),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationPacketVerification:
    directory: str
    state: ReleaseAssuranceAttestationRuntimeState
    packet_id: str
    bundle_id: str
    run_id: str
    checked_artifact_count: int
    missing_paths: tuple[str, ...]
    unexpected_paths: tuple[str, ...]
    duplicate_paths: tuple[str, ...]
    unsafe_paths: tuple[str, ...]
    tampered_paths: tuple[str, ...]
    boundary_violations: tuple[str, ...]
    manifest_drift: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationOffline:
    packet_id: str
    attestation: ReleaseAssuranceAttestation
    manifest: dict[str, Any]
    verification: ReleaseAssuranceAttestationPacketVerification
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationQueryResult:
    attestation_id: str
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


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationDiff:
    left_attestation_id: str
    right_attestation_id: str
    left_address: str
    right_address: str
    added_component_ids: tuple[str, ...]
    removed_component_ids: tuple[str, ...]
    changed_component_ids: tuple[str, ...]
    unchanged_component_ids: tuple[str, ...]
    added_check_ids: tuple[str, ...]
    removed_check_ids: tuple[str, ...]
    changed_check_ids: tuple[str, ...]
    unchanged_check_ids: tuple[str, ...]
    changed_policy_fields: tuple[str, ...]
    identical: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationMetric:
    metric_id: str
    component_id: str
    name: str
    value: int | float
    unit: str
    source_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationObservability:
    attestation_id: str
    metrics: tuple[ReleaseAssuranceAttestationMetric, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"metric_count": len(self.metrics)}


__all__ = [
    name
    for name in globals()
    if name.startswith("RELEASE_ASSURANCE_ATTESTATION")
    or name.startswith("ReleaseAssuranceAttestation")
]
