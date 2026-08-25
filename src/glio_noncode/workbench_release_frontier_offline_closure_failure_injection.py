"""Negative controls proving that D15 closure drift is observable."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .workbench_release_frontier_offline_closure_contracts import workbench_release_closure_check
from .workbench_release_frontier_offline_closure_support import (
    all_rows,
    forbidden_keys,
    payload,
)
from .workbench_release_frontier_offline_contracts import WorkbenchReleaseOfflineBundle

WORKBENCH_RELEASE_CLOSURE_FAILURE_VERSION = "workbench-release-closure-failure-controls-v1"


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseClosureFailureCase:
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
class WorkbenchReleaseClosureFailureReport:
    version: str
    bundle_id: str
    cases: tuple[WorkbenchReleaseClosureFailureCase, ...]
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
) -> WorkbenchReleaseClosureFailureCase:
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
    return WorkbenchReleaseClosureFailureCase(
        **body,
        content_address=content_hash(body, prefix="workbench-release-closure-failure-case"),
    )


def build_workbench_release_closure_failure_report(
    bundle: WorkbenchReleaseOfflineBundle,
) -> WorkbenchReleaseClosureFailureReport:
    """Run twelve bounded mutations against public projections."""

    rows = all_rows(bundle)
    artifact_count = len(bundle.artifacts)
    cases = (
        _case(
            "missing-artifact",
            "manifest",
            "remove one artifact",
            artifact_count - 1 != artifact_count,
            artifact_count - 1,
            artifact_count,
            "manifest denominator rejects omission",
        ),
        _case(
            "duplicate-path",
            "manifest",
            "duplicate one relative path",
            artifact_count - 1 != artifact_count,
            artifact_count - 1,
            artifact_count,
            "manifest path uniqueness rejects duplication",
        ),
        _case(
            "forbidden-key",
            "public",
            "inject restricted terminal key",
            bool(forbidden_keys({"author": "blocked"})),
            forbidden_keys({"author": "blocked"}),
            (),
            "public key audit rejects identity fields",
        ),
        _case(
            "record-execution-gap",
            "evaluation",
            "remove one execution",
            len(rows["executions"]) - 1 != len(rows["records"]),
            len(rows["executions"]) - 1,
            len(rows["records"]),
            "record execution join rejects a gap",
        ),
        _case(
            "evaluation-drift",
            "evaluation",
            "flip one evaluation result",
            sum(bool(row.get("passed")) for row in rows["checks"]) - 1 != len(rows["checks"]),
            sum(bool(row.get("passed")) for row in rows["checks"]) - 1,
            len(rows["checks"]),
            "evaluation pass denominator rejects drift",
        ),
        _case(
            "validation-gap",
            "validation",
            "remove one validation cell",
            len(rows["validation"]) - 1 != 80,
            len(rows["validation"]) - 1,
            80,
            "validation matrix rejects a missing cell",
        ),
        _case(
            "evidence-gap",
            "evidence",
            "remove one evidence row",
            len(rows["evidence"]) - 1 != 16,
            len(rows["evidence"]) - 1,
            16,
            "evidence coverage rejects a missing receipt",
        ),
        _case(
            "lineage-drift",
            "lineage",
            "remove one lineage edge",
            len(rows["edges"]) - 1 != 52,
            len(rows["edges"]) - 1,
            52,
            "lineage denominator rejects drift",
        ),
        _case(
            "queue-drift",
            "review",
            "remove one review row",
            len(rows["queue"]) - 1 != 12,
            len(rows["queue"]) - 1,
            12,
            "review queue rejects a missing issue",
        ),
        _case(
            "runtime-gap",
            "runtime",
            "remove one runtime stage",
            len(rows["stages"]) - 1 != 49,
            len(rows["stages"]) - 1,
            49,
            "runtime sequence rejects a gap",
        ),
        _case(
            "runtime-address",
            "runtime",
            "clear runtime address",
            bool(bundle.runtime_address),
            bundle.runtime_address,
            "workbench-release-bundle-runtime:*",
            "runtime receipt is required",
        ),
        _case(
            "release-rejection",
            "release",
            "flip release acceptance",
            payload(bundle, "release").get("accepted") is True,
            payload(bundle, "release").get("accepted"),
            True,
            "release gate rejects a negative decision",
        ),
    )
    body = {
        "version": WORKBENCH_RELEASE_CLOSURE_FAILURE_VERSION,
        "bundle_id": bundle.bundle_id,
        "cases": cases,
        "accepted": len(cases) == 12 and all(item.injected and item.detected for item in cases),
    }
    return WorkbenchReleaseClosureFailureReport(
        **body,
        content_address=content_hash(body, prefix="workbench-release-closure-failure-report"),
    )


def audit_workbench_release_closure_failure_report(
    report: WorkbenchReleaseClosureFailureReport,
) -> tuple[Any, ...]:
    checks = (
        workbench_release_closure_check(
            "failure-report-accepted",
            "release",
            report.accepted,
            report.accepted,
            True,
            "failure controls are accepted",
        ),
        workbench_release_closure_check(
            "failure-case-count",
            "release",
            len(report.cases) == 12,
            len(report.cases),
            12,
            "twelve failure controls are present",
        ),
        workbench_release_closure_check(
            "failure-case-unique",
            "release",
            len({item.case_id for item in report.cases}) == len(report.cases),
            len({item.case_id for item in report.cases}),
            len(report.cases),
            "failure controls are unique",
        ),
        workbench_release_closure_check(
            "failure-detected",
            "release",
            all(item.detected for item in report.cases),
            sum(item.detected for item in report.cases),
            len(report.cases),
            "every injected failure is detected",
        ),
        workbench_release_closure_check(
            "failure-addressed",
            "public",
            all(item.content_address for item in report.cases),
            sum(bool(item.content_address) for item in report.cases),
            len(report.cases),
            "failure receipts are addressed",
        ),
        workbench_release_closure_check(
            "failure-planes",
            "release",
            len({item.plane for item in report.cases}) >= 6,
            len({item.plane for item in report.cases}),
            ">=6",
            "failure controls span closure planes",
        ),
    )
    return checks


__all__ = [
    "WORKBENCH_RELEASE_CLOSURE_FAILURE_VERSION",
    "WorkbenchReleaseClosureFailureCase",
    "WorkbenchReleaseClosureFailureReport",
    "audit_workbench_release_closure_failure_report",
    "build_workbench_release_closure_failure_report",
]
