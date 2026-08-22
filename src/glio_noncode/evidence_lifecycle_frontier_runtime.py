"""Ordered runtime rehearsal for the Domain 14 lifecycle frontier."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from .evidence_lifecycle_frontier_bundle import (
    EvidenceLifecycleReleaseBundle,
    assemble_evidence_lifecycle_bundle,
)
from .evidence_lifecycle_frontier_contracts import default_evidence_lifecycle_contracts
from .evidence_lifecycle_frontier_fixture_eval import evaluate_evidence_lifecycle_fixture
from .evidence_lifecycle_frontier_lineage import build_evidence_lifecycle_lineage
from .evidence_lifecycle_frontier_metrics import measure_evidence_lifecycle
from .evidence_lifecycle_frontier_policy import default_evidence_lifecycle_policy
from .evidence_lifecycle_frontier_public_data import (
    EvidenceLifecycleFixture,
    audit_evidence_lifecycle_data,
    default_evidence_lifecycle_fixture,
)
from .evidence_lifecycle_frontier_quality_gate import evaluate_evidence_lifecycle_quality
from .evidence_lifecycle_frontier_reconciliation import reconcile_evidence_lifecycle
from .evidence_lifecycle_frontier_schema import default_evidence_lifecycle_schema
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleRuntimeStage:
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
class EvidenceLifecycleRuntimeReport:
    run_id: str
    stages: tuple[EvidenceLifecycleRuntimeStage, ...]
    bundle: EvidenceLifecycleReleaseBundle
    accepted: bool
    content_address: str

    @property
    def stage_ids(self) -> tuple[str, ...]:
        return tuple(item.stage_id for item in self.stages)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"stage_ids": list(self.stage_ids)}


def run_evidence_lifecycle_runtime(fixture: EvidenceLifecycleFixture | None = None, *, run_id: str = "evidence-lifecycle-runtime") -> EvidenceLifecycleRuntimeReport:
    fixture = fixture or default_evidence_lifecycle_fixture()
    require_non_empty(run_id, "run_id")
    stages: list[EvidenceLifecycleRuntimeStage] = []

    def stage(stage_id: str, sequence: int, fn: Callable[[], Any], detail: str) -> Any:
        started = perf_counter()
        result = fn()
        duration = round((perf_counter() - started) * 1000, 3)
        address = result.content_address if hasattr(result, "content_address") else content_hash(result)
        body = {"stage_id": stage_id, "sequence": sequence, "state": "completed", "duration_ms": duration, "output_address": address, "detail": detail}
        stages.append(EvidenceLifecycleRuntimeStage(**body, content_address=content_hash(body)))
        return result

    audit = stage("data-audit", 1, lambda: audit_evidence_lifecycle_data(fixture), "audit public lifecycle fixture")
    contracts = stage("contracts", 2, default_evidence_lifecycle_contracts, "load lifecycle contracts")
    schema = stage("schema", 3, default_evidence_lifecycle_schema, "load lifecycle schema")
    evaluation = stage("fixture-evaluation", 4, lambda: evaluate_evidence_lifecycle_fixture(fixture), "execute four lifecycle operations")
    metrics = stage("metrics", 5, lambda: measure_evidence_lifecycle(evaluation), "measure state and control coverage")
    policy = stage("policy", 6, default_evidence_lifecycle_policy, "apply research-use lifecycle policy")
    lineage = stage("lineage", 7, lambda: build_evidence_lifecycle_lineage(fixture, evaluation), "build source and execution lineage")
    reconciliation = stage("reconciliation", 8, lambda: reconcile_evidence_lifecycle(fixture, evaluation, policy), "reconcile expected lifecycle states")
    gate = stage("quality-gate", 9, lambda: evaluate_evidence_lifecycle_quality(fixture, evaluation, contracts, schema, lineage, reconciliation), "run blocking lifecycle checks")
    bundle = stage("release-bundle", 10, lambda: assemble_evidence_lifecycle_bundle(fixture, evaluation, metrics, lineage, reconciliation, policy, bundle_id=run_id), "assemble lifecycle review bundle")
    accepted = bool(audit.accepted and gate.accepted and reconciliation.reconciled and bundle.publishable)
    body = {"run_id": run_id, "stages": tuple(stages), "bundle": bundle, "accepted": accepted}
    return EvidenceLifecycleRuntimeReport(**body, content_address=content_hash(body))


__all__ = ["EvidenceLifecycleRuntimeReport", "EvidenceLifecycleRuntimeStage", "run_evidence_lifecycle_runtime"]
