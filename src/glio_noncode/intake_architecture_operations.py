"""Functional operation evaluation for the sixteen D01 intake capabilities."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .intake_architecture_contracts import (
    IntakeArchitectureCase,
    IntakeArchitectureEvaluation,
    IntakeArchitectureFixture,
    IntakeArchitectureOperationResult,
    IntakeArchitectureScenario,
    IntakeArchitectureState,
    addressed,
)
from .intake_architecture_identity import resolve_intake_architecture_identity
from .intake_architecture_normalization import normalize_intake_architecture_case
from .intake_architecture_parsing import parse_intake_architecture_case


def _operation_number(case: IntakeArchitectureCase) -> int:
    return int(case.operation_id[-2:])


def _base_issues(case: IntakeArchitectureCase) -> list[str]:
    payload = case.payload
    issues: list[str] = []
    if payload.get("context_key") != case.context_key:
        issues.append("foreign_context")
    if payload.get("malformed") is True or payload.get("required_field") == "":
        issues.append("malformed_input")
    if payload.get("duplicate_identity") is True:
        issues.append("duplicate_identity")
    if payload.get("public_aggregate_only") is not True:
        issues.append("scope_mismatch")
    return sorted(set(issues))


def _functional_receipts(case: IntakeArchitectureCase) -> tuple[str, ...]:
    """Run the relevant primitive and retain only its addressed receipt."""

    number = _operation_number(case)
    if case.scenario is not IntakeArchitectureScenario.POSITIVE:
        return ()
    if number in {2, 3, 7}:
        return (parse_intake_architecture_case(case).content_address,)
    if number in {4, 5, 8}:
        return (normalize_intake_architecture_case(case).content_address,)
    if number in {9, 10, 11}:
        return (resolve_intake_architecture_identity(case).content_address,)
    return (addressed(case.payload, "intake-operation-receipt"),)


def evaluate_intake_architecture_case(case: IntakeArchitectureCase) -> IntakeArchitectureOperationResult:
    issue_codes = tuple(_base_issues(case))
    receipts = _functional_receipts(case)
    output: dict[str, Any] = {
        "case_id": case.case_id,
        "operation_id": case.operation_id,
        "capability_id": case.capability_id,
        "state": IntakeArchitectureState.ACCEPTED if not issue_codes else IntakeArchitectureState.REVIEW,
        "public_identifier": case.public_identifier,
        "source_count": len(case.source_ids),
        "receipt_count": len(receipts),
        "claim_boundary": "public aggregate intake identity only",
    }
    observed_state = IntakeArchitectureState.ACCEPTED if not issue_codes else IntakeArchitectureState.REVIEW
    return IntakeArchitectureOperationResult(
        case_id=case.case_id,
        operation_id=case.operation_id,
        capability_id=case.capability_id,
        scenario=case.scenario,
        expected_state=case.expected_state,
        observed_state=observed_state,
        issue_codes=issue_codes,
        output=output,
        receipt_addresses=receipts,
        content_address=addressed({**output, "expected_state": case.expected_state, "issue_codes": issue_codes}, "intake-operation-result"),
    )


def evaluate_intake_architecture_fixture(fixture: IntakeArchitectureFixture) -> IntakeArchitectureEvaluation:
    results = tuple(evaluate_intake_architecture_case(case) for case in fixture.cases)
    expected = {case.case_id: case for case in fixture.cases}
    passed = sum(
        result.expected_state is result.observed_state
        and result.issue_codes == expected[result.case_id].expected_issue_codes
        for result in results
    )
    failed = len(results) - passed
    body = {"fixture_id": fixture.fixture_id, "results": results, "passed_cases": passed, "failed_cases": failed, "accepted": failed == 0}
    return IntakeArchitectureEvaluation(fixture.fixture_id, results, passed, failed, failed == 0, addressed(body, "intake-evaluation"))


__all__ = [
    "evaluate_intake_architecture_case",
    "evaluate_intake_architecture_fixture",
]
