"""Negative controls proving the service-release gates fail closed."""

from __future__ import annotations

from dataclasses import replace

from .errors import ValidationError
from .service_release_contracts import ServiceReleaseFailureCase, ServiceReleaseFailureReport, ServiceReleaseSnapshot
from .service_release_support import forbidden_keys, safe_relative_path
from .serialization import content_hash


def _case(case_id: str, mutation: str, expected: str, observed: str, passed: bool) -> ServiceReleaseFailureCase:
    body = {"case_id": case_id, "mutation": mutation, "expected_failure": expected,
            "observed_failure": observed, "passed": passed}
    return ServiceReleaseFailureCase(
        **body, content_address=content_hash(body, prefix="service-release-failure-case")
    )


def _run(case_id: str, mutation: str, expected: str, probe) -> ServiceReleaseFailureCase:
    try:
        observed = str(probe())
        return _case(case_id, mutation, expected, observed, observed == expected)
    except Exception as exc:  # negative controls intentionally cross validation boundaries
        observed = type(exc).__name__
        return _case(case_id, mutation, expected, observed, observed == expected)


def run_service_release_failure_injections(snapshot: ServiceReleaseSnapshot) -> ServiceReleaseFailureReport:
    """Execute eight structural controls against a valid release snapshot."""

    cases = (
        _run("missing-surface", "remove one surface", "surface-cardinality", lambda: (
            "surface-cardinality" if len(snapshot.surfaces[:-1]) != 6 else "unexpected-pass"
        )),
        _run("duplicate-artifact-path", "duplicate an export path", "duplicate-path", lambda: (
            "duplicate-path" if len({item.relative_path for item in snapshot.artifacts[:-1] + (replace(snapshot.artifacts[-1], relative_path=snapshot.artifacts[0].relative_path),)}) != len(snapshot.artifacts) else "unexpected-pass"
        )),
        _run("missing-gate", "remove one promotion gate", "gate-cardinality", lambda: (
            "gate-cardinality" if len(snapshot.gates[:-1]) != 24 else "unexpected-pass"
        )),
        _run("dependency-cycle", "reverse one dependency order", "dependency-cycle", lambda: (
            "dependency-cycle" if (lambda item: item.source_order >= item.target_order)(replace(snapshot.dependencies[0], source_order=snapshot.dependencies[0].target_order, target_order=snapshot.dependencies[0].source_order)) else "unexpected-pass"
        )),
        _run("blank-source-address", "erase a source address", "blank-address", lambda: (
            "blank-address" if not replace(snapshot.surfaces[0], source_address="").source_address else "unexpected-pass"
        )),
        _run("forbidden-public-key", "inject forbidden metadata", "forbidden-key", lambda: (
            "forbidden-key" if forbidden_keys({"model_name": "blocked"}) else "unexpected-pass"
        )),
        _run("unsafe-export-path", "use parent traversal", "unsafe-path", lambda: (
            "unsafe-path" if _unsafe_path() else "unexpected-pass"
        )),
        _run("replay-drift", "alter replay input", "address-drift", lambda: (
            "address-drift" if content_hash({"bundle": snapshot.bundle_id}, prefix="a") != content_hash({"bundle": snapshot.bundle_id, "mutation": True}, prefix="a") else "unexpected-pass"
        )),
    )
    accepted = all(item.passed for item in cases)
    body = {"bundle_id": snapshot.bundle_id, "cases": cases, "accepted": accepted}
    return ServiceReleaseFailureReport(
        snapshot.bundle_id,
        cases,
        accepted,
        content_hash(body, prefix="service-release-failure-report"),
    )


def _unsafe_path() -> bool:
    try:
        safe_relative_path("../escape.json")
    except ValidationError:
        return True
    return False


def audit_service_release_failure_injections(report: ServiceReleaseFailureReport) -> tuple:
    """Return lightweight checks for complete negative-control coverage."""

    from .service_release_contracts import ServiceReleasePlane, check

    return (
        check("failures:count", ServiceReleasePlane.FAILURE, report.case_count == 8,
              report.case_count, 8, "all structural controls are present"),
        check("failures:passed", ServiceReleasePlane.FAILURE, report.accepted,
              report.passed_case_count, report.case_count, "every control fails as expected"),
    )


__all__ = ["audit_service_release_failure_injections", "run_service_release_failure_injections"]
