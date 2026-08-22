"""Ordered runtime stages for producing the workspace frontier bundle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_frontier_bundle import (
    WorkspaceFrontierReleaseBundle,
    assemble_workspace_frontier_bundle,
)
from .workspace_frontier_contracts import default_workspace_frontier_contracts
from .workspace_frontier_fixture_eval import (
    WorkspaceFrontierEvaluation,
    evaluate_workspace_frontier_fixture,
)
from .workspace_frontier_lineage import build_workspace_frontier_lineage
from .workspace_frontier_metrics import WorkspaceFrontierMetricsReport, measure_workspace_frontier
from .workspace_frontier_policy import default_workspace_frontier_policy
from .workspace_frontier_public_data import (
    WorkspaceFrontierFixture,
    default_workspace_frontier_fixture,
)
from .workspace_frontier_reconciliation import (
    WorkspaceFrontierReconciliation,
    reconcile_workspace_frontier,
)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierRuntimeStage:
    sequence: int
    stage_id: str
    state: str
    input_addresses: tuple[str, ...]
    output_address: str
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError("workspace runtime sequence must be positive")
        require_non_empty(self.stage_id, "stage_id")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierRuntimeReport:
    run_id: str
    fixture_id: str
    stages: tuple[WorkspaceFrontierRuntimeStage, ...]
    evaluation: WorkspaceFrontierEvaluation
    metrics: WorkspaceFrontierMetricsReport
    reconciliation: WorkspaceFrontierReconciliation
    bundle: WorkspaceFrontierReleaseBundle
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _stage(sequence: int, stage_id: str, state: str, inputs: tuple[str, ...], output: str, detail: str) -> WorkspaceFrontierRuntimeStage:
    body = {"sequence": sequence, "stage_id": stage_id, "state": state, "input_addresses": inputs, "output_address": output, "detail": detail}
    return WorkspaceFrontierRuntimeStage(**body, content_address=content_hash(body))


def run_workspace_frontier_runtime(fixture: WorkspaceFrontierFixture | None = None, *, run_id: str = "workspace-frontier-runtime") -> WorkspaceFrontierRuntimeReport:
    fixture = fixture or default_workspace_frontier_fixture()
    policy = default_workspace_frontier_policy()
    contracts = default_workspace_frontier_contracts()
    evaluation = evaluate_workspace_frontier_fixture(fixture)
    metrics = measure_workspace_frontier(evaluation)
    replayable_lineage = build_workspace_frontier_lineage(fixture, evaluation)
    reconciliation = reconcile_workspace_frontier(fixture, evaluation, policy)
    bundle = assemble_workspace_frontier_bundle(fixture, evaluation, metrics, reconciliation)
    stages = (
        _stage(1, "fixture-load", "complete", (), fixture.content_address, "load bounded public aggregate fixture"),
        _stage(2, "contract-load", "complete", (), contracts.content_address, "load four operation contracts"),
        _stage(3, "surface-execution", "complete" if evaluation.accepted else "failed", (fixture.content_address, contracts.content_address), evaluation.content_address, "execute case, cohort, variant, and track surfaces"),
        _stage(4, "metric-measurement", "complete", (evaluation.content_address,), metrics.content_address, "measure descriptive surface and boundary metrics"),
        _stage(5, "lineage-build", "complete" if replayable_lineage.acyclic else "failed", (fixture.content_address, evaluation.content_address), replayable_lineage.content_address, "build acyclic source lineage"),
        _stage(6, "policy-review", "complete", (evaluation.content_address, policy.content_address), content_hash(policy.decide(evaluation)), "apply research-use decisions"),
        _stage(7, "reconciliation", "complete" if reconciliation.reconciled else "failed", (evaluation.content_address, policy.content_address), reconciliation.content_address, "reconcile expected and observed rows"),
        _stage(8, "bundle-assembly", "complete" if bundle.accepted else "failed", (fixture.content_address, evaluation.content_address, metrics.content_address, reconciliation.content_address), bundle.content_address, "assemble release inputs"),
    )
    body = {"run_id": run_id, "fixture_id": fixture.fixture_id, "stages": stages, "evaluation": evaluation, "metrics": metrics, "reconciliation": reconciliation, "bundle": bundle, "accepted": evaluation.accepted and reconciliation.reconciled and bundle.accepted}
    return WorkspaceFrontierRuntimeReport(**body, content_address=content_hash(body))


__all__ = ["WorkspaceFrontierRuntimeReport", "WorkspaceFrontierRuntimeStage", "run_workspace_frontier_runtime"]
