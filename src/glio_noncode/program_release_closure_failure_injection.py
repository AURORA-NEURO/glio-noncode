"""Negative controls for the aggregate release closure."""

from __future__ import annotations

from dataclasses import replace

from .program_release_closure_boundary import audit_program_release_closure_boundary
from .program_release_closure_contracts import (
    ProgramReleaseFailureCase,
    ProgramReleaseFailureReport,
    ProgramReleaseSnapshot,
)
from .program_release_closure_support import forbidden_keys
from .serialization import content_hash, jsonable


def _case(
    case_id: str, target: str, mutation: str, expected: bool, observed: bool, detail: str
) -> ProgramReleaseFailureCase:
    body = {
        "case_id": case_id,
        "target": target,
        "mutation": mutation,
        "expected_rejection": expected,
        "observed_rejection": observed,
        "accepted": expected == observed,
        "detail": detail,
    }
    return ProgramReleaseFailureCase(
        **body, content_address=content_hash(body, prefix="program-release-failure-case")
    )


def _boundary_rejects(value: ProgramReleaseSnapshot) -> bool:
    return not all(item.passed for item in audit_program_release_closure_boundary(value))


def _mutated(snapshot: ProgramReleaseSnapshot, case_id: str) -> tuple[bool, str]:
    if case_id == "missing-domain":
        return _boundary_rejects(replace(snapshot, domains=snapshot.domains[:-1])), "remove D16"
    if case_id == "duplicate-domain":
        return _boundary_rejects(
            replace(snapshot, domains=snapshot.domains[:-1] + (snapshot.domains[-2],))
        ), "duplicate D15"
    if case_id == "missing-artifact":
        return _boundary_rejects(
            replace(snapshot, artifacts=snapshot.artifacts[:-1])
        ), "remove one portable artifact"
    if case_id == "duplicate-artifact":
        return _boundary_rejects(
            replace(snapshot, artifacts=snapshot.artifacts[:-1] + (snapshot.artifacts[-2],))
        ), "duplicate one artifact"
    if case_id == "unsafe-path":
        artifact = replace(snapshot.artifacts[0], relative_path="../unsafe.json")
        return _boundary_rejects(
            replace(snapshot, artifacts=(artifact,) + snapshot.artifacts[1:])
        ), "insert traversal path"
    if case_id == "failed-gate":
        gate = replace(snapshot.gates[0], passed=False)
        return _boundary_rejects(
            replace(snapshot, gates=(gate,) + snapshot.gates[1:])
        ), "fail D01 bundle gate"
    if case_id == "dependency-cycle":
        dependency = replace(snapshot.dependencies[0], source_order=2, target_order=1)
        return _boundary_rejects(
            replace(snapshot, dependencies=(dependency,) + snapshot.dependencies[1:])
        ), "reverse the first dependency"
    if case_id == "forbidden-key":
        value = jsonable(snapshot) | {"agent": "forbidden"}
        return bool(forbidden_keys(value)), "insert prohibited public metadata key"
    if case_id == "missing-address":
        domain = replace(snapshot.domains[0], content_address="")
        return _boundary_rejects(
            replace(snapshot, domains=(domain,) + snapshot.domains[1:])
        ), "remove a domain receipt address"
    if case_id == "missing-source-address":
        artifact = replace(snapshot.artifacts[0], source_address="")
        return _boundary_rejects(
            replace(snapshot, artifacts=(artifact,) + snapshot.artifacts[1:])
        ), "remove a source artifact address"
    if case_id == "gate-partition":
        return _boundary_rejects(
            replace(snapshot, gates=snapshot.gates[:-1])
        ), "remove one gate from the partition"
    if case_id == "replay-nondeterminism":
        changed = replace(snapshot, content_address=snapshot.content_address + "-changed")
        return changed.content_address != snapshot.content_address, "change replay address"
    raise KeyError(case_id)


def run_program_release_failure_injections(
    snapshot: ProgramReleaseSnapshot,
) -> ProgramReleaseFailureReport:
    cases: list[ProgramReleaseFailureCase] = []
    specifications = (
        ("missing-domain", "domains"),
        ("duplicate-domain", "domains"),
        ("missing-artifact", "artifacts"),
        ("duplicate-artifact", "artifacts"),
        ("unsafe-path", "artifacts"),
        ("failed-gate", "gates"),
        ("dependency-cycle", "dependencies"),
        ("forbidden-key", "boundary"),
        ("missing-address", "domains"),
        ("missing-source-address", "artifacts"),
        ("gate-partition", "gates"),
        ("replay-nondeterminism", "replay"),
    )
    for case_id, target in specifications:
        observed, mutation = _mutated(snapshot, case_id)
        cases.append(
            _case(
                case_id,
                target,
                mutation,
                True,
                observed,
                "negative control must reject the mutation",
            )
        )
    accepted = all(item.accepted for item in cases)
    body = {"bundle_id": snapshot.bundle_id, "cases": tuple(cases), "accepted": accepted}
    return ProgramReleaseFailureReport(
        snapshot.bundle_id,
        tuple(cases),
        accepted,
        content_hash(body, prefix="program-release-failure-report"),
    )


def audit_program_release_failure_injections(
    report: ProgramReleaseFailureReport,
) -> dict[str, object]:
    checks = {
        "accepted": report.accepted,
        "case_count": len(report.cases) == 12,
        "case_ids_unique": len({item.case_id for item in report.cases}) == len(report.cases),
        "all_expected_rejections": all(
            item.expected_rejection and item.observed_rejection for item in report.cases
        ),
    }
    body = {"bundle_id": report.bundle_id, "checks": checks, "accepted": all(checks.values())}
    body["content_address"] = content_hash(body, prefix="program-release-failure-audit")
    return body


__all__ = [
    name
    for name in globals()
    if name.startswith("run_program_release")
    or name.startswith("audit_program_release")
    or name.startswith("ProgramRelease")
]
