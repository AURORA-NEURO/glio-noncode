"""Cross-module invariants for the methylation frontier package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .methylation_frontier_fixture_eval import MethylationFrontierEvaluation
from .methylation_frontier_public_data import (
    MethylationFrontierFixture,
    MethylationFrontierOperation,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class MethylationFrontierInvariant:
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
class MethylationFrontierInvariantReport:
    fixture_id: str
    invariants: tuple[MethylationFrontierInvariant, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.invariants:
            raise ValidationError("invariant report requires checks")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def failed_ids(self) -> tuple[str, ...]:
        return tuple(item.invariant_id for item in self.invariants if not item.passed)

    def by_category(self, category: str) -> tuple[MethylationFrontierInvariant, ...]:
        return tuple(item for item in self.invariants if item.category == category)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_ids": list(self.failed_ids)}


def _invariant(
    index: int, category: str, passed: bool, observed: Any, required: Any, detail: str
) -> MethylationFrontierInvariant:
    return MethylationFrontierInvariant(
        f"methylation-invariant-{index:03d}", category, passed, observed, required, detail
    )


def run_methylation_frontier_invariants(
    fixture: MethylationFrontierFixture,
    evaluation: MethylationFrontierEvaluation,
) -> MethylationFrontierInvariantReport:
    """Check count, operation balance, address, state, and control invariants."""

    addresses = tuple(item.adapter.content_address for item in evaluation.records)
    checks: list[MethylationFrontierInvariant] = [
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
            "context uses the six-part key",
        ),
        _invariant(
            3,
            "balance",
            len(fixture.records) == 16,
            len(fixture.records),
            16,
            "sixteen fixture records are present",
        ),
        _invariant(
            4,
            "balance",
            len(fixture.positive_records) == 4,
            len(fixture.positive_records),
            4,
            "four positive records are present",
        ),
        _invariant(
            5,
            "balance",
            len(fixture.control_records) == 12,
            len(fixture.control_records),
            12,
            "twelve control records are present",
        ),
        _invariant(
            6,
            "execution",
            len(evaluation.records) == len(fixture.records),
            len(evaluation.records),
            len(fixture.records),
            "every record is executed",
        ),
        _invariant(
            7,
            "execution",
            evaluation.state_match_count == 16,
            evaluation.state_match_count,
            16,
            "every state follows the fixture path",
        ),
        _invariant(
            8,
            "execution",
            evaluation.issue_match_count == 16,
            evaluation.issue_match_count,
            16,
            "every issue path is retained",
        ),
        _invariant(
            9,
            "address",
            len(set(addresses)) == len(addresses),
            len(set(addresses)),
            len(addresses),
            "every row result is distinct",
        ),
        _invariant(
            10,
            "address",
            all(address.startswith("sha256:") for address in addresses),
            len(addresses),
            len(addresses),
            "every row result is addressed",
        ),
        _invariant(
            11,
            "boundary",
            all(record.context_key == fixture.context_key for record in fixture.records),
            len(fixture.records),
            len(fixture.records),
            "all records use the locked context",
        ),
        _invariant(
            12,
            "boundary",
            fixture.evidence_boundary == "public_aggregate_non_patient",
            fixture.evidence_boundary,
            "public_aggregate_non_patient",
            "aggregate boundary is preserved",
        ),
        _invariant(
            13,
            "controls",
            any(
                item.observed_state.value == "invalid"
                for item in evaluation.records
                if item.role == "control"
            ),
            True,
            True,
            "invalid control path is covered",
        ),
        _invariant(
            14,
            "controls",
            any(
                item.observed_state.value == "partial"
                for item in evaluation.records
                if item.role == "control"
            ),
            True,
            True,
            "partial control path is covered",
        ),
        _invariant(
            15,
            "controls",
            any(
                item.observed_state.value == "out_of_domain"
                for item in evaluation.records
                if item.role == "control"
            ),
            True,
            True,
            "out-of-domain control path is covered",
        ),
        _invariant(
            16,
            "controls",
            any(
                item.observed_state.value == "abstained"
                for item in evaluation.records
                if item.role == "control"
            ),
            True,
            True,
            "abstention control path is covered",
        ),
    ]
    for index, operation in enumerate(MethylationFrontierOperation, start=17):
        rows = tuple(item for item in evaluation.records if item.adapter.operation is operation)
        checks.append(
            _invariant(
                index,
                "operation",
                len(rows) == 4,
                len(rows),
                4,
                f"{operation.value} has four records",
            )
        )
    return MethylationFrontierInvariantReport(
        fixture.fixture_id, tuple(checks), all(check.passed for check in checks)
    )


__all__ = [
    "MethylationFrontierInvariant",
    "MethylationFrontierInvariantReport",
    "run_methylation_frontier_invariants",
]
