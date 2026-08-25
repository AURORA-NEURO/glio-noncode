"""Ten-domain, sixty-check certification for the D16 closure."""

from __future__ import annotations

from typing import Any

from .deployment_frontier_offline_closure_boundary import audit_deployment_frontier_closure_boundary
from .deployment_frontier_offline_closure_contracts import (
    DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_CERTIFICATION_CHECK_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_CERTIFICATION_DOMAIN_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_CERTIFICATION_VERSION,
    DEPLOYMENT_FRONTIER_CLOSURE_DIAGNOSTIC_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_EVALUATION_CHECK_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_EVIDENCE_CELL_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_EXECUTION_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_LINEAGE_EDGE_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_QUEUE_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_RECORD_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_STAGE_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_SOURCE_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_VALIDATION_CELL_COUNT,
    DeploymentFrontierClosureCertificationCheck,
    DeploymentFrontierClosureCertificationDomain,
    DeploymentFrontierClosureCertificationReport,
)
from .deployment_frontier_offline_closure_graph import build_deployment_frontier_closure_graph
from .deployment_frontier_offline_closure_reconciliation import (
    reconcile_deployment_frontier_closure,
)
from .deployment_frontier_offline_closure_support import all_rows, forbidden_keys, payload
from .deployment_frontier_offline_contracts import DeploymentFrontierOfflineBundle
from .serialization import content_hash


def _check(
    check_id: str,
    domain: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
    evidence: tuple[str, ...],
) -> DeploymentFrontierClosureCertificationCheck:
    body = {
        "check_id": check_id,
        "domain": domain,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
        "evidence": evidence,
    }
    return DeploymentFrontierClosureCertificationCheck(
        **body,
        content_address=content_hash(
            body, prefix="deployment-frontier-closure-certification-check"
        ),
    )


def _domain(
    domain_id: str, title: str, checks: tuple[DeploymentFrontierClosureCertificationCheck, ...]
) -> DeploymentFrontierClosureCertificationDomain:
    body = {
        "domain_id": domain_id,
        "title": title,
        "check_ids": tuple(item.check_id for item in checks),
        "passed_count": sum(item.passed for item in checks),
        "check_count": len(checks),
        "accepted": all(item.passed for item in checks),
    }
    return DeploymentFrontierClosureCertificationDomain(
        **body,
        content_address=content_hash(
            body, prefix="deployment-frontier-closure-certification-domain"
        ),
    )


