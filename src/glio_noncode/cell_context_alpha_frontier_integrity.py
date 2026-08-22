"""Integrity checks for alpha fixture, sources, rows, and evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_alpha_frontier_fixture_eval import CellContextAlphaFrontierEvaluation
from .cell_context_alpha_frontier_public_data import CellContextAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierIntegrityCheck:
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
class CellContextAlphaFrontierIntegrityReport:
    checks: tuple[CellContextAlphaFrontierIntegrityCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_cell_context_alpha_frontier_integrity(
    fixture: CellContextAlphaFrontierFixture, evaluation: CellContextAlphaFrontierEvaluation
) -> CellContextAlphaFrontierIntegrityReport:
    checks = (
        CellContextAlphaFrontierIntegrityCheck(
            "fixture-address",
            bool(fixture.content_address),
            "fixture address exists",
            fixture.content_address,
            "non-empty",
        ),
        CellContextAlphaFrontierIntegrityCheck(
            "source-addresses",
            all(item.content_address for item in fixture.sources),
            "source addresses exist",
            True,
            True,
        ),
        CellContextAlphaFrontierIntegrityCheck(
            "record-addresses",
            all(item.content_address for item in fixture.records),
            "record addresses exist",
            True,
            True,
        ),
        CellContextAlphaFrontierIntegrityCheck(
            "evaluation-addresses",
            all(item.content_address for item in evaluation.records),
            "evaluation addresses exist",
            True,
            True,
        ),
        CellContextAlphaFrontierIntegrityCheck(
            "closed-count",
            len(fixture.records) == 16 and len(evaluation.records) == 16,
            (len(fixture.records), len(evaluation.records)),
            (16, 16),
            "counts remain closed",
        ),
        CellContextAlphaFrontierIntegrityCheck(
            "positive-controls",
            len(evaluation.positive_rows) == 4 and len(evaluation.control_rows) == 12,
            (len(evaluation.positive_rows), len(evaluation.control_rows)),
            (4, 12),
            "positive and control counts remain closed",
        ),
    )
    return CellContextAlphaFrontierIntegrityReport(checks, all(item.passed for item in checks))


__all__ = [
    "CellContextAlphaFrontierIntegrityCheck",
    "CellContextAlphaFrontierIntegrityReport",
    "evaluate_cell_context_alpha_frontier_integrity",
]
