"""D12 operation and stage runbook projections."""

from __future__ import annotations

from .cohort_architecture_contracts import CohortArchitectureFixture


def cohort_architecture_runbook(
    fixture: CohortArchitectureFixture,
) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "ordinal": item.ordinal,
            "operation_id": item.operation_id,
            "operation": item.operation.value,
            "delegate_operation": item.delegate_operation,
            "family": item.family.value,
            "plane": item.plane.value,
            "dependencies": item.dependencies,
            "source_count": len(item.source_ids),
            "control_policy": item.control_policy,
        }
        for item in fixture.operations
    )


def cohort_architecture_stage_runbook() -> tuple[dict[str, object], ...]:
    names = (
        "fixture-loaded",
        "sources-audited",
        "schema-validated",
        "plan-compiled",
        "foundation-family-ready",
        "beta-family-ready",
        "alpha-family-ready",
        "frontier-family-ready",
        "cases-executed",
        "review-routed",
        "lineage-linked",
        "ledger-closed",
        "metrics-materialized",
        "replay-closed",
        "artifacts-materialized",
        "bundle-closed",
        "release-built",
        "quality-gated",
        "depth-accounted",
        "runtime-finalized",
        "controls-closed",
        "observability-closed",
    )
    return tuple(
        {"ordinal": index, "stage_id": name, "state": "accepted"}
        for index, name in enumerate(names, start=1)
    )


def cohort_architecture_module_inventory() -> tuple[str, ...]:
    return (
        "contracts",
        "public_data",
        "operations",
        "plan",
        "review",
        "lineage",
        "ledger",
        "metrics",
        "artifacts",
        "release",
        "replay",
        "depth",
        "quality",
        "runtime",
        "schema",
        "compliance",
        "contract_matrix",
        "controls",
        "query",
        "views",
        "reporting",
        "runbook",
        "data_dictionary",
        "audit",
        "exports",
    )


__all__ = [
    "cohort_architecture_module_inventory",
    "cohort_architecture_runbook",
    "cohort_architecture_stage_runbook",
]
