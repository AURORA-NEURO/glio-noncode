"""Ordered runtime rehearsal for Domain 16 C01-C04."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from .platform_frontier_access import build_platform_frontier_access_manifest
from .platform_frontier_adapters import build_platform_frontier_adapters
from .platform_frontier_artifacts import PlatformFrontierArtifactInventory, build_platform_frontier_artifact_inventory
from .platform_frontier_benchmark import PlatformFrontierBenchmarkReport, run_platform_frontier_benchmark
from .platform_frontier_bundle import PlatformFrontierReleaseBundle, assemble_platform_frontier_bundle
from .platform_frontier_contracts import PlatformFrontierFixture
from .platform_frontier_depth import PlatformFrontierDepthAudit, audit_platform_frontier_depth
from .platform_frontier_fixture_eval import evaluate_platform_frontier_fixture
from .platform_frontier_handoff import build_platform_frontier_handoff
from .platform_frontier_integrity import PlatformFrontierIntegrityReport, evaluate_platform_frontier_integrity
from .platform_frontier_lineage import build_platform_frontier_lineage
from .platform_frontier_metrics import measure_platform_frontier
from .platform_frontier_observability import PlatformFrontierTrace, build_platform_frontier_trace
from .platform_frontier_operational import build_platform_frontier_operational_matrix
from .platform_frontier_package import PlatformFrontierPackageManifest, build_platform_frontier_package_manifest
from .platform_frontier_performance import build_platform_frontier_performance_budget
from .platform_frontier_policy import default_platform_frontier_policy
from .platform_frontier_public_data import audit_platform_frontier_data, default_platform_frontier_fixture
from .platform_frontier_quality_gate import run_platform_frontier_quality_gate
from .platform_frontier_reconciliation import reconcile_platform_frontier
from .platform_frontier_release import build_platform_frontier_release
from .platform_frontier_replay import replay_platform_frontier_evaluation
from .platform_frontier_review_queue import build_platform_frontier_review_queue
from .platform_frontier_review_sla import build_platform_frontier_review_sla
from .platform_frontier_schema import default_platform_frontier_schema
from .platform_frontier_summary import PlatformFrontierSummary, build_platform_frontier_summary
from .platform_frontier_views import build_platform_frontier_view
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class PlatformFrontierRuntimeStage:
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
class PlatformFrontierRuntimeReport:
    run_id: str
    stages: tuple[PlatformFrontierRuntimeStage, ...]
    fixture: PlatformFrontierFixture
    evaluation: Any
    metrics: Any
    quality: Any
    lineage: Any
    replay: Any
    release: Any
    artifacts: PlatformFrontierArtifactInventory
    trace: PlatformFrontierTrace
    depth: PlatformFrontierDepthAudit
    integrity: PlatformFrontierIntegrityReport
    summary: PlatformFrontierSummary
    package: PlatformFrontierPackageManifest
    bundle: PlatformFrontierReleaseBundle
    accepted: bool
    content_address: str

    @property
    def stage_ids(self) -> tuple[str, ...]:
        return tuple(item.stage_id for item in self.stages)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"stage_ids": list(self.stage_ids)}


def run_platform_frontier_runtime(fixture: PlatformFrontierFixture | None = None, *, run_id: str = "platform-frontier-runtime") -> PlatformFrontierRuntimeReport:
    fixture = fixture or default_platform_frontier_fixture()
    require_non_empty(run_id, "run_id")
    stages: list[PlatformFrontierRuntimeStage] = []

    def stage(stage_id: str, fn: Callable[[], Any], detail: str) -> Any:
        started = perf_counter()
        result = fn()
        duration = round((perf_counter() - started) * 1000, 3)
        address = result.content_address if hasattr(result, "content_address") else content_hash(result)
        body = {"stage_id": stage_id, "sequence": len(stages) + 1, "state": "completed", "duration_ms": duration, "output_address": address, "detail": detail}
        stages.append(PlatformFrontierRuntimeStage(**body, content_address=content_hash(body)))
        return result

    audit = stage("data-audit", lambda: audit_platform_frontier_data(fixture), "audit public aggregate boundaries")
    adapters = stage("adapters", build_platform_frontier_adapters, "load four typed operation adapters")
    schema = stage("schema", default_platform_frontier_schema, "load typed input and output fields")
    evaluation = stage("fixture-evaluation", lambda: evaluate_platform_frontier_fixture(fixture), "execute positive and control rows")
    metrics = stage("metrics", lambda: measure_platform_frontier(evaluation), "measure state and issue distributions")
    policy = stage("policy", default_platform_frontier_policy, "materialize research-use policy")
    lineage = stage("lineage", lambda: build_platform_frontier_lineage(fixture, evaluation), "build source-to-execution lineage")
    reconciliation = stage("reconciliation", lambda: reconcile_platform_frontier(fixture, evaluation), "reconcile expected and observed states")
    quality = stage("quality-gate", lambda: run_platform_frontier_quality_gate(fixture, audit, evaluation, metrics, adapters, schema, policy, lineage, reconciliation), "run blocking quality checks")
    replay = stage("replay", lambda: replay_platform_frontier_evaluation(fixture, evaluation), "replay every operation address")
    release = stage("release", lambda: build_platform_frontier_release(fixture, evaluation, quality, lineage, replay, release_id=run_id), "build aggregate release manifest")
    artifacts = stage("artifacts", lambda: build_platform_frontier_artifact_inventory(fixture, release), "inventory release addresses")
    view = stage("review-view", lambda: build_platform_frontier_view(evaluation), "build stable review projection")
    queue = stage("review-queue", lambda: build_platform_frontier_review_queue(evaluation), "route controls to bounded review")
    sla = stage("review-sla", lambda: build_platform_frontier_review_sla(queue), "assign review response bands")
    handoff = stage("handoff", lambda: build_platform_frontier_handoff(fixture, evaluation, metrics, queue), "assemble reproducible handoff")
    integrity = stage("integrity", lambda: evaluate_platform_frontier_integrity(fixture, evaluation), "recompute nested addresses")
    depth = stage("depth", lambda: audit_platform_frontier_depth(fixture, evaluation), "audit scenario threshold validation evidence surfaces")
    operational = stage("operational", lambda: build_platform_frontier_operational_matrix(evaluation), "describe control response actions")
    performance = stage("performance", lambda: build_platform_frontier_performance_budget(evaluation), "close deterministic resource budget")
    benchmark = stage("benchmark", lambda: run_platform_frontier_benchmark(fixture, repetitions=2), "measure repeatable local evaluation")
    access = stage("access", lambda: build_platform_frontier_access_manifest(fixture), "describe public export surfaces")
    trace = stage("observability", lambda: build_platform_frontier_trace(run_id, tuple({"stage_id": item.stage_id, "state": item.state, "output_address": item.output_address, "events": (item.detail,)} for item in stages), accepted=quality.accepted), "emit ordered stage trace")
    package_values: dict[str, Any] = {}

    def close_bundle() -> dict[str, Any]:
        summary = build_platform_frontier_summary(evaluation, metrics, release)
        package = build_platform_frontier_package_manifest(release, artifacts)
        bundle = assemble_platform_frontier_bundle(release, package, artifacts, summary)
        package_values.update({"summary": summary, "package": package, "bundle": bundle, "view": view, "sla": sla, "handoff": handoff, "access": access})
        return package_values

    stage("package-close", close_bundle, "assemble summary package and release bundle")
    summary = package_values["summary"]
    package = package_values["package"]
    bundle = package_values["bundle"]
    accepted = bool(audit.accepted and evaluation.accepted and quality.accepted and replay.deterministic and release.accepted and artifacts.complete and trace.accepted and depth.accepted and integrity.accepted and operational.accepted and performance.accepted and benchmark.accepted and package.complete and bundle.accepted)
    body = {"run_id": run_id, "stages": tuple(stages), "fixture": fixture, "evaluation": evaluation, "metrics": metrics, "quality": quality, "lineage": lineage, "replay": replay, "release": release, "artifacts": artifacts, "trace": trace, "depth": depth, "integrity": integrity, "summary": summary, "package": package, "bundle": bundle, "accepted": accepted}
    return PlatformFrontierRuntimeReport(**body, content_address=content_hash(body))


__all__ = ["PlatformFrontierRuntimeReport", "PlatformFrontierRuntimeStage", "run_platform_frontier_runtime"]
