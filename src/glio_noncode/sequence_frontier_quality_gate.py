"""Layered quality gate for Domain 06 C13-C16."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_frontier_bundle import SequenceFrontierBundle, build_sequence_frontier_bundle
from .sequence_frontier_fixture_eval import evaluate_sequence_frontier_fixture
from .sequence_frontier_lineage import (
    build_sequence_frontier_lineage,
    verify_sequence_frontier_lineage,
)
from .sequence_frontier_metrics import compute_sequence_frontier_metrics
from .sequence_frontier_policy import evaluate_sequence_frontier_policy
from .sequence_frontier_public_data import (
    SequenceFrontierFixture,
    audit_sequence_frontier_data,
    default_sequence_frontier_fixture,
)
from .sequence_frontier_reconciliation import reconcile_sequence_frontier
from .sequence_frontier_replay import replay_sequence_frontier_evaluation
from .sequence_frontier_scenario_matrix import evaluate_sequence_frontier_scenarios
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceFrontierQualityCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceFrontierQualityReport:
    fixture_id: str
    checks: tuple[SequenceFrontierQualityCheck, ...]
    bundle: SequenceFrontierBundle
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(item.passed for item in self.checks) and self.bundle.accepted

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "failed_check_ids": list(self.failed_check_ids),
        }


def run_sequence_frontier_quality_gate(
    fixture: SequenceFrontierFixture | None = None,
) -> SequenceFrontierQualityReport:
    selected = fixture or default_sequence_frontier_fixture()
    audit = audit_sequence_frontier_data(selected)
    evaluation = evaluate_sequence_frontier_fixture(selected)
    replay = replay_sequence_frontier_evaluation(evaluation, fixture=selected)
    scenarios = evaluate_sequence_frontier_scenarios(evaluation)
    policy = evaluate_sequence_frontier_policy(selected, evaluation)
    lineage = build_sequence_frontier_lineage(selected, evaluation)
    reconciliation = reconcile_sequence_frontier(selected, evaluation)
    metrics = compute_sequence_frontier_metrics(evaluation)
    checks: list[SequenceFrontierQualityCheck] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "passed": passed, "detail": detail}
        checks.append(SequenceFrontierQualityCheck(**body, content_address=content_hash(body)))

    add("data-audit", audit.accepted, "public aggregate audit accepted")
    add("evaluation", evaluation.accepted, "adapter evaluation accepted")
    add("replay", replay.accepted, "replay accepted")
    add("scenarios", scenarios.accepted, "scenario matrix accepted")
    add("policy", policy.accepted, "policy accepted")
    add(
        "lineage",
        not verify_sequence_frontier_lineage(lineage, selected, evaluation),
        "lineage closes",
    )
    add("reconciliation", reconciliation.accepted, "expected and observed states reconcile")
    add("check-floor", len(evaluation.checks) >= 120, "evaluation has 120 checks")
    add("positive-floor", evaluation.positive_count == 4, "four positive paths exist")
    add("control-floor", evaluation.control_count == 12, "twelve controls exist")
    add("metric-address", metrics.content_address.startswith("sha256:"), "metrics are addressed")
    bundle = build_sequence_frontier_bundle(
        selected, audit, evaluation, replay, scenarios, policy, lineage, reconciliation, metrics
    )
    body = {"fixture_id": selected.fixture_id, "checks": checks, "bundle": bundle}
    return SequenceFrontierQualityReport(
        selected.fixture_id, tuple(checks), bundle, content_hash(body)
    )


__all__ = [
    "SequenceFrontierQualityCheck",
    "SequenceFrontierQualityReport",
    "run_sequence_frontier_quality_gate",
]
