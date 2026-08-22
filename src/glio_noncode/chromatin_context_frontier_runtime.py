"""Ten-stage runtime rehearsal for the C01-C04 context track release."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_context_frontier_adapters import (
    ChromatinContextFrontierAdapterRegistry,
    build_chromatin_context_frontier_adapters,
)
from .chromatin_context_frontier_contracts import (
    ChromatinContextFrontierContractReport,
    build_chromatin_context_frontier_contracts,
)
from .chromatin_context_frontier_fixture_eval import (
    ChromatinContextFrontierEvaluation,
    evaluate_chromatin_context_frontier_fixture,
)
from .chromatin_context_frontier_lineage import (
    ChromatinContextFrontierLineage,
    build_chromatin_context_frontier_lineage,
)
from .chromatin_context_frontier_metrics import (
    ChromatinContextFrontierMetrics,
    build_chromatin_context_frontier_metrics,
)
from .chromatin_context_frontier_policy import (
    ChromatinContextFrontierPolicyReport,
    evaluate_chromatin_context_frontier_policy,
)
from .chromatin_context_frontier_public_data import (
    ChromatinContextFrontierDataAudit,
    ChromatinContextFrontierFixture,
    audit_chromatin_context_frontier_data,
)
from .chromatin_context_frontier_quality_gate import (
    ChromatinContextFrontierQualityReport,
    build_chromatin_context_frontier_quality,
)
from .chromatin_context_frontier_reconciliation import (
    ChromatinContextFrontierReconciliation,
    reconcile_chromatin_context_frontier,
)
from .chromatin_context_frontier_schema import (
    ChromatinContextFrontierSchemaReport,
    validate_chromatin_context_frontier_schema,
)
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierRuntimeOptions:
    run_id: str = "chromatin-context-frontier"
    strict: bool = True
    include_controls: bool = True
    max_records: int = 64
    require_receipts: bool = True
    context_key: str = "GRCh38|glioma|adult|stem_like|tumor|unknown"

    def __post_init__(self) -> None:
        if not self.run_id or self.max_records < 1 or not self.context_key:
            raise ValidationError("runtime options are invalid")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierStage:
    stage_id: str
    status: str
    input_count: int
    output_count: int
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.stage_id or self.status not in {"passed", "failed", "skipped"}:
            raise ValidationError("runtime stage is invalid")
        if self.input_count < 0 or self.output_count < 0:
            raise ValidationError("runtime stage counts cannot be negative")
        if not self.detail:
            raise ValidationError("runtime stage detail is required")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierRuntimeReport:
    run_id: str
    options: ChromatinContextFrontierRuntimeOptions
    data: ChromatinContextFrontierDataAudit
    contracts: ChromatinContextFrontierContractReport
    adapters: ChromatinContextFrontierAdapterRegistry
    schema: ChromatinContextFrontierSchemaReport
    evaluation: ChromatinContextFrontierEvaluation
    metrics: ChromatinContextFrontierMetrics
    lineage: ChromatinContextFrontierLineage
    policy: ChromatinContextFrontierPolicyReport
    reconciliation: ChromatinContextFrontierReconciliation
    quality: ChromatinContextFrontierQualityReport
    stages: tuple[ChromatinContextFrontierStage, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.run_id or len(self.stages) != 10:
            raise ValidationError("context runtime requires ten stages")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "run_id": self.run_id,
                        "stages": self.stages,
                        "evaluation": self.evaluation.content_address,
                        "metrics": self.metrics.content_address,
                        "lineage": self.lineage.content_address,
                        "policy": self.policy.content_address,
                        "quality": self.quality.content_address,
                    }
                ),
            )

    @property
    def failed_stages(self) -> tuple[str, ...]:
        return tuple(item.stage_id for item in self.stages if item.status != "passed")

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "options": self.options.to_dict(),
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
            "stages": [item.to_dict() for item in self.stages],
            "failed_stages": list(self.failed_stages),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _stage(
    stage_id: str, passed: bool, inputs: int, outputs: int, detail: str
) -> ChromatinContextFrontierStage:
    return ChromatinContextFrontierStage(
        stage_id, "passed" if passed else "failed", inputs, outputs, detail
    )


def run_chromatin_context_frontier_runtime(
    options: ChromatinContextFrontierRuntimeOptions | None = None,
    *,
    fixture: ChromatinContextFrontierFixture,
) -> ChromatinContextFrontierRuntimeReport:
    options = options or ChromatinContextFrontierRuntimeOptions()
    if fixture.context_key != options.context_key:
        raise ValidationError("fixture context does not match runtime context")
    if len(fixture.records) > options.max_records:
        raise ValidationError("fixture exceeds runtime record limit")
    data = audit_chromatin_context_frontier_data(fixture)
    contracts = build_chromatin_context_frontier_contracts(fixture.evidence_boundary)
    adapters = build_chromatin_context_frontier_adapters()
    evaluation = evaluate_chromatin_context_frontier_fixture(fixture)
    schema = validate_chromatin_context_frontier_schema(fixture, evaluation)
    metrics = build_chromatin_context_frontier_metrics(evaluation)
    lineage = build_chromatin_context_frontier_lineage(fixture, evaluation)
    policy = evaluate_chromatin_context_frontier_policy(evaluation)
    reconciliation = reconcile_chromatin_context_frontier(evaluation)
    quality = build_chromatin_context_frontier_quality(
        fixture, data, schema, evaluation, metrics, reconciliation
    )
    stages = (
        _stage("load", data.accepted, 1, len(fixture.records), "aggregate context fixture loaded"),
        _stage(
            "contracts",
            contracts.accepted,
            4,
            contracts.unique_operations,
            "four operation contracts checked",
        ),
        _stage(
            "adapter_registry",
            adapters.accepted,
            4,
            len(adapters.specs),
            "typed primitive adapters registered",
        ),
        _stage(
            "execute",
            evaluation.accepted,
            len(fixture.records),
            len(evaluation.records),
            "positive and control rows executed",
        ),
        _stage(
            "schema",
            schema.accepted,
            len(fixture.records),
            len(schema.checks),
            "schema and boundary checks run",
        ),
        _stage(
            "metrics",
            metrics.accepted,
            len(evaluation.records),
            len(metrics.metrics),
            "release metrics calculated",
        ),
        _stage(
            "lineage",
            lineage.accepted,
            len(evaluation.records),
            len(lineage.edges),
            "source lineage assembled",
        ),
        _stage(
            "policy",
            policy.accepted,
            len(evaluation.records),
            len(policy.decisions),
            "release and review policy evaluated",
        ),
        _stage(
            "reconcile",
            reconciliation.accepted,
            len(evaluation.records),
            len(reconciliation.items),
            "expected paths reconciled",
        ),
        _stage(
            "quality_gate",
            quality.accepted,
            len(quality.checks),
            quality.passed_count,
            "quality gate evaluated",
        ),
    )
    accepted = all(item.status == "passed" for item in stages) and quality.accepted
    return ChromatinContextFrontierRuntimeReport(
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
    "ChromatinContextFrontierRuntimeOptions",
    "ChromatinContextFrontierRuntimeReport",
    "ChromatinContextFrontierStage",
    "run_chromatin_context_frontier_runtime",
]
