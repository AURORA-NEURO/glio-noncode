"""Twelve-check release gate for Domain 09 topology evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_frontier_bundle import TopologyFrontierEvidenceBundle, build_topology_frontier_bundle
from .topology_frontier_fixture_eval import evaluate_topology_frontier_fixture
from .topology_frontier_lineage import (
    build_topology_frontier_lineage,
    verify_topology_frontier_lineage,
)
from .topology_frontier_metrics import compute_topology_frontier_metrics
from .topology_frontier_policy import evaluate_topology_frontier_policy
from .topology_frontier_public_data import (
    TopologyFrontierFixture,
    TopologyFrontierOperation,
    audit_topology_frontier_data,
    default_topology_frontier_fixture,
)
from .topology_frontier_reconciliation import reconcile_topology_frontier
from .topology_frontier_replay import replay_topology_frontier_evaluation
from .topology_frontier_scenario_matrix import evaluate_topology_frontier_scenarios
from .topology_frontier_schema import validate_topology_frontier_schema


@dataclass(frozen=True, slots=True)
class TopologyFrontierQualityCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyFrontierQualityReport:
    fixture_id: str
    bundle: TopologyFrontierEvidenceBundle
    checks: tuple[TopologyFrontierQualityCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.checks) and all(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted, "failed_check_ids": list(self.failed_check_ids)}


def run_topology_frontier_quality_gate(
    fixture: TopologyFrontierFixture | None = None,
) -> TopologyFrontierQualityReport:
    selected = fixture or default_topology_frontier_fixture()
    data_audit = audit_topology_frontier_data(selected)
    evaluation = evaluate_topology_frontier_fixture(selected)
    replay = replay_topology_frontier_evaluation(evaluation, fixture=selected)
    scenarios = evaluate_topology_frontier_scenarios(evaluation, fixture=selected)
    policy = evaluate_topology_frontier_policy(selected, evaluation)
    schemas = validate_topology_frontier_schema(evaluation)
    lineage = build_topology_frontier_lineage(selected, evaluation)
    reconciliation = reconcile_topology_frontier(selected, evaluation)
    metrics = compute_topology_frontier_metrics(evaluation)
    bundle = build_topology_frontier_bundle(
        selected,
        data_audit=data_audit,
        evaluation=evaluation,
        replay=replay,
        scenarios=scenarios,
        policy=policy,
        lineage=lineage,
        reconciliation=reconciliation,
        metrics=metrics,
    )
    checks: list[TopologyFrontierQualityCheck] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "passed": passed, "detail": detail}
        checks.append(TopologyFrontierQualityCheck(**body, content_address=content_hash(body)))

    add("data-audit", data_audit.accepted, "source and payload boundary")
    add("evaluation", evaluation.accepted, "adapter receipts and checks")
    add("replay", replay.accepted, "deterministic replay")
    add("scenarios", scenarios.accepted, "positive and control scenarios")
    add("policy", policy.accepted, "scope and interpretation policy")
    add("schema", schemas.accepted, "operation schema validation")
    add("lineage", not verify_topology_frontier_lineage(lineage, selected, evaluation), "lineage closes")
    add("reconciliation", reconciliation.accepted, "expected and observed states")
    add("record-closure", set(bundle.record_ids) == {item.record_id for item in evaluation.receipts}, "bundle covers all records")
    add("source-closure", set(bundle.source_ids) == {item.source_id for item in selected.sources}, "bundle covers all sources")
    add("operation-closure", {item.operation for item in evaluation.receipts} == set(TopologyFrontierOperation), "bundle covers all operations")
    add("bundle", bundle.accepted, "content-addressed release input")
    body = {"fixture_id": selected.fixture_id, "bundle": bundle, "checks": checks}
    return TopologyFrontierQualityReport(selected.fixture_id, bundle, tuple(checks), content_hash(body))


__all__ = [
    "TopologyFrontierQualityCheck",
    "TopologyFrontierQualityReport",
    "run_topology_frontier_quality_gate",
]
