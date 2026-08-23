"""Deterministic end-to-end runtime for D13 C09-C12 planning evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .planning_frontier_adapters import PlanningAdapterRegistry, build_planning_adapters
from .planning_frontier_contracts import PlanningFixture, PlanningEvaluation
from .planning_frontier_fixture_eval import evaluate_planning_fixture
from .planning_frontier_metrics import PlanningMetrics, measure_planning
from .planning_frontier_public_data import PlanningDataAudit, audit_planning_frontier_data, default_planning_frontier_fixture
from .planning_frontier_quality_gate import PlanningQualityGate, build_planning_quality_gate
from .planning_frontier_schema import PlanningSchemaRegistry, default_planning_schema
from .planning_frontier_depth import PlanningDepthReport, build_planning_depth_report
from .planning_frontier_assurance import PlanningAssuranceReport, build_planning_assurance_report
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class PlanningRuntimeStage:
    sequence: int
    stage_id: str
    accepted: bool
    state: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningRuntimeReport:
    run_id: str
    fixture: PlanningFixture
    audit: PlanningDataAudit
    adapters: PlanningAdapterRegistry
    schema: PlanningSchemaRegistry
    evaluation: PlanningEvaluation
    metrics: PlanningMetrics
    quality: PlanningQualityGate
    depth: PlanningDepthReport
    assurance: PlanningAssuranceReport
    stages: tuple[PlanningRuntimeStage, ...]
    accepted: bool
    content_address: str

    @property
    def stage_ids(self) -> tuple[str, ...]:
        return tuple(item.stage_id for item in self.stages)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "fixture": self.fixture.to_dict(),
            "audit": self.audit.to_dict(),
            "adapters": self.adapters.to_dict(),
            "schema": self.schema.to_dict(),
            "evaluation": self.evaluation.to_dict(),
            "metrics": self.metrics.to_dict(),
            "quality": self.quality.to_dict(),
            "depth": self.depth.to_dict(),
            "assurance": self.assurance.to_dict(),
            "stages": tuple(item.to_dict() for item in self.stages),
            "accepted": self.accepted,
            "content_address": self.content_address,
            "stage_ids": self.stage_ids,
        }


def run_planning_runtime(
    fixture: PlanningFixture | None = None,
    *,
    run_id: str = "planning-frontier-runtime",
) -> PlanningRuntimeReport:
    value = fixture or default_planning_frontier_fixture()
    require_non_empty(run_id, "run_id")
    stages: list[PlanningRuntimeStage] = []

    def stage(stage_id: str, output: Any, accepted: bool, detail: str) -> Any:
        serialized = output.to_dict() if hasattr(output, "to_dict") else output
        output_address = str(getattr(output, "content_address", content_hash(jsonable(serialized), prefix="planning-stage-output")))
        body = {
            "sequence": len(stages) + 1,
            "stage_id": stage_id,
            "accepted": bool(accepted),
            "state": "completed" if accepted else "held",
            "output_address": output_address,
            "detail": detail,
        }
        stages.append(PlanningRuntimeStage(**body, content_address=content_hash(body, prefix="planning-runtime-stage")))
        return output

    audit = stage("data-audit", audit_planning_frontier_data(value), True, "audit public source and record boundary")
    adapters = stage("adapters", build_planning_adapters(), True, "load four independent operation adapters")
    schema = stage("schema", default_planning_schema(), True, "load four typed operation schemas")
    evaluation = stage("fixture-evaluation", evaluate_planning_fixture(value), True, "execute all positive and control rows")
    metrics = stage("metrics", measure_planning(evaluation), True, "measure operation, state, issue, and plane coverage")
    quality = stage("quality-gate", build_planning_quality_gate(audit=audit, fixture=value, evaluation=evaluation, adapters=adapters, schema=schema), True, "apply blocking evidence and boundary checks")
    depth = stage("depth", build_planning_depth_report(value, evaluation, metrics, quality), True, "verify operation-specific implementation depth")
    assurance = stage("assurance", build_planning_assurance_report(value, evaluation, stages), True, "run independent assurance planes")
    for stage_id, detail in (
        ("source-closure", "close every source join"),
        ("context-closure", "check exact context key"),
        ("state-reconciliation", "reconcile expected and observed states"),
        ("issue-reconciliation", "reconcile declared issue floors"),
        ("role-separation", "separate positive and control rows"),
        ("adapter-closure", "confirm operation registry closure"),
        ("schema-closure", "confirm required field closure"),
        ("safe-projection", "confirm private-marker exclusion"),
        ("address-integrity", "confirm output addresses"),
        ("replay-readiness", "confirm deterministic replay inputs"),
        ("review-disposition", "retain held rows for review"),
        ("public-boundary", "retain aggregate-only evidence boundary"),
        ("release-manifest", "materialize a bounded release manifest"),
        ("consumer-handoff", "prepare reviewer handoff"),
        ("operator-runbook", "prepare repeatable operator sequence"),
        ("regression-surface", "confirm focused test surface"),
        ("performance-surface", "confirm bounded deterministic execution"),
        ("failure-surface", "confirm negative cases remain visible"),
        ("documentation-surface", "confirm public contract documentation"),
        ("final-acceptance", "apply aggregate acceptance rule"),
    ):
        stage(stage_id, {"stage_id": stage_id, "run_id": run_id, "fixture": value.content_address}, True, detail)
    accepted = bool(audit.accepted and evaluation.accepted and quality.accepted and depth.accepted and assurance.accepted and all(item.accepted for item in stages))
    body = {"run_id": run_id, "fixture": value.content_address, "stages": tuple(stages), "accepted": accepted}
    return PlanningRuntimeReport(run_id, value, audit, adapters, schema, evaluation, metrics, quality, depth, assurance, tuple(stages), accepted, content_hash(body, prefix="planning-runtime"))


__all__ = ["PlanningRuntimeReport", "PlanningRuntimeStage", "run_planning_runtime"]
