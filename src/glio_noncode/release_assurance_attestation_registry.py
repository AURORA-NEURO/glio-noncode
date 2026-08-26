"""Build and inspect an append-only registry of release attestations.

The final attestation proves one release state.  This module adds the missing
longitudinal layer: a bounded sequence of those states that can be replayed,
queried, compared, exported, and checked without rebuilding source payloads.
Every entry is a compact summary of an attestation.  The registry never
stores the underlying component rows, checks, case content, or execution
inputs; callers can independently retain the original attestation packets.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from io import StringIO
from typing import Any

from .errors import ValidationError
from .release_assurance_attestation_contracts import ReleaseAssuranceAttestation
from .release_assurance_attestation_registry_contracts import (
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_DEFAULT_LIMIT,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_DIFF_VERSION,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_MAX_ENTRIES,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_MAX_LIMIT,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_RESOURCE_NAMES,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_SCHEMA_VERSION,
    RELEASE_ASSURANCE_ATTESTATION_REGISTRY_VERSION,
    ReleaseAssuranceAttestationRegistry,
    ReleaseAssuranceAttestationRegistryDiff,
    ReleaseAssuranceAttestationRegistryEntry,
    ReleaseAssuranceAttestationRegistryQueryResult,
    ReleaseAssuranceAttestationRegistryTransition,
    ReleaseAssuranceAttestationRegistryTransitionState,
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


def _changed_summary_fields(
    before: ReleaseAssuranceAttestation,
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
        "failed_check_ids",
    )
    before_body = before.to_dict()
    after_body = after.to_dict()
    return tuple(field for field in fields if before_body.get(field) != after_body.get(field))


def _transition_state(
    before: ReleaseAssuranceAttestation,
    after: ReleaseAssuranceAttestation,
) -> ReleaseAssuranceAttestationRegistryTransitionState:
    if not after.accepted:
        return ReleaseAssuranceAttestationRegistryTransitionState.BLOCKED
    if before.content_address == after.content_address:
        return ReleaseAssuranceAttestationRegistryTransitionState.REPEAT
    return ReleaseAssuranceAttestationRegistryTransitionState.ADVANCE


def _entry(
    ordinal: int,
    attestation: ReleaseAssuranceAttestation,
    previous_entry_address: str,
    transition: ReleaseAssuranceAttestationRegistryTransitionState,
) -> ReleaseAssuranceAttestationRegistryEntry:
    body = {
        "ordinal": ordinal,
        "entry_id": f"registry:{ordinal:04d}:{attestation.attestation_id}",
        "attestation_id": attestation.attestation_id,
        "bundle_id": attestation.bundle_id,
        "run_id": attestation.run_id,
        "attestation_address": attestation.content_address,
        "previous_entry_address": previous_entry_address,
        "transition": transition,
        "accepted": attestation.accepted,
        "component_count": attestation.component_count,
        "check_count": attestation.check_count,
        "passed_check_count": attestation.passed_check_count,
        "overall_percent": attestation.overall_percent,
    }
    return ReleaseAssuranceAttestationRegistryEntry(
        **body,
        content_address=content_hash(body, prefix="release-assurance-attestation-registry-entry"),
    )


def _transition(
    ordinal: int,
    before: ReleaseAssuranceAttestation,
    after: ReleaseAssuranceAttestation,
    before_entry: ReleaseAssuranceAttestationRegistryEntry,
    after_entry: ReleaseAssuranceAttestationRegistryEntry,
) -> ReleaseAssuranceAttestationRegistryTransition:
    body = {
        "ordinal": ordinal,
        "transition_id": f"transition:{ordinal:04d}:{before.attestation_id}:{after.attestation_id}",
        "from_entry_address": before_entry.content_address,
        "to_entry_address": after_entry.content_address,
        "from_attestation_address": before.content_address,
        "to_attestation_address": after.content_address,
        "state": _transition_state(before, after),
        "changed_summary_fields": _changed_summary_fields(before, after),
        "accepted": before.accepted and after.accepted,
    }
    return ReleaseAssuranceAttestationRegistryTransition(
        **body,
        content_address=content_hash(
            body,
            prefix="release-assurance-attestation-registry-transition",
        ),
    )


def _registry_body(
    registry_version: str,
    schema_version: str,
    registry_id: str,
    entries: tuple[ReleaseAssuranceAttestationRegistryEntry, ...],
    transitions: tuple[ReleaseAssuranceAttestationRegistryTransition, ...],
    head_address: str,
    accepted: bool,
) -> dict[str, Any]:
    return {
        "registry_version": registry_version,
        "schema_version": schema_version,
        "registry_id": registry_id,
        "entries": tuple(item.to_dict() for item in entries),
        "transitions": tuple(item.to_dict() for item in transitions),
        "head_address": head_address,
        "accepted": accepted,
    }


def build_release_assurance_attestation_registry(
    attestations: Iterable[ReleaseAssuranceAttestation | Mapping[str, Any]] | None = None,
    *,
    registry_id: str = "glio-noncode-release-assurance-attestation-registry",
) -> ReleaseAssuranceAttestationRegistry:
    """Build a bounded append-only registry in caller-supplied order."""

    _text(registry_id, "registry_id", maximum=180)
    if attestations is None:
        from .release_assurance_attestation_runtime import run_release_assurance_attestation

        selected_attestations = (run_release_assurance_attestation().attestation,)
    else:
        selected_attestations = tuple(_as_attestation(item) for item in attestations)
    if not selected_attestations:
        raise ValidationError("attestation registry requires at least one attestation")
    if len(selected_attestations) > RELEASE_ASSURANCE_ATTESTATION_REGISTRY_MAX_ENTRIES:
        raise ValidationError("attestation registry exceeds the maximum entry count")
    entries: list[ReleaseAssuranceAttestationRegistryEntry] = []
    transitions: list[ReleaseAssuranceAttestationRegistryTransition] = []
    previous_address = "root"
    for ordinal, attestation in enumerate(selected_attestations, start=1):
        transition_state = (
            ReleaseAssuranceAttestationRegistryTransitionState.INITIAL
            if ordinal == 1
            else _transition_state(selected_attestations[ordinal - 2], attestation)
        )
        current = _entry(ordinal, attestation, previous_address, transition_state)
        entries.append(current)
        if ordinal > 1:
            transitions.append(
                _transition(
                    ordinal - 1,
                    selected_attestations[ordinal - 2],
                    attestation,
                    entries[-2],
                    current,
                )
            )
        previous_address = current.content_address
    entry_tuple = tuple(entries)
    transition_tuple = tuple(transitions)
    accepted = bool(entry_tuple) and all(item.accepted for item in entry_tuple)
    body = _registry_body(
        RELEASE_ASSURANCE_ATTESTATION_REGISTRY_VERSION,
        RELEASE_ASSURANCE_ATTESTATION_REGISTRY_SCHEMA_VERSION,
        registry_id,
        entry_tuple,
        transition_tuple,
        entry_tuple[-1].content_address,
        accepted,
    )
    return ReleaseAssuranceAttestationRegistry(
        registry_version=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_VERSION,
        schema_version=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_SCHEMA_VERSION,
        registry_id=registry_id,
        entries=entry_tuple,
        transitions=transition_tuple,
        head_address=entry_tuple[-1].content_address,
        accepted=accepted,
        content_address=content_hash(body, prefix="release-assurance-attestation-registry"),
    )


def audit_release_assurance_attestation_registry(
    registry: ReleaseAssuranceAttestationRegistry,
    attestations: Iterable[ReleaseAssuranceAttestation | Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """Audit linkage, ordering, chain continuity, and acceptance propagation."""

    selected = tuple(_as_attestation(item) for item in attestations)
    ids = tuple(item.entry_id for item in registry.entries)
    ordinals = tuple(item.ordinal for item in registry.entries)
    expected_registry = build_release_assurance_attestation_registry(
        selected, registry_id=registry.registry_id
    )
    checks: list[dict[str, Any]] = [
        {
            "check_id": "registry:entry-count",
            "passed": registry.entry_count
            == len(selected)
            <= RELEASE_ASSURANCE_ATTESTATION_REGISTRY_MAX_ENTRIES,
            "observed": registry.entry_count,
            "expected": len(selected),
        },
        {
            "check_id": "registry:non-empty",
            "passed": bool(registry.entries),
            "observed": registry.entry_count,
            "expected": ">0",
        },
        {
            "check_id": "registry:ordinals",
            "passed": ordinals == tuple(range(1, registry.entry_count + 1)),
            "observed": ordinals,
            "expected": tuple(range(1, registry.entry_count + 1)),
        },
        {
            "check_id": "registry:unique-entry-ids",
            "passed": len(ids) == len(set(ids)),
            "observed": len(ids),
            "expected": len(set(ids)),
        },
        {
            "check_id": "registry:attestation-linkage",
            "passed": tuple(item.attestation_address for item in registry.entries)
            == tuple(item.content_address for item in selected),
            "observed": tuple(item.attestation_address for item in registry.entries),
            "expected": tuple(item.content_address for item in selected),
        },
        {
            "check_id": "registry:summary-linkage",
            "passed": all(
                entry.component_count == attestation.component_count
                and entry.check_count == attestation.check_count
                and entry.passed_check_count == attestation.passed_check_count
                and entry.overall_percent == attestation.overall_percent
                and entry.accepted == attestation.accepted
                for entry, attestation in zip(registry.entries, selected, strict=False)
            ),
            "observed": registry.entry_count,
            "expected": len(selected),
        },
        {
            "check_id": "registry:previous-entry-chain",
            "passed": bool(registry.entries)
            and registry.entries[0].previous_entry_address == "root"
            and all(
                current.previous_entry_address == previous.content_address
                for previous, current in zip(registry.entries, registry.entries[1:], strict=False)
            ),
            "observed": tuple(item.previous_entry_address for item in registry.entries),
            "expected": "root then prior entry address",
        },
        {
            "check_id": "registry:transition-count",
            "passed": registry.transition_count == max(0, registry.entry_count - 1),
            "observed": registry.transition_count,
            "expected": max(0, registry.entry_count - 1),
        },
        {
            "check_id": "registry:transition-linkage",
            "passed": all(
                transition.from_entry_address == registry.entries[index].content_address
                and transition.to_entry_address == registry.entries[index + 1].content_address
                for index, transition in enumerate(registry.transitions)
            ),
            "observed": tuple(item.transition_id for item in registry.transitions),
            "expected": registry.transition_count,
        },
        {
            "check_id": "registry:head",
            "passed": bool(registry.entries)
            and registry.head_address == registry.entries[-1].content_address,
            "observed": registry.head_address,
            "expected": registry.entries[-1].content_address if registry.entries else None,
        },
        {
            "check_id": "registry:acceptance-propagation",
            "passed": registry.accepted == all(item.accepted for item in registry.entries),
            "observed": registry.accepted,
            "expected": all(item.accepted for item in registry.entries),
        },
        {
            "check_id": "registry:address-replay",
            "passed": registry.content_address == expected_registry.content_address,
            "observed": registry.content_address,
            "expected": expected_registry.content_address,
        },
        {
            "check_id": "registry:public-boundary",
            "passed": not forbidden_keys(registry.to_dict()),
            "observed": (),
            "expected": "no restricted public metadata",
        },
    ]
    return tuple(checks)


def replay_release_assurance_attestation_registry(
    registry: ReleaseAssuranceAttestationRegistry,
    attestations: Iterable[ReleaseAssuranceAttestation | Mapping[str, Any]],
) -> dict[str, Any]:
    """Rebuild a registry from supplied attestations and compare its address."""

    selected = tuple(_as_attestation(item) for item in attestations)
    replayed = build_release_assurance_attestation_registry(
        selected, registry_id=registry.registry_id
    )
    audits = audit_release_assurance_attestation_registry(registry, selected)
    return {
        "registry_id": registry.registry_id,
        "first_address": registry.content_address,
        "replayed_address": replayed.content_address,
        "deterministic": registry.content_address == replayed.content_address,
        "accepted": registry.content_address == replayed.content_address
        and all(item["passed"] for item in audits),
        "audit": audits,
        "content_address": content_hash(
            {
                "registry_id": registry.registry_id,
                "first_address": registry.content_address,
                "replayed_address": replayed.content_address,
                "deterministic": registry.content_address == replayed.content_address,
                "audit": audits,
            },
            prefix="release-assurance-attestation-registry-replay",
        ),
    }


def _query_filter_value(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _text(value, field, maximum=180)


def query_release_assurance_attestation_registry(
    registry: ReleaseAssuranceAttestationRegistry,
    *,
    resource: str = "entries",
    bundle_id: str | None = None,
    accepted_only: bool = False,
    transition_state: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = RELEASE_ASSURANCE_ATTESTATION_REGISTRY_DEFAULT_LIMIT,
) -> ReleaseAssuranceAttestationRegistryQueryResult:
    """Return a stable bounded page over entries or adjacent transitions."""

    resource = _text(resource, "registry_query.resource", maximum=32)
    if resource not in RELEASE_ASSURANCE_ATTESTATION_REGISTRY_RESOURCE_NAMES:
        raise ValidationError(f"unsupported registry query resource: {resource}")
    offset = _int(offset, "registry_query.offset")
    limit = _int(
        limit,
        "registry_query.limit",
        minimum=1,
        maximum=min(
            RELEASE_ASSURANCE_ATTESTATION_REGISTRY_MAX_LIMIT,
            RELEASE_ASSURANCE_ATTESTATION_REGISTRY_MAX_ENTRIES,
        ),
    )
    accepted_only = _bool(accepted_only, "registry_query.accepted_only")
    bundle_id = _query_filter_value(bundle_id, "registry_query.bundle_id")
    transition_state = _query_filter_value(transition_state, "registry_query.transition_state")
    text = None if text is None else _text(text, "registry_query.text", maximum=240)
    rows: tuple[dict[str, Any], ...]
    if resource == "entries":
        selected_entries = registry.entries
        if bundle_id is not None:
            selected_entries = tuple(
                item for item in selected_entries if item.bundle_id == bundle_id
            )
        if accepted_only:
            selected_entries = tuple(item for item in selected_entries if item.accepted)
        if transition_state is not None:
            selected_entries = tuple(
                item for item in selected_entries if item.transition.value == transition_state
            )
        rows = tuple(item.to_dict() for item in selected_entries)
    else:
        selected_transitions = registry.transitions
        if transition_state is not None:
            selected_transitions = tuple(
                item for item in selected_transitions if item.state.value == transition_state
            )
        if accepted_only:
            selected_transitions = tuple(item for item in selected_transitions if item.accepted)
        rows = tuple(item.to_dict() for item in selected_transitions)
    if text is not None:
        rows = tuple(item for item in rows if text_matches(item, text))
    page = rows[offset : offset + limit]
    filters = {
        "bundle_id": bundle_id,
        "accepted_only": accepted_only,
        "transition_state": transition_state,
        "text": text,
    }
    body = {
        "registry_id": registry.registry_id,
        "resource": resource,
        "filters": filters,
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": page,
    }
    return ReleaseAssuranceAttestationRegistryQueryResult(
        registry_id=registry.registry_id,
        resource=resource,
        filters=filters,
        total=len(rows),
        offset=offset,
        limit=limit,
        items=page,
        accepted=True,
        content_address=content_hash(
            body,
            prefix="release-assurance-attestation-registry-query",
        ),
    )


def diff_release_assurance_attestation_registries(
    left: ReleaseAssuranceAttestationRegistry | Mapping[str, Any],
    right: ReleaseAssuranceAttestationRegistry | Mapping[str, Any],
) -> ReleaseAssuranceAttestationRegistryDiff:
    """Compare two registries using only public entry and transition summaries."""

    before = (
        left
        if isinstance(left, ReleaseAssuranceAttestationRegistry)
        else ReleaseAssuranceAttestationRegistry.from_mapping(left)
    )
    after = (
        right
        if isinstance(right, ReleaseAssuranceAttestationRegistry)
        else ReleaseAssuranceAttestationRegistry.from_mapping(right)
    )
    left_entries = {item.entry_id: item.to_dict() for item in before.entries}
    right_entries = {item.entry_id: item.to_dict() for item in after.entries}
    shared = sorted(set(left_entries) & set(right_entries))
    changed = tuple(item for item in shared if left_entries[item] != right_entries[item])
    unchanged = tuple(item for item in shared if item not in changed)
    left_addresses = {item.attestation_address for item in before.entries}
    right_addresses = {item.attestation_address for item in after.entries}
    transition_changes = tuple(
        index + 1
        for index, (left_item, right_item) in enumerate(
            zip(before.transitions, after.transitions, strict=False), start=0
        )
        if left_item.to_dict() != right_item.to_dict()
    )
    body = {
        "left_registry_id": before.registry_id,
        "right_registry_id": after.registry_id,
        "left_address": before.content_address,
        "right_address": after.content_address,
        "added_entry_ids": tuple(sorted(set(right_entries) - set(left_entries))),
        "removed_entry_ids": tuple(sorted(set(left_entries) - set(right_entries))),
        "changed_entry_ids": changed,
        "unchanged_entry_ids": unchanged,
        "added_attestation_addresses": tuple(sorted(right_addresses - left_addresses)),
        "removed_attestation_addresses": tuple(sorted(left_addresses - right_addresses)),
        "changed_transition_ordinals": transition_changes,
        "identical": before.content_address == after.content_address,
        "accepted": before.accepted and after.accepted,
    }
    return ReleaseAssuranceAttestationRegistryDiff(
        **body,
        content_address=content_hash(
            body, prefix=RELEASE_ASSURANCE_ATTESTATION_REGISTRY_DIFF_VERSION
        ),
    )


def release_assurance_attestation_registry_json(
    registry: ReleaseAssuranceAttestationRegistry | Mapping[str, Any],
) -> str:
    selected = (
        registry
        if isinstance(registry, ReleaseAssuranceAttestationRegistry)
        else ReleaseAssuranceAttestationRegistry.from_mapping(registry)
    )
    return canonical_json(selected.to_dict()) + "\n"


def release_assurance_attestation_registry_csv(
    registry: ReleaseAssuranceAttestationRegistry | Mapping[str, Any],
) -> str:
    selected = (
        registry
        if isinstance(registry, ReleaseAssuranceAttestationRegistry)
        else ReleaseAssuranceAttestationRegistry.from_mapping(registry)
    )
    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "row_type",
            "ordinal",
            "row_id",
            "attestation_address",
            "from_address",
            "to_address",
            "state",
            "accepted",
            "content_address",
        )
    )
    for item in selected.entries:
        writer.writerow(
            (
                "entry",
                item.ordinal,
                item.entry_id,
                item.attestation_address,
                item.previous_entry_address,
                item.content_address,
                item.transition.value,
                str(item.accepted).lower(),
                item.content_address,
            )
        )
    for item in selected.transitions:
        writer.writerow(
            (
                "transition",
                item.ordinal,
                item.transition_id,
                item.to_attestation_address,
                item.from_entry_address,
                item.to_entry_address,
                item.state.value,
                str(item.accepted).lower(),
                item.content_address,
            )
        )
    return output.getvalue()


def release_assurance_attestation_registry_markdown(
    registry: ReleaseAssuranceAttestationRegistry | Mapping[str, Any],
) -> str:
    selected = (
        registry
        if isinstance(registry, ReleaseAssuranceAttestationRegistry)
        else ReleaseAssuranceAttestationRegistry.from_mapping(registry)
    )
    lines = [
        "# Release assurance attestation registry",
        "",
        f"- Registry: `{selected.registry_id}`",
        f"- Accepted: `{str(selected.accepted).lower()}`",
        f"- Entries: `{selected.entry_count}`",
        f"- Head: `{selected.head_address}`",
        "",
        "| Ordinal | Entry | Transition | Accepted | Attestation address | Entry address |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| {item.ordinal} | `{item.entry_id}` | {item.transition.value} | "
        f"{str(item.accepted).lower()} | `{item.attestation_address}` | `{item.content_address}` |"
        for item in selected.entries
    )
    lines.extend(("", "The registry retains public summaries and addresses only.", ""))
    return "\n".join(lines)


def release_assurance_attestation_registry_export_payloads(
    registry: ReleaseAssuranceAttestationRegistry,
) -> dict[str, bytes]:
    """Return deterministic registry exports for a packet or caller."""

    return {
        "registry.json": release_assurance_attestation_registry_json(registry).encode("utf-8"),
        "registry.csv": release_assurance_attestation_registry_csv(registry).encode("utf-8"),
        "registry.md": release_assurance_attestation_registry_markdown(registry).encode("utf-8"),
    }


def release_assurance_attestation_registry_schema() -> dict[str, Any]:
    """Describe registry resources, chain rules, and public limits."""

    return {
        "version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_SCHEMA_VERSION,
        "registry_version": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_VERSION,
        "boundary": "public_longitudinal_release_registry",
        "resources": list(RELEASE_ASSURANCE_ATTESTATION_REGISTRY_RESOURCE_NAMES),
        "max_entries": RELEASE_ASSURANCE_ATTESTATION_REGISTRY_MAX_ENTRIES,
        "entry_fields": [
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
        ],
        "transition_states": [
            item.value for item in ReleaseAssuranceAttestationRegistryTransitionState
        ],
        "append_only": True,
        "timestamp_free": True,
        "source_payloads": False,
    }


def release_assurance_attestation_registry_capabilities() -> dict[str, Any]:
    """Describe the longitudinal registry's public guarantees."""

    return {
        "version": "release-assurance-attestation-registry-capabilities-v1",
        "append_only_chain": True,
        "bounded_entries": True,
        "entry_summary_only": True,
        "transition_classification": True,
        "replay_audit": True,
        "bounded_query": True,
        "registry_diff": True,
        "json_export": True,
        "csv_export": True,
        "markdown_export": True,
        "timestamp_free": True,
        "source_payloads": False,
        "restricted_metadata": False,
    }


__all__ = [
    "audit_release_assurance_attestation_registry",
    "build_release_assurance_attestation_registry",
    "diff_release_assurance_attestation_registries",
    "query_release_assurance_attestation_registry",
    "replay_release_assurance_attestation_registry",
    "release_assurance_attestation_registry_capabilities",
    "release_assurance_attestation_registry_csv",
    "release_assurance_attestation_registry_export_payloads",
    "release_assurance_attestation_registry_json",
    "release_assurance_attestation_registry_markdown",
    "release_assurance_attestation_registry_schema",
]
