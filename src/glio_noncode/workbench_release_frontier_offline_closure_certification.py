"""Ten-domain, sixty-check certification for the D15 public closure."""

from __future__ import annotations

from typing import Any

from .serialization import content_hash
from .workbench_release_frontier_offline_closure_boundary import (
    audit_workbench_release_closure_boundary,
)
from .workbench_release_frontier_offline_closure_contracts import (
    WORKBENCH_RELEASE_CLOSURE_ARTIFACT_COUNT,
    WORKBENCH_RELEASE_CLOSURE_CERTIFICATION_CHECK_COUNT,
    WORKBENCH_RELEASE_CLOSURE_CERTIFICATION_DOMAIN_COUNT,
    WORKBENCH_RELEASE_CLOSURE_CERTIFICATION_VERSION,
    WORKBENCH_RELEASE_CLOSURE_DIAGNOSTIC_COUNT,
    WORKBENCH_RELEASE_CLOSURE_EVALUATION_CHECK_COUNT,
    WORKBENCH_RELEASE_CLOSURE_EVIDENCE_CELL_COUNT,
    WORKBENCH_RELEASE_CLOSURE_EXECUTION_COUNT,
    WORKBENCH_RELEASE_CLOSURE_LINEAGE_EDGE_COUNT,
    WORKBENCH_RELEASE_CLOSURE_QUEUE_COUNT,
    WORKBENCH_RELEASE_CLOSURE_RECORD_COUNT,
    WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT,
    WORKBENCH_RELEASE_CLOSURE_SOURCE_COUNT,
    WORKBENCH_RELEASE_CLOSURE_VALIDATION_CELL_COUNT,
    WorkbenchReleaseClosureCertificationCheck,
    WorkbenchReleaseClosureCertificationDomain,
    WorkbenchReleaseClosureCertificationReport,
)
from .workbench_release_frontier_offline_closure_reconciliation import (
    reconcile_workbench_release_closure,
)
from .workbench_release_frontier_offline_closure_support import (
    all_rows,
    forbidden_keys,
    payload,
)
from .workbench_release_frontier_offline_contracts import WorkbenchReleaseOfflineBundle


def _check(
    check_id: str,
    domain: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
    evidence: tuple[str, ...],
) -> WorkbenchReleaseClosureCertificationCheck:
    body = {
        "check_id": check_id,
        "domain": domain,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
        "evidence": tuple(evidence),
    }
    return WorkbenchReleaseClosureCertificationCheck(
        **body,
        content_address=content_hash(body, prefix="workbench-release-closure-certification-check"),
    )


def _domain(
    domain_id: str,
    title: str,
    checks: tuple[WorkbenchReleaseClosureCertificationCheck, ...],
) -> WorkbenchReleaseClosureCertificationDomain:
    body = {
        "domain_id": domain_id,
        "title": title,
        "check_ids": tuple(item.check_id for item in checks),
        "passed_count": sum(item.passed for item in checks),
        "check_count": len(checks),
        "accepted": all(item.passed for item in checks),
    }
    return WorkbenchReleaseClosureCertificationDomain(
        **body,
        content_address=content_hash(body, prefix="workbench-release-closure-certification-domain"),
    )


