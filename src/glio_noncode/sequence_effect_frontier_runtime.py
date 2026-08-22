"""Ordered runtime pipeline for Domain 06 C01–C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_effect_frontier_fixture_eval import (
    SequenceEffectEvaluation,
    evaluate_sequence_effect_fixture,
)
from .sequence_effect_frontier_public_data import (
    SequenceEffectFixture,
    default_sequence_effect_fixture,
)
from .sequence_effect_frontier_quality_gate import (
    SequenceEffectQualityReport,
    run_sequence_effect_quality_gate,
)
from .sequence_effect_frontier_replay import (
    SequenceEffectReplayReport,
    replay_sequence_effect_evaluation,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceEffectRuntimeOptions:
    run_id: str = "sequence-effect-runtime"
    requested_context_key: str | None = None
    fail_on_review: bool = False

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValidationError("run_id is required")


@dataclass(frozen=True, slots=True)
class SequenceEffectRuntimeStage:
    stage_id: str
    ordinal: int
    status: str
    input_address: str
    output_address: str
    counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceEffectRuntimeReport:
    run_id: str
    status: str
    accepted: bool
    stages: tuple[SequenceEffectRuntimeStage, ...]
    evaluation: SequenceEffectEvaluation
    quality: SequenceEffectQualityReport
    replay: SequenceEffectReplayReport
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.stages) != 10:
            raise ValueError("sequence-effect runtime requires ten ordered stages")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "run_id": self.run_id,
                        "status": self.status,
                        "accepted": self.accepted,
                        "stages": self.stages,
                        "evaluation": self.evaluation.content_address,
                        "quality": self.quality.content_address,
                        "replay": self.replay.content_address,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "accepted": self.accepted,
            "stages": [item.to_dict() for item in self.stages],
            "evaluation": {
                "accepted": self.evaluation.accepted,
                "content_address": self.evaluation.content_address,
            },
            "quality": {
                "accepted": self.quality.accepted,
                "content_address": self.quality.content_address,
                "check_count": len(self.quality.checks),
            },
            "replay": self.replay.to_dict(),
            "content_address": self.content_address,
        }


def run_sequence_effect_pipeline(
    options: SequenceEffectRuntimeOptions | None = None,
    *,
    fixture: SequenceEffectFixture | None = None,
) -> SequenceEffectRuntimeReport:
    options = options or SequenceEffectRuntimeOptions()
    fixture = fixture or default_sequence_effect_fixture()
    context_ok = options.requested_context_key in {None, fixture.context_key}
    evaluation = evaluate_sequence_effect_fixture(fixture)
    quality = run_sequence_effect_quality_gate(fixture)
    replay = replay_sequence_effect_evaluation(
        evaluation, fixture, replay_id=f"{options.run_id}:replay"
    )
    review_count = sum(bool(item.issue_codes) for item in evaluation.executions)
    status = (
        "ready"
        if context_ok
        and evaluation.accepted
        and quality.accepted
        and replay.accepted
        and (not options.fail_on_review or review_count == 0)
        else "rejected"
    )
    stages = (
        SequenceEffectRuntimeStage(
            "data-boundary",
            1,
            "accepted" if context_ok else "rejected",
            fixture.content_address,
            fixture.content_address,
            {"sources": len(fixture.sources), "records": len(fixture.records)},
        ),
        SequenceEffectRuntimeStage(
            "fixture-evaluation",
            2,
            "accepted" if evaluation.accepted else "rejected",
            fixture.content_address,
            evaluation.content_address,
            {"checks": len(evaluation.checks), "executions": len(evaluation.executions)},
        ),
        SequenceEffectRuntimeStage(
            "contracts",
            3,
            "accepted",
            evaluation.content_address,
            quality.schema.content_address,
            {"operations": 4},
        ),
        SequenceEffectRuntimeStage(
            "schema",
            4,
            "accepted" if quality.schema.accepted else "rejected",
            quality.schema.content_address,
            quality.schema.content_address,
            {"schemas": len(quality.schema.schemas)},
        ),
        SequenceEffectRuntimeStage(
            "metrics",
            5,
            "accepted",
            evaluation.content_address,
            quality.metrics.content_address,
            {"operation_metrics": len(quality.metrics.operation_metrics)},
        ),
        SequenceEffectRuntimeStage(
            "lineage",
            6,
            "accepted" if quality.lineage.accepted else "rejected",
            fixture.content_address,
            quality.lineage.content_address,
            {"nodes": len(quality.lineage.nodes), "edges": len(quality.lineage.edges)},
        ),
        SequenceEffectRuntimeStage(
            "policy",
            7,
            "accepted" if quality.policy.accepted else "rejected",
            evaluation.content_address,
            quality.policy.content_address,
            {"decisions": len(quality.policy.decisions)},
        ),
        SequenceEffectRuntimeStage(
            "reconciliation",
            8,
            "accepted" if quality.reconciliation.accepted else "rejected",
            evaluation.content_address,
            quality.reconciliation.content_address,
            {"items": len(quality.reconciliation.items)},
        ),
        SequenceEffectRuntimeStage(
            "replay",
            9,
            "accepted" if replay.accepted else "rejected",
            evaluation.content_address,
            replay.content_address,
            {"checks": len(replay.checks)},
        ),
        SequenceEffectRuntimeStage(
            "release-gate",
            10,
            status,
            quality.content_address,
            quality.content_address,
            {"review_records": review_count, "fail_on_review": int(options.fail_on_review)},
        ),
    )
    return SequenceEffectRuntimeReport(
        options.run_id, status, status == "ready", stages, evaluation, quality, replay
    )


__all__ = [
    "SequenceEffectRuntimeOptions",
    "SequenceEffectRuntimeReport",
    "SequenceEffectRuntimeStage",
    "run_sequence_effect_pipeline",
]
