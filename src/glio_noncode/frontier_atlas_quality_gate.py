"""Layered C13-C16 frontier atlas quality gate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .frontier_atlas_bundle import FrontierAtlasBundle, build_frontier_atlas_bundle
from .frontier_atlas_fixture_eval import evaluate_frontier_atlas_fixture
from .frontier_atlas_lineage import build_frontier_atlas_lineage, verify_frontier_atlas_lineage
from .frontier_atlas_metrics import compute_frontier_atlas_metrics
from .frontier_atlas_policy import evaluate_frontier_atlas_policy
from .frontier_atlas_public_data import (
    FrontierAtlasFixture,
    audit_frontier_atlas_data,
    default_frontier_atlas_fixture,
)
from .frontier_atlas_reconciliation import reconcile_frontier_atlas
from .frontier_atlas_replay import replay_frontier_atlas_evaluation
from .frontier_atlas_scenario_matrix import evaluate_frontier_atlas_scenarios
from .frontier_atlas_schema import validate_frontier_atlas_schema
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class FrontierAtlasQualityCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierAtlasQualityReport:
    fixture_id: str
    checks: tuple[FrontierAtlasQualityCheck, ...]
    bundle: FrontierAtlasBundle
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(check.passed for check in self.checks) and self.bundle.accepted

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "failed_check_ids": list(self.failed_check_ids),
        }


def run_frontier_atlas_quality_gate(
    fixture: FrontierAtlasFixture | None = None,
) -> FrontierAtlasQualityReport:
    """Run source, adapter, replay, scenario, policy, lineage, and release gates."""

    selected = fixture or default_frontier_atlas_fixture()
    data_audit = audit_frontier_atlas_data(selected)
    evaluation = evaluate_frontier_atlas_fixture(selected)
    replay = replay_frontier_atlas_evaluation(evaluation, fixture=selected)
    scenarios = evaluate_frontier_atlas_scenarios(evaluation)
    policy = evaluate_frontier_atlas_policy(selected, evaluation)
    lineage = build_frontier_atlas_lineage(selected, evaluation)
    reconciliation = reconcile_frontier_atlas(selected, evaluation)
    metrics = compute_frontier_atlas_metrics(evaluation)
    schema = validate_frontier_atlas_schema(selected, evaluation)
    checks: list[FrontierAtlasQualityCheck] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "passed": passed, "detail": detail}
        checks.append(FrontierAtlasQualityCheck(**body, content_address=content_hash(body)))

    add("data-audit", data_audit.accepted, "public aggregate data audit accepted")
    add("evaluation", evaluation.accepted, "adapter evaluation accepted")
    add("replay", replay.accepted, "replay accepted")
    add("scenarios", scenarios.accepted, "scenario matrix accepted")
    add("policy", policy.accepted, "policy accepted")
    add(
        "lineage",
        not verify_frontier_atlas_lineage(lineage, selected, evaluation),
        "lineage closes",
    )
    add("reconciliation", reconciliation.accepted, "expected and observed states reconcile")
    add("check-floor", len(evaluation.checks) >= 120, "evaluation has 120 checks")
    add("positive-floor", evaluation.positive_count == 4, "four positive paths exist")
    add("control-floor", evaluation.control_count == 12, "twelve controls exist")
    add("metric-address", metrics.content_address.startswith("sha256:"), "metrics are addressed")
    add("schema", schema.accepted, "operation schemas are accepted")
    bundle = build_frontier_atlas_bundle(
        selected,
        data_audit,
        evaluation,
        replay,
        scenarios,
        policy,
        lineage,
        reconciliation,
        metrics,
    )
    body = {"fixture_id": selected.fixture_id, "checks": checks, "bundle": bundle}
    return FrontierAtlasQualityReport(
        selected.fixture_id, tuple(checks), bundle, content_hash(body)
    )


__all__ = [
    "FrontierAtlasQualityCheck",
    "FrontierAtlasQualityReport",
    "run_frontier_atlas_quality_gate",
]
