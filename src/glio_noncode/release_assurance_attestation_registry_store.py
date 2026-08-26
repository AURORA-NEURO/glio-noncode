"""Operate a bounded, public, append-only attestation-registry store.

The registry itself is a pure addressed sequence.  This module supplies the
operational controls needed to maintain that sequence without introducing a
database-specific framework: policy checks, optimistic head checks,
idempotent retry behavior, duplicate and capacity rejection, batch append,
operation history, replay, audit, query, diff, and deterministic exports.

All functions are pure with respect to their inputs.  An append returns a new
store value and a public decision; callers decide where to persist the value.
The store therefore works equally well in a service process, an offline
packet workflow, or a CI release gate.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from io import StringIO
from typing import Any

from .errors import ValidationError
from .release_assurance_attestation_contracts import ReleaseAssuranceAttestation
from .release_assurance_attestation_registry import (
    _entry,
    build_release_assurance_attestation_registry,
    diff_release_assurance_attestation_registries,
)
from .release_assurance_attestation_registry_contracts import (
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_MAX_ENTRIES,
    ReleaseAssuranceAttestationRegistry,
    ReleaseAssuranceAttestationRegistryEntry,
    ReleaseAssuranceAttestationRegistryTransition,
    ReleaseAssuranceAttestationRegistryTransitionState,
)
from .release_assurance_attestation_registry_store_contracts import (
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_BOUNDARY,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_DEFAULT_LIMIT,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_DEFAULT_MAX_ENTRIES,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_DEFAULT_MAX_OPERATIONS,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_MAX_BATCH_SIZE,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_MAX_ENTRIES,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_MAX_LIMIT,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_MAX_OPERATIONS,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_SCHEMA_VERSION,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_VERSION,
    ReleaseAssuranceAttestationRegistryStore,
    ReleaseAssuranceAttestationRegistryStoreAnomalyCode,
    ReleaseAssuranceAttestationRegistryStoreAppendResult,
    ReleaseAssuranceAttestationRegistryStoreAudit,
    ReleaseAssuranceAttestationRegistryStoreAuditCheck,
    ReleaseAssuranceAttestationRegistryStoreBatchResult,
    ReleaseAssuranceAttestationRegistryStoreDisposition,
    ReleaseAssuranceAttestationRegistryStoreHead,
    ReleaseAssuranceAttestationRegistryStoreOperation,
    ReleaseAssuranceAttestationRegistryStoreOperationKind,
    ReleaseAssuranceAttestationRegistryStorePolicy,
    ReleaseAssuranceAttestationRegistryStoreReplay,
    ReleaseAssuranceAttestationRegistryStoreState,
)
from .release_assurance_support import forbidden_keys, text_matches
from .serialization import canonical_json, content_hash


def _as_attestation(
    value: ReleaseAssuranceAttestation | Mapping[str, Any],
) -> ReleaseAssuranceAttestation:
    return (
        value
        if isinstance(value, ReleaseAssuranceAttestation)
        else ReleaseAssuranceAttestation.from_mapping(value)
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


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _changed_entry_fields(
    before: ReleaseAssuranceAttestationRegistryEntry,
    after: ReleaseAssuranceAttestation,
) -> tuple[str, ...]:
    fields = (
        "bundle_id",
        "run_id",
        "overall_percent",
        "accepted",
        "component_count",
        "check_count",
        "passed_check_count",
    )
    return tuple(field for field in fields if getattr(before, field) != getattr(after, field))


def _transition_state_for_append(
    before: ReleaseAssuranceAttestationRegistryEntry,
    after: ReleaseAssuranceAttestation,
) -> ReleaseAssuranceAttestationRegistryTransitionState:
    if not after.accepted:
        return ReleaseAssuranceAttestationRegistryTransitionState.BLOCKED
    if before.attestation_address == after.content_address:
        return ReleaseAssuranceAttestationRegistryTransitionState.REPEAT
    return ReleaseAssuranceAttestationRegistryTransitionState.ADVANCE


def _transition_for_append(
    before: ReleaseAssuranceAttestationRegistryEntry,
    after: ReleaseAssuranceAttestationRegistryEntry,
    attestation: ReleaseAssuranceAttestation,
) -> ReleaseAssuranceAttestationRegistryTransition:
    state = _transition_state_for_append(before, attestation)
    body = {
        "ordinal": before.ordinal,
        "transition_id": (
            f"transition:{before.ordinal:04d}:{before.attestation_id}:{after.attestation_id}"
        ),
        "from_entry_address": before.content_address,
        "to_entry_address": after.content_address,
        "from_attestation_address": before.attestation_address,
        "to_attestation_address": after.attestation_address,
        "state": state,
        "changed_summary_fields": _changed_entry_fields(before, attestation),
        "accepted": before.accepted and after.accepted,
    }
    return ReleaseAssuranceAttestationRegistryTransition(
        **body,
        content_address=content_hash(
            body,
            prefix="release-assurance-attestation-registry-transition",
        ),
    )


def _registry_with_append(
    registry: ReleaseAssuranceAttestationRegistry,
    attestation: ReleaseAssuranceAttestation,
) -> tuple[ReleaseAssuranceAttestationRegistry, ReleaseAssuranceAttestationRegistryEntry]:
    if registry.entry_count >= RELEASE_ASSURANCE_ATTESTATION_REGISTRY_MAX_ENTRIES:
        raise ValidationError("attestation registry exceeds the maximum entry count")
    before = registry.latest_entry
    current_state = _transition_state_for_append(before, attestation)
    current = _entry(
        registry.entry_count + 1,
        attestation,
        before.content_address,
        current_state,
    )
    transition = _transition_for_append(before, current, attestation)
    entries = registry.entries + (current,)
    transitions = registry.transitions + (transition,)
    body = {
        "registry_version": registry.registry_version,
        "schema_version": registry.schema_version,
        "registry_id": registry.registry_id,
        "entries": tuple(item.to_dict() for item in entries),
        "transitions": tuple(item.to_dict() for item in transitions),
        "head_address": current.content_address,
        "accepted": all(item.accepted for item in entries),
    }
    return (
        ReleaseAssuranceAttestationRegistry(
            registry_version=registry.registry_version,
            schema_version=registry.schema_version,
            registry_id=registry.registry_id,
            entries=entries,
            transitions=transitions,
            head_address=current.content_address,
            accepted=all(item.accepted for item in entries),
            content_address=content_hash(
                body,
                prefix="release-assurance-attestation-registry",
            ),
        ),
        current,
    )


def build_release_assurance_attestation_registry_store_policy(
    registry_id: str,
    *,
    max_entries: int = RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_DEFAULT_MAX_ENTRIES,
    max_operations: int = RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_DEFAULT_MAX_OPERATIONS,
    require_accepted: bool = True,
    reject_duplicates: bool = True,
    allow_repeats: bool = True,
) -> ReleaseAssuranceAttestationRegistryStorePolicy:
    """Create a validated policy for one registry identity."""

    return ReleaseAssuranceAttestationRegistryStorePolicy(
        registry_id=_text(registry_id, "registry_id", maximum=180),
        max_entries=_int(
            max_entries,
            "max_entries",
            minimum=1,
            maximum=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_MAX_ENTRIES,
        ),
        max_operations=_int(
            max_operations,
            "max_operations",
            minimum=1,
            maximum=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_MAX_OPERATIONS,
        ),
        require_accepted=_bool(require_accepted, "require_accepted"),
        reject_duplicates=_bool(reject_duplicates, "reject_duplicates"),
        allow_repeats=_bool(allow_repeats, "allow_repeats"),
    )


def _head(
    registry: ReleaseAssuranceAttestationRegistry,
) -> ReleaseAssuranceAttestationRegistryStoreHead:
    latest = registry.latest_entry
    return ReleaseAssuranceAttestationRegistryStoreHead(
        registry_id=registry.registry_id,
        entry_count=registry.entry_count,
        accepted_entry_count=registry.accepted_entry_count,
        head_entry_id=latest.entry_id,
        head_entry_address=latest.content_address,
        head_attestation_address=latest.attestation_address,
        accepted=registry.accepted,
    )


def _store(
    store: ReleaseAssuranceAttestationRegistryStore,
    *,
    registry: ReleaseAssuranceAttestationRegistry | None = None,
    operations: tuple[ReleaseAssuranceAttestationRegistryStoreOperation, ...] | None = None,
) -> ReleaseAssuranceAttestationRegistryStore:
    selected_registry = registry or store.registry
    selected_operations = operations if operations is not None else store.operations
    accepted = selected_registry.accepted
    body = {
        "store_version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_VERSION,
        "schema_version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_SCHEMA_VERSION,
        "store_id": store.store_id,
        "registry": selected_registry.to_dict(),
        "policy": store.policy.to_dict(),
        "head": _head(selected_registry).to_dict(),
        "operations": tuple(item.to_dict() for item in selected_operations),
        "accepted": accepted,
    }
    return ReleaseAssuranceAttestationRegistryStore(
        store_version=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_VERSION,
        schema_version=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_SCHEMA_VERSION,
        store_id=store.store_id,
        registry=selected_registry,
        policy=store.policy,
        head=_head(selected_registry),
        operations=selected_operations,
        accepted=accepted,
        content_address=content_hash(
            body,
            prefix="release-assurance-attestation-registry-store",
        ),
    )


def build_release_assurance_attestation_registry_store(
    registry: ReleaseAssuranceAttestationRegistry | Mapping[str, Any],
    *,
    store_id: str | None = None,
    policy: ReleaseAssuranceAttestationRegistryStorePolicy | Mapping[str, Any] | None = None,
    operations: Iterable[
        ReleaseAssuranceAttestationRegistryStoreOperation | Mapping[str, Any]
    ] = (),
) -> ReleaseAssuranceAttestationRegistryStore:
    """Create an addressed operational store around a validated registry."""

    selected_registry = (
        registry
        if isinstance(registry, ReleaseAssuranceAttestationRegistry)
        else ReleaseAssuranceAttestationRegistry.from_mapping(registry)
    )
    selected_policy = (
        build_release_assurance_attestation_registry_store_policy(selected_registry.registry_id)
        if policy is None
        else policy
        if isinstance(policy, ReleaseAssuranceAttestationRegistryStorePolicy)
        else ReleaseAssuranceAttestationRegistryStorePolicy.from_mapping(policy)
    )
    if selected_policy.registry_id != selected_registry.registry_id:
        raise ValidationError("store policy and registry IDs do not reconcile")
    if selected_policy.max_entries < selected_registry.entry_count:
        raise ValidationError("store policy max entries is below the registry count")
    selected_operations = tuple(
        item
        if isinstance(item, ReleaseAssuranceAttestationRegistryStoreOperation)
        else ReleaseAssuranceAttestationRegistryStoreOperation.from_mapping(item)
        for item in operations
    )
    if len(selected_operations) > selected_policy.max_operations:
        raise ValidationError("store operation count exceeds policy")
    identity = _text(store_id or f"{selected_registry.registry_id}-store", "store_id", maximum=180)
    body = {
        "store_version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_VERSION,
        "schema_version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_SCHEMA_VERSION,
        "store_id": identity,
        "registry": selected_registry.to_dict(),
        "policy": selected_policy.to_dict(),
        "head": _head(selected_registry).to_dict(),
        "operations": tuple(item.to_dict() for item in selected_operations),
        "accepted": selected_registry.accepted,
    }
    return ReleaseAssuranceAttestationRegistryStore(
        store_version=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_VERSION,
        schema_version=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_SCHEMA_VERSION,
        store_id=identity,
        registry=selected_registry,
        policy=selected_policy,
        head=_head(selected_registry),
        operations=selected_operations,
        accepted=selected_registry.accepted,
        content_address=content_hash(
            body,
            prefix="release-assurance-attestation-registry-store",
        ),
    )


def _operation(
    *,
    ordinal: int,
    kind: ReleaseAssuranceAttestationRegistryStoreOperationKind,
    disposition: ReleaseAssuranceAttestationRegistryStoreDisposition,
    state: ReleaseAssuranceAttestationRegistryStoreState,
    anomaly_code: ReleaseAssuranceAttestationRegistryStoreAnomalyCode,
    attestation: ReleaseAssuranceAttestation | None,
    before_address: str | None,
    after_address: str | None,
    entry_id: str | None,
    changed_summary_fields: tuple[str, ...] = (),
    audit_check_ids: tuple[str, ...] = (),
    accepted: bool,
) -> ReleaseAssuranceAttestationRegistryStoreOperation:
    attestation_id = attestation.attestation_id if attestation is not None else None
    attestation_address = attestation.content_address if attestation is not None else None
    operation_id = f"operation:{ordinal:06d}:{kind.value}:{attestation_id or 'store'}"
    return ReleaseAssuranceAttestationRegistryStoreOperation(
        ordinal=ordinal,
        operation_id=operation_id,
        kind=kind,
        disposition=disposition,
        state=state,
        anomaly_code=anomaly_code,
        attestation_id=attestation_id,
        attestation_address=attestation_address,
        before_address=before_address,
        after_address=after_address,
        entry_id=entry_id,
        changed_summary_fields=changed_summary_fields,
        audit_check_ids=audit_check_ids,
        accepted=accepted,
    )


def _append_operation(
    store: ReleaseAssuranceAttestationRegistryStore,
    attestation: ReleaseAssuranceAttestation,
    *,
    disposition: ReleaseAssuranceAttestationRegistryStoreDisposition,
    state: ReleaseAssuranceAttestationRegistryStoreState,
    anomaly_code: ReleaseAssuranceAttestationRegistryStoreAnomalyCode,
    registry: ReleaseAssuranceAttestationRegistry | None = None,
    entry: ReleaseAssuranceAttestationRegistryEntry | None = None,
) -> ReleaseAssuranceAttestationRegistryStoreAppendResult:
    selected_registry = registry or store.registry
    selected_entry = entry or store.registry.latest_entry
    changed = (
        _changed_entry_fields(store.registry.latest_entry, attestation)
        if selected_registry is not store.registry
        else ()
    )
    operation = _operation(
        ordinal=store.operation_count + 1,
        kind=ReleaseAssuranceAttestationRegistryStoreOperationKind.APPEND,
        disposition=disposition,
        state=state,
        anomaly_code=anomaly_code,
        attestation=attestation,
        before_address=store.registry.content_address,
        after_address=selected_registry.content_address,
        entry_id=selected_entry.entry_id if selected_registry is not store.registry else None,
        changed_summary_fields=changed,
        accepted=state is ReleaseAssuranceAttestationRegistryStoreState.ACCEPTED,
    )
    next_store = _store(
        store, registry=selected_registry, operations=store.operations + (operation,)
    )
    return ReleaseAssuranceAttestationRegistryStoreAppendResult(
        store=next_store,
        operation=operation,
        accepted=operation.accepted,
    )


def _rejection(
    store: ReleaseAssuranceAttestationRegistryStore,
    attestation: ReleaseAssuranceAttestation,
    anomaly_code: ReleaseAssuranceAttestationRegistryStoreAnomalyCode,
) -> ReleaseAssuranceAttestationRegistryStoreAppendResult:
    return _append_operation(
        store,
        attestation,
        disposition=ReleaseAssuranceAttestationRegistryStoreDisposition.REJECTED,
        state=ReleaseAssuranceAttestationRegistryStoreState.REJECTED,
        anomaly_code=anomaly_code,
    )


def append_release_assurance_attestation_registry_store(
    store: ReleaseAssuranceAttestationRegistryStore,
    attestation: ReleaseAssuranceAttestation | Mapping[str, Any],
    *,
    expected_head_address: str | None = None,
) -> ReleaseAssuranceAttestationRegistryStoreAppendResult:
    """Append one attestation with optimistic concurrency and retry controls."""

    selected = _as_attestation(attestation)
    if store.operation_count >= store.policy.max_operations:
        raise ValidationError("store operation limit has been reached")
    if expected_head_address is not None and expected_head_address != store.head_address:
        return _rejection(
            store,
            selected,
            ReleaseAssuranceAttestationRegistryStoreAnomalyCode.HEAD_MISMATCH,
        )
    if store.registry.entry_count >= store.policy.max_entries:
        return _rejection(
            store,
            selected,
            ReleaseAssuranceAttestationRegistryStoreAnomalyCode.CAPACITY_EXCEEDED,
        )
    existing_addresses = {item.attestation_address for item in store.registry.entries}
    existing_ids = {item.attestation_id for item in store.registry.entries}
    if selected.content_address in existing_addresses:
        return _append_operation(
            store,
            selected,
            disposition=ReleaseAssuranceAttestationRegistryStoreDisposition.IDEMPOTENT,
            state=ReleaseAssuranceAttestationRegistryStoreState.ACCEPTED,
            anomaly_code=ReleaseAssuranceAttestationRegistryStoreAnomalyCode.NONE,
        )
    if store.policy.reject_duplicates and selected.attestation_id in existing_ids:
        return _rejection(
            store,
            selected,
            ReleaseAssuranceAttestationRegistryStoreAnomalyCode.DUPLICATE_ATTESTATION,
        )
    if store.policy.require_accepted and not selected.accepted:
        return _rejection(
            store,
            selected,
            ReleaseAssuranceAttestationRegistryStoreAnomalyCode.UNACCEPTED_ATTESTATION,
        )
    if (
        not store.policy.allow_repeats
        and selected.content_address == store.head.head_attestation_address
    ):
        return _rejection(
            store,
            selected,
            ReleaseAssuranceAttestationRegistryStoreAnomalyCode.POLICY_MISMATCH,
        )
    registry, entry = _registry_with_append(store.registry, selected)
    return _append_operation(
        store,
        selected,
        disposition=ReleaseAssuranceAttestationRegistryStoreDisposition.APPENDED,
        state=ReleaseAssuranceAttestationRegistryStoreState.ACCEPTED,
        anomaly_code=ReleaseAssuranceAttestationRegistryStoreAnomalyCode.NONE,
        registry=registry,
        entry=entry,
    )


def append_release_assurance_attestation_registry_store_batch(
    store: ReleaseAssuranceAttestationRegistryStore,
    attestations: Iterable[ReleaseAssuranceAttestation | Mapping[str, Any]],
    *,
    expected_head_address: str | None = None,
    fail_fast: bool = False,
) -> ReleaseAssuranceAttestationRegistryStoreBatchResult:
    """Apply a bounded batch while preserving each individual decision."""

    selected = tuple(_as_attestation(item) for item in attestations)
    if not selected:
        raise ValidationError("store batch requires at least one attestation")
    if len(selected) > RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_MAX_BATCH_SIZE:
        raise ValidationError("store batch exceeds the maximum batch size")
    current = store
    decisions: list[ReleaseAssuranceAttestationRegistryStoreOperation] = []
    for index, item in enumerate(selected):
        result = append_release_assurance_attestation_registry_store(
            current,
            item,
            expected_head_address=expected_head_address if index == 0 else None,
        )
        decisions.append(result.operation)
        current = result.store
        if fail_fast and not result.accepted:
            break
    appended = sum(
        item.disposition is ReleaseAssuranceAttestationRegistryStoreDisposition.APPENDED
        for item in decisions
    )
    rejected = sum(
        item.disposition is ReleaseAssuranceAttestationRegistryStoreDisposition.REJECTED
        for item in decisions
    )
    idempotent = sum(
        item.disposition is ReleaseAssuranceAttestationRegistryStoreDisposition.IDEMPOTENT
        for item in decisions
    )
    accepted = rejected == 0 and len(decisions) == len(selected)
    body = {
        "store": current.to_dict(),
        "operations": tuple(item.to_dict() for item in decisions),
        "appended_count": appended,
        "rejected_count": rejected,
        "idempotent_count": idempotent,
        "accepted": accepted,
    }
    return ReleaseAssuranceAttestationRegistryStoreBatchResult(
        store=current,
        operations=tuple(decisions),
        appended_count=appended,
        rejected_count=rejected,
        idempotent_count=idempotent,
        accepted=accepted,
        content_address=content_hash(
            body,
            prefix="release-assurance-attestation-registry-store-batch-result",
        ),
    )


def release_assurance_attestation_registry_store_head_matches(
    store: ReleaseAssuranceAttestationRegistryStore,
    expected_head_address: str,
) -> bool:
    """Return whether a caller's optimistic cursor is still current."""

    return _text(expected_head_address, "expected_head_address") == store.head_address


