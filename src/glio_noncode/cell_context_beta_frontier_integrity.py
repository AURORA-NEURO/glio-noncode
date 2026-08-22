"""Integrity checks for immutable addresses, row counts, and fixture coverage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_beta_frontier_fixture_eval import CellContextBetaFrontierEvaluation
from .cell_context_beta_frontier_public_data import CellContextBetaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierIntegrityCheck:
    check_id: str
    passed: bool
    detail: str
    observed: Any
    required: Any
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierIntegrityReport:
    checks: tuple[CellContextBetaFrontierIntegrityCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def failed_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_ids": list(self.failed_ids)}


def evaluate_cell_context_beta_frontier_integrity(
    fixture: CellContextBetaFrontierFixture, evaluation: CellContextBetaFrontierEvaluation
) -> CellContextBetaFrontierIntegrityReport:
    checks = (
        CellContextBetaFrontierIntegrityCheck(
            "fixture-address",
            bool(fixture.content_address),
            "fixture address exists",
            fixture.content_address,
            "non-empty",
        ),
        CellContextBetaFrontierIntegrityCheck(
            "source-addresses",
            all(item.content_address for item in fixture.sources),
            "source addresses exist",
            True,
            True,
        ),
        CellContextBetaFrontierIntegrityCheck(
            "record-addresses",
            all(item.content_address for item in fixture.records),
            "record addresses exist",
            True,
            True,
        ),
        CellContextBetaFrontierIntegrityCheck(
            "evaluation-addresses",
            all(item.content_address for item in evaluation.records),
            "evaluation addresses exist",
            True,
            True,
        ),
        CellContextBetaFrontierIntegrityCheck(
            "closed-count",
            len(fixture.records) == 16 and len(evaluation.records) == 16,
            (len(fixture.records), len(evaluation.records)),
            (16, 16),
            "fixture and evaluation counts match",
        ),
        CellContextBetaFrontierIntegrityCheck(
            "positive-controls",
            len(evaluation.positive_rows) == 4 and len(evaluation.control_rows) == 12,
            (len(evaluation.positive_rows), len(evaluation.control_rows)),
            (4, 12),
            "positive and control counts match",
        ),
    )
    return CellContextBetaFrontierIntegrityReport(checks, all(item.passed for item in checks))


__all__ = [
    "CellContextBetaFrontierIntegrityCheck",
    "CellContextBetaFrontierIntegrityReport",
    "evaluate_cell_context_beta_frontier_integrity",
]
