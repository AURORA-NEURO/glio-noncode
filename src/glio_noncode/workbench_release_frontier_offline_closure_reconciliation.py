"""Independent denominator and join reconciliation for D15 closure projections."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .serialization import content_hash
from .workbench_release_frontier_offline_closure_contracts import (
    WORKBENCH_RELEASE_CLOSURE_ARTIFACT_COUNT,
    WORKBENCH_RELEASE_CLOSURE_CHECK_PREFIX,
    WORKBENCH_RELEASE_CLOSURE_DIAGNOSTIC_COUNT,
    WORKBENCH_RELEASE_CLOSURE_EVALUATION_CHECK_COUNT,
    WORKBENCH_RELEASE_CLOSURE_EVIDENCE_CELL_COUNT,
    WORKBENCH_RELEASE_CLOSURE_EXECUTION_COUNT,
    WORKBENCH_RELEASE_CLOSURE_LINEAGE_EDGE_COUNT,
    WORKBENCH_RELEASE_CLOSURE_OPERATION_COUNT,
    WORKBENCH_RELEASE_CLOSURE_QUEUE_COUNT,
    WORKBENCH_RELEASE_CLOSURE_RECORD_COUNT,
    WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT,
    WORKBENCH_RELEASE_CLOSURE_SOURCE_COUNT,
    WORKBENCH_RELEASE_CLOSURE_VALIDATION_CELL_COUNT,
    WORKBENCH_RELEASE_CLOSURE_VIEW_COUNT,
    WorkbenchReleaseClosureReconciliationCheck,
    WorkbenchReleaseClosureReconciliationDelta,
    WorkbenchReleaseClosureReconciliationReport,
)
from .workbench_release_frontier_offline_closure_support import all_rows, forbidden_keys, payload
from .workbench_release_frontier_offline_contracts import WorkbenchReleaseOfflineBundle

WORKBENCH_RELEASE_CLOSURE_RECONCILIATION_VERSION = "workbench-release-closure-reconciliation-v1"


def _check(
    check_id: str,
    plane: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> WorkbenchReleaseClosureReconciliationCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return WorkbenchReleaseClosureReconciliationCheck(
        **body,
        content_address=content_hash(body, prefix=WORKBENCH_RELEASE_CLOSURE_CHECK_PREFIX),
    )


def _accepted_payload(bundle: WorkbenchReleaseOfflineBundle, artifact_id: str) -> bool:
    value = payload(bundle, artifact_id)
    return isinstance(value, dict) and bool(value.get("accepted"))


def _addressed(rows: tuple[dict[str, Any], ...]) -> bool:
    return bool(rows) and all(bool(row.get("content_address")) for row in rows)


def reconcile_workbench_release_closure(
    bundle: WorkbenchReleaseOfflineBundle,
) -> WorkbenchReleaseClosureReconciliationReport:
    rows = all_rows(bundle)
    fixture = payload(bundle, "fixture")
    runtime = payload(bundle, "runtime")
    record_ids = {str(row.get("record_id")) for row in rows["records"]}
    execution_ids = {str(row.get("record_id")) for row in rows["executions"]}
    fixture_ids = (
        {str(row.get("record_id")) for row in fixture.get("records", ())}
        if isinstance(fixture, dict)
        else set()
    )
    issue_count = sum(bool(row.get("issue_codes")) for row in rows["executions"])
    roles = Counter(str(row.get("role")) for row in rows["records"])
    operations = {str(row.get("operation")) for row in rows["records"]}
    checks = (
        _check(
            "bundle-ready",
            "manifest",
            bundle.ready,
            bundle.state,
            "ready",
            "source D15 bundle is ready",
        ),
        _check(
            "artifact-count",
            "manifest",
            len(bundle.artifacts) == WORKBENCH_RELEASE_CLOSURE_ARTIFACT_COUNT,
            len(bundle.artifacts),
            WORKBENCH_RELEASE_CLOSURE_ARTIFACT_COUNT,
            "artifact denominator is conserved",
        ),
        _check(
            "artifact-addresses",
            "manifest",
            all(
                item.content_address.startswith("workbench-release-bundle-artifact:")
                for item in bundle.artifacts
            ),
            len(bundle.artifacts),
            WORKBENCH_RELEASE_CLOSURE_ARTIFACT_COUNT,
            "artifact addresses are exact-byte addresses",
        ),
        _check(
            "artifact-paths",
            "manifest",
            len({item.relative_path for item in bundle.artifacts})
            == WORKBENCH_RELEASE_CLOSURE_ARTIFACT_COUNT,
            len({item.relative_path for item in bundle.artifacts}),
            WORKBENCH_RELEASE_CLOSURE_ARTIFACT_COUNT,
            "artifact paths are unique",
        ),
        _check(
            "fixture-records",
            "fixture",
            len(rows["records"]) == WORKBENCH_RELEASE_CLOSURE_RECORD_COUNT,
            len(rows["records"]),
            WORKBENCH_RELEASE_CLOSURE_RECORD_COUNT,
            "fixture records are conserved",
        ),
        _check(
            "fixture-sources",
            "fixture",
            len(rows["sources"]) == WORKBENCH_RELEASE_CLOSURE_SOURCE_COUNT,
            len(rows["sources"]),
            WORKBENCH_RELEASE_CLOSURE_SOURCE_COUNT,
            "fixture sources are conserved",
        ),
        _check(
            "fixture-record-join",
            "fixture",
            fixture_ids == record_ids,
            len(fixture_ids),
            WORKBENCH_RELEASE_CLOSURE_RECORD_COUNT,
            "fixture and closure records join",
        ),
        _check(
            "fixture-roles",
            "fixture",
            roles == {"positive": 4, "control": 12},
            dict(roles),
            {"positive": 4, "control": 12},
            "positive and control denominators are balanced",
        ),
        _check(
            "fixture-operations",
            "fixture",
            len(operations) == WORKBENCH_RELEASE_CLOSURE_OPERATION_COUNT
            and all(row.get("record_count") == 4 for row in rows["operations"]),
            len(operations),
            WORKBENCH_RELEASE_CLOSURE_OPERATION_COUNT,
            "operations are balanced four-record partitions",
        ),
        _check(
            "source-uris",
            "fixture",
            all(str(row.get("uri", "")).startswith("https://") for row in rows["sources"]),
            len(rows["sources"]),
            WORKBENCH_RELEASE_CLOSURE_SOURCE_COUNT,
            "source receipts use HTTPS",
        ),
        _check(
            "execution-count",
            "evaluation",
            len(rows["executions"]) == WORKBENCH_RELEASE_CLOSURE_EXECUTION_COUNT,
            len(rows["executions"]),
            WORKBENCH_RELEASE_CLOSURE_EXECUTION_COUNT,
            "executions are conserved",
        ),
        _check(
            "execution-join",
            "evaluation",
            execution_ids == record_ids,
            len(execution_ids),
            WORKBENCH_RELEASE_CLOSURE_RECORD_COUNT,
            "execution identities close records",
        ),
        _check(
            "evaluation-check-count",
            "evaluation",
            len(rows["checks"]) == WORKBENCH_RELEASE_CLOSURE_EVALUATION_CHECK_COUNT,
            len(rows["checks"]),
            WORKBENCH_RELEASE_CLOSURE_EVALUATION_CHECK_COUNT,
            "evaluation checks are conserved",
        ),
        _check(
            "evaluation-record-coverage",
            "evaluation",
            {row.get("record_id") for row in rows["checks"]} == record_ids,
            len({row.get("record_id") for row in rows["checks"]}),
            WORKBENCH_RELEASE_CLOSURE_RECORD_COUNT,
            "evaluation checks cover every record",
        ),
        _check(
            "evaluation-passed",
            "evaluation",
            all(bool(row.get("passed")) for row in rows["checks"]),
            sum(bool(row.get("passed")) for row in rows["checks"]),
            WORKBENCH_RELEASE_CLOSURE_EVALUATION_CHECK_COUNT,
            "evaluation checks pass",
        ),
        _check(
            "validation-count",
            "validation",
            len(rows["validation"]) == WORKBENCH_RELEASE_CLOSURE_VALIDATION_CELL_COUNT,
            len(rows["validation"]),
            WORKBENCH_RELEASE_CLOSURE_VALIDATION_CELL_COUNT,
            "validation cells are conserved",
        ),
        _check(
            "validation-record-coverage",
            "validation",
            {row.get("record_id") for row in rows["validation"]} == record_ids,
            len({row.get("record_id") for row in rows["validation"]}),
            WORKBENCH_RELEASE_CLOSURE_RECORD_COUNT,
            "validation cells cover every record",
        ),
        _check(
            "validation-passed",
            "validation",
            all(bool(row.get("passed")) for row in rows["validation"]),
            sum(bool(row.get("passed")) for row in rows["validation"]),
            WORKBENCH_RELEASE_CLOSURE_VALIDATION_CELL_COUNT,
            "validation cells pass",
        ),
        _check(
            "evidence-count",
            "evidence",
            len(rows["evidence"]) == WORKBENCH_RELEASE_CLOSURE_EVIDENCE_CELL_COUNT,
            len(rows["evidence"]),
            WORKBENCH_RELEASE_CLOSURE_EVIDENCE_CELL_COUNT,
            "evidence cells are conserved",
        ),
        _check(
            "evidence-record-coverage",
            "evidence",
            {row.get("record_id") for row in rows["evidence"]} == record_ids,
            len({row.get("record_id") for row in rows["evidence"]}),
            WORKBENCH_RELEASE_CLOSURE_RECORD_COUNT,
            "evidence cells cover every record",
        ),
        _check(
            "lineage-count",
            "lineage",
            len(rows["edges"]) == WORKBENCH_RELEASE_CLOSURE_LINEAGE_EDGE_COUNT,
            len(rows["edges"]),
            WORKBENCH_RELEASE_CLOSURE_LINEAGE_EDGE_COUNT,
            "lineage edges are conserved",
        ),
        _check(
            "lineage-identities",
            "lineage",
            len({row.get("edge_id") for row in rows["edges"]})
            == WORKBENCH_RELEASE_CLOSURE_LINEAGE_EDGE_COUNT,
            len({row.get("edge_id") for row in rows["edges"]}),
            WORKBENCH_RELEASE_CLOSURE_LINEAGE_EDGE_COUNT,
            "lineage edges are unique",
        ),
        _check(
            "lineage-source-coverage",
            "lineage",
            {
                row.get("parent_id")
                for row in rows["edges"]
                if row.get("relation") == "source_to_record"
            }
            >= {row.get("source_id") for row in rows["sources"]},
            len(
                {
                    row.get("parent_id")
                    for row in rows["edges"]
                    if row.get("relation") == "source_to_record"
                }
            ),
            WORKBENCH_RELEASE_CLOSURE_SOURCE_COUNT,
            "lineage names every source",
        ),
        _check(
            "lineage-record-coverage",
            "lineage",
            {
                row.get("parent_id")
                for row in rows["edges"]
                if row.get("relation") == "record_to_execution"
            }
            == record_ids,
            len(
                {
                    row.get("parent_id")
                    for row in rows["edges"]
                    if row.get("relation") == "record_to_execution"
                }
            ),
            WORKBENCH_RELEASE_CLOSURE_RECORD_COUNT,
            "lineage names every record",
        ),
        _check(
            "view-count",
            "review",
            len(rows["views"]) == WORKBENCH_RELEASE_CLOSURE_VIEW_COUNT,
            len(rows["views"]),
            WORKBENCH_RELEASE_CLOSURE_VIEW_COUNT,
            "review view closes records",
        ),
        _check(
            "view-record-coverage",
            "review",
            {row.get("record_id") for row in rows["views"]} == record_ids,
            len({row.get("record_id") for row in rows["views"]}),
            WORKBENCH_RELEASE_CLOSURE_RECORD_COUNT,
            "view rows join records",
        ),
        _check(
            "queue-count",
            "review",
            len(rows["queue"]) == WORKBENCH_RELEASE_CLOSURE_QUEUE_COUNT,
            len(rows["queue"]),
            WORKBENCH_RELEASE_CLOSURE_QUEUE_COUNT,
            "review queue denominator is conserved",
        ),
        _check(
            "queue-record-coverage",
            "review",
            {row.get("record_id") for row in rows["queue"]} <= record_ids,
            len({row.get("record_id") for row in rows["queue"]}),
            WORKBENCH_RELEASE_CLOSURE_QUEUE_COUNT,
            "queue rows reference records",
        ),
        _check(
            "diagnostic-count",
            "review",
            len(rows["diagnostics"]) == WORKBENCH_RELEASE_CLOSURE_DIAGNOSTIC_COUNT,
            len(rows["diagnostics"]),
            WORKBENCH_RELEASE_CLOSURE_DIAGNOSTIC_COUNT,
            "diagnostics close records",
        ),
        _check(
            "stage-count",
            "runtime",
            len(rows["stages"]) == WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT
            and [row.get("sequence") for row in rows["stages"]] == list(range(1, 50)),
            len(rows["stages"]),
            WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT,
            "runtime stages are contiguous",
        ),
        _check(
            "stage-index-count",
            "runtime",
            len(rows["stage_index"]) == WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT
            and [row.get("sequence") for row in rows["stage_index"]] == list(range(1, 50)),
            len(rows["stage_index"]),
            WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT,
            "stage index closes runtime",
        ),
        _check(
            "stage-manifest-join",
            "runtime",
            bundle.stage_count == WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT,
            bundle.stage_count,
            WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT,
            "root manifest stage count joins runtime",
        ),
        _check(
            "runtime-address",
            "runtime",
            isinstance(runtime, dict) and runtime.get("content_address") == bundle.runtime_address,
            runtime.get("content_address") if isinstance(runtime, dict) else None,
            bundle.runtime_address,
            "runtime address joins root manifest",
        ),
        _check(
            "base-reconciliation",
            "release",
            _accepted_payload(bundle, "reconciliation"),
            payload(bundle, "reconciliation").get("accepted"),
            True,
            "source reconciliation is accepted",
        ),
        _check(
            "base-quality",
            "release",
            _accepted_payload(bundle, "quality"),
            payload(bundle, "quality").get("accepted"),
            True,
            "source quality gate is accepted",
        ),
        _check(
            "base-release",
            "release",
            _accepted_payload(bundle, "release"),
            payload(bundle, "release").get("accepted"),
            True,
            "source release is accepted",
        ),
        _check(
            "base-handoff",
            "release",
            _accepted_payload(bundle, "handoff"),
            payload(bundle, "handoff").get("accepted"),
            True,
            "source handoff is accepted",
        ),
        _check(
            "policy-aggregate",
            "public",
            bool(payload(bundle, "policy").get("aggregate_only")),
            payload(bundle, "policy").get("aggregate_only"),
            True,
            "policy remains aggregate-only",
        ),
        _check(
            "public-key-policy",
            "public",
            not forbidden_keys(payload(bundle, "fixture")),
            forbidden_keys(payload(bundle, "fixture")),
            (),
            "fixture stays within public boundary",
        ),
        _check(
            "row-addresses",
            "public",
            all(_addressed(value) for value in rows.values() if value),
            {key: len(value) for key, value in rows.items()},
            "addressed",
            "closure rows are addressable",
        ),
        _check(
            "control-count",
            "release",
            len(rows["controls"]) == 4,
            len(rows["controls"]),
            4,
            "control coverage is conserved",
        ),
        _check(
            "failure-case-count",
            "release",
            len(rows["failures"]) == 4,
            len(rows["failures"]),
            4,
            "failure cases are conserved",
        ),
        _check(
            "issue-visibility",
            "release",
            issue_count == 12,
            issue_count,
            12,
            "issue-bearing executions remain visible",
        ),
        _check(
            "accepted-root",
            "release",
            bundle.accepted,
            bundle.accepted,
            True,
            "root handoff remains accepted",
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {
        "version": WORKBENCH_RELEASE_CLOSURE_RECONCILIATION_VERSION,
        "bundle_id": bundle.bundle_id,
        "checks": checks,
        "accepted": accepted,
    }
    return WorkbenchReleaseClosureReconciliationReport(
        **body,
        content_address=content_hash(body, prefix="workbench-release-closure-reconciliation"),
    )


def diff_workbench_release_closure_bundles(
    left: WorkbenchReleaseOfflineBundle, right: WorkbenchReleaseOfflineBundle
) -> WorkbenchReleaseClosureReconciliationDelta:
    left_map = {item.artifact_id: item.content_address for item in left.artifacts}
    right_map = {item.artifact_id: item.content_address for item in right.artifacts}
    changed = tuple(
        sorted(
            key for key in set(left_map) | set(right_map) if left_map.get(key) != right_map.get(key)
        )
    )
    left_counts = {key: len(value) for key, value in all_rows(left).items()}
    right_counts = {key: len(value) for key, value in all_rows(right).items()}
    changed_counts = {
        key: (left_counts.get(key, 0), right_counts.get(key, 0))
        for key in set(left_counts) | set(right_counts)
        if left_counts.get(key, 0) != right_counts.get(key, 0)
    }
    body = {
        "left_bundle_id": left.bundle_id,
        "right_bundle_id": right.bundle_id,
        "left_address": left.content_address,
        "right_address": right.content_address,
        "changed_artifacts": changed,
        "changed_counts": changed_counts,
        "accepted": not changed and not changed_counts,
    }
    return WorkbenchReleaseClosureReconciliationDelta(
        **body, content_address=content_hash(body, prefix="workbench-release-closure-delta")
    )


def workbench_release_closure_reconciliation_markdown(
    report: WorkbenchReleaseClosureReconciliationReport,
) -> str:
    lines = [
        "# Workbench release closure reconciliation",
        "",
        f"Bundle: `{report.bundle_id}`",
        f"Accepted: `{str(report.accepted).lower()}`",
        f"Checks: `{report.passed_count}/{len(report.checks)}`",
        "",
        "| Check | Plane | State | Detail |",
        "| --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| `{item.check_id}` | `{item.plane}` | `{'pass' if item.passed else 'hold'}` | "
        f"{item.detail} |"
        for item in report.checks
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "WORKBENCH_RELEASE_CLOSURE_RECONCILIATION_VERSION",
    "diff_workbench_release_closure_bundles",
    "reconcile_workbench_release_closure",
    "workbench_release_closure_reconciliation_markdown",
]
