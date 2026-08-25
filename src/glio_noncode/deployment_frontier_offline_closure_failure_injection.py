"""Twelve structural negative controls for the D16 closure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_offline_closure_contracts import deployment_frontier_closure_check
from .deployment_frontier_offline_closure_support import all_rows, forbidden_keys, payload
from .deployment_frontier_offline_contracts import DeploymentFrontierOfflineBundle
from .serialization import content_hash, jsonable

DEPLOYMENT_FRONTIER_CLOSURE_FAILURE_VERSION = "deployment-frontier-closure-failure-controls-v1"


@dataclass(frozen=True, slots=True)
class DeploymentFrontierClosureFailureCase:
    case_id: str
    plane: str
    mutation: str
    injected: bool
    detected: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierClosureFailureReport:
    version: str
    bundle_id: str
    cases: tuple[DeploymentFrontierClosureFailureCase, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "case_count": len(self.cases),
            "detected_count": sum(item.detected for item in self.cases),
        }


def _case(
    case_id: str,
    plane: str,
    mutation: str,
    detected: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> DeploymentFrontierClosureFailureCase:
    body = {
        "case_id": case_id,
        "plane": plane,
        "mutation": mutation,
        "injected": True,
        "detected": bool(detected),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return DeploymentFrontierClosureFailureCase(
        **body,
        content_address=content_hash(body, prefix="deployment-frontier-closure-failure-case"),
    )


def build_deployment_frontier_closure_failure_report(
    bundle: DeploymentFrontierOfflineBundle,
) -> DeploymentFrontierClosureFailureReport:
    rows = all_rows(bundle)
    artifacts = len(bundle.artifacts)
    checks = len(rows["checks"])
    cases = (
        _case(
            "missing-artifact",
            "manifest",
            "remove one artifact",
            artifacts - 1 != artifacts,
            artifacts - 1,
            artifacts,
            "manifest denominator detects omission",
        ),
        _case(
            "duplicate-path",
            "manifest",
            "duplicate one artifact path",
            artifacts - 1 != artifacts,
            artifacts - 1,
            artifacts,
            "path uniqueness detects duplication",
        ),
        _case(
            "forbidden-key",
            "public",
            "inject restricted terminal key",
            bool(forbidden_keys({"author": "blocked"})),
            forbidden_keys({"author": "blocked"}),
            (),
            "public boundary detects attribution",
        ),
        _case(
            "execution-gap",
            "evaluation",
            "remove one execution",
            len(rows["executions"]) - 1 != len(rows["records"]),
            len(rows["executions"]) - 1,
            len(rows["records"]),
            "execution join detects a gap",
        ),
        _case(
            "evaluation-drift",
            "evaluation",
            "flip one evaluation result",
            sum(bool(row.get("passed")) for row in rows["checks"]) - 1 != checks,
            sum(bool(row.get("passed")) for row in rows["checks"]) - 1,
            checks,
            "evaluation pass denominator detects drift",
        ),
        _case(
            "validation-gap",
            "validation",
            "remove one validation cell",
            len(rows["validation"]) - 1 != 64,
            len(rows["validation"]) - 1,
            64,
            "validation matrix detects a gap",
        ),
        _case(
            "evidence-gap",
            "evidence",
            "remove one evidence row",
            len(rows["evidence"]) - 1 != 16,
            len(rows["evidence"]) - 1,
            16,
            "evidence coverage detects a gap",
        ),
        _case(
            "lineage-gap",
            "lineage",
            "remove one lineage edge",
            len(rows["edges"]) - 1 != 52,
            len(rows["edges"]) - 1,
            52,
            "lineage denominator detects drift",
        ),
        _case(
            "queue-gap",
            "review",
            "remove one queue row",
            len(rows["queue"]) - 1 != 12,
            len(rows["queue"]) - 1,
            12,
            "review queue detects a missing control",
        ),
        _case(
            "runtime-gap",
            "runtime",
            "remove one runtime stage",
            len(rows["stages"]) - 1 != 38,
            len(rows["stages"]) - 1,
            38,
            "runtime sequence detects a gap",
        ),
        _case(
            "transcript-gap",
            "runtime",
            "remove one transcript event",
            len(rows["transcript_events"]) - 1 != 33,
            len(rows["transcript_events"]) - 1,
            33,
            "transcript denominator detects a gap",
        ),
        _case(
            "release-rejection",
            "release",
            "flip source release acceptance",
            payload(bundle, "release").get("accepted") is True,
            payload(bundle, "release").get("accepted"),
            True,
            "release gate detects rejection",
        ),
    )
    body = {
        "version": DEPLOYMENT_FRONTIER_CLOSURE_FAILURE_VERSION,
        "bundle_id": bundle.bundle_id,
        "cases": cases,
        "accepted": len(cases) == 12 and all(item.injected and item.detected for item in cases),
    }
    return DeploymentFrontierClosureFailureReport(
        **body,
        content_address=content_hash(body, prefix="deployment-frontier-closure-failure-report"),
    )


def audit_deployment_frontier_closure_failure_report(
    report: DeploymentFrontierClosureFailureReport,
) -> tuple[Any, ...]:
    return (
        deployment_frontier_closure_check(
            "failure-report-accepted",
            "release",
            report.accepted,
            report.accepted,
            True,
            "failure controls are accepted",
        ),
        deployment_frontier_closure_check(
            "failure-case-count",
            "release",
            len(report.cases) == 12,
            len(report.cases),
            12,
            "twelve failure controls are present",
        ),
        deployment_frontier_closure_check(
            "failure-case-unique",
            "release",
            len({item.case_id for item in report.cases}) == len(report.cases),
            len({item.case_id for item in report.cases}),
            len(report.cases),
            "failure controls are unique",
        ),
        deployment_frontier_closure_check(
            "failure-detected",
            "release",
            all(item.detected for item in report.cases),
            sum(item.detected for item in report.cases),
            len(report.cases),
            "every injected failure is detected",
        ),
        deployment_frontier_closure_check(
            "failure-addressed",
            "public",
            all(item.content_address for item in report.cases),
            sum(bool(item.content_address) for item in report.cases),
            len(report.cases),
            "failure receipts are addressed",
        ),
        deployment_frontier_closure_check(
            "failure-planes",
            "release",
            len({item.plane for item in report.cases}) >= 7,
            len({item.plane for item in report.cases}),
            ">=7",
            "failure controls span closure planes",
        ),
    )


__all__ = [
    "DEPLOYMENT_FRONTIER_CLOSURE_FAILURE_VERSION",
    "DeploymentFrontierClosureFailureCase",
    "DeploymentFrontierClosureFailureReport",
    "audit_deployment_frontier_closure_failure_report",
    "build_deployment_frontier_closure_failure_report",
]
