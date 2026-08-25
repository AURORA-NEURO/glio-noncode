"""Twelve-stage deterministic runtime for the D13-D16 release closure."""

from __future__ import annotations

from typing import Any

from .frontier_release_closure_boundary import audit_frontier_release_boundary
from .frontier_release_closure_bundle import (
    FrontierReleaseSnapshot,
    build_frontier_release_snapshot,
)
from .frontier_release_closure_certification import certify_frontier_release
from .frontier_release_closure_contracts import (
    FRONTIER_RELEASE_CLOSURE_RUNTIME_STAGE_TOTAL,
    FrontierReleaseClosureState,
    FrontierReleaseReplay,
    FrontierReleaseRuntimeReport,
    FrontierReleaseRuntimeStage,
)
from .frontier_release_closure_failure_injection import (
    audit_frontier_release_failure_report,
    build_frontier_release_failure_report,
)
from .frontier_release_closure_graph import (
    audit_frontier_release_graph,
    build_frontier_release_graph,
)
from .frontier_release_closure_indexes import (
    audit_frontier_release_indexes,
    build_frontier_release_indexes,
)
from .frontier_release_closure_observability import (
    audit_frontier_release_observability,
    build_frontier_release_observability,
)
from .frontier_release_closure_plan import audit_frontier_release_plan, build_frontier_release_plan
from .frontier_release_closure_reconciliation import reconcile_frontier_release
from .frontier_release_closure_summary import (
    audit_frontier_release_summary,
    build_frontier_release_summary,
)
from .frontier_release_closure_schema import (
    audit_frontier_release_schema,
    build_frontier_release_schema,
)
from .serialization import content_hash, jsonable, require_non_empty


def _stage(
    ordinal: int,
    stage_id: str,
    input_address: str,
    value: Any,
    detail: str,
    accepted: bool = True,
) -> FrontierReleaseRuntimeStage:
    state = FrontierReleaseClosureState.READY if accepted else FrontierReleaseClosureState.BLOCKED
    output_address = content_hash(
        {"stage_id": stage_id, "value": jsonable(value), "state": state},
        prefix="frontier-release-stage-output",
    )
    body = {
        "ordinal": ordinal,
        "stage_id": stage_id,
        "state": state,
        "input_address": input_address,
        "output_address": output_address,
        "detail": detail,
    }
    return FrontierReleaseRuntimeStage(
        **body,
        content_address=content_hash(body, prefix="frontier-release-runtime-stage"),
    )


def _replay(
    first: FrontierReleaseSnapshot,
    second: FrontierReleaseSnapshot,
) -> FrontierReleaseReplay:
    body = {
        "first_address": first.content_address,
        "second_address": second.content_address,
        "expected_address": first.content_address,
        "deterministic": first.content_address == second.content_address,
        "accepted": first.content_address == second.content_address,
    }
    return FrontierReleaseReplay(
        **body,
        content_address=content_hash(body, prefix="frontier-release-replay"),
    )


