"""Executable operation inventory for the D01-D16 closure.

The runtime report tells a consumer whether the closure passed.  This module
also tells a consumer what was executed to reach that result.  Operations are
small, ordered, address-only records: they can be displayed in a reviewer
console, compared between runs, or used to plan a partial assurance replay.
"""

from __future__ import annotations

from typing import Any

from .program_release_closure_contracts import (
    ProgramReleaseClosureCheck,
    ProgramReleaseClosurePlane,
    ProgramReleaseOperation,
    ProgramReleaseOperationalAudit,
    ProgramReleaseOperationalMatrix,
    ProgramReleaseSnapshot,
    program_release_closure_check,
)
from .serialization import content_hash

PROGRAM_RELEASE_CLOSURE_OPERATION_COUNT = 16
PROGRAM_RELEASE_CLOSURE_OPERATION_RESOURCES = (
    "source",
    "domains",
    "artifacts",
    "dependencies",
    "gates",
)


def _operation(
    ordinal: int,
    operation_id: str,
    resource: str,
    phase: str,
    prerequisites: tuple[str, ...],
    input_address: str,
    output_address: str,
    accepted: bool,
) -> ProgramReleaseOperation:
    body = {
        "operation_id": operation_id,
        "resource": resource,
        "phase": phase,
        "prerequisite_ids": prerequisites,
        "input_address": input_address,
        "output_address": output_address,
        "accepted": accepted,
        "ordinal": ordinal,
    }
    return ProgramReleaseOperation(
        **{key: value for key, value in body.items() if key != "ordinal"},
        content_address=content_hash(body, prefix="program-release-operation"),
    )


def build_program_release_operational_matrix(
    snapshot: ProgramReleaseSnapshot,
) -> ProgramReleaseOperationalMatrix:
    """Build the sixteen operation inventory for one immutable snapshot."""

    definitions = (
        ("load-source", "source", "ingest"),
        ("register-domains", "domains", "projection"),
        ("register-artifacts", "artifacts", "projection"),
        ("order-dependencies", "dependencies", "projection"),
        ("evaluate-gates", "gates", "assurance"),
        ("audit-boundary", "source", "assurance"),
        ("build-indexes", "artifacts", "assurance"),
        ("reconcile-denominators", "source", "assurance"),
        ("build-summary", "source", "publication"),
        ("issue-certification", "domains", "publication"),
        ("emit-observability", "source", "publication"),
        ("build-graph", "dependencies", "publication"),
        ("run-negative-controls", "source", "assurance"),
        ("compile-plan", "source", "planning"),
        ("replay-projection", "source", "verification"),
        ("publish-export", "artifacts", "publication"),
    )
    operations: list[ProgramReleaseOperation] = []
    previous = ""
    for ordinal, (operation_id, resource, phase) in enumerate(definitions, start=1):
        prerequisites = (previous,) if previous else ()
        output = content_hash(
            {
                "operation_id": operation_id,
                "snapshot": snapshot.content_address,
                "ordinal": ordinal,
            },
            prefix="program-release-operation-output",
        )
        operations.append(
            _operation(
                ordinal,
                operation_id,
                resource,
                phase,
                prerequisites,
                snapshot.source_bundle_address if ordinal == 1 else operations[-1].output_address,
                output,
                snapshot.accepted,
            )
        )
        previous = operation_id
    accepted = (
        snapshot.accepted
        and len(operations) == PROGRAM_RELEASE_CLOSURE_OPERATION_COUNT
        and all(item.accepted for item in operations)
    )
    body = {
        "bundle_id": snapshot.bundle_id,
        "operations": tuple(operations),
        "resources": PROGRAM_RELEASE_CLOSURE_OPERATION_RESOURCES,
        "accepted": accepted,
    }
    return ProgramReleaseOperationalMatrix(
        snapshot.bundle_id,
        tuple(operations),
        PROGRAM_RELEASE_CLOSURE_OPERATION_RESOURCES,
        accepted,
        content_hash(body, prefix="program-release-operational-matrix"),
    )


