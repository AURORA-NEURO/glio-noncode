"""Invariant checks that are cheap enough to run on every local command."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierEvaluation, LifecycleBetaFrontierFixture
from .lifecycle_beta_frontier_source_registry import LifecycleBetaFrontierSourceRegistry
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierInvariant:
    invariant_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierInvariantReport:
    fixture_id: str
    invariants: tuple[LifecycleBetaFrontierInvariant, ...]
    accepted: bool
    failed_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def run_lifecycle_beta_frontier_invariants(fixture: LifecycleBetaFrontierFixture, evaluation: LifecycleBetaFrontierEvaluation, registry: LifecycleBetaFrontierSourceRegistry) -> LifecycleBetaFrontierInvariantReport:
    values = (
        ("source-registry", registry.accepted, True, registry.accepted, "source IDs resolve"),
        ("source-count", len(fixture.sources), 9, len(fixture.sources) == 9, "source count is fixed"),
        ("record-count", len(fixture.records), 32, len(fixture.records) == 32, "record count is fixed"),
        ("execution-count", len(evaluation.executions), 32, len(evaluation.executions) == 32, "every record executes"),
        ("positive-count", sum(item.accepted for item in evaluation.executions), 8, sum(item.accepted for item in evaluation.executions) == 8, "one positive per operation"),
        ("control-count", sum(item.role.value == "control" for item in evaluation.executions), 24, sum(item.role.value == "control" for item in evaluation.executions) == 24, "three controls per operation"),
        ("context-closure", all(item.context_key == fixture.context_key for item in fixture.records), True, all(item.context_key == fixture.context_key for item in fixture.records), "fixture context is exact"),
        ("address-closure", all(item.content_address.startswith("sha256:") for item in evaluation.executions), True, all(item.content_address.startswith("sha256:") for item in evaluation.executions), "execution addresses are closed"),
    )
    rows = []
    for invariant_id, observed, required, passed, detail in values:
        body = {"invariant_id": invariant_id, "passed": passed, "observed": observed, "required": required, "detail": detail}
        rows.append(LifecycleBetaFrontierInvariant(**body, content_address=content_hash(body)))
    failed = tuple(item.invariant_id for item in rows if not item.passed)
    return LifecycleBetaFrontierInvariantReport(fixture.fixture_id, tuple(rows), not failed, failed, content_hash({"invariants": tuple(rows), "failed": failed}))


__all__ = ["LifecycleBetaFrontierInvariant", "LifecycleBetaFrontierInvariantReport", "run_lifecycle_beta_frontier_invariants"]
