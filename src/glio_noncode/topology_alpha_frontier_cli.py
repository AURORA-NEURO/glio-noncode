"""Programmatic command surface for the topology-alpha release slice."""

from __future__ import annotations

from typing import Any

from .topology_alpha_frontier_accessibility import evaluate_topology_alpha_frontier_accessibility
from .topology_alpha_frontier_catalog import build_topology_alpha_frontier_catalog
from .topology_alpha_frontier_contracts import build_topology_alpha_frontier_contracts
from .topology_alpha_frontier_fixture_eval import evaluate_topology_alpha_frontier_fixture
from .topology_alpha_frontier_metrics import build_topology_alpha_frontier_metrics
from .topology_alpha_frontier_pipeline import run_topology_alpha_frontier_pipeline
from .topology_alpha_frontier_public_data import default_topology_alpha_frontier_fixture
from .topology_alpha_frontier_release import build_topology_alpha_frontier_release
from .topology_alpha_frontier_runbook import default_topology_alpha_frontier_runbook
from .topology_alpha_frontier_schema import validate_topology_alpha_frontier_schema


TOPOLOGY_ALPHA_FRONTIER_COMMANDS = (
    "topology-alpha-frontier-fixture",
    "topology-alpha-frontier-evaluate",
    "topology-alpha-frontier-contracts",
    "topology-alpha-frontier-schema",
    "topology-alpha-frontier-metrics",
    "topology-alpha-frontier-catalog",
    "topology-alpha-frontier-accessibility",
    "topology-alpha-frontier-runbook",
    "topology-alpha-frontier-review",
    "topology-alpha-frontier-release",
    "topology-alpha-frontier-manifest",
    "topology-alpha-frontier-summary",
)


def run_topology_alpha_frontier_operation(operation: str) -> dict[str, Any]:
    fixture = default_topology_alpha_frontier_fixture()
    evaluation = evaluate_topology_alpha_frontier_fixture(fixture)
    pipeline = run_topology_alpha_frontier_pipeline(fixture)
    values: dict[str, Any] = {
        "topology-alpha-frontier-fixture": fixture.to_dict(),
        "topology-alpha-frontier-evaluate": evaluation.to_dict(),
        "topology-alpha-frontier-contracts": build_topology_alpha_frontier_contracts().to_dict(),
        "topology-alpha-frontier-schema": validate_topology_alpha_frontier_schema(fixture, evaluation).to_dict(),
        "topology-alpha-frontier-metrics": build_topology_alpha_frontier_metrics(evaluation).to_dict(),
        "topology-alpha-frontier-catalog": build_topology_alpha_frontier_catalog().to_dict(),
        "topology-alpha-frontier-accessibility": evaluate_topology_alpha_frontier_accessibility(evaluation).to_dict(),
        "topology-alpha-frontier-runbook": default_topology_alpha_frontier_runbook().to_dict(),
        "topology-alpha-frontier-review": {"record_count": len(evaluation.rows), "review_count": len(evaluation.controls()), "rows": [item.to_dict() for item in evaluation.controls()]},
        "topology-alpha-frontier-release": build_topology_alpha_frontier_release(fixture, evaluation, pipeline.quality).to_dict(),
        "topology-alpha-frontier-manifest": {"fixture_id": fixture.fixture_id, "version": fixture.version, "boundary": fixture.boundary},
        "topology-alpha-frontier-summary": {"accepted": pipeline.accepted, "state_match_count": evaluation.state_match_count, "issue_match_count": evaluation.issue_match_count, "stage_count": len(pipeline.stages)},
    }
    if operation not in values:
        raise KeyError(operation)
    return values[operation]


__all__ = ["TOPOLOGY_ALPHA_FRONTIER_COMMANDS", "run_topology_alpha_frontier_operation"]
