"""Contracts for a longitudinal public release-attestation registry.

The registry retains only public attestation summaries and content addresses.
It is an append-only sequence: every entry points to the previous entry, and
the registry address covers the complete ordered sequence.  The contracts in
this module are deliberately independent from storage and transport so the
same registry can be inspected in memory, served by the API, or verified from
an offline packet.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

RELEASE_ASSURANCE_ATTESTATION_REGISTRY_VERSION = "release-assurance-attestation-registry-v1"
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_SCHEMA_VERSION = (
    "release-assurance-attestation-registry-schema-v1"
)
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_QUERY_VERSION = (
    "release-assurance-attestation-registry-query-v1"
)
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_DIFF_VERSION = (
    "release-assurance-attestation-registry-diff-v1"
)
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_PACKET_VERSION = (
    "release-assurance-attestation-registry-packet-v1"
)
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_BOUNDARY = "public_longitudinal_release_registry"
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_DEFAULT_LIMIT = 50
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_MAX_LIMIT = 500
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_MAX_ENTRIES = 256
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_PACKET_PAYLOAD_COUNT = 6
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_PACKET_ARTIFACT_COUNT = 7
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_RESOURCE_NAMES = ("entries", "transitions")


def _text(value: Any, field: str, *, maximum: int = 240) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    result = str(value).strip()
    if not result:
        raise ValidationError(f"{field} must not be empty")
    if len(result) > maximum:
        raise ValidationError(f"{field} exceeds the maximum length")
    return result


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


def _percent(value: Any, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"{field} must be numeric") from exc
    if result < 0 or result > 100:
        raise ValidationError(f"{field} must be between 0 and 100")
    return result


def _strings(value: Any, field: str, *, maximum: int = 256) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise ValidationError(f"{field} must be an array")
    result = tuple(_text(item, f"{field}[{index}]") for index, item in enumerate(value))
    if len(result) > maximum or len(result) != len(set(result)):
        raise ValidationError(f"{field} must be bounded and unique")
    return result


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(dict(body), prefix=prefix)


class ReleaseAssuranceAttestationRegistryTransitionState(StrEnum):
    INITIAL = "initial"
    ADVANCE = "advance"
    REPEAT = "repeat"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationRegistryEntry:
    """One immutable public attestation summary in sequence order."""

    ordinal: int
    entry_id: str
    attestation_id: str
    bundle_id: str
    run_id: str
    attestation_address: str
    previous_entry_address: str
    transition: ReleaseAssuranceAttestationRegistryTransitionState
    accepted: bool
    component_count: int
    check_count: int
    passed_check_count: int
    overall_percent: float
    content_address: str

    def _body(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "entry_id": self.entry_id,
            "attestation_id": self.attestation_id,
            "bundle_id": self.bundle_id,
            "run_id": self.run_id,
            "attestation_address": self.attestation_address,
            "previous_entry_address": self.previous_entry_address,
            "transition": self.transition,
            "accepted": self.accepted,
            "component_count": self.component_count,
            "check_count": self.check_count,
            "passed_check_count": self.passed_check_count,
            "overall_percent": self.overall_percent,
        }

    def __post_init__(self) -> None:
        _int(
            self.ordinal,
            "registry_entry.ordinal",
            minimum=1,
            maximum=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_MAX_ENTRIES,
        )
        _text(self.entry_id, "registry_entry.entry_id", maximum=160)
        _text(self.attestation_id, "registry_entry.attestation_id", maximum=160)
        _text(self.bundle_id, "registry_entry.bundle_id", maximum=180)
        _text(self.run_id, "registry_entry.run_id", maximum=180)
        _text(self.attestation_address, "registry_entry.attestation_address")
        if self.ordinal == 1:
            if self.previous_entry_address != "root":
                raise ValidationError("first registry entry must point to root")
            if self.transition is not ReleaseAssuranceAttestationRegistryTransitionState.INITIAL:
                raise ValidationError("first registry entry must be initial")
        else:
            _text(self.previous_entry_address, "registry_entry.previous_entry_address")
            if self.transition is ReleaseAssuranceAttestationRegistryTransitionState.INITIAL:
                raise ValidationError("non-first registry entry cannot be initial")
        _bool(self.accepted, "registry_entry.accepted")
        _int(self.component_count, "registry_entry.component_count", minimum=1)
        _int(self.check_count, "registry_entry.check_count", minimum=1)
        _int(self.passed_check_count, "registry_entry.passed_check_count")
        if self.passed_check_count > self.check_count:
            raise ValidationError("registry entry passed checks exceed total checks")
        _percent(self.overall_percent, "registry_entry.overall_percent")
        _text(self.content_address, "registry_entry.content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ReleaseAssuranceAttestationRegistryEntry:
        body = _mapping(value, "registry entry")
        allowed = {
            "ordinal",
            "entry_id",
            "attestation_id",
            "bundle_id",
            "run_id",
            "attestation_address",
            "previous_entry_address",
            "transition",
            "accepted",
            "component_count",
            "check_count",
            "passed_check_count",
            "overall_percent",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"registry entry contains unsupported fields: {sorted(unknown)}")
        try:
            transition = ReleaseAssuranceAttestationRegistryTransitionState(body.get("transition"))
        except ValueError as exc:
            raise ValidationError("registry entry transition is invalid") from exc
        entry = cls(
            ordinal=_int(
                body.get("ordinal"),
                "registry_entry.ordinal",
                minimum=1,
                maximum=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_MAX_ENTRIES,
            ),
            entry_id=_text(body.get("entry_id"), "registry_entry.entry_id", maximum=160),
            attestation_id=_text(
                body.get("attestation_id"), "registry_entry.attestation_id", maximum=160
            ),
            bundle_id=_text(body.get("bundle_id"), "registry_entry.bundle_id", maximum=180),
            run_id=_text(body.get("run_id"), "registry_entry.run_id", maximum=180),
            attestation_address=_text(
                body.get("attestation_address"), "registry_entry.attestation_address"
            ),
            previous_entry_address=_text(
                body.get("previous_entry_address"), "registry_entry.previous_entry_address"
            ),
            transition=transition,
            accepted=_bool(body.get("accepted"), "registry_entry.accepted"),
            component_count=_int(
                body.get("component_count"), "registry_entry.component_count", minimum=1
            ),
            check_count=_int(body.get("check_count"), "registry_entry.check_count", minimum=1),
            passed_check_count=_int(
                body.get("passed_check_count"), "registry_entry.passed_check_count"
            ),
            overall_percent=_percent(body.get("overall_percent"), "registry_entry.overall_percent"),
            content_address=_text(body.get("content_address"), "registry_entry.content_address"),
        )
        if (
            _address(entry._body(), "release-assurance-attestation-registry-entry")
            != entry.content_address
        ):
            raise ValidationError("registry entry content address does not reconcile")
        return entry


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationRegistryTransition:
    """Address-only change classification between adjacent entries."""

    ordinal: int
    transition_id: str
    from_entry_address: str
    to_entry_address: str
    from_attestation_address: str
    to_attestation_address: str
    state: ReleaseAssuranceAttestationRegistryTransitionState
    changed_summary_fields: tuple[str, ...]
    accepted: bool
    content_address: str

    def _body(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "transition_id": self.transition_id,
            "from_entry_address": self.from_entry_address,
            "to_entry_address": self.to_entry_address,
            "from_attestation_address": self.from_attestation_address,
            "to_attestation_address": self.to_attestation_address,
            "state": self.state,
            "changed_summary_fields": self.changed_summary_fields,
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        _int(
            self.ordinal,
            "registry_transition.ordinal",
            minimum=1,
            maximum=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_MAX_ENTRIES,
        )
        _text(self.transition_id, "registry_transition.transition_id", maximum=180)
        _text(self.from_entry_address, "registry_transition.from_entry_address")
        _text(self.to_entry_address, "registry_transition.to_entry_address")
        _text(self.from_attestation_address, "registry_transition.from_attestation_address")
        _text(self.to_attestation_address, "registry_transition.to_attestation_address")
        _strings(self.changed_summary_fields, "registry_transition.changed_summary_fields")
        _bool(self.accepted, "registry_transition.accepted")
        _text(self.content_address, "registry_transition.content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(
        cls, value: Mapping[str, Any]
    ) -> ReleaseAssuranceAttestationRegistryTransition:
        body = _mapping(value, "registry transition")
        allowed = {
            "ordinal",
            "transition_id",
            "from_entry_address",
            "to_entry_address",
            "from_attestation_address",
            "to_attestation_address",
            "state",
            "changed_summary_fields",
            "accepted",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(
                f"registry transition contains unsupported fields: {sorted(unknown)}"
            )
        try:
            state = ReleaseAssuranceAttestationRegistryTransitionState(body.get("state"))
        except ValueError as exc:
            raise ValidationError("registry transition state is invalid") from exc
        transition = cls(
            ordinal=_int(
                body.get("ordinal"),
                "registry_transition.ordinal",
                minimum=1,
                maximum=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_MAX_ENTRIES,
            ),
            transition_id=_text(
                body.get("transition_id"), "registry_transition.transition_id", maximum=180
            ),
            from_entry_address=_text(
                body.get("from_entry_address"), "registry_transition.from_entry_address"
            ),
            to_entry_address=_text(
                body.get("to_entry_address"), "registry_transition.to_entry_address"
            ),
            from_attestation_address=_text(
                body.get("from_attestation_address"), "registry_transition.from_attestation_address"
            ),
            to_attestation_address=_text(
                body.get("to_attestation_address"), "registry_transition.to_attestation_address"
            ),
            state=state,
            changed_summary_fields=_strings(
                body.get("changed_summary_fields"), "registry_transition.changed_summary_fields"
            ),
            accepted=_bool(body.get("accepted"), "registry_transition.accepted"),
            content_address=_text(
                body.get("content_address"), "registry_transition.content_address"
            ),
        )
        if (
            _address(transition._body(), "release-assurance-attestation-registry-transition")
            != transition.content_address
        ):
            raise ValidationError("registry transition content address does not reconcile")
        return transition


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationRegistry:
    """Addressed append-only history of public attestations."""

    registry_version: str
    schema_version: str
    registry_id: str
    entries: tuple[ReleaseAssuranceAttestationRegistryEntry, ...]
    transitions: tuple[ReleaseAssuranceAttestationRegistryTransition, ...]
    head_address: str
    accepted: bool
    content_address: str

    @property
    def boundary(self) -> str:
        return RELEASE_ASSURANCE_ATTESTATION_REGISTRY_BOUNDARY

    @property
    def entry_count(self) -> int:
        return len(self.entries)

    @property
    def transition_count(self) -> int:
        return len(self.transitions)

    @property
    def accepted_entry_count(self) -> int:
        return sum(item.accepted for item in self.entries)

    @property
    def blocked_entry_count(self) -> int:
        return self.entry_count - self.accepted_entry_count

    @property
    def latest_entry(self) -> ReleaseAssuranceAttestationRegistryEntry:
        if not self.entries:
            raise ValidationError("registry has no entries")
        return self.entries[-1]

    @property
    def failed_entry_ids(self) -> tuple[str, ...]:
        return tuple(item.entry_id for item in self.entries if not item.accepted)

    def _body(self) -> dict[str, Any]:
        return {
            "registry_version": self.registry_version,
            "schema_version": self.schema_version,
            "registry_id": self.registry_id,
            "entries": tuple(item.to_dict() for item in self.entries),
            "transitions": tuple(item.to_dict() for item in self.transitions),
            "head_address": self.head_address,
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        if self.registry_version != RELEASE_ASSURANCE_ATTESTATION_REGISTRY_VERSION:
            raise ValidationError("registry version is invalid")
        if self.schema_version != RELEASE_ASSURANCE_ATTESTATION_REGISTRY_SCHEMA_VERSION:
            raise ValidationError("registry schema version is invalid")
        _text(self.registry_id, "registry.registry_id", maximum=180)
        if (
            not self.entries
            or len(self.entries) > RELEASE_ASSURANCE_ATTESTATION_REGISTRY_MAX_ENTRIES
        ):
            raise ValidationError("registry entry count is outside its contract")
        if len(self.transitions) != max(0, len(self.entries) - 1):
            raise ValidationError("registry transition count does not reconcile")
        _text(self.head_address, "registry.head_address")
        _bool(self.accepted, "registry.accepted")
        _text(self.content_address, "registry.content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            self._body()
            | {
                "boundary": self.boundary,
                "entry_count": self.entry_count,
                "transition_count": self.transition_count,
                "accepted_entry_count": self.accepted_entry_count,
                "blocked_entry_count": self.blocked_entry_count,
                "failed_entry_ids": self.failed_entry_ids,
                "content_address": self.content_address,
            }
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ReleaseAssuranceAttestationRegistry:
        body = _mapping(value, "attestation registry")
        allowed = {
            "registry_version",
            "schema_version",
            "registry_id",
            "entries",
            "transitions",
            "head_address",
            "accepted",
            "content_address",
            "boundary",
            "entry_count",
            "transition_count",
            "accepted_entry_count",
            "blocked_entry_count",
            "failed_entry_ids",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(
                f"attestation registry contains unsupported fields: {sorted(unknown)}"
            )
        raw_entries = body.get("entries")
        raw_transitions = body.get("transitions")
        if not isinstance(raw_entries, (list, tuple)) or not isinstance(
            raw_transitions, (list, tuple)
        ):
            raise ValidationError("registry entries and transitions must be arrays")
        entries = tuple(
            ReleaseAssuranceAttestationRegistryEntry.from_mapping(item) for item in raw_entries
        )
        transitions = tuple(
            ReleaseAssuranceAttestationRegistryTransition.from_mapping(item)
            for item in raw_transitions
        )
        registry = cls(
            registry_version=str(body.get("registry_version")),
            schema_version=str(body.get("schema_version")),
            registry_id=_text(body.get("registry_id"), "registry.registry_id", maximum=180),
            entries=entries,
            transitions=transitions,
            head_address=_text(body.get("head_address"), "registry.head_address"),
            accepted=_bool(body.get("accepted"), "registry.accepted"),
            content_address=_text(body.get("content_address"), "registry.content_address"),
        )
        if body.get("boundary") not in (None, RELEASE_ASSURANCE_ATTESTATION_REGISTRY_BOUNDARY):
            raise ValidationError("registry boundary is invalid")
        if body.get("entry_count") != registry.entry_count:
            raise ValidationError("registry entry count does not reconcile")
        if body.get("transition_count") != registry.transition_count:
            raise ValidationError("registry transition count does not reconcile")
        if body.get("accepted_entry_count") != registry.accepted_entry_count:
            raise ValidationError("registry accepted entry count does not reconcile")
        if body.get("blocked_entry_count") != registry.blocked_entry_count:
            raise ValidationError("registry blocked entry count does not reconcile")
        if tuple(body.get("failed_entry_ids", ())) != registry.failed_entry_ids:
            raise ValidationError("registry failed entry IDs do not reconcile")
        if (
            _address(registry._body(), "release-assurance-attestation-registry")
            != registry.content_address
        ):
            raise ValidationError("registry content address does not reconcile")
        return registry


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationRegistryQueryResult:
    registry_id: str
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
class ReleaseAssuranceAttestationRegistryDiff:
    left_registry_id: str
    right_registry_id: str
    left_address: str
    right_address: str
    added_entry_ids: tuple[str, ...]
    removed_entry_ids: tuple[str, ...]
    changed_entry_ids: tuple[str, ...]
    unchanged_entry_ids: tuple[str, ...]
    added_attestation_addresses: tuple[str, ...]
    removed_attestation_addresses: tuple[str, ...]
    changed_transition_ordinals: tuple[int, ...]
    identical: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationRegistryPacketArtifact:
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
class ReleaseAssuranceAttestationRegistryPacketManifest:
    version: str
    schema_version: str
    packet_id: str
    registry_id: str
    artifact_count: int
    payload_artifact_count: int
    artifacts: tuple[dict[str, Any], ...]
    source_addresses: tuple[tuple[str, str], ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationRegistryPacket:
    packet_id: str
    registry_id: str
    artifacts: tuple[ReleaseAssuranceAttestationRegistryPacketArtifact, ...]
    manifest: ReleaseAssuranceAttestationRegistryPacketManifest
    accepted: bool
    content_address: str

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "registry_id": self.registry_id,
            "artifacts": [item.to_dict(include_content=include_content) for item in self.artifacts],
            "manifest": self.manifest.to_dict(),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationRegistryPacketVerification:
    directory: str
    packet_id: str
    registry_id: str
    checked_artifact_count: int
    missing_paths: tuple[str, ...]
    unexpected_paths: tuple[str, ...]
    unsafe_paths: tuple[str, ...]
    tampered_paths: tuple[str, ...]
    manifest_drift: tuple[str, ...]
    boundary_violations: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationRegistryOffline:
    packet_id: str
    registry: ReleaseAssuranceAttestationRegistry
    manifest: dict[str, Any]
    verification: ReleaseAssuranceAttestationRegistryPacketVerification
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


__all__ = [
    name
    for name in globals()
    if name.startswith("RELEASE_ASSURANCE_ATTESTATION_REGISTRY")
    or name.startswith("ReleaseAssuranceAttestationRegistry")
]
