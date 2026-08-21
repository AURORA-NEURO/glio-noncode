"""Independent state-transition scenarios for Domain 04 C09–C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .reference_governance_fixture_eval import ReferenceGovernanceEvaluationReport
from .reference_governance_public_data import (
    ReferenceGovernanceFixture,
    ReferenceGovernanceOperation,
    ReferenceGovernanceRole,
    default_reference_governance_fixture,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ReferenceGovernanceScenarioResult:
    """One scenario expectation and observed state."""

    scenario_id: str
    operation: ReferenceGovernanceOperation
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
class ReferenceGovernanceScenarioMatrix:
    """Scenario suite covering support, ambiguity, drift, and missing evidence."""

    fixture_id: str
    results: tuple[ReferenceGovernanceScenarioResult, ...]
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


def evaluate_reference_governance_scenarios(
    fixture: ReferenceGovernanceFixture | None = None,
    *,
    report: ReferenceGovernanceEvaluationReport,
) -> ReferenceGovernanceScenarioMatrix:
    """Evaluate independent floors from receipts rather than input text."""

    selected = fixture or default_reference_governance_fixture()
    by_id = {receipt.record_id: receipt for receipt in report.receipts}
    definitions = (
        (
            "alias-exact",
            ReferenceGovernanceOperation.GENE_ALIAS,
            "C09-POS-001",
            "supported",
            False,
            "exact alias resolves",
        ),
        (
            "alias-ambiguity",
            ReferenceGovernanceOperation.GENE_ALIAS,
            "C09-CTRL-001",
            "ambiguous",
            True,
            "shared symbol remains ambiguous",
        ),
        (
            "alias-build-boundary",
            ReferenceGovernanceOperation.GENE_ALIAS,
            "C09-CTRL-003",
            "out_of_domain",
            True,
            "assembly mismatch remains outside domain",
        ),
        (
            "frequency-derived",
            ReferenceGovernanceOperation.POPULATION_FREQUENCY,
            "C10-POS-001",
            "supported",
            False,
            "AC and AN derive a bounded frequency",
        ),
        (
            "frequency-conflict",
            ReferenceGovernanceOperation.POPULATION_FREQUENCY,
            "C10-CTRL-001",
            "contradictory",
            True,
            "same-population disagreement remains visible",
        ),
        (
            "frequency-missing-counts",
            ReferenceGovernanceOperation.POPULATION_FREQUENCY,
            "C10-CTRL-002",
            "partial",
            True,
            "missing counts do not become zero",
        ),
        (
            "snapshot-address",
            ReferenceGovernanceOperation.REFERENCE_SNAPSHOT,
            "C11-POS-001",
            "supported",
            False,
            "manifest is content-addressed",
        ),
        (
            "snapshot-hash-drift",
            ReferenceGovernanceOperation.REFERENCE_SNAPSHOT,
            "C11-CTRL-001",
            "contradictory",
            True,
            "expected hash drift blocks acceptance",
        ),
        (
            "snapshot-duplicate",
            ReferenceGovernanceOperation.REFERENCE_SNAPSHOT,
            "C11-CTRL-002",
            "contradictory",
            True,
            "duplicate resource identity is not overwritten",
        ),
        (
            "snapshot-assembly",
            ReferenceGovernanceOperation.REFERENCE_SNAPSHOT,
            "C11-CTRL-003",
            "out_of_domain",
            True,
            "older assembly remains outside context",
        ),
        (
            "license-allowed",
            ReferenceGovernanceOperation.LICENSE_RESTRICTION,
            "C12-POS-001",
            "supported",
            False,
            "declared permission allows research",
        ),
        (
            "license-missing",
            ReferenceGovernanceOperation.LICENSE_RESTRICTION,
            "C12-CTRL-001",
            "partial",
            True,
            "missing permission blocks use",
        ),
        (
            "license-expired",
            ReferenceGovernanceOperation.LICENSE_RESTRICTION,
            "C12-CTRL-002",
            "partial",
            True,
            "expired permission blocks use",
        ),
        (
            "license-conflict",
            ReferenceGovernanceOperation.LICENSE_RESTRICTION,
            "C12-CTRL-003",
            "contradictory",
            True,
            "conflicting restrictions require review",
        ),
    )
    results: list[ReferenceGovernanceScenarioResult] = []
    for scenario_id, operation, record_id, expected_state, expected_review, detail in definitions:
        receipt = by_id[record_id]
        record = selected.record_map()[record_id]
        observed_review = receipt.adapter_state != "supported"
        passed = (
            receipt.operation is operation
            and record.role
            is (
                ReferenceGovernanceRole.POSITIVE
                if not expected_review
                else ReferenceGovernanceRole.CONTROL
            )
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
        results.append(ReferenceGovernanceScenarioResult(**body, content_address=_address(body)))
    body = {"fixture_id": selected.fixture_id, "results": results}
    return ReferenceGovernanceScenarioMatrix(selected.fixture_id, tuple(results), _address(body))


__all__ = [
    "ReferenceGovernanceScenarioMatrix",
    "ReferenceGovernanceScenarioResult",
    "evaluate_reference_governance_scenarios",
]
