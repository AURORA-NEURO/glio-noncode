"""Cross-surface invariants for the Domain 08 runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_frontier_fixture_eval import CellContextFrontierEvaluation
from .cell_context_frontier_public_data import CellContextFrontierFixture
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierInvariant:
    invariant_id: str
    passed: bool
    detail: str
    observed: Any = None
    required: Any = None
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.invariant_id or not self.detail:
            raise ValidationError("cell invariant is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextFrontierInvariantReport:
    invariants: tuple[CellContextFrontierInvariant, ...]
    accepted: bool
    failed_ids: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.invariants:
            raise ValidationError("cell invariant report is empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def run_cell_context_frontier_invariants(
    fixture: CellContextFrontierFixture, evaluation: CellContextFrontierEvaluation
) -> CellContextFrontierInvariantReport:
    fixture_ids = {item.record_id for item in fixture.records}
    result_ids = {item.record_id for item in evaluation.records}
    checks = (
        CellContextFrontierInvariant(
            "one_result_per_record",
            len(result_ids) == len(fixture_ids) == 16,
            "one result exists for each fixture row",
        ),
        CellContextFrontierInvariant(
            "record_id_alignment", result_ids == fixture_ids, "result IDs align with fixture IDs"
        ),
        CellContextFrontierInvariant(
            "operation_coverage",
            len({item.operation for item in evaluation.records}) == 4,
            "all four operations execute",
        ),
        CellContextFrontierInvariant(
            "positive_count", len(evaluation.positive_rows) == 4, "four positive rows remain"
        ),
        CellContextFrontierInvariant(
            "control_count", len(evaluation.control_rows) == 12, "twelve control rows remain"
        ),
        CellContextFrontierInvariant(
            "positive_support",
            all(item.observed_state == "supported" for item in evaluation.positive_rows),
            "positive rows support",
        ),
        CellContextFrontierInvariant(
            "ambiguity_path",
            any(item.observed_state == "ambiguous" for item in evaluation.control_rows),
            "ambiguous candidates remain visible",
        ),
        CellContextFrontierInvariant(
            "contradiction_path",
            any(item.observed_state == "contradictory" for item in evaluation.control_rows),
            "contradictory age path remains visible",
        ),
        CellContextFrontierInvariant(
            "abstention_path",
            any(item.observed_state == "abstained" for item in evaluation.control_rows),
            "missing molecular state abstains",
        ),
        CellContextFrontierInvariant(
            "receipt_path",
            all(item.adapter.content_address.startswith("sha256:") for item in evaluation.records),
            "all outputs have receipts",
        ),
        CellContextFrontierInvariant(
            "foreign_path",
            any(item.observed_state == "out_of_domain" for item in evaluation.control_rows),
            "foreign context is refused",
        ),
        CellContextFrontierInvariant(
            "limitations_path",
            all(item.adapter.warnings for item in evaluation.records),
            "limitations are present on every result",
        ),
    )
    failed = tuple(item.invariant_id for item in checks if not item.passed)
    return CellContextFrontierInvariantReport(checks, not failed, failed)


__all__ = [
    "CellContextFrontierInvariant",
    "CellContextFrontierInvariantReport",
    "run_cell_context_frontier_invariants",
]
