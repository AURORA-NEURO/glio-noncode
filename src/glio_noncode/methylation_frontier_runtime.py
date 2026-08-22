"""Ten-stage runtime for reproducible methylation tranche execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .methylation_frontier_adapters import (
    MethylationFrontierAdapterRegistry,
    build_methylation_frontier_adapters,
)
from .methylation_frontier_contracts import (
    MethylationFrontierContractReport,
    build_methylation_frontier_contracts,
)
from .methylation_frontier_fixture_eval import (
    MethylationFrontierEvaluation,
    evaluate_methylation_frontier_fixture,
)
from .methylation_frontier_lineage import (
    MethylationFrontierLineage,
    build_methylation_frontier_lineage,
)
from .methylation_frontier_metrics import (
    MethylationFrontierMetrics,
    build_methylation_frontier_metrics,
)
from .methylation_frontier_policy import (
    MethylationFrontierPolicyReport,
    evaluate_methylation_frontier_policy,
)
from .methylation_frontier_public_data import (
    MethylationFrontierDataAudit,
    MethylationFrontierFixture,
    audit_methylation_frontier_data,
)
from .methylation_frontier_quality_gate import (
    MethylationFrontierQualityReport,
    build_methylation_frontier_quality,
)
from .methylation_frontier_reconciliation import (
    MethylationFrontierReconciliation,
    reconcile_methylation_frontier,
)
from .methylation_frontier_schema import (
    MethylationFrontierSchemaReport,
    validate_methylation_frontier_schema,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class MethylationFrontierRuntimeOptions:
    run_id: str = "methylation-frontier"
    strict: bool = True
    include_controls: bool = True
    max_records: int = 64

    def __post_init__(self) -> None:
        if not self.run_id or self.max_records < 1:
            raise ValidationError("runtime options are invalid")


@dataclass(frozen=True, slots=True)
class MethylationFrontierStage:
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
class MethylationFrontierRuntimeReport:
    run_id: str
    options: MethylationFrontierRuntimeOptions
    data: MethylationFrontierDataAudit
    contracts: MethylationFrontierContractReport
    adapters: MethylationFrontierAdapterRegistry
    schema: MethylationFrontierSchemaReport
    evaluation: MethylationFrontierEvaluation
    metrics: MethylationFrontierMetrics
    lineage: MethylationFrontierLineage
    policy: MethylationFrontierPolicyReport
    reconciliation: MethylationFrontierReconciliation
    quality: MethylationFrontierQualityReport
    stages: tuple[MethylationFrontierStage, ...]
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
                        "evaluation": self.evaluation.content_address,
                        "quality": self.quality.content_address,
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


def run_methylation_frontier_runtime(
    options: MethylationFrontierRuntimeOptions | None = None,
    *,
    fixture: MethylationFrontierFixture,
) -> MethylationFrontierRuntimeReport:
    options = options or MethylationFrontierRuntimeOptions()
    data = audit_methylation_frontier_data(fixture)
    contracts = build_methylation_frontier_contracts()
    adapters = build_methylation_frontier_adapters()
    schema = validate_methylation_frontier_schema(fixture)
    evaluation = evaluate_methylation_frontier_fixture(fixture)
    metrics = build_methylation_frontier_metrics(evaluation)
    lineage = build_methylation_frontier_lineage(fixture, evaluation)
    policy = evaluate_methylation_frontier_policy(evaluation)
    reconciliation = reconcile_methylation_frontier(evaluation)
    quality = build_methylation_frontier_quality(
        fixture, data, schema, evaluation, metrics, reconciliation
    )
    stages = (
        MethylationFrontierStage(
            "load",
            "passed" if data.accepted else "failed",
            1,
            len(fixture.records),
            "public methylation fixture loaded",
        ),
        MethylationFrontierStage(
            "contracts",
            "passed" if contracts.accepted else "failed",
            4,
            contracts.unique_operations,
            "operation contracts checked",
        ),
        MethylationFrontierStage(
            "adapter_registry",
            "passed" if adapters.accepted else "failed",
            4,
            len(adapters.specs),
            "methylation primitives registered",
        ),
        MethylationFrontierStage(
            "schema",
            "passed" if schema.accepted else "failed",
            len(fixture.records),
            len(schema.checks),
            "schema and public boundary checks run",
        ),
        MethylationFrontierStage(
            "execute",
            "passed" if evaluation.accepted else "failed",
            len(fixture.records),
            len(evaluation.results),
            "positive and control records executed",
        ),
        MethylationFrontierStage(
            "metrics",
            "passed" if metrics.accepted else "failed",
            len(evaluation.records),
            len(metrics.metrics),
            "release metrics calculated",
        ),
        MethylationFrontierStage(
            "lineage",
            "passed" if lineage.accepted else "failed",
            len(evaluation.records),
            len(lineage.edges),
            "source lineage assembled",
        ),
        MethylationFrontierStage(
            "policy",
            "passed" if policy.accepted else "failed",
            len(evaluation.records),
            len(policy.decisions),
            "release and review policy evaluated",
        ),
        MethylationFrontierStage(
            "reconcile",
            "passed" if reconciliation.accepted else "failed",
            len(evaluation.records),
            len(reconciliation.items),
            "expected paths reconciled",
        ),
        MethylationFrontierStage(
            "quality_gate",
            "passed" if quality.accepted else "failed",
            len(quality.checks),
            quality.passed_count,
            "quality gate evaluated",
        ),
    )
    accepted = all(stage.status == "passed" for stage in stages) and quality.accepted
    return MethylationFrontierRuntimeReport(
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
    "MethylationFrontierRuntimeOptions",
    "MethylationFrontierRuntimeReport",
    "MethylationFrontierStage",
    "run_methylation_frontier_runtime",
]
