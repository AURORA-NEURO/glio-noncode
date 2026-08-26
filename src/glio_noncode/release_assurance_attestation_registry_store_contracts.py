"""Public contracts for the operational attestation-registry store.

The registry module describes an immutable sequence.  This module describes
the narrow operational envelope around that sequence: policy, append
decisions, bounded operation history, head state, and deterministic audits.
The store contracts contain only public identifiers, summaries, addresses, and
decision codes.  They deliberately do not contain source attestations or
execution payloads.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_VERSION = (
    "release-assurance-attestation-registry-store-v1"
)
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_SCHEMA_VERSION = (
    "release-assurance-attestation-registry-store-schema-v1"
)
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_OPERATION_VERSION = (
    "release-assurance-attestation-registry-store-operation-v1"
)
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_AUDIT_VERSION = (
    "release-assurance-attestation-registry-store-audit-v1"
)
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_REPLAY_VERSION = (
    "release-assurance-attestation-registry-store-replay-v1"
)
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_BOUNDARY = "public_longitudinal_release_registry_store"
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_DEFAULT_MAX_ENTRIES = 256
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_MAX_ENTRIES = 256
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_DEFAULT_MAX_OPERATIONS = 1024
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_MAX_OPERATIONS = 4096
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_MAX_BATCH_SIZE = 256
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_DEFAULT_LIMIT = 50
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_MAX_LIMIT = 500
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_OPERATION_KINDS = (
    "append",
    "append_batch",
    "inspect",
    "verify",
    "query",
    "replay",
    "diff",
)
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_DISPOSITIONS = (
    "appended",
    "idempotent",
    "rejected",
    "inspected",
    "verified",
    "queried",
    "replayed",
    "diffed",
)
RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_ANOMALY_CODES = (
    "none",
    "empty_registry",
    "unaccepted_attestation",
    "duplicate_attestation",
    "head_mismatch",
    "capacity_exceeded",
    "registry_mismatch",
    "policy_mismatch",
    "invalid_registry",
    "boundary_violation",
    "address_mismatch",
    "operation_limit",
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


class ReleaseAssuranceAttestationRegistryStoreOperationKind(StrEnum):
    APPEND = "append"
    APPEND_BATCH = "append_batch"
    INSPECT = "inspect"
    VERIFY = "verify"
    QUERY = "query"
    REPLAY = "replay"
    DIFF = "diff"


class ReleaseAssuranceAttestationRegistryStoreDisposition(StrEnum):
    APPENDED = "appended"
    IDEMPOTENT = "idempotent"
    REJECTED = "rejected"
    INSPECTED = "inspected"
    VERIFIED = "verified"
    QUERIED = "queried"
    REPLAYED = "replayed"
    DIFFED = "diffed"


class ReleaseAssuranceAttestationRegistryStoreState(StrEnum):
    ACCEPTED = "accepted"
    BLOCKED = "blocked"
    REJECTED = "rejected"


class ReleaseAssuranceAttestationRegistryStoreAnomalyCode(StrEnum):
    NONE = "none"
    EMPTY_REGISTRY = "empty_registry"
    UNACCEPTED_ATTESTATION = "unaccepted_attestation"
    DUPLICATE_ATTESTATION = "duplicate_attestation"
    HEAD_MISMATCH = "head_mismatch"
    CAPACITY_EXCEEDED = "capacity_exceeded"
    REGISTRY_MISMATCH = "registry_mismatch"
    POLICY_MISMATCH = "policy_mismatch"
    INVALID_REGISTRY = "invalid_registry"
    BOUNDARY_VIOLATION = "boundary_violation"
    ADDRESS_MISMATCH = "address_mismatch"
    OPERATION_LIMIT = "operation_limit"


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationRegistryStorePolicy:
    """Deterministic rules governing one store instance."""

    registry_id: str
    max_entries: int = RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_DEFAULT_MAX_ENTRIES
    max_operations: int = RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_DEFAULT_MAX_OPERATIONS
    require_accepted: bool = True
    reject_duplicates: bool = True
    allow_repeats: bool = True
    content_address: str = ""

    def _body(self) -> dict[str, Any]:
        return {
            "registry_id": self.registry_id,
            "max_entries": self.max_entries,
            "max_operations": self.max_operations,
            "require_accepted": self.require_accepted,
            "reject_duplicates": self.reject_duplicates,
            "allow_repeats": self.allow_repeats,
        }

    def __post_init__(self) -> None:
        _text(self.registry_id, "store_policy.registry_id", maximum=180)
        _int(
            self.max_entries,
            "store_policy.max_entries",
            minimum=1,
            maximum=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_MAX_ENTRIES,
        )
        _int(
            self.max_operations,
            "store_policy.max_operations",
            minimum=1,
            maximum=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_MAX_OPERATIONS,
        )
        _bool(self.require_accepted, "store_policy.require_accepted")
        _bool(self.reject_duplicates, "store_policy.reject_duplicates")
        _bool(self.allow_repeats, "store_policy.allow_repeats")
        expected = _address(self._body(), "release-assurance-attestation-registry-store-policy")
        if self.content_address and self.content_address != expected:
            raise ValidationError("store policy content address does not reconcile")
        object.__setattr__(self, "content_address", expected)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(
        cls, value: Mapping[str, Any]
    ) -> ReleaseAssuranceAttestationRegistryStorePolicy:
        body = _mapping(value, "store policy")
        allowed = {
            "registry_id",
            "max_entries",
            "max_operations",
            "require_accepted",
            "reject_duplicates",
            "allow_repeats",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"store policy contains unsupported fields: {sorted(unknown)}")
        return cls(
            registry_id=_text(body.get("registry_id"), "store_policy.registry_id", maximum=180),
            max_entries=_int(
                body.get("max_entries"),
                "store_policy.max_entries",
                minimum=1,
                maximum=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_MAX_ENTRIES,
            ),
            max_operations=_int(
                body.get("max_operations"),
                "store_policy.max_operations",
                minimum=1,
                maximum=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_MAX_OPERATIONS,
            ),
            require_accepted=_bool(body.get("require_accepted"), "store_policy.require_accepted"),
            reject_duplicates=_bool(
                body.get("reject_duplicates"), "store_policy.reject_duplicates"
            ),
            allow_repeats=_bool(body.get("allow_repeats"), "store_policy.allow_repeats"),
            content_address=_text(body.get("content_address"), "store_policy.content_address"),
        )


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationRegistryStoreHead:
    """The public cursor required for safe append operations."""

    registry_id: str
    entry_count: int
    accepted_entry_count: int
    head_entry_id: str
    head_entry_address: str
    head_attestation_address: str
    accepted: bool
    content_address: str = ""

    def _body(self) -> dict[str, Any]:
        return {
            "registry_id": self.registry_id,
            "entry_count": self.entry_count,
            "accepted_entry_count": self.accepted_entry_count,
            "head_entry_id": self.head_entry_id,
            "head_entry_address": self.head_entry_address,
            "head_attestation_address": self.head_attestation_address,
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        _text(self.registry_id, "store_head.registry_id", maximum=180)
        _int(
            self.entry_count,
            "store_head.entry_count",
            minimum=1,
            maximum=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_MAX_ENTRIES,
        )
        _int(self.accepted_entry_count, "store_head.accepted_entry_count", minimum=0)
        if self.accepted_entry_count > self.entry_count:
            raise ValidationError("store head accepted entries exceed total entries")
        _text(self.head_entry_id, "store_head.head_entry_id", maximum=180)
        _text(self.head_entry_address, "store_head.head_entry_address")
        _text(self.head_attestation_address, "store_head.head_attestation_address")
        _bool(self.accepted, "store_head.accepted")
        expected = _address(self._body(), "release-assurance-attestation-registry-store-head")
        if self.content_address and self.content_address != expected:
            raise ValidationError("store head content address does not reconcile")
        object.__setattr__(self, "content_address", expected)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ReleaseAssuranceAttestationRegistryStoreHead:
        body = _mapping(value, "store head")
        allowed = {
            "registry_id",
            "entry_count",
            "accepted_entry_count",
            "head_entry_id",
            "head_entry_address",
            "head_attestation_address",
            "accepted",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"store head contains unsupported fields: {sorted(unknown)}")
        return cls(
            registry_id=_text(body.get("registry_id"), "store_head.registry_id", maximum=180),
            entry_count=_int(
                body.get("entry_count"),
                "store_head.entry_count",
                minimum=1,
                maximum=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_MAX_ENTRIES,
            ),
            accepted_entry_count=_int(
                body.get("accepted_entry_count"), "store_head.accepted_entry_count", minimum=0
            ),
            head_entry_id=_text(body.get("head_entry_id"), "store_head.head_entry_id", maximum=180),
            head_entry_address=_text(
                body.get("head_entry_address"), "store_head.head_entry_address"
            ),
            head_attestation_address=_text(
                body.get("head_attestation_address"), "store_head.head_attestation_address"
            ),
            accepted=_bool(body.get("accepted"), "store_head.accepted"),
            content_address=_text(body.get("content_address"), "store_head.content_address"),
        )


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationRegistryStoreAuditCheck:
    """One deterministic store audit result."""

    check_id: str
    passed: bool
    observed: Any
    expected: Any
    detail: str
    content_address: str = ""

    def _body(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "passed": self.passed,
            "observed": self.observed,
            "expected": self.expected,
            "detail": self.detail,
        }

    def __post_init__(self) -> None:
        _text(self.check_id, "store_audit_check.check_id", maximum=180)
        _bool(self.passed, "store_audit_check.passed")
        _text(self.detail, "store_audit_check.detail", maximum=500)
        expected = _address(
            self._body(), "release-assurance-attestation-registry-store-audit-check"
        )
        if self.content_address and self.content_address != expected:
            raise ValidationError("store audit check content address does not reconcile")
        object.__setattr__(self, "content_address", expected)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(
        cls, value: Mapping[str, Any]
    ) -> ReleaseAssuranceAttestationRegistryStoreAuditCheck:
        body = _mapping(value, "store audit check")
        allowed = {"check_id", "passed", "observed", "expected", "detail", "content_address"}
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(
                f"store audit check contains unsupported fields: {sorted(unknown)}"
            )
        return cls(
            check_id=_text(body.get("check_id"), "store_audit_check.check_id", maximum=180),
            passed=_bool(body.get("passed"), "store_audit_check.passed"),
            observed=body.get("observed"),
            expected=body.get("expected"),
            detail=_text(body.get("detail"), "store_audit_check.detail", maximum=500),
            content_address=_text(body.get("content_address"), "store_audit_check.content_address"),
        )


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationRegistryStoreOperation:
    """A timestamp-free public decision in the bounded operation ledger."""

    ordinal: int
    operation_id: str
    kind: ReleaseAssuranceAttestationRegistryStoreOperationKind
    disposition: ReleaseAssuranceAttestationRegistryStoreDisposition
    state: ReleaseAssuranceAttestationRegistryStoreState
    anomaly_code: ReleaseAssuranceAttestationRegistryStoreAnomalyCode
    attestation_id: str | None
    attestation_address: str | None
    before_address: str | None
    after_address: str | None
    entry_id: str | None
    changed_summary_fields: tuple[str, ...]
    audit_check_ids: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def _body(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "operation_id": self.operation_id,
            "kind": self.kind,
            "disposition": self.disposition,
            "state": self.state,
            "anomaly_code": self.anomaly_code,
            "attestation_id": self.attestation_id,
            "attestation_address": self.attestation_address,
            "before_address": self.before_address,
            "after_address": self.after_address,
            "entry_id": self.entry_id,
            "changed_summary_fields": self.changed_summary_fields,
            "audit_check_ids": self.audit_check_ids,
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        _int(
            self.ordinal,
            "store_operation.ordinal",
            minimum=1,
            maximum=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_MAX_OPERATIONS,
        )
        _text(self.operation_id, "store_operation.operation_id", maximum=220)
        if not isinstance(self.kind, ReleaseAssuranceAttestationRegistryStoreOperationKind):
            raise ValidationError("store operation kind is invalid")
        if not isinstance(self.disposition, ReleaseAssuranceAttestationRegistryStoreDisposition):
            raise ValidationError("store operation disposition is invalid")
        if not isinstance(self.state, ReleaseAssuranceAttestationRegistryStoreState):
            raise ValidationError("store operation state is invalid")
        if not isinstance(self.anomaly_code, ReleaseAssuranceAttestationRegistryStoreAnomalyCode):
            raise ValidationError("store operation anomaly code is invalid")
        _optional_text(self.attestation_id, "store_operation.attestation_id", maximum=180)
        _optional_text(self.attestation_address, "store_operation.attestation_address")
        _optional_text(self.before_address, "store_operation.before_address")
        _optional_text(self.after_address, "store_operation.after_address")
        _optional_text(self.entry_id, "store_operation.entry_id", maximum=180)
        _strings(self.changed_summary_fields, "store_operation.changed_summary_fields")
        _strings(self.audit_check_ids, "store_operation.audit_check_ids")
        _bool(self.accepted, "store_operation.accepted")
        expected = _address(self._body(), "release-assurance-attestation-registry-store-operation")
        if self.content_address and self.content_address != expected:
            raise ValidationError("store operation content address does not reconcile")
        object.__setattr__(self, "content_address", expected)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(
        cls, value: Mapping[str, Any]
    ) -> ReleaseAssuranceAttestationRegistryStoreOperation:
        body = _mapping(value, "store operation")
        allowed = {
            "ordinal",
            "operation_id",
            "kind",
            "disposition",
            "state",
            "anomaly_code",
            "attestation_id",
            "attestation_address",
            "before_address",
            "after_address",
            "entry_id",
            "changed_summary_fields",
            "audit_check_ids",
            "accepted",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"store operation contains unsupported fields: {sorted(unknown)}")
        try:
            kind = ReleaseAssuranceAttestationRegistryStoreOperationKind(body.get("kind"))
            disposition = ReleaseAssuranceAttestationRegistryStoreDisposition(
                body.get("disposition")
            )
            state = ReleaseAssuranceAttestationRegistryStoreState(body.get("state"))
            anomaly = ReleaseAssuranceAttestationRegistryStoreAnomalyCode(body.get("anomaly_code"))
        except ValueError as exc:
            raise ValidationError("store operation enum value is invalid") from exc
        return cls(
            ordinal=_int(
                body.get("ordinal"),
                "store_operation.ordinal",
                minimum=1,
                maximum=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_MAX_OPERATIONS,
            ),
            operation_id=_text(
                body.get("operation_id"), "store_operation.operation_id", maximum=220
            ),
            kind=kind,
            disposition=disposition,
            state=state,
            anomaly_code=anomaly,
            attestation_id=_optional_text(
                body.get("attestation_id"), "store_operation.attestation_id", maximum=180
            ),
            attestation_address=_optional_text(
                body.get("attestation_address"), "store_operation.attestation_address"
            ),
            before_address=_optional_text(
                body.get("before_address"), "store_operation.before_address"
            ),
            after_address=_optional_text(
                body.get("after_address"), "store_operation.after_address"
            ),
            entry_id=_optional_text(body.get("entry_id"), "store_operation.entry_id", maximum=180),
            changed_summary_fields=_strings(
                body.get("changed_summary_fields"), "store_operation.changed_summary_fields"
            ),
            audit_check_ids=_strings(
                body.get("audit_check_ids"), "store_operation.audit_check_ids"
            ),
            accepted=_bool(body.get("accepted"), "store_operation.accepted"),
            content_address=_text(body.get("content_address"), "store_operation.content_address"),
        )


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationRegistryStore:
    """Addressed registry plus public policy and operation ledger."""

    store_version: str
    schema_version: str
    store_id: str
    registry: Any
    policy: ReleaseAssuranceAttestationRegistryStorePolicy
    head: ReleaseAssuranceAttestationRegistryStoreHead
    operations: tuple[ReleaseAssuranceAttestationRegistryStoreOperation, ...]
    accepted: bool
    content_address: str

    @property
    def boundary(self) -> str:
        return RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_BOUNDARY

    @property
    def operation_count(self) -> int:
        return len(self.operations)

    @property
    def append_count(self) -> int:
        return sum(
            item.disposition is ReleaseAssuranceAttestationRegistryStoreDisposition.APPENDED
            for item in self.operations
        )

    @property
    def rejection_count(self) -> int:
        return sum(
            item.disposition is ReleaseAssuranceAttestationRegistryStoreDisposition.REJECTED
            for item in self.operations
        )

    @property
    def idempotent_count(self) -> int:
        return sum(
            item.disposition is ReleaseAssuranceAttestationRegistryStoreDisposition.IDEMPOTENT
            for item in self.operations
        )

    @property
    def head_address(self) -> str:
        return self.head.head_entry_address

    def _body(self) -> dict[str, Any]:
        return {
            "store_version": self.store_version,
            "schema_version": self.schema_version,
            "store_id": self.store_id,
            "registry": self.registry.to_dict(),
            "policy": self.policy.to_dict(),
            "head": self.head.to_dict(),
            "operations": tuple(item.to_dict() for item in self.operations),
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        if self.store_version != RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_VERSION:
            raise ValidationError("store version is invalid")
        if self.schema_version != RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_SCHEMA_VERSION:
            raise ValidationError("store schema version is invalid")
        _text(self.store_id, "store.store_id", maximum=180)
        if self.policy.registry_id != self.registry.registry_id:
            raise ValidationError("store policy and registry IDs do not reconcile")
        if self.head.registry_id != self.registry.registry_id:
            raise ValidationError("store head and registry IDs do not reconcile")
        if len(self.operations) > self.policy.max_operations:
            raise ValidationError("store operation count exceeds policy")
        _bool(self.accepted, "store.accepted")
        expected = _address(self._body(), "release-assurance-attestation-registry-store")
        if expected != self.content_address:
            raise ValidationError("store content address does not reconcile")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            self._body()
            | {
                "boundary": self.boundary,
                "operation_count": self.operation_count,
                "append_count": self.append_count,
                "rejection_count": self.rejection_count,
                "idempotent_count": self.idempotent_count,
                "head_address": self.head_address,
                "content_address": self.content_address,
            }
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ReleaseAssuranceAttestationRegistryStore:
        from .release_assurance_attestation_registry_contracts import (
            ReleaseAssuranceAttestationRegistry,
        )

        body = _mapping(value, "attestation registry store")
        allowed = {
            "store_version",
            "schema_version",
            "store_id",
            "registry",
            "policy",
            "head",
            "operations",
            "accepted",
            "content_address",
            "boundary",
            "operation_count",
            "append_count",
            "rejection_count",
            "idempotent_count",
            "head_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(
                f"attestation registry store contains unsupported fields: {sorted(unknown)}"
            )
        raw_operations = body.get("operations")
        if not isinstance(raw_operations, (list, tuple)):
            raise ValidationError("store operations must be an array")
        store = cls(
            store_version=_text(body.get("store_version"), "store.store_version"),
            schema_version=_text(body.get("schema_version"), "store.schema_version"),
            store_id=_text(body.get("store_id"), "store.store_id", maximum=180),
            registry=ReleaseAssuranceAttestationRegistry.from_mapping(
                _mapping(body.get("registry"), "store.registry")
            ),
            policy=ReleaseAssuranceAttestationRegistryStorePolicy.from_mapping(
                _mapping(body.get("policy"), "store.policy")
            ),
            head=ReleaseAssuranceAttestationRegistryStoreHead.from_mapping(
                _mapping(body.get("head"), "store.head")
            ),
            operations=tuple(
                ReleaseAssuranceAttestationRegistryStoreOperation.from_mapping(item)
                for item in raw_operations
            ),
            accepted=_bool(body.get("accepted"), "store.accepted"),
            content_address=_text(body.get("content_address"), "store.content_address"),
        )
        if body.get("boundary") not in (
            None,
            RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_BOUNDARY,
        ):
            raise ValidationError("store boundary is invalid")
        if body.get("operation_count") != store.operation_count:
            raise ValidationError("store operation count does not reconcile")
        if body.get("append_count") != store.append_count:
            raise ValidationError("store append count does not reconcile")
        if body.get("rejection_count") != store.rejection_count:
            raise ValidationError("store rejection count does not reconcile")
        if body.get("idempotent_count") != store.idempotent_count:
            raise ValidationError("store idempotent count does not reconcile")
        if body.get("head_address") != store.head_address:
            raise ValidationError("store head address does not reconcile")
        return store


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationRegistryStoreAudit:
    store_id: str
    registry_id: str
    checks: tuple[ReleaseAssuranceAttestationRegistryStoreAuditCheck, ...]
    accepted: bool
    content_address: str = ""

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
            "audit_version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_AUDIT_VERSION,
            "store_id": self.store_id,
            "registry_id": self.registry_id,
            "checks": tuple(item.to_dict() for item in self.checks),
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        _text(self.store_id, "store_audit.store_id", maximum=180)
        _text(self.registry_id, "store_audit.registry_id", maximum=180)
        if not self.checks:
            raise ValidationError("store audit requires checks")
        _bool(self.accepted, "store_audit.accepted")
        expected = _address(self._body(), "release-assurance-attestation-registry-store-audit")
        if self.content_address and self.content_address != expected:
            raise ValidationError("store audit content address does not reconcile")
        object.__setattr__(self, "content_address", expected)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            self._body()
            | {
                "check_count": self.check_count,
                "passed_check_count": self.passed_check_count,
                "failed_check_ids": self.failed_check_ids,
                "content_address": self.content_address,
            }
        )


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationRegistryStoreAppendResult:
    store: ReleaseAssuranceAttestationRegistryStore
    operation: ReleaseAssuranceAttestationRegistryStoreOperation
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        _bool(self.accepted, "store_append_result.accepted")
        body = {
            "store": self.store.to_dict(),
            "operation": self.operation.to_dict(),
            "accepted": self.accepted,
        }
        expected = _address(body, "release-assurance-attestation-registry-store-append-result")
        if self.content_address and self.content_address != expected:
            raise ValidationError("store append result content address does not reconcile")
        object.__setattr__(self, "content_address", expected)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            {
                "store": self.store.to_dict(),
                "operation": self.operation.to_dict(),
                "accepted": self.accepted,
                "content_address": self.content_address,
            }
        )


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationRegistryStoreBatchResult:
    store: ReleaseAssuranceAttestationRegistryStore
    operations: tuple[ReleaseAssuranceAttestationRegistryStoreOperation, ...]
    appended_count: int
    rejected_count: int
    idempotent_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        _int(self.appended_count, "store_batch_result.appended_count", minimum=0)
        _int(self.rejected_count, "store_batch_result.rejected_count", minimum=0)
        _int(self.idempotent_count, "store_batch_result.idempotent_count", minimum=0)
        if self.appended_count + self.rejected_count + self.idempotent_count != len(
            self.operations
        ):
            raise ValidationError("store batch result counts do not reconcile")
        _bool(self.accepted, "store_batch_result.accepted")
        body = {
            "store": self.store.to_dict(),
            "operations": tuple(item.to_dict() for item in self.operations),
            "appended_count": self.appended_count,
            "rejected_count": self.rejected_count,
            "idempotent_count": self.idempotent_count,
            "accepted": self.accepted,
        }
        expected = _address(body, "release-assurance-attestation-registry-store-batch-result")
        if self.content_address and self.content_address != expected:
            raise ValidationError("store batch result content address does not reconcile")
        object.__setattr__(self, "content_address", expected)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            {
                "store": self.store.to_dict(),
                "operations": tuple(item.to_dict() for item in self.operations),
                "appended_count": self.appended_count,
                "rejected_count": self.rejected_count,
                "idempotent_count": self.idempotent_count,
                "accepted": self.accepted,
                "content_address": self.content_address,
            }
        )


@dataclass(frozen=True, slots=True)
class ReleaseAssuranceAttestationRegistryStoreReplay:
    store_id: str
    original_address: str
    replayed_address: str
    operation_count: int
    deterministic: bool
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        _text(self.store_id, "store_replay.store_id", maximum=180)
        _text(self.original_address, "store_replay.original_address")
        _text(self.replayed_address, "store_replay.replayed_address")
        _int(
            self.operation_count,
            "store_replay.operation_count",
            minimum=0,
            maximum=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_MAX_OPERATIONS,
        )
        _bool(self.deterministic, "store_replay.deterministic")
        _bool(self.accepted, "store_replay.accepted")
        body = {
            "replay_version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_REPLAY_VERSION,
            "store_id": self.store_id,
            "original_address": self.original_address,
            "replayed_address": self.replayed_address,
            "operation_count": self.operation_count,
            "deterministic": self.deterministic,
            "accepted": self.accepted,
        }
        expected = _address(body, "release-assurance-attestation-registry-store-replay")
        if self.content_address and self.content_address != expected:
            raise ValidationError("store replay content address does not reconcile")
        object.__setattr__(self, "content_address", expected)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            {
                "replay_version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_REPLAY_VERSION,
                "store_id": self.store_id,
                "original_address": self.original_address,
                "replayed_address": self.replayed_address,
                "operation_count": self.operation_count,
                "deterministic": self.deterministic,
                "accepted": self.accepted,
                "content_address": self.content_address,
            }
        )


__all__ = [
    name
    for name in globals()
    if name.startswith("RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE")
    or name.startswith("ReleaseAssuranceAttestationRegistryStore")
]
