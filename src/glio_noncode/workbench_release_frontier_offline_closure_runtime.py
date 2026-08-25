"""Fourteen-stage deterministic runtime for closing the D15 workbench handoff."""

from __future__ import annotations

from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workbench_release_frontier_offline_bundle import build_workbench_release_offline_bundle
from .workbench_release_frontier_offline_closure_boundary import (
    audit_workbench_release_closure_boundary,
)
from .workbench_release_frontier_offline_closure_certification import (
    certify_workbench_release_closure,
)
from .workbench_release_frontier_offline_closure_contracts import (
    WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_TOTAL,
    WORKBENCH_RELEASE_CLOSURE_RUNTIME_VERSION,
    WorkbenchReleaseClosureReplay,
    WorkbenchReleaseClosureRuntimeReport,
    WorkbenchReleaseClosureRuntimeStage,
    WorkbenchReleaseClosureState,
)
from .workbench_release_frontier_offline_closure_graph import build_workbench_release_closure_graph
from .workbench_release_frontier_offline_closure_indexes import (
    audit_workbench_release_closure_indexes,
    build_workbench_release_closure_indexes,
)
from .workbench_release_frontier_offline_closure_observability import (
    build_workbench_release_closure_observability,
)
from .workbench_release_frontier_offline_closure_reconciliation import (
    diff_workbench_release_closure_bundles,
    reconcile_workbench_release_closure,
)
from .workbench_release_frontier_offline_closure_schema import (
    audit_workbench_release_closure_schema,
    build_workbench_release_closure_schema,
)
from .workbench_release_frontier_offline_closure_summary import (
    audit_workbench_release_closure_summary,
    build_workbench_release_closure_summary,
)
from .workbench_release_frontier_offline_contracts import WorkbenchReleaseOfflineBundle


def _stage(
    ordinal: int,
    stage_id: str,
    input_address: str,
    value: Any,
    detail: str,
) -> WorkbenchReleaseClosureRuntimeStage:
    output_address = content_hash(
        {"stage_id": stage_id, "value": jsonable(value)},
        prefix="workbench-release-closure-stage-output",
    )
    body = {
        "stage_id": stage_id,
        "ordinal": ordinal,
        "state": WorkbenchReleaseClosureState.READY,
        "input_address": input_address,
        "output_address": output_address,
        "detail": detail,
    }
    return WorkbenchReleaseClosureRuntimeStage(
        **body,
        content_address=content_hash(body, prefix="workbench-release-closure-runtime-stage"),
    )


def _replay(
    left: WorkbenchReleaseOfflineBundle, right: WorkbenchReleaseOfflineBundle
) -> WorkbenchReleaseClosureReplay:
    delta = diff_workbench_release_closure_bundles(left, right)
    body = {
        "first_address": left.content_address,
        "second_address": right.content_address,
        "expected_address": left.content_address,
        "deterministic": delta.accepted and left.content_address == right.content_address,
        "accepted": delta.accepted and left.content_address == right.content_address,
    }
    return WorkbenchReleaseClosureReplay(
        **body,
        content_address=content_hash(body, prefix="workbench-release-closure-replay"),
    )


def run_workbench_release_closure_runtime(
    *,
    bundle_id: str = "workbench-release-public-bundle",
    run_id: str = "workbench-release-closure-runtime",
) -> WorkbenchReleaseClosureRuntimeReport:
    """Run source materialization plus every independent closure projection."""

    require_non_empty(bundle_id, "bundle_id")
    require_non_empty(run_id, "run_id")
    source_bundle = build_workbench_release_offline_bundle(
        bundle_id=bundle_id, run_id=f"{run_id}:source"
    )
    stages: list[WorkbenchReleaseClosureRuntimeStage] = []
    input_address = source_bundle.content_address

    def add(stage_id: str, value: Any, detail: str) -> None:
        nonlocal input_address
        item = _stage(len(stages) + 1, stage_id, input_address, value, detail)
        stages.append(item)
        input_address = item.output_address

    add(
        "source_bundle",
        source_bundle.to_dict(include_payloads=False),
        "materialize source D15 bundle",
    )
    boundary = audit_workbench_release_closure_boundary(source_bundle)
    add("boundary", boundary, "audit public boundary and forbidden keys")
    indexes = build_workbench_release_closure_indexes(source_bundle)
    add("indexes", indexes, "build ten bounded closure indexes")
    index_audit = audit_workbench_release_closure_indexes(source_bundle, indexes)
    add("index_audit", index_audit, "audit index conservation and addresses")
    reconciliation = reconcile_workbench_release_closure(source_bundle)
    add("reconciliation", reconciliation, "reconcile source projections and denominators")
    summary = build_workbench_release_closure_summary(source_bundle)
    add("summary", summary, "materialize operation, state, and issue summary")
    summary_audit = audit_workbench_release_closure_summary(summary)
    add("summary_audit", summary_audit, "audit summary conservation")
    certification = certify_workbench_release_closure(source_bundle)
    add("certification", certification, "issue ten-domain certification")
    observability = build_workbench_release_closure_observability(source_bundle)
    add("observability", observability, "materialize 184 closure events and 24 metrics")
    graph = build_workbench_release_closure_graph(source_bundle)
    add("graph", graph, "build connected public closure graph")
    schema = build_workbench_release_closure_schema()
    add("schema", schema, "materialize row schemas and public policy")
    schema_audit = audit_workbench_release_closure_schema(source_bundle, schema)
    add("schema_audit", schema_audit, "audit schema shape and row addresses")
    replay_left = build_workbench_release_offline_bundle(
        bundle_id=bundle_id, run_id=f"{run_id}:replay"
    )
    replay_right = build_workbench_release_offline_bundle(
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
            replay.accepted,
        )
    )
    final_value = {
        "accepted": accepted,
        "bundle_id": source_bundle.bundle_id,
        "stage_count": WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_TOTAL,
        "certification": certification.content_address,
        "graph": graph.content_address,
        "replay": replay.content_address,
    }
    add("finalize", final_value, "finalize closure release decision")
    state = WorkbenchReleaseClosureState.READY if accepted else WorkbenchReleaseClosureState.BLOCKED
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
    return WorkbenchReleaseClosureRuntimeReport(
        **body,
        content_address=content_hash(
            {"version": WORKBENCH_RELEASE_CLOSURE_RUNTIME_VERSION, **body},
            prefix="workbench-release-closure-runtime",
        ),
    )


__all__ = ["run_workbench_release_closure_runtime"]
