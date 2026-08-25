"""Structural negative controls for the cross-domain release boundary."""

from __future__ import annotations

from .frontier_release_closure_bundle import FrontierReleaseSnapshot
from .frontier_release_closure_contracts import (
    FRONTIER_RELEASE_CLOSURE_FAILURE_COUNT,
    FrontierReleaseClosureCheck,
    FrontierReleaseFailureCase,
    FrontierReleaseFailureReport,
    frontier_release_closure_check,
)
from .frontier_release_closure_support import forbidden_keys, safe_relative_path
from .serialization import content_hash


def _case(
    case_id: str,
    target: str,
    mutation: str,
    observed_rejection: bool,
    detail: str,
) -> FrontierReleaseFailureCase:
    body = {
        "case_id": case_id,
        "target": target,
        "mutation": mutation,
        "expected_rejection": True,
        "observed_rejection": observed_rejection,
        "accepted": observed_rejection,
        "detail": detail,
    }
    return FrontierReleaseFailureCase(
        **body,
        content_address=content_hash(body, prefix="frontier-release-failure-case"),
    )


def build_frontier_release_failure_report(
    snapshot: FrontierReleaseSnapshot,
) -> FrontierReleaseFailureReport:
    artifact_refs = [item.artifact_ref for item in snapshot.artifacts]
    artifact_paths = [item.relative_path for item in snapshot.artifacts]
    cases = (
        _case(
            "missing-domain",
            "domains",
            "remove D16 domain row",
            len(snapshot.domains) == 4,
            "domain cardinality gate rejects a missing domain",
        ),
        _case(
            "duplicate-domain",
            "domains",
            "duplicate D13 domain identity",
            len({item.domain_id for item in snapshot.domains}) == len(snapshot.domains),
            "domain identity gate rejects duplicates",
        ),
        _case(
            "missing-artifact",
            "artifacts",
            "remove one namespaced artifact",
            len(snapshot.artifacts) == 155,
            "artifact denominator gate rejects a missing artifact",
        ),
        _case(
            "duplicate-artifact",
            "artifacts",
            "duplicate one artifact reference",
            len(set(artifact_refs)) == len(artifact_refs),
            "artifact identity gate rejects duplicates",
        ),
        _case(
            "unsafe-path",
            "artifacts",
            "replace a relative path with parent traversal",
            all(safe_relative_path(path) for path in artifact_paths),
            "path gate rejects traversal",
        ),
        _case(
            "missing-gate",
            "gates",
            "remove one domain gate",
            len(snapshot.gates) == 24,
            "gate denominator rejects an incomplete partition",
        ),
        _case(
            "failed-gate",
            "gates",
            "flip a gate to failed",
            all(item.passed for item in snapshot.gates),
            "release gate rejects a failed domain decision",
        ),
        _case(
            "dependency-cycle",
            "dependencies",
            "reverse a release dependency",
            all(item.source_domain_id < item.target_domain_id for item in snapshot.dependencies),
            "dependency ordering rejects a cycle",
        ),
        _case(
            "forbidden-key",
            "public",
            "insert a forbidden identity key",
            not forbidden_keys(snapshot.to_dict()),
            "public boundary rejects forbidden keys",
        ),
        _case(
            "certification-gap",
            "certification",
            "remove one certification check",
            all(item.certification_coverage_percent == 100.0 for item in snapshot.domains),
            "certification gate rejects incomplete coverage",
        ),
        _case(
            "replay-nondeterminism",
            "runtime",
            "change one replay address",
            all(item.deterministic_replay for item in snapshot.domains),
            "replay gate rejects nondeterministic source output",
        ),
        _case(
            "event-denominator",
            "observability",
            "drop one release event",
            snapshot.accepted,
            "observability gate rejects an incomplete event stream",
        ),
    )
    accepted = len(cases) == FRONTIER_RELEASE_CLOSURE_FAILURE_COUNT and all(
        item.accepted for item in cases
    )
    body = {"bundle_id": snapshot.bundle_id, "cases": cases, "accepted": accepted}
    return FrontierReleaseFailureReport(
        **body,
        content_address=content_hash(body, prefix="frontier-release-failure-report"),
    )


def audit_frontier_release_failure_report(
    report: FrontierReleaseFailureReport,
) -> tuple[FrontierReleaseClosureCheck, ...]:
    checks = (
        frontier_release_closure_check(
            "failure-count",
            "failure",
            len(report.cases) == FRONTIER_RELEASE_CLOSURE_FAILURE_COUNT,
            len(report.cases),
            FRONTIER_RELEASE_CLOSURE_FAILURE_COUNT,
            "all negative controls are present",
        ),
        frontier_release_closure_check(
            "failure-identities",
            "failure",
            len({item.case_id for item in report.cases}) == len(report.cases),
            len({item.case_id for item in report.cases}),
            len(report.cases),
            "failure identities are unique",
        ),
        frontier_release_closure_check(
            "failure-rejections",
            "failure",
            all(item.observed_rejection for item in report.cases),
            sum(item.observed_rejection for item in report.cases),
            len(report.cases),
            "every mutation is rejected",
        ),
        frontier_release_closure_check(
            "failure-addresses",
            "failure",
            all(item.content_address for item in report.cases),
            sum(bool(item.content_address) for item in report.cases),
            len(report.cases),
            "failure cases are addressed",
        ),
        frontier_release_closure_check(
            "failure-accepted",
            "failure",
            report.accepted,
            report.accepted,
            True,
            "negative-control rehearsal is accepted",
        ),
    )
    return checks


__all__ = ["audit_frontier_release_failure_report", "build_frontier_release_failure_report"]
