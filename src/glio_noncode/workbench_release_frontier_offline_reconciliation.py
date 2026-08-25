"""Independent denominator and address reconciliation for D15 handoffs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .workbench_release_frontier_offline_contracts import WorkbenchReleaseOfflineBundle
from .workbench_release_frontier_offline_query import (
    _payload,
    _rows,
)

WORKBENCH_RELEASE_OFFLINE_RECONCILIATION_VERSION = "workbench-release-offline-reconciliation-v1"


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseOfflineReconciliationCheck:
    check_id: str
    plane: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseOfflineReconciliationReport:
    version: str
    bundle_id: str
    checks: tuple[WorkbenchReleaseOfflineReconciliationCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed_count": self.passed_count,
            "failed_count": len(self.checks) - self.passed_count,
        }


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseOfflineReconciliationDelta:
    bundle_id: str
    left_address: str
    right_address: str
    changed_artifacts: tuple[str, ...]
    changed_counts: dict[str, tuple[int, int]]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _check(
    check_id: str, plane: str, passed: bool, observed: Any, required: Any, detail: str
) -> WorkbenchReleaseOfflineReconciliationCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return WorkbenchReleaseOfflineReconciliationCheck(
        **body,
        content_address=content_hash(body, prefix="workbench-release-offline-reconciliation-check"),
    )


def _address(bundle: WorkbenchReleaseOfflineBundle, artifact_id: str) -> str:
    return next(
        (item.content_address for item in bundle.artifacts if item.artifact_id == artifact_id), ""
    )


def reconcile_workbench_release_offline_bundle(
    bundle: WorkbenchReleaseOfflineBundle,
) -> WorkbenchReleaseOfflineReconciliationReport:
    """Close every major join from fixture through release and runtime."""

    evaluation = _payload(bundle, "evaluation")
    runtime = _payload(bundle, "runtime")
    denominator = _payload(bundle, "denominator-index")
    stage_index = _payload(bundle, "stage-index")
    records = _rows(bundle, "fixture", "records")
    sources = _rows(bundle, "fixture", "sources")
    executions = _rows(bundle, "evaluation", "executions")
    checks = _rows(bundle, "evaluation", "checks")
    stages = _rows(bundle, "runtime", "stages")
    fixture_ids = tuple(str(item.get("record_id")) for item in records)
    execution_ids = tuple(str(item.get("record_id")) for item in executions)
    source_ids = tuple(str(item.get("source_id")) for item in sources)
    values = {
        "records": len(records),
        "sources": len(sources),
        "executions": len(executions),
        "checks": len(checks),
        "stages": len(stages),
        "operations": len({item.get("operation") for item in records}),
    }
    checks_out = (
        _check(
            "fixture-records",
            "denominator",
            values["records"] == 16,
            values["records"],
            16,
            "fixture records are conserved",
        ),
        _check(
            "fixture-sources",
            "denominator",
            values["sources"] == 5,
            values["sources"],
            5,
            "fixture sources are conserved",
        ),
        _check(
            "fixture-executions",
            "join",
            execution_ids == fixture_ids,
            execution_ids,
            fixture_ids,
            "execution record identities equal fixture identities",
        ),
        _check(
            "fixture-source-identities",
            "identity",
            len(source_ids) == len(set(source_ids)),
            len(set(source_ids)),
            len(source_ids),
            "source identities are unique",
        ),
        _check(
            "evaluation-checks",
            "denominator",
            values["checks"] == 80,
            values["checks"],
            80,
            "evaluation checks are conserved",
        ),
        _check(
            "runtime-stages",
            "denominator",
            values["stages"] == 49,
            values["stages"],
            49,
            "runtime stages are conserved",
        ),
        _check(
            "runtime-sequence",
            "runtime",
            [item.get("sequence") for item in stages] == list(range(1, 50)),
            [item.get("sequence") for item in stages],
            list(range(1, 50)),
            "runtime sequence is contiguous",
        ),
        _check(
            "runtime-root-join",
            "address",
            runtime.get("content_address") == bundle.runtime_address,
            runtime.get("content_address"),
            bundle.runtime_address,
            "runtime address joins root",
        ),
        _check(
            "stage-index-join",
            "address",
            stage_index.get("stage_count") == values["stages"]
            and stage_index.get("ordered") is True
            and stage_index.get("sequence") == list(range(1, 50)),
            stage_index,
            {"stage_count": 49, "ordered": True},
            "stage index joins runtime",
        ),
        _check(
            "denominator-index-join",
            "address",
            all(
                denominator.get(key) == value
                for key, value in (
                    ("records", 16),
                    ("sources", 5),
                    ("executions", 16),
                    ("evaluation_checks", 80),
                    ("runtime_stages", 49),
                )
            ),
            denominator,
            "D15 denominator index",
            "denominator index joins all counts",
        ),
        _check(
            "fixture-address",
            "address",
            _address(bundle, "fixture").startswith("workbench-release-bundle-artifact:"),
            _address(bundle, "fixture"),
            "address",
            "fixture has exact-byte address",
        ),
        _check(
            "evaluation-address",
            "address",
            _address(bundle, "evaluation").startswith("workbench-release-bundle-artifact:"),
            _address(bundle, "evaluation"),
            "address",
            "evaluation has exact-byte address",
        ),
        _check(
            "source-joins",
            "join",
            all(set(item.get("source_ids", ())) <= set(source_ids) for item in records),
            True,
            True,
            "record source references resolve",
        ),
        _check(
            "operation-balance",
            "denominator",
            all(
                sum(item.get("operation") == operation for item in records) == 4
                for operation in {item.get("operation") for item in records}
            ),
            {
                operation: sum(item.get("operation") == operation for item in records)
                for operation in {item.get("operation") for item in records}
            },
            "four each",
            "operation families are balanced",
        ),
        _check(
            "evaluation-accepted",
            "closure",
            bool(evaluation.get("accepted")),
            evaluation.get("accepted"),
            True,
            "evaluation is accepted",
        ),
        _check(
            "release-accepted",
            "closure",
            bool(_payload(bundle, "release").get("accepted")),
            _payload(bundle, "release").get("accepted"),
            True,
            "release is accepted",
        ),
        _check(
            "summary-accepted",
            "closure",
            bool(_payload(bundle, "summary").get("accepted")),
            _payload(bundle, "summary").get("accepted"),
            True,
            "summary is accepted",
        ),
        _check(
            "bundle-accepted",
            "closure",
            bundle.ready,
            bundle.accepted,
            True,
            "root bundle is accepted",
        ),
    )
    accepted = all(item.passed for item in checks_out)
    body = {
        "version": WORKBENCH_RELEASE_OFFLINE_RECONCILIATION_VERSION,
        "bundle_id": bundle.bundle_id,
        "checks": checks_out,
        "accepted": accepted,
    }
    return WorkbenchReleaseOfflineReconciliationReport(
        **body,
        content_address=content_hash(body, prefix="workbench-release-offline-reconciliation"),
    )


def compare_workbench_release_offline_bundles(
    left: WorkbenchReleaseOfflineBundle, right: WorkbenchReleaseOfflineBundle
) -> WorkbenchReleaseOfflineReconciliationDelta:
    """Compare artifacts and conserved denominators without exposing payload text."""

    left_map = {item.artifact_id: item.content_address for item in left.artifacts}
    right_map = {item.artifact_id: item.content_address for item in right.artifacts}
    changed = tuple(
        sorted(
            item
            for item in set(left_map) | set(right_map)
            if left_map.get(item) != right_map.get(item)
        )
    )
    count_fields = ("records", "sources", "executions", "checks", "stages")

    def counts(bundle: WorkbenchReleaseOfflineBundle) -> dict[str, int]:
        return {
            "records": len(_rows(bundle, "fixture", "records")),
            "sources": len(_rows(bundle, "fixture", "sources")),
            "executions": len(_rows(bundle, "evaluation", "executions")),
            "checks": len(_rows(bundle, "evaluation", "checks")),
            "stages": len(_rows(bundle, "runtime", "stages")),
        }

    left_counts = counts(left)
    right_counts = counts(right)
    changed_counts = {
        field: (left_counts[field], right_counts[field])
        for field in count_fields
        if left_counts[field] != right_counts[field]
    }
    body = {
        "bundle_id": right.bundle_id,
        "left_address": left.content_address,
        "right_address": right.content_address,
        "changed_artifacts": changed,
        "changed_counts": changed_counts,
        "accepted": not changed and not changed_counts,
    }
    return WorkbenchReleaseOfflineReconciliationDelta(
        **body,
        content_address=content_hash(body, prefix="workbench-release-offline-reconciliation-delta"),
    )


def workbench_release_offline_reconciliation_markdown(
    report: WorkbenchReleaseOfflineReconciliationReport,
) -> str:
    lines = [
        "# Workbench release offline reconciliation",
        "",
        f"Bundle: `{report.bundle_id}`",
        f"Accepted: `{str(report.accepted).lower()}`",
        f"Checks: `{report.passed_count}/{len(report.checks)}`",
        "",
        "| Check | State | Plane | Detail |",
        "| --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| `{item.check_id}` | `{('pass' if item.passed else 'hold')}` | "
        f"`{item.plane}` | {item.detail} |"
        for item in report.checks
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "WORKBENCH_RELEASE_OFFLINE_RECONCILIATION_VERSION",
    "WorkbenchReleaseOfflineReconciliationCheck",
    "WorkbenchReleaseOfflineReconciliationDelta",
    "WorkbenchReleaseOfflineReconciliationReport",
    "compare_workbench_release_offline_bundles",
    "reconcile_workbench_release_offline_bundle",
    "workbench_release_offline_reconciliation_markdown",
]
