"""Schema and boundary checks for the beta fixture and evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_beta_frontier_fixture_eval import CellContextBetaFrontierEvaluation
from .cell_context_beta_frontier_public_data import CellContextBetaFrontierFixture
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierSchemaCheck:
    check_id: str
    passed: bool
    detail: str
    observed: Any = None
    required: Any = None
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.check_id or not self.detail:
            raise ValidationError("beta schema check is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierSchemaReport:
    fixture_id: str
    checks: tuple[CellContextBetaFrontierSchemaCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.fixture_id or not self.checks:
            raise ValidationError("beta schema report is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_check_ids": list(self.failed_check_ids)}


def validate_cell_context_beta_frontier_schema(
    fixture: CellContextBetaFrontierFixture, evaluation: CellContextBetaFrontierEvaluation
) -> CellContextBetaFrontierSchemaReport:
    restricted = {"patient", "subject", "sample_id", "donor_id", "participant_id", "individual_id"}
    checks = (
        CellContextBetaFrontierSchemaCheck(
            "fixture-address",
            bool(fixture.content_address),
            "fixture has a content address",
            fixture.content_address,
            "non-empty",
        ),
        CellContextBetaFrontierSchemaCheck(
            "record-addresses",
            all(bool(item.content_address) for item in fixture.records),
            "records are content addressed",
            len(fixture.records),
            16,
        ),
        CellContextBetaFrontierSchemaCheck(
            "aggregate-keys",
            all(
                not restricted.intersection({str(key).lower() for key in item.payload})
                for item in fixture.records
            ),
            "payloads exclude subject-level keys",
            True,
            True,
        ),
        CellContextBetaFrontierSchemaCheck(
            "target-contexts",
            all("target_context_key" in item.payload for item in fixture.records),
            "every operation declares its target context",
            True,
            True,
        ),
        CellContextBetaFrontierSchemaCheck(
            "evaluation-alignment",
            len(evaluation.records) == len(fixture.records),
            "evaluation covers every fixture record",
            len(evaluation.records),
            len(fixture.records),
        ),
        CellContextBetaFrontierSchemaCheck(
            "expected-state-enumeration",
            all(
                item.record.expected_state.value == item.record.expected_state.value
                for item in evaluation.records
            ),
            "expected states use the closed enum",
            True,
            True,
        ),
        CellContextBetaFrontierSchemaCheck(
            "source-versions",
            all(
                item.adapter.measurements.get("source_versions") is not None
                for item in evaluation.records
            ),
            "source versions survive adapter execution",
            True,
            True,
        ),
    )
    return CellContextBetaFrontierSchemaReport(
        fixture.fixture_id, checks, all(item.passed for item in checks)
    )


__all__ = [
    "CellContextBetaFrontierSchemaCheck",
    "CellContextBetaFrontierSchemaReport",
    "validate_cell_context_beta_frontier_schema",
]
