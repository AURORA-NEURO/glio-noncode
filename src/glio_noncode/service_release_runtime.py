"""Staged runtime for the complete public service-release registry."""

from __future__ import annotations

from typing import Any

from .service_release_bundle import build_service_release_snapshot
from .service_release_certification import (
    audit_service_release_certification,
    certify_service_release,
)
from .service_release_contracts import (
    ServiceReleaseRuntimeReport,
    ServiceReleaseRuntimeStage,
    ServiceReleaseState,
    ServiceReleaseReplay,
)
from .service_release_failure_injection import (
    audit_service_release_failure_injections,
    run_service_release_failure_injections,
)
from .service_release_graph import audit_service_release_graph, build_service_release_graph
from .service_release_indexes import audit_service_release_indexes, build_service_release_indexes
from .service_release_observability import (
    audit_service_release_observability,
    build_service_release_observability,
)
from .service_release_plan import audit_service_release_plan, build_service_release_plan
from .service_release_reconciliation import (
    audit_service_release_summary,
    build_service_release_summary,
    reconcile_service_release,
)
from .service_release_views import audit_service_release_views, build_service_release_views
from .service_surface import ServiceSurfaceSnapshot
from .serialization import content_hash, require_non_empty


def _stage(ordinal: int, stage_id: str, input_address: str, output_address: str,
           accepted: bool, detail: str) -> ServiceReleaseRuntimeStage:
    body = {"ordinal": ordinal, "stage_id": stage_id,
            "state": ServiceReleaseState.READY if accepted else ServiceReleaseState.BLOCKED,
            "input_address": input_address, "output_address": output_address, "detail": detail}
    return ServiceReleaseRuntimeStage(
        **body, content_address=content_hash(body, prefix="service-release-runtime-stage")
    )


def _result(value: Any) -> tuple[bool, str]:
    if isinstance(value, dict):
        return bool(value.get("accepted")), str(value.get("content_address", ""))
    if isinstance(value, tuple):
        results = [_result(item)[0] if isinstance(item, tuple) else bool(getattr(item, "passed", getattr(item, "accepted", False))) for item in value]
        accepted = all(results)
        return accepted, content_hash(value, prefix="service-release-stage-audit")
    return bool(getattr(value, "accepted", False)), str(getattr(value, "content_address", ""))


def _stage_for(ordinal: int, stage_id: str, previous: str, value: Any, detail: str) -> ServiceReleaseRuntimeStage:
    accepted, address = _result(value)
    return _stage(ordinal, stage_id, previous, address, accepted, detail)


