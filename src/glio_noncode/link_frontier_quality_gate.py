"""Release-quality checks for the Domain 10 link frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_frontier_fixture_eval import LinkFrontierEvaluation, evaluate_link_frontier_fixture
from .link_frontier_lineage import build_link_frontier_lineage
from .link_frontier_metrics import compute_link_frontier_metrics
from .link_frontier_policy import evaluate_link_frontier_policy
from .link_frontier_public_data import (
    LinkFrontierFixture,
    audit_link_frontier_data,
    default_link_frontier_fixture,
)
from .link_frontier_reconciliation import reconcile_link_frontier
from .link_frontier_replay import replay_link_frontier_evaluation
from .link_frontier_schema import validate_link_frontier_schema
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkFrontierQualityCheck:
    check_id: str
    passed: bool
    observed: Any
    threshold: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkFrontierQualityGate:
    fixture_id: str
    checks: tuple[LinkFrontierQualityCheck, ...]
    accepted: bool
    evaluation_address: str
    bundle_inputs: dict[str, str]
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_check_ids": list(self.failed_check_ids)}


def _check(check_id: str, passed: bool, observed: Any, threshold: Any, detail: str) -> LinkFrontierQualityCheck:
    body = {"check_id": check_id, "passed": passed, "observed": observed, "threshold": threshold, "detail": detail}
    return LinkFrontierQualityCheck(**body, content_address=content_hash(body))


def run_link_frontier_quality_gate(
    fixture: LinkFrontierFixture | None = None,
    *,
    evaluation: LinkFrontierEvaluation | None = None,
) -> LinkFrontierQualityGate:
    fixture = fixture or default_link_frontier_fixture()
    evaluation = evaluation or evaluate_link_frontier_fixture(fixture)
    audit = audit_link_frontier_data(fixture)
    reconciliation = reconcile_link_frontier(fixture, evaluation)
    lineage = build_link_frontier_lineage(fixture, evaluation)
    policy = evaluate_link_frontier_policy(fixture, evaluation=evaluation)
    schema = validate_link_frontier_schema(fixture)
    replay = replay_link_frontier_evaluation(fixture, first=evaluation)
    metrics = compute_link_frontier_metrics(fixture, evaluation)
    checks = [
        _check("data_audit", audit.accepted, audit.accepted, True, "fixture data audit accepted"),
        _check("evaluation", evaluation.accepted, evaluation.failed_check_ids, (), "positive and control evaluation accepted"),
        _check("reconciliation", reconciliation.accepted, reconciliation.accepted, True, "expected and observed states reconcile"),
        _check("lineage", lineage.valid, lineage.valid, True, "lineage graph is closed"),
        _check("policy", policy.accepted, policy.failed_rule_ids, (), "policy report accepted"),
        _check("schema", schema.accepted, schema.failed_check_ids, (), "schema report accepted"),
        _check("replay", replay.deterministic, replay.deterministic, True, "replay is deterministic"),
        _check("positive_acceptance", metrics.positive_acceptance_rate == 1.0, metrics.positive_acceptance_rate, 1.0, "all positive records accepted"),
        _check("control_rejection", metrics.control_rejection_rate == 1.0, metrics.control_rejection_rate, 1.0, "all controls rejected or reviewed"),
        _check("record_count", metrics.record_count == 16, metrics.record_count, 16, "fixture record count is fixed"),
        _check("source_count", len(fixture.sources) == 5, len(fixture.sources), 5, "source receipt count is fixed"),
        _check("operation_count", len(metrics.operation_counts) == 4, len(metrics.operation_counts), 4, "all operation bands execute"),
    ]
    body = {
        "fixture_id": fixture.fixture_id,
        "checks": checks,
        "accepted": all(item.passed for item in checks),
        "evaluation_address": evaluation.content_address,
        "bundle_inputs": {
            "audit": audit.content_address,
            "reconciliation": reconciliation.content_address,
            "lineage": lineage.content_address,
            "policy": policy.content_address,
            "schema": schema.content_address,
            "replay": replay.content_address,
            "metrics": metrics.content_address,
        },
    }
    return LinkFrontierQualityGate(**body, content_address=content_hash(body))


__all__ = ["LinkFrontierQualityCheck", "LinkFrontierQualityGate", "run_link_frontier_quality_gate"]
