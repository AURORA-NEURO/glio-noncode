"""CLI operations for the Domain 06 C09-C12 aggregate plane."""

from __future__ import annotations

from typing import Any

from .sequence_regulation_frontier_adapters import build_sequence_regulation_adapters
from .sequence_regulation_frontier_contracts import build_sequence_regulation_contracts
from .sequence_regulation_frontier_fixture_eval import evaluate_sequence_regulation_fixture
from .sequence_regulation_frontier_pipeline import run_sequence_regulation_frontier_pipeline
from .sequence_regulation_frontier_public_data import (
    audit_sequence_regulation_data,
    build_sequence_regulation_catalog,
    default_sequence_regulation_fixture,
)
from .sequence_regulation_frontier_replay import replay_sequence_regulation_evaluation
from .sequence_regulation_frontier_runtime import run_sequence_regulation_runtime

_OPERATIONS = {
    "sequence-regulation-fixture",
    "sequence-regulation-data",
    "sequence-regulation-evaluate",
    "sequence-regulation-replay",
    "sequence-regulation-quality",
    "sequence-regulation-contracts",
    "sequence-regulation-adapters",
    "sequence-regulation-catalog",
    "run-sequence-regulation-pipeline",
}


def run_sequence_regulation_operation(operation: str) -> dict[str, Any]:
    """Run one named aggregate operation and return a JSON-compatible object."""

    if operation not in _OPERATIONS:
        raise ValueError(f"unsupported sequence-regulation operation: {operation}")
    fixture = default_sequence_regulation_fixture()
    if operation == "sequence-regulation-fixture":
        return fixture.to_dict(include_payload=True)
    if operation == "sequence-regulation-data":
        return audit_sequence_regulation_data(fixture).to_dict()
    if operation == "sequence-regulation-evaluate":
        return evaluate_sequence_regulation_fixture(fixture).to_dict()
    if operation == "sequence-regulation-replay":
        return replay_sequence_regulation_evaluation(fixture).to_dict()
    if operation == "sequence-regulation-quality":
        return run_sequence_regulation_runtime(fixture=fixture).quality.to_dict()
    if operation == "sequence-regulation-contracts":
        return build_sequence_regulation_contracts().to_dict()
    if operation == "sequence-regulation-adapters":
        return build_sequence_regulation_adapters().to_dict()
    if operation == "sequence-regulation-catalog":
        return build_sequence_regulation_catalog(fixture).to_dict()
    return run_sequence_regulation_frontier_pipeline(fixture).to_dict()


__all__ = ["run_sequence_regulation_operation"]
