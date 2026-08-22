"""CLI operations for the Domain 07 C01-C04 aggregate plane."""

from __future__ import annotations

from typing import Any

from .chromatin_context_frontier_adapters import build_chromatin_context_frontier_adapters
from .chromatin_context_frontier_contracts import build_chromatin_context_frontier_contracts
from .chromatin_context_frontier_fixture_eval import evaluate_chromatin_context_frontier_fixture
from .chromatin_context_frontier_pipeline import run_chromatin_context_frontier_pipeline
from .chromatin_context_frontier_public_data import (
    audit_chromatin_context_frontier_data,
    default_chromatin_context_frontier_fixture,
)
from .chromatin_context_frontier_replay import replay_chromatin_context_frontier
from .chromatin_context_frontier_runtime import run_chromatin_context_frontier_runtime
from .chromatin_context_frontier_schema import validate_chromatin_context_frontier_schema
from .chromatin_context_frontier_source_registry import (
    build_chromatin_context_frontier_source_registry,
)

_OPERATIONS = {
    "chromatin-context-frontier-fixture",
    "chromatin-context-frontier-data",
    "chromatin-context-frontier-evaluate",
    "chromatin-context-frontier-replay",
    "chromatin-context-frontier-quality",
    "chromatin-context-frontier-contracts",
    "chromatin-context-frontier-adapters",
    "chromatin-context-frontier-schema",
    "chromatin-context-frontier-sources",
    "run-chromatin-context-frontier-pipeline",
}


def run_chromatin_context_frontier_operation(operation: str) -> dict[str, Any]:
    if operation not in _OPERATIONS:
        raise ValueError(f"unsupported chromatin-context-frontier operation: {operation}")
    fixture = default_chromatin_context_frontier_fixture()
    if operation == "chromatin-context-frontier-fixture":
        return fixture.to_dict(include_payload=True)
    if operation == "chromatin-context-frontier-data":
        return audit_chromatin_context_frontier_data(fixture).to_dict()
    if operation == "chromatin-context-frontier-evaluate":
        return evaluate_chromatin_context_frontier_fixture(fixture).to_dict()
    if operation == "chromatin-context-frontier-replay":
        return replay_chromatin_context_frontier(fixture).to_dict()
    if operation == "chromatin-context-frontier-quality":
        return run_chromatin_context_frontier_runtime(fixture=fixture).quality.to_dict()
    if operation == "chromatin-context-frontier-contracts":
        return build_chromatin_context_frontier_contracts().to_dict()
    if operation == "chromatin-context-frontier-adapters":
        return build_chromatin_context_frontier_adapters().to_dict()
    if operation == "chromatin-context-frontier-schema":
        return validate_chromatin_context_frontier_schema(
            fixture, evaluate_chromatin_context_frontier_fixture(fixture)
        ).to_dict()
    if operation == "chromatin-context-frontier-sources":
        return build_chromatin_context_frontier_source_registry(fixture).to_dict()
    return run_chromatin_context_frontier_pipeline(fixture).to_dict()


__all__ = ["run_chromatin_context_frontier_operation"]
