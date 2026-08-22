"""Depth audit proving the causal frontier has operational surface area."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_frontier_contracts import default_causal_frontier_contracts
from .causal_frontier_fixture_eval import evaluate_causal_frontier_fixture
from .causal_frontier_lineage import build_causal_frontier_lineage
from .causal_frontier_metrics import measure_causal_frontier
from .causal_frontier_policy import default_causal_frontier_policy
from .causal_frontier_public_data import audit_causal_frontier_data, default_causal_frontier_fixture
from .causal_frontier_quality_gate import evaluate_causal_frontier_quality
from .causal_frontier_reconciliation import reconcile_causal_frontier
from .causal_frontier_replay import replay_causal_frontier, replay_is_deterministic
from .causal_frontier_runtime import run_causal_frontier_runtime
from .causal_frontier_schema import default_causal_frontier_schema
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalFrontierDepthCheck:
    check_id: str
    passed: bool
    observed: int | float | bool
    required: int | float | bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalFrontierDepthAudit:
    checks: tuple[CausalFrontierDepthCheck, ...]
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


def audit_causal_frontier_depth() -> CausalFrontierDepthAudit:
    fixture = default_causal_frontier_fixture()
    audit = audit_causal_frontier_data(fixture)
    contracts = default_causal_frontier_contracts()
    schema = default_causal_frontier_schema()
    evaluation = evaluate_causal_frontier_fixture(fixture)
    metrics = measure_causal_frontier(evaluation)
    policy = default_causal_frontier_policy(contracts)
    lineage = build_causal_frontier_lineage(fixture, evaluation)
    reconciliation = reconcile_causal_frontier(fixture, evaluation, policy)
    gate = evaluate_causal_frontier_quality(fixture, evaluation, contracts, schema, lineage, reconciliation)
    runtime = run_causal_frontier_runtime(fixture, run_id="depth-audit")
    replay = replay_causal_frontier(fixture, replay_id="depth-replay")
    values = (
        ("source-count", len(fixture.sources), 5, "public source receipts are present"),
        ("record-count", len(fixture.records), 16, "positive and control records are present"),
        ("positive-count", len(fixture.positive_records), 4, "each operation has a positive record"),
        ("control-count", len(fixture.control_records), 12, "each operation has three controls"),
        ("operation-count", len(contracts.contracts), 4, "each operation has a contract"),
        ("schema-count", len(schema.operations), 4, "each operation has a schema"),
        ("evaluation-check-count", len(evaluation.checks), 120, "each record has seven checks plus eight globals"),
        ("lineage-edge-count", len(lineage.edges), 36, "source and fixture edges connect each execution"),
        ("quality-check-count", len(gate.checks), 12, "release gate has layered checks"),
        ("runtime-stage-count", len(runtime.stages), 10, "runtime has ordered stages"),
        ("metric-count", len(metrics.metrics), 13, "coverage and operation metrics are emitted"),
        ("data-audit", audit.accepted, True, "data audit is accepted"),
        ("evaluation", evaluation.accepted, True, "fixture replay is accepted"),
        ("reconciliation", reconciliation.reconciled, True, "expected states reconcile"),
        ("quality-gate", gate.accepted, True, "quality gate is accepted"),
        ("runtime", runtime.accepted, True, "runtime release rehearsal is accepted"),
        ("replay", replay.accepted, True, "replay is accepted"),
        ("determinism", replay_is_deterministic(fixture), True, "two replays produce identical receipts"),
    )
    checks = tuple(
        CausalFrontierDepthCheck(
            check_id=item[0],
            passed=item[1] >= item[2] if isinstance(item[1], (int, float)) and isinstance(item[2], (int, float)) else item[1] == item[2],
            observed=item[1],
            required=item[2],
            detail=item[3],
            content_address=content_hash(item),
        )
        for item in values
    )
    body = {"checks": checks, "accepted": all(item.passed for item in checks)}
    return CausalFrontierDepthAudit(**body, content_address=content_hash(body))


__all__ = ["CausalFrontierDepthAudit", "CausalFrontierDepthCheck", "audit_causal_frontier_depth"]
