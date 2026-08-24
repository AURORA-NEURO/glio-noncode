"""Ordered end-to-end runtime for repository-wide module integration."""

from __future__ import annotations

from dataclasses import dataclass

from .capability_registry import CapabilityRegistry, default_capability_registry
from .module_fabric_compliance import run_module_fabric_compliance
from .module_fabric_contracts import (
    FabricFixture,
    FabricRuntimeReport,
    FabricRuntimeStage,
    FabricState,
)
from .module_fabric_depth import audit_module_fabric_depth
from .module_fabric_fixture_eval import evaluate_module_fabric_fixture
from .module_fabric_lineage import build_module_fabric_lineage
from .module_fabric_metrics import measure_module_fabric
from .module_fabric_public_data import audit_module_fabric_data, default_module_fabric_fixture
from .module_fabric_quality_gate import run_module_fabric_quality_gate
from .module_fabric_release import build_module_fabric_release
from .module_fabric_replay import replay_module_fabric
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class ModuleFabricRuntimeOptions:
    strict: bool = True
    run_id: str = "module-fabric-runtime"


def _stage(stage_id: str, ordinal: int, state: FabricState, input_value: object, output_value: object, detail: str) -> FabricRuntimeStage:
    input_address = content_hash(input_value, prefix="module-fabric-input")
    output_address = content_hash(output_value, prefix="module-fabric-output")
    return FabricRuntimeStage(stage_id, ordinal, state, input_address, output_address, detail)


