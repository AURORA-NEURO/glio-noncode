"""Staged whole-product release-assurance runtime and replay gate."""

from __future__ import annotations

from typing import Any

from .public_surface_audit import PublicSurfaceAudit, build_default_public_surface_audit
from .release_assurance_bundle import build_release_assurance_snapshot
from .release_assurance_contracts import (
    ReleaseAssuranceReplay,
    ReleaseAssuranceRuntimeReport,
    ReleaseAssuranceRuntimeStage,
    ReleaseAssuranceState,
)
from .release_assurance_failure_injection import (
    audit_release_assurance_failure_injections,
    run_release_assurance_failure_injections,
)
from .release_assurance_graph import audit_release_assurance_graph, build_release_assurance_graph
from .release_assurance_indexes import audit_release_assurance_indexes, build_release_assurance_indexes
from .release_assurance_observability import (
    audit_release_assurance_observability,
    build_release_assurance_observability,
)
from .release_assurance_plan import audit_release_assurance_plan, build_release_assurance_plan
from .release_assurance_summary import (
    audit_release_assurance_summary,
    build_release_assurance_summary,
)
from .release_assurance_views import audit_release_assurance_views, build_release_assurance_views
from .service_release_bundle import build_service_release_snapshot
from .service_surface import ServiceSurfaceSnapshot, build_service_surface_snapshot
from .serialization import content_hash, require_non_empty


def _stage(
    ordinal: int,
    stage_id: str,
    input_address: str,
    output_address: str,
    accepted: bool,
    detail: str,
) -> ReleaseAssuranceRuntimeStage:
    body = {
        "ordinal": ordinal,
        "stage_id": stage_id,
        "state": ReleaseAssuranceState.READY if accepted else ReleaseAssuranceState.BLOCKED,
        "input_address": input_address,
        "output_address": output_address,
        "detail": detail,
    }
    return ReleaseAssuranceRuntimeStage(
        **body,
        content_address=content_hash(body, prefix="release-assurance-runtime-stage"),
    )


def _result(value: Any) -> tuple[bool, str]:
    if isinstance(value, dict):
        return bool(value.get("accepted", False)), str(value.get("content_address", ""))
    if isinstance(value, tuple):
        values = [
            _result(item)[0] if isinstance(item, tuple)
            else bool(getattr(item, "passed", getattr(item, "accepted", False)))
            for item in value
        ]
        return all(values), content_hash(value, prefix="release-assurance-stage-audit")
    return bool(getattr(value, "accepted", False)), str(getattr(value, "content_address", ""))


def _stage_for(ordinal: int, stage_id: str, previous: str, value: Any, detail: str) -> ReleaseAssuranceRuntimeStage:
    accepted, address = _result(value)
    return _stage(ordinal, stage_id, previous, address, accepted, detail)


