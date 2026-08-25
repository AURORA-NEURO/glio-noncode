"""Runtime orchestration for the public D01-D16 release closure."""

from __future__ import annotations

from typing import Any

from .program_release_closure_boundary import audit_program_release_closure_boundary
from .program_release_closure_bundle import build_program_release_snapshot
from .program_release_closure_certification import (
    audit_program_release_certification,
    certify_program_release_closure,
)
from .program_release_closure_contracts import (
    ProgramReleaseClosureState,
    ProgramReleaseReplay,
    ProgramReleaseRuntimeReport,
    ProgramReleaseRuntimeStage,
)
from .program_release_closure_failure_injection import (
    audit_program_release_failure_injections,
    run_program_release_failure_injections,
)
from .program_release_closure_graph import audit_program_release_graph, build_program_release_graph
from .program_release_closure_indexes import (
    audit_program_release_closure_indexes,
    build_program_release_closure_indexes,
)
from .program_release_closure_observability import (
    audit_program_release_observability,
    build_program_release_observability,
)
from .program_release_closure_operations import (
    audit_program_release_operational_matrix,
    build_program_release_operational_matrix,
)
from .program_release_closure_plan import (
    audit_program_release_closure_plan,
    build_program_release_closure_plan,
)
from .program_release_closure_reconciliation import reconcile_program_release_closure
from .program_release_closure_summary import (
    audit_program_release_closure_summary,
    build_program_release_closure_summary,
)
from .program_release_closure_views import (
    audit_program_release_review_views,
    build_program_release_review_views,
)
from .program_runtime_offline_bundle import build_program_runtime_offline_bundle
from .program_runtime_offline_contracts import ProgramRuntimeOfflineBundle
from .serialization import content_hash, require_non_empty


def _stage(
    ordinal: int,
    stage_id: str,
    input_address: str,
    output_address: str,
    accepted: bool,
    detail: str,
) -> ProgramReleaseRuntimeStage:
    state = ProgramReleaseClosureState.READY if accepted else ProgramReleaseClosureState.BLOCKED
    body = {
        "ordinal": ordinal,
        "stage_id": stage_id,
        "state": state,
        "input_address": input_address,
        "output_address": output_address,
        "detail": detail,
    }
    return ProgramReleaseRuntimeStage(
        **body, content_address=content_hash(body, prefix="program-release-runtime-stage")
    )


def _stage_result(value: Any) -> tuple[bool, str]:
    if isinstance(value, dict):
        return bool(value.get("accepted", False)), str(value.get("content_address", ""))
    if isinstance(value, tuple):
        if all(hasattr(item, "passed") for item in value):
            accepted = all(getattr(item, "passed", False) for item in value)
        else:
            accepted = all(_stage_result(item)[0] for item in value)
        return accepted, content_hash(value, prefix="program-release-stage-audit")
    return bool(getattr(value, "accepted", False)), str(getattr(value, "content_address", ""))


def _make_stage(
    ordinal: int, stage_id: str, previous: str, value: Any, detail: str
) -> ProgramReleaseRuntimeStage:
    accepted, address = _stage_result(value)
    return _stage(ordinal, stage_id, previous, address, accepted, detail)


