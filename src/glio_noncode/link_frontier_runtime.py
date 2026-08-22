"""Staged runtime orchestration for Domain 10 link evidence."""

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
from .link_frontier_quality_gate import LinkFrontierQualityGate, run_link_frontier_quality_gate
from .link_frontier_reconciliation import reconcile_link_frontier
from .link_frontier_schema import validate_link_frontier_schema
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkFrontierRuntimeStage:
    stage_id: str
    state: str
    output_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkFrontierPipeline:
    fixture_id: str
    stages: tuple[LinkFrontierRuntimeStage, ...]
    evaluation: LinkFrontierEvaluation
    quality_gate: LinkFrontierQualityGate
    metrics_address: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _stage(stage_id: str, state: str, address: str, detail: str) -> LinkFrontierRuntimeStage:
    body = {"stage_id": stage_id, "state": state, "output_address": address, "detail": detail}
    return LinkFrontierRuntimeStage(**body, content_address=content_hash(body))


def run_link_frontier_pipeline(
    fixture: LinkFrontierFixture | None = None,
) -> LinkFrontierPipeline:
    fixture = fixture or default_link_frontier_fixture()
    audit = audit_link_frontier_data(fixture)
    evaluation = evaluate_link_frontier_fixture(fixture)
    reconciliation = reconcile_link_frontier(fixture, evaluation)
    lineage = build_link_frontier_lineage(fixture, evaluation)
    policy = evaluate_link_frontier_policy(fixture, evaluation=evaluation)
    schema = validate_link_frontier_schema(fixture)
    metrics = compute_link_frontier_metrics(fixture, evaluation)
    quality = run_link_frontier_quality_gate(fixture, evaluation=evaluation)
    stages = (
        _stage("load", "accepted" if audit.accepted else "blocked", fixture.content_address, "load fixture"),
        _stage("evaluate", "accepted" if evaluation.accepted else "review", evaluation.content_address, "execute four link operations"),
        _stage("reconcile", "accepted" if reconciliation.accepted else "review", reconciliation.content_address, "compare expectations"),
        _stage("lineage", "accepted" if lineage.valid else "blocked", lineage.content_address, "close source and record lineage"),
        _stage("policy", "accepted" if policy.accepted else "blocked", policy.content_address, "apply bounded-use policy"),
        _stage("schema", "accepted" if schema.accepted else "blocked", schema.content_address, "validate contract schemas"),
        _stage("metrics", "accepted", metrics.content_address, "compute operational metrics"),
        _stage("quality", "accepted" if quality.accepted else "blocked", quality.content_address, "run release gate"),
        _stage("complete", "accepted" if quality.accepted else "blocked", quality.content_address, "pipeline complete"),
    )
    body = {
        "fixture_id": fixture.fixture_id,
        "stages": stages,
        "evaluation": evaluation,
        "quality_gate": quality,
        "metrics_address": metrics.content_address,
        "accepted": quality.accepted,
    }
    return LinkFrontierPipeline(**body, content_address=content_hash(body))


__all__ = ["LinkFrontierPipeline", "LinkFrontierRuntimeStage", "run_link_frontier_pipeline"]
