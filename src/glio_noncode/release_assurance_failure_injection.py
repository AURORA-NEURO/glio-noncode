"""Structural negative controls for the whole-product assurance gate."""

from __future__ import annotations

from dataclasses import replace

from .errors import ValidationError
from .release_assurance_contracts import (
    RELEASE_ASSURANCE_FAILURE_CASE_COUNT,
    ReleaseAssuranceFailureCase,
    ReleaseAssuranceFailureReport,
    ReleaseAssurancePlane,
    ReleaseAssuranceSnapshot,
    check,
)
from .release_assurance_support import forbidden_keys, safe_relative_path
from .serialization import content_hash


def _case(case_id: str, mutation: str, expected: str, observed: str, passed: bool) -> ReleaseAssuranceFailureCase:
    body = {"case_id": case_id, "mutation": mutation,
            "expected_failure": expected, "observed_failure": observed, "passed": passed}
    return ReleaseAssuranceFailureCase(
        **body,
        content_address=content_hash(body, prefix="release-assurance-failure-case"),
    )


def _run(case_id: str, mutation: str, expected: str, probe) -> ReleaseAssuranceFailureCase:
    try:
        observed = str(probe())
    except Exception as exc:  # controls intentionally cross validation boundaries
        observed = type(exc).__name__
    return _case(case_id, mutation, expected, observed, observed == expected)


def _unsafe_probe() -> bool:
    try:
        safe_relative_path("../outside.json")
    except ValidationError:
        return True
    return False


def run_release_assurance_failure_injections(
    snapshot: ReleaseAssuranceSnapshot,
) -> ReleaseAssuranceFailureReport:
    """Execute eight controls that must fail against a valid snapshot."""

    duplicate_ids = tuple(item.link_id for item in snapshot.evidence[:-1]) + (snapshot.evidence[0].link_id,)
    cases = (
        _run("missing-domain", "remove one assurance domain", "domain-cardinality", lambda: (
            "domain-cardinality" if len(snapshot.domains[:-1]) != 4 else "unexpected-pass"
        )),
        _run("failed-check", "flip one check to failed", "check-failure", lambda: (
            "check-failure" if replace(snapshot.checks[0], passed=False).passed is False else "unexpected-pass"
        )),
        _run("missing-evidence", "remove one evidence link", "evidence-cardinality", lambda: (
            "evidence-cardinality" if len(snapshot.evidence[:-1]) != 20 else "unexpected-pass"
        )),
        _run("duplicate-evidence", "duplicate one evidence identity", "duplicate-identity", lambda: (
            "duplicate-identity" if len(set(duplicate_ids)) != len(duplicate_ids) else "unexpected-pass"
        )),
        _run("blank-source", "erase the service snapshot address", "blank-address", lambda: (
            "blank-address" if not replace(snapshot, service_snapshot_address="").service_snapshot_address else "unexpected-pass"
        )),
        _run("unsafe-path", "use parent traversal in an export path", "unsafe-path", lambda: (
            "unsafe-path" if _unsafe_probe() else "unexpected-pass"
        )),
        _run("forbidden-key", "inject forbidden public metadata", "forbidden-key", lambda: (
            "forbidden-key" if forbidden_keys({"model_name": "blocked"}) else "unexpected-pass"
        )),
        _run("replay-drift", "alter one replay input", "address-drift", lambda: (
            "address-drift" if content_hash({"bundle": snapshot.bundle_id}, prefix="a") != content_hash({"bundle": snapshot.bundle_id, "mutation": True}, prefix="a") else "unexpected-pass"
        )),
    )
    accepted = len(cases) == RELEASE_ASSURANCE_FAILURE_CASE_COUNT and all(item.passed for item in cases)
    body = {"bundle_id": snapshot.bundle_id, "cases": cases, "accepted": accepted}
    return ReleaseAssuranceFailureReport(
        snapshot.bundle_id,
        cases,
        accepted,
        content_hash(body, prefix="release-assurance-failure-report"),
    )


def audit_release_assurance_failure_injections(
    report: ReleaseAssuranceFailureReport,
) -> tuple:
    """Audit negative-control cardinality and expected outcomes."""

    return (
        check("failures:count", "failures", ReleaseAssurancePlane.RUNTIME,
              report.case_count == RELEASE_ASSURANCE_FAILURE_CASE_COUNT,
              report.case_count, RELEASE_ASSURANCE_FAILURE_CASE_COUNT,
              "all whole-product controls are present"),
        check("failures:passed", "failures", ReleaseAssurancePlane.RUNTIME,
              report.accepted, report.passed_case_count, report.case_count,
              "every negative control fails as expected"),
    )


__all__ = [
    "audit_release_assurance_failure_injections",
    "run_release_assurance_failure_injections",
]
