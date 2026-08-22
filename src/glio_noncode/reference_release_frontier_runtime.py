"""Nine-stage runtime rehearsal for the reference release frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .reference_release_frontier_contracts import (
    ReferenceReleaseContractRegistry,
    default_reference_release_contracts,
)
from .reference_release_frontier_fixture_eval import (
    ReferenceReleaseEvaluation,
    evaluate_reference_release_fixture,
)
from .reference_release_frontier_lineage import (
    ReferenceReleaseLineageGraph,
    build_reference_release_lineage,
)
from .reference_release_frontier_metrics import (
    ReferenceReleaseMetricsReport,
    build_reference_release_metrics,
)
from .reference_release_frontier_policy import (
    ReferenceReleasePolicyReport,
    evaluate_reference_release_policy,
)
from .reference_release_frontier_projection_assertions import (
    ReferenceReleaseProjectionAudit,
    audit_reference_release_projections,
)
from .reference_release_frontier_public_data import (
    ReferenceReleaseDataAudit,
    ReferenceReleaseFixture,
    audit_reference_release_data,
    default_reference_release_fixture,
)
from .reference_release_frontier_quality_gate import (
    ReferenceReleaseQualityGate,
    evaluate_reference_release_quality,
)
from .reference_release_frontier_reconciliation import (
    ReferenceReleaseReconciliation,
    reconcile_reference_release_views,
)
from .reference_release_frontier_replay import (
    ReferenceReleaseReplayReceipt,
    replay_reference_release_evaluation,
)
from .reference_release_frontier_schema import (
    ReferenceReleaseSchemaRegistry,
    default_reference_release_schema,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ReferenceReleaseRuntimeStage:
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
class ReferenceReleaseRuntimeReport:
    """All intermediate reports and the final runtime acceptance state."""

    run_id: str
    fixture_id: str
    stages: tuple[ReferenceReleaseRuntimeStage, ...]
    data_audit: ReferenceReleaseDataAudit
    evaluation: ReferenceReleaseEvaluation
    metrics: ReferenceReleaseMetricsReport
    policy: ReferenceReleasePolicyReport
    lineage: ReferenceReleaseLineageGraph
    projection: ReferenceReleaseProjectionAudit
    reconciliation: ReferenceReleaseReconciliation
    quality: ReferenceReleaseQualityGate
    replay: ReferenceReleaseReplayReceipt
    contracts: ReferenceReleaseContractRegistry
    schema: ReferenceReleaseSchemaRegistry
    accepted: bool
    content_address: str

    def stage(self, stage_id: str) -> ReferenceReleaseRuntimeStage:
        return next(item for item in self.stages if item.stage_id == stage_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "fixture_id": self.fixture_id,
            "stages": [item.to_dict() for item in self.stages],
            "data_audit": self.data_audit.to_dict(),
            "evaluation": self.evaluation.to_dict(),
            "metrics": self.metrics.to_dict(),
            "policy": self.policy.to_dict(),
            "lineage": self.lineage.to_dict(),
            "projection": self.projection.to_dict(),
            "reconciliation": self.reconciliation.to_dict(),
            "quality": self.quality.to_dict(),
            "replay": self.replay.to_dict(),
            "contracts": self.contracts.manifest(),
            "schema": self.schema.manifest(),
            "accepted": self.accepted,
            "content_address": self.content_address,
            "stage_count": len(self.stages),
        }


def _stage(
    sequence: int, stage_id: str, state: str, inputs: tuple[str, ...], output: str, detail: str
) -> ReferenceReleaseRuntimeStage:
    body = {
        "sequence": sequence,
        "stage_id": stage_id,
        "state": state,
        "inputs": inputs,
        "output_address": output,
        "detail": detail,
    }
    return ReferenceReleaseRuntimeStage(
        **body, content_address=content_hash(body, prefix="release-runtime-stage")
    )


def run_reference_release_runtime(
    fixture: ReferenceReleaseFixture | None = None,
    *,
    run_id: str = "reference-release-frontier-runtime",
) -> ReferenceReleaseRuntimeReport:
    """Run data, execution, policy, lineage, quality, and replay stages."""

    fixture = fixture or default_reference_release_fixture()
    require_non_empty(run_id, "run_id")
    stages: list[ReferenceReleaseRuntimeStage] = []
    data_audit = audit_reference_release_data(fixture)
    stages.append(
        _stage(
            1,
            "data-audit",
            "accepted" if data_audit.accepted else "blocked",
            (fixture.content_address,),
            data_audit.content_address,
            "fixture count and source closure",
        )
    )
    evaluation = evaluate_reference_release_fixture(fixture)
    stages.append(
        _stage(
            2,
            "fixture-evaluation",
            "accepted" if evaluation.accepted else "blocked",
            (data_audit.content_address,),
            evaluation.content_address,
            "positive and control execution",
        )
    )
    metrics = build_reference_release_metrics(evaluation)
    stages.append(
        _stage(
            3,
            "metrics",
            "complete",
            (evaluation.content_address,),
            metrics.content_address,
            "state and issue metrics",
        )
    )
    policy = evaluate_reference_release_policy(fixture, evaluation)
    stages.append(
        _stage(
            4,
            "policy",
            "accepted" if policy.accepted else "blocked",
            (evaluation.content_address,),
            policy.content_address,
            "release policy decisions",
        )
    )
    lineage = build_reference_release_lineage(fixture, evaluation)
    stages.append(
        _stage(
            5,
            "lineage",
            "complete",
            (fixture.content_address, evaluation.content_address),
            lineage.content_address,
            "source-to-receipt lineage",
        )
    )
    projection = audit_reference_release_projections(evaluation)
    stages.append(
        _stage(
            6,
            "projection-audit",
            "accepted" if projection.accepted else "blocked",
            (evaluation.content_address,),
            projection.content_address,
            "schema and redaction assertions",
        )
    )
    reconciliation = reconcile_reference_release_views(
        fixture, data_audit, evaluation, projection, policy, lineage
    )
    stages.append(
        _stage(
            7,
            "reconciliation",
            "accepted" if reconciliation.accepted else "blocked",
            (evaluation.content_address, policy.content_address, lineage.content_address),
            reconciliation.content_address,
            "cross-view identity and count closure",
        )
    )
    contracts = default_reference_release_contracts()
    schema = default_reference_release_schema()
    quality = evaluate_reference_release_quality(
        fixture,
        data_audit,
        evaluation,
        contracts,
        schema,
        lineage,
        reconciliation,
        projection,
        policy,
    )
    stages.append(
        _stage(
            8,
            "quality-gate",
            "accepted" if quality.accepted else "blocked",
            (reconciliation.content_address, projection.content_address),
            quality.content_address,
            "complete release-quality gate",
        )
    )
    replay = replay_reference_release_evaluation(
        evaluation, fixture=fixture, replay_id=f"{run_id}:replay"
    )
    stages.append(
        _stage(
            9,
            "replay",
            "accepted" if replay.accepted else "blocked",
            (evaluation.content_address,),
            replay.content_address,
            "deterministic rerun",
        )
    )
    accepted = all(
        (
            data_audit.accepted,
            evaluation.accepted,
            policy.accepted,
            projection.accepted,
            reconciliation.accepted,
            quality.accepted,
            replay.accepted,
        )
    )
    body = {
        "run_id": run_id,
        "fixture_id": fixture.fixture_id,
        "stages": tuple(stages),
        "data_audit": data_audit,
        "evaluation": evaluation,
        "metrics": metrics,
        "policy": policy,
        "lineage": lineage,
        "projection": projection,
        "reconciliation": reconciliation,
        "quality": quality,
        "replay": replay,
        "contracts": contracts,
        "schema": schema,
        "accepted": accepted,
    }
    address_body = dict(body)
    address_body["contracts"] = contracts.manifest()
    address_body["schema"] = schema.manifest()
    return ReferenceReleaseRuntimeReport(
        **body,
        content_address=content_hash(address_body, prefix="release-runtime"),
    )


__all__ = [
    "ReferenceReleaseRuntimeReport",
    "ReferenceReleaseRuntimeStage",
    "run_reference_release_runtime",
]
