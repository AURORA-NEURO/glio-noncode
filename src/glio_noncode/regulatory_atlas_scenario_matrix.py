"""Independent state-transition scenarios for Domain 05 C01–C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .regulatory_atlas_fixture_eval import RegulatoryAtlasEvaluationReport
from .regulatory_atlas_public_data import (
    RegulatoryAtlasFixture,
    RegulatoryAtlasOperation,
    RegulatoryAtlasRole,
    default_regulatory_atlas_fixture,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class RegulatoryAtlasScenarioResult:
    """One named scenario and its observed state."""

    scenario_id: str
    operation: RegulatoryAtlasOperation
    source_record_id: str
    expected_state: str
    observed_state: str
    expected_review: bool
    observed_review: bool
    passed: bool
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.scenario_id, "scenario_id")
        require_non_empty(self.source_record_id, "source_record_id")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RegulatoryAtlasScenarioMatrix:
    """Scenario suite covering parse, profile, absence, context, and ambiguity."""

    fixture_id: str
    results: tuple[RegulatoryAtlasScenarioResult, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(result.passed for result in self.results)

    @property
    def failed_scenario_ids(self) -> tuple[str, ...]:
        return tuple(result.scenario_id for result in self.results if not result.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "failed_scenario_ids": list(self.failed_scenario_ids),
        }


def _address(body: Any) -> str:
    return content_hash(body)


def evaluate_regulatory_atlas_scenarios(
    fixture: RegulatoryAtlasFixture | None = None,
    *,
    report: RegulatoryAtlasEvaluationReport,
) -> RegulatoryAtlasScenarioMatrix:
    """Evaluate named independent floors from sanitized execution receipts."""

    selected = fixture or default_regulatory_atlas_fixture()
    by_id = {receipt.record_id: receipt for receipt in report.receipts}
    definitions = (
        (
            "parse-valid",
            RegulatoryAtlasOperation.CCRE_PARSE,
            "C01-POS-001",
            "supported",
            False,
            "valid cCRE record parses",
        ),
        (
            "parse-malformed-coordinate",
            RegulatoryAtlasOperation.CCRE_PARSE,
            "C01-CTRL-001",
            "partial",
            True,
            "malformed coordinate is quarantined",
        ),
        (
            "parse-invalid-json",
            RegulatoryAtlasOperation.CCRE_PARSE,
            "C01-CTRL-003",
            "abstained",
            True,
            "invalid JSON prevents parsing",
        ),
        (
            "brain-supported",
            RegulatoryAtlasOperation.BRAIN_CELL_PROFILE,
            "C02-POS-001",
            "supported",
            False,
            "brain cell profile matches context",
        ),
        (
            "brain-context-mismatch",
            RegulatoryAtlasOperation.BRAIN_CELL_PROFILE,
            "C02-CTRL-001",
            "out_of_domain",
            True,
            "brain evidence does not cross disease context",
        ),
        (
            "brain-absent",
            RegulatoryAtlasOperation.BRAIN_CELL_PROFILE,
            "C02-CTRL-002",
            "absent",
            True,
            "no overlap remains absence",
        ),
        (
            "adult-supported",
            RegulatoryAtlasOperation.ADULT_GLIO_PROFILE,
            "C03-POS-001",
            "supported",
            False,
            "adult glioma profile matches",
        ),
        (
            "adult-age-mismatch",
            RegulatoryAtlasOperation.ADULT_GLIO_PROFILE,
            "C03-CTRL-001",
            "out_of_domain",
            True,
            "adult profile retains age mismatch",
        ),
        (
            "adult-ambiguous",
            RegulatoryAtlasOperation.ADULT_GLIO_PROFILE,
            "C03-CTRL-003",
            "ambiguous",
            True,
            "multiple adult overlaps remain ambiguous",
        ),
        (
            "pediatric-supported",
            RegulatoryAtlasOperation.PEDIATRIC_GLIO_PROFILE,
            "C04-POS-001",
            "supported",
            False,
            "pediatric profile matches pediatric context",
        ),
        (
            "pediatric-adult-mismatch",
            RegulatoryAtlasOperation.PEDIATRIC_GLIO_PROFILE,
            "C04-CTRL-001",
            "out_of_domain",
            True,
            "pediatric evidence does not cross age context",
        ),
        (
            "pediatric-absent",
            RegulatoryAtlasOperation.PEDIATRIC_GLIO_PROFILE,
            "C04-CTRL-002",
            "absent",
            True,
            "pediatric interval absence remains explicit",
        ),
        (
            "pediatric-ambiguous",
            RegulatoryAtlasOperation.PEDIATRIC_GLIO_PROFILE,
            "C04-CTRL-003",
            "ambiguous",
            True,
            "multiple pediatric overlaps remain ambiguous",
        ),
    )
    results: list[RegulatoryAtlasScenarioResult] = []
    records = selected.record_map()
    for scenario_id, operation, record_id, expected_state, expected_review, detail in definitions:
        receipt = by_id[record_id]
        record = records[record_id]
        observed_review = receipt.adapter_state != "supported"
        expected_role = (
            RegulatoryAtlasRole.CONTROL if expected_review else RegulatoryAtlasRole.POSITIVE
        )
        passed = (
            receipt.operation is operation
            and record.role is expected_role
            and receipt.adapter_state == expected_state
            and observed_review == expected_review
        )
        body = {
            "scenario_id": scenario_id,
            "operation": operation,
            "source_record_id": record_id,
            "expected_state": expected_state,
            "observed_state": receipt.adapter_state,
            "expected_review": expected_review,
            "observed_review": observed_review,
            "passed": passed,
            "detail": detail,
        }
        results.append(RegulatoryAtlasScenarioResult(**body, content_address=_address(body)))
    body = {"fixture_id": selected.fixture_id, "results": results}
    return RegulatoryAtlasScenarioMatrix(selected.fixture_id, tuple(results), _address(body))


__all__ = [
    "RegulatoryAtlasScenarioMatrix",
    "RegulatoryAtlasScenarioResult",
    "evaluate_regulatory_atlas_scenarios",
]
