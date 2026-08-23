"""Ordered runtime rehearsal for Domain 14 C05-C12."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from .lifecycle_beta_frontier_adapters import build_lifecycle_beta_frontier_adapters
from .lifecycle_beta_frontier_artifacts import build_lifecycle_beta_frontier_artifact_inventory
from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierFixture
from .lifecycle_beta_frontier_depth import audit_lifecycle_beta_frontier_depth
from .lifecycle_beta_frontier_exports import lifecycle_beta_frontier_export_payload
from .lifecycle_beta_frontier_fixture_eval import evaluate_lifecycle_beta_frontier_fixture
from .lifecycle_beta_frontier_handoff import build_lifecycle_beta_frontier_handoff
from .lifecycle_beta_frontier_lineage import build_lifecycle_beta_frontier_lineage
from .lifecycle_beta_frontier_metrics import measure_lifecycle_beta_frontier
from .lifecycle_beta_frontier_observability import build_lifecycle_beta_frontier_trace
from .lifecycle_beta_frontier_policy import default_lifecycle_beta_frontier_policy
from .lifecycle_beta_frontier_public_data import audit_lifecycle_beta_frontier_data, default_lifecycle_beta_frontier_fixture
from .lifecycle_beta_frontier_quality_gate import run_lifecycle_beta_frontier_quality_gate
from .lifecycle_beta_frontier_reconciliation import reconcile_lifecycle_beta_frontier
from .lifecycle_beta_frontier_release import build_lifecycle_beta_frontier_release
from .lifecycle_beta_frontier_replay import replay_lifecycle_beta_frontier_evaluation
from .lifecycle_beta_frontier_review_queue import build_lifecycle_beta_frontier_review_queue
from .lifecycle_beta_frontier_schema import default_lifecycle_beta_frontier_schema
from .lifecycle_beta_frontier_scenario_matrix import evaluate_lifecycle_beta_frontier_scenarios
from .lifecycle_beta_frontier_thresholds import build_lifecycle_beta_frontier_threshold_report
from .lifecycle_beta_frontier_validation_matrix import build_lifecycle_beta_frontier_validation_matrix
from .lifecycle_beta_frontier_views import build_lifecycle_beta_frontier_view
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierRuntimeStage:
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
class LifecycleBetaFrontierRuntimeReport:
    run_id: str
    stages: tuple[LifecycleBetaFrontierRuntimeStage, ...]
    fixture: LifecycleBetaFrontierFixture
    evaluation: Any
    metrics: Any
    quality: Any
    depth: Any
    thresholds: Any
    validation_matrix: Any
    handoff: Any
    release: Any
    artifacts: Any
    accepted: bool
    content_address: str

    @property
    def stage_ids(self) -> tuple[str, ...]:
        return tuple(item.stage_id for item in self.stages)

    def to_dict(self) -> dict[str, Any]:
        payload = jsonable(self) | {"stage_ids": list(self.stage_ids)}
        payload["thresholds"] = self.thresholds.to_dict()
        payload["validation_matrix"] = self.validation_matrix.to_dict()
        payload["handoff"] = self.handoff.to_dict()
        payload["release"] = self.release.to_dict()
        payload["artifacts"] = self.artifacts.to_dict()
        return payload


def run_lifecycle_beta_frontier_runtime(fixture: LifecycleBetaFrontierFixture | None = None, *, run_id: str = "lifecycle-beta-frontier-runtime") -> LifecycleBetaFrontierRuntimeReport:
    fixture = fixture or default_lifecycle_beta_frontier_fixture()
    require_non_empty(run_id, "run_id")
    stages: list[LifecycleBetaFrontierRuntimeStage] = []

    def stage(stage_id: str, fn: Callable[[], Any], detail: str) -> Any:
        started = perf_counter()
        result = fn()
        duration = round((perf_counter() - started) * 1000, 3)
        address = result.content_address if hasattr(result, "content_address") else content_hash(result)
        body = {"stage_id": stage_id, "sequence": len(stages) + 1, "state": "completed", "duration_ms": duration, "output_address": address, "detail": detail}
        stages.append(LifecycleBetaFrontierRuntimeStage(**body, content_address=content_hash(body)))
        return result

    audit = stage("data-audit", lambda: audit_lifecycle_beta_frontier_data(fixture), "audit public aggregate receipts")
    contracts = stage("contracts", build_lifecycle_beta_frontier_adapters, "load eight operation adapter contracts")
    schema = stage("schema", default_lifecycle_beta_frontier_schema, "load record and receipt schema")
    evaluation = stage("fixture-evaluation", lambda: evaluate_lifecycle_beta_frontier_fixture(fixture), "execute positive and control records")
    metrics = stage("metrics", lambda: measure_lifecycle_beta_frontier(evaluation), "measure states, issues, and control coverage")
    policy = stage("policy", default_lifecycle_beta_frontier_policy, "materialize research-use policy")
    lineage = stage("lineage", lambda: build_lifecycle_beta_frontier_lineage(fixture, evaluation), "build source and execution lineage")
    reconciliation = stage("reconciliation", lambda: reconcile_lifecycle_beta_frontier(fixture, evaluation), "reconcile expected and observed boundaries")
    quality = stage("quality-gate", lambda: run_lifecycle_beta_frontier_quality_gate(fixture, audit, evaluation, metrics, contracts, schema, policy, lineage, reconciliation), "run blocking quality checks")
    scenarios = stage("scenario-matrix", lambda: evaluate_lifecycle_beta_frontier_scenarios(evaluation), "cover four scenario axes per operation")
    thresholds = stage("thresholds", build_lifecycle_beta_frontier_threshold_report, "probe five boundaries per operation")
    validation_matrix = stage("validation-matrix", lambda: build_lifecycle_beta_frontier_validation_matrix(evaluation), "cross records with six evidence planes")
    replay = stage("replay", lambda: replay_lifecycle_beta_frontier_evaluation(fixture, evaluation), "replay deterministic execution receipts")
    release = stage("release", lambda: build_lifecycle_beta_frontier_release(fixture, evaluation, quality, lineage, replay, release_id=run_id), "build research-only release manifest")
    artifacts = stage("artifacts", lambda: build_lifecycle_beta_frontier_artifact_inventory(fixture, release), "inventory content-addressed artifacts")
    view = stage("review-view", lambda: build_lifecycle_beta_frontier_view(evaluation), "build stable review projection")
    queue = stage("review-queue", lambda: build_lifecycle_beta_frontier_review_queue(evaluation), "prioritize unresolved review rows")
    handoff = stage("handoff", lambda: build_lifecycle_beta_frontier_handoff(fixture, evaluation, metrics), "build reproducible handoff")
    depth = stage("depth", lambda: audit_lifecycle_beta_frontier_depth(fixture, evaluation, validation_matrix, handoff), "audit implementation depth")
    trace = stage("observability", lambda: build_lifecycle_beta_frontier_trace(run_id, tuple({"stage_id": item.stage_id, "sequence": item.sequence, "state": item.state, "output_address": item.output_address, "duration_ms": item.duration_ms, "events": (item.detail,)} for item in stages), accepted=quality.accepted), "emit stage and event trace")
    export_manifest = stage("export-manifest", lambda: {"json_keys": tuple(sorted(lifecycle_beta_frontier_export_payload(evaluation))), "csv_surfaces": ("review", "metrics"), "trace": trace.content_address}, "describe export surfaces")
    release_check = stage("release-check", lambda: {"quality": quality.accepted, "replay": replay.deterministic, "artifacts": artifacts.complete, "depth": depth.accepted}, "check release prerequisites")
    package = stage("package", lambda: {"fixture": fixture.content_address, "evaluation": evaluation.content_address, "quality": quality.content_address, "release": release.content_address}, "assemble package addresses")
    summary = stage("summary", lambda: {"record_count": metrics.record_count, "accepted_count": metrics.accepted_count, "queue_count": len(queue.items), "scenario_cells": len(scenarios.cells)}, "emit package summary")
    stage("handoff-summary", lambda: handoff.to_dict(), "close handoff projection")
    accepted = bool(audit.accepted and evaluation.accepted and quality.accepted and replay.deterministic and depth.accepted and release.accepted and artifacts.complete and validation_matrix.accepted and scenarios.accepted)
    body = {"run_id": run_id, "stages": tuple(stages), "fixture": fixture, "evaluation": evaluation, "metrics": metrics, "quality": quality, "depth": depth, "thresholds": thresholds, "validation_matrix": validation_matrix, "handoff": handoff, "release": release, "artifacts": artifacts, "accepted": accepted}
    return LifecycleBetaFrontierRuntimeReport(**body, content_address=content_hash(body))


__all__ = ["LifecycleBetaFrontierRuntimeReport", "LifecycleBetaFrontierRuntimeStage", "run_lifecycle_beta_frontier_runtime"]
