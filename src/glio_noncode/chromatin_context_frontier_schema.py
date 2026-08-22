"""Schema and boundary checks for public context track records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_context_frontier_fixture_eval import ChromatinContextFrontierEvaluation
from .chromatin_context_frontier_public_data import (
    CHROMATIN_CONTEXT_FRONTIER_BOUNDARY,
    CHROMATIN_CONTEXT_FRONTIER_CONTEXT_KEY,
    ChromatinContextFrontierFixture,
)
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierSchemaCheck:
    check_id: str
    passed: bool
    detail: str
    observed: Any = None
    required: Any = None
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.check_id or not self.detail:
            raise ValidationError("schema check is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierSchemaReport:
    checks: tuple[ChromatinContextFrontierSchemaCheck, ...]
    accepted: bool
    failed_check_ids: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.checks:
            raise ValidationError("schema report requires checks")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def validate_chromatin_context_frontier_schema(
    fixture: ChromatinContextFrontierFixture,
    evaluation: ChromatinContextFrontierEvaluation | None = None,
) -> ChromatinContextFrontierSchemaReport:
    checks = [
        ChromatinContextFrontierSchemaCheck(
            "fixture_context",
            fixture.context_key == CHROMATIN_CONTEXT_FRONTIER_CONTEXT_KEY,
            "fixture uses the declared six-part context key",
            fixture.context_key,
            CHROMATIN_CONTEXT_FRONTIER_CONTEXT_KEY,
        ),
        ChromatinContextFrontierSchemaCheck(
            "evidence_boundary",
            fixture.evidence_boundary == CHROMATIN_CONTEXT_FRONTIER_BOUNDARY,
            "fixture remains aggregate-only",
            fixture.evidence_boundary,
            CHROMATIN_CONTEXT_FRONTIER_BOUNDARY,
        ),
        ChromatinContextFrontierSchemaCheck(
            "source_receipts",
            all(item.uri.startswith("https://") for item in fixture.sources),
            "all source receipts use HTTPS",
        ),
        ChromatinContextFrontierSchemaCheck(
            "source_scope",
            all(item.public_aggregate for item in fixture.sources),
            "all sources declare aggregate scope",
        ),
        ChromatinContextFrontierSchemaCheck(
            "record_context",
            all(item.context_key == fixture.context_key for item in fixture.records),
            "all records use the fixture context",
        ),
        ChromatinContextFrontierSchemaCheck(
            "record_payloads",
            all(bool(item.payload) for item in fixture.records),
            "all records carry typed payloads",
        ),
        ChromatinContextFrontierSchemaCheck(
            "content_addresses",
            fixture.content_address.startswith("sha256:")
            and all(item.content_address.startswith("sha256:") for item in fixture.records),
            "fixture and records have content addresses",
        ),
        ChromatinContextFrontierSchemaCheck(
            "expected_states",
            all(bool(item.expected_state.value) for item in fixture.records),
            "every record declares an expected state",
        ),
    ]
    if evaluation is not None:
        checks.append(
            ChromatinContextFrontierSchemaCheck(
                "evaluation_shape",
                len(evaluation.records) == len(fixture.records),
                "evaluation has one row per fixture record",
                len(evaluation.records),
                len(fixture.records),
            )
        )
    failed = tuple(item.check_id for item in checks if not item.passed)
    return ChromatinContextFrontierSchemaReport(tuple(checks), not failed, failed)


__all__ = [
    "ChromatinContextFrontierSchemaCheck",
    "ChromatinContextFrontierSchemaReport",
    "validate_chromatin_context_frontier_schema",
]
