"""Depth audit for Domain 13 validation-planning coverage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_frontier_contracts import default_validation_frontier_contracts
from .validation_frontier_fixture_eval import evaluate_validation_frontier_fixture
from .validation_frontier_lineage import build_validation_frontier_lineage
from .validation_frontier_metrics import measure_validation_frontier
from .validation_frontier_policy import default_validation_frontier_policy
from .validation_frontier_public_data import (
    audit_validation_frontier_data,
    default_validation_frontier_fixture,
)
from .validation_frontier_quality_gate import evaluate_validation_frontier_quality
from .validation_frontier_reconciliation import reconcile_validation_frontier
from .validation_frontier_replay import (
    replay_validation_frontier,
    validation_frontier_replay_is_deterministic,
)
from .validation_frontier_runtime import run_validation_frontier_runtime
from .validation_frontier_scenario_matrix import build_validation_frontier_scenario_matrix
from .validation_frontier_schema import default_validation_frontier_schema
from .validation_frontier_thresholds import build_validation_frontier_threshold_report


@dataclass(frozen=True, slots=True)
class ValidationFrontierDepthCheck:
    check_id: str
    passed: bool
    observed: int | float | bool
    required: int | float | bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationFrontierDepthAudit:
    checks: tuple[ValidationFrontierDepthCheck, ...]
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


def audit_validation_frontier_depth() -> ValidationFrontierDepthAudit:
    fixture = default_validation_frontier_fixture()
    audit = audit_validation_frontier_data(fixture)
    contracts = default_validation_frontier_contracts()
    schema = default_validation_frontier_schema()
    evaluation = evaluate_validation_frontier_fixture(fixture)
    metrics = measure_validation_frontier(evaluation)
    policy = default_validation_frontier_policy(contracts)
    lineage = build_validation_frontier_lineage(fixture, evaluation)
    reconciliation = reconcile_validation_frontier(fixture, evaluation, policy)
    quality = evaluate_validation_frontier_quality(fixture, evaluation, contracts, schema, lineage, reconciliation)
    runtime = run_validation_frontier_runtime(fixture, run_id="validation-depth")
    replay = replay_validation_frontier(fixture, replay_id="validation-depth-replay")
    matrix = build_validation_frontier_scenario_matrix()
    thresholds = build_validation_frontier_threshold_report()
    values = (("source-count", len(fixture.sources), 5, "public source receipts"), ("record-count", len(fixture.records), 16, "planning records"), ("positive-count", len(fixture.positive_records), 4, "one positive per operation"), ("control-count", len(fixture.control_records), 12, "three controls per operation"), ("operation-count", len(contracts.contracts), 4, "four operation contracts"), ("schema-count", len(schema.operations), 4, "four schemas"), ("evaluation-check-count", len(evaluation.checks), 120, "seven record and eight global checks"), ("lineage-edge-count", len(lineage.edges), 36, "source and fixture edges"), ("quality-check-count", len(quality.checks), 12, "quality checks"), ("runtime-stage-count", len(runtime.stages), 10, "runtime stages"), ("metric-count", len(metrics.metrics), 13, "coverage metrics"), ("scenario-count", len(matrix.scenarios), 31, "planning scenarios"), ("threshold-probe-count", len(thresholds.probes), 972, "threshold probes"), ("data-audit", audit.accepted, True, "data audit"), ("evaluation", evaluation.accepted, True, "evaluation"), ("reconciliation", reconciliation.reconciled, True, "reconciliation"), ("quality-gate", quality.accepted, True, "quality gate"), ("runtime", runtime.accepted, True, "runtime"), ("replay", replay.accepted, True, "replay"), ("determinism", validation_frontier_replay_is_deterministic(fixture), True, "replay determinism"))
    checks = tuple(ValidationFrontierDepthCheck(item[0], item[1] >= item[2] if isinstance(item[1], (int, float)) and isinstance(item[2], (int, float)) else item[1] == item[2], item[1], item[2], item[3], content_hash(item)) for item in values)
    body = {"checks": checks, "accepted": all(item.passed for item in checks)}
    return ValidationFrontierDepthAudit(**body, content_address=content_hash(body))


__all__ = ["ValidationFrontierDepthAudit", "ValidationFrontierDepthCheck", "audit_validation_frontier_depth"]
