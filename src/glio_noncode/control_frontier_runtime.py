"""Ordered runtime rehearsal for Domain 16 C05-C12."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from .control_frontier_adapters import build_control_frontier_adapters
from .control_frontier_artifacts import build_control_frontier_artifact_inventory
from .control_frontier_contracts import ControlFrontierFixture
from .control_frontier_depth import audit_control_frontier_depth
from .control_frontier_fixture_eval import evaluate_control_frontier_fixture
from .control_frontier_lineage import build_control_frontier_lineage
from .control_frontier_metrics import measure_control_frontier
from .control_frontier_observability import build_control_frontier_trace
from .control_frontier_policy import default_control_frontier_policy
from .control_frontier_public_data import audit_control_frontier_data, default_control_frontier_fixture
from .control_frontier_quality_gate import run_control_frontier_quality_gate
from .control_frontier_reconciliation import reconcile_control_frontier
from .control_frontier_release import build_control_frontier_release
from .control_frontier_replay import replay_control_frontier_evaluation
from .control_frontier_schema import default_control_frontier_schema
from .control_frontier_views import build_control_frontier_view
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ControlFrontierRuntimeStage:
    stage_id: str
    sequence: int
    state: str
    duration_ms: float
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierRuntimeReport:
    run_id: str
    stages: tuple[ControlFrontierRuntimeStage, ...]
    fixture: ControlFrontierFixture
    evaluation: Any
    metrics: Any
    quality: Any
    lineage: Any
    replay: Any
    release: Any
    artifacts: Any
    trace: Any
    depth: Any
    accepted: bool
    content_address: str

    @property
    def stage_ids(self) -> tuple[str, ...]:
        return tuple(item.stage_id for item in self.stages)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"stage_ids": list(self.stage_ids)}


def run_control_frontier_runtime(fixture: ControlFrontierFixture | None = None, *, run_id: str = "control-frontier-runtime") -> ControlFrontierRuntimeReport:
    fixture = fixture or default_control_frontier_fixture()
    require_non_empty(run_id, "run_id")
    stages: list[ControlFrontierRuntimeStage] = []

    def stage(stage_id: str, fn: Callable[[], Any], detail: str) -> Any:
        started = perf_counter()
        result = fn()
        duration = round((perf_counter() - started) * 1000, 3)
        address = result.content_address if hasattr(result, "content_address") else content_hash(result)
        body = {"stage_id": stage_id, "sequence": len(stages) + 1, "state": "completed", "duration_ms": duration, "output_address": address, "detail": detail}
        stages.append(ControlFrontierRuntimeStage(**body, content_address=content_hash(body)))
        return result

    audit = stage("data-audit", lambda: audit_control_frontier_data(fixture), "audit source and aggregate boundaries")
    adapters = stage("adapters", build_control_frontier_adapters, "load eight typed operation adapters")
    schema = stage("schema", default_control_frontier_schema, "load public receipt schema")
    evaluation = stage("fixture-evaluation", lambda: evaluate_control_frontier_fixture(fixture), "execute positive and control rows")
    metrics = stage("metrics", lambda: measure_control_frontier(evaluation), "measure states and issue codes")
    policy = stage("policy", default_control_frontier_policy, "materialize research-only use policy")
    lineage = stage("lineage", lambda: build_control_frontier_lineage(fixture, evaluation), "build redacted source lineage")
    reconciliation = stage("reconciliation", lambda: reconcile_control_frontier(fixture, evaluation), "reconcile expected and observed outcomes")
    quality = stage("quality-gate", lambda: run_control_frontier_quality_gate(fixture, audit, evaluation, metrics, adapters, schema, policy, lineage, reconciliation), "run blocking quality checks")
    replay = stage("replay", lambda: replay_control_frontier_evaluation(fixture, evaluation), "replay every execution address")
    release = stage("release", lambda: build_control_frontier_release(fixture, evaluation, quality, lineage, replay, release_id=run_id), "build research-only release manifest")
    artifacts = stage("artifacts", lambda: build_control_frontier_artifact_inventory(fixture, release), "inventory release addresses")
    view = stage("review-view", lambda: build_control_frontier_view(evaluation), "build stable review projection")
    summary = stage("summary", lambda: {"record_count": metrics.record_count, "accepted_count": metrics.accepted_count, "state_counts": metrics.state_counts, "review_count": len(view.entries)}, "emit review summary")
    stage("policy-receipt", lambda: policy.to_dict(), "close policy projection")
    stage("lineage-receipt", lambda: lineage.to_dict(), "close lineage projection")
    stage("reconciliation-receipt", lambda: reconciliation.to_dict(), "close reconciliation projection")
    stage("release-receipt", lambda: release.to_dict(), "close release projection")
    stage("artifact-receipt", lambda: artifacts.to_dict(), "close artifact projection")
    trace = stage("observability", lambda: build_control_frontier_trace(run_id, tuple({"stage_id": item.stage_id, "state": item.state, "output_address": item.output_address, "events": (item.detail,)} for item in stages), accepted=quality.accepted), "emit stage trace")
    stage("export-manifest", lambda: {"json": ("fixture", "evaluation", "metrics", "release"), "csv": ("review", "metrics"), "trace": trace.content_address}, "describe export surfaces")
    stage("handoff", lambda: {"fixture": fixture.content_address, "evaluation": evaluation.content_address, "quality": quality.content_address, "release": release.content_address}, "assemble reproducible handoff")
    stage("close", lambda: {"quality": quality.accepted, "replay": replay.deterministic, "release": release.accepted, "artifacts": artifacts.complete}, "close runtime prerequisites")
    depth = stage("depth", lambda: audit_control_frontier_depth(fixture, evaluation), "audit scenario, threshold, validation, evidence, access, and claim surfaces")
    accepted = bool(audit.accepted and evaluation.accepted and quality.accepted and replay.deterministic and release.accepted and artifacts.complete and depth.accepted)
    body = {"run_id": run_id, "stages": tuple(stages), "fixture": fixture, "evaluation": evaluation, "metrics": metrics, "quality": quality, "lineage": lineage, "replay": replay, "release": release, "artifacts": artifacts, "trace": trace, "depth": depth, "accepted": accepted}
    return ControlFrontierRuntimeReport(**body, content_address=content_hash(body))


__all__ = ["ControlFrontierRuntimeReport", "ControlFrontierRuntimeStage", "run_control_frontier_runtime"]
