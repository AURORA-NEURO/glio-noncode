"""CLI operations for Domain 07 C05-C08 aggregate methylation evidence."""

from __future__ import annotations

from typing import Any

from .methylation_frontier_adapters import build_methylation_frontier_adapters
from .methylation_frontier_contracts import build_methylation_frontier_contracts
from .methylation_frontier_fixture_eval import evaluate_methylation_frontier_fixture
from .methylation_frontier_pipeline import run_methylation_frontier_pipeline
from .methylation_frontier_public_data import (
    audit_methylation_frontier_data,
    build_methylation_frontier_catalog,
    default_methylation_frontier_fixture,
)
from .methylation_frontier_replay import replay_methylation_frontier
from .methylation_frontier_runtime import run_methylation_frontier_runtime
from .methylation_frontier_schema import validate_methylation_frontier_schema
from .methylation_frontier_source_registry import build_methylation_frontier_source_registry

_OPERATIONS = {
    "methylation-frontier-fixture",
    "methylation-frontier-data",
    "methylation-frontier-evaluate",
    "methylation-frontier-replay",
    "methylation-frontier-quality",
    "methylation-frontier-contracts",
    "methylation-frontier-adapters",
    "methylation-frontier-catalog",
    "methylation-frontier-schema",
    "methylation-frontier-sources",
    "run-methylation-frontier-pipeline",
}


def run_methylation_frontier_operation(operation: str) -> dict[str, Any]:
    """Run one named operation and return a JSON-compatible aggregate result."""

    if operation not in _OPERATIONS:
        raise ValueError(f"unsupported methylation-frontier operation: {operation}")
    fixture = default_methylation_frontier_fixture()
    if operation == "methylation-frontier-fixture":
        return fixture.to_dict(include_payload=True)
    if operation == "methylation-frontier-data":
        return audit_methylation_frontier_data(fixture).to_dict()
    if operation == "methylation-frontier-evaluate":
        return evaluate_methylation_frontier_fixture(fixture).to_dict()
    if operation == "methylation-frontier-replay":
        return replay_methylation_frontier(fixture).to_dict()
    if operation == "methylation-frontier-quality":
        return run_methylation_frontier_runtime(fixture=fixture).quality.to_dict()
    if operation == "methylation-frontier-contracts":
        return build_methylation_frontier_contracts().to_dict()
    if operation == "methylation-frontier-adapters":
        return build_methylation_frontier_adapters().to_dict()
    if operation == "methylation-frontier-catalog":
        return build_methylation_frontier_catalog(fixture).to_dict()
    if operation == "methylation-frontier-schema":
        return validate_methylation_frontier_schema(fixture).to_dict()
    if operation == "methylation-frontier-sources":
        return build_methylation_frontier_source_registry(fixture).to_dict()
    return run_methylation_frontier_pipeline(fixture).to_dict()


__all__ = ["run_methylation_frontier_operation"]
