"""Nine-stage runtime rehearsal for the C09-C12 release path."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_gamma_frontier_contracts import default_gamma_frontier_contracts
from .workspace_gamma_frontier_fixture_eval import (
    GammaFrontierEvaluation,
    evaluate_gamma_frontier_fixture,
)
from .workspace_gamma_frontier_lineage import (
    GammaFrontierLineageGraph,
    build_gamma_frontier_lineage,
)
from .workspace_gamma_frontier_metrics import GammaFrontierMetricsReport, measure_gamma_frontier
from .workspace_gamma_frontier_policy import (
    GammaFrontierPolicyDecision,
    default_gamma_frontier_policy,
)
from .workspace_gamma_frontier_projection_assertions import (
    GammaFrontierProjectionAudit,
    audit_gamma_frontier_projections,
)
from .workspace_gamma_frontier_public_data import (
    GammaFrontierDataAudit,
    GammaFrontierFixture,
    audit_gamma_frontier_data,
    default_gamma_frontier_fixture,
)
from .workspace_gamma_frontier_quality_gate import (
    GammaFrontierQualityGate,
    evaluate_gamma_frontier_quality,
)
from .workspace_gamma_frontier_reconciliation import (
    GammaFrontierReconciliation,
    reconcile_gamma_frontier,
)
from .workspace_gamma_frontier_schema import default_gamma_frontier_schema


@dataclass(frozen=True, slots=True)
class GammaFrontierRuntimeStage:
    """One ordered runtime receipt."""

    sequence: int
    stage_id: str
    state: str
    inputs: tuple[str, ...]
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierRuntimeReport:
    """Complete runtime rehearsal with all intermediate reports."""

    run_id: str
    fixture_id: str
    stages: tuple[GammaFrontierRuntimeStage, ...]
    data_audit: GammaFrontierDataAudit
    evaluation: GammaFrontierEvaluation
    metrics: GammaFrontierMetricsReport
    policy_decisions: tuple[GammaFrontierPolicyDecision, ...]
    lineage: GammaFrontierLineageGraph
    reconciliation: GammaFrontierReconciliation
    projection_audit: GammaFrontierProjectionAudit
    quality: GammaFrontierQualityGate
    accepted: bool
    content_address: str

    def stage(self, stage_id: str) -> GammaFrontierRuntimeStage:
        return next(item for item in self.stages if item.stage_id == stage_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"stage_count": len(self.stages)}


def _stage(
    sequence: int, stage_id: str, state: str, inputs: tuple[str, ...], output: str, detail: str
) -> GammaFrontierRuntimeStage:
    body = {
        "sequence": sequence,
        "stage_id": stage_id,
        "state": state,
        "inputs": inputs,
        "output_address": output,
        "detail": detail,
    }
    return GammaFrontierRuntimeStage(
        **body, content_address=content_hash(body, prefix="runtime-stage")
    )


def run_gamma_frontier_runtime(
    fixture: GammaFrontierFixture | None = None, *, run_id: str = "workspace-gamma-frontier-runtime"
) -> GammaFrontierRuntimeReport:
    """Run data, execution, policy, lineage, reconciliation, and quality stages."""

    fixture = fixture or default_gamma_frontier_fixture()
    require_non_empty(run_id, "run_id")
    stages: list[GammaFrontierRuntimeStage] = []
    data_audit = audit_gamma_frontier_data(fixture)
    stages.append(
        _stage(
            1,
            "data-audit",
            "accepted" if data_audit.accepted else "blocked",
            (fixture.content_address,),
            data_audit.content_address,
            "count and source boundary audit",
        )
    )
    evaluation = evaluate_gamma_frontier_fixture(fixture)
    stages.append(
        _stage(
            2,
            "fixture-evaluation",
            "accepted" if evaluation.accepted else "blocked",
            (data_audit.content_address,),
            evaluation.content_address,
            "positive and control surface execution",
        )
    )
    metrics = measure_gamma_frontier(evaluation)
    stages.append(
        _stage(
            3,
            "metrics",
            "complete",
            (evaluation.content_address,),
            metrics.content_address,
            "surface and control metrics",
        )
    )
    policy = default_gamma_frontier_policy()
    decisions = policy.decide(evaluation)
    policy_address = content_hash(
        {"policy": policy.content_address, "decisions": decisions}, prefix="policy-report"
    )
    stages.append(
        _stage(
            4,
            "policy",
            "complete",
            (evaluation.content_address, policy.content_address),
            policy_address,
            "ordered release and hold routing",
        )
    )
    lineage = build_gamma_frontier_lineage(fixture, evaluation)
    stages.append(
        _stage(
            5,
            "lineage",
            "complete",
            (fixture.content_address, evaluation.content_address),
            lineage.content_address,
            "source-to-output lineage",
        )
    )
    reconciliation = reconcile_gamma_frontier(fixture, evaluation, decisions)
    stages.append(
        _stage(
            6,
            "reconciliation",
            "accepted" if reconciliation.accepted else "blocked",
            (evaluation.content_address, policy_address),
            reconciliation.content_address,
            "expected and observed evidence",
        )
    )
    projection_audit = audit_gamma_frontier_projections(evaluation)
    stages.append(
        _stage(
            7,
            "projection-audit",
            "accepted" if projection_audit.accepted else "blocked",
            (evaluation.content_address,),
            projection_audit.content_address,
            "serialized output assertions",
        )
    )
    quality = evaluate_gamma_frontier_quality(
        fixture,
        evaluation,
        data_audit,
        default_gamma_frontier_contracts(),
        default_gamma_frontier_schema(),
        lineage,
        reconciliation,
        projection_audit,
    )
    stages.append(
        _stage(
            8,
            "quality-gate",
            "accepted" if quality.accepted else "blocked",
            (
                data_audit.content_address,
                reconciliation.content_address,
                projection_audit.content_address,
            ),
            quality.content_address,
            "release evidence gate",
        )
    )
    run_body = {
        "run_id": run_id,
        "fixture_id": fixture.fixture_id,
        "stages": tuple(stages),
        "data_audit": data_audit,
        "evaluation": evaluation,
        "metrics": metrics,
        "policy_decisions": decisions,
        "lineage": lineage,
        "reconciliation": reconciliation,
        "projection_audit": projection_audit,
        "quality": quality,
        "accepted": quality.accepted,
    }
    return GammaFrontierRuntimeReport(
        **run_body, content_address=content_hash(run_body, prefix="runtime")
    )


__all__ = ["GammaFrontierRuntimeReport", "GammaFrontierRuntimeStage", "run_gamma_frontier_runtime"]
