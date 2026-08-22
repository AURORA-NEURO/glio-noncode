"""Depth audit for Domain 12 cohort convergence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_frontier_contracts import default_cohort_frontier_contracts
from .cohort_frontier_fixture_eval import evaluate_cohort_frontier_fixture
from .cohort_frontier_lineage import build_cohort_frontier_lineage
from .cohort_frontier_metrics import measure_cohort_frontier
from .cohort_frontier_policy import default_cohort_frontier_policy
from .cohort_frontier_public_data import audit_cohort_frontier_data, default_cohort_frontier_fixture
from .cohort_frontier_quality_gate import evaluate_cohort_frontier_quality
from .cohort_frontier_reconciliation import reconcile_cohort_frontier
from .cohort_frontier_replay import replay_cohort_frontier, replay_cohort_frontier_is_deterministic
from .cohort_frontier_runtime import run_cohort_frontier_runtime
from .cohort_frontier_scenario_matrix import build_cohort_frontier_scenario_matrix
from .cohort_frontier_schema import default_cohort_frontier_schema
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortFrontierDepthCheck:
    check_id: str
    passed: bool
    observed: int | float | bool
    required: int | float | bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFrontierDepthAudit:
    checks: tuple[CohortFrontierDepthCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed_count": self.passed_count, "failed_check_ids": list(self.failed_check_ids)}


def audit_cohort_frontier_depth() -> CohortFrontierDepthAudit:
    fixture = default_cohort_frontier_fixture()
    audit = audit_cohort_frontier_data(fixture)
    contracts = default_cohort_frontier_contracts()
    schema = default_cohort_frontier_schema()
    evaluation = evaluate_cohort_frontier_fixture(fixture)
    metrics = measure_cohort_frontier(evaluation)
    policy = default_cohort_frontier_policy(contracts)
    lineage = build_cohort_frontier_lineage(fixture, evaluation)
    reconciliation = reconcile_cohort_frontier(fixture, evaluation, policy)
    quality = evaluate_cohort_frontier_quality(fixture, evaluation, contracts, schema, lineage, reconciliation)
    runtime = run_cohort_frontier_runtime(fixture, run_id="cohort-depth")
    replay = replay_cohort_frontier(fixture, replay_id="cohort-depth-replay")
    matrix = build_cohort_frontier_scenario_matrix()
    values = (("source-count", len(fixture.sources), 5, "public source receipts"), ("record-count", len(fixture.records), 16, "positive and control records"), ("positive-count", len(fixture.positive_records), 4, "one positive per operation"), ("control-count", len(fixture.control_records), 12, "three controls per operation"), ("operation-count", len(contracts.contracts), 4, "four contracts"), ("schema-count", len(schema.operations), 4, "four schemas"), ("evaluation-check-count", len(evaluation.checks), 120, "seven record checks and eight global checks"), ("lineage-edge-count", len(lineage.edges), 36, "source and fixture edges"), ("quality-check-count", len(quality.checks), 12, "quality gate checks"), ("runtime-stage-count", len(runtime.stages), 10, "runtime stages"), ("metric-count", len(metrics.metrics), 11, "coverage and operation metrics"), ("scenario-count", len(matrix.scenarios), 33, "threshold and operation scenarios"), ("data-audit", audit.accepted, True, "data audit"), ("evaluation", evaluation.accepted, True, "fixture evaluation"), ("reconciliation", reconciliation.reconciled, True, "reconciliation"), ("quality-gate", quality.accepted, True, "quality gate"), ("runtime", runtime.accepted, True, "runtime"), ("replay", replay.accepted, True, "replay"), ("determinism", replay_cohort_frontier_is_deterministic(fixture), True, "replay determinism"))
    checks = tuple(CohortFrontierDepthCheck(item[0], item[1] >= item[2] if isinstance(item[1], (int, float)) and isinstance(item[2], (int, float)) else item[1] == item[2], item[1], item[2], item[3], content_hash(item)) for item in values)
    body = {"checks": checks, "accepted": all(item.passed for item in checks)}
    return CohortFrontierDepthAudit(**body, content_address=content_hash(body))


__all__ = ["CohortFrontierDepthAudit", "CohortFrontierDepthCheck", "audit_cohort_frontier_depth"]
