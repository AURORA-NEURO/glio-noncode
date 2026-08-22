"""CLI operation facade for Domain 08 C09-C12."""

from __future__ import annotations

from typing import Any

from .cell_context_alpha_frontier_adapters import build_cell_context_alpha_frontier_adapters
from .cell_context_alpha_frontier_contracts import build_cell_context_alpha_frontier_contracts
from .cell_context_alpha_frontier_exports import (
    export_cell_context_alpha_frontier_manifest,
    export_cell_context_alpha_frontier_review_csv,
    render_cell_context_alpha_frontier_review_markdown,
)
from .cell_context_alpha_frontier_fixture_eval import evaluate_cell_context_alpha_frontier_fixture
from .cell_context_alpha_frontier_pipeline import run_cell_context_alpha_frontier_pipeline
from .cell_context_alpha_frontier_public_data import (
    audit_cell_context_alpha_frontier_data,
    default_cell_context_alpha_frontier_fixture,
)
from .cell_context_alpha_frontier_replay import replay_cell_context_alpha_frontier
from .cell_context_alpha_frontier_runtime import run_cell_context_alpha_frontier_runtime
from .cell_context_alpha_frontier_schema import validate_cell_context_alpha_frontier_schema
from .cell_context_alpha_frontier_source_registry import (
    build_cell_context_alpha_frontier_source_registry,
)

CELL_CONTEXT_ALPHA_FRONTIER_COMMANDS = (
    "cell-context-alpha-frontier-fixture",
    "cell-context-alpha-frontier-data",
    "cell-context-alpha-frontier-evaluate",
    "cell-context-alpha-frontier-replay",
    "cell-context-alpha-frontier-quality",
    "cell-context-alpha-frontier-contracts",
    "cell-context-alpha-frontier-adapters",
    "cell-context-alpha-frontier-schema",
    "cell-context-alpha-frontier-sources",
    "cell-context-alpha-frontier-export",
    "cell-context-alpha-frontier-review",
    "run-cell-context-alpha-frontier-pipeline",
)


def run_cell_context_alpha_frontier_operation(operation: str) -> dict[str, Any]:
    if operation not in CELL_CONTEXT_ALPHA_FRONTIER_COMMANDS:
        raise ValueError(f"unsupported alpha frontier operation: {operation}")
    fixture = default_cell_context_alpha_frontier_fixture()
    evaluation = evaluate_cell_context_alpha_frontier_fixture(fixture)
    if operation == "cell-context-alpha-frontier-fixture":
        return fixture.to_dict(True)
    if operation == "cell-context-alpha-frontier-data":
        return audit_cell_context_alpha_frontier_data(fixture).to_dict()
    if operation == "cell-context-alpha-frontier-evaluate":
        return evaluation.to_dict()
    if operation == "cell-context-alpha-frontier-replay":
        return replay_cell_context_alpha_frontier(fixture).to_dict()
    if operation == "cell-context-alpha-frontier-quality":
        return run_cell_context_alpha_frontier_runtime(fixture=fixture).quality.to_dict()
    if operation == "cell-context-alpha-frontier-contracts":
        return build_cell_context_alpha_frontier_contracts().to_dict()
    if operation == "cell-context-alpha-frontier-adapters":
        return build_cell_context_alpha_frontier_adapters().to_dict()
    if operation == "cell-context-alpha-frontier-schema":
        return validate_cell_context_alpha_frontier_schema(fixture, evaluation).to_dict()
    if operation == "cell-context-alpha-frontier-sources":
        return build_cell_context_alpha_frontier_source_registry(fixture).to_dict()
    if operation == "cell-context-alpha-frontier-export":
        return {
            "manifest": export_cell_context_alpha_frontier_manifest(fixture, evaluation),
            "review_csv": export_cell_context_alpha_frontier_review_csv(evaluation),
        }
    if operation == "cell-context-alpha-frontier-review":
        return {"markdown": render_cell_context_alpha_frontier_review_markdown(evaluation)}
    return run_cell_context_alpha_frontier_pipeline(fixture).to_dict()


__all__ = ["CELL_CONTEXT_ALPHA_FRONTIER_COMMANDS", "run_cell_context_alpha_frontier_operation"]
