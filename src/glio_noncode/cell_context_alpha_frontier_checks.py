"""Cross-surface invariants for context-alpha release."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_alpha_frontier_fixture_eval import CellContextAlphaFrontierEvaluation
from .cell_context_alpha_frontier_public_data import CellContextAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierInvariant:
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
class CellContextAlphaFrontierInvariantReport:
    invariants: tuple[CellContextAlphaFrontierInvariant, ...]
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


def run_cell_context_alpha_frontier_invariants(
    fixture: CellContextAlphaFrontierFixture, evaluation: CellContextAlphaFrontierEvaluation
) -> CellContextAlphaFrontierInvariantReport:
    invariants = (
        CellContextAlphaFrontierInvariant(
            "record-addresses",
            all(item.content_address for item in fixture.records),
            True,
            True,
            "records are addressed",
        ),
        CellContextAlphaFrontierInvariant(
            "unique-records",
            len({item.record_id for item in fixture.records}) == 16,
            len({item.record_id for item in fixture.records}),
            16,
            "record IDs are unique",
        ),
        CellContextAlphaFrontierInvariant(
            "operation-count",
            len({item.operation for item in fixture.records}) == 4,
            len({item.operation for item in fixture.records}),
            4,
            "four operations are covered",
        ),
        CellContextAlphaFrontierInvariant(
            "evaluation-count",
            len(evaluation.records) == 16,
            len(evaluation.records),
            16,
            "all rows executed",
        ),
        CellContextAlphaFrontierInvariant(
            "state-closure",
            all(item.observed_state for item in evaluation.records),
            True,
            True,
            "states are non-empty",
        ),
        CellContextAlphaFrontierInvariant(
            "source-closure",
            all(item.record.source_ids for item in evaluation.records),
            True,
            True,
            "source IDs are attached",
        ),
    )
    return CellContextAlphaFrontierInvariantReport(
        invariants, all(item.passed for item in invariants)
    )


__all__ = [
    "CellContextAlphaFrontierInvariant",
    "CellContextAlphaFrontierInvariantReport",
    "run_cell_context_alpha_frontier_invariants",
]
