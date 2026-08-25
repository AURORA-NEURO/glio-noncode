"""Eight-domain certification over the D14 closure handoff."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .evidence_lifecycle_frontier_offline_closure_boundary import (
    audit_evidence_lifecycle_closure_boundary,
)
from .evidence_lifecycle_frontier_offline_closure_contracts import (
    EVIDENCE_LIFECYCLE_CLOSURE_ARTIFACT_COUNT,
    EVIDENCE_LIFECYCLE_CLOSURE_CERTIFICATION_VERSION,
    EVIDENCE_LIFECYCLE_CLOSURE_CHECK_PREFIX,
    EVIDENCE_LIFECYCLE_CLOSURE_EVALUATION_CHECK_COUNT,
    EVIDENCE_LIFECYCLE_CLOSURE_LINEAGE_EDGE_COUNT,
    EVIDENCE_LIFECYCLE_CLOSURE_QUEUE_COUNT,
    EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
    EVIDENCE_LIFECYCLE_CLOSURE_SCENARIO_COUNT,
    EVIDENCE_LIFECYCLE_CLOSURE_SOURCE_COUNT,
    EVIDENCE_LIFECYCLE_CLOSURE_STAGE_COUNT,
    EvidenceLifecycleClosureCertificationCheck,
    EvidenceLifecycleClosureCertificationDomain,
    EvidenceLifecycleClosureCertificationReport,
)
from .evidence_lifecycle_frontier_offline_closure_indexes import (
    audit_evidence_lifecycle_closure_indexes,
    build_evidence_lifecycle_closure_indexes,
)
from .evidence_lifecycle_frontier_offline_closure_reconciliation import (
    reconcile_evidence_lifecycle_closure,
)
from .evidence_lifecycle_frontier_offline_closure_summary import (
    audit_evidence_lifecycle_closure_summary,
    build_evidence_lifecycle_closure_summary,
)
from .evidence_lifecycle_frontier_offline_closure_support import (
    all_rows,
    forbidden_keys,
    payload,
    safe_relative_path,
)
from .evidence_lifecycle_frontier_offline_contracts import EvidenceLifecycleOfflineBundle
from .serialization import content_hash


def _check(
    check_id: str,
    domain: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
    evidence: tuple[str, ...],
) -> EvidenceLifecycleClosureCertificationCheck:
    body = {
        "check_id": check_id,
        "domain": domain,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
        "evidence": evidence,
    }
    return EvidenceLifecycleClosureCertificationCheck(
        **body, content_address=content_hash(body, prefix=EVIDENCE_LIFECYCLE_CLOSURE_CHECK_PREFIX)
    )


def certify_evidence_lifecycle_closure(
    bundle: EvidenceLifecycleOfflineBundle,
) -> EvidenceLifecycleClosureCertificationReport:
    """Issue a deterministic 48-check certification receipt."""

    rows = all_rows(bundle)
    fixture = payload(bundle, "fixture")
    catalog = payload(bundle, "catalog")
    evaluation = payload(bundle, "evaluation")
    lineage = payload(bundle, "lineage")
    release = payload(bundle, "release")
    replay = payload(bundle, "replay")
    metrics = payload(bundle, "metrics")
    boundary = audit_evidence_lifecycle_closure_boundary(bundle)
    indexes = build_evidence_lifecycle_closure_indexes(bundle)
    index_audit = audit_evidence_lifecycle_closure_indexes(bundle, indexes)
    reconciliation = reconcile_evidence_lifecycle_closure(bundle)
    summary = build_evidence_lifecycle_closure_summary(bundle)
    summary_audit = audit_evidence_lifecycle_closure_summary(summary)
    record_ids = {row.get("record_id") for row in rows["records"]}
    execution_ids = {row.get("record_id") for row in rows["executions"]}
    dispositions = Counter(str(row.get("disposition")) for row in rows["queue"])
    domains: list[tuple[str, str, tuple[tuple[str, bool, Any, Any, str, tuple[str, ...]], ...]]] = [
        (
            "manifest",
            "Manifest integrity",
            (
                (
                    "manifest-ready",
                    bundle.ready,
                    bundle.state,
                    "ready",
                    "root manifest is ready",
                    (bundle.content_address,),
                ),
                (
                    "manifest-artifacts",
                    len(bundle.artifacts) == EVIDENCE_LIFECYCLE_CLOSURE_ARTIFACT_COUNT,
                    len(bundle.artifacts),
                    EVIDENCE_LIFECYCLE_CLOSURE_ARTIFACT_COUNT,
                    "artifact denominator is conserved",
                    tuple(item.content_address for item in bundle.artifacts),
                ),
                (
                    "manifest-paths",
                    len({item.relative_path for item in bundle.artifacts}) == len(bundle.artifacts),
                    len({item.relative_path for item in bundle.artifacts}),
                    EVIDENCE_LIFECYCLE_CLOSURE_ARTIFACT_COUNT,
                    "artifact paths are unique",
                    tuple(item.content_address for item in bundle.artifacts),
                ),
                (
                    "manifest-addresses",
                    all(item.content_address for item in bundle.artifacts),
                    sum(bool(item.content_address) for item in bundle.artifacts),
                    EVIDENCE_LIFECYCLE_CLOSURE_ARTIFACT_COUNT,
                    "artifact addresses are present",
                    tuple(item.content_address for item in bundle.artifacts),
                ),
                (
                    "manifest-runtime-address",
                    bool(bundle.runtime_address),
                    bundle.runtime_address,
                    "addressed",
                    "runtime address is retained",
                    (bundle.runtime_address,),
                ),
                (
                    "manifest-boundary",
                    bool(bundle.boundary),
                    bundle.boundary,
                    "public_aggregate_non_patient",
                    "public aggregate boundary is explicit",
                    (bundle.content_address,),
                ),
            ),
        ),
        (
            "fixture",
            "Fixture and source integrity",
            (
                (
                    "fixture-records",
                    len(rows["records"]) == EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
                    len(rows["records"]),
                    EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
                    "records are conserved",
                    tuple(row["content_address"] for row in rows["records"]),
                ),
                (
                    "fixture-sources",
                    len(rows["sources"]) == EVIDENCE_LIFECYCLE_CLOSURE_SOURCE_COUNT,
                    len(rows["sources"]),
                    EVIDENCE_LIFECYCLE_CLOSURE_SOURCE_COUNT,
                    "sources are conserved",
                    tuple(row["content_address"] for row in rows["sources"]),
                ),
                (
                    "fixture-operations",
                    len(rows["operations"]) == 4,
                    len(rows["operations"]),
                    4,
                    "operations are conserved",
                    tuple(str(row.get("content_address")) for row in rows["operations"]),
                ),
                (
                    "fixture-roles",
                    Counter(row.get("role") for row in rows["records"])
                    == {"positive": 4, "control": 12},
                    dict(Counter(row.get("role") for row in rows["records"])),
                    {"positive": 4, "control": 12},
                    "positive and control roles are balanced",
                    tuple(row["content_address"] for row in rows["records"]),
                ),
                (
                    "fixture-scenarios",
                    len(rows["scenarios"]) == EVIDENCE_LIFECYCLE_CLOSURE_SCENARIO_COUNT,
                    len(rows["scenarios"]),
                    EVIDENCE_LIFECYCLE_CLOSURE_SCENARIO_COUNT,
                    "scenario denominator is conserved",
                    tuple(row["content_address"] for row in rows["scenarios"]),
                ),
                (
                    "fixture-context",
                    bool(fixture.get("context_key")) and bool(catalog.get("fixture_id")),
                    {
                        "context": fixture.get("context_key"),
                        "fixture_id": catalog.get("fixture_id"),
                    },
                    "present",
                    "fixture context is explicit",
                    (bundle.content_address,),
                ),
            ),
        ),
        (
            "evaluation",
            "Evaluation and join integrity",
            (
                (
                    "evaluation-executions",
                    len(rows["executions"]) == EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
                    len(rows["executions"]),
                    EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
                    "executions are conserved",
                    tuple(row["content_address"] for row in rows["executions"]),
                ),
                (
                    "evaluation-join",
                    execution_ids == record_ids,
                    len(execution_ids),
                    EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
                    "execution identities close records",
                    tuple(row["content_address"] for row in rows["executions"]),
                ),
                (
                    "evaluation-checks",
                    len(rows["checks"]) == EVIDENCE_LIFECYCLE_CLOSURE_EVALUATION_CHECK_COUNT,
                    len(rows["checks"]),
                    EVIDENCE_LIFECYCLE_CLOSURE_EVALUATION_CHECK_COUNT,
                    "evaluation checks are conserved",
                    tuple(row["content_address"] for row in rows["checks"]),
                ),
                (
                    "evaluation-record-coverage",
                    {row.get("record_id") for row in rows["checks"] if row.get("record_id")}
                    == record_ids,
                    len({row.get("record_id") for row in rows["checks"] if row.get("record_id")}),
                    EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
                    "each record has record-level checks",
                    tuple(row["content_address"] for row in rows["checks"]),
                ),
                (
                    "evaluation-accepted-field",
                    all("accepted" in row for row in rows["executions"]),
                    sum("accepted" in row for row in rows["executions"]),
                    EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
                    "execution acceptance is explicit",
                    tuple(row["content_address"] for row in rows["executions"]),
                ),
                (
                    "evaluation-source-address",
                    bool(evaluation.get("content_address")),
                    evaluation.get("content_address"),
                    "present",
                    "evaluation projection is addressed",
                    (str(evaluation.get("content_address")),),
                ),
            ),
        ),
        (
            "lineage",
            "Lineage integrity",
            (
                (
                    "lineage-edges",
                    len(rows["edges"]) == EVIDENCE_LIFECYCLE_CLOSURE_LINEAGE_EDGE_COUNT,
                    len(rows["edges"]),
                    EVIDENCE_LIFECYCLE_CLOSURE_LINEAGE_EDGE_COUNT,
                    "lineage edges are conserved",
                    tuple(row["content_address"] for row in rows["edges"]),
                ),
                (
                    "lineage-identities",
                    len({row.get("edge_id") for row in rows["edges"]}) == len(rows["edges"]),
                    len({row.get("edge_id") for row in rows["edges"]}),
                    EVIDENCE_LIFECYCLE_CLOSURE_LINEAGE_EDGE_COUNT,
                    "lineage identities are unique",
                    tuple(row["content_address"] for row in rows["edges"]),
                ),
                (
                    "lineage-addresses",
                    all(
                        str(row.get("content_address", "")).startswith("sha256:")
                        for row in rows["edges"]
                    ),
                    len(rows["edges"]),
                    EVIDENCE_LIFECYCLE_CLOSURE_LINEAGE_EDGE_COUNT,
                    "lineage edges are addressed",
                    tuple(row["content_address"] for row in rows["edges"]),
                ),
                (
                    "lineage-source",
                    {
                        row.get("parent_id")
                        for row in rows["edges"]
                        if str(row.get("parent_id", "")).startswith("src-")
                    }
                    >= {row.get("source_id") for row in rows["sources"]},
                    len(
                        {
                            row.get("parent_id")
                            for row in rows["edges"]
                            if str(row.get("parent_id", "")).startswith("src-")
                        }
                    ),
                    EVIDENCE_LIFECYCLE_CLOSURE_SOURCE_COUNT,
                    "lineage names source receipts",
                    (str(lineage.get("content_address")),),
                ),
                (
                    "lineage-record",
                    {
                        row.get("child_id")
                        for row in rows["edges"]
                        if str(row.get("child_id", "")).startswith("execution:")
                    }
                    >= {f"execution:{row.get('record_id')}" for row in rows["records"]},
                    len(
                        {
                            row.get("child_id")
                            for row in rows["edges"]
                            if str(row.get("child_id", "")).startswith("execution:")
                        }
                    ),
                    EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
                    "lineage names record receipts",
                    (str(lineage.get("content_address")),),
                ),
                (
                    "lineage-reconciled",
                    reconciliation.accepted,
                    reconciliation.passed_count,
                    len(reconciliation.checks),
                    "closure reconciliation accepts lineage",
                    (reconciliation.content_address,),
                ),
            ),
        ),
        (
            "queue-review",
            "Queue and review integrity",
            (
                (
                    "queue-count",
                    len(rows["queue"]) == EVIDENCE_LIFECYCLE_CLOSURE_QUEUE_COUNT,
                    len(rows["queue"]),
                    EVIDENCE_LIFECYCLE_CLOSURE_QUEUE_COUNT,
                    "queue items are conserved",
                    tuple(row["content_address"] for row in rows["queue"]),
                ),
                (
                    "queue-dispositions",
                    dispositions == {"ready_for_review": 4, "hold_for_repair": 12},
                    dict(dispositions),
                    {"ready_for_review": 4, "hold_for_repair": 12},
                    "queue dispositions are explicit",
                    tuple(row["content_address"] for row in rows["queue"]),
                ),
                (
                    "queue-record-join",
                    {row.get("record_id") for row in rows["queue"]} == record_ids,
                    len({row.get("record_id") for row in rows["queue"]}),
                    EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
                    "queue identities close records",
                    tuple(row["content_address"] for row in rows["queue"]),
                ),
                (
                    "review-count",
                    len(rows["reviews"]) == EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
                    len(rows["reviews"]),
                    EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
                    "review rows are conserved",
                    tuple(row["content_address"] for row in rows["reviews"]),
                ),
                (
                    "review-record-join",
                    {row.get("record_id") for row in rows["reviews"]} == record_ids,
                    len({row.get("record_id") for row in rows["reviews"]}),
                    EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
                    "review identities close records",
                    tuple(row["content_address"] for row in rows["reviews"]),
                ),
                (
                    "review-accepted-field",
                    all("accepted" in row and "release_state" in row for row in rows["reviews"]),
                    len(rows["reviews"]),
                    EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
                    "review decisions are explicit",
                    tuple(row["content_address"] for row in rows["reviews"]),
                ),
            ),
        ),
        (
            "runtime",
            "Runtime and replay integrity",
            (
                (
                    "runtime-stages",
                    len(rows["stages"]) == EVIDENCE_LIFECYCLE_CLOSURE_STAGE_COUNT,
                    len(rows["stages"]),
                    EVIDENCE_LIFECYCLE_CLOSURE_STAGE_COUNT,
                    "source runtime stages are conserved",
                    tuple(row["content_address"] for row in rows["stages"]),
                ),
                (
                    "runtime-sequence",
                    [row.get("sequence") for row in rows["stages"]] == list(range(1, 11)),
                    [row.get("sequence") for row in rows["stages"]],
                    list(range(1, 11)),
                    "source runtime is contiguous",
                    tuple(row["content_address"] for row in rows["stages"]),
                ),
                (
                    "runtime-output-addresses",
                    all(
                        str(row.get("output_address", "")).startswith("sha256:")
                        for row in rows["stages"]
                    ),
                    len(rows["stages"]),
                    EVIDENCE_LIFECYCLE_CLOSURE_STAGE_COUNT,
                    "stage outputs are addressed",
                    tuple(row["content_address"] for row in rows["stages"]),
                ),
                (
                    "runtime-replay",
                    bool(replay.get("accepted")),
                    replay.get("accepted"),
                    True,
                    "replay receipt is accepted",
                    (str(replay.get("content_address")),),
                ),
                (
                    "runtime-observability",
                    len(rows["events"]) == 26,
                    len(rows["events"]),
                    26,
                    "source runtime observability is conserved",
                    tuple(row["content_address"] for row in rows["events"]),
                ),
                (
                    "runtime-bundle-address",
                    bool(bundle.runtime_address),
                    bundle.runtime_address,
                    "present",
                    "runtime address joins root",
                    (bundle.runtime_address,),
                ),
            ),
        ),
        (
            "public",
            "Public boundary and index integrity",
            (
                (
                    "public-boundary",
                    boundary.accepted,
                    boundary.discovered_key_count,
                    "bounded",
                    "public boundary is accepted",
                    (boundary.content_address,),
                ),
                (
                    "public-forbidden-keys",
                    not forbidden_keys(fixture),
                    forbidden_keys(fixture),
                    (),
                    "fixture exposes no direct identity keys",
                    (bundle.content_address,),
                ),
                (
                    "public-paths",
                    all(safe_relative_path(item.relative_path) for item in bundle.artifacts),
                    len(bundle.artifacts),
                    EVIDENCE_LIFECYCLE_CLOSURE_ARTIFACT_COUNT,
                    "artifact paths are safe",
                    tuple(item.content_address for item in bundle.artifacts),
                ),
                (
                    "public-indexes",
                    indexes.accepted,
                    indexes.resource_counts,
                    "indexed",
                    "all closure resources are indexed",
                    (indexes.content_address,),
                ),
                (
                    "public-index-audit",
                    index_audit.accepted,
                    index_audit.passed_count,
                    len(index_audit.checks),
                    "index audit accepts",
                    (index_audit.content_address,),
                ),
                (
                    "public-source-uris",
                    all(str(row.get("uri", "")).startswith("https://") for row in rows["sources"]),
                    len(rows["sources"]),
                    EVIDENCE_LIFECYCLE_CLOSURE_SOURCE_COUNT,
                    "public sources use HTTPS",
                    tuple(row["content_address"] for row in rows["sources"]),
                ),
            ),
        ),
        (
            "release",
            "Release and summary integrity",
            (
                (
                    "release-accepted",
                    bool(release.get("accepted")),
                    release.get("accepted"),
                    True,
                    "release manifest is accepted",
                    (str(release.get("content_address")),),
                ),
                (
                    "release-reconciliation",
                    reconciliation.accepted,
                    reconciliation.passed_count,
                    len(reconciliation.checks),
                    "reconciliation is accepted",
                    (reconciliation.content_address,),
                ),
                (
                    "release-summary",
                    summary.accepted,
                    summary.counter_map.get("record_count"),
                    EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
                    "closure summary is accepted",
                    (summary.content_address,),
                ),
                (
                    "release-summary-audit",
                    summary_audit.accepted,
                    len(summary_audit.failed_check_ids),
                    0,
                    "summary audit has no failed checks",
                    (summary_audit.content_address,),
                ),
                (
                    "release-metric-denominator",
                    any(
                        item.get("metric_id") == "execution_acceptance_rate"
                        and item.get("denominator") == EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT
                        for item in metrics.get("metrics", ())
                    ),
                    True,
                    "metric denominator",
                    "release metrics retain denominator",
                    (str(metrics.get("content_address")),),
                ),
                (
                    "release-content-address",
                    bool(bundle.content_address),
                    bundle.content_address,
                    "present",
                    "root release address is present",
                    (bundle.content_address,),
                ),
            ),
        ),
    ]
    checks: list[EvidenceLifecycleClosureCertificationCheck] = []
    domain_reports: list[EvidenceLifecycleClosureCertificationDomain] = []
    for domain_id, title, definitions in domains:
        domain_checks = tuple(
            _check(check_id, domain_id, passed, observed, required, detail, evidence)
            for check_id, passed, observed, required, detail, evidence in definitions
        )
        checks.extend(domain_checks)
        domain_body = {
            "domain_id": domain_id,
            "title": title,
            "check_ids": tuple(item.check_id for item in domain_checks),
            "passed_count": sum(item.passed for item in domain_checks),
            "check_count": len(domain_checks),
            "accepted": all(item.passed for item in domain_checks),
        }
        domain_reports.append(
            EvidenceLifecycleClosureCertificationDomain(
                **domain_body,
                content_address=content_hash(
                    domain_body, prefix="evidence-lifecycle-closure-certification-domain"
                ),
            )
        )
    check_tuple = tuple(checks)
    body = {
        "version": EVIDENCE_LIFECYCLE_CLOSURE_CERTIFICATION_VERSION,
        "bundle_id": bundle.bundle_id,
        "artifact_count": len(bundle.artifacts),
        "check_count": len(check_tuple),
        "passed_check_count": sum(item.passed for item in check_tuple),
        "failed_check_count": sum(not item.passed for item in check_tuple),
        "coverage_percent": round(
            100 * sum(item.passed for item in check_tuple) / len(check_tuple), 4
        )
        if check_tuple
        else 0.0,
        "domains": tuple(domain_reports),
        "checks": check_tuple,
        "accepted": len(check_tuple) == 48 and all(item.passed for item in check_tuple),
    }
    return EvidenceLifecycleClosureCertificationReport(
        **body,
        content_address=content_hash(body, prefix="evidence-lifecycle-closure-certification"),
    )


__all__ = ["certify_evidence_lifecycle_closure"]
