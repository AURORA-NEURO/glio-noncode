"""Ten-stage runtime rehearsal for the C09-C12 release plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_alpha_frontier_adapters import (
    ChromatinAlphaFrontierAdapterRegistry,
    build_chromatin_alpha_frontier_adapters,
)
from .chromatin_alpha_frontier_contracts import (
    ChromatinAlphaFrontierContractReport,
    build_chromatin_alpha_frontier_contracts,
)
from .chromatin_alpha_frontier_fixture_eval import (
    ChromatinAlphaFrontierEvaluation,
    evaluate_chromatin_alpha_frontier_fixture,
)
from .chromatin_alpha_frontier_lineage import (
    ChromatinAlphaFrontierLineage,
    build_chromatin_alpha_frontier_lineage,
)
from .chromatin_alpha_frontier_metrics import (
    ChromatinAlphaFrontierMetrics,
    build_chromatin_alpha_frontier_metrics,
)
from .chromatin_alpha_frontier_policy import (
    ChromatinAlphaFrontierPolicyReport,
    evaluate_chromatin_alpha_frontier_policy,
)
from .chromatin_alpha_frontier_public_data import (
    ChromatinAlphaFrontierDataAudit,
    ChromatinAlphaFrontierFixture,
    audit_chromatin_alpha_frontier_data,
)
from .chromatin_alpha_frontier_quality_gate import (
    ChromatinAlphaFrontierQualityReport,
    build_chromatin_alpha_frontier_quality,
)
from .chromatin_alpha_frontier_reconciliation import (
    ChromatinAlphaFrontierReconciliation,
    reconcile_chromatin_alpha_frontier,
)
from .chromatin_alpha_frontier_schema import (
    ChromatinAlphaFrontierSchemaReport,
    validate_chromatin_alpha_frontier_schema,
)
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierRuntimeOptions:
    run_id: str = "chromatin-alpha-frontier"
    strict: bool = True
    include_controls: bool = True
    max_records: int = 64

    def __post_init__(self) -> None:
        if not self.run_id or self.max_records < 1:
            raise ValidationError("runtime options are invalid")


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierStage:
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
class ChromatinAlphaFrontierRuntimeReport:
    run_id: str
    options: ChromatinAlphaFrontierRuntimeOptions
    data: ChromatinAlphaFrontierDataAudit
    contracts: ChromatinAlphaFrontierContractReport
    adapters: ChromatinAlphaFrontierAdapterRegistry
    schema: ChromatinAlphaFrontierSchemaReport
    evaluation: ChromatinAlphaFrontierEvaluation
    metrics: ChromatinAlphaFrontierMetrics
    lineage: ChromatinAlphaFrontierLineage
    policy: ChromatinAlphaFrontierPolicyReport
    reconciliation: ChromatinAlphaFrontierReconciliation
    quality: ChromatinAlphaFrontierQualityReport
    stages: tuple[ChromatinAlphaFrontierStage, ...]
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


def run_chromatin_alpha_frontier_runtime(
    options: ChromatinAlphaFrontierRuntimeOptions | None = None,
    *,
    fixture: ChromatinAlphaFrontierFixture,
) -> ChromatinAlphaFrontierRuntimeReport:
    options = options or ChromatinAlphaFrontierRuntimeOptions()
    data = audit_chromatin_alpha_frontier_data(fixture)
    contracts = build_chromatin_alpha_frontier_contracts(fixture.evidence_boundary)
    adapters = build_chromatin_alpha_frontier_adapters()
    evaluation = evaluate_chromatin_alpha_frontier_fixture(fixture)
    schema = validate_chromatin_alpha_frontier_schema(fixture, evaluation)
    metrics = build_chromatin_alpha_frontier_metrics(evaluation)
    lineage = build_chromatin_alpha_frontier_lineage(fixture, evaluation)
    policy = evaluate_chromatin_alpha_frontier_policy(evaluation)
    reconciliation = reconcile_chromatin_alpha_frontier(evaluation)
    quality = build_chromatin_alpha_frontier_quality(
        fixture, data, schema, evaluation, metrics, reconciliation
    )
    stages = (
        ChromatinAlphaFrontierStage(
            "load",
            "passed" if data.accepted else "failed",
            1,
            len(fixture.records),
            "public chromatin-alpha fixture loaded",
        ),
        ChromatinAlphaFrontierStage(
            "contracts",
            "passed" if contracts.accepted else "failed",
            4,
            contracts.unique_operations,
            "operation contracts checked",
        ),
        ChromatinAlphaFrontierStage(
            "adapter_registry",
            "passed" if adapters.accepted else "failed",
            4,
            len(adapters.specs),
            "primitive adapters registered",
        ),
        ChromatinAlphaFrontierStage(
            "execute",
            "passed" if evaluation.accepted else "failed",
            len(fixture.records),
            len(evaluation.results),
            "positive and control rows executed",
        ),
        ChromatinAlphaFrontierStage(
            "schema",
            "passed" if schema.accepted else "failed",
            len(fixture.records),
            len(schema.checks),
            "schema and boundary checks run",
        ),
        ChromatinAlphaFrontierStage(
            "metrics",
            "passed" if metrics.accepted else "failed",
            len(evaluation.records),
            len(metrics.metrics),
            "quality metrics calculated",
        ),
        ChromatinAlphaFrontierStage(
            "lineage",
            "passed" if lineage.accepted else "failed",
            len(evaluation.records),
            len(lineage.edges),
            "source lineage assembled",
        ),
        ChromatinAlphaFrontierStage(
            "policy",
            "passed" if policy.accepted else "failed",
            len(evaluation.records),
            len(policy.decisions),
            "release and review policy evaluated",
        ),
        ChromatinAlphaFrontierStage(
            "reconcile",
            "passed" if reconciliation.accepted else "failed",
            len(evaluation.records),
            len(reconciliation.items),
            "expected paths reconciled",
        ),
        ChromatinAlphaFrontierStage(
            "quality_gate",
            "passed" if quality.accepted else "failed",
            len(quality.checks),
            quality.passed_count,
            "quality gate evaluated",
        ),
    )
    accepted = all(stage.status == "passed" for stage in stages) and quality.accepted
    return ChromatinAlphaFrontierRuntimeReport(
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
    "ChromatinAlphaFrontierRuntimeOptions",
    "ChromatinAlphaFrontierRuntimeReport",
    "ChromatinAlphaFrontierStage",
    "run_chromatin_alpha_frontier_runtime",
]
