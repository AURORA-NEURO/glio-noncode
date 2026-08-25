"""Address-only indexes over aggregate domains, artifacts, dependencies, and gates."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .program_release_closure_contracts import (
    ProgramReleaseClosureCheck,
    ProgramReleaseClosurePlane,
    ProgramReleaseIndexAudit,
    ProgramReleaseIndexEntry,
    ProgramReleaseIndexes,
    ProgramReleaseSnapshot,
    program_release_closure_check,
)
from .serialization import content_hash


def _entry(
    index_name: str, key: Any, resource: str, reference: Any, source: Any
) -> ProgramReleaseIndexEntry:
    body = {
        "index_name": index_name,
        "key": str(key),
        "resource": resource,
        "reference": str(reference),
        "source_address": str(source),
    }
    return ProgramReleaseIndexEntry(
        **body, content_address=content_hash(body, prefix="program-release-index-entry")
    )


def build_program_release_closure_indexes(
    snapshot: ProgramReleaseSnapshot,
) -> ProgramReleaseIndexes:
    """Build stable sorted indexes without copying source payload bytes."""

    domains = tuple(
        _entry("by_domain_id", item.domain_id, "domains", item.domain_id, item.content_address)
        for item in snapshot.domains
    )
    artifacts = tuple(
        _entry(
            "by_artifact_ref",
            item.artifact_ref,
            "artifacts",
            item.artifact_ref,
            item.content_address,
        )
        for item in snapshot.artifacts
    )
    dependencies = tuple(
        _entry(
            "by_dependency_id",
            item.dependency_id,
            "dependencies",
            item.dependency_id,
            item.content_address,
        )
        for item in snapshot.dependencies
    )
    gates = tuple(
        _entry("by_gate_id", item.gate_id, "gates", item.gate_id, item.content_address)
        for item in snapshot.gates
    )
    addresses = tuple(
        _entry(
            "by_content_address",
            item.content_address,
            resource,
            reference,
            item.source_address if hasattr(item, "source_address") else item.content_address,
        )
        for resource, values in (
            ("domains", snapshot.domains),
            ("artifacts", snapshot.artifacts),
            ("dependencies", snapshot.dependencies),
            ("gates", snapshot.gates),
        )
        for item in values
        for reference in (
            (
                getattr(item, "domain_id", None)
                or getattr(item, "artifact_ref", None)
                or getattr(item, "dependency_id", None)
                or getattr(item, "gate_id", None)
            ),
        )
    )
    sources = tuple(
        _entry(
            "by_source_address",
            item.source_address,
            "artifacts",
            item.artifact_ref,
            item.content_address,
        )
        for item in snapshot.artifacts
    ) + tuple(
        _entry(
            "by_source_address",
            item.source_runtime_address,
            "domains",
            item.domain_id,
            item.content_address,
        )
        for item in snapshot.domains
    )
    states = tuple(
        _entry(
            "by_state",
            state,
            "domains",
            state,
            content_hash({"state": state, "count": count}, prefix="program-release-state"),
        )
        for state, count in sorted(_state_counts(snapshot.domains).items())
    )
    body = {
        "bundle_id": snapshot.bundle_id,
        "by_domain_id": domains,
        "by_artifact_ref": artifacts,
        "by_dependency_id": dependencies,
        "by_gate_id": gates,
        "by_content_address": addresses,
        "by_source_address": sources,
        "by_state": states,
        "accepted": snapshot.accepted,
    }
    return ProgramReleaseIndexes(
        **body, content_address=content_hash(body, prefix="program-release-indexes")
    )


def _state_counts(domains: Iterable[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in domains:
        state = str(item.runtime_state)
        counts[state] = counts.get(state, 0) + 1
    return counts


def _audit(
    index_name: str, passed: bool, observed: Any, expected: Any, detail: str
) -> ProgramReleaseClosureCheck:
    return program_release_closure_check(
        f"indexes:{index_name}",
        ProgramReleaseClosurePlane.RECONCILIATION,
        passed,
        observed,
        expected,
        detail,
    )


def audit_program_release_closure_indexes(
    snapshot: ProgramReleaseSnapshot, indexes: ProgramReleaseIndexes
) -> ProgramReleaseIndexAudit:
    checks = (
        _audit(
            "accepted",
            indexes.accepted,
            indexes.accepted,
            True,
            "index build follows snapshot acceptance",
        ),
        _audit(
            "domain-count",
            len(indexes.by_domain_id) == len(snapshot.domains),
            len(indexes.by_domain_id),
            len(snapshot.domains),
            "domain index conserves domains",
        ),
        _audit(
            "artifact-count",
            len(indexes.by_artifact_ref) == len(snapshot.artifacts),
            len(indexes.by_artifact_ref),
            len(snapshot.artifacts),
            "artifact index conserves artifacts",
        ),
        _audit(
            "dependency-count",
            len(indexes.by_dependency_id) == len(snapshot.dependencies),
            len(indexes.by_dependency_id),
            len(snapshot.dependencies),
            "dependency index conserves edges",
        ),
        _audit(
            "gate-count",
            len(indexes.by_gate_id) == len(snapshot.gates),
            len(indexes.by_gate_id),
            len(snapshot.gates),
            "gate index conserves gates",
        ),
        _audit(
            "domain-unique",
            len({item.key for item in indexes.by_domain_id}) == len(indexes.by_domain_id),
            len({item.key for item in indexes.by_domain_id}),
            len(indexes.by_domain_id),
            "domain keys are unique",
        ),
        _audit(
            "artifact-unique",
            len({item.key for item in indexes.by_artifact_ref}) == len(indexes.by_artifact_ref),
            len({item.key for item in indexes.by_artifact_ref}),
            len(indexes.by_artifact_ref),
            "artifact keys are unique",
        ),
        _audit(
            "dependency-unique",
            len({item.key for item in indexes.by_dependency_id}) == len(indexes.by_dependency_id),
            len({item.key for item in indexes.by_dependency_id}),
            len(indexes.by_dependency_id),
            "dependency keys are unique",
        ),
        _audit(
            "gate-unique",
            len({item.key for item in indexes.by_gate_id}) == len(indexes.by_gate_id),
            len({item.key for item in indexes.by_gate_id}),
            len(indexes.by_gate_id),
            "gate keys are unique",
        ),
        _audit(
            "source-populated",
            len(indexes.by_source_address) == len(snapshot.artifacts) + len(snapshot.domains),
            len(indexes.by_source_address),
            len(snapshot.artifacts) + len(snapshot.domains),
            "source addresses are queryable",
        ),
        _audit(
            "address-populated",
            len(indexes.by_content_address)
            == len(snapshot.domains)
            + len(snapshot.artifacts)
            + len(snapshot.dependencies)
            + len(snapshot.gates),
            len(indexes.by_content_address),
            len(snapshot.domains)
            + len(snapshot.artifacts)
            + len(snapshot.dependencies)
            + len(snapshot.gates),
            "all resource addresses are queryable",
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {"bundle_id": snapshot.bundle_id, "checks": checks, "accepted": accepted}
    return ProgramReleaseIndexAudit(
        snapshot.bundle_id,
        checks,
        accepted,
        content_hash(body, prefix="program-release-index-audit"),
    )


def lookup_program_release_index(
    indexes: ProgramReleaseIndexes, index_name: str, key: str
) -> tuple[ProgramReleaseIndexEntry, ...]:
    values = getattr(indexes, index_name, None)
    if values is None or not index_name.startswith("by_"):
        raise KeyError(f"unknown program release index: {index_name}")
    return tuple(item for item in values if item.key == str(key))


__all__ = [
    name
    for name in globals()
    if name.startswith("build_program_release")
    or name.startswith("audit_program_release")
    or name.startswith("lookup_program_release")
    or name.startswith("ProgramRelease")
]
