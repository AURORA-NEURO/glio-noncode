"""Ordered runtime stages for a causal frontier release rehearsal."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from .causal_frontier_bundle import CausalFrontierReleaseBundle, assemble_causal_frontier_bundle
from .causal_frontier_contracts import default_causal_frontier_contracts
from .causal_frontier_fixture_eval import evaluate_causal_frontier_fixture
from .causal_frontier_lineage import build_causal_frontier_lineage
from .causal_frontier_metrics import measure_causal_frontier
from .causal_frontier_policy import default_causal_frontier_policy
from .causal_frontier_public_data import (
    CausalFrontierFixture,
    audit_causal_frontier_data,
    default_causal_frontier_fixture,
)
from .causal_frontier_quality_gate import evaluate_causal_frontier_quality
from .causal_frontier_reconciliation import reconcile_causal_frontier
from .causal_frontier_schema import default_causal_frontier_schema
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class CausalFrontierRuntimeStage:
    stage_id: str
    sequence: int
    state: str
    duration_ms: float
    output_address: str
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.stage_id, "stage_id")
        if self.sequence < 1 or self.duration_ms < 0:
            raise ValueError("runtime stage sequence and duration must be nonnegative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalFrontierRuntimeReport:
    run_id: str
    stages: tuple[CausalFrontierRuntimeStage, ...]
    bundle: CausalFrontierReleaseBundle
    accepted: bool
    content_address: str

    @property
    def stage_ids(self) -> tuple[str, ...]:
        return tuple(item.stage_id for item in self.stages)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"stage_ids": list(self.stage_ids)}


def run_causal_frontier_runtime(
    fixture: CausalFrontierFixture | None = None,
    *,
    run_id: str = "causal-frontier-runtime",
) -> CausalFrontierRuntimeReport:
    fixture = fixture or default_causal_frontier_fixture()
    require_non_empty(run_id, "run_id")
    stages: list[CausalFrontierRuntimeStage] = []

    def stage(stage_id: str, sequence: int, fn: Callable[[], Any], detail: str) -> Any:
        started = perf_counter()
        result = fn()
        duration = round((perf_counter() - started) * 1000, 3)
        address = result.content_address if hasattr(result, "content_address") else content_hash(result)
        body = {"stage_id": stage_id, "sequence": sequence, "state": "completed", "duration_ms": duration, "output_address": address, "detail": detail}
        stages.append(CausalFrontierRuntimeStage(**body, content_address=content_hash(body)))
        return result

    audit = stage("data-audit", 1, lambda: audit_causal_frontier_data(fixture), "validate public fixture and source receipts")
    contracts = stage("contracts", 2, default_causal_frontier_contracts, "load operation contracts")
    schema = stage("schema", 3, default_causal_frontier_schema, "load field and invariant schema")
    evaluation = stage("fixture-replay", 4, lambda: evaluate_causal_frontier_fixture(fixture), "execute positive and control records")
    metrics = stage("metrics", 5, lambda: measure_causal_frontier(evaluation), "calculate bounded coverage metrics")
    policy = stage("policy", 6, lambda: default_causal_frontier_policy(contracts), "apply release boundary decisions")
    lineage = stage("lineage", 7, lambda: build_causal_frontier_lineage(fixture, evaluation), "build source-to-output lineage")
    reconciliation = stage("reconciliation", 8, lambda: reconcile_causal_frontier(fixture, evaluation, policy), "reconcile expectations and observed receipts")
    gate = stage("quality-gate", 9, lambda: evaluate_causal_frontier_quality(fixture, evaluation, contracts, schema, lineage, reconciliation), "run release checks")
    bundle = stage("release-bundle", 10, lambda: assemble_causal_frontier_bundle(fixture, evaluation, metrics, lineage, reconciliation, policy, bundle_id=run_id), "assemble content-addressed release bundle")
    accepted = bool(audit.accepted and gate.accepted and reconciliation.reconciled and bundle.publishable)
    body = {"run_id": run_id, "stages": tuple(stages), "bundle": bundle, "accepted": accepted}
    return CausalFrontierRuntimeReport(**body, content_address=content_hash(body))


__all__ = ["CausalFrontierRuntimeReport", "CausalFrontierRuntimeStage", "run_causal_frontier_runtime"]
