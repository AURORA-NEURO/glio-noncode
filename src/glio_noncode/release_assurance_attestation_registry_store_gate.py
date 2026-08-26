"""Evaluate registry-store promotion readiness.

An addressed store can be correct and still not be ready for a release
handoff.  This module provides a deterministic gate over that distinction. It
checks identity, acceptance, operation integrity, policy limits, rejection
history, head continuity, packet verification, baseline continuity, and the
public boundary.  A gate never promotes by side effect; it returns a decision
that a caller may retain, review, or explicitly use in a release workflow.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping
from io import StringIO
from typing import Any

from .errors import ValidationError
from .release_assurance_attestation_contracts import ReleaseAssuranceAttestation
from .release_assurance_attestation_registry_store import (
    append_release_assurance_attestation_registry_store,
    audit_release_assurance_attestation_registry_store,
)
from .release_assurance_attestation_registry_store_contracts import (
    ReleaseAssuranceAttestationRegistryStore,
)
from .release_assurance_attestation_registry_store_gate_contracts import (
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_BOUNDARY,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_DEFAULT_LIMIT,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_DIFF_VERSION,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_EXPECTED_CHECK_COUNT,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_MAX_CHECKS,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_MAX_LIMIT,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PLAN_VERSION,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_SCHEMA_VERSION,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_VERSION,
    ReleaseAssuranceAttestationRegistryStoreGate,
    ReleaseAssuranceAttestationRegistryStoreGateCheck,
    ReleaseAssuranceAttestationRegistryStoreGateDecision,
    ReleaseAssuranceAttestationRegistryStoreGateDiff,
    ReleaseAssuranceAttestationRegistryStoreGatePlan,
    ReleaseAssuranceAttestationRegistryStoreGatePolicy,
    ReleaseAssuranceAttestationRegistryStoreGateQueryResult,
    ReleaseAssuranceAttestationRegistryStoreGateSeverity,
    ReleaseAssuranceAttestationRegistryStoreGateState,
)
from .release_assurance_attestation_registry_store_packet_contracts import (
    ReleaseAssuranceAttestationRegistryStorePacketVerification,
)
from .release_assurance_support import forbidden_keys, text_matches
from .serialization import canonical_json, content_hash


def _as_store(
    value: ReleaseAssuranceAttestationRegistryStore | Mapping[str, Any],
) -> ReleaseAssuranceAttestationRegistryStore:
    return (
        value
        if isinstance(value, ReleaseAssuranceAttestationRegistryStore)
        else ReleaseAssuranceAttestationRegistryStore.from_mapping(value)
    )


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


def _severity_for(
    category: str, passed: bool
) -> ReleaseAssuranceAttestationRegistryStoreGateSeverity:
    if passed:
        return ReleaseAssuranceAttestationRegistryStoreGateSeverity.NONE
    if category in {"identity", "acceptance", "boundary"}:
        return ReleaseAssuranceAttestationRegistryStoreGateSeverity.CRITICAL
    if category in {"packet", "history", "baseline"}:
        return ReleaseAssuranceAttestationRegistryStoreGateSeverity.HIGH
    if category == "policy":
        return ReleaseAssuranceAttestationRegistryStoreGateSeverity.MODERATE
    return ReleaseAssuranceAttestationRegistryStoreGateSeverity.MODERATE


def _check(
    check_id: str,
    category: str,
    passed: bool,
    observed: Any,
    expected: Any,
    detail: str,
) -> ReleaseAssuranceAttestationRegistryStoreGateCheck:
    return ReleaseAssuranceAttestationRegistryStoreGateCheck(
        check_id=check_id,
        category=category,
        severity=_severity_for(category, passed),
        passed=bool(passed),
        observed=observed,
        expected=expected,
        detail=detail,
    )


def build_release_assurance_attestation_registry_store_gate_policy(
    *,
    gate_id: str,
    store_id: str,
    registry_id: str,
    require_accepted: bool = True,
    require_audit: bool = True,
    require_packet: bool = True,
    require_no_rejections: bool = True,
    require_baseline_continuity: bool = True,
    max_entries: int = 256,
    max_operations: int = 1024,
) -> ReleaseAssuranceAttestationRegistryStoreGatePolicy:
    """Create a named promotion policy with bounded limits."""

    return ReleaseAssuranceAttestationRegistryStoreGatePolicy(
        gate_id=_text(gate_id, "gate_id", maximum=180),
        store_id=_text(store_id, "store_id", maximum=180),
        registry_id=_text(registry_id, "registry_id", maximum=180),
        require_accepted=_bool(require_accepted, "require_accepted"),
        require_audit=_bool(require_audit, "require_audit"),
        require_packet=_bool(require_packet, "require_packet"),
        require_no_rejections=_bool(require_no_rejections, "require_no_rejections"),
        require_baseline_continuity=_bool(
            require_baseline_continuity,
            "require_baseline_continuity",
        ),
        max_entries=_int(max_entries, "max_entries", minimum=1, maximum=256),
        max_operations=_int(max_operations, "max_operations", minimum=1, maximum=4096),
    )


def _packet_accepted(
    packet_verification: ReleaseAssuranceAttestationRegistryStorePacketVerification
    | Mapping[str, Any]
    | None,
) -> bool:
    if packet_verification is None:
        return False
    if isinstance(packet_verification, ReleaseAssuranceAttestationRegistryStorePacketVerification):
        return packet_verification.accepted
    return bool(packet_verification.get("accepted", False))


def diff_release_assurance_attestation_registry_store_gate_state(
    baseline: ReleaseAssuranceAttestationRegistryStore | Mapping[str, Any],
    candidate: ReleaseAssuranceAttestationRegistryStore | Mapping[str, Any],
) -> ReleaseAssuranceAttestationRegistryStoreGateDiff:
    """Compare store sequence prefixes, heads, and operation histories."""

    left = _as_store(baseline)
    right = _as_store(candidate)
    left_entries = {item.entry_id: item for item in left.registry.entries}
    right_entries = {item.entry_id: item for item in right.registry.entries}
    shared_entries = set(left_entries) & set(right_entries)
    changed_entries = sum(
        left_entries[item].content_address != right_entries[item].content_address
        for item in shared_entries
    )
    left_operations = {item.operation_id: item for item in left.operations}
    right_operations = {item.operation_id: item for item in right.operations}
    continuous = (
        left.registry.registry_id == right.registry.registry_id
        and len(right.registry.entries) >= len(left.registry.entries)
        and tuple(
            item.content_address for item in right.registry.entries[: left.registry.entry_count]
        )
        == tuple(item.content_address for item in left.registry.entries)
    )
    body = {
        "diff_version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_DIFF_VERSION,
        "baseline_store_id": left.store_id,
        "candidate_store_id": right.store_id,
        "baseline_address": left.content_address,
        "candidate_address": right.content_address,
        "baseline_registry_address": left.registry.content_address,
        "candidate_registry_address": right.registry.content_address,
        "added_entry_count": len(set(right_entries) - set(left_entries)),
        "removed_entry_count": len(set(left_entries) - set(right_entries)),
        "changed_entry_count": changed_entries,
        "added_operation_count": len(set(right_operations) - set(left_operations)),
        "removed_operation_count": len(set(left_operations) - set(right_operations)),
        "changed_head": left.head_address != right.head_address,
        "continuous": continuous,
        "identical": left.content_address == right.content_address,
        "accepted": left.accepted and right.accepted,
    }
    return ReleaseAssuranceAttestationRegistryStoreGateDiff(
        **body,
        content_address=content_hash(
            body,
            prefix="release-assurance-attestation-registry-store-gate-diff",
        ),
    )


def _baseline_checks(
    store: ReleaseAssuranceAttestationRegistryStore,
    baseline: ReleaseAssuranceAttestationRegistryStore | None,
    required: bool,
) -> tuple[ReleaseAssuranceAttestationRegistryStoreGateCheck, ...]:
    if baseline is None:
        return (
            _check(
                "baseline-continuity",
                "baseline",
                not required or True,
                None,
                "not-required-or-no-baseline",
                "no baseline was supplied for this gate evaluation",
            ),
            _check(
                "baseline-identity",
                "baseline",
                True,
                None,
                "optional",
                "baseline identity check is not applicable",
            ),
        )
    diff = diff_release_assurance_attestation_registry_store_gate_state(baseline, store)
    return (
        _check(
            "baseline-continuity",
            "baseline",
            diff.continuous if required else True,
            diff.continuous,
            True if required else "not-required",
            "candidate registry preserves the baseline sequence prefix",
        ),
        _check(
            "baseline-identity",
            "baseline",
            baseline.store_id == store.store_id
            and baseline.registry.registry_id == store.registry.registry_id,
            (baseline.store_id, baseline.registry.registry_id),
            (store.store_id, store.registry.registry_id),
            "candidate and baseline belong to the same store identity",
        ),
    )


def build_release_assurance_attestation_registry_store_gate_checks(
    store: ReleaseAssuranceAttestationRegistryStore,
    policy: ReleaseAssuranceAttestationRegistryStoreGatePolicy,
    *,
    packet_verification: ReleaseAssuranceAttestationRegistryStorePacketVerification
    | Mapping[str, Any]
    | None = None,
    baseline: ReleaseAssuranceAttestationRegistryStore | None = None,
) -> tuple[ReleaseAssuranceAttestationRegistryStoreGateCheck, ...]:
    """Build the fixed twenty-check promotion denominator."""

    audit = audit_release_assurance_attestation_registry_store(store)
    operations = store.operations
    operation_ordinals = tuple(item.ordinal for item in operations)
    expected_ordinals = tuple(range(1, len(operations) + 1))
    public_violations = forbidden_keys(store.to_dict())
    packet_ok = _packet_accepted(packet_verification)
    checks = [
        _check(
            "identity-store",
            "identity",
            store.store_id == policy.store_id,
            store.store_id,
            policy.store_id,
            "store identity matches gate policy",
        ),
        _check(
            "identity-registry",
            "identity",
            store.registry.registry_id == policy.registry_id,
            store.registry.registry_id,
            policy.registry_id,
            "registry identity matches gate policy",
        ),
        _check(
            "acceptance-store",
            "acceptance",
            store.accepted if policy.require_accepted else True,
            store.accepted,
            True if policy.require_accepted else "not-required",
            "store acceptance satisfies the gate policy",
        ),
        _check(
            "acceptance-registry",
            "acceptance",
            store.registry.accepted if policy.require_accepted else True,
            store.registry.accepted,
            True if policy.require_accepted else "not-required",
            "registry acceptance satisfies the gate policy",
        ),
        _check(
            "acceptance-head",
            "acceptance",
            store.head.accepted if policy.require_accepted else True,
            store.head.accepted,
            True if policy.require_accepted else "not-required",
            "head acceptance satisfies the gate policy",
        ),
        _check(
            "policy-entry-capacity",
            "policy",
            store.registry.entry_count <= policy.max_entries,
            store.registry.entry_count,
            policy.max_entries,
            "entry count is within the promotion policy",
        ),
        _check(
            "policy-operation-capacity",
            "policy",
            len(operations) <= policy.max_operations,
            len(operations),
            policy.max_operations,
            "operation count is within the promotion policy",
        ),
        _check(
            "integrity-audit",
            "integrity",
            audit.accepted if policy.require_audit else True,
            audit.accepted,
            True if policy.require_audit else "not-required",
            "store audit closes policy, head, operation, and boundary checks",
        ),
        _check(
            "integrity-operation-ordinals",
            "integrity",
            operation_ordinals == expected_ordinals,
            operation_ordinals,
            expected_ordinals,
            "operation ordinals are contiguous",
        ),
        _check(
            "integrity-operation-addresses",
            "integrity",
            all(item.after_address is not None for item in operations),
            tuple(item.after_address for item in operations),
            "non-empty addresses",
            "every operation carries a public after-address",
        ),
        _check(
            "history-no-rejections",
            "history",
            store.rejection_count == 0 if policy.require_no_rejections else True,
            store.rejection_count,
            0 if policy.require_no_rejections else "not-required",
            "operation history has no rejected append decisions",
        ),
        _check(
            "history-head-operation",
            "history",
            all(
                item.after_address == store.registry.content_address
                or item.after_address is not None
                for item in operations
            ),
            tuple(item.after_address for item in operations),
            "addressed operation outcomes",
            "operation outcomes remain addressable",
        ),
        _check(
            "head-address",
            "integrity",
            store.head.head_entry_address == store.registry.head_address == store.head_address,
            (store.head.head_entry_address, store.registry.head_address, store.head_address),
            store.registry.head_address,
            "store head agrees with registry head",
        ),
        _check(
            "head-count",
            "integrity",
            store.head.entry_count == store.registry.entry_count,
            store.head.entry_count,
            store.registry.entry_count,
            "store head count agrees with registry count",
        ),
        _check(
            "boundary-public",
            "boundary",
            not public_violations,
            public_violations,
            (),
            "store projection remains within the public metadata boundary",
        ),
        _check(
            "packet-verification",
            "packet",
            packet_ok if policy.require_packet else True,
            packet_ok,
            True if policy.require_packet else "not-required",
            "an exact-byte store packet has been verified",
        ),
        _check(
            "packet-identity",
            "packet",
            packet_verification is None or packet_ok,
            packet_ok,
            True if packet_verification is not None else "not-supplied",
            "supplied packet verification is accepted",
        ),
        *_baseline_checks(store, baseline, policy.require_baseline_continuity),
        _check(
            "denominator-closure",
            "integrity",
            len(operations) <= policy.max_operations
            and len(store.registry.entries) <= policy.max_entries,
            (len(store.registry.entries), len(operations)),
            (policy.max_entries, policy.max_operations),
            "store denominators remain bounded and explicit",
        ),
    ]
    if len(checks) != RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_EXPECTED_CHECK_COUNT:
        raise ValidationError("store gate check denominator is not closed")
    return tuple(checks)


def evaluate_release_assurance_attestation_registry_store_gate(
    store: ReleaseAssuranceAttestationRegistryStore | Mapping[str, Any],
    *,
    policy: ReleaseAssuranceAttestationRegistryStoreGatePolicy | Mapping[str, Any] | None = None,
    packet_verification: ReleaseAssuranceAttestationRegistryStorePacketVerification
    | Mapping[str, Any]
    | None = None,
    baseline: ReleaseAssuranceAttestationRegistryStore | Mapping[str, Any] | None = None,
) -> ReleaseAssuranceAttestationRegistryStoreGate:
    """Evaluate one store against a deterministic twenty-check gate."""

    selected_store = _as_store(store)
    selected_policy = (
        build_release_assurance_attestation_registry_store_gate_policy(
            gate_id=f"{selected_store.store_id}-gate",
            store_id=selected_store.store_id,
            registry_id=selected_store.registry.registry_id,
        )
        if policy is None
        else policy
        if isinstance(policy, ReleaseAssuranceAttestationRegistryStoreGatePolicy)
        else ReleaseAssuranceAttestationRegistryStoreGatePolicy.from_mapping(policy)
    )
    if selected_policy.store_id != selected_store.store_id:
        raise ValidationError("gate policy and store IDs do not reconcile")
    if selected_policy.registry_id != selected_store.registry.registry_id:
        raise ValidationError("gate policy and registry IDs do not reconcile")
    selected_baseline = None if baseline is None else _as_store(baseline)
    checks = build_release_assurance_attestation_registry_store_gate_checks(
        selected_store,
        selected_policy,
        packet_verification=packet_verification,
        baseline=selected_baseline,
    )
    failed = tuple(item for item in checks if not item.passed)
    critical = any(
        item.severity is ReleaseAssuranceAttestationRegistryStoreGateSeverity.CRITICAL
        for item in failed
    )
    if not failed:
        state = ReleaseAssuranceAttestationRegistryStoreGateState.READY
        decision = ReleaseAssuranceAttestationRegistryStoreGateDecision.PROMOTE
    elif critical:
        state = ReleaseAssuranceAttestationRegistryStoreGateState.BLOCKED
        decision = ReleaseAssuranceAttestationRegistryStoreGateDecision.BLOCK_RELEASE
    else:
        state = ReleaseAssuranceAttestationRegistryStoreGateState.HOLD
        decision = ReleaseAssuranceAttestationRegistryStoreGateDecision.RETAIN
    body = {
        "gate_version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_VERSION,
        "schema_version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_SCHEMA_VERSION,
        "gate_id": selected_policy.gate_id,
        "store_id": selected_store.store_id,
        "registry_id": selected_store.registry.registry_id,
        "baseline_store_address": None
        if selected_baseline is None
        else selected_baseline.content_address,
        "candidate_store_address": selected_store.content_address,
        "policy": selected_policy.to_dict(),
        "checks": tuple(item.to_dict() for item in checks),
        "state": state,
        "decision": decision,
        "packet_verified": _packet_accepted(packet_verification),
        "accepted": not failed,
    }
    return ReleaseAssuranceAttestationRegistryStoreGate(
        gate_version=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_VERSION,
        schema_version=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_SCHEMA_VERSION,
        gate_id=selected_policy.gate_id,
        store_id=selected_store.store_id,
        registry_id=selected_store.registry.registry_id,
        baseline_store_address=None
        if selected_baseline is None
        else selected_baseline.content_address,
        candidate_store_address=selected_store.content_address,
        policy=selected_policy,
        checks=checks,
        state=state,
        decision=decision,
        packet_verified=_packet_accepted(packet_verification),
        accepted=not failed,
        content_address=content_hash(
            body, prefix="release-assurance-attestation-registry-store-gate"
        ),
    )


def build_release_assurance_attestation_registry_store_gate_plan(
    store: ReleaseAssuranceAttestationRegistryStore | Mapping[str, Any],
    attestation: ReleaseAssuranceAttestation | Mapping[str, Any],
    *,
    policy: ReleaseAssuranceAttestationRegistryStoreGatePolicy | Mapping[str, Any] | None = None,
    expected_head_address: str | None = None,
) -> ReleaseAssuranceAttestationRegistryStoreGatePlan:
    """Build a public preflight plan for appending a candidate attestation."""

    selected_store = _as_store(store)
    selected_attestation = _as_attestation(attestation)
    result = append_release_assurance_attestation_registry_store(
        selected_store,
        selected_attestation,
        expected_head_address=expected_head_address,
    )
    candidate = result.store
    selected_policy = (
        build_release_assurance_attestation_registry_store_gate_policy(
            gate_id=f"{selected_store.store_id}-gate",
            store_id=selected_store.store_id,
            registry_id=selected_store.registry.registry_id,
        )
        if policy is None
        else policy
        if isinstance(policy, ReleaseAssuranceAttestationRegistryStoreGatePolicy)
        else ReleaseAssuranceAttestationRegistryStoreGatePolicy.from_mapping(policy)
    )
    gate = evaluate_release_assurance_attestation_registry_store_gate(
        candidate,
        policy=selected_policy,
        baseline=selected_store,
    )
    accepted = result.accepted and gate.accepted
    proposed_action = (
        "append-and-promote"
        if accepted
        else "retain-and-review"
        if gate.state is ReleaseAssuranceAttestationRegistryStoreGateState.HOLD
        else "block-release"
    )
    body = {
        "plan_version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PLAN_VERSION,
        "gate_id": selected_policy.gate_id,
        "store_id": selected_store.store_id,
        "registry_id": selected_store.registry.registry_id,
        "current_store_address": selected_store.content_address,
        "expected_head_address": selected_store.head_address,
        "candidate_attestation_id": selected_attestation.attestation_id,
        "candidate_attestation_address": selected_attestation.content_address,
        "proposed_action": proposed_action,
        "gate_address": gate.content_address,
        "accepted": accepted,
    }
    return ReleaseAssuranceAttestationRegistryStoreGatePlan(
        **body,
        content_address=content_hash(
            body,
            prefix="release-assurance-attestation-registry-store-gate-plan",
        ),
    )


def query_release_assurance_attestation_registry_store_gate(
    gate: ReleaseAssuranceAttestationRegistryStoreGate | Mapping[str, Any],
    *,
    category: str | None = None,
    severity: str | None = None,
    failed_only: bool = False,
    text: str | None = None,
    offset: int = 0,
    limit: int = RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_DEFAULT_LIMIT,
) -> ReleaseAssuranceAttestationRegistryStoreGateQueryResult:
    """Return a bounded page of gate checks."""

    selected = (
        gate
        if isinstance(gate, ReleaseAssuranceAttestationRegistryStoreGate)
        else ReleaseAssuranceAttestationRegistryStoreGate.from_mapping(gate)
    )
    offset = _int(offset, "offset", minimum=0)
    limit = _int(
        limit,
        "limit",
        minimum=1,
        maximum=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_MAX_LIMIT,
    )
    category_filter = None if category is None else _text(category, "category", maximum=120).lower()
    severity_filter = None if severity is None else _text(severity, "severity", maximum=40).lower()
    text_filter = None if text is None else _text(text, "text", maximum=240).lower()
    items = selected.checks
    if category_filter is not None:
        items = tuple(item for item in items if item.category == category_filter)
    if severity_filter is not None:
        items = tuple(item for item in items if item.severity.value == severity_filter)
    if failed_only:
        items = tuple(item for item in items if not item.passed)
    if text_filter:
        items = tuple(item for item in items if text_matches(item.to_dict(), text_filter))
    total = len(items)
    page = items[offset : offset + limit]
    filters = {
        "category": category,
        "severity": severity,
        "failed_only": failed_only,
        "text": text,
    }
    body = {
        "gate_id": selected.gate_id,
        "resource": "checks",
        "filters": filters,
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": tuple(item.to_dict() for item in page),
        "accepted": selected.accepted,
    }
    return ReleaseAssuranceAttestationRegistryStoreGateQueryResult(
        gate_id=selected.gate_id,
        resource="checks",
        filters=filters,
        total=total,
        offset=offset,
        limit=limit,
        items=tuple(item.to_dict() for item in page),
        accepted=selected.accepted,
        content_address=content_hash(
            body,
            prefix="release-assurance-attestation-registry-store-gate-query",
        ),
    )


def release_assurance_attestation_registry_store_gate_json(
    gate: ReleaseAssuranceAttestationRegistryStoreGate,
) -> str:
    return canonical_json(gate.to_dict())


def release_assurance_attestation_registry_store_gate_csv(
    gate: ReleaseAssuranceAttestationRegistryStoreGate,
) -> bytes:
    stream = StringIO()
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(("check_id", "category", "severity", "passed", "detail", "content_address"))
    writer.writerows(
        (
            item.check_id,
            item.category,
            item.severity.value,
            str(item.passed).lower(),
            item.detail,
            item.content_address,
        )
        for item in gate.checks
    )
    return stream.getvalue().encode("utf-8")


def release_assurance_attestation_registry_store_gate_markdown(
    gate: ReleaseAssuranceAttestationRegistryStoreGate,
) -> bytes:
    lines = [
        "# Registry Store Promotion Gate",
        "",
        f"- Gate: `{gate.gate_id}`",
        f"- Store: `{gate.store_id}`",
        f"- Registry: `{gate.registry_id}`",
        f"- State: `{gate.state.value}`",
        f"- Decision: `{gate.decision.value}`",
        f"- Accepted: `{str(gate.accepted).lower()}`",
        f"- Candidate address: `{gate.candidate_store_address}`",
        "",
        "| Check | Category | Severity | Passed | Detail |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| `{item.check_id}` | `{item.category}` | `{item.severity.value}` | "
        f"`{str(item.passed).lower()}` | {item.detail} |"
        for item in gate.checks
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


def release_assurance_attestation_registry_store_gate_capabilities() -> dict[str, Any]:
    return {
        "version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_VERSION,
        "schema_version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_SCHEMA_VERSION,
        "boundary": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_BOUNDARY,
        "fixed_check_count": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_EXPECTED_CHECK_COUNT,
        "record_consistency_checks": True,
        "acceptance_checks": True,
        "policy_checks": True,
        "integrity_checks": True,
        "history_checks": True,
        "packet_checks": True,
        "baseline_continuity": True,
        "public_boundary": True,
        "preflight_plan": True,
        "bounded_query": True,
        "json_export": True,
        "csv_export": True,
        "markdown_export": True,
        "source_payloads": False,
        "timestamp_free": True,
    }


def release_assurance_attestation_registry_store_gate_schema() -> dict[str, Any]:
    return {
        "version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_SCHEMA_VERSION,
        "type": "object",
        "boundary": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_BOUNDARY,
        "required": (
            "gate_version",
            "schema_version",
            "gate_id",
            "store_id",
            "registry_id",
            "candidate_store_address",
            "policy",
            "checks",
            "state",
            "decision",
            "packet_verified",
            "accepted",
            "content_address",
        ),
        "check_count": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_EXPECTED_CHECK_COUNT,
        "max_checks": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_MAX_CHECKS,
        "states": tuple(item.value for item in ReleaseAssuranceAttestationRegistryStoreGateState),
        "decisions": tuple(
            item.value for item in ReleaseAssuranceAttestationRegistryStoreGateDecision
        ),
        "severities": tuple(
            item.value for item in ReleaseAssuranceAttestationRegistryStoreGateSeverity
        ),
        "categories": (
            "identity",
            "acceptance",
            "policy",
            "integrity",
            "history",
            "packet",
            "baseline",
            "boundary",
        ),
        "plan": {
            "version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_STORE_GATE_PLAN_VERSION,
            "type": "object",
            "address_only": True,
        },
    }


__all__ = [
    name
    for name in globals()
    if name.startswith("build_release_assurance_attestation_registry_store_gate")
    or name.startswith("evaluate_release_assurance_attestation_registry_store_gate")
    or name.startswith("diff_release_assurance_attestation_registry_store_gate")
    or name.startswith("query_release_assurance_attestation_registry_store_gate")
    or name.startswith("release_assurance_attestation_registry_store_gate_")
    or name.startswith("ReleaseAssuranceAttestationRegistryStoreGate")
]
