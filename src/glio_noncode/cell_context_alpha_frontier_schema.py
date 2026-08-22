"""Schema checks for the C09-C12 aggregate fixture and execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_alpha_frontier_fixture_eval import CellContextAlphaFrontierEvaluation
from .cell_context_alpha_frontier_public_data import CellContextAlphaFrontierFixture
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierSchemaCheck:
    check_id: str
    passed: bool
    detail: str
    observed: Any = None
    required: Any = None
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.check_id or not self.detail:
            raise ValidationError("alpha schema check is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextAlphaFrontierSchemaReport:
    fixture_id: str
    checks: tuple[CellContextAlphaFrontierSchemaCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.fixture_id or not self.checks:
            raise ValidationError("alpha schema report is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_check_ids": list(self.failed_check_ids)}


def validate_cell_context_alpha_frontier_schema(
    fixture: CellContextAlphaFrontierFixture, evaluation: CellContextAlphaFrontierEvaluation
) -> CellContextAlphaFrontierSchemaReport:
    restricted = {"patient", "subject", "sample_id", "donor_id", "participant_id", "individual_id"}
    checks = (
        CellContextAlphaFrontierSchemaCheck(
            "fixture-address",
            bool(fixture.content_address),
            "fixture has an address",
            fixture.content_address,
            "non-empty",
        ),
        CellContextAlphaFrontierSchemaCheck(
            "record-addresses",
            all(item.content_address for item in fixture.records),
            "records have addresses",
            True,
            True,
        ),
        CellContextAlphaFrontierSchemaCheck(
            "aggregate-payloads",
            all(
                not restricted.intersection({str(key).lower() for key in item.payload})
                for item in fixture.records
            ),
            "payloads have no subject-level keys",
            True,
            True,
        ),
        CellContextAlphaFrontierSchemaCheck(
            "target-contexts",
            all(item.payload.get("target_context_key") for item in fixture.records),
            "target context is declared",
            True,
            True,
        ),
        CellContextAlphaFrontierSchemaCheck(
            "evaluation-coverage",
            len(evaluation.records) == len(fixture.records),
            "evaluation covers fixture records",
            len(evaluation.records),
            len(fixture.records),
        ),
        CellContextAlphaFrontierSchemaCheck(
            "issue-retention",
            all(item.adapter.issue_codes is not None for item in evaluation.records),
            "adapter issue tuples are retained",
            True,
            True,
        ),
        CellContextAlphaFrontierSchemaCheck(
            "source-version-retention",
            all(item.adapter.measurements.get("source_versions") for item in evaluation.records),
            "source versions are retained",
            True,
            True,
        ),
    )
    return CellContextAlphaFrontierSchemaReport(
        fixture.fixture_id, checks, all(item.passed for item in checks)
    )


__all__ = [
    "CellContextAlphaFrontierSchemaCheck",
    "CellContextAlphaFrontierSchemaReport",
    "validate_cell_context_alpha_frontier_schema",
]
