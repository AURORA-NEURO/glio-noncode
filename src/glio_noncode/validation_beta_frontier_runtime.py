"""End-to-end runtime rehearsal for Domain 13 C05–C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .serialization import content_hash, jsonable, require_non_empty
from .validation_beta_frontier_adapters import (
    ValidationBetaFrontierAdapterRegistry,
    default_validation_beta_frontier_adapters,
)
from .validation_beta_frontier_contracts import (
    ValidationBetaFrontierContractRegistry,
    default_validation_beta_frontier_contracts,
)
from .validation_beta_frontier_fixture_eval import (
    ValidationBetaFrontierEvaluation,
    evaluate_validation_beta_frontier_fixture,
)
from .validation_beta_frontier_governance import (
    ValidationBetaFrontierArtifactInventory,
    ValidationBetaFrontierClaimBoundary,
    ValidationBetaFrontierControlCoverage,
    ValidationBetaFrontierDepthAudit,
    ValidationBetaFrontierFailureInjectionReport,
    ValidationBetaFrontierIntegrityReport,
    ValidationBetaFrontierLineage,
    ValidationBetaFrontierMetrics,
    ValidationBetaFrontierObservabilityReport,
    ValidationBetaFrontierOperationalMatrix,
    ValidationBetaFrontierPolicy,
    ValidationBetaFrontierQualityGate,
    ValidationBetaFrontierReconciliation,
    ValidationBetaFrontierReleaseBundle,
    ValidationBetaFrontierReleaseManifest,
    ValidationBetaFrontierReplayReceipt,
    ValidationBetaFrontierReviewQueue,
    ValidationBetaFrontierScenarioMatrix,
    ValidationBetaFrontierSourceRegistry,
    ValidationBetaFrontierRunbook,
    assemble_validation_beta_frontier_bundle,
    audit_validation_beta_frontier_depth,
    build_validation_beta_frontier_artifact_inventory,
    build_validation_beta_frontier_claim_boundary,
    build_validation_beta_frontier_control_coverage,
    build_validation_beta_frontier_lineage,
    build_validation_beta_frontier_operational_matrix,
    build_validation_beta_frontier_release_manifest,
    build_validation_beta_frontier_review_queue,
    build_validation_beta_frontier_runbook,
    build_validation_beta_frontier_scenario_matrix,
    build_validation_beta_frontier_source_registry,
    evaluate_validation_beta_frontier_integrity,
    evaluate_validation_beta_frontier_quality,
    materialize_validation_beta_frontier_policy,
    measure_validation_beta_frontier,
    observe_validation_beta_frontier,
    reconcile_validation_beta_frontier,
    replay_validation_beta_frontier,
    run_validation_beta_frontier_failure_injections,
)
from .validation_beta_frontier_public_data import (
    ValidationBetaFrontierDataAudit,
    ValidationBetaFrontierFixture,
    audit_validation_beta_frontier_data,
    default_validation_beta_frontier_fixture,
)
from .validation_beta_frontier_runtime_types import ValidationBetaFrontierRuntimeStage
from .validation_beta_frontier_handoff import (
    ValidationBetaFrontierHandoff,
    build_validation_beta_frontier_handoff,
)
from .validation_beta_frontier_schema import (
    ValidationBetaFrontierSchemaReport,
    default_validation_beta_frontier_schema,
)
from .validation_beta_frontier_thresholds import (
    ValidationBetaFrontierThresholdReport,
    build_validation_beta_frontier_threshold_report,
)
from .validation_beta_frontier_validation_matrix import (
    ValidationBetaFrontierValidationMatrix,
    build_validation_beta_frontier_validation_matrix,
)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierRuntimeReport:
    run_id: str
    fixture: ValidationBetaFrontierFixture
    data_audit: ValidationBetaFrontierDataAudit
    adapters: ValidationBetaFrontierAdapterRegistry
    contracts: ValidationBetaFrontierContractRegistry
    schema: ValidationBetaFrontierSchemaReport
    evaluation: ValidationBetaFrontierEvaluation
    metrics: ValidationBetaFrontierMetrics
    lineage: ValidationBetaFrontierLineage
    policy: ValidationBetaFrontierPolicy
    reconciliation: ValidationBetaFrontierReconciliation
    quality: ValidationBetaFrontierQualityGate
    replay: ValidationBetaFrontierReplayReceipt
    release: ValidationBetaFrontierReleaseManifest
    bundle: ValidationBetaFrontierReleaseBundle
    review: ValidationBetaFrontierReviewQueue
    scenarios: ValidationBetaFrontierScenarioMatrix
    depth: ValidationBetaFrontierDepthAudit
    thresholds: ValidationBetaFrontierThresholdReport
    validation_matrix: ValidationBetaFrontierValidationMatrix
    handoff: ValidationBetaFrontierHandoff
    artifacts: ValidationBetaFrontierArtifactInventory
    claim_boundary: ValidationBetaFrontierClaimBoundary
    control_coverage: ValidationBetaFrontierControlCoverage
    operational: ValidationBetaFrontierOperationalMatrix
    integrity: ValidationBetaFrontierIntegrityReport
    failure_injections: ValidationBetaFrontierFailureInjectionReport
    runbook: ValidationBetaFrontierRunbook
    observability: ValidationBetaFrontierObservabilityReport
    stages: tuple[ValidationBetaFrontierRuntimeStage, ...]
    accepted: bool
    content_address: str

    @property
    def stage_ids(self) -> tuple[str, ...]:
        return tuple(item.stage_id for item in self.stages)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"stage_ids": self.stage_ids}


def run_validation_beta_frontier_runtime(
    fixture: ValidationBetaFrontierFixture | None = None,
    *,
    run_id: str = "validation-beta-frontier-runtime",
) -> ValidationBetaFrontierRuntimeReport:
    """Run all evidence, control, and release stages in deterministic order."""

    value = fixture or default_validation_beta_frontier_fixture()
    require_non_empty(run_id, "run_id")
    stages: list[ValidationBetaFrontierRuntimeStage] = []

    def stage(stage_id: str, output: Any, accepted: bool, detail: str) -> Any:
        serialized = output.to_dict() if hasattr(output, "to_dict") else output
        output_address = str(getattr(output, "content_address", content_hash(jsonable(serialized), prefix="validation-beta-stage-output")))
        body = {"sequence": len(stages) + 1, "stage_id": stage_id, "accepted": accepted, "state": "completed" if accepted else "held", "output_address": output_address, "detail": detail}
        stages.append(ValidationBetaFrontierRuntimeStage(**body, content_address=content_hash(body, prefix="validation-beta-runtime-stage")))
        return output

    data_audit = stage("data-audit", audit_validation_beta_frontier_data(value), True, "audit public source and record boundary")
    source_registry = stage("source-registry", build_validation_beta_frontier_source_registry(value), True, "close public source receipts")
    adapters = stage("adapters", default_validation_beta_frontier_adapters(), True, "load eight input adapters")
    contracts = stage("contracts", default_validation_beta_frontier_contracts(), True, "load eight typed contracts")
    schema = stage("schema", default_validation_beta_frontier_schema(), True, "load eight operation schemas")
    evaluation = stage("fixture-evaluation", evaluate_validation_beta_frontier_fixture(value), True, "execute all positive and control rows")
    metrics = stage("metrics", measure_validation_beta_frontier(evaluation), True, "measure operation, state, and issue coverage")
    lineage = stage("lineage", build_validation_beta_frontier_lineage(value, evaluation), True, "connect public sources to results")
    policy = stage("policy", materialize_validation_beta_frontier_policy(evaluation), True, "apply state-aware research policy")
    reconciliation = stage("reconciliation", reconcile_validation_beta_frontier(value, evaluation), True, "reconcile expected states and issue floors")
    quality = stage("quality", evaluate_validation_beta_frontier_quality(value, evaluation, contracts, schema, lineage, reconciliation), True, "run blocking quality checks")
    replay = stage("replay", replay_validation_beta_frontier(value, replay_id=run_id + "-replay"), True, "replay the fixture twice")
    review = stage("review-queue", build_validation_beta_frontier_review_queue(evaluation, policy), True, "retain non-publishable rows for review")
    scenarios = stage("scenarios", build_validation_beta_frontier_scenario_matrix(evaluation, policy), True, "materialize all positive and control scenarios")
    depth = audit_validation_beta_frontier_depth(value, evaluation, metrics, lineage, quality)
    thresholds = build_validation_beta_frontier_threshold_report()
    validation_matrix = build_validation_beta_frontier_validation_matrix(value, evaluation)
    handoff = build_validation_beta_frontier_handoff(value, evaluation, handoff_id=run_id + "-handoff")
    stage(
        "depth",
        {"depth": depth.to_dict(), "thresholds": thresholds.to_dict(), "validation_matrix": validation_matrix.to_dict(), "handoff": handoff.to_dict()},
        bool(depth.accepted and thresholds.accepted and validation_matrix.accepted and handoff.accepted),
        "run implementation-depth thresholds and publication handoff checks",
    )
    artifacts = stage("artifacts", build_validation_beta_frontier_artifact_inventory(value, evaluation), True, "index addressed release artifacts")
    claim_boundary = stage("claim-boundary", build_validation_beta_frontier_claim_boundary(), True, "attach allowed and excluded uses")
    control_coverage = stage("control-coverage", build_validation_beta_frontier_control_coverage(evaluation), True, "verify three controls per operation")
    operational = stage("operational", build_validation_beta_frontier_operational_matrix(policy), True, "materialize consumer dispositions")
    integrity = stage("integrity", evaluate_validation_beta_frontier_integrity(value, evaluation), True, "check address and source closure")
    failure_injections = stage("failure-injections", run_validation_beta_frontier_failure_injections(value), True, "exercise declared negative boundaries")
    release = stage("release", build_validation_beta_frontier_release_manifest(quality, replay, policy, release_id=run_id + "-release"), True, "build bounded review release manifest")
    bundle = stage("bundle", assemble_validation_beta_frontier_bundle(value, evaluation, lineage, policy, quality, release, bundle_id=run_id + "-bundle"), True, "assemble content-addressed release bundle")
    runbook = stage("runbook", build_validation_beta_frontier_runbook(), True, "emit executable operator sequence")
    stage_outputs = tuple((item.stage_id, "completed" if item.accepted else "held", item.output_address) for item in stages)
    observability = stage("observability", observe_validation_beta_frontier(run_id, stage_outputs), True, "emit structured stage events")
    accepted = all(item.accepted for item in stages) and bool(data_audit.accepted and evaluation.accepted and quality.accepted and thresholds.accepted and validation_matrix.accepted and handoff.accepted and release.ready and bundle.publishable and observability.accepted)
    body = {"run_id": run_id, "fixture": value.content_address, "stages": tuple(stages), "release": release.content_address, "bundle": bundle.content_address, "accepted": accepted}
    return ValidationBetaFrontierRuntimeReport(run_id, value, data_audit, adapters, contracts, schema, evaluation, metrics, lineage, policy, reconciliation, quality, replay, release, bundle, review, scenarios, depth, thresholds, validation_matrix, handoff, artifacts, claim_boundary, control_coverage, operational, integrity, failure_injections, runbook, observability, tuple(stages), accepted, content_hash(body, prefix="validation-beta-runtime"))


__all__ = ["ValidationBetaFrontierRuntimeReport", "ValidationBetaFrontierRuntimeStage", "run_validation_beta_frontier_runtime"]