def certify_workbench_release_closure(
    bundle: WorkbenchReleaseOfflineBundle,
) -> WorkbenchReleaseClosureCertificationReport:
    """Issue a certification receipt over all public D15 closure planes."""

    rows = all_rows(bundle)
    boundary = audit_workbench_release_closure_boundary(bundle)
    reconciliation = reconcile_workbench_release_closure(bundle)
    artifact_ids = tuple(item.artifact_id for item in bundle.artifacts)
    source_payload = payload(bundle, "fixture")
    runtime_payload = payload(bundle, "runtime")
    source_ids = {str(row.get("source_id")) for row in rows["sources"]}
    record_ids = {str(row.get("record_id")) for row in rows["records"]}
    execution_ids = {str(row.get("record_id")) for row in rows["executions"]}
    evidence_ids = {str(row.get("record_id")) for row in rows["evidence"]}
    stage_ids = {str(row.get("stage_id")) for row in rows["stages"]}
    specs: tuple[tuple[str, str, str, bool, Any, Any, str, tuple[str, ...]], ...] = (
        (
            "manifest",
            "artifact-count",
            "artifact inventory",
            len(artifact_ids) == WORKBENCH_RELEASE_CLOSURE_ARTIFACT_COUNT,
            len(artifact_ids),
            WORKBENCH_RELEASE_CLOSURE_ARTIFACT_COUNT,
            "all source artifacts are represented",
            (bundle.content_address,),
        ),
        (
            "manifest",
            "artifact-unique",
            "unique artifact ids",
            len(set(artifact_ids)) == len(artifact_ids),
            len(set(artifact_ids)),
            len(artifact_ids),
            "artifact identifiers are unique",
            (bundle.content_address,),
        ),
        (
            "manifest",
            "artifact-addressed",
            "addressed artifacts",
            all(item.content_address for item in bundle.artifacts),
            sum(bool(item.content_address) for item in bundle.artifacts),
            len(artifact_ids),
            "every artifact has a content address",
            (bundle.content_address,),
        ),
        (
            "manifest",
            "artifact-paths",
            "unique safe paths",
            len({item.relative_path for item in bundle.artifacts}) == len(artifact_ids),
            len({item.relative_path for item in bundle.artifacts}),
            len(artifact_ids),
            "artifact paths are unique",
            (bundle.content_address,),
        ),
        (
            "manifest",
            "root-accepted",
            "source bundle accepted",
            bundle.accepted,
            bundle.accepted,
            True,
            "source handoff is accepted",
            (bundle.content_address,),
        ),
        (
            "manifest",
            "schema-present",
            "schema artifact",
            "schema" in artifact_ids,
            "schema" in artifact_ids,
            True,
            "schema is part of the manifest",
            (bundle.content_address,),
        ),
        (
            "fixture",
            "fixture-records",
            "fixture records",
            len(rows["records"]) == WORKBENCH_RELEASE_CLOSURE_RECORD_COUNT,
            len(rows["records"]),
            WORKBENCH_RELEASE_CLOSURE_RECORD_COUNT,
            "fixture records are complete",
            (bundle.content_address,),
        ),
        (
            "fixture",
            "fixture-sources",
            "fixture sources",
            len(source_ids) == WORKBENCH_RELEASE_CLOSURE_SOURCE_COUNT,
            len(source_ids),
            WORKBENCH_RELEASE_CLOSURE_SOURCE_COUNT,
            "fixture sources are complete",
            (bundle.content_address,),
        ),
        (
            "fixture",
            "fixture-operations",
            "fixture operations",
            len({str(row.get("operation")) for row in rows["records"]}) == 4,
            len({str(row.get("operation")) for row in rows["records"]}),
            4,
            "fixture operations are partitioned",
            (bundle.content_address,),
        ),
        (
            "fixture",
            "fixture-roles",
            "positive and control roles",
            {str(row.get("role")) for row in rows["records"]} == {"positive", "control"},
            {str(row.get("role")) for row in rows["records"]},
            {"positive", "control"},
            "fixture roles remain aggregate",
            (bundle.content_address,),
        ),
        (
            "fixture",
            "fixture-source-links",
            "source links",
            all(set(row.get("source_ids", ())) <= source_ids for row in rows["records"]),
            all(set(row.get("source_ids", ())) <= source_ids for row in rows["records"]),
            True,
            "records reference declared sources",
            (bundle.content_address,),
        ),
        (
            "fixture",
            "fixture-public",
            "fixture public keys",
            not forbidden_keys(source_payload),
            forbidden_keys(source_payload),
            (),
            "fixture excludes restricted identity keys",
            (bundle.content_address,),
        ),
        (
            "evaluation",
            "evaluation-count",
            "evaluation checks",
            len(rows["checks"]) == WORKBENCH_RELEASE_CLOSURE_EVALUATION_CHECK_COUNT,
            len(rows["checks"]),
            WORKBENCH_RELEASE_CLOSURE_EVALUATION_CHECK_COUNT,
            "evaluation checks are complete",
            (bundle.content_address,),
        ),
        (
            "evaluation",
            "evaluation-record-coverage",
            "evaluation record coverage",
            {str(row.get("record_id")) for row in rows["checks"]} == record_ids,
            len({str(row.get("record_id")) for row in rows["checks"]}),
            len(record_ids),
            "every record has checks",
            (bundle.content_address,),
        ),
        (
            "evaluation",
            "evaluation-pass",
            "evaluation pass status",
            all(bool(row.get("passed")) for row in rows["checks"]),
            sum(bool(row.get("passed")) for row in rows["checks"]),
            len(rows["checks"]),
            "all evaluation checks pass",
            (bundle.content_address,),
        ),
        (
            "evaluation",
            "execution-count",
            "executions",
            len(rows["executions"]) == WORKBENCH_RELEASE_CLOSURE_EXECUTION_COUNT,
            len(rows["executions"]),
            WORKBENCH_RELEASE_CLOSURE_EXECUTION_COUNT,
            "one execution per record",
            (bundle.content_address,),
        ),
        (
            "evaluation",
            "execution-join",
            "execution join",
            execution_ids == record_ids,
            len(execution_ids),
            len(record_ids),
            "executions join fixture records",
            (bundle.content_address,),
        ),
        (
            "evaluation",
            "issue-visibility",
            "issue-bearing executions",
            sum(bool(row.get("issue_codes")) for row in rows["executions"]) == 12,
            sum(bool(row.get("issue_codes")) for row in rows["executions"]),
            12,
            "issue-bearing executions remain visible",
            (bundle.content_address,),
        ),
        (
            "validation",
            "validation-count",
            "validation cells",
            len(rows["validation"]) == WORKBENCH_RELEASE_CLOSURE_VALIDATION_CELL_COUNT,
            len(rows["validation"]),
            WORKBENCH_RELEASE_CLOSURE_VALIDATION_CELL_COUNT,
            "validation matrix is complete",
            (bundle.content_address,),
        ),
        (
            "validation",
            "validation-coverage",
            "validation coverage",
            {str(row.get("record_id")) for row in rows["validation"]} == record_ids,
            len({str(row.get("record_id")) for row in rows["validation"]}),
            len(record_ids),
            "validation covers every record",
            (bundle.content_address,),
        ),
        (
            "validation",
            "validation-pass",
            "validation status",
            all(bool(row.get("passed")) for row in rows["validation"]),
            sum(bool(row.get("passed")) for row in rows["validation"]),
            len(rows["validation"]),
            "validation cells pass",
            (bundle.content_address,),
        ),
        (
            "validation",
            "evidence-count",
            "evidence cells",
            len(rows["evidence"]) == WORKBENCH_RELEASE_CLOSURE_EVIDENCE_CELL_COUNT,
            len(rows["evidence"]),
            WORKBENCH_RELEASE_CLOSURE_EVIDENCE_CELL_COUNT,
            "evidence cells are complete",
            (bundle.content_address,),
        ),
        (
            "validation",
            "evidence-coverage",
            "evidence coverage",
            evidence_ids == record_ids,
            len(evidence_ids),
            len(record_ids),
            "evidence covers every record",
            (bundle.content_address,),
        ),
        (
            "validation",
            "evidence-addressed",
            "evidence addresses",
            all(row.get("input_address") and row.get("output_address") for row in rows["evidence"]),
            sum(
                bool(row.get("input_address") and row.get("output_address"))
                for row in rows["evidence"]
            ),
            len(rows["evidence"]),
            "evidence cells link input and output",
            (bundle.content_address,),
        ),
        (
            "lineage",
            "lineage-count",
            "lineage edges",
            len(rows["edges"]) == WORKBENCH_RELEASE_CLOSURE_LINEAGE_EDGE_COUNT,
            len(rows["edges"]),
            WORKBENCH_RELEASE_CLOSURE_LINEAGE_EDGE_COUNT,
            "lineage edge count is conserved",
            (bundle.content_address,),
        ),
        (
            "lineage",
            "lineage-unique",
            "lineage identities",
            len({row.get("edge_id") for row in rows["edges"]}) == len(rows["edges"]),
            len({row.get("edge_id") for row in rows["edges"]}),
            len(rows["edges"]),
            "lineage identities are unique",
            (bundle.content_address,),
        ),
        (
            "lineage",
            "lineage-source-coverage",
            "source lineage coverage",
            {
                str(row.get("parent_id"))
                for row in rows["edges"]
                if row.get("relation") == "source_to_record"
            }
            == source_ids,
            len(
                {
                    str(row.get("parent_id"))
                    for row in rows["edges"]
                    if row.get("relation") == "source_to_record"
                }
            ),
            len(source_ids),
            "all sources have outgoing lineage",
            (bundle.content_address,),
        ),
        (
            "lineage",
            "lineage-record-coverage",
            "record lineage coverage",
            {
                str(row.get("parent_id"))
                for row in rows["edges"]
                if row.get("relation") == "record_to_execution"
            }
            == record_ids,
            len(
                {
                    str(row.get("parent_id"))
                    for row in rows["edges"]
                    if row.get("relation") == "record_to_execution"
                }
            ),
            len(record_ids),
            "all records have execution lineage",
            (bundle.content_address,),
        ),
        (
            "lineage",
            "lineage-runtime",
            "runtime lineage",
            len(stage_ids) == WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT,
            len(stage_ids),
            WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT,
            "runtime stage identity is retained",
            (bundle.content_address,),
        ),
        (
            "lineage",
            "lineage-root",
            "root lineage",
            bool(bundle.content_address),
            bool(bundle.content_address),
            True,
            "closure has a root address",
            (bundle.content_address,),
        ),
        (
            "review",
            "review-queue-count",
            "review queue rows",
            len(rows["queue"]) == WORKBENCH_RELEASE_CLOSURE_QUEUE_COUNT,
            len(rows["queue"]),
            WORKBENCH_RELEASE_CLOSURE_QUEUE_COUNT,
            "review queue is complete",
            (bundle.content_address,),
        ),
        (
            "review",
            "review-record-coverage",
            "review issue coverage",
            {str(row.get("record_id")) for row in rows["queue"]}
            == record_ids
            - {
                str(row.get("record_id"))
                for row in rows["records"]
                if row.get("role") == "positive"
            },
            len({str(row.get("record_id")) for row in rows["queue"]}),
            12,
            "every control has a review row",
            (bundle.content_address,),
        ),
        (
            "review",
            "review-priorities",
            "review priority vocabulary",
            {str(row.get("priority")) for row in rows["queue"]} <= {"normal", "high"},
            {str(row.get("priority")) for row in rows["queue"]},
            {"normal", "high"},
            "queue priority is bounded",
            (bundle.content_address,),
        ),
        (
            "review",
            "review-diagnostics",
            "diagnostic rows",
            len(rows["diagnostics"]) == WORKBENCH_RELEASE_CLOSURE_DIAGNOSTIC_COUNT,
            len(rows["diagnostics"]),
            WORKBENCH_RELEASE_CLOSURE_DIAGNOSTIC_COUNT,
            "diagnostics are complete",
            (bundle.content_address,),
        ),
        (
            "review",
            "review-diagnostic-coverage",
            "diagnostic coverage",
            {str(row.get("record_id")) for row in rows["diagnostics"]} == record_ids,
            len({str(row.get("record_id")) for row in rows["diagnostics"]}),
            len(record_ids),
            "diagnostics cover every record",
            (bundle.content_address,),
        ),
        (
            "review",
            "review-issue-conservation",
            "issue conservation",
            sum(bool(row.get("issue_codes")) for row in rows["executions"]) == len(rows["queue"]),
            sum(bool(row.get("issue_codes")) for row in rows["executions"]),
            len(rows["queue"]),
            "issue executions match review queue",
            (bundle.content_address,),
        ),
        (
            "runtime",
            "runtime-count",
            "runtime stages",
            len(rows["stages"]) == WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT,
            len(rows["stages"]),
            WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT,
            "runtime stages are complete",
            (bundle.content_address,),
        ),
        (
            "runtime",
            "runtime-ordinals",
            "runtime ordinals",
            tuple(row.get("ordinal") for row in rows["stages"])
            == tuple(range(1, WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT + 1)),
            tuple(row.get("ordinal") for row in rows["stages"]),
            "1..49",
            "runtime ordinals are contiguous",
            (bundle.content_address,),
        ),
        (
            "runtime",
            "runtime-stage-index",
            "stage index",
            len(rows["stage_index"]) == WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT,
            len(rows["stage_index"]),
            WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT,
            "stage index is complete",
            (bundle.content_address,),
        ),
        (
            "runtime",
            "runtime-payload",
            "runtime payload",
            isinstance(runtime_payload, dict),
            isinstance(runtime_payload, dict),
            True,
            "runtime payload is structured",
            (bundle.content_address,),
        ),
        (
            "runtime",
            "runtime-address",
            "runtime address",
            bool(bundle.runtime_address),
            bool(bundle.runtime_address),
            True,
            "runtime has an address",
            (bundle.content_address,),
        ),
        (
            "runtime",
            "runtime-release",
            "release acceptance",
            all(
                payload(bundle, name).get("accepted") is True
                for name in ("reconciliation", "quality", "release", "handoff")
            ),
            True,
            True,
            "source release gates are accepted",
            (bundle.content_address,),
        ),
        (
            "public",
            "boundary-accepted",
            "closure boundary",
            boundary.accepted,
            boundary.accepted,
            True,
            "closure boundary is accepted",
            (boundary.content_address,),
        ),
        (
            "public",
            "boundary-forbidden",
            "closure forbidden keys",
            boundary.forbidden_keys == (),
            boundary.forbidden_keys,
            (),
            "public boundary has no forbidden keys",
            (boundary.content_address,),
        ),
        (
            "public",
            "boundary-artifacts",
            "boundary artifacts",
            len(boundary.artifact_checks) == WORKBENCH_RELEASE_CLOSURE_ARTIFACT_COUNT,
            len(boundary.artifact_checks),
            WORKBENCH_RELEASE_CLOSURE_ARTIFACT_COUNT,
            "boundary audits every artifact",
            (boundary.content_address,),
        ),
        (
            "public",
            "public-fixture",
            "fixture public policy",
            not forbidden_keys(source_payload),
            forbidden_keys(source_payload),
            (),
            "fixture is aggregate-only",
            (boundary.content_address,),
        ),
        (
            "public",
            "public-content-addresses",
            "public row addresses",
            all(row.get("content_address") for values in rows.values() for row in values),
            sum(bool(row.get("content_address")) for values in rows.values() for row in values),
            sum(len(values) for values in rows.values()),
            "all closure rows are addressable",
            (boundary.content_address,),
        ),
        (
            "public",
            "public-policy",
            "aggregate-only policy",
            bool(payload(bundle, "policy").get("aggregate_only")),
            payload(bundle, "policy").get("aggregate_only"),
            True,
            "policy prohibits identity-level output",
            (boundary.content_address,),
        ),
        (
            "graph",
            "graph-seed",
            "graph source seed",
            bool(bundle.content_address),
            bool(bundle.content_address),
            True,
            "graph can be rooted",
            (bundle.content_address,),
        ),
        (
            "graph",
            "graph-records",
            "graph record nodes",
            len(record_ids) == WORKBENCH_RELEASE_CLOSURE_RECORD_COUNT,
            len(record_ids),
            WORKBENCH_RELEASE_CLOSURE_RECORD_COUNT,
            "graph retains records",
            (bundle.content_address,),
        ),
        (
            "graph",
            "graph-executions",
            "graph execution nodes",
            len(execution_ids) == WORKBENCH_RELEASE_CLOSURE_EXECUTION_COUNT,
            len(execution_ids),
            WORKBENCH_RELEASE_CLOSURE_EXECUTION_COUNT,
            "graph retains executions",
            (bundle.content_address,),
        ),
        (
            "graph",
            "graph-evidence",
            "graph evidence nodes",
            len(evidence_ids) == WORKBENCH_RELEASE_CLOSURE_EVIDENCE_CELL_COUNT,
            len(evidence_ids),
            WORKBENCH_RELEASE_CLOSURE_EVIDENCE_CELL_COUNT,
            "graph retains evidence",
            (bundle.content_address,),
        ),
        (
            "graph",
            "graph-lineage",
            "graph lineage nodes",
            len(rows["edges"]) == WORKBENCH_RELEASE_CLOSURE_LINEAGE_EDGE_COUNT,
            len(rows["edges"]),
            WORKBENCH_RELEASE_CLOSURE_LINEAGE_EDGE_COUNT,
            "graph retains lineage",
            (bundle.content_address,),
        ),
        (
            "graph",
            "graph-runtime",
            "graph runtime nodes",
            len(stage_ids) == WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT,
            len(stage_ids),
            WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT,
            "graph retains runtime",
            (bundle.content_address,),
        ),
        (
            "release",
            "reconciliation",
            "reconciliation accepted",
            reconciliation.accepted,
            reconciliation.accepted,
            True,
            "denominator reconciliation is accepted",
            (reconciliation.content_address,),
        ),
        (
            "release",
            "reconciliation-checks",
            "reconciliation checks",
            reconciliation.passed_count == len(reconciliation.checks),
            reconciliation.passed_count,
            len(reconciliation.checks),
            "all reconciliation checks pass",
            (reconciliation.content_address,),
        ),
        (
            "release",
            "source-handoff",
            "source handoff",
            bundle.accepted,
            bundle.accepted,
            True,
            "source handoff remains accepted",
            (bundle.content_address,),
        ),
        (
            "release",
            "source-schema",
            "source schema",
            "schema" in artifact_ids,
            "schema" in artifact_ids,
            True,
            "source schema is published",
            (bundle.content_address,),
        ),
        (
            "release",
            "source-report",
            "source report",
            "report" in artifact_ids,
            "report" in artifact_ids,
            True,
            "source report is published",
            (bundle.content_address,),
        ),
        (
            "release",
            "release-identity",
            "release identifier",
            bool(bundle.bundle_id),
            bool(bundle.bundle_id),
            True,
            "release identity is non-empty",
            (bundle.content_address,),
        ),
    )
    checks = tuple(
        _check(f"{domain}-{check_id}", domain, passed, observed, required, detail, evidence)
        for domain, check_id, _, passed, observed, required, detail, evidence in specs
    )
    domain_titles = {
        "manifest": "Manifest completeness",
        "fixture": "Fixture integrity",
        "evaluation": "Evaluation coverage",
        "validation": "Validation and evidence",
        "lineage": "Lineage continuity",
        "review": "Review and diagnostics",
        "runtime": "Runtime determinism",
        "public": "Public boundary",
        "graph": "Closure graph",
        "release": "Release readiness",
    }
    domains = tuple(
        _domain(
            domain, domain_titles[domain], tuple(item for item in checks if item.domain == domain)
        )
        for domain in domain_titles
    )
    body = {
        "version": WORKBENCH_RELEASE_CLOSURE_CERTIFICATION_VERSION,
        "bundle_id": bundle.bundle_id,
        "artifact_count": len(bundle.artifacts),
        "check_count": len(checks),
        "passed_check_count": sum(item.passed for item in checks),
        "failed_check_count": sum(not item.passed for item in checks),
        "coverage_percent": round(100.0 * sum(item.passed for item in checks) / len(checks), 2),
        "domains": domains,
        "checks": checks,
        "accepted": len(domains) == WORKBENCH_RELEASE_CLOSURE_CERTIFICATION_DOMAIN_COUNT
        and len(checks) == WORKBENCH_RELEASE_CLOSURE_CERTIFICATION_CHECK_COUNT
        and all(item.passed for item in checks),
    }
    return WorkbenchReleaseClosureCertificationReport(
        **body,
        content_address=content_hash(body, prefix="workbench-release-closure-certification"),
    )


__all__ = ["certify_workbench_release_closure"]
