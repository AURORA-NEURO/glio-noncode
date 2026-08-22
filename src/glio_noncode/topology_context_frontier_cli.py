"""CLI operation facade for Domain 09 C01-C04."""

from __future__ import annotations

from typing import Any

from .topology_context_frontier_adapters import build_topology_context_frontier_adapters
from .topology_context_frontier_contracts import build_topology_context_frontier_contracts
from .topology_context_frontier_exports import (
    export_topology_context_frontier_manifest,
    export_topology_context_frontier_review_csv,
    render_topology_context_frontier_review_markdown,
)
from .topology_context_frontier_fixture_eval import evaluate_topology_context_frontier_fixture
from .topology_context_frontier_pipeline import run_topology_context_frontier_pipeline
from .topology_context_frontier_public_data import (
    audit_topology_context_frontier_data,
    default_topology_context_frontier_fixture,
)
from .topology_context_frontier_replay import replay_topology_context_frontier
from .topology_context_frontier_runtime import run_topology_context_frontier_runtime
from .topology_context_frontier_schema import validate_topology_context_frontier_schema
from .topology_context_frontier_source_registry import (
    build_topology_context_frontier_source_registry,
)

TOPOLOGY_CONTEXT_FRONTIER_COMMANDS = (
    "topology-context-frontier-fixture",
    "topology-context-frontier-data",
    "topology-context-frontier-evaluate",
    "topology-context-frontier-replay",
    "topology-context-frontier-quality",
    "topology-context-frontier-contracts",
    "topology-context-frontier-adapters",
    "topology-context-frontier-schema",
    "topology-context-frontier-sources",
    "topology-context-frontier-export",
    "topology-context-frontier-review",
    "run-topology-context-frontier-pipeline",
)


def run_topology_context_frontier_operation(operation: str) -> dict[str, Any]:
    if operation not in TOPOLOGY_CONTEXT_FRONTIER_COMMANDS:
        raise ValueError(f"unsupported topology frontier operation: {operation}")
    fixture = default_topology_context_frontier_fixture()
    evaluation = evaluate_topology_context_frontier_fixture(fixture)
    if operation == "topology-context-frontier-fixture":
        return fixture.to_dict(True)
    if operation == "topology-context-frontier-data":
        return audit_topology_context_frontier_data(fixture).to_dict()
    if operation == "topology-context-frontier-evaluate":
        return evaluation.to_dict()
    if operation == "topology-context-frontier-replay":
        return replay_topology_context_frontier(fixture).to_dict()
    if operation == "topology-context-frontier-quality":
        return run_topology_context_frontier_runtime(fixture=fixture).quality.to_dict()
    if operation == "topology-context-frontier-contracts":
        return build_topology_context_frontier_contracts().to_dict()
    if operation == "topology-context-frontier-adapters":
        return build_topology_context_frontier_adapters().to_dict()
    if operation == "topology-context-frontier-schema":
        return validate_topology_context_frontier_schema(fixture, evaluation).to_dict()
    if operation == "topology-context-frontier-sources":
        return build_topology_context_frontier_source_registry(fixture).to_dict()
    if operation == "topology-context-frontier-export":
        return {
            "manifest": export_topology_context_frontier_manifest(fixture, evaluation),
            "review_csv": export_topology_context_frontier_review_csv(evaluation),
        }
    if operation == "topology-context-frontier-review":
        return {"markdown": render_topology_context_frontier_review_markdown(evaluation)}
    return run_topology_context_frontier_pipeline(fixture).to_dict()


__all__ = ["TOPOLOGY_CONTEXT_FRONTIER_COMMANDS", "run_topology_context_frontier_operation"]
