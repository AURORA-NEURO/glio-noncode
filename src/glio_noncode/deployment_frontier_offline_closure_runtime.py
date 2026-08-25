"""Fourteen-stage deterministic runtime for the D16 closure handoff."""

from __future__ import annotations

from typing import Any

from .deployment_frontier_offline_bundle import build_deployment_frontier_offline_bundle
from .deployment_frontier_offline_closure_boundary import audit_deployment_frontier_closure_boundary
from .deployment_frontier_offline_closure_certification import certify_deployment_frontier_closure
from .deployment_frontier_offline_closure_contracts import (
    DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_STAGE_TOTAL,
    DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_VERSION,
    DeploymentFrontierClosureReplay,
    DeploymentFrontierClosureRuntimeReport,
    DeploymentFrontierClosureRuntimeStage,
    DeploymentFrontierClosureState,
)
from .deployment_frontier_offline_closure_failure_injection import (
    build_deployment_frontier_closure_failure_report,
)
from .deployment_frontier_offline_closure_graph import build_deployment_frontier_closure_graph
from .deployment_frontier_offline_closure_indexes import (
    audit_deployment_frontier_closure_indexes,
    build_deployment_frontier_closure_indexes,
)
from .deployment_frontier_offline_closure_observability import (
    build_deployment_frontier_closure_observability,
)
from .deployment_frontier_offline_closure_reconciliation import (
    diff_deployment_frontier_closure_bundles,
    reconcile_deployment_frontier_closure,
)
from .deployment_frontier_offline_closure_schema import (
    audit_deployment_frontier_closure_schema,
    build_deployment_frontier_closure_schema,
)
from .deployment_frontier_offline_closure_summary import (
    audit_deployment_frontier_closure_summary,
    build_deployment_frontier_closure_summary,
)
from .deployment_frontier_offline_contracts import DeploymentFrontierOfflineBundle
from .serialization import content_hash, jsonable, require_non_empty


def _stage(
    ordinal: int, stage_id: str, input_address: str, value: Any, detail: str
) -> DeploymentFrontierClosureRuntimeStage:
    output_address = content_hash(
        {"stage_id": stage_id, "value": jsonable(value)},
        prefix="deployment-frontier-closure-stage-output",
    )
    body = {
        "stage_id": stage_id,
        "ordinal": ordinal,
        "state": DeploymentFrontierClosureState.READY,
        "input_address": input_address,
        "output_address": output_address,
        "detail": detail,
    }
    return DeploymentFrontierClosureRuntimeStage(
        **body,
        content_address=content_hash(body, prefix="deployment-frontier-closure-runtime-stage"),
    )


def _replay(
    left: DeploymentFrontierOfflineBundle, right: DeploymentFrontierOfflineBundle
) -> DeploymentFrontierClosureReplay:
    delta = diff_deployment_frontier_closure_bundles(left, right)
    body = {
        "first_address": left.content_address,
        "second_address": right.content_address,
        "expected_address": left.content_address,
        "deterministic": delta.accepted and left.content_address == right.content_address,
        "accepted": delta.accepted and left.content_address == right.content_address,
    }
    return DeploymentFrontierClosureReplay(
        **body, content_address=content_hash(body, prefix="deployment-frontier-closure-replay")
    )


def run_deployment_frontier_closure_runtime(
    *,
    bundle_id: str = "deployment-frontier-public-bundle",
    run_id: str = "deployment-frontier-closure-runtime",
) -> DeploymentFrontierClosureRuntimeReport:
    require_non_empty(bundle_id, "bundle_id")
    require_non_empty(run_id, "run_id")
    source_bundle = build_deployment_frontier_offline_bundle(
        bundle_id=bundle_id, run_id=f"{run_id}:source"
    )
    stages: list[DeploymentFrontierClosureRuntimeStage] = []
    input_address = source_bundle.content_address

    def add(stage_id: str, value: Any, detail: str) -> None:
        nonlocal input_address
        item = _stage(len(stages) + 1, stage_id, input_address, value, detail)
        stages.append(item)
        input_address = item.output_address

    add(
        "source_bundle",
        source_bundle.to_dict(include_payloads=False),
        "materialize source D16 bundle",
    )
    boundary = audit_deployment_frontier_closure_boundary(source_bundle)
    add("boundary", boundary, "audit public boundary and forbidden keys")
    indexes = build_deployment_frontier_closure_indexes(source_bundle)
    add("indexes", indexes, "build ten bounded closure indexes")
    index_audit = audit_deployment_frontier_closure_indexes(source_bundle, indexes)
    add("index_audit", index_audit, "audit index conservation and addresses")
    reconciliation = reconcile_deployment_frontier_closure(source_bundle)
    add("reconciliation", reconciliation, "reconcile source projections and denominators")
    summary = build_deployment_frontier_closure_summary(source_bundle)
    add("summary", summary, "materialize operation, state, and issue summary")
    summary_audit = audit_deployment_frontier_closure_summary(summary)
    add("summary_audit", summary_audit, "audit summary conservation")
    certification = certify_deployment_frontier_closure(source_bundle)
    add("certification", certification, "issue ten-domain certification")
    observability = build_deployment_frontier_closure_observability(source_bundle)
    add("observability", observability, "materialize 151 closure events and 24 metrics")
    graph = build_deployment_frontier_closure_graph(source_bundle)
    add("graph", graph, "build connected public closure graph")
    schema = build_deployment_frontier_closure_schema()
    schema_audit = audit_deployment_frontier_closure_schema(source_bundle, schema)
    add("schema", {"schema": schema, "audit": schema_audit}, "audit schema shape and row addresses")
    failure = build_deployment_frontier_closure_failure_report(source_bundle)
    add("failure_controls", failure, "run twelve structural negative controls")
    replay_left = build_deployment_frontier_offline_bundle(
        bundle_id=bundle_id, run_id=f"{run_id}:replay"
    )
    replay_right = build_deployment_frontier_offline_bundle(
        bundle_id=bundle_id, run_id=f"{run_id}:replay"
    )
    replay = _replay(replay_left, replay_right)
    add("replay", replay, "verify deterministic source replay")
    accepted = all(
        (
            boundary.accepted,
            indexes.accepted,
            index_audit.accepted,
            reconciliation.accepted,
            summary.accepted,
            summary_audit.accepted,
            certification.accepted,
            observability.accepted,
            graph.accepted,
            all(item.passed for item in schema_audit),
            failure.accepted,
            replay.accepted,
        )
    )
    final_value = {
        "accepted": accepted,
        "bundle_id": source_bundle.bundle_id,
        "stage_count": DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_STAGE_TOTAL,
        "certification": certification.content_address,
        "graph": graph.content_address,
        "failure": failure.content_address,
        "replay": replay.content_address,
    }
    add("finalize", final_value, "finalize closure release decision")
    state = (
        DeploymentFrontierClosureState.READY if accepted else DeploymentFrontierClosureState.BLOCKED
    )
    body = {
        "run_id": run_id,
        "state": state,
        "stages": tuple(stages),
        "bundle": source_bundle,
        "boundary": boundary,
        "indexes": indexes,
        "index_audit": index_audit,
        "reconciliation": reconciliation,
        "summary": summary,
        "summary_audit": summary_audit,
        "certification": certification,
        "observability": observability,
        "graph": graph,
        "replay": replay,
        "accepted": accepted,
    }
    return DeploymentFrontierClosureRuntimeReport(
        **body,
        content_address=content_hash(
            {"version": DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_VERSION, **body},
            prefix="deployment-frontier-closure-runtime",
        ),
    )


__all__ = ["run_deployment_frontier_closure_runtime"]
