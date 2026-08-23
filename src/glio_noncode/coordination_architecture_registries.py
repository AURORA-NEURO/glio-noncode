"""Compute and public-reference registries for coordination runs."""

from __future__ import annotations

from .coordination_architecture_contracts import (
    CoordinationFixture,
    CoordinationRegistry,
    CoordinationRegistryEntry,
    addressed,
)


def _entry(entry_id: str, kind: str, title: str, version: str, contract: str, scope: str) -> CoordinationRegistryEntry:
    digest = addressed({"entry_id": entry_id, "version": version, "contract": contract}, "coordination-digest")
    body = {
        "entry_id": entry_id,
        "kind": kind,
        "title": title,
        "version": version,
        "digest": digest,
        "contract": contract,
        "public_scope": scope,
    }
    return CoordinationRegistryEntry(**body, content_address=addressed(body, "coordination-registry-entry"))


def build_coordination_compute_registry(fixture: CoordinationFixture) -> CoordinationRegistry:
    entries = (
        _entry("compute-local-cpu", "compute", "Deterministic local CPU profile", "1", "offline-json", "local_public_aggregate"),
        _entry("compute-local-memory", "compute", "Bounded local memory profile", "1", "addressed-projections", "local_public_aggregate"),
        _entry("compute-offline-package", "compute", "Offline package execution profile", "1", "bundle-manifest", "local_public_aggregate"),
        _entry("compute-reference-only", "compute", "Reference resolution profile", "1", "public-source-receipts", "public_aggregate"),
    )
    issues = () if all(item.public_scope in {"local_public_aggregate", "public_aggregate"} for item in entries) else ("scope_mismatch",)
    body = {"registry_id": f"{fixture.fixture_id}:compute", "kind": "compute", "entries": entries, "accepted": not issues, "issues": issues}
    return CoordinationRegistry(**body, content_address=addressed(body, "coordination-compute-registry"))


def build_coordination_reference_registry(fixture: CoordinationFixture) -> CoordinationRegistry:
    entries = tuple(
        _entry(source.source_id, "reference", source.title, source.version, "https-public-receipt", source.scope)
        for source in fixture.sources
    )
    issues = () if len({item.entry_id for item in entries}) == len(entries) else ("duplicate_reference_id",)
    body = {"registry_id": f"{fixture.fixture_id}:references", "kind": "reference", "entries": entries, "accepted": not issues, "issues": issues}
    return CoordinationRegistry(**body, content_address=addressed(body, "coordination-reference-registry"))


def validate_coordination_registry(registry: CoordinationRegistry, expected_scope: str | None = None) -> tuple[str, ...]:
    issues = list(registry.issues)
    if len({item.entry_id for item in registry.entries}) != len(registry.entries):
        issues.append("duplicate_entry_id")
    if any(not item.digest or not item.content_address for item in registry.entries):
        issues.append("missing_entry_address")
    if expected_scope is not None and any(item.public_scope != expected_scope for item in registry.entries):
        issues.append("unexpected_scope")
    return tuple(sorted(set(issues)))


__all__ = ["build_coordination_compute_registry", "build_coordination_reference_registry", "validate_coordination_registry"]
