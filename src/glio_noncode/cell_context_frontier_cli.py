"""CLI operation facade for Domain 08 C01-C04."""

from __future__ import annotations

from typing import Any

from .cell_context_frontier_adapters import build_cell_context_frontier_adapters
from .cell_context_frontier_contracts import build_cell_context_frontier_contracts
from .cell_context_frontier_fixture_eval import evaluate_cell_context_frontier_fixture
from .cell_context_frontier_pipeline import run_cell_context_frontier_pipeline
from .cell_context_frontier_public_data import (
    audit_cell_context_frontier_data,
    default_cell_context_frontier_fixture,
)
from .cell_context_frontier_replay import replay_cell_context_frontier
from .cell_context_frontier_runtime import run_cell_context_frontier_runtime
from .cell_context_frontier_schema import validate_cell_context_frontier_schema
from .cell_context_frontier_source_registry import build_cell_context_frontier_source_registry

CELL_CONTEXT_FRONTIER_COMMANDS = (
    "cell-context-frontier-fixture",
    "cell-context-frontier-data",
    "cell-context-frontier-evaluate",
    "cell-context-frontier-replay",
    "cell-context-frontier-quality",
    "cell-context-frontier-contracts",
    "cell-context-frontier-adapters",
    "cell-context-frontier-schema",
    "cell-context-frontier-sources",
    "run-cell-context-frontier-pipeline",
)


def run_cell_context_frontier_operation(operation: str) -> dict[str, Any]:
    if operation not in CELL_CONTEXT_FRONTIER_COMMANDS:
        raise ValueError(f"unsupported cell-context-frontier operation: {operation}")
    fixture = default_cell_context_frontier_fixture()
    if operation == "cell-context-frontier-fixture":
        return fixture.to_dict(include_payload=True)
    if operation == "cell-context-frontier-data":
        return audit_cell_context_frontier_data(fixture).to_dict()
    if operation == "cell-context-frontier-evaluate":
        return evaluate_cell_context_frontier_fixture(fixture).to_dict()
    if operation == "cell-context-frontier-replay":
        return replay_cell_context_frontier(fixture).to_dict()
    if operation == "cell-context-frontier-quality":
        return run_cell_context_frontier_runtime(fixture=fixture).quality.to_dict()
    if operation == "cell-context-frontier-contracts":
        return build_cell_context_frontier_contracts().to_dict()
    if operation == "cell-context-frontier-adapters":
        return build_cell_context_frontier_adapters().to_dict()
    if operation == "cell-context-frontier-schema":
        return validate_cell_context_frontier_schema(
            fixture, evaluate_cell_context_frontier_fixture(fixture)
        ).to_dict()
    if operation == "cell-context-frontier-sources":
        return build_cell_context_frontier_source_registry(fixture).to_dict()
    return run_cell_context_frontier_pipeline(fixture).to_dict()


__all__ = ["CELL_CONTEXT_FRONTIER_COMMANDS", "run_cell_context_frontier_operation"]
