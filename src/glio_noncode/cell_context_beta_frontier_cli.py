"""CLI operation facade for Domain 08 C05-C08."""

from __future__ import annotations

from typing import Any

from .cell_context_beta_frontier_adapters import build_cell_context_beta_frontier_adapters
from .cell_context_beta_frontier_contracts import build_cell_context_beta_frontier_contracts
from .cell_context_beta_frontier_exports import (
    export_cell_context_beta_frontier_manifest,
    export_cell_context_beta_frontier_review_csv,
    render_cell_context_beta_frontier_review_markdown,
)
from .cell_context_beta_frontier_fixture_eval import evaluate_cell_context_beta_frontier_fixture
from .cell_context_beta_frontier_pipeline import run_cell_context_beta_frontier_pipeline
from .cell_context_beta_frontier_public_data import (
    audit_cell_context_beta_frontier_data,
    default_cell_context_beta_frontier_fixture,
)
from .cell_context_beta_frontier_replay import replay_cell_context_beta_frontier
from .cell_context_beta_frontier_runtime import run_cell_context_beta_frontier_runtime
from .cell_context_beta_frontier_schema import validate_cell_context_beta_frontier_schema
from .cell_context_beta_frontier_source_registry import (
    build_cell_context_beta_frontier_source_registry,
)

CELL_CONTEXT_BETA_FRONTIER_COMMANDS = (
    "cell-context-beta-frontier-fixture",
    "cell-context-beta-frontier-data",
    "cell-context-beta-frontier-evaluate",
    "cell-context-beta-frontier-replay",
    "cell-context-beta-frontier-quality",
    "cell-context-beta-frontier-contracts",
    "cell-context-beta-frontier-adapters",
    "cell-context-beta-frontier-schema",
    "cell-context-beta-frontier-sources",
    "cell-context-beta-frontier-export",
    "cell-context-beta-frontier-review",
    "run-cell-context-beta-frontier-pipeline",
)


def run_cell_context_beta_frontier_operation(operation: str) -> dict[str, Any]:
    if operation not in CELL_CONTEXT_BETA_FRONTIER_COMMANDS:
        raise ValueError(f"unsupported beta frontier operation: {operation}")
    fixture = default_cell_context_beta_frontier_fixture()
    evaluation = evaluate_cell_context_beta_frontier_fixture(fixture)
    if operation == "cell-context-beta-frontier-fixture":
        return fixture.to_dict(True)
    if operation == "cell-context-beta-frontier-data":
        return audit_cell_context_beta_frontier_data(fixture).to_dict()
    if operation == "cell-context-beta-frontier-evaluate":
        return evaluation.to_dict()
    if operation == "cell-context-beta-frontier-replay":
        return replay_cell_context_beta_frontier(fixture).to_dict()
    if operation == "cell-context-beta-frontier-quality":
        return run_cell_context_beta_frontier_runtime(fixture=fixture).quality.to_dict()
    if operation == "cell-context-beta-frontier-contracts":
        return build_cell_context_beta_frontier_contracts().to_dict()
    if operation == "cell-context-beta-frontier-adapters":
        return build_cell_context_beta_frontier_adapters().to_dict()
    if operation == "cell-context-beta-frontier-schema":
        return validate_cell_context_beta_frontier_schema(fixture, evaluation).to_dict()
    if operation == "cell-context-beta-frontier-sources":
        return build_cell_context_beta_frontier_source_registry(fixture).to_dict()
    if operation == "cell-context-beta-frontier-export":
        return {
            "manifest": export_cell_context_beta_frontier_manifest(fixture, evaluation),
            "review_csv": export_cell_context_beta_frontier_review_csv(evaluation),
        }
    if operation == "cell-context-beta-frontier-review":
        return {"markdown": render_cell_context_beta_frontier_review_markdown(evaluation)}
    return run_cell_context_beta_frontier_pipeline(fixture).to_dict()


__all__ = ["CELL_CONTEXT_BETA_FRONTIER_COMMANDS", "run_cell_context_beta_frontier_operation"]
