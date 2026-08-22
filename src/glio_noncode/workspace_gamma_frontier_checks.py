"""Cross-record invariants for the collaboration frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_gamma_frontier_fixture_eval import GammaFrontierEvaluation
from .workspace_gamma_frontier_public_data import GammaFrontierFixture, GammaFrontierOperation


@dataclass(frozen=True, slots=True)
class GammaFrontierInvariant:
    """Named invariant with a stable priority."""

    invariant_id: str
    priority: int
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.invariant_id, "invariant_id")
        require_non_empty(self.detail, "detail")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierInvariantResult:
    """Observed result for one invariant."""

    invariant_id: str
    passed: bool
    observed: Any
    required: Any
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierInvariantReport:
    """Invariant report with execution lookup helpers."""

    fixture_id: str
    invariants: tuple[GammaFrontierInvariant, ...]
    results: tuple[GammaFrontierInvariantResult, ...]
    accepted: bool
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.results)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed_count": self.passed_count}


def default_gamma_frontier_invariants() -> tuple[GammaFrontierInvariant, ...]:
    """Return release-critical invariant definitions."""

    values = (
        ("four-operation-coverage", 1, "all four surfaces occur"),
        ("positive-control-balance", 1, "each operation has a positive and controls"),
        ("addressed-executions", 1, "every execution has a content address"),
        ("explicit-states", 2, "every execution has a state"),
        ("control-issues-visible", 2, "controls preserve issue evidence"),
        ("no-duplicate-records", 1, "record identifiers remain unique"),
    )
    return tuple(
        GammaFrontierInvariant(
            invariant_id=item[0],
            priority=item[1],
            detail=item[2],
            content_address=content_hash(item, prefix="invariant"),
        )
        for item in values
    )


def _result(
    invariant: GammaFrontierInvariant, passed: bool, observed: Any, required: Any
) -> GammaFrontierInvariantResult:
    body = {
        "invariant_id": invariant.invariant_id,
        "passed": passed,
        "observed": observed,
        "required": required,
    }
    return GammaFrontierInvariantResult(
        **body, content_address=content_hash(body, prefix="invariant-result")
    )


def run_gamma_frontier_invariants(
    fixture: GammaFrontierFixture, evaluation: GammaFrontierEvaluation
) -> GammaFrontierInvariantReport:
    """Evaluate all cross-record invariants."""

    invariants = default_gamma_frontier_invariants()
    operations = {item.operation for item in fixture.records}
    per_operation = {
        operation: tuple(item for item in fixture.records if item.operation is operation)
        for operation in GammaFrontierOperation
    }
    values = {
        "four-operation-coverage": (
            operations == set(GammaFrontierOperation),
            set(operations),
            set(GammaFrontierOperation),
        ),
        "positive-control-balance": (
            all(
                any(item.role.value == "positive" for item in rows)
                and sum(item.role.value == "control" for item in rows) >= 3
                for rows in per_operation.values()
            ),
            {key.value: len(value) for key, value in per_operation.items()},
            "positive+3 controls per operation",
        ),
        "addressed-executions": (
            all(item.content_address.startswith("sha256:") for item in evaluation.executions),
            len(evaluation.executions),
            len(evaluation.executions),
        ),
        "explicit-states": (
            all(bool(item.state) for item in evaluation.executions),
            tuple(item.state for item in evaluation.executions),
            "non-empty state",
        ),
        "control-issues-visible": (
            all(item.issue_codes for item in evaluation.executions if item.role.value == "control"),
            tuple(
                item.record_id
                for item in evaluation.executions
                if not item.issue_codes and item.role.value == "control"
            ),
            "every control has issue evidence",
        ),
        "no-duplicate-records": (
            len({item.record_id for item in fixture.records}) == len(fixture.records),
            len(fixture.records),
            len({item.record_id for item in fixture.records}),
        ),
    }
    results = tuple(_result(invariant, *values[invariant.invariant_id]) for invariant in invariants)
    body = {
        "fixture_id": fixture.fixture_id,
        "invariants": invariants,
        "results": results,
        "accepted": all(item.passed for item in results),
    }
    return GammaFrontierInvariantReport(
        **body, content_address=content_hash(body, prefix="invariants")
    )


def gamma_frontier_observation_map(
    evaluation: GammaFrontierEvaluation,
) -> dict[str, dict[str, Any]]:
    """Expose compact row observations for diagnostics."""

    return {
        item.record_id: {
            "operation": item.operation.value,
            "role": item.role.value,
            "state": item.state,
            "issue_codes": item.issue_codes,
            "address": item.content_address,
        }
        for item in evaluation.executions
    }


__all__ = [
    "GammaFrontierInvariant",
    "GammaFrontierInvariantReport",
    "GammaFrontierInvariantResult",
    "default_gamma_frontier_invariants",
    "gamma_frontier_observation_map",
    "run_gamma_frontier_invariants",
]
