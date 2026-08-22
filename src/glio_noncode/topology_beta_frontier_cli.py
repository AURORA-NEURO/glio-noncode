"""Programmatic command surface for the topology-beta release slice."""

from __future__ import annotations

from typing import Any

from .topology_beta_frontier_accessibility import evaluate_topology_beta_frontier_accessibility
from .topology_beta_frontier_catalog import build_topology_beta_frontier_catalog
from .topology_beta_frontier_contracts import build_topology_beta_frontier_contracts
from .topology_beta_frontier_fixture_eval import evaluate_topology_beta_frontier_fixture
from .topology_beta_frontier_metrics import build_topology_beta_frontier_metrics
from .topology_beta_frontier_public_data import default_topology_beta_frontier_fixture
from .topology_beta_frontier_release import build_topology_beta_frontier_release
from .topology_beta_frontier_runbook import default_topology_beta_frontier_runbook
from .topology_beta_frontier_schema import validate_topology_beta_frontier_schema

TOPOLOGY_BETA_FRONTIER_COMMANDS = (
    "topology-beta-frontier-fixture",
    "topology-beta-frontier-evaluate",
    "topology-beta-frontier-contracts",
    "topology-beta-frontier-schema",
    "topology-beta-frontier-metrics",
    "topology-beta-frontier-catalog",
    "topology-beta-frontier-accessibility",
    "topology-beta-frontier-runbook",
    "topology-beta-frontier-review",
    "topology-beta-frontier-release",
    "topology-beta-frontier-manifest",
    "topology-beta-frontier-summary",
)


def run_topology_beta_frontier_operation(operation: str) -> dict[str, Any]:
    fixture = default_topology_beta_frontier_fixture()
    evaluation = evaluate_topology_beta_frontier_fixture(fixture)
    values: dict[str, Any] = {
        "topology-beta-frontier-fixture": fixture.to_dict(),
        "topology-beta-frontier-evaluate": evaluation.to_dict(),
        "topology-beta-frontier-contracts": build_topology_beta_frontier_contracts().to_dict(),
        "topology-beta-frontier-schema": validate_topology_beta_frontier_schema(fixture, evaluation).to_dict(),
        "topology-beta-frontier-metrics": build_topology_beta_frontier_metrics(evaluation).to_dict(),
        "topology-beta-frontier-catalog": build_topology_beta_frontier_catalog().to_dict(),
        "topology-beta-frontier-accessibility": evaluate_topology_beta_frontier_accessibility(evaluation).to_dict(),
        "topology-beta-frontier-runbook": default_topology_beta_frontier_runbook().to_dict(),
        "topology-beta-frontier-review": {"record_count": len(evaluation.rows), "review_count": len(evaluation.controls()), "rows": [item.to_dict() for item in evaluation.controls()]},
        "topology-beta-frontier-release": {"fixture_id": fixture.fixture_id, "ready": evaluation.accepted},
        "topology-beta-frontier-manifest": {"fixture_id": fixture.fixture_id, "version": fixture.version, "boundary": fixture.boundary},
        "topology-beta-frontier-summary": {"accepted": evaluation.accepted, "state_match_count": evaluation.state_match_count, "issue_match_count": evaluation.issue_match_count},
    }
    if operation not in values:
        raise KeyError(operation)
    return values[operation]


__all__ = ["TOPOLOGY_BETA_FRONTIER_COMMANDS", "run_topology_beta_frontier_operation"]
