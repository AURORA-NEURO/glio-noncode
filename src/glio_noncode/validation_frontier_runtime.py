"""Ordered runtime rehearsal for Domain 13 planning."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .validation_frontier_bundle import (
    ValidationFrontierReleaseBundle,
    assemble_validation_frontier_bundle,
)
from .validation_frontier_contracts import default_validation_frontier_contracts
from .validation_frontier_fixture_eval import evaluate_validation_frontier_fixture
from .validation_frontier_lineage import build_validation_frontier_lineage
from .validation_frontier_metrics import measure_validation_frontier
from .validation_frontier_policy import default_validation_frontier_policy
from .validation_frontier_public_data import (
    ValidationFrontierFixture,
    audit_validation_frontier_data,
    default_validation_frontier_fixture,
)
from .validation_frontier_quality_gate import evaluate_validation_frontier_quality
from .validation_frontier_reconciliation import reconcile_validation_frontier
from .validation_frontier_schema import default_validation_frontier_schema


@dataclass(frozen=True, slots=True)
class ValidationFrontierRuntimeStage:
    stage_id: str
    sequence: int
    state: str
    duration_ms: float
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationFrontierRuntimeReport:
    run_id: str
    stages: tuple[ValidationFrontierRuntimeStage, ...]
    bundle: ValidationFrontierReleaseBundle
    accepted: bool
    content_address: str

    @property
    def stage_ids(self) -> tuple[str, ...]:
        return tuple(item.stage_id for item in self.stages)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"stage_ids": list(self.stage_ids)}


def run_validation_frontier_runtime(fixture: ValidationFrontierFixture | None = None, *, run_id: str = "validation-frontier-runtime") -> ValidationFrontierRuntimeReport:
    fixture = fixture or default_validation_frontier_fixture()
    require_non_empty(run_id, "run_id")
    stages: list[ValidationFrontierRuntimeStage] = []
    def stage(stage_id: str, sequence: int, fn: Callable[[], Any], detail: str) -> Any:
        start = perf_counter()
        result = fn()
        duration = round((perf_counter() - start) * 1000, 3)
        address = result.content_address if hasattr(result, "content_address") else content_hash(result)
        body = {"stage_id": stage_id, "sequence": sequence, "state": "completed", "duration_ms": duration, "output_address": address, "detail": detail}
        stages.append(ValidationFrontierRuntimeStage(**body, content_address=content_hash(body)))
        return result
    audit = stage("data-audit", 1, lambda: audit_validation_frontier_data(fixture), "audit public planning fixture")
    contracts = stage("contracts", 2, default_validation_frontier_contracts, "load operation contracts")
    schema = stage("schema", 3, default_validation_frontier_schema, "load operation schema")
    evaluation = stage("fixture-replay", 4, lambda: evaluate_validation_frontier_fixture(fixture), "execute positive and control records")
    metrics = stage("metrics", 5, lambda: measure_validation_frontier(evaluation), "measure planning state coverage")
    policy = stage("policy", 6, lambda: default_validation_frontier_policy(contracts), "apply research-use planning policy")
    lineage = stage("lineage", 7, lambda: build_validation_frontier_lineage(fixture, evaluation), "build source lineage")
    reconciliation = stage("reconciliation", 8, lambda: reconcile_validation_frontier(fixture, evaluation, policy), "reconcile expected states")
    gate = stage("quality-gate", 9, lambda: evaluate_validation_frontier_quality(fixture, evaluation, contracts, schema, lineage, reconciliation), "run blocking checks")
    bundle = stage("release-bundle", 10, lambda: assemble_validation_frontier_bundle(fixture, evaluation, metrics, lineage, reconciliation, policy, bundle_id=run_id), "assemble review bundle")
    accepted = bool(audit.accepted and gate.accepted and reconciliation.reconciled and bundle.publishable)
    body = {"run_id": run_id, "stages": tuple(stages), "bundle": bundle, "accepted": accepted}
    return ValidationFrontierRuntimeReport(**body, content_address=content_hash(body))


__all__ = ["ValidationFrontierRuntimeReport", "ValidationFrontierRuntimeStage", "run_validation_frontier_runtime"]
