"""Boundary validation for the public D01-D16 release projection."""

from __future__ import annotations

from typing import Any

from .program_release_closure_contracts import (
    PROGRAM_RELEASE_CLOSURE_ARTIFACT_COUNT,
    PROGRAM_RELEASE_CLOSURE_ARTIFACT_PREFIX,
    PROGRAM_RELEASE_CLOSURE_BOUNDARY,
    PROGRAM_RELEASE_CLOSURE_DEPENDENCY_COUNT,
    PROGRAM_RELEASE_CLOSURE_DOMAIN_COUNT,
    PROGRAM_RELEASE_CLOSURE_DOMAIN_IDS,
    PROGRAM_RELEASE_CLOSURE_GATE_COUNT,
    ProgramReleaseClosureCheck,
    ProgramReleaseClosurePlane,
    ProgramReleaseSnapshot,
    program_release_closure_check,
)
from .program_release_closure_support import forbidden_keys, safe_relative_path
from .serialization import jsonable


def _check(
    check_id: str, passed: bool, observed: Any, expected: Any, detail: str
) -> ProgramReleaseClosureCheck:
    return program_release_closure_check(
        check_id, ProgramReleaseClosurePlane.BOUNDARY, passed, observed, expected, detail
    )


def audit_program_release_closure_boundary(
    snapshot: ProgramReleaseSnapshot,
) -> tuple[ProgramReleaseClosureCheck, ...]:
    """Return independent boundary receipts; no receipt mutates the snapshot."""

    checks: list[ProgramReleaseClosureCheck] = [
        _check(
            "boundary-name",
            snapshot.boundary == PROGRAM_RELEASE_CLOSURE_BOUNDARY,
            snapshot.boundary,
            PROGRAM_RELEASE_CLOSURE_BOUNDARY,
            "public aggregate boundary is stable",
        ),
        _check(
            "snapshot-accepted",
            snapshot.accepted,
            snapshot.accepted,
            True,
            "aggregate snapshot is accepted",
        ),
        _check(
            "domain-count",
            len(snapshot.domains) == PROGRAM_RELEASE_CLOSURE_DOMAIN_COUNT,
            len(snapshot.domains),
            PROGRAM_RELEASE_CLOSURE_DOMAIN_COUNT,
            "all sixteen domains are represented",
        ),
        _check(
            "domain-order",
            tuple(item.domain_id for item in snapshot.domains)
            == PROGRAM_RELEASE_CLOSURE_DOMAIN_IDS,
            tuple(item.domain_id for item in snapshot.domains),
            PROGRAM_RELEASE_CLOSURE_DOMAIN_IDS,
            "domain order is deterministic",
        ),
        _check(
            "domain-identities",
            len({item.domain_id for item in snapshot.domains}) == len(snapshot.domains),
            len({item.domain_id for item in snapshot.domains}),
            len(snapshot.domains),
            "domain identities are unique",
        ),
        _check(
            "domain-addresses",
            all(item.content_address for item in snapshot.domains),
            sum(bool(item.content_address) for item in snapshot.domains),
            len(snapshot.domains),
            "domain receipts are addressed",
        ),
        _check(
            "artifact-count",
            len(snapshot.artifacts) == PROGRAM_RELEASE_CLOSURE_ARTIFACT_COUNT,
            len(snapshot.artifacts),
            PROGRAM_RELEASE_CLOSURE_ARTIFACT_COUNT,
            "portable source artifacts are conserved",
        ),
        _check(
            "artifact-identities",
            len({item.artifact_ref for item in snapshot.artifacts}) == len(snapshot.artifacts),
            len({item.artifact_ref for item in snapshot.artifacts}),
            len(snapshot.artifacts),
            "artifact references are unique",
        ),
        _check(
            "artifact-addresses",
            all(
                item.content_address.startswith(f"{PROGRAM_RELEASE_CLOSURE_ARTIFACT_PREFIX}:")
                for item in snapshot.artifacts
            ),
            sum(
                item.content_address.startswith(f"{PROGRAM_RELEASE_CLOSURE_ARTIFACT_PREFIX}:")
                for item in snapshot.artifacts
            ),
            len(snapshot.artifacts),
            "artifact projections are addressed",
        ),
        _check(
            "artifact-source-addresses",
            all(item.source_address for item in snapshot.artifacts),
            sum(bool(item.source_address) for item in snapshot.artifacts),
            len(snapshot.artifacts),
            "source artifact addresses are retained",
        ),
        _check(
            "artifact-paths",
            len({item.relative_path for item in snapshot.artifacts}) == len(snapshot.artifacts),
            len({item.relative_path for item in snapshot.artifacts}),
            len(snapshot.artifacts),
            "artifact paths are unique",
        ),
        _check(
            "artifact-path-safety",
            _safe_paths(snapshot),
            True,
            True,
            "artifact paths are relative and traversal-free",
        ),
        _check(
            "dependency-count",
            len(snapshot.dependencies) == PROGRAM_RELEASE_CLOSURE_DEPENDENCY_COUNT,
            len(snapshot.dependencies),
            PROGRAM_RELEASE_CLOSURE_DEPENDENCY_COUNT,
            "complete ordered dependency matrix is conserved",
        ),
        _check(
            "dependency-direction",
            all(item.source_order < item.target_order for item in snapshot.dependencies),
            sum(item.source_order < item.target_order for item in snapshot.dependencies),
            len(snapshot.dependencies),
            "dependency edges form a forward DAG",
        ),
        _check(
            "dependency-identities",
            len({item.dependency_id for item in snapshot.dependencies})
            == len(snapshot.dependencies),
            len({item.dependency_id for item in snapshot.dependencies}),
            len(snapshot.dependencies),
            "dependency identities are unique",
        ),
        _check(
            "gate-count",
            len(snapshot.gates) == PROGRAM_RELEASE_CLOSURE_GATE_COUNT,
            len(snapshot.gates),
            PROGRAM_RELEASE_CLOSURE_GATE_COUNT,
            "six gates exist for each domain",
        ),
        _check(
            "gate-identities",
            len({item.gate_id for item in snapshot.gates}) == len(snapshot.gates),
            len({item.gate_id for item in snapshot.gates}),
            len(snapshot.gates),
            "gate identities are unique",
        ),
        _check(
            "gate-partition",
            len({item.domain_id for item in snapshot.gates})
            == PROGRAM_RELEASE_CLOSURE_DOMAIN_COUNT,
            len({item.domain_id for item in snapshot.gates}),
            PROGRAM_RELEASE_CLOSURE_DOMAIN_COUNT,
            "gates cover every domain",
        ),
        _check(
            "gate-results",
            all(item.passed for item in snapshot.gates),
            sum(item.passed for item in snapshot.gates),
            len(snapshot.gates),
            "every release gate passes",
        ),
        _check(
            "public-key-policy",
            not forbidden_keys(jsonable(snapshot)),
            forbidden_keys(jsonable(snapshot)),
            (),
            "public aggregate projections contain no prohibited metadata keys",
        ),
    ]
    return tuple(checks)


def _safe_paths(snapshot: ProgramReleaseSnapshot) -> bool:
    try:
        return all(
            safe_relative_path(item.relative_path) == item.relative_path
            for item in snapshot.artifacts
        )
    except Exception:
        return False


def validate_program_release_closure_boundary(snapshot: ProgramReleaseSnapshot) -> dict[str, Any]:
    """Serialize a compact public boundary report for API and CLI consumers."""

    checks = audit_program_release_closure_boundary(snapshot)
    body = {
        "boundary": PROGRAM_RELEASE_CLOSURE_BOUNDARY,
        "bundle_id": snapshot.bundle_id,
        "accepted": all(item.passed for item in checks),
        "checks": checks,
    }
    from .serialization import content_hash

    body["content_address"] = content_hash(body, prefix="program-release-boundary-report")
    return jsonable(body)


__all__ = [
    name
    for name in globals()
    if name.startswith("PROGRAM_RELEASE")
    or name.startswith("audit_program_release")
    or name.startswith("validate_program_release")
    or name.startswith("ProgramRelease")
]
