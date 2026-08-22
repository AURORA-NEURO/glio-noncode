"""Ordered runtime rehearsal for the C05-C08 release package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_beta_frontier_bundle import BetaFrontierReleaseBundle, assemble_beta_frontier_bundle
from .workspace_beta_frontier_contracts import default_beta_frontier_contracts
from .workspace_beta_frontier_fixture_eval import (
    BetaFrontierEvaluation,
    evaluate_beta_frontier_fixture,
)
from .workspace_beta_frontier_lineage import build_beta_frontier_lineage
from .workspace_beta_frontier_metrics import BetaFrontierMetricsReport, measure_beta_frontier
from .workspace_beta_frontier_policy import default_beta_frontier_policy
from .workspace_beta_frontier_public_data import BetaFrontierFixture, default_beta_frontier_fixture
from .workspace_beta_frontier_quality_gate import (
    BetaFrontierQualityGate,
    evaluate_beta_frontier_quality,
)
from .workspace_beta_frontier_reconciliation import (
    BetaFrontierReconciliation,
    reconcile_beta_frontier,
)
from .workspace_beta_frontier_schema import default_beta_frontier_schema


@dataclass(frozen=True, slots=True)
class BetaFrontierRuntimeStage:
    """One ordered runtime stage and its input/output addresses."""

    sequence: int
    stage_id: str
    state: str
    input_addresses: tuple[str, ...]
    output_address: str
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError("beta frontier runtime sequence must be positive")
        require_non_empty(self.stage_id, "stage_id")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierRuntimeReport:
    """Complete runtime rehearsal output."""

    run_id: str
    fixture_id: str
    stages: tuple[BetaFrontierRuntimeStage, ...]
    evaluation: BetaFrontierEvaluation
    metrics: BetaFrontierMetricsReport
    reconciliation: BetaFrontierReconciliation
    quality: BetaFrontierQualityGate
    bundle: BetaFrontierReleaseBundle
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _stage(sequence: int, stage_id: str, state: str, inputs: tuple[str, ...], output: str, detail: str) -> BetaFrontierRuntimeStage:
    body = {"sequence": sequence, "stage_id": stage_id, "state": state, "input_addresses": inputs, "output_address": output, "detail": detail}
    return BetaFrontierRuntimeStage(**body, content_address=content_hash(body))


def run_beta_frontier_runtime(
    fixture: BetaFrontierFixture | None = None,
    *,
    run_id: str = "workspace-beta-frontier-runtime",
) -> BetaFrontierRuntimeReport:
    """Run the full C05-C08 package in a fixed eight-stage order."""

    fixture = fixture or default_beta_frontier_fixture()
    contracts = default_beta_frontier_contracts()
    schema = default_beta_frontier_schema()
    policy = default_beta_frontier_policy()
    evaluation = evaluate_beta_frontier_fixture(fixture)
    metrics = measure_beta_frontier(evaluation)
    lineage = build_beta_frontier_lineage(fixture, evaluation)
    reconciliation = reconcile_beta_frontier(fixture, evaluation, policy)
    quality = evaluate_beta_frontier_quality(fixture, evaluation, contracts, schema, lineage, reconciliation)
    bundle = assemble_beta_frontier_bundle(fixture, evaluation, metrics, reconciliation)
    stages = (
        _stage(1, "fixture-load", "complete", (), fixture.content_address, "load public aggregate projection fixture"),
        _stage(2, "contract-schema-load", "complete", (), content_hash((contracts.content_address, schema.content_address)), "load operation contracts and field schema"),
        _stage(3, "projection-execution", "complete" if evaluation.accepted else "failed", (fixture.content_address, contracts.content_address), evaluation.content_address, "execute topology, causal, posterior, and table projections"),
        _stage(4, "metric-measurement", "complete", (evaluation.content_address,), metrics.content_address, "measure state, control, and output visibility"),
        _stage(5, "lineage-build", "complete" if lineage.acyclic else "failed", (fixture.content_address, evaluation.content_address), lineage.content_address, "build source-to-output lineage"),
        _stage(6, "policy-application", "complete", (evaluation.content_address, policy.content_address), content_hash(policy.decide(evaluation)), "apply research-use policy"),
        _stage(7, "reconciliation", "complete" if reconciliation.reconciled else "failed", (evaluation.content_address,), reconciliation.content_address, "reconcile fixture expectations and observed outputs"),
        _stage(8, "quality-bundle", "complete" if quality.accepted and bundle.accepted else "failed", (quality.content_address, reconciliation.content_address), bundle.content_address, "assemble quality-gated release inputs"),
    )
    accepted = evaluation.accepted and reconciliation.reconciled and quality.accepted and bundle.accepted
    body = {"run_id": run_id, "fixture_id": fixture.fixture_id, "stages": stages, "evaluation": evaluation, "metrics": metrics, "reconciliation": reconciliation, "quality": quality, "bundle": bundle, "accepted": accepted}
    return BetaFrontierRuntimeReport(**body, content_address=content_hash(body))


__all__ = ["BetaFrontierRuntimeReport", "BetaFrontierRuntimeStage", "run_beta_frontier_runtime"]