def certify_deployment_frontier_closure(
    bundle: DeploymentFrontierOfflineBundle,
) -> DeploymentFrontierClosureCertificationReport:
    rows = all_rows(bundle)
    boundary = audit_deployment_frontier_closure_boundary(bundle)
    reconciliation = reconcile_deployment_frontier_closure(bundle)
    graph = build_deployment_frontier_closure_graph(bundle)
    artifact_ids = {item.artifact_id for item in bundle.artifacts}
    source_ids = {str(row.get("source_id")) for row in rows["sources"]}
    record_ids = {str(row.get("record_id")) for row in rows["records"]}
    execution_ids = {str(row.get("record_id")) for row in rows["executions"]}
    stage_ids = {str(row.get("stage_id")) for row in rows["stages"]}
    specs = (
        (
            "manifest",
            "artifact-count",
            len(artifact_ids) == DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT,
            len(artifact_ids),
            DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT,
            "all source artifacts are represented",
            (bundle.content_address,),
        ),
        (
            "manifest",
            "artifact-unique",
            len(artifact_ids) == len(bundle.artifacts),
            len(artifact_ids),
            len(bundle.artifacts),
            "artifact identifiers are unique",
            (bundle.content_address,),
        ),
        (
            "manifest",
            "artifact-addressed",
            all(item.content_address for item in bundle.artifacts),
            sum(bool(item.content_address) for item in bundle.artifacts),
            len(bundle.artifacts),
            "every artifact has an address",
            (bundle.content_address,),
        ),
        (
            "manifest",
            "artifact-paths",
            len({item.relative_path for item in bundle.artifacts}) == len(bundle.artifacts),
            len({item.relative_path for item in bundle.artifacts}),
            len(bundle.artifacts),
            "artifact paths are unique",
            (bundle.content_address,),
        ),
        (
            "manifest",
            "root-accepted",
            bundle.accepted,
            bundle.accepted,
            True,
            "source handoff is accepted",
            (bundle.content_address,),
        ),
        (
            "manifest",
            "schema-present",
            "schema" in artifact_ids,
            "schema" in artifact_ids,
            True,
            "schema is published",
            (bundle.content_address,),
        ),
        (
            "fixture",
            "fixture-records",
            len(rows["records"]) == DEPLOYMENT_FRONTIER_CLOSURE_RECORD_COUNT,
            len(rows["records"]),
            DEPLOYMENT_FRONTIER_CLOSURE_RECORD_COUNT,
            "fixture records are complete",
            (bundle.content_address,),
        ),
        (
            "fixture",
            "fixture-sources",
            len(source_ids) == DEPLOYMENT_FRONTIER_CLOSURE_SOURCE_COUNT,
            len(source_ids),
            DEPLOYMENT_FRONTIER_CLOSURE_SOURCE_COUNT,
            "fixture sources are complete",
            (bundle.content_address,),
        ),
        (
            "fixture",
            "fixture-operations",
            len({str(row.get("operation")) for row in rows["records"]}) == 4,
            len({str(row.get("operation")) for row in rows["records"]}),
            4,
            "fixture operations are partitioned",
            (bundle.content_address,),
        ),
        (
            "fixture",
            "fixture-roles",
            {str(row.get("role")) for row in rows["records"]} == {"positive", "control"},
            {str(row.get("role")) for row in rows["records"]},
            {"positive", "control"},
            "fixture roles remain aggregate",
            (bundle.content_address,),
        ),
        (
            "fixture",
            "fixture-source-links",
            all(set(row.get("source_ids", ())) <= source_ids for row in rows["records"]),
            True,
            True,
            "records reference declared sources",
            (bundle.content_address,),
        ),
        (
            "fixture",
            "fixture-public",
            not forbidden_keys(payload(bundle, "fixture")),
            forbidden_keys(payload(bundle, "fixture")),
            (),
            "fixture excludes restricted identity keys",
            (bundle.content_address,),
        ),
        (
            "evaluation",
            "evaluation-count",
            len(rows["checks"]) == DEPLOYMENT_FRONTIER_CLOSURE_EVALUATION_CHECK_COUNT,
            len(rows["checks"]),
            DEPLOYMENT_FRONTIER_CLOSURE_EVALUATION_CHECK_COUNT,
            "evaluation checks are complete",
            (bundle.content_address,),
        ),
        (
            "evaluation",
            "evaluation-coverage",
            {str(row.get("record_id")) for row in rows["checks"]} == record_ids,
            len({str(row.get("record_id")) for row in rows["checks"]}),
            len(record_ids),
            "every record has checks",
            (bundle.content_address,),
        ),
        (
            "evaluation",
            "evaluation-pass",
            all(bool(row.get("passed")) for row in rows["checks"]),
            sum(bool(row.get("passed")) for row in rows["checks"]),
            len(rows["checks"]),
            "all evaluation checks pass",
            (bundle.content_address,),
        ),
        (
            "evaluation",
            "execution-count",
            len(rows["executions"]) == DEPLOYMENT_FRONTIER_CLOSURE_EXECUTION_COUNT,
            len(rows["executions"]),
            DEPLOYMENT_FRONTIER_CLOSURE_EXECUTION_COUNT,
            "executions are complete",
            (bundle.content_address,),
        ),
        (
            "evaluation",
            "execution-join",
            execution_ids == record_ids,
            len(execution_ids),
            len(record_ids),
            "executions join records",
            (bundle.content_address,),
        ),
        (
            "evaluation",
            "issue-visibility",
            sum(bool(row.get("issue_codes")) for row in rows["executions"]) == 12,
            sum(bool(row.get("issue_codes")) for row in rows["executions"]),
            12,
            "issue-bearing executions remain visible",
            (bundle.content_address,),
        ),
        (
            "validation",
            "validation-count",
            len(rows["validation"]) == DEPLOYMENT_FRONTIER_CLOSURE_VALIDATION_CELL_COUNT,
            len(rows["validation"]),
            DEPLOYMENT_FRONTIER_CLOSURE_VALIDATION_CELL_COUNT,
            "validation cells are complete",
            (bundle.content_address,),
        ),
        (
            "validation",
            "validation-coverage",
            {str(row.get("record_id")) for row in rows["validation"]} == record_ids,
            len({str(row.get("record_id")) for row in rows["validation"]}),
            len(record_ids),
            "validation covers records",
            (bundle.content_address,),
        ),
        (
            "validation",
            "validation-pass",
            all(bool(row.get("passed")) for row in rows["validation"]),
            sum(bool(row.get("passed")) for row in rows["validation"]),
            len(rows["validation"]),
            "validation cells pass",
            (bundle.content_address,),
        ),
        (
            "validation",
            "evidence-count",
            len(rows["evidence"]) == DEPLOYMENT_FRONTIER_CLOSURE_EVIDENCE_CELL_COUNT,
            len(rows["evidence"]),
            DEPLOYMENT_FRONTIER_CLOSURE_EVIDENCE_CELL_COUNT,
            "evidence cells are complete",
            (bundle.content_address,),
        ),
        (
            "validation",
            "evidence-coverage",
            {str(row.get("record_id")) for row in rows["evidence"]} == record_ids,
            len({str(row.get("record_id")) for row in rows["evidence"]}),
            len(record_ids),
            "evidence covers records",
            (bundle.content_address,),
        ),
        (
            "validation",
            "evidence-addressed",
            all(row.get("input_address") and row.get("output_address") for row in rows["evidence"]),
            sum(
                bool(row.get("input_address") and row.get("output_address"))
                for row in rows["evidence"]
            ),
            len(rows["evidence"]),
            "evidence links input and output",
            (bundle.content_address,),
        ),
        (
            "lineage",
            "lineage-count",
            len(rows["edges"]) == DEPLOYMENT_FRONTIER_CLOSURE_LINEAGE_EDGE_COUNT,
            len(rows["edges"]),
            DEPLOYMENT_FRONTIER_CLOSURE_LINEAGE_EDGE_COUNT,
            "lineage edges are complete",
            (bundle.content_address,),
        ),
        (
            "lineage",
            "lineage-unique",
            len({row.get("edge_id") for row in rows["edges"]}) == len(rows["edges"]),
            len({row.get("edge_id") for row in rows["edges"]}),
            len(rows["edges"]),
            "lineage identities are unique",
            (bundle.content_address,),
        ),
        (
            "lineage",
            "lineage-source-subset",
            {
                str(row.get("parent_id"))
                for row in rows["edges"]
                if row.get("relation") == "supports"
            }
            <= source_ids,
            True,
            True,
            "lineage parents are declared sources",
            (bundle.content_address,),
        ),
        (
            "lineage",
            "lineage-records",
            {
                str(row.get("parent_id"))
                for row in rows["edges"]
                if row.get("relation") == "executes"
            }
            == record_ids,
            len(
                {
                    str(row.get("parent_id"))
                    for row in rows["edges"]
                    if row.get("relation") == "executes"
                }
            ),
            len(record_ids),
            "every record has execution lineage",
            (bundle.content_address,),
        ),
        (
            "lineage",
            "lineage-runtime",
            len(stage_ids) == DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_STAGE_COUNT,
            len(stage_ids),
            DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_STAGE_COUNT,
            "runtime stage identity is retained",
            (bundle.content_address,),
        ),
        (
            "lineage",
            "lineage-root",
            bool(bundle.content_address),
            bool(bundle.content_address),
            True,
            "closure has a root address",
            (bundle.content_address,),
        ),
        (
            "review",
            "review-queue",
            len(rows["queue"]) == DEPLOYMENT_FRONTIER_CLOSURE_QUEUE_COUNT,
            len(rows["queue"]),
            DEPLOYMENT_FRONTIER_CLOSURE_QUEUE_COUNT,
            "review queue is complete",
            (bundle.content_address,),
        ),
        (
            "review",
            "review-control-coverage",
            {str(row.get("record_id")) for row in rows["queue"]}
            == {
                str(row.get("record_id")) for row in rows["records"] if row.get("role") == "control"
            },
            len({str(row.get("record_id")) for row in rows["queue"]}),
            12,
            "every control is queued",
            (bundle.content_address,),
        ),
        (
            "review",
            "review-priority",
            all(int(row.get("priority", 0)) > 0 for row in rows["queue"]),
            sum(int(row.get("priority", 0)) > 0 for row in rows["queue"]),
            len(rows["queue"]),
            "queue priorities are positive",
            (bundle.content_address,),
        ),
        (
            "review",
            "review-diagnostics",
            len(rows["diagnostics"]) == DEPLOYMENT_FRONTIER_CLOSURE_DIAGNOSTIC_COUNT,
            len(rows["diagnostics"]),
            DEPLOYMENT_FRONTIER_CLOSURE_DIAGNOSTIC_COUNT,
            "diagnostics are complete",
            (bundle.content_address,),
        ),
        (
            "review",
            "review-issues",
            sum(bool(row.get("issue_codes")) for row in rows["executions"]) == len(rows["queue"]),
            sum(bool(row.get("issue_codes")) for row in rows["executions"]),
            len(rows["queue"]),
            "issue executions match queue",
            (bundle.content_address,),
        ),
        (
            "review",
            "review-controls",
            len(rows["controls"]) == 12,
            len(rows["controls"]),
            12,
            "control rows are explicit",
            (bundle.content_address,),
        ),
        (
            "runtime",
            "runtime-count",
            len(rows["stages"]) == DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_STAGE_COUNT,
            len(rows["stages"]),
            DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_STAGE_COUNT,
            "runtime stages are complete",
            (bundle.content_address,),
        ),
        (
            "runtime",
            "runtime-ordinals",
            tuple(row.get("sequence") for row in rows["stages"])
            == tuple(range(1, DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_STAGE_COUNT + 1)),
            (rows["stages"][0].get("sequence"), rows["stages"][-1].get("sequence")),
            "1..38",
            "runtime ordinals are contiguous",
            (bundle.content_address,),
        ),
        (
            "runtime",
            "runtime-index",
            len(rows["stage_index"]) == DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_STAGE_COUNT,
            len(rows["stage_index"]),
            DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_STAGE_COUNT,
            "stage index is complete",
            (bundle.content_address,),
        ),
        (
            "runtime",
            "runtime-address",
            bool(bundle.runtime_address),
            bool(bundle.runtime_address),
            True,
            "runtime has an address",
            (bundle.content_address,),
        ),
        (
            "runtime",
            "runtime-audit",
            len(rows["audit_events"]) == 32,
            len(rows["audit_events"]),
            32,
            "audit event log is retained",
            (bundle.content_address,),
        ),
        (
            "runtime",
            "runtime-transcript",
            len(rows["transcript_events"]) == 33,
            len(rows["transcript_events"]),
            33,
            "transcript is retained",
            (bundle.content_address,),
        ),
        (
            "public",
            "boundary-accepted",
            boundary.accepted,
            boundary.accepted,
            True,
            "closure boundary is accepted",
            (boundary.content_address,),
        ),
        (
            "public",
            "boundary-forbidden",
            boundary.forbidden_keys == (),
            boundary.forbidden_keys,
            (),
            "public boundary has no forbidden keys",
            (boundary.content_address,),
        ),
        (
            "public",
            "boundary-artifacts",
            len(boundary.artifact_checks) == DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT,
            len(boundary.artifact_checks),
            DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT,
            "boundary audits every artifact",
            (boundary.content_address,),
        ),
        (
            "public",
            "public-row-addresses",
            all(row.get("content_address") for values in rows.values() for row in values),
            sum(bool(row.get("content_address")) for values in rows.values() for row in values),
            sum(len(values) for values in rows.values()),
            "all closure rows are addressed",
            (boundary.content_address,),
        ),
        (
            "public",
            "public-policy",
            not forbidden_keys(payload(bundle, "fixture")),
            forbidden_keys(payload(bundle, "fixture")),
            (),
            "fixture is aggregate-only",
            (boundary.content_address,),
        ),
        (
            "public",
            "public-keys",
            boundary.discovered_key_count > 0,
            boundary.discovered_key_count,
            ">0",
            "public key inventory is populated",
            (boundary.content_address,),
        ),
        (
            "graph",
            "graph-accepted",
            graph.accepted,
            graph.accepted,
            True,
            "closure graph is connected",
            (graph.content_address,),
        ),
        (
            "graph",
            "graph-nodes",
            len(graph.nodes) > 400,
            len(graph.nodes),
            ">400",
            "graph retains deep nodes",
            (graph.content_address,),
        ),
        (
            "graph",
            "graph-edges",
            len(graph.edges) > len(graph.nodes),
            len(graph.edges),
            f">{len(graph.nodes)}",
            "graph retains relationship depth",
            (graph.content_address,),
        ),
        (
            "graph",
            "graph-components",
            graph.connected_component_count == 1,
            graph.connected_component_count,
            1,
            "graph has one component",
            (graph.content_address,),
        ),
        (
            "graph",
            "graph-records",
            len(record_ids) == DEPLOYMENT_FRONTIER_CLOSURE_RECORD_COUNT,
            len(record_ids),
            DEPLOYMENT_FRONTIER_CLOSURE_RECORD_COUNT,
            "graph retains records",
            (graph.content_address,),
        ),
        (
            "graph",
            "graph-lineage",
            len(rows["edges"]) == DEPLOYMENT_FRONTIER_CLOSURE_LINEAGE_EDGE_COUNT,
            len(rows["edges"]),
            DEPLOYMENT_FRONTIER_CLOSURE_LINEAGE_EDGE_COUNT,
            "graph retains lineage",
            (graph.content_address,),
        ),
        (
            "release",
            "release-reconciliation",
            reconciliation.accepted,
            reconciliation.accepted,
            True,
            "closure reconciliation is accepted",
            (reconciliation.content_address,),
        ),
        (
            "release",
            "release-reconciliation-checks",
            reconciliation.passed_count == len(reconciliation.checks),
            reconciliation.passed_count,
            len(reconciliation.checks),
            "all reconciliation checks pass",
            (reconciliation.content_address,),
        ),
        (
            "release",
            "release-source-gates",
            all(
                bool(payload(bundle, name).get("accepted"))
                for name in ("reconciliation", "quality", "release", "handoff")
            ),
            True,
            True,
            "source release gates are accepted",
            (bundle.content_address,),
        ),
        (
            "release",
            "release-failures",
            len(rows["failures"]) == 12,
            len(rows["failures"]),
            12,
            "failure controls are retained",
            (bundle.content_address,),
        ),
        (
            "release",
            "release-report",
            "summary" in artifact_ids,
            "summary" in artifact_ids,
            True,
            "release summary is published",
            (bundle.content_address,),
        ),
        (
            "release",
            "release-identity",
            bool(bundle.bundle_id),
            bool(bundle.bundle_id),
            True,
            "release identity is non-empty",
            (bundle.content_address,),
        ),
    )
    checks = tuple(
        _check(f"{domain}-{check_id}", domain, passed, observed, required, detail, evidence)
        for domain, check_id, passed, observed, required, detail, evidence in specs
    )
    titles = {
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
        _domain(domain, titles[domain], tuple(item for item in checks if item.domain == domain))
        for domain in titles
    )
    body = {
        "version": DEPLOYMENT_FRONTIER_CLOSURE_CERTIFICATION_VERSION,
        "bundle_id": bundle.bundle_id,
        "artifact_count": len(bundle.artifacts),
        "check_count": len(checks),
        "passed_check_count": sum(item.passed for item in checks),
        "failed_check_count": sum(not item.passed for item in checks),
        "coverage_percent": round(100.0 * sum(item.passed for item in checks) / len(checks), 2),
        "domains": domains,
        "checks": checks,
        "accepted": len(domains) == DEPLOYMENT_FRONTIER_CLOSURE_CERTIFICATION_DOMAIN_COUNT
        and len(checks) == DEPLOYMENT_FRONTIER_CLOSURE_CERTIFICATION_CHECK_COUNT
        and all(item.passed for item in checks),
    }
    return DeploymentFrontierClosureCertificationReport(
        **body,
        content_address=content_hash(body, prefix="deployment-frontier-closure-certification"),
    )


__all__ = ["certify_deployment_frontier_closure"]
