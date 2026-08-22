"""CLI operations for the Domain 07 C09-C12 aggregate plane."""

from __future__ import annotations

from typing import Any

from .chromatin_alpha_frontier_adapters import build_chromatin_alpha_frontier_adapters
from .chromatin_alpha_frontier_contracts import build_chromatin_alpha_frontier_contracts
from .chromatin_alpha_frontier_fixture_eval import evaluate_chromatin_alpha_frontier_fixture
from .chromatin_alpha_frontier_pipeline import run_chromatin_alpha_frontier_pipeline
from .chromatin_alpha_frontier_public_data import (
    audit_chromatin_alpha_frontier_data,
    build_chromatin_alpha_frontier_catalog,
    default_chromatin_alpha_frontier_fixture,
)
from .chromatin_alpha_frontier_replay import replay_chromatin_alpha_frontier
from .chromatin_alpha_frontier_runtime import run_chromatin_alpha_frontier_runtime
from .chromatin_alpha_frontier_schema import (
    chromatin_alpha_frontier_schema_manifest,
    validate_chromatin_alpha_frontier_schema,
)
from .chromatin_alpha_frontier_source_registry import build_chromatin_alpha_frontier_source_registry

_OPERATIONS = {
    "chromatin-alpha-frontier-fixture",
    "chromatin-alpha-frontier-data",
    "chromatin-alpha-frontier-evaluate",
    "chromatin-alpha-frontier-replay",
    "chromatin-alpha-frontier-quality",
    "chromatin-alpha-frontier-contracts",
    "chromatin-alpha-frontier-adapters",
    "chromatin-alpha-frontier-catalog",
    "chromatin-alpha-frontier-schema",
    "chromatin-alpha-frontier-sources",
    "run-chromatin-alpha-frontier-pipeline",
}


def run_chromatin_alpha_frontier_operation(operation: str) -> dict[str, Any]:
    if operation not in _OPERATIONS:
        raise ValueError(f"unsupported chromatin-alpha-frontier operation: {operation}")
    fixture = default_chromatin_alpha_frontier_fixture()
    if operation == "chromatin-alpha-frontier-fixture":
        return fixture.to_dict(include_payload=True)
    if operation == "chromatin-alpha-frontier-data":
        return audit_chromatin_alpha_frontier_data(fixture).to_dict()
    if operation == "chromatin-alpha-frontier-evaluate":
        return evaluate_chromatin_alpha_frontier_fixture(fixture).to_dict()
    if operation == "chromatin-alpha-frontier-replay":
        return replay_chromatin_alpha_frontier(fixture).to_dict()
    if operation == "chromatin-alpha-frontier-quality":
        return run_chromatin_alpha_frontier_runtime(fixture=fixture).quality.to_dict()
    if operation == "chromatin-alpha-frontier-contracts":
        return build_chromatin_alpha_frontier_contracts().to_dict()
    if operation == "chromatin-alpha-frontier-adapters":
        return build_chromatin_alpha_frontier_adapters().to_dict()
    if operation == "chromatin-alpha-frontier-catalog":
        return build_chromatin_alpha_frontier_catalog(fixture).to_dict()
    if operation == "chromatin-alpha-frontier-schema":
        return validate_chromatin_alpha_frontier_schema(
            fixture, evaluate_chromatin_alpha_frontier_fixture(fixture)
        ).to_dict() | {"manifest": chromatin_alpha_frontier_schema_manifest()}
    if operation == "chromatin-alpha-frontier-sources":
        return build_chromatin_alpha_frontier_source_registry(fixture).to_dict()
    return run_chromatin_alpha_frontier_pipeline(fixture).to_dict()


__all__ = ["run_chromatin_alpha_frontier_operation"]
