"""Portable release checkpoint joining the deep assurance projections."""

from __future__ import annotations

from .release_assurance_catalog import build_release_assurance_catalog
from .release_assurance_compliance import audit_release_assurance_compliance
from .release_assurance_contracts import (
    ReleaseAssuranceCheckpoint,
    ReleaseAssurancePlane,
    ReleaseAssuranceRuntimeReport,
    check,
)
from .release_assurance_operations import build_release_assurance_operations
from .release_assurance_performance import audit_release_assurance_performance
from .release_assurance_reconciliation import reconcile_release_assurance
from .serialization import content_hash


def build_release_assurance_checkpoint(
    runtime: ReleaseAssuranceRuntimeReport,
) -> ReleaseAssuranceCheckpoint:
    """Build one compact checkpoint over every runtime-derived projection."""

    snapshot = runtime.snapshot
    reconciliation = reconcile_release_assurance(snapshot)
    catalog = build_release_assurance_catalog(snapshot, runtime)
    compliance = audit_release_assurance_compliance(snapshot, runtime=runtime)
    performance = audit_release_assurance_performance(snapshot, runtime=runtime)
    operations = build_release_assurance_operations(snapshot, runtime)
    components = (
        ("runtime", runtime.content_address, runtime.accepted),
        ("reconciliation", reconciliation.content_address, reconciliation.accepted),
        ("catalog", catalog.content_address, catalog.accepted),
        ("compliance", compliance.content_address, compliance.accepted),
        ("performance", performance.content_address, performance.accepted),
        ("operations", operations.content_address, operations.accepted),
    )
    accepted = runtime.accepted and all(item[2] for item in components)
    body = {
        "bundle_id": snapshot.bundle_id,
        "run_id": runtime.run_id,
        "snapshot_address": snapshot.content_address,
        "component_addresses": components,
        "accepted": accepted,
    }
    return ReleaseAssuranceCheckpoint(
        snapshot.bundle_id,
        runtime.run_id,
        snapshot.content_address,
        components,
        accepted,
        content_hash(body, prefix="release-assurance-checkpoint"),
    )


def audit_release_assurance_checkpoint(
    checkpoint: ReleaseAssuranceCheckpoint,
    runtime: ReleaseAssuranceRuntimeReport,
) -> tuple:
    """Audit component cardinality, address presence, and checkpoint identity."""

    component_addresses = tuple(item[1] for item in checkpoint.component_addresses)
    body = {
        "bundle_id": checkpoint.bundle_id,
        "run_id": checkpoint.run_id,
        "snapshot_address": checkpoint.snapshot_address,
        "component_addresses": checkpoint.component_addresses,
        "accepted": checkpoint.accepted,
    }
    expected_address = content_hash(body, prefix="release-assurance-checkpoint")
    return (
        check("checkpoint:bundle", "checkpoint", ReleaseAssurancePlane.RUNTIME,
              checkpoint.bundle_id == runtime.snapshot.bundle_id,
              checkpoint.bundle_id, runtime.snapshot.bundle_id, "checkpoint bundle matches runtime"),
        check("checkpoint:run", "checkpoint", ReleaseAssurancePlane.RUNTIME,
              checkpoint.run_id == runtime.run_id, checkpoint.run_id, runtime.run_id,
              "checkpoint run matches runtime"),
        check("checkpoint:source", "checkpoint", ReleaseAssurancePlane.CROSS_PLANE,
              checkpoint.snapshot_address == runtime.snapshot.content_address,
              checkpoint.snapshot_address, runtime.snapshot.content_address,
              "checkpoint retains the snapshot address"),
        check("checkpoint:components", "checkpoint", ReleaseAssurancePlane.RUNTIME,
              checkpoint.component_count == 6, checkpoint.component_count, 6,
              "checkpoint closes six deep component projections"),
        check("checkpoint:addresses", "checkpoint", ReleaseAssurancePlane.PUBLIC_BOUNDARY,
              all(component_addresses) and len(component_addresses) == len(set(component_addresses)),
              len(set(component_addresses)), len(component_addresses),
              "component addresses are present and unique"),
        check("checkpoint:accepted", "checkpoint", ReleaseAssurancePlane.RUNTIME,
              checkpoint.accepted == all(item[2] for item in checkpoint.component_addresses),
              checkpoint.accepted, all(item[2] for item in checkpoint.component_addresses),
              "checkpoint acceptance follows component acceptance"),
        check("checkpoint:address", "checkpoint", ReleaseAssurancePlane.PUBLIC_BOUNDARY,
              checkpoint.content_address == expected_address,
              checkpoint.content_address, expected_address, "checkpoint address is reproducible"),
    )


__all__ = ["audit_release_assurance_checkpoint", "build_release_assurance_checkpoint"]
