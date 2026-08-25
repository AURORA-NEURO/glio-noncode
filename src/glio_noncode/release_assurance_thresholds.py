"""Explicit threshold evaluation for whole-product release decisions."""

from __future__ import annotations

from .release_assurance_contracts import (
    ReleaseAssurancePlane,
    ReleaseAssuranceRuntimeReport,
    ReleaseAssuranceSnapshot,
    ReleaseAssuranceState,
    ReleaseAssuranceThresholdReport,
    ReleaseAssuranceThresholdResult,
    check,
)
from .serialization import content_hash


def _result(
    threshold_id: str,
    name: str,
    expected,
    observed,
    passed: bool,
    detail: str,
) -> ReleaseAssuranceThresholdResult:
    body = {
        "threshold_id": threshold_id,
        "name": name,
        "expected": expected,
        "observed": observed,
        "passed": passed,
        "detail": detail,
    }
    return ReleaseAssuranceThresholdResult(
        **body,
        content_address=content_hash(body, prefix="release-assurance-threshold"),
    )


def evaluate_release_assurance_thresholds(
    snapshot: ReleaseAssuranceSnapshot,
    *,
    runtime: ReleaseAssuranceRuntimeReport | None = None,
) -> ReleaseAssuranceThresholdReport:
    """Evaluate readiness, failure, boundary, stage, and replay thresholds."""

    results = [
        _result(
            "threshold:overall-readiness",
            "overall readiness",
            100.0,
            snapshot.overall_percent,
            snapshot.overall_percent >= 100.0,
            "all four assurance planes must reach full readiness",
        ),
        _result(
            "threshold:domain-readiness",
            "domain readiness",
            100.0,
            tuple(item.readiness_percent for item in snapshot.domains),
            all(item.readiness_percent >= 100.0 for item in snapshot.domains),
            "each assurance plane must reach full readiness",
        ),
        _result(
            "threshold:failed-checks",
            "failed checks",
            0,
            len(snapshot.checks) - snapshot.passed_check_count,
            snapshot.passed_check_count == len(snapshot.checks),
            "no cross-plane check may remain failed",
        ),
        _result(
            "threshold:snapshot-accepted",
            "snapshot acceptance",
            True,
            snapshot.accepted,
            snapshot.accepted,
            "source snapshot must be accepted",
        ),
        _result(
            "threshold:source-addresses",
            "source addresses",
            True,
            bool(snapshot.service_snapshot_address and snapshot.public_audit_address),
            bool(snapshot.service_snapshot_address and snapshot.public_audit_address),
            "both upstream source addresses must be present",
        ),
    ]
    if runtime is not None:
        results.extend((
            _result(
                "threshold:runtime-accepted",
                "runtime acceptance",
                True,
                runtime.accepted,
                runtime.accepted,
                "runtime must be accepted",
            ),
            _result(
                "threshold:runtime-states",
                "runtime stage states",
                ReleaseAssuranceState.READY.value,
                tuple(item.state.value for item in runtime.stages),
                all(item.state is ReleaseAssuranceState.READY for item in runtime.stages),
                "every runtime stage must be ready",
            ),
            _result(
                "threshold:replay",
                "deterministic replay",
                True,
                runtime.replay.deterministic,
                runtime.replay.accepted,
                "replay addresses must match the expected snapshot",
            ),
        ))
    accepted = snapshot.accepted and all(item.passed for item in results)
    body = {"bundle_id": snapshot.bundle_id, "results": results, "accepted": accepted}
    return ReleaseAssuranceThresholdReport(
        snapshot.bundle_id,
        tuple(results),
        accepted,
        content_hash(body, prefix="release-assurance-threshold-report"),
    )


def audit_release_assurance_thresholds(
    report: ReleaseAssuranceThresholdReport,
    snapshot: ReleaseAssuranceSnapshot,
) -> tuple:
    """Audit threshold identity, result closure, and bundle linkage."""

    ids = tuple(item.threshold_id for item in report.results)
    return (
        check("thresholds:bundle", "thresholds", ReleaseAssurancePlane.RUNTIME,
              report.bundle_id == snapshot.bundle_id, report.bundle_id, snapshot.bundle_id,
              "threshold bundle matches snapshot"),
        check("thresholds:non-empty", "thresholds", ReleaseAssurancePlane.RUNTIME,
              bool(report.results), len(report.results), ">0", "threshold report is populated"),
        check("thresholds:identities", "thresholds", ReleaseAssurancePlane.RUNTIME,
              len(ids) == len(set(ids)), len(ids), len(set(ids)), "threshold identifiers are unique"),
        check("thresholds:accepted", "thresholds", ReleaseAssurancePlane.RUNTIME,
              report.accepted == all(item.passed for item in report.results),
              report.accepted, all(item.passed for item in report.results),
              "report acceptance follows threshold results"),
        check("thresholds:addresses", "thresholds", ReleaseAssurancePlane.PUBLIC_BOUNDARY,
              all(item.content_address for item in report.results),
              sum(bool(item.content_address) for item in report.results), len(report.results),
              "every threshold result is addressed"),
    )


def release_assurance_threshold_status(report: ReleaseAssuranceThresholdReport) -> dict[str, object]:
    """Return compact threshold status for CI and health clients."""

    return {
        "bundle_id": report.bundle_id,
        "accepted": report.accepted,
        "threshold_count": len(report.results),
        "failed_threshold_ids": report.failed_threshold_ids,
        "content_address": report.content_address,
    }


__all__ = [
    "audit_release_assurance_thresholds",
    "evaluate_release_assurance_thresholds",
    "release_assurance_threshold_status",
]
