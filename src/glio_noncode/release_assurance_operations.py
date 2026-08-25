"""Deterministic operator projection for whole-product release assurance."""

from __future__ import annotations

from .release_assurance_contracts import (
    ReleaseAssuranceOperation,
    ReleaseAssuranceOperations,
    ReleaseAssurancePlane,
    ReleaseAssuranceRuntimeReport,
    ReleaseAssuranceSnapshot,
    ReleaseAssuranceState,
    check,
)
from .serialization import content_hash


def _operation(
    operation_id: str,
    operation_type: str,
    priority: int,
    state: ReleaseAssuranceState,
    topic: str,
    source_address: str,
    action: str,
    accepted: bool,
) -> ReleaseAssuranceOperation:
    body = {
        "operation_id": operation_id,
        "operation_type": operation_type,
        "priority": priority,
        "state": state,
        "topic": topic,
        "source_address": source_address,
        "action": action,
        "accepted": accepted,
    }
    return ReleaseAssuranceOperation(
        **body,
        content_address=content_hash(body, prefix="release-assurance-operation"),
    )


def build_release_assurance_operations(
    snapshot: ReleaseAssuranceSnapshot,
    runtime: ReleaseAssuranceRuntimeReport | None = None,
) -> ReleaseAssuranceOperations:
    """Build an address-only queue from checks, stages, and negative controls."""

    operations: list[ReleaseAssuranceOperation] = []
    for ordinal, item in enumerate(snapshot.checks, start=1):
        state = ReleaseAssuranceState.READY if item.passed else ReleaseAssuranceState.BLOCKED
        operations.append(_operation(
            f"check:{ordinal:03d}:{item.check_id}",
            "check",
            10 if not item.passed else 50,
            state,
            item.check_id,
            item.content_address,
            "review failed check" if not item.passed else "retain passed check evidence",
            item.passed,
        ))
    if runtime is not None:
        for item in runtime.stages:
            operations.append(_operation(
                f"stage:{item.ordinal:02d}:{item.stage_id}",
                "stage",
                5 if item.state is ReleaseAssuranceState.BLOCKED else 60,
                item.state,
                item.stage_id,
                item.content_address,
                "repair blocked runtime stage" if item.state is ReleaseAssuranceState.BLOCKED else "record ready runtime stage",
                item.state is ReleaseAssuranceState.READY,
            ))
        for item in runtime.failures.cases:
            operations.append(_operation(
                f"control:{item.case_id}",
                "negative-control",
                30 if not item.passed else 70,
                ReleaseAssuranceState.READY if item.passed else ReleaseAssuranceState.BLOCKED,
                item.case_id,
                item.content_address,
                "repair failed negative control" if not item.passed else "retain fail-closed control",
                item.passed,
            ))
    operations.sort(key=lambda item: (item.priority, item.operation_id))
    accepted = snapshot.accepted and all(item.accepted for item in operations)
    body = {"bundle_id": snapshot.bundle_id, "operations": operations, "accepted": accepted}
    return ReleaseAssuranceOperations(
        snapshot.bundle_id,
        tuple(operations),
        accepted,
        content_hash(body, prefix="release-assurance-operations"),
    )


def audit_release_assurance_operations(
    operations: ReleaseAssuranceOperations,
    snapshot: ReleaseAssuranceSnapshot,
) -> tuple:
    """Audit queue ordering, identity uniqueness, and source addresses."""

    ids = tuple(item.operation_id for item in operations.operations)
    return (
        check("operations:non-empty", "operations", ReleaseAssurancePlane.RUNTIME,
              bool(ids), len(ids), ">0", "operator queue has actionable rows"),
        check("operations:identities", "operations", ReleaseAssurancePlane.RUNTIME,
              len(ids) == len(set(ids)), len(ids), len(set(ids)), "operation identifiers are unique"),
        check("operations:ordering", "operations", ReleaseAssurancePlane.RUNTIME,
              tuple((item.priority, item.operation_id) for item in operations.operations)
              == tuple(sorted((item.priority, item.operation_id) for item in operations.operations)),
              tuple(item.operation_id for item in operations.operations[:3]), "priority order", "operator rows are sorted"),
        check("operations:addresses", "operations", ReleaseAssurancePlane.PUBLIC_BOUNDARY,
              all(item.source_address for item in operations.operations),
              sum(bool(item.source_address) for item in operations.operations), len(operations.operations),
              "every operation retains a source address"),
        check("operations:bundle", "operations", ReleaseAssurancePlane.RUNTIME,
              operations.bundle_id == snapshot.bundle_id, operations.bundle_id, snapshot.bundle_id,
              "operation bundle matches snapshot"),
        check("operations:accepted", "operations", ReleaseAssurancePlane.RUNTIME,
              operations.accepted == all(item.accepted for item in operations.operations),
              operations.accepted, all(item.accepted for item in operations.operations),
              "queue acceptance follows operation acceptance"),
    )


__all__ = ["audit_release_assurance_operations", "build_release_assurance_operations"]