def audit_release_assurance_attestation_registry_store(
    store: ReleaseAssuranceAttestationRegistryStore,
) -> ReleaseAssuranceAttestationRegistryStoreAudit:
    """Audit policy, head, operation sequence, addresses, and public boundary."""

    registry = store.registry
    operations = store.operations
    checks: list[ReleaseAssuranceAttestationRegistryStoreAuditCheck] = []

    def add(check_id: str, passed: bool, observed: Any, expected: Any, detail: str) -> None:
        checks.append(
            ReleaseAssuranceAttestationRegistryStoreAuditCheck(
                check_id=check_id,
                passed=bool(passed),
                observed=observed,
                expected=expected,
                detail=detail,
            )
        )

    add(
        "registry-id",
        store.policy.registry_id == registry.registry_id == store.head.registry_id,
        (store.policy.registry_id, registry.registry_id, store.head.registry_id),
        registry.registry_id,
        "policy, registry, and head identities agree",
    )
    add(
        "policy-entry-capacity",
        registry.entry_count
        <= store.policy.max_entries
        <= RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_MAX_ENTRIES,
        (registry.entry_count, store.policy.max_entries),
        f"at most {RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_MAX_ENTRIES}",
        "registry entry count is within policy capacity",
    )
    add(
        "policy-operation-capacity",
        len(operations)
        <= store.policy.max_operations
        <= RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_MAX_OPERATIONS,
        (len(operations), store.policy.max_operations),
        f"at most {RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_MAX_OPERATIONS}",
        "operation history is within policy capacity",
    )
    add(
        "head-entry-count",
        store.head.entry_count == registry.entry_count,
        store.head.entry_count,
        registry.entry_count,
        "head count matches registry count",
    )
    add(
        "head-entry-address",
        store.head.head_entry_address
        == registry.latest_entry.content_address
        == registry.head_address,
        (
            store.head.head_entry_address,
            registry.latest_entry.content_address,
            registry.head_address,
        ),
        registry.head_address,
        "head addresses reconcile",
    )
    add(
        "head-attestation-address",
        store.head.head_attestation_address == registry.latest_entry.attestation_address,
        store.head.head_attestation_address,
        registry.latest_entry.attestation_address,
        "head attestation address reconciles",
    )
    add(
        "head-accepted-count",
        store.head.accepted_entry_count == registry.accepted_entry_count,
        store.head.accepted_entry_count,
        registry.accepted_entry_count,
        "head accepted count reconciles",
    )
    add(
        "head-accepted-state",
        store.head.accepted == registry.accepted,
        store.head.accepted,
        registry.accepted,
        "head acceptance state reconciles",
    )
    add(
        "operation-ordinals",
        tuple(item.ordinal for item in operations) == tuple(range(1, len(operations) + 1)),
        tuple(item.ordinal for item in operations),
        tuple(range(1, len(operations) + 1)),
        "operation ordinals are contiguous",
    )
    add(
        "operation-identities",
        len({item.operation_id for item in operations}) == len(operations),
        tuple(item.operation_id for item in operations),
        "unique operation IDs",
        "operation IDs are unique",
    )
    add(
        "operation-addresses",
        all(item.after_address is not None for item in operations),
        tuple(item.after_address for item in operations),
        "non-empty registry addresses",
        "operations carry public registry addresses",
    )
    add(
        "operation-rejection-policy",
        all(
            item.disposition is not ReleaseAssuranceAttestationRegistryStoreDisposition.REJECTED
            or not item.accepted
            for item in operations
        ),
        tuple(
            item.operation_id
            for item in operations
            if item.disposition is ReleaseAssuranceAttestationRegistryStoreDisposition.REJECTED
            and item.accepted
        ),
        (),
        "rejected decisions cannot claim acceptance",
    )
    add(
        "operation-idempotence-policy",
        all(
            item.disposition is not ReleaseAssuranceAttestationRegistryStoreDisposition.IDEMPOTENT
            or item.state is ReleaseAssuranceAttestationRegistryStoreState.ACCEPTED
            for item in operations
        ),
        tuple(
            item.operation_id
            for item in operations
            if item.disposition is ReleaseAssuranceAttestationRegistryStoreDisposition.IDEMPOTENT
            and item.state is not ReleaseAssuranceAttestationRegistryStoreState.ACCEPTED
        ),
        (),
        "idempotent retries remain accepted",
    )
    public_keys = forbidden_keys(store.to_dict())
    add(
        "public-boundary",
        not public_keys,
        public_keys,
        (),
        "store projection contains no restricted metadata",
    )
    add(
        "store-address",
        bool(store.content_address),
        store.content_address,
        "non-empty content address",
        "store projection is addressed",
    )
    accepted = all(item.passed for item in checks) and store.accepted == registry.accepted
    return ReleaseAssuranceAttestationRegistryStoreAudit(
        store_id=store.store_id,
        registry_id=registry.registry_id,
        checks=tuple(checks),
        accepted=accepted,
    )