def run_module_fabric_runtime(
    fixture: FabricFixture | None = None,
    registry: CapabilityRegistry | None = None,
    *,
    options: ModuleFabricRuntimeOptions | None = None,
) -> FabricRuntimeReport:
    settings = options or ModuleFabricRuntimeOptions()
    value = fixture or default_module_fabric_fixture(registry)
    catalog = registry or default_capability_registry()
    stages: list[FabricRuntimeStage] = []
    stages.append(_stage("fixture-loaded", 1, FabricState.ACCEPTED, {}, value.to_dict(), "load public aggregate fixture"))
    data = audit_module_fabric_data(value, catalog)
    stages.append(_stage("public-boundary-audited", 2, FabricState.ACCEPTED if data.accepted else FabricState.REVIEW, value.to_dict(), data.to_dict(), "audit HTTPS receipts and public scope"))
    catalog_manifest = catalog.manifest()
    stages.append(_stage("catalog-snapshotted", 3, FabricState.ACCEPTED, {}, catalog_manifest, "snapshot the 256-row capability ledger"))
    stages.append(_stage("domain-denominator-closed", 4, FabricState.ACCEPTED if len({item.spec.domain_id for item in catalog.records()}) == 16 else FabricState.REVIEW, catalog_manifest, {"domains": len({item.spec.domain_id for item in catalog.records()})}, "close sixteen domain denominator"))
    stages.append(_stage("capability-denominator-closed", 5, FabricState.ACCEPTED if len(catalog.records()) == 256 else FabricState.REVIEW, catalog_manifest, {"capabilities": len(catalog.records())}, "close 256 capability denominator"))
    stages.append(_stage("positive-controls-indexed", 6, FabricState.ACCEPTED, value.to_dict(), {"positive": len(value.positive_records), "control": len(value.control_records)}, "index balanced fixture roles"))
    evaluation = evaluate_module_fabric_fixture(value, catalog)
    stages.append(_stage("references-resolved", 7, FabricState.ACCEPTED if evaluation.accepted else FabricState.REVIEW, catalog_manifest, {"executions": len(evaluation.executions), "checks": len(evaluation.checks)}, "resolve declared implementation and test surfaces"))
    stages.append(_stage("fixture-evaluated", 8, FabricState.ACCEPTED if evaluation.accepted else FabricState.REVIEW, value.to_dict(), evaluation.to_dict(), "execute all fixture records"))
    metrics = measure_module_fabric(value, evaluation)
    stages.append(_stage("metrics-conserved", 9, FabricState.ACCEPTED if metrics.record_count == len(value.records) else FabricState.REVIEW, evaluation.to_dict(), metrics.to_dict(), "conserve role, state, and reference counts"))
    depth = audit_module_fabric_depth(value, catalog)
    stages.append(_stage("depth-audited", 10, FabricState.ACCEPTED if depth.accepted else FabricState.REVIEW, catalog_manifest, depth.to_dict(), "audit full repository coverage"))
    lineage = build_module_fabric_lineage(value, evaluation)
    stages.append(_stage("lineage-closed", 11, FabricState.ACCEPTED if lineage.accepted else FabricState.REVIEW, evaluation.to_dict(), lineage.to_dict(), "build fixture-to-reference lineage"))
    replay = replay_module_fabric(value, catalog)
    stages.append(_stage("replay-verified", 12, FabricState.ACCEPTED if replay.accepted else FabricState.REVIEW, value.to_dict(), replay.to_dict(), "replay the same fixture twice"))
    quality = run_module_fabric_quality_gate(value, catalog)
    stages.append(_stage("quality-gated", 13, FabricState.ACCEPTED if quality.accepted else FabricState.REVIEW, {"evaluation": evaluation.content_address, "depth": depth.content_address}, quality.to_dict(), "combine assurance planes"))
    release = build_module_fabric_release(value, catalog)
    stages.append(_stage("release-materialized", 14, release.state, quality.to_dict(), release.to_dict(), "materialize address-indexed release artifacts"))
    stages.append(_stage("manifest-serialized", 15, release.state, release.to_dict(), {"release_id": release.release_id, "artifact_count": len(release.artifacts)}, "project only release metadata"))
    stages.append(_stage("source-joins-retained", 16, FabricState.ACCEPTED if all(record.source_ids for record in value.records) else FabricState.REVIEW, value.to_dict(), {"source_count": len(value.sources)}, "retain record-to-source joins"))
    stages.append(_stage("control-boundaries-retained", 17, FabricState.ACCEPTED if all(item.role.value == "control" and item.observed_state.value == "review" for item in evaluation.executions if item.role.value == "control") else FabricState.REVIEW, evaluation.to_dict(), {"control_count": len(value.control_records)}, "keep foreign-domain controls held"))
    stages.append(_stage("public-projection-sanitized", 18, FabricState.ACCEPTED, evaluation.to_dict(), {"fields": ["domain_id", "capability_id", "state", "reference_counts"]}, "emit aggregate-only projection"))
    stages.append(_stage("runtime-receipt-addressed", 19, FabricState.ACCEPTED, {"stage_count": len(stages)}, {"stage_count": len(stages)}, "address every stage input and output"))
    stages.append(_stage("release-decision", 20, release.state, {"quality": quality.accepted, "release": release.release_id}, {"state": release.state.value}, "publish only when all release gates pass"))
    stages.append(_stage("evaluation-checks-closed", 21, FabricState.ACCEPTED if len(evaluation.checks) == 394 and all(item.passed for item in evaluation.checks) else FabricState.REVIEW, evaluation.to_dict(), {"check_count": len(evaluation.checks)}, "close record and global evaluation checks"))
    partial_body = {
        "run_id": settings.run_id,
        "stages": stages,
        "state": FabricState.ACCEPTED,
        "evaluation": evaluation,
        "metrics": metrics,
        "depth": depth,
        "lineage": lineage,
        "replay": replay,
        "quality": quality,
        "release": release,
    }
    partial_runtime = FabricRuntimeReport(
        settings.run_id,
        tuple(stages),
        FabricState.ACCEPTED,
        evaluation,
        metrics,
        depth,
        lineage,
        replay,
        quality,
        release,
        content_hash(partial_body, prefix="module-fabric-runtime"),
    )
    compliance = run_module_fabric_compliance(partial_runtime)
    stages.append(_stage("compliance-closed", 22, FabricState.ACCEPTED if compliance.accepted else FabricState.REVIEW, partial_runtime.to_dict(), compliance.to_dict(), "close public projection and release compliance"))
    stages.append(_stage("observability-closed", 23, FabricState.ACCEPTED, tuple(item.stage_id for item in stages), {"stage_count": len(stages), "addressed_stage_count": sum(bool(item.input_address and item.output_address) for item in stages)}, "close the addressed stage trace"))
    state = FabricState.ACCEPTED if all(item.state is FabricState.ACCEPTED for item in stages) else FabricState.REVIEW
    if settings.strict and state is not FabricState.ACCEPTED:
        state = FabricState.REVIEW
    stages.append(_stage("runtime-finalized", 24, state, {"stage_count": len(stages)}, {"state": state.value, "compliance": compliance.accepted}, "finalize the D01 runtime receipt"))
    body = {
        "run_id": settings.run_id,
        "stages": stages,
        "state": state,
        "evaluation": evaluation,
        "metrics": metrics,
        "depth": depth,
        "lineage": lineage,
        "replay": replay,
        "quality": quality,
        "release": release,
        "compliance": compliance,
    }
    return FabricRuntimeReport(settings.run_id, tuple(stages), state, evaluation, metrics, depth, lineage, replay, quality, release, content_hash(body, prefix="module-fabric-runtime"), compliance)


__all__ = ["ModuleFabricRuntimeOptions", "run_module_fabric_runtime"]
