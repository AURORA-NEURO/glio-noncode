"""Cross-module invariants for the chromatin-alpha frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_alpha_frontier_fixture_eval import ChromatinAlphaFrontierEvaluation
from .chromatin_alpha_frontier_public_data import (
    ChromatinAlphaFrontierFixture,
    ChromatinAlphaFrontierOperation,
)
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierInvariant:
    invariant_id: str
    category: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.invariant_id or not self.category or not self.detail:
            raise ValidationError("invariant is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierInvariantReport:
    fixture_id: str
    invariants: tuple[ChromatinAlphaFrontierInvariant, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.fixture_id or not self.invariants:
            raise ValidationError("invariant report is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def failed_ids(self) -> tuple[str, ...]:
        return tuple(item.invariant_id for item in self.invariants if not item.passed)

    def by_category(self, category: str) -> tuple[ChromatinAlphaFrontierInvariant, ...]:
        return tuple(item for item in self.invariants if item.category == category)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_ids": list(self.failed_ids)}


def _invariant(
    index: int, category: str, passed: bool, observed: Any, required: Any, detail: str
) -> ChromatinAlphaFrontierInvariant:
    return ChromatinAlphaFrontierInvariant(
        f"chromatin-alpha-invariant-{index:03d}", category, passed, observed, required, detail
    )


def run_chromatin_alpha_frontier_invariants(
    fixture: ChromatinAlphaFrontierFixture,
    evaluation: ChromatinAlphaFrontierEvaluation,
) -> ChromatinAlphaFrontierInvariantReport:
    addresses = tuple(item.adapter.content_address for item in evaluation.records)
    values: list[ChromatinAlphaFrontierInvariant] = [
        _invariant(
            1,
            "identity",
            bool(fixture.fixture_id),
            fixture.fixture_id,
            "fixture ID",
            "fixture has identity",
        ),
        _invariant(
            2,
            "identity",
            fixture.context_key.count("|") == 5,
            fixture.context_key,
            "six context components",
            "context uses six components",
        ),
        _invariant(
            3,
            "balance",
            len(fixture.records) == 16,
            len(fixture.records),
            16,
            "sixteen rows are retained",
        ),
        _invariant(
            4,
            "balance",
            len(fixture.positive_records) == 4,
            len(fixture.positive_records),
            4,
            "four positive rows are retained",
        ),
        _invariant(
            5,
            "balance",
            len(fixture.control_records) == 12,
            len(fixture.control_records),
            12,
            "twelve control rows are retained",
        ),
        _invariant(
            6,
            "execution",
            len(evaluation.records) == len(fixture.records),
            len(evaluation.records),
            len(fixture.records),
            "every row executes",
        ),
        _invariant(
            7,
            "execution",
            evaluation.state_match_count == 16,
            evaluation.state_match_count,
            16,
            "all state expectations match",
        ),
        _invariant(
            8,
            "execution",
            evaluation.issue_match_count == 16,
            evaluation.issue_match_count,
            16,
            "all issue floors match",
        ),
        _invariant(
            9,
            "address",
            len(set(addresses)) == len(addresses),
            len(set(addresses)),
            len(addresses),
            "result addresses are distinct",
        ),
        _invariant(
            10,
            "address",
            all(address.startswith("sha256:") for address in addresses),
            len(addresses),
            len(addresses),
            "result addresses are present",
        ),
        _invariant(
            11,
            "boundary",
            fixture.evidence_boundary == "public_aggregate_non_patient",
            fixture.evidence_boundary,
            "public_aggregate_non_patient",
            "aggregate boundary is retained",
        ),
        _invariant(
            12,
            "boundary",
            all(record.context_key == fixture.context_key for record in fixture.records),
            len(fixture.records),
            len(fixture.records),
            "record contexts are locked",
        ),
        _invariant(
            13,
            "controls",
            any(
                item.observed_state == "ambiguous"
                for item in evaluation.records
                if item.role == "control"
            ),
            True,
            True,
            "ambiguous control is present",
        ),
        _invariant(
            14,
            "controls",
            any(
                item.observed_state == "out_of_domain"
                for item in evaluation.records
                if item.role == "control"
            ),
            True,
            True,
            "out-of-domain control is present",
        ),
        _invariant(
            15,
            "controls",
            any(
                item.observed_state == "partial"
                for item in evaluation.records
                if item.role == "control"
            ),
            True,
            True,
            "partial control is present",
        ),
        _invariant(
            16,
            "sources",
            len(fixture.sources) == 5,
            len(fixture.sources),
            5,
            "five public sources are declared",
        ),
    ]
    for index, operation in enumerate(ChromatinAlphaFrontierOperation, start=17):
        rows = tuple(item for item in evaluation.records if item.adapter.operation is operation)
        values.append(
            _invariant(
                index, "operation", len(rows) == 4, len(rows), 4, f"{operation.value} has four rows"
            )
        )
    return ChromatinAlphaFrontierInvariantReport(
        fixture.fixture_id, tuple(values), all(item.passed for item in values)
    )


__all__ = [
    "ChromatinAlphaFrontierInvariant",
    "ChromatinAlphaFrontierInvariantReport",
    "run_chromatin_alpha_frontier_invariants",
]
