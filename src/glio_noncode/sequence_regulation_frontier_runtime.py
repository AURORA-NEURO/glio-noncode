"""Staged runtime for reproducible C09-C12 evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_regulation_frontier_adapters import (
    SequenceRegulationAdapterRegistry,
    build_sequence_regulation_adapters,
)
from .sequence_regulation_frontier_contracts import (
    SequenceRegulationContractReport,
    build_sequence_regulation_contracts,
)
from .sequence_regulation_frontier_fixture_eval import (
    SequenceRegulationEvaluation,
    evaluate_sequence_regulation_fixture,
)
from .sequence_regulation_frontier_lineage import (
    SequenceRegulationLineage,
    build_sequence_regulation_lineage,
)
from .sequence_regulation_frontier_metrics import (
    SequenceRegulationMetrics,
    build_sequence_regulation_metrics,
)
from .sequence_regulation_frontier_policy import (
    SequenceRegulationPolicyReport,
    evaluate_sequence_regulation_policy,
)
from .sequence_regulation_frontier_public_data import (
    SequenceRegulationDataAudit,
    SequenceRegulationFixture,
    audit_sequence_regulation_data,
)
from .sequence_regulation_frontier_quality_gate import (
    SequenceRegulationQualityReport,
    build_sequence_regulation_quality,
)
from .sequence_regulation_frontier_reconciliation import (
    SequenceRegulationReconciliation,
    reconcile_sequence_regulation,
)
from .sequence_regulation_frontier_schema import (
    SequenceRegulationSchemaReport,
    validate_sequence_regulation_schema,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceRegulationRuntimeOptions:
    run_id: str = "sequence-regulation-frontier"
    strict: bool = True
    include_controls: bool = True
    max_records: int = 64

    def __post_init__(self) -> None:
        if not self.run_id or self.max_records < 1:
            raise ValidationError("runtime options are invalid")


@dataclass(frozen=True, slots=True)
class SequenceRegulationStage:
    stage_id: str
    status: str
    input_count: int
    output_count: int
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.stage_id or self.status not in {"passed", "failed", "skipped"}:
            raise ValidationError("runtime stage is invalid")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceRegulationRuntimeReport:
    run_id: str
    options: SequenceRegulationRuntimeOptions
    data: SequenceRegulationDataAudit
    contracts: SequenceRegulationContractReport
    adapters: SequenceRegulationAdapterRegistry
    schema: SequenceRegulationSchemaReport
    evaluation: SequenceRegulationEvaluation
    metrics: SequenceRegulationMetrics
    lineage: SequenceRegulationLineage
    policy: SequenceRegulationPolicyReport
    reconciliation: SequenceRegulationReconciliation
    quality: SequenceRegulationQualityReport
    stages: tuple[SequenceRegulationStage, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.run_id or len(self.stages) != 10:
            raise ValidationError("runtime requires ten stages")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "run_id": self.run_id,
                        "stages": self.stages,
                        "quality": self.quality.content_address,
                        "evaluation": self.evaluation.content_address,
                        "lineage": self.lineage.content_address,
                        "policy": self.policy.content_address,
                        "reconciliation": self.reconciliation.content_address,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "options": jsonable(self.options),
            "data": self.data.to_dict(),
            "contracts": self.contracts.to_dict(),
            "adapters": self.adapters.to_dict(),
            "schema": self.schema.to_dict(),
            "evaluation": self.evaluation.to_dict(),
            "metrics": self.metrics.to_dict(),
            "lineage": self.lineage.to_dict(),
            "policy": self.policy.to_dict(),
            "reconciliation": self.reconciliation.to_dict(),
            "quality": self.quality.to_dict(),
            "stages": [stage.to_dict() for stage in self.stages],
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def run_sequence_regulation_runtime(
    options: SequenceRegulationRuntimeOptions | None = None,
    *,
    fixture: SequenceRegulationFixture,
) -> SequenceRegulationRuntimeReport:
    options = options or SequenceRegulationRuntimeOptions()
    bounded = fixture if len(fixture.records) <= options.max_records else None
    data = audit_sequence_regulation_data(fixture)
    contracts = build_sequence_regulation_contracts()
    adapters = build_sequence_regulation_adapters()
    schema = (
        validate_sequence_regulation_schema(fixture)
        if bounded
        else validate_sequence_regulation_schema(fixture)
    )
    evaluation = evaluate_sequence_regulation_fixture(fixture)
    metrics = build_sequence_regulation_metrics(evaluation)
    lineage = build_sequence_regulation_lineage(fixture, evaluation)
    policy = evaluate_sequence_regulation_policy(evaluation)
    reconciliation = reconcile_sequence_regulation(evaluation)
    quality = build_sequence_regulation_quality(
        fixture, data, schema, evaluation, metrics, reconciliation
    )
    stages = (
        SequenceRegulationStage(
            "load",
            "passed" if data.accepted else "failed",
            1,
            len(fixture.records),
            "public fixture loaded",
        ),
        SequenceRegulationStage(
            "contracts",
            "passed" if contracts.accepted else "failed",
            4,
            contracts.unique_operations,
            "operation contracts checked",
        ),
        SequenceRegulationStage(
            "adapter_registry",
            "passed" if adapters.accepted else "failed",
            4,
            len(adapters.specs),
            "primitive adapters registered",
        ),
        SequenceRegulationStage(
            "schema",
            "passed" if schema.accepted else "failed",
            len(fixture.records),
            len(schema.checks),
            "schema and boundary checks run",
        ),
        SequenceRegulationStage(
            "execute",
            "passed" if evaluation.accepted else "failed",
            len(fixture.records),
            len(evaluation.results),
            "records executed with controls",
        ),
        SequenceRegulationStage(
            "metrics",
            "passed" if metrics.accepted else "failed",
            len(evaluation.records),
            len(metrics.metrics),
            "release metrics calculated",
        ),
        SequenceRegulationStage(
            "lineage",
            "passed" if lineage.accepted else "failed",
            len(fixture.records),
            len(lineage.edges),
            "source lineage assembled",
        ),
        SequenceRegulationStage(
            "policy",
            "passed" if policy.accepted else "failed",
            len(evaluation.records),
            len(policy.decisions),
            "boundary policy evaluated",
        ),
        SequenceRegulationStage(
            "reconcile",
            "passed" if reconciliation.accepted else "failed",
            len(evaluation.records),
            len(reconciliation.items),
            "expected paths reconciled",
        ),
        SequenceRegulationStage(
            "quality_gate",
            "passed" if quality.accepted else "failed",
            len(quality.checks),
            quality.passed_count,
            "quality gate evaluated",
        ),
    )
    accepted = all(stage.status == "passed" for stage in stages) and quality.accepted
    return SequenceRegulationRuntimeReport(
        options.run_id,
        options,
        data,
        contracts,
        adapters,
        schema,
        evaluation,
        metrics,
        lineage,
        policy,
        reconciliation,
        quality,
        stages,
        accepted,
    )


__all__ = [
    "SequenceRegulationRuntimeOptions",
    "SequenceRegulationRuntimeReport",
    "SequenceRegulationStage",
    "run_sequence_regulation_runtime",
]
