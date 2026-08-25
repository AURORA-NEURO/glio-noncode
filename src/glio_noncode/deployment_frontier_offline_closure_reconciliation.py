"""Independent D16 denominator, join, and release reconciliation."""

from __future__ import annotations

from typing import Any

from .deployment_frontier_offline_closure_contracts import (
    DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_AUDIT_EVENT_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_DIAGNOSTIC_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_EVALUATION_CHECK_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_EVIDENCE_CELL_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_EXECUTION_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_LINEAGE_EDGE_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_OPERATION_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_QUEUE_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_RECORD_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_STAGE_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_SOURCE_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_TRACE_OBSERVATION_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_TRANSCRIPT_EVENT_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_VALIDATION_CELL_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_VIEW_COUNT,
    DeploymentFrontierClosureReconciliationCheck,
    DeploymentFrontierClosureReconciliationDelta,
    DeploymentFrontierClosureReconciliationReport,
)
from .deployment_frontier_offline_closure_support import all_rows, forbidden_keys, payload
from .deployment_frontier_offline_contracts import DeploymentFrontierOfflineBundle
from .serialization import content_hash

DEPLOYMENT_FRONTIER_CLOSURE_RECONCILIATION_VERSION = "deployment-frontier-closure-reconciliation-v1"


def _check(
    check_id: str,
    plane: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> DeploymentFrontierClosureReconciliationCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return DeploymentFrontierClosureReconciliationCheck(
        **body,
        content_address=content_hash(
            body, prefix="deployment-frontier-closure-reconciliation-check"
        ),
    )


def reconcile_deployment_frontier_closure(
    bundle: DeploymentFrontierOfflineBundle,
) -> DeploymentFrontierClosureReconciliationReport:
    rows = all_rows(bundle)
    source_ids = {str(row.get("source_id")) for row in rows["sources"]}
    record_ids = {str(row.get("record_id")) for row in rows["records"]}
    execution_ids = {str(row.get("record_id")) for row in rows["executions"]}
    check_record_ids = {str(row.get("record_id")) for row in rows["checks"]}
    validation_record_ids = {str(row.get("record_id")) for row in rows["validation"]}
    evidence_record_ids = {str(row.get("record_id")) for row in rows["evidence"]}
    view_record_ids = {str(row.get("record_id")) for row in rows["views"]}
    queue_record_ids = {str(row.get("record_id")) for row in rows["queue"]}
    diagnostic_record_ids = {str(row.get("record_id")) for row in rows["diagnostics"]}
    source_lineage_ids = {
        str(row.get("parent_id")) for row in rows["edges"] if row.get("relation") == "supports"
    }
    execution_lineage_ids = {
        str(row.get("child_id")) for row in rows["edges"] if row.get("relation") == "executes"
    }
    runtime_sequences = tuple(int(row.get("sequence", 0)) for row in rows["stages"])
    index_sequences = tuple(int(row.get("sequence", 0)) for row in rows["stage_index"])
    issue_count = sum(bool(row.get("issue_codes")) for row in rows["executions"])
    policy = payload(bundle, "policy")
    policy_ok = isinstance(policy, dict) and all(
        str(rule.get("allowed_scope")) in {"aggregate", "local"}
        and bool(rule.get("deny_if_sensitive"))
        for rule in policy.get("rules", ())
        if isinstance(rule, dict)
    )
    checks = (
        _check(
            "bundle-ready", "manifest", bundle.ready, bundle.ready, True, "source bundle is ready"
        ),
        _check(
            "artifact-count",
            "manifest",
            len(rows["artifacts"]) == DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT,
            len(rows["artifacts"]),
            DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT,
            "artifact denominator is conserved",
        ),
        _check(
            "artifact-identities",
            "manifest",
            len({row.get("artifact_id") for row in rows["artifacts"]})
            == DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT,
            len({row.get("artifact_id") for row in rows["artifacts"]}),
            DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT,
            "artifact identities are unique",
        ),
        _check(
            "artifact-paths",
            "manifest",
            len({row.get("relative_path") for row in rows["artifacts"]})
            == DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT,
            len({row.get("relative_path") for row in rows["artifacts"]}),
            DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT,
            "artifact paths are unique",
        ),
        _check(
            "artifact-addresses",
            "manifest",
            all(row.get("content_address") for row in rows["artifacts"]),
            sum(bool(row.get("content_address")) for row in rows["artifacts"]),
            DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT,
            "artifact projections are addressed",
        ),
        _check(
            "source-count",
            "fixture",
            len(rows["sources"]) == DEPLOYMENT_FRONTIER_CLOSURE_SOURCE_COUNT,
            len(rows["sources"]),
            DEPLOYMENT_FRONTIER_CLOSURE_SOURCE_COUNT,
            "source denominator is conserved",
        ),
        _check(
            "source-identities",
            "fixture",
            len(source_ids) == DEPLOYMENT_FRONTIER_CLOSURE_SOURCE_COUNT,
            len(source_ids),
            DEPLOYMENT_FRONTIER_CLOSURE_SOURCE_COUNT,
            "source identities are unique",
        ),
        _check(
            "source-https",
            "fixture",
            all(str(row.get("uri", "")).startswith("https://") for row in rows["sources"]),
            True,
            True,
            "source receipts use HTTPS",
        ),
        _check(
            "record-count",
            "fixture",
            len(rows["records"]) == DEPLOYMENT_FRONTIER_CLOSURE_RECORD_COUNT,
            len(rows["records"]),
            DEPLOYMENT_FRONTIER_CLOSURE_RECORD_COUNT,
            "record denominator is conserved",
        ),
        _check(
            "record-roles",
            "fixture",
            sum(row.get("role") == "positive" for row in rows["records"]) == 4
            and sum(row.get("role") == "control" for row in rows["records"]) == 12,
            {
                "positive": sum(row.get("role") == "positive" for row in rows["records"]),
                "control": sum(row.get("role") == "control" for row in rows["records"]),
            },
            {"positive": 4, "control": 12},
            "record roles are balanced",
        ),
        _check(
            "operation-count",
            "fixture",
            len(rows["operations"]) == DEPLOYMENT_FRONTIER_CLOSURE_OPERATION_COUNT,
            len(rows["operations"]),
            DEPLOYMENT_FRONTIER_CLOSURE_OPERATION_COUNT,
            "operation denominator is conserved",
        ),
        _check(
            "operation-balance",
            "fixture",
            all(
                row.get("record_ids") and len(row.get("record_ids")) == 4
                for row in rows["operations"]
            ),
            [len(row.get("record_ids", ())) for row in rows["operations"]],
            [4, 4, 4, 4],
            "each operation has four records",
        ),
        _check(
            "execution-count",
            "evaluation",
            len(rows["executions"]) == DEPLOYMENT_FRONTIER_CLOSURE_EXECUTION_COUNT,
            len(rows["executions"]),
            DEPLOYMENT_FRONTIER_CLOSURE_EXECUTION_COUNT,
            "execution denominator is conserved",
        ),
        _check(
            "execution-join",
            "evaluation",
            execution_ids == record_ids,
            len(execution_ids),
            len(record_ids),
            "executions join records",
        ),
        _check(
            "evaluation-count",
            "evaluation",
            len(rows["checks"]) == DEPLOYMENT_FRONTIER_CLOSURE_EVALUATION_CHECK_COUNT,
            len(rows["checks"]),
            DEPLOYMENT_FRONTIER_CLOSURE_EVALUATION_CHECK_COUNT,
            "evaluation checks are conserved",
        ),
        _check(
            "evaluation-coverage",
            "evaluation",
            check_record_ids == record_ids,
            len(check_record_ids),
            len(record_ids),
            "evaluation checks cover records",
        ),
        _check(
            "evaluation-pass",
            "evaluation",
            all(bool(row.get("passed")) for row in rows["checks"]),
            sum(bool(row.get("passed")) for row in rows["checks"]),
            len(rows["checks"]),
            "evaluation checks pass",
        ),
        _check(
            "validation-count",
            "validation",
            len(rows["validation"]) == DEPLOYMENT_FRONTIER_CLOSURE_VALIDATION_CELL_COUNT,
            len(rows["validation"]),
            DEPLOYMENT_FRONTIER_CLOSURE_VALIDATION_CELL_COUNT,
            "validation cells are conserved",
        ),
        _check(
            "validation-coverage",
            "validation",
            validation_record_ids == record_ids,
            len(validation_record_ids),
            len(record_ids),
            "validation covers records",
        ),
        _check(
            "validation-pass",
            "validation",
            all(bool(row.get("passed")) for row in rows["validation"]),
            sum(bool(row.get("passed")) for row in rows["validation"]),
            len(rows["validation"]),
            "validation cells pass",
        ),
        _check(
            "evidence-count",
            "evidence",
            len(rows["evidence"]) == DEPLOYMENT_FRONTIER_CLOSURE_EVIDENCE_CELL_COUNT,
            len(rows["evidence"]),
            DEPLOYMENT_FRONTIER_CLOSURE_EVIDENCE_CELL_COUNT,
            "evidence cells are conserved",
        ),
        _check(
            "evidence-coverage",
            "evidence",
            evidence_record_ids == record_ids,
            len(evidence_record_ids),
            len(record_ids),
            "evidence covers records",
        ),
        _check(
            "evidence-addresses",
            "evidence",
            all(row.get("input_address") and row.get("output_address") for row in rows["evidence"]),
            sum(
                bool(row.get("input_address") and row.get("output_address"))
                for row in rows["evidence"]
            ),
            len(rows["evidence"]),
            "evidence joins input and output",
        ),
        _check(
            "lineage-count",
            "lineage",
            len(rows["edges"]) == DEPLOYMENT_FRONTIER_CLOSURE_LINEAGE_EDGE_COUNT,
            len(rows["edges"]),
            DEPLOYMENT_FRONTIER_CLOSURE_LINEAGE_EDGE_COUNT,
            "lineage denominator is conserved",
        ),
        _check(
            "lineage-unique",
            "lineage",
            len({row.get("edge_id") for row in rows["edges"]}) == len(rows["edges"]),
            len({row.get("edge_id") for row in rows["edges"]}),
            len(rows["edges"]),
            "lineage identities are unique",
        ),
        _check(
            "lineage-sources",
            "lineage",
            source_lineage_ids <= source_ids and len(source_lineage_ids) == 4,
            {"used": len(source_lineage_ids), "declared": len(source_ids)},
            {"used": 4, "declared": len(source_ids)},
            "used sources are declared; unused receipts remain visible",
        ),
        _check(
            "lineage-executions",
            "lineage",
            execution_lineage_ids == {f"execution:{record_id}" for record_id in record_ids},
            len(execution_lineage_ids),
            len(record_ids),
            "every record has an execution edge",
        ),
        _check(
            "view-count",
            "review",
            len(rows["views"]) == DEPLOYMENT_FRONTIER_CLOSURE_VIEW_COUNT,
            len(rows["views"]),
            DEPLOYMENT_FRONTIER_CLOSURE_VIEW_COUNT,
            "view denominator is conserved",
        ),
        _check(
            "view-coverage",
            "review",
            view_record_ids == record_ids,
            len(view_record_ids),
            len(record_ids),
            "views cover records",
        ),
        _check(
            "queue-count",
            "review",
            len(rows["queue"]) == DEPLOYMENT_FRONTIER_CLOSURE_QUEUE_COUNT,
            len(rows["queue"]),
            DEPLOYMENT_FRONTIER_CLOSURE_QUEUE_COUNT,
            "queue denominator is conserved",
        ),
        _check(
            "queue-control-coverage",
            "review",
            queue_record_ids
            == {
                str(row.get("record_id")) for row in rows["records"] if row.get("role") == "control"
            },
            len(queue_record_ids),
            12,
            "every control is queued",
        ),
        _check(
            "diagnostic-count",
            "review",
            len(rows["diagnostics"]) == DEPLOYMENT_FRONTIER_CLOSURE_DIAGNOSTIC_COUNT,
            len(rows["diagnostics"]),
            DEPLOYMENT_FRONTIER_CLOSURE_DIAGNOSTIC_COUNT,
            "diagnostic denominator is conserved",
        ),
        _check(
            "diagnostic-records",
            "review",
            diagnostic_record_ids <= record_ids,
            len(diagnostic_record_ids),
            "record subset",
            "diagnostics reference known records",
        ),
        _check(
            "issue-visibility",
            "review",
            issue_count == DEPLOYMENT_FRONTIER_CLOSURE_QUEUE_COUNT,
            issue_count,
            DEPLOYMENT_FRONTIER_CLOSURE_QUEUE_COUNT,
            "issue executions match queue rows",
        ),
        _check(
            "runtime-count",
            "runtime",
            len(rows["stages"]) == DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_STAGE_COUNT,
            len(rows["stages"]),
            DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_STAGE_COUNT,
            "runtime denominator is conserved",
        ),
        _check(
            "runtime-sequence",
            "runtime",
            runtime_sequences
            == tuple(range(1, DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_STAGE_COUNT + 1)),
            runtime_sequences,
            "1..38",
            "runtime sequence is contiguous",
        ),
        _check(
            "stage-index",
            "runtime",
            index_sequences == runtime_sequences,
            len(index_sequences),
            len(runtime_sequences),
            "stage index matches runtime",
        ),
        _check(
            "audit-log",
            "runtime",
            len(rows["audit_events"]) == DEPLOYMENT_FRONTIER_CLOSURE_AUDIT_EVENT_COUNT,
            len(rows["audit_events"]),
            DEPLOYMENT_FRONTIER_CLOSURE_AUDIT_EVENT_COUNT,
            "audit log denominator is conserved",
        ),
        _check(
            "transcript",
            "runtime",
            len(rows["transcript_events"]) == DEPLOYMENT_FRONTIER_CLOSURE_TRANSCRIPT_EVENT_COUNT,
            len(rows["transcript_events"]),
            DEPLOYMENT_FRONTIER_CLOSURE_TRANSCRIPT_EVENT_COUNT,
            "transcript denominator is conserved",
        ),
        _check(
            "trace",
            "runtime",
            len(rows["trace_observations"]) == DEPLOYMENT_FRONTIER_CLOSURE_TRACE_OBSERVATION_COUNT,
            len(rows["trace_observations"]),
            DEPLOYMENT_FRONTIER_CLOSURE_TRACE_OBSERVATION_COUNT,
            "trace denominator is conserved",
        ),
        _check(
            "base-release",
            "release",
            all(
                bool(payload(bundle, name).get("accepted"))
                for name in ("reconciliation", "quality", "release", "handoff")
            ),
            True,
            True,
            "source release gates are accepted",
        ),
        _check(
            "policy-boundary",
            "public",
            policy_ok,
            policy_ok,
            True,
            "deployment policy denies sensitive access",
        ),
        _check(
            "public-key-policy",
            "public",
            not forbidden_keys(payload(bundle, "fixture")),
            forbidden_keys(payload(bundle, "fixture")),
            (),
            "fixture remains public aggregate",
        ),
        _check(
            "row-addresses",
            "public",
            all(row.get("content_address") for values in rows.values() for row in values),
            sum(bool(row.get("content_address")) for values in rows.values() for row in values),
            sum(len(values) for values in rows.values()),
            "all closure rows are addressed",
        ),
        _check(
            "control-count",
            "release",
            len(rows["controls"]) == 12,
            len(rows["controls"]),
            12,
            "control projection is complete",
        ),
        _check(
            "failure-count",
            "release",
            len(rows["failures"]) == 12,
            len(rows["failures"]),
            12,
            "failure projection is complete",
        ),
        _check(
            "root-accepted",
            "release",
            bundle.accepted,
            bundle.accepted,
            True,
            "root handoff remains accepted",
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {
        "version": DEPLOYMENT_FRONTIER_CLOSURE_RECONCILIATION_VERSION,
        "bundle_id": bundle.bundle_id,
        "checks": checks,
        "accepted": accepted,
    }
    return DeploymentFrontierClosureReconciliationReport(
        **body,
        content_address=content_hash(body, prefix="deployment-frontier-closure-reconciliation"),
    )


def diff_deployment_frontier_closure_bundles(
    left: DeploymentFrontierOfflineBundle,
    right: DeploymentFrontierOfflineBundle,
) -> DeploymentFrontierClosureReconciliationDelta:
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
    return DeploymentFrontierClosureReconciliationDelta(
        **body, content_address=content_hash(body, prefix="deployment-frontier-closure-delta")
    )


def deployment_frontier_closure_reconciliation_markdown(
    report: DeploymentFrontierClosureReconciliationReport,
) -> str:
    lines = [
        "# Deployment frontier closure reconciliation",
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
    "DEPLOYMENT_FRONTIER_CLOSURE_RECONCILIATION_VERSION",
    "deployment_frontier_closure_reconciliation_markdown",
    "diff_deployment_frontier_closure_bundles",
    "reconcile_deployment_frontier_closure",
]
