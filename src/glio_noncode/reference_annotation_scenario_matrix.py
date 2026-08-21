"""State-transition matrix for positive and control annotation scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .reference_annotation_fixture_eval import (
    ReferenceAnnotationEvaluationReport,
    evaluate_reference_annotation_fixture,
)
from .reference_annotation_public_data import (
    ReferenceAnnotationFixture,
    ReferenceAnnotationOperation,
    ReferenceAnnotationRole,
    default_reference_annotation_fixture,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ReferenceAnnotationScenarioResult:
    scenario_id: str
    record_id: str
    operation: ReferenceAnnotationOperation
    role: ReferenceAnnotationRole
    expected_state: str
    observed_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    passed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceAnnotationScenarioMatrix:
    fixture_id: str
    fixture_version: str
    results: tuple[ReferenceAnnotationScenarioResult, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(result.passed for result in self.results)

    @property
    def positive_count(self) -> int:
        return sum(result.role is ReferenceAnnotationRole.POSITIVE for result in self.results)

    @property
    def control_count(self) -> int:
        return sum(result.role is ReferenceAnnotationRole.CONTROL for result in self.results)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "positive_count": self.positive_count,
            "control_count": self.control_count,
        }


def evaluate_reference_annotation_scenarios(
    fixture: ReferenceAnnotationFixture | None = None,
    *,
    report: ReferenceAnnotationEvaluationReport | None = None,
) -> ReferenceAnnotationScenarioMatrix:
    selected = fixture or default_reference_annotation_fixture()
    evaluation = report or evaluate_reference_annotation_fixture(selected)
    by_id = {receipt.record_id: receipt for receipt in evaluation.receipts}
    results: list[ReferenceAnnotationScenarioResult] = []
    for index, record in enumerate(selected.records, start=1):
        receipt = by_id.get(record.record_id)
        if receipt is None:
            raise ValidationError(f"missing annotation receipt for scenario {record.record_id}")
        observed_issues = tuple(receipt.observed_issue_codes)
        state_ok = receipt.resolution_state == record.expected_state
        issue_ok = set(record.expected_issue_codes) <= set(observed_issues)
        role_ok = (
            record.role is ReferenceAnnotationRole.POSITIVE
            and receipt.resolution_state == "supported"
        ) or (
            record.role is ReferenceAnnotationRole.CONTROL
            and receipt.resolution_state != "supported"
        )
        passed = state_ok and issue_ok and role_ok
        body = {
            "scenario_id": f"S{index:03d}",
            "record_id": record.record_id,
            "operation": record.operation,
            "role": record.role,
            "expected_state": record.expected_state,
            "observed_state": receipt.resolution_state,
            "expected_issue_codes": record.expected_issue_codes,
            "observed_issue_codes": observed_issues,
            "passed": passed,
        }
        results.append(
            ReferenceAnnotationScenarioResult(**body, content_address=content_hash(body))
        )
    body = {
        "fixture_id": selected.fixture_id,
        "fixture_version": selected.fixture_version,
        "results": results,
    }
    return ReferenceAnnotationScenarioMatrix(
        selected.fixture_id,
        selected.fixture_version,
        tuple(results),
        content_hash(body),
    )


__all__ = [
    "ReferenceAnnotationScenarioMatrix",
    "ReferenceAnnotationScenarioResult",
    "evaluate_reference_annotation_scenarios",
]
