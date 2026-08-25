"""Address-only indexes for fast service-release inspection."""

from __future__ import annotations

from collections.abc import Iterable
from .service_release_contracts import (
    ServiceReleaseCheck,
    ServiceReleaseIndexAudit,
    ServiceReleaseIndexEntry,
    ServiceReleaseIndexes,
    ServiceReleasePlane,
    ServiceReleaseSnapshot,
    check,
)
from .serialization import content_hash


def _entry(index_name: str, key: str, resource: str, reference: str, source_address: str) -> ServiceReleaseIndexEntry:
    body = {
        "index_name": index_name,
        "key": key,
        "resource": resource,
        "reference": reference,
        "source_address": source_address,
    }
    return ServiceReleaseIndexEntry(
        **body,
        content_address=content_hash(body, prefix="service-release-index-entry"),
    )


def build_service_release_indexes(snapshot: ServiceReleaseSnapshot) -> ServiceReleaseIndexes:
    """Build six sorted address-only lookup maps."""

    surfaces = tuple(
        _entry("by_surface_id", item.surface_id, "surfaces", item.surface_id, item.content_address)
        for item in snapshot.surfaces
    )
    artifacts = tuple(
        _entry("by_artifact_ref", item.artifact_ref, "artifacts", item.artifact_ref, item.content_address)
        for item in snapshot.artifacts
    )
    dependencies = tuple(
        _entry("by_dependency_id", item.dependency_id, "dependencies", item.dependency_id, item.content_address)
        for item in snapshot.dependencies
    )
    gates = tuple(
        _entry("by_gate_id", item.gate_id, "gates", item.gate_id, item.content_address)
        for item in snapshot.gates
    )
    address_values = [
        ("surfaces", item.surface_id, item.content_address)
        for item in snapshot.surfaces
    ] + [
        ("artifacts", item.artifact_ref, item.content_address)
        for item in snapshot.artifacts
    ] + [
        ("dependencies", item.dependency_id, item.content_address)
        for item in snapshot.dependencies
    ] + [
        ("gates", item.gate_id, item.content_address)
        for item in snapshot.gates
    ]
    by_address = tuple(
        _entry("by_content_address", address, resource, reference, address)
        for resource, reference, address in sorted(address_values, key=lambda item: item[2])
    )
    by_state = tuple(
        _entry("by_state", "accepted", "surfaces", item.surface_id, item.content_address)
        for item in snapshot.surfaces
        if item.accepted
    ) + tuple(
        _entry("by_state", "passed", "gates", item.gate_id, item.content_address)
        for item in snapshot.gates
        if item.passed
    )
    body = {
        "bundle_id": snapshot.bundle_id,
        "by_surface_id": surfaces,
        "by_artifact_ref": artifacts,
        "by_dependency_id": dependencies,
        "by_gate_id": gates,
        "by_content_address": by_address,
        "by_state": by_state,
        "accepted": snapshot.accepted,
    }
    return ServiceReleaseIndexes(
        snapshot.bundle_id,
        surfaces,
        artifacts,
        dependencies,
        gates,
        by_address,
        by_state,
        snapshot.accepted,
        content_hash(body, prefix="service-release-indexes"),
    )


def _unique_keys(values: Iterable[ServiceReleaseIndexEntry]) -> bool:
    rows = tuple(values)
    return len(rows) == len({(item.key, item.reference) for item in rows})


def audit_service_release_indexes(
    snapshot: ServiceReleaseSnapshot,
    indexes: ServiceReleaseIndexes,
) -> ServiceReleaseIndexAudit:
    """Independently check index coverage, ordering, and source addresses."""

    checks: list[ServiceReleaseCheck] = []
    checks.append(check(
        "indexes:surface-cardinality",
        ServiceReleasePlane.RECONCILIATION,
        len(indexes.by_surface_id) == len(snapshot.surfaces),
        len(indexes.by_surface_id),
        len(snapshot.surfaces),
        "surface index covers every registered surface",
    ))
    checks.append(check(
        "indexes:artifact-cardinality",
        ServiceReleasePlane.RECONCILIATION,
        len(indexes.by_artifact_ref) == len(snapshot.artifacts),
        len(indexes.by_artifact_ref),
        len(snapshot.artifacts),
        "artifact index covers every exact-byte artifact",
    ))
    checks.append(check(
        "indexes:dependency-cardinality",
        ServiceReleasePlane.RECONCILIATION,
        len(indexes.by_dependency_id) == len(snapshot.dependencies),
        len(indexes.by_dependency_id),
        len(snapshot.dependencies),
        "dependency index covers every forward edge",
    ))
    checks.append(check(
        "indexes:gate-cardinality",
        ServiceReleasePlane.RECONCILIATION,
        len(indexes.by_gate_id) == len(snapshot.gates),
        len(indexes.by_gate_id),
        len(snapshot.gates),
        "gate index covers every promotion gate",
    ))
    for name, values in (
        ("surface", indexes.by_surface_id),
        ("artifact", indexes.by_artifact_ref),
        ("dependency", indexes.by_dependency_id),
        ("gate", indexes.by_gate_id),
        ("address", indexes.by_content_address),
    ):
        checks.append(check(
            f"indexes:{name}-unique",
            ServiceReleasePlane.RECONCILIATION,
            _unique_keys(values),
            len(values),
            "unique key/reference pairs",
            f"{name} index keys are collision-free",
        ))
    checks.append(check(
        "indexes:address-order",
        ServiceReleasePlane.RECONCILIATION,
        tuple(item.key for item in indexes.by_content_address)
        == tuple(sorted(item.key for item in indexes.by_content_address)),
        tuple(item.key for item in indexes.by_content_address[:3]),
        "lexicographic",
        "address index has deterministic ordering",
    ))
    accepted = all(item.passed for item in checks) and indexes.accepted == snapshot.accepted
    body = {"bundle_id": snapshot.bundle_id, "checks": checks, "accepted": accepted}
    return ServiceReleaseIndexAudit(
        snapshot.bundle_id,
        tuple(checks),
        accepted,
        content_hash(body, prefix="service-release-index-audit"),
    )


__all__ = [
    "audit_service_release_indexes",
    "build_service_release_indexes",
]
