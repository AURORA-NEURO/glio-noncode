"""Schema, exact-context, and aggregate-boundary validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_frontier_fixture_eval import CellContextFrontierEvaluation
from .cell_context_frontier_public_data import (
    CELL_CONTEXT_FRONTIER_BOUNDARY,
    CELL_CONTEXT_FRONTIER_CONTEXT_KEY,
    CellContextFrontierFixture,
)
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierSchemaCheck:
    check_id: str
    passed: bool
    detail: str
    observed: Any = None
    required: Any = None
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.check_id or not self.detail:
            raise ValidationError("cell schema check is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextFrontierSchemaReport:
    checks: tuple[CellContextFrontierSchemaCheck, ...]
    accepted: bool
    failed_check_ids: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.checks:
            raise ValidationError("cell schema report requires checks")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def validate_cell_context_frontier_schema(
    fixture: CellContextFrontierFixture, evaluation: CellContextFrontierEvaluation | None = None
) -> CellContextFrontierSchemaReport:
    checks = [
        CellContextFrontierSchemaCheck(
            "fixture_context",
            fixture.context_key == CELL_CONTEXT_FRONTIER_CONTEXT_KEY,
            "fixture uses the exact six-part context key",
            fixture.context_key,
            CELL_CONTEXT_FRONTIER_CONTEXT_KEY,
        ),
        CellContextFrontierSchemaCheck(
            "aggregate_boundary",
            fixture.evidence_boundary == CELL_CONTEXT_FRONTIER_BOUNDARY,
            "fixture remains aggregate-only",
            fixture.evidence_boundary,
            CELL_CONTEXT_FRONTIER_BOUNDARY,
        ),
        CellContextFrontierSchemaCheck(
            "source_https",
            all(item.uri.startswith("https://") for item in fixture.sources),
            "all source receipts use HTTPS",
        ),
        CellContextFrontierSchemaCheck(
            "source_scope",
            all(item.public_aggregate for item in fixture.sources),
            "all source receipts declare public aggregate scope",
        ),
        CellContextFrontierSchemaCheck(
            "record_context",
            all(item.context_key == fixture.context_key for item in fixture.records),
            "all records retain fixture context",
        ),
        CellContextFrontierSchemaCheck(
            "payload_shape",
            all(bool(item.payload.get("observation_text")) for item in fixture.records),
            "all records carry observation text",
        ),
        CellContextFrontierSchemaCheck(
            "record_addresses",
            all(item.content_address.startswith("sha256:") for item in fixture.records),
            "all records are content addressed",
        ),
        CellContextFrontierSchemaCheck(
            "fixture_address",
            fixture.content_address.startswith("sha256:"),
            "fixture is content addressed",
        ),
    ]
    if evaluation is not None:
        checks.append(
            CellContextFrontierSchemaCheck(
                "evaluation_shape",
                len(evaluation.records) == len(fixture.records),
                "evaluation has one row per fixture record",
                len(evaluation.records),
                len(fixture.records),
            )
        )
    failed = tuple(item.check_id for item in checks if not item.passed)
    return CellContextFrontierSchemaReport(tuple(checks), not failed, failed)


__all__ = [
    "CellContextFrontierSchemaCheck",
    "CellContextFrontierSchemaReport",
    "validate_cell_context_frontier_schema",
]
