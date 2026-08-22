"""Composed quality gate for Domain 07 chromatin frontier evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_frontier_bundle import ChromatinFrontierBundle, build_chromatin_frontier_bundle
from .chromatin_frontier_fixture_eval import evaluate_chromatin_frontier_fixture
from .chromatin_frontier_lineage import (
    build_chromatin_frontier_lineage,
    verify_chromatin_frontier_lineage,
)
from .chromatin_frontier_metrics import compute_chromatin_frontier_metrics
from .chromatin_frontier_policy import evaluate_chromatin_frontier_policy
from .chromatin_frontier_public_data import (
    ChromatinFrontierFixture,
    audit_chromatin_frontier_data,
    default_chromatin_frontier_fixture,
)
from .chromatin_frontier_reconciliation import reconcile_chromatin_frontier
from .chromatin_frontier_replay import replay_chromatin_frontier_evaluation
from .chromatin_frontier_scenario_matrix import evaluate_chromatin_frontier_scenarios
from .chromatin_frontier_schema import validate_chromatin_frontier_schema
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinFrontierQualityCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinFrontierQualityReport:
    fixture_id: str
    checks: tuple[ChromatinFrontierQualityCheck, ...]
    bundle: ChromatinFrontierBundle
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(item.passed for item in self.checks) and self.bundle.accepted

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        failed = [item.check_id for item in self.checks if not item.passed]
        if not self.bundle.accepted:
            failed.append("bundle-accepted")
        return tuple(failed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "failed_check_ids": list(self.failed_check_ids),
        }


def run_chromatin_frontier_quality_gate(
    fixture: ChromatinFrontierFixture | None = None,
) -> ChromatinFrontierQualityReport:
    selected = fixture or default_chromatin_frontier_fixture()
    audit = audit_chromatin_frontier_data(selected)
    evaluation = evaluate_chromatin_frontier_fixture(selected)
    replay = replay_chromatin_frontier_evaluation(evaluation, fixture=selected)
    scenarios = evaluate_chromatin_frontier_scenarios(evaluation)
    policy = evaluate_chromatin_frontier_policy(selected, evaluation)
    schema = validate_chromatin_frontier_schema(selected, evaluation)
    lineage = build_chromatin_frontier_lineage(selected, evaluation)
    reconciliation = reconcile_chromatin_frontier(selected, evaluation)
    metrics = compute_chromatin_frontier_metrics(evaluation)
    checks: list[ChromatinFrontierQualityCheck] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "passed": passed, "detail": detail}
        checks.append(ChromatinFrontierQualityCheck(**body, content_address=content_hash(body)))

    add("data-audit", audit.accepted, "public aggregate audit accepted")
    add("evaluation", evaluation.accepted, "adapter evaluation accepted")
    add("replay", replay.accepted, "replay accepted")
    add("scenarios", scenarios.accepted, "scenario matrix accepted")
    add("policy", policy.accepted, "policy accepted")
    add("schema", schema.accepted, "schema accepted")
    add(
        "lineage",
        not verify_chromatin_frontier_lineage(lineage, selected, evaluation),
        "lineage closes",
    )
    add("reconciliation", reconciliation.accepted, "expected and observed states reconcile")
    add("check-floor", len(evaluation.checks) >= 120, "evaluation has 120 checks")
    add("positive-floor", evaluation.positive_count == 4, "four positive paths exist")
    add("control-floor", evaluation.control_count == 12, "twelve controls exist")
    add("metric-address", metrics.content_address.startswith("sha256:"), "metrics are addressed")
    bundle = build_chromatin_frontier_bundle(
        selected,
        audit,
        evaluation,
        replay,
        scenarios,
        policy,
        lineage,
        reconciliation,
        metrics,
    )
    body = {"fixture_id": selected.fixture_id, "checks": checks, "bundle": bundle}
    return ChromatinFrontierQualityReport(
        selected.fixture_id,
        tuple(checks),
        bundle,
        content_hash(body),
    )


__all__ = [
    "ChromatinFrontierQualityCheck",
    "ChromatinFrontierQualityReport",
    "run_chromatin_frontier_quality_gate",
]