def run_program_release_closure(
    source_bundle: ProgramRuntimeOfflineBundle | None = None,
    *,
    run_id: str = "glio-noncode-program-release-closure-run",
    bundle_id: str = "glio-noncode-program-release-closure",
) -> ProgramReleaseRuntimeReport:
    """Run all closure planes over one source handoff and replay the projection."""

    require_non_empty(run_id, "run_id")
    require_non_empty(bundle_id, "bundle_id")
    source = source_bundle or build_program_runtime_offline_bundle(
        bundle_id=bundle_id, run_id=run_id
    )
    snapshot = build_program_release_snapshot(source, bundle_id=bundle_id, run_id=run_id)
    stages: list[ProgramReleaseRuntimeStage] = []
    stages.append(
        _stage(
            1,
            "source-bundle",
            "",
            source.content_address,
            source.ready,
            "reuse or build source offline handoff",
        )
    )
    stages.append(
        _stage(
            2,
            "aggregate-snapshot",
            stages[-1].output_address,
            snapshot.content_address,
            snapshot.accepted,
            "project D01-D16 aggregate snapshot",
        )
    )
    stages.append(
        _stage(
            3,
            "domain-registry",
            stages[-1].output_address,
            content_hash(snapshot.domains, prefix="program-release-domains"),
            all(item.accepted for item in snapshot.domains),
            "register sixteen domain receipts",
        )
    )
    stages.append(
        _stage(
            4,
            "artifact-registry",
            stages[-1].output_address,
            content_hash(snapshot.artifacts, prefix="program-release-artifacts"),
            bool(snapshot.artifacts),
            "index eighteen portable artifacts",
        )
    )
    stages.append(
        _stage(
            5,
            "dependency-dag",
            stages[-1].output_address,
            content_hash(snapshot.dependencies, prefix="program-release-dependencies"),
            len(snapshot.dependencies) == 120,
            "materialize complete ordered dependency matrix",
        )
    )
    stages.append(
        _stage(
            6,
            "release-gates",
            stages[-1].output_address,
            content_hash(snapshot.gates, prefix="program-release-gates"),
            all(item.passed for item in snapshot.gates),
            "evaluate six gates per domain",
        )
    )
    boundary = audit_program_release_closure_boundary(snapshot)
    stages.append(
        _make_stage(
            7,
            "boundary",
            stages[-1].output_address,
            {
                "accepted": all(item.passed for item in boundary),
                "content_address": content_hash(boundary, prefix="program-release-boundary"),
            },
            "validate public aggregate boundary",
        )
    )
    indexes = build_program_release_closure_indexes(snapshot)
    index_audit = audit_program_release_closure_indexes(snapshot, indexes)
    stages.append(
        _make_stage(
            8, "indexes", stages[-1].output_address, index_audit, "audit address-only query indexes"
        )
    )
    reconciliation = reconcile_program_release_closure(snapshot, source)
    stages.append(
        _make_stage(
            9,
            "reconciliation",
            stages[-1].output_address,
            reconciliation,
            "reconcile source and aggregate denominators",
        )
    )
    summary = build_program_release_closure_summary(snapshot, source)
    summary_audit = audit_program_release_closure_summary(summary, source)
    stages.append(
        _make_stage(
            10, "summary", stages[-1].output_address, summary_audit, "publish denominator summary"
        )
    )
    certification = certify_program_release_closure(snapshot)
    observability = build_program_release_observability(snapshot)
    graph = build_program_release_graph(snapshot)
    failures = run_program_release_failure_injections(snapshot)
    plan = build_program_release_closure_plan(snapshot)
    plan_audit = audit_program_release_closure_plan(plan)
    operational = build_program_release_operational_matrix(snapshot)
    operational_audit = audit_program_release_operational_matrix(operational)
    views = build_program_release_review_views(snapshot)
    views_audit = audit_program_release_review_views(views, snapshot)
    assurance_values = (
        audit_program_release_certification(certification, snapshot),
        audit_program_release_observability(observability),
        audit_program_release_graph(graph, snapshot),
        audit_program_release_failure_injections(failures),
        plan_audit,
        operational_audit,
        views_audit,
    )
    stages.append(
        _make_stage(
            11,
            "assurance",
            stages[-1].output_address,
            assurance_values,
            "certify, observe, graph, negative-control, and plan planes",
        )
    )
    first = build_program_release_snapshot(source, bundle_id=bundle_id, run_id=run_id)
    second = build_program_release_snapshot(source, bundle_id=bundle_id, run_id=run_id)
    deterministic = first.content_address == second.content_address == snapshot.content_address
    replay = ProgramReleaseReplay(
        first.content_address,
        second.content_address,
        snapshot.content_address,
        deterministic,
        deterministic,
        content_hash(
            {
                "first": first.content_address,
                "second": second.content_address,
                "expected": snapshot.content_address,
                "deterministic": deterministic,
            },
            prefix="program-release-replay",
        ),
    )
    stages.append(
        _stage(
            12,
            "replay",
            stages[-1].output_address,
            replay.content_address,
            replay.accepted,
            "replay the immutable projection twice",
        )
    )
    final_address = content_hash(
        {
            "snapshot": snapshot.content_address,
            "reconciliation": reconciliation.content_address,
            "certification": certification.content_address,
            "observability": observability.content_address,
            "graph": graph.content_address,
            "failures": failures.content_address,
            "plan": plan.content_address,
            "operational": operational.content_address,
            "views": views.content_address,
            "replay": replay.content_address,
        },
        prefix="program-release-finalize",
    )
    all_planes = (
        snapshot.accepted,
        all(item.passed for item in boundary),
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
        all(item.passed for item in plan_audit),
        operational.accepted,
        operational_audit.accepted,
        views.accepted,
        all(item.passed for item in views_audit),
        replay.accepted,
    )
    stages.append(
        _stage(
            13,
            "finalize",
            stages[-1].output_address,
            final_address,
            all(all_planes),
            "close the aggregate release handoff",
        )
    )
    stages.append(
        _stage(
            14,
            "public-state",
            stages[-1].output_address,
            final_address,
            all(all_planes),
            "expose stable ready state",
        )
    )
    accepted = all(item.state is ProgramReleaseClosureState.READY for item in stages) and all(
        all_planes
    )
    report_body = {
        "run_id": run_id,
        "state": ProgramReleaseClosureState.READY
        if accepted
        else ProgramReleaseClosureState.BLOCKED,
        "stages": tuple(stages),
        "snapshot": snapshot,
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
        "operational": operational,
        "operational_audit": operational_audit,
        "views": views,
        "views_audit": views_audit,
        "replay": replay,
        "accepted": accepted,
    }
    return ProgramReleaseRuntimeReport(
        run_id,
        report_body["state"],
        tuple(stages),
        snapshot,
        indexes,
        index_audit,
        reconciliation,
        summary,
        summary_audit,
        certification,
        observability,
        graph,
        failures,
        plan,
        tuple(plan_audit),
        operational,
        operational_audit,
        views,
        tuple(views_audit),
        replay,
        accepted,
        content_hash(report_body, prefix="program-release-runtime-report"),
    )


build_program_release_runtime = run_program_release_closure


__all__ = [
    name
    for name in globals()
    if name.startswith("run_program_release")
    or name.startswith("build_program_release")
    or name.startswith("ProgramRelease")
]