def run_frontier_release_closure_runtime(
    *,
    bundle_id: str = "frontier-release-public-bundle",
    run_id: str = "frontier-release-closure-runtime",
) -> FrontierReleaseRuntimeReport:
    require_non_empty(bundle_id, "bundle_id")
    require_non_empty(run_id, "run_id")
    snapshot = build_frontier_release_snapshot(run_id=run_id, bundle_id=bundle_id)
    stages: list[FrontierReleaseRuntimeStage] = []
    input_address = snapshot.content_address

    def add(stage_id: str, value: Any, detail: str, accepted: bool = True) -> None:
        nonlocal input_address
        item = _stage(len(stages) + 1, stage_id, input_address, value, detail, accepted)
        stages.append(item)
        input_address = item.output_address

    add("snapshot", snapshot, "materialize four-domain release snapshot", snapshot.accepted)
    add("domains", snapshot.domains, "conserve D13-D16 domain runtimes")
    add("artifacts", snapshot.artifacts, "namespace all source artifact manifests")
    add("dependencies", snapshot.dependencies, "materialize forward-only release order")
    add(
        "gates",
        snapshot.gates,
        "evaluate six gates per domain",
        all(item.passed for item in snapshot.gates),
    )
    boundary = audit_frontier_release_boundary(snapshot)
    add(
        "boundary",
        boundary,
        "audit public keys, paths, identities, and addresses",
        boundary.accepted,
    )
    indexes = build_frontier_release_indexes(snapshot)
    add("indexes", indexes, "build seven address-only release indexes", indexes.accepted)
    index_audit = audit_frontier_release_indexes(snapshot, indexes)
    add("index_audit", index_audit, "audit release index conservation", index_audit.accepted)
    reconciliation = reconcile_frontier_release(snapshot)
    add(
        "reconciliation",
        reconciliation,
        "reconcile cross-domain denominators and dependencies",
        reconciliation.accepted,
    )
    summary = build_frontier_release_summary(snapshot)
    summary_audit = audit_frontier_release_summary(summary)
    add(
        "summary",
        {"summary": summary, "audit": summary_audit},
        "build and audit release counters",
        summary.accepted and summary_audit.accepted,
    )
    certification = certify_frontier_release(snapshot)
    schema = build_frontier_release_schema()
    schema_audit = audit_frontier_release_schema(snapshot, schema)
    plan = build_frontier_release_plan(snapshot)
    plan_audit = audit_frontier_release_plan(plan)
    observability = build_frontier_release_observability(snapshot)
    graph = build_frontier_release_graph(snapshot)
    failures = build_frontier_release_failure_report(snapshot)
    assurance_checks = (
        *audit_frontier_release_observability(observability),
        *audit_frontier_release_graph(graph),
        *audit_frontier_release_failure_report(failures),
    )
    assurance_accepted = (
        observability.accepted
        and graph.accepted
        and failures.accepted
        and all(item.passed for item in assurance_checks)
        and all(item.passed for item in schema_audit)
        and plan.accepted
        and all(item["passed"] for item in plan_audit)
    )
    add(
        "assurance",
        {
            "certification": certification,
            "schema": schema,
            "schema_audit": schema_audit,
            "plan": plan,
            "plan_audit": plan_audit,
            "observability": observability,
            "graph": graph,
            "failures": failures,
            "checks": assurance_checks,
        },
        "certify, observe, graph, schema, and rehearse release controls",
        certification.accepted and assurance_accepted,
    )
    replay_left = build_frontier_release_snapshot(run_id=run_id, bundle_id=bundle_id)
    replay_right = build_frontier_release_snapshot(run_id=run_id, bundle_id=bundle_id)
    replay = _replay(replay_left, replay_right)
    accepted = all(
        (
            snapshot.accepted,
            boundary.accepted,
            indexes.accepted,
            index_audit.accepted,
            reconciliation.accepted,
            summary.accepted,
            summary_audit.accepted,
            certification.accepted,
            observability.accepted,
            graph.accepted,
            failures.accepted,
            plan.accepted,
            all(item["passed"] for item in plan_audit),
            assurance_accepted,
            replay.accepted,
        )
    )
    add(
        "finalize",
        {"bundle_id": bundle_id, "accepted": accepted, "replay": replay},
        "finalize cross-domain release decision",
        accepted,
    )
    if len(stages) != FRONTIER_RELEASE_CLOSURE_RUNTIME_STAGE_TOTAL:
        accepted = False
    state = FrontierReleaseClosureState.READY if accepted else FrontierReleaseClosureState.BLOCKED
    body = {
        "run_id": run_id,
        "state": state,
        "stages": tuple(stages),
        "snapshot": snapshot,
        "boundary": boundary,
        "indexes": indexes,
        "index_audit": index_audit,
        "reconciliation": reconciliation,
        "summary": summary,
        "summary_audit": summary_audit,
        "certification": certification,
        "observability": observability,
        "graph": graph,
        "failures": failures,
        "plan": plan,
        "plan_audit": plan_audit,
        "replay": replay,
        "accepted": accepted,
    }
    return FrontierReleaseRuntimeReport(
        **body,
        content_address=content_hash(
            {"version": "frontier-release-runtime-v1", **body},
            prefix="frontier-release-runtime",
        ),
    )


__all__ = ["run_frontier_release_closure_runtime"]