def run_release_assurance(
    source_snapshot: ServiceSurfaceSnapshot | None = None,
    *,
    public_audit: PublicSurfaceAudit | None = None,
    run_id: str = "glio-noncode-release-assurance-run",
    bundle_id: str = "glio-noncode-release-assurance",
) -> ReleaseAssuranceRuntimeReport:
    """Run the whole-product gate over one immutable service snapshot."""

    require_non_empty(run_id, "run_id")
    require_non_empty(bundle_id, "bundle_id")
    source = source_snapshot or build_service_surface_snapshot()
    audit = public_audit or build_default_public_surface_audit(snapshot=source)
    service_release = build_service_release_snapshot(source)
    snapshot = build_release_assurance_snapshot(
        source,
        public_audit=audit,
        service_release=service_release,
        bundle_id=bundle_id,
        run_id=run_id,
    )
    stages: list[ReleaseAssuranceRuntimeStage] = []
    stages.append(_stage(1, "source-surface", "", source.content_address, source.accepted,
                         "reuse or build the accepted service snapshot"))
    stages.append(_stage(2, "public-audit", stages[-1].output_address,
                         audit.content_address, audit.accepted,
                         "reuse or build the repository public-surface audit"))
    stages.append(_stage(3, "assurance-snapshot", stages[-1].output_address,
                         snapshot.content_address, snapshot.accepted,
                         "assemble four cross-plane assurance domains"))
    stages.append(_stage(4, "cross-plane-checks", stages[-1].output_address,
                         content_hash(snapshot.checks, prefix="release-assurance-checks"),
                         all(item.passed for item in snapshot.checks),
                         "reconcile capability, architecture, service, and boundary planes"))
    indexes = build_release_assurance_indexes(snapshot)
    index_audit = audit_release_assurance_indexes(snapshot, indexes)
    stages.append(_stage_for(5, "indexes", stages[-1].output_address, index_audit,
                             "build and audit address-only indexes"))
    summary = build_release_assurance_summary(snapshot)
    summary_audit = audit_release_assurance_summary(summary, snapshot)
    stages.append(_stage_for(6, "summary", stages[-1].output_address, summary_audit,
                             "publish conserved readiness denominators"))
    observability = build_release_assurance_observability(snapshot)
    observability_audit = audit_release_assurance_observability(observability)
    stages.append(_stage_for(7, "observability", stages[-1].output_address, observability_audit,
                             "publish deterministic events and metrics"))
    graph = build_release_assurance_graph(snapshot)
    graph_audit = audit_release_assurance_graph(graph, snapshot)
    stages.append(_stage_for(8, "graph", stages[-1].output_address, graph_audit,
                             "connect whole-product evidence lineage"))
    failures = run_release_assurance_failure_injections(snapshot)
    failure_audit = audit_release_assurance_failure_injections(failures)
    stages.append(_stage_for(9, "negative-controls", stages[-1].output_address, failure_audit,
                             "run fail-closed structural controls"))
    plan = build_release_assurance_plan(snapshot)
    plan_audit = audit_release_assurance_plan(plan)
    views = build_release_assurance_views(snapshot)
    views_audit = audit_release_assurance_views(views, snapshot)
    stages.append(_stage_for(
        10,
        "plan-and-views",
        stages[-1].output_address,
        (plan_audit, views_audit),
        "prepare executable plan and reviewer views",
    ))
    first = build_release_assurance_snapshot(
        source,
        public_audit=audit,
        service_release=service_release,
        bundle_id=bundle_id,
        run_id=run_id,
    )
    second = build_release_assurance_snapshot(
        source,
        public_audit=audit,
        service_release=service_release,
        bundle_id=bundle_id,
        run_id=run_id,
    )
    deterministic = first.content_address == second.content_address == snapshot.content_address
    replay = ReleaseAssuranceReplay(
        first.content_address,
        second.content_address,
        snapshot.content_address,
        deterministic,
        deterministic,
        content_hash({"first": first.content_address, "second": second.content_address,
                      "expected": snapshot.content_address, "deterministic": deterministic},
                     prefix="release-assurance-replay"),
    )
    stages.append(_stage(11, "replay", stages[-1].output_address, replay.content_address,
                         replay.accepted, "rebuild the immutable assurance snapshot twice"))
    all_planes = (
        source.accepted,
        audit.accepted,
        snapshot.accepted,
        all(item.passed for item in snapshot.checks),
        indexes.accepted,
        index_audit.accepted,
        summary.accepted,
        summary_audit.accepted,
        observability.accepted,
        all(item.passed for item in observability_audit),
        graph.accepted,
        all(item.passed for item in graph_audit),
        failures.accepted,
        all(item.passed for item in failure_audit),
        plan.accepted,
        all(item.passed for item in plan_audit),
        views.accepted,
        all(item.passed for item in views_audit),
        replay.accepted,
    )
    final_address = content_hash(
        {"snapshot": snapshot.content_address, "indexes": indexes.content_address,
         "summary": summary.content_address, "observability": observability.content_address,
         "graph": graph.content_address, "failures": failures.content_address,
         "plan": plan.content_address, "views": views.content_address,
         "replay": replay.content_address},
        prefix="release-assurance-finalize",
    )
    accepted = all(all_planes)
    stages.append(_stage(12, "public-state", stages[-1].output_address, final_address,
                         accepted, "publish the final whole-product release decision"))
    accepted = accepted and all(item.state is ReleaseAssuranceState.READY for item in stages)
    body = {
        "run_id": run_id,
        "state": ReleaseAssuranceState.READY if accepted else ReleaseAssuranceState.BLOCKED,
        "stages": tuple(stages),
        "snapshot": snapshot,
        "indexes": indexes,
        "index_audit": index_audit,
        "summary": summary,
        "summary_audit": summary_audit,
        "observability": observability,
        "graph": graph,
        "failures": failures,
        "plan": plan,
        "plan_audit": tuple(plan_audit),
        "views": views,
        "views_audit": tuple(views_audit),
        "replay": replay,
        "accepted": accepted,
    }
    return ReleaseAssuranceRuntimeReport(
        run_id,
        ReleaseAssuranceState.READY if accepted else ReleaseAssuranceState.BLOCKED,
        tuple(stages),
        snapshot,
        indexes,
        index_audit,
        summary,
        summary_audit,
        observability,
        graph,
        failures,
        plan,
        tuple(plan_audit),
        views,
        tuple(views_audit),
        replay,
        accepted,
        content_hash(body, prefix="release-assurance-runtime-report"),
    )


build_release_assurance_runtime = run_release_assurance

__all__ = ["build_release_assurance_runtime", "run_release_assurance"]
