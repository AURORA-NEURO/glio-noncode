"""Invariant checks across records, operations, sources, and states."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_beta_frontier_fixture_eval import CellContextBetaFrontierEvaluation
from .cell_context_beta_frontier_public_data import CellContextBetaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierInvariant:
    invariant_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierInvariantReport:
    invariants: tuple[CellContextBetaFrontierInvariant, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def failed_ids(self) -> tuple[str, ...]:
        return tuple(item.invariant_id for item in self.invariants if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_ids": list(self.failed_ids)}


def run_cell_context_beta_frontier_invariants(
    fixture: CellContextBetaFrontierFixture, evaluation: CellContextBetaFrontierEvaluation
) -> CellContextBetaFrontierInvariantReport:
    invariants = (
        CellContextBetaFrontierInvariant(
            "record-addresses",
            all(item.content_address for item in fixture.records),
            True,
            True,
            "records are addressed",
        ),
        CellContextBetaFrontierInvariant(
            "unique-records",
            len({item.record_id for item in fixture.records}) == len(fixture.records),
            len({item.record_id for item in fixture.records}),
            len(fixture.records),
            "record identifiers are unique",
        ),
        CellContextBetaFrontierInvariant(
            "four-operations",
            len({item.operation for item in fixture.records}) == 4,
            len({item.operation for item in fixture.records}),
            4,
            "all prior families are present",
        ),
        CellContextBetaFrontierInvariant(
            "sixteen-results",
            len(evaluation.records) == 16,
            len(evaluation.records),
            16,
            "all fixture records executed",
        ),
        CellContextBetaFrontierInvariant(
            "state-closure",
            all(item.observed_state for item in evaluation.records),
            True,
            True,
            "every result has a closed state",
        ),
        CellContextBetaFrontierInvariant(
            "source-closure",
            all(item.record.source_ids for item in evaluation.records),
            True,
            True,
            "every record has source receipt IDs",
        ),
    )
    return CellContextBetaFrontierInvariantReport(
        invariants, all(item.passed for item in invariants)
    )


__all__ = [
    "CellContextBetaFrontierInvariant",
    "CellContextBetaFrontierInvariantReport",
    "run_cell_context_beta_frontier_invariants",
]