def run_service_release(
    source_snapshot: ServiceSurfaceSnapshot | None = None,
    *,
    run_id: str = "glio-noncode-service-release-run",
    bundle_id: str = "glio-noncode-service-release",
) -> ServiceReleaseRuntimeReport:
    """Run all registry planes and a deterministic replay gate."""

    require_non_empty(run_id, "run_id")
    require_non_empty(bundle_id, "bundle_id")
    source = source_snapshot or __import__(
        "glio_noncode.service_surface", fromlist=["build_service_surface_snapshot"]
    ).build_service_surface_snapshot()
    snapshot = build_service_release_snapshot(source, bundle_id=bundle_id)
    stages: list[ServiceReleaseRuntimeStage] = []
    stages.append(_stage(1, "source-surface", "", source.content_address, source.accepted,
                         "reuse or build one immutable service snapshot"))
    stages.append(_stage(2, "registry-snapshot", stages[-1].output_address,
                         snapshot.content_address, snapshot.accepted,
                         "project the service release registry"))
    stages.append(_stage(3, "surface-registry", stages[-1].output_address,
                         content_hash(snapshot.surfaces, prefix="service-release-surfaces"),
                         all(item.accepted for item in snapshot.surfaces),
                         "register six ordered service surfaces"))
    stages.append(_stage(4, "artifact-registry", stages[-1].output_address,
                         content_hash(snapshot.artifacts, prefix="service-release-artifacts"),
                         bool(snapshot.artifacts), "address exact-byte export artifacts"))
    stages.append(_stage(5, "dependency-matrix", stages[-1].output_address,
                         content_hash(snapshot.dependencies, prefix="service-release-dependencies"),
                         len(snapshot.dependencies) == 15,
                         "materialize complete surface dependency matrix"))
    stages.append(_stage(6, "promotion-gates", stages[-1].output_address,
                         content_hash(snapshot.gates, prefix="service-release-gates"),
                         all(item.passed for item in snapshot.gates),
                         "evaluate four gates per service surface"))
    indexes = build_service_release_indexes(snapshot)
    index_audit = audit_service_release_indexes(snapshot, indexes)
    stages.append(_stage_for(7, "indexes", stages[-1].output_address, index_audit,
                             "build and audit address-only indexes"))
    reconciliation = reconcile_service_release(snapshot, source)
    stages.append(_stage_for(8, "reconciliation", stages[-1].output_address, reconciliation,
                             "reconcile source and registry denominators"))
    summary = build_service_release_summary(snapshot, source)
    summary_audit = audit_service_release_summary(summary, source)
    stages.append(_stage_for(9, "summary", stages[-1].output_address, summary_audit,
                             "publish conserved service counters"))
    certification = certify_service_release(snapshot)
    certification_audit = audit_service_release_certification(certification, snapshot)
    stages.append(_stage_for(10, "certification", stages[-1].output_address, certification_audit,
                             "certify public service surfaces"))
    observability = build_service_release_observability(snapshot)
    observability_audit = audit_service_release_observability(observability)
    graph = build_service_release_graph(snapshot)
    graph_audit = audit_service_release_graph(graph, snapshot)
    failures = run_service_release_failure_injections(snapshot)
    failure_audit = audit_service_release_failure_injections(failures)
    plan = build_service_release_plan(snapshot)
    plan_audit = audit_service_release_plan(plan)
    views = build_service_release_views(snapshot)
    views_audit = audit_service_release_views(views, snapshot)
    assurance = (observability_audit, graph_audit, failure_audit, plan_audit, views_audit)
    stages.append(_stage_for(11, "assurance", stages[-1].output_address, assurance,
                             "observe, graph, negative-control, plan, and review planes"))
    first = build_service_release_snapshot(source, bundle_id=bundle_id)
    second = build_service_release_snapshot(source, bundle_id=bundle_id)
    deterministic = first.content_address == second.content_address == snapshot.content_address
    replay = ServiceReleaseReplay(
        first.content_address, second.content_address, snapshot.content_address,
        deterministic, deterministic,
        content_hash({"first": first.content_address, "second": second.content_address,
                      "expected": snapshot.content_address, "deterministic": deterministic},
                     prefix="service-release-replay"),
    )
    stages.append(_stage(12, "replay", stages[-1].output_address, replay.content_address,
                         replay.accepted, "replay the immutable registry twice"))
    final_address = content_hash(
        {"snapshot": snapshot.content_address, "indexes": indexes.content_address,
         "reconciliation": reconciliation.content_address, "summary": summary.content_address,
         "certification": certification.content_address, "observability": observability.content_address,
         "graph": graph.content_address, "failures": failures.content_address,
         "plan": plan.content_address, "views": views.content_address, "replay": replay.content_address},
        prefix="service-release-finalize",
    )
    all_planes = (
        source.accepted, snapshot.accepted, indexes.accepted, index_audit.accepted,
        reconciliation.accepted, summary.accepted, summary_audit.accepted,
        certification.accepted, all(item.passed for item in certification_audit),
        observability.accepted, all(item.passed for item in observability_audit),
        graph.accepted, all(item.passed for item in graph_audit), failures.accepted,
        all(item.passed for item in failure_audit), plan.accepted,
        all(item.passed for item in plan_audit), views.accepted,
        all(item.passed for item in views_audit), replay.accepted,
    )
    stages.append(_stage(13, "finalize", stages[-1].output_address, final_address,
                         all(all_planes), "close the service release handoff"))
    stages.append(_stage(14, "public-state", stages[-1].output_address, final_address,
                         all(all_planes), "expose stable ready state"))
    accepted = all(all_planes) and all(item.state is ServiceReleaseState.READY for item in stages)
    body = {
        "run_id": run_id, "state": ServiceReleaseState.READY if accepted else ServiceReleaseState.BLOCKED,
        "stages": tuple(stages), "snapshot": snapshot, "indexes": indexes,
        "index_audit": index_audit, "reconciliation": reconciliation, "summary": summary,
        "summary_audit": summary_audit, "certification": certification,
        "observability": observability, "graph": graph, "failures": failures,
        "plan": plan, "plan_audit": tuple(plan_audit), "views": views,
        "views_audit": tuple(views_audit), "replay": replay, "accepted": accepted,
    }
    return ServiceReleaseRuntimeReport(
        run_id, body["state"], tuple(stages), snapshot, indexes, index_audit,
        reconciliation, summary, summary_audit, certification, observability,
        graph, failures, plan, tuple(plan_audit), views, tuple(views_audit),
        replay, accepted, content_hash(body, prefix="service-release-runtime-report"),
    )


build_service_release_runtime = run_service_release

__all__ = ["build_service_release_runtime", "run_service_release"]
