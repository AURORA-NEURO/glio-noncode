"""Cross-surface invariants for a context track run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_context_frontier_fixture_eval import ChromatinContextFrontierEvaluation
from .chromatin_context_frontier_public_data import ChromatinContextFrontierFixture
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierInvariant:
    invariant_id: str
    passed: bool
    detail: str
    observed: Any = None
    required: Any = None
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.invariant_id or not self.detail:
            raise ValidationError("invariant is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierInvariantReport:
    invariants: tuple[ChromatinContextFrontierInvariant, ...]
    accepted: bool
    failed_ids: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.invariants:
            raise ValidationError("invariant report is empty")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def run_chromatin_context_frontier_invariants(
    fixture: ChromatinContextFrontierFixture,
    evaluation: ChromatinContextFrontierEvaluation,
) -> ChromatinContextFrontierInvariantReport:
    observed_operations = {item.operation for item in evaluation.records}
    expected_ids = {item.record_id for item in fixture.records}
    observed_ids = {item.record_id for item in evaluation.records}
    invariants = (
        ChromatinContextFrontierInvariant(
            "one_result_per_record",
            len(evaluation.records) == len(fixture.records),
            "one result exists per fixture row",
            len(evaluation.records),
            len(fixture.records),
        ),
        ChromatinContextFrontierInvariant(
            "unique_record_ids",
            len(observed_ids) == len(evaluation.records),
            "result IDs are unique",
        ),
        ChromatinContextFrontierInvariant(
            "fixture_id_alignment",
            observed_ids == expected_ids,
            "result IDs align with fixture IDs",
        ),
        ChromatinContextFrontierInvariant(
            "operation_coverage",
            len(observed_operations) == 4,
            "four operations are represented",
            len(observed_operations),
            4,
        ),
        ChromatinContextFrontierInvariant(
            "positive_count", len(evaluation.positive_rows) == 4, "four positive rows are retained"
        ),
        ChromatinContextFrontierInvariant(
            "control_count", len(evaluation.control_rows) == 12, "twelve controls are retained"
        ),
        ChromatinContextFrontierInvariant(
            "content_receipts",
            all(item.adapter.content_address.startswith("sha256:") for item in evaluation.records),
            "adapter outputs are content addressed",
        ),
        ChromatinContextFrontierInvariant(
            "uncertainty_paths",
            any(
                item.observed_state in {"ambiguous", "partial", "abstained"}
                for item in evaluation.control_rows
            ),
            "uncertainty paths remain observable",
        ),
        ChromatinContextFrontierInvariant(
            "foreign_path",
            any(item.observed_state == "out_of_domain" for item in evaluation.control_rows),
            "foreign context path remains observable",
        ),
        ChromatinContextFrontierInvariant(
            "positive_paths",
            all(item.observed_state == "supported" for item in evaluation.positive_rows),
            "positive rows are supported",
        ),
    )
    failed = tuple(item.invariant_id for item in invariants if not item.passed)
    return ChromatinContextFrontierInvariantReport(invariants, not failed, failed)


__all__ = [
    "ChromatinContextFrontierInvariant",
    "ChromatinContextFrontierInvariantReport",
    "run_chromatin_context_frontier_invariants",
]
