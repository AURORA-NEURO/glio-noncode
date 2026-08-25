"""Independent cross-projection reconciliation for the D14 closure layer."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .evidence_lifecycle_frontier_offline_closure_contracts import (
    EVIDENCE_LIFECYCLE_CLOSURE_ARTIFACT_COUNT,
    EVIDENCE_LIFECYCLE_CLOSURE_CHECK_PREFIX,
    EVIDENCE_LIFECYCLE_CLOSURE_EVALUATION_CHECK_COUNT,
    EVIDENCE_LIFECYCLE_CLOSURE_LINEAGE_EDGE_COUNT,
    EVIDENCE_LIFECYCLE_CLOSURE_OPERATION_COUNT,
    EVIDENCE_LIFECYCLE_CLOSURE_QUEUE_COUNT,
    EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
    EVIDENCE_LIFECYCLE_CLOSURE_REVIEW_COUNT,
    EVIDENCE_LIFECYCLE_CLOSURE_SCENARIO_COUNT,
    EVIDENCE_LIFECYCLE_CLOSURE_SOURCE_COUNT,
    EVIDENCE_LIFECYCLE_CLOSURE_STAGE_COUNT,
    EvidenceLifecycleClosureReconciliationCheck,
    EvidenceLifecycleClosureReconciliationDelta,
    EvidenceLifecycleClosureReconciliationReport,
)
from .evidence_lifecycle_frontier_offline_closure_support import all_rows, payload
from .evidence_lifecycle_frontier_offline_contracts import EvidenceLifecycleOfflineBundle
from .serialization import content_hash

EVIDENCE_LIFECYCLE_CLOSURE_RECONCILIATION_VERSION = "evidence-lifecycle-closure-reconciliation-v1"


def _check(
    check_id: str,
    plane: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> EvidenceLifecycleClosureReconciliationCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return EvidenceLifecycleClosureReconciliationCheck(
        **body,
        content_address=content_hash(body, prefix=EVIDENCE_LIFECYCLE_CLOSURE_CHECK_PREFIX),
    )


def _addressed(rows: tuple[dict[str, Any], ...]) -> bool:
    return bool(rows) and all(
        str(row.get("content_address", "")).startswith("sha256:") for row in rows
    )


def reconcile_evidence_lifecycle_closure(
    bundle: EvidenceLifecycleOfflineBundle,
) -> EvidenceLifecycleClosureReconciliationReport:
    """Reconcile all public projections without depending on producer internals."""

    rows = all_rows(bundle)
    fixture = payload(bundle, "fixture")
    catalog = payload(bundle, "catalog")
    metrics = payload(bundle, "metrics")
    release = payload(bundle, "release")
    replay = payload(bundle, "replay")
    reconciliation = payload(bundle, "reconciliation")
    policy = payload(bundle, "policy")
    records = rows["records"]
    executions = rows["executions"]
    checks = rows["checks"]
    sources = rows["sources"]
    events = rows["events"]
    stages = rows["stages"]
    edges = rows["edges"]
    queue = rows["queue"]
    reviews = rows["reviews"]
    scenarios = rows["scenarios"]
    record_ids = tuple(str(row.get("record_id")) for row in records)
    execution_ids = tuple(str(row.get("record_id")) for row in executions)
    fixture_records = (
        tuple(str(row.get("record_id")) for row in fixture.get("records", ()))
        if isinstance(fixture, dict)
        else ()
    )
    catalog_records = (
        tuple(str(item) for item in catalog.get("record_ids", ()))
        if isinstance(catalog, dict)
        else ()
    )
    catalog_sources = (
        tuple(str(item) for item in catalog.get("source_ids", ()))
        if isinstance(catalog, dict)
        else ()
    )
    source_ids = tuple(str(row.get("source_id")) for row in sources)
    issue_count = sum(bool(row.get("issue_codes")) for row in executions)
    disposition_counts = Counter(str(row.get("disposition")) for row in queue)
    checks_out = (
        _check(
            "bundle-ready",
            "manifest",
            bundle.ready,
            bundle.state,
            "ready",
            "source bundle is accepted and ready",
        ),
        _check(
            "artifact-count",
            "manifest",
            len(bundle.artifacts) == EVIDENCE_LIFECYCLE_CLOSURE_ARTIFACT_COUNT,
            len(bundle.artifacts),
            EVIDENCE_LIFECYCLE_CLOSURE_ARTIFACT_COUNT,
            "closure conserves source artifacts",
        ),
        _check(
            "artifact-addresses",
            "manifest",
            all(
                str(row.get("content_address", "")).startswith(
                    "evidence-lifecycle-bundle-artifact:"
                )
                for row in rows["artifacts"]
            ),
            sum(
                str(row.get("content_address", "")).startswith(
                    "evidence-lifecycle-bundle-artifact:"
                )
                for row in rows["artifacts"]
            ),
            EVIDENCE_LIFECYCLE_CLOSURE_ARTIFACT_COUNT,
            "every artifact has an address",
        ),
        _check(
            "fixture-record-identities",
            "fixture",
            set(fixture_records) == set(record_ids),
            fixture_records,
            record_ids,
            "fixture and record projections agree",
        ),
        _check(
            "record-count",
            "fixture",
            len(records) == EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
            len(records),
            EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
            "record denominator is conserved",
        ),
        _check(
            "source-count",
            "fixture",
            len(sources) == EVIDENCE_LIFECYCLE_CLOSURE_SOURCE_COUNT,
            len(sources),
            EVIDENCE_LIFECYCLE_CLOSURE_SOURCE_COUNT,
            "source denominator is conserved",
        ),
        _check(
            "source-identities",
            "fixture",
            len(set(source_ids)) == len(source_ids) and all(source_ids),
            source_ids,
            EVIDENCE_LIFECYCLE_CLOSURE_SOURCE_COUNT,
            "sources are unique and identified",
        ),
        _check(
            "source-uri-policy",
            "fixture",
            all(str(row.get("uri", "")).startswith("https://") for row in sources),
            sum(str(row.get("uri", "")).startswith("https://") for row in sources),
            EVIDENCE_LIFECYCLE_CLOSURE_SOURCE_COUNT,
            "source receipts use HTTPS",
        ),
        _check(
            "role-denominator",
            "fixture",
            Counter(str(row.get("role")) for row in records) == {"positive": 4, "control": 12},
            dict(Counter(str(row.get("role")) for row in records)),
            {"positive": 4, "control": 12},
            "positive and control records are balanced",
        ),
        _check(
            "operation-denominator",
            "fixture",
            len(rows["operations"]) == EVIDENCE_LIFECYCLE_CLOSURE_OPERATION_COUNT
            and all(row.get("record_count") == 4 for row in rows["operations"]),
            len(rows["operations"]),
            EVIDENCE_LIFECYCLE_CLOSURE_OPERATION_COUNT,
            "operations are balanced four-record partitions",
        ),
        _check(
            "catalog-record-join",
            "join",
            set(catalog_records) == set(fixture_records),
            catalog_records,
            fixture_records,
            "catalog closes the fixture records",
        ),
        _check(
            "catalog-source-join",
            "join",
            catalog_sources == source_ids,
            catalog_sources,
            source_ids,
            "catalog closes the fixture sources",
        ),
        _check(
            "execution-count",
            "evaluation",
            len(executions) == EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
            len(executions),
            EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
            "every record has one execution",
        ),
        _check(
            "execution-join",
            "evaluation",
            set(execution_ids) == set(record_ids),
            execution_ids,
            record_ids,
            "execution identities join one-to-one",
        ),
        _check(
            "execution-addresses",
            "evaluation",
            _addressed(executions),
            sum(str(row.get("content_address", "")).startswith("sha256:") for row in executions),
            EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
            "execution receipts remain addressed",
        ),
        _check(
            "evaluation-check-count",
            "evaluation",
            len(checks) == EVIDENCE_LIFECYCLE_CLOSURE_EVALUATION_CHECK_COUNT,
            len(checks),
            EVIDENCE_LIFECYCLE_CLOSURE_EVALUATION_CHECK_COUNT,
            "evaluation check denominator is conserved",
        ),
        _check(
            "record-check-coverage",
            "evaluation",
            set(row.get("record_id") for row in checks if row.get("record_id")) == set(record_ids),
            len({row.get("record_id") for row in checks if row.get("record_id")}),
            EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
            "record-level evaluation checks cover every record",
        ),
        _check(
            "check-addresses",
            "evaluation",
            _addressed(checks),
            sum(str(row.get("content_address", "")).startswith("sha256:") for row in checks),
            EVIDENCE_LIFECYCLE_CLOSURE_EVALUATION_CHECK_COUNT,
            "evaluation receipts remain addressed",
        ),
        _check(
            "lineage-edge-count",
            "lineage",
            len(edges) == EVIDENCE_LIFECYCLE_CLOSURE_LINEAGE_EDGE_COUNT,
            len(edges),
            EVIDENCE_LIFECYCLE_CLOSURE_LINEAGE_EDGE_COUNT,
            "lineage edge denominator is conserved",
        ),
        _check(
            "lineage-edge-identities",
            "lineage",
            len({row.get("edge_id") for row in edges}) == len(edges),
            len({row.get("edge_id") for row in edges}),
            EVIDENCE_LIFECYCLE_CLOSURE_LINEAGE_EDGE_COUNT,
            "lineage edges have deterministic identities",
        ),
        _check(
            "reconciliation-accepted",
            "reconciliation",
            bool(isinstance(reconciliation, dict) and reconciliation.get("reconciled")),
            reconciliation.get("reconciled") if isinstance(reconciliation, dict) else None,
            True,
            "source reconciliation projection is accepted",
        ),
        _check(
            "release-accepted",
            "release",
            bool(isinstance(release, dict) and release.get("accepted")),
            release.get("accepted") if isinstance(release, dict) else None,
            True,
            "release projection is accepted",
        ),
        _check(
            "replay-accepted",
            "replay",
            bool(isinstance(replay, dict) and replay.get("accepted")),
            replay.get("accepted") if isinstance(replay, dict) else None,
            True,
            "replay projection is accepted",
        ),
        _check(
            "queue-count",
            "queue",
            len(queue) == EVIDENCE_LIFECYCLE_CLOSURE_QUEUE_COUNT,
            len(queue),
            EVIDENCE_LIFECYCLE_CLOSURE_QUEUE_COUNT,
            "review queue closes the record set",
        ),
        _check(
            "queue-dispositions",
            "queue",
            disposition_counts == {"ready_for_review": 4, "hold_for_repair": 12},
            dict(disposition_counts),
            {"ready_for_review": 4, "hold_for_repair": 12},
            "queue disposition is deterministic",
        ),
        _check(
            "review-count",
            "review",
            len(reviews) == EVIDENCE_LIFECYCLE_CLOSURE_REVIEW_COUNT,
            len(reviews),
            EVIDENCE_LIFECYCLE_CLOSURE_REVIEW_COUNT,
            "review projection closes the record set",
        ),
        _check(
            "review-identities",
            "review",
            {row.get("record_id") for row in reviews} == set(record_ids),
            len({row.get("record_id") for row in reviews}),
            EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
            "review rows join records",
        ),
        _check(
            "scenario-count",
            "fixture",
            len(scenarios) == EVIDENCE_LIFECYCLE_CLOSURE_SCENARIO_COUNT,
            len(scenarios),
            EVIDENCE_LIFECYCLE_CLOSURE_SCENARIO_COUNT,
            "scenario matrix denominator is conserved",
        ),
        _check(
            "runtime-stage-count",
            "runtime",
            len(stages) == EVIDENCE_LIFECYCLE_CLOSURE_STAGE_COUNT
            and [row.get("sequence") for row in stages] == list(range(1, 11)),
            len(stages),
            EVIDENCE_LIFECYCLE_CLOSURE_STAGE_COUNT,
            "source runtime stages are contiguous",
        ),
        _check(
            "observability-event-count",
            "observability",
            len(events) == 26,
            len(events),
            26,
            "source observability remains available",
        ),
        _check(
            "policy-exclusions",
            "boundary",
            isinstance(policy, dict) and bool(policy.get("excluded_uses")),
            len(policy.get("excluded_uses", ())) if isinstance(policy, dict) else 0,
            1,
            "privacy policy projection remains explicit",
        ),
        _check(
            "metric-denominator",
            "summary",
            any(
                row.get("metric_id") == "execution_acceptance_rate"
                and row.get("denominator") == EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT
                for row in (metrics.get("metrics", ()) if isinstance(metrics, dict) else ())
            ),
            True,
            EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
            "metric denominator joins record count",
        ),
        _check(
            "issue-visibility",
            "summary",
            issue_count == 13,
            issue_count,
            13,
            "all executions retain issue or empty outcome visibility",
        ),
        _check(
            "all-resource-addresses",
            "address",
            all(
                bool(row.get("content_address"))
                for key, value in rows.items()
                if key not in {"states"}
                for row in value
            ),
            {key: len(value) for key, value in rows.items() if key not in {"states"}},
            "addressed",
            "closure rows are content-addressed",
        ),
    )
    accepted = all(item.passed for item in checks_out)
    body = {
        "version": EVIDENCE_LIFECYCLE_CLOSURE_RECONCILIATION_VERSION,
        "bundle_id": bundle.bundle_id,
        "checks": checks_out,
        "accepted": accepted,
    }
    return EvidenceLifecycleClosureReconciliationReport(
        **body,
        content_address=content_hash(body, prefix="evidence-lifecycle-closure-reconciliation"),
    )


def diff_evidence_lifecycle_closure_bundles(
    left: EvidenceLifecycleOfflineBundle, right: EvidenceLifecycleOfflineBundle
) -> EvidenceLifecycleClosureReconciliationDelta:
    """Compare two hydrated handoffs by artifact bytes and projection counts."""

    left_artifacts = {item.artifact_id: item.content_address for item in left.artifacts}
    right_artifacts = {item.artifact_id: item.content_address for item in right.artifacts}
    changed_artifacts = tuple(
        sorted(
            key
            for key in set(left_artifacts) | set(right_artifacts)
            if left_artifacts.get(key) != right_artifacts.get(key)
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
        "changed_artifacts": changed_artifacts,
        "changed_counts": changed_counts,
        "accepted": not changed_artifacts and not changed_counts,
    }
    return EvidenceLifecycleClosureReconciliationDelta(
        **body, content_address=content_hash(body, prefix="evidence-lifecycle-closure-delta")
    )


def evidence_lifecycle_closure_reconciliation_markdown(
    report: EvidenceLifecycleClosureReconciliationReport,
) -> str:
    lines = [
        "# Evidence lifecycle closure reconciliation",
        "",
        f"Bundle: `{report.bundle_id}`",
        f"Accepted: `{str(report.accepted).lower()}`",
        f"Checks: `{report.passed_count}/{len(report.checks)}`",
        "",
        "| Check | Plane | State | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for item in report.checks:
        state = "pass" if item.passed else "hold"
        lines.append(f"| `{item.check_id}` | `{item.plane}` | `{state}` | {item.detail} |")
    return "\n".join(lines) + "\n"


__all__ = [
    "EVIDENCE_LIFECYCLE_CLOSURE_RECONCILIATION_VERSION",
    "diff_evidence_lifecycle_closure_bundles",
    "evidence_lifecycle_closure_reconciliation_markdown",
    "reconcile_evidence_lifecycle_closure",
]