def verify_release_assurance_attestation_registry_store(
    value: ReleaseAssuranceAttestationRegistryStore | Mapping[str, Any],
) -> ReleaseAssuranceAttestationRegistryStoreAudit:
    """Strictly hydrate and audit a public store projection."""

    store = (
        value
        if isinstance(value, ReleaseAssuranceAttestationRegistryStore)
        else ReleaseAssuranceAttestationRegistryStore.from_mapping(value)
    )
    return audit_release_assurance_attestation_registry_store(store)


def query_release_assurance_attestation_registry_store_operations(
    store: ReleaseAssuranceAttestationRegistryStore,
    *,
    disposition: str | None = None,
    state: str | None = None,
    anomaly_code: str | None = None,
    kind: str | None = None,
    attestation_id: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return a deterministic, bounded page of public operation decisions."""

    offset = _int(offset, "offset", minimum=0)
    limit = _int(
        limit, "limit", minimum=1, maximum=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_MAX_LIMIT
    )
    selected = store.operations
    filters = {
        "disposition": disposition,
        "state": state,
        "anomaly_code": anomaly_code,
        "kind": kind,
        "attestation_id": attestation_id,
        "text": text,
    }
    normalized = {
        key: None if value is None else _text(value, key).lower() for key, value in filters.items()
    }
    if normalized["disposition"] is not None:
        selected = tuple(
            item for item in selected if item.disposition.value == normalized["disposition"]
        )
    if normalized["state"] is not None:
        selected = tuple(item for item in selected if item.state.value == normalized["state"])
    if normalized["anomaly_code"] is not None:
        selected = tuple(
            item for item in selected if item.anomaly_code.value == normalized["anomaly_code"]
        )
    if normalized["kind"] is not None:
        selected = tuple(item for item in selected if item.kind.value == normalized["kind"])
    if normalized["attestation_id"] is not None:
        selected = tuple(
            item for item in selected if item.attestation_id == normalized["attestation_id"]
        )
    if normalized["text"]:
        selected = tuple(
            item for item in selected if text_matches(item.to_dict(), normalized["text"])
        )
    total = len(selected)
    page = selected[offset : offset + limit]
    body = {
        "store_id": store.store_id,
        "resource": "operations",
        "filters": filters,
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": tuple(item.to_dict() for item in page),
        "accepted": store.accepted,
    }
    return body | {
        "has_more": offset + len(page) < total,
        "content_address": content_hash(
            body,
            prefix="release-assurance-attestation-registry-store-query",
        ),
    }


def replay_release_assurance_attestation_registry_store(
    store: ReleaseAssuranceAttestationRegistryStore,
    attestations: Iterable[ReleaseAssuranceAttestation | Mapping[str, Any]],
) -> ReleaseAssuranceAttestationRegistryStoreReplay:
    """Rebuild store state from source attestations and compare addresses."""

    selected = tuple(_as_attestation(item) for item in attestations)
    if not selected:
        raise ValidationError("store replay requires at least one attestation")
    rebuilt_registry = build_release_assurance_attestation_registry(
        [selected[0]], registry_id=store.registry.registry_id
    )
    rebuilt = build_release_assurance_attestation_registry_store(
        rebuilt_registry,
        store_id=store.store_id,
        policy=store.policy,
    )
    for attestation in selected[1:]:
        rebuilt = append_release_assurance_attestation_registry_store(rebuilt, attestation).store
    deterministic = rebuilt.registry.content_address == store.registry.content_address
    return ReleaseAssuranceAttestationRegistryStoreReplay(
        store_id=store.store_id,
        original_address=store.content_address,
        replayed_address=rebuilt.content_address,
        operation_count=rebuilt.operation_count,
        deterministic=deterministic,
        accepted=deterministic and rebuilt.accepted,
    )


def diff_release_assurance_attestation_registry_stores(
    left: ReleaseAssuranceAttestationRegistryStore | Mapping[str, Any],
    right: ReleaseAssuranceAttestationRegistryStore | Mapping[str, Any],
) -> dict[str, Any]:
    """Compare registry state and operational history without source payloads."""

    left_store = (
        left
        if isinstance(left, ReleaseAssuranceAttestationRegistryStore)
        else ReleaseAssuranceAttestationRegistryStore.from_mapping(left)
    )
    right_store = (
        right
        if isinstance(right, ReleaseAssuranceAttestationRegistryStore)
        else ReleaseAssuranceAttestationRegistryStore.from_mapping(right)
    )
    registry_diff = diff_release_assurance_attestation_registries(
        left_store.registry, right_store.registry
    ).to_dict()
    left_operation_ids = tuple(item.operation_id for item in left_store.operations)
    right_operation_ids = tuple(item.operation_id for item in right_store.operations)
    left_set = set(left_operation_ids)
    right_set = set(right_operation_ids)
    body = {
        "left_store_id": left_store.store_id,
        "right_store_id": right_store.store_id,
        "left_address": left_store.content_address,
        "right_address": right_store.content_address,
        "registry_diff": registry_diff,
        "added_operation_ids": tuple(item for item in right_operation_ids if item not in left_set),
        "removed_operation_ids": tuple(
            item for item in left_operation_ids if item not in right_set
        ),
        "identical_operation_ids": tuple(item for item in left_operation_ids if item in right_set),
        "identical": left_store.content_address == right_store.content_address,
        "accepted": left_store.accepted and right_store.accepted,
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix="release-assurance-attestation-registry-store-diff",
        )
    }


def release_assurance_attestation_registry_store_json(
    store: ReleaseAssuranceAttestationRegistryStore,
) -> str:
    return canonical_json(store.to_dict())


def release_assurance_attestation_registry_store_operations_csv(
    store: ReleaseAssuranceAttestationRegistryStore,
) -> bytes:
    stream = StringIO()
    writer = csv.DictWriter(
        stream,
        fieldnames=(
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
            "accepted",
            "content_address",
        ),
        lineterminator="\n",
    )
    writer.writeheader()
    for item in store.operations:
        writer.writerow(
            {
                "ordinal": item.ordinal,
                "operation_id": item.operation_id,
                "kind": item.kind.value,
                "disposition": item.disposition.value,
                "state": item.state.value,
                "anomaly_code": item.anomaly_code.value,
                "attestation_id": item.attestation_id or "",
                "attestation_address": item.attestation_address or "",
                "before_address": item.before_address or "",
                "after_address": item.after_address or "",
                "entry_id": item.entry_id or "",
                "changed_summary_fields": "|".join(item.changed_summary_fields),
                "accepted": str(item.accepted).lower(),
                "content_address": item.content_address,
            }
        )
    return stream.getvalue().encode("utf-8")


def release_assurance_attestation_registry_store_csv(
    store: ReleaseAssuranceAttestationRegistryStore,
) -> bytes:
    """Compatibility-shaped public alias for the operation ledger export."""

    return release_assurance_attestation_registry_store_operations_csv(store)


def release_assurance_attestation_registry_store_markdown(
    store: ReleaseAssuranceAttestationRegistryStore,
) -> bytes:
    audit = audit_release_assurance_attestation_registry_store(store)
    lines = [
        "# Longitudinal Attestation Registry Store",
        "",
        f"- Store: `{store.store_id}`",
        f"- Registry: `{store.registry.registry_id}`",
        f"- Accepted: `{str(store.accepted).lower()}`",
        f"- Registry address: `{store.registry.content_address}`",
        f"- Head address: `{store.head_address}`",
        f"- Entries: `{store.registry.entry_count}`",
        f"- Operations: `{store.operation_count}`",
        f"- Audit: `{str(audit.accepted).lower()}`",
        "",
        "## Operation ledger",
        "",
        "| Ordinal | Kind | Disposition | State | Anomaly | Attestation | Address |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for item in store.operations:
        lines.append(
            f"| {item.ordinal} | `{item.kind.value}` | `{item.disposition.value}` | "
            f"`{item.state.value}` | `{item.anomaly_code.value}` | "
            f"`{item.attestation_address or 'none'}` | `{item.content_address}` |"
        )
    lines.extend(("", "## Audit checks", "", "| Check | Passed | Detail |", "| --- | --- | --- |"))
    for check in audit.checks:
        lines.append(f"| `{check.check_id}` | `{str(check.passed).lower()}` | {check.detail} |")
    return ("\n".join(lines) + "\n").encode("utf-8")


def release_assurance_attestation_registry_store_capabilities() -> dict[str, Any]:
    return {
        "version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_VERSION,
        "schema_version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_SCHEMA_VERSION,
        "boundary": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_BOUNDARY,
        "append": True,
        "optimistic_head_check": True,
        "idempotent_retries": True,
        "duplicate_rejection": True,
        "capacity_rejection": True,
        "batch_append": True,
        "bounded_operation_history": True,
        "audit": True,
        "replay": True,
        "query": True,
        "diff": True,
        "json_export": True,
        "csv_export": True,
        "markdown_export": True,
        "source_payloads": False,
        "timestamp_free": True,
        "max_entries": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_MAX_ENTRIES,
        "max_operations": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_MAX_OPERATIONS,
        "max_batch_size": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_MAX_BATCH_SIZE,
    }


def release_assurance_attestation_registry_store_schema() -> dict[str, Any]:
    return {
        "version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_SCHEMA_VERSION,
        "type": "object",
        "boundary": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_BOUNDARY,
        "required": (
            "store_version",
            "schema_version",
            "store_id",
            "registry",
            "policy",
            "head",
            "operations",
            "accepted",
            "content_address",
        ),
        "properties": {
            "store_version": {
                "type": "string",
                "const": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_VERSION,
            },
            "schema_version": {
                "type": "string",
                "const": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_SCHEMA_VERSION,
            },
            "store_id": {"type": "string", "maxLength": 180},
            "registry": {"type": "object", "addressed": True},
            "policy": {"type": "object", "addressed": True},
            "head": {"type": "object", "addressed": True},
            "operations": {
                "type": "array",
                "maxItems": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_MAX_OPERATIONS,
            },
            "accepted": {"type": "boolean"},
            "content_address": {"type": "string"},
        },
        "operation_kinds": tuple(
            item.value for item in ReleaseAssuranceAttestationRegistryStoreOperationKind
        ),
        "dispositions": tuple(
            item.value for item in ReleaseAssuranceAttestationRegistryStoreDisposition
        ),
        "states": tuple(item.value for item in ReleaseAssuranceAttestationRegistryStoreState),
        "anomaly_codes": tuple(
            item.value for item in ReleaseAssuranceAttestationRegistryStoreAnomalyCode
        ),
    }


__all__ = [
    name
    for name in globals()
    if name.startswith("build_release_assurance_attestation_registry_store")
    or name.startswith("append_release_assurance_attestation_registry_store")
    or name.startswith("audit_release_assurance_attestation_registry_store")
    or name.startswith("verify_release_assurance_attestation_registry_store")
    or name.startswith("query_release_assurance_attestation_registry_store")
    or name.startswith("replay_release_assurance_attestation_registry_store")
    or name.startswith("diff_release_assurance_attestation_registry_store")
    or name.startswith("release_assurance_attestation_registry_store_")
    or name.startswith("ReleaseAssuranceAttestationRegistryStore")
]
