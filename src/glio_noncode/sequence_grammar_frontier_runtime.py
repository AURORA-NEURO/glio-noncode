"""Deterministic runtime stages for sequence grammar evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_grammar_frontier_fixture_eval import (
    SequenceGrammarEvaluation,
    evaluate_sequence_grammar_fixture,
)
from .sequence_grammar_frontier_lineage import (
    SequenceGrammarLineage,
    build_sequence_grammar_lineage,
)
from .sequence_grammar_frontier_metrics import (
    SequenceGrammarMetrics,
    compute_sequence_grammar_metrics,
)
from .sequence_grammar_frontier_policy import (
    SequenceGrammarPolicyReport,
    evaluate_sequence_grammar_policy,
)
from .sequence_grammar_frontier_public_data import (
    SequenceGrammarFixture,
    audit_sequence_grammar_data,
)
from .sequence_grammar_frontier_quality_gate import (
    SequenceGrammarQualityReport,
    run_sequence_grammar_quality_gate,
)
from .sequence_grammar_frontier_reconciliation import (
    SequenceGrammarReconciliation,
    reconcile_sequence_grammar,
)
from .sequence_grammar_frontier_schema import (
    SequenceGrammarSchemaReport,
    validate_sequence_grammar_schema,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceGrammarRuntimeOptions:
    run_id: str = "sequence-grammar-runtime"
    fail_on_review: bool = False
    strict_boundary: bool = True

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValidationError("runtime run_id is required")


@dataclass(frozen=True, slots=True)
class SequenceGrammarRuntimeStage:
    ordinal: int
    stage_id: str
    status: str
    detail: str
    receipt: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceGrammarRuntimeReport:
    run_id: str
    status: str
    accepted: bool
    stages: tuple[SequenceGrammarRuntimeStage, ...]
    evaluation: SequenceGrammarEvaluation
    schema: SequenceGrammarSchemaReport
    metrics: SequenceGrammarMetrics
    lineage: SequenceGrammarLineage
    policy: SequenceGrammarPolicyReport
    reconciliation: SequenceGrammarReconciliation
    quality: SequenceGrammarQualityReport
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.run_id.strip() or len(self.stages) != 10:
            raise ValidationError("runtime requires run ID and ten stages")
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
                        "schema": self.schema.content_address,
                        "metrics": self.metrics.content_address,
                        "lineage": self.lineage.content_address,
                        "policy": self.policy.content_address,
                        "reconciliation": self.reconciliation.content_address,
                        "quality": self.quality.content_address,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "accepted": self.accepted,
            "stages": [stage.to_dict() for stage in self.stages],
            "evaluation": self.evaluation.to_dict(),
            "schema": self.schema.to_dict(),
            "metrics": self.metrics.to_dict(),
            "lineage": self.lineage.to_dict(),
            "policy": self.policy.to_dict(),
            "reconciliation": self.reconciliation.to_dict(),
            "quality": self.quality.to_dict(),
            "content_address": self.content_address,
        }


def run_sequence_grammar_pipeline(
    options: SequenceGrammarRuntimeOptions | None = None, *, fixture: SequenceGrammarFixture
) -> SequenceGrammarRuntimeReport:
    options = options or SequenceGrammarRuntimeOptions()
    data_audit = audit_sequence_grammar_data(fixture)
    evaluation = evaluate_sequence_grammar_fixture(fixture)
    schema = validate_sequence_grammar_schema(fixture, evaluation)
    metrics = compute_sequence_grammar_metrics(evaluation)
    lineage = build_sequence_grammar_lineage(fixture, evaluation)
    policy = evaluate_sequence_grammar_policy(fixture, evaluation)
    reconciliation = reconcile_sequence_grammar(fixture, evaluation, policy)
    quality = run_sequence_grammar_quality_gate(fixture)
    stage_values = (
        ("ingest", True, "fixture loaded", fixture.content_address),
        (
            "data-audit",
            data_audit.accepted,
            "source and record closure checked",
            data_audit.content_address,
        ),
        ("evaluate", evaluation.accepted, "six checks per execution", evaluation.content_address),
        ("schema", schema.accepted, "payload and state schemas checked", schema.content_address),
        ("metrics", True, "role and state metrics computed", metrics.content_address),
        ("lineage", lineage.accepted, "source-to-result graph built", lineage.content_address),
        ("policy", policy.accepted, "research publication policy applied", policy.content_address),
        (
            "reconcile",
            reconciliation.accepted,
            "expected and observed states reconciled",
            reconciliation.content_address,
        ),
        ("quality", quality.accepted, "depth and boundary gate executed", quality.content_address),
        (
            "release-ready",
            quality.accepted and reconciliation.accepted,
            "release readiness determined",
            quality.content_address,
        ),
    )
    stages = tuple(
        SequenceGrammarRuntimeStage(
            index, stage_id, "accepted" if passed else "rejected", detail, receipt
        )
        for index, (stage_id, passed, detail, receipt) in enumerate(stage_values, start=1)
    )
    accepted = all(stage.status == "accepted" for stage in stages) and not (
        options.fail_on_review
        and evaluation.review_count + evaluation.invalid_count + evaluation.abstained_count > 0
    )
    return SequenceGrammarRuntimeReport(
        options.run_id,
        "ready" if accepted else "rejected",
        accepted,
        stages,
        evaluation,
        schema,
        metrics,
        lineage,
        policy,
        reconciliation,
        quality,
    )


__all__ = [
    "SequenceGrammarRuntimeOptions",
    "SequenceGrammarRuntimeReport",
    "SequenceGrammarRuntimeStage",
    "run_sequence_grammar_pipeline",
]