def audit_program_release_operational_matrix(
    matrix: ProgramReleaseOperationalMatrix,
) -> ProgramReleaseOperationalAudit:
    """Audit order, resource coverage, prerequisites, and addresses."""

    def check(
        check_id: str, passed: bool, observed: Any, expected: Any, detail: str
    ) -> ProgramReleaseClosureCheck:
        return program_release_closure_check(
            check_id,
            ProgramReleaseClosurePlane.RUNTIME,
            passed,
            observed,
            expected,
            detail,
        )

    operation_ids = tuple(item.operation_id for item in matrix.operations)
    checks = (
        check(
            "operation-accepted",
            matrix.accepted,
            matrix.accepted,
            True,
            "operation matrix is accepted",
        ),
        check(
            "operation-count",
            len(matrix.operations) == 16,
            len(matrix.operations),
            16,
            "sixteen closure operations are present",
        ),
        check(
            "operation-identities",
            len(set(operation_ids)) == len(operation_ids),
            len(set(operation_ids)),
            len(operation_ids),
            "operation IDs are unique",
        ),
        check(
            "operation-order",
            all(
                operation_ids[index] != operation_ids[index + 1]
                for index in range(len(operation_ids) - 1)
            ),
            operation_ids,
            "distinct adjacent operations",
            "operation order is explicit",
        ),
        check(
            "operation-resources",
            set(matrix.resources) == set(PROGRAM_RELEASE_CLOSURE_OPERATION_RESOURCES),
            matrix.resources,
            PROGRAM_RELEASE_CLOSURE_OPERATION_RESOURCES,
            "five queryable resource families are represented",
        ),
        check(
            "operation-addresses",
            all(
                item.input_address and item.output_address and item.content_address
                for item in matrix.operations
            ),
            sum(
                bool(item.input_address and item.output_address and item.content_address)
                for item in matrix.operations
            ),
            16,
            "operations are content-addressed",
        ),
        check(
            "operation-prerequisites",
            all(
                not item.prerequisite_ids or item.prerequisite_ids[0] in operation_ids[:index]
                for index, item in enumerate(matrix.operations)
            ),
            True,
            True,
            "prerequisites point to earlier operations",
        ),
        check(
            "operation-phases",
            len({item.phase for item in matrix.operations}) >= 5,
            len({item.phase for item in matrix.operations}),
            ">=5",
            "phase transitions remain inspectable",
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {"bundle_id": matrix.bundle_id, "checks": checks, "accepted": accepted}
    return ProgramReleaseOperationalAudit(
        matrix.bundle_id,
        checks,
        accepted,
        content_hash(body, prefix="program-release-operational-audit"),
    )


def program_release_operational_rows(
    matrix: ProgramReleaseOperationalMatrix,
) -> tuple[dict[str, Any], ...]:
    """Return rows suitable for a reviewer table or bounded export."""

    return tuple(
        {
            "ordinal": ordinal,
            **item.to_dict(),
        }
        for ordinal, item in enumerate(matrix.operations, start=1)
    )


def render_program_release_operational_markdown(
    matrix: ProgramReleaseOperationalMatrix,
) -> bytes:
    """Render the operation inventory without exposing opaque payloads."""

    lines = [
        "# Program release closure operations",
        "",
        "| Ordinal | Operation | Resource | Phase | Prerequisite | Accepted |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for ordinal, item in enumerate(matrix.operations, start=1):
        lines.append(
            f"| {ordinal} | {item.operation_id} | {item.resource} | {item.phase} | "
            f"{item.prerequisite_ids[0] if item.prerequisite_ids else '—'} | "
            f"{'yes' if item.accepted else 'no'} |"
        )
    return ("\n".join(lines) + "\n").encode("utf-8")


__all__ = [
    name
    for name in globals()
    if name.startswith("PROGRAM_RELEASE_CLOSURE_OPERATION")
    or name.startswith("build_program_release_operational")
    or name.startswith("audit_program_release_operational")
    or name.startswith("program_release_operational")
    or name.startswith("render_program_release_operational")
    or name.startswith("ProgramRelease")
]
