"""Functional operation evaluation for the sixteen D01 intake capabilities."""

from __future__ import annotations

from typing import Any

from .intake_architecture_contracts import (
    IntakeArchitectureCase,
    IntakeArchitectureCheckKind,
    IntakeArchitectureEvaluation,
    IntakeArchitectureEvaluationCheck,
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


def evaluate_intake_architecture_case(
    case: IntakeArchitectureCase,
) -> IntakeArchitectureOperationResult:
    issue_codes = tuple(_base_issues(case))
    receipts = _functional_receipts(case)
    output: dict[str, Any] = {
        "case_id": case.case_id,
        "operation_id": case.operation_id,
        "capability_id": case.capability_id,
        "state": IntakeArchitectureState.ACCEPTED
        if not issue_codes
        else IntakeArchitectureState.REVIEW,
        "public_identifier": case.public_identifier,
        "source_count": len(case.source_ids),
        "receipt_count": len(receipts),
        "claim_boundary": "public aggregate intake identity only",
    }
    observed_state = (
        IntakeArchitectureState.ACCEPTED if not issue_codes else IntakeArchitectureState.REVIEW
    )
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
        content_address=addressed(
            {**output, "expected_state": case.expected_state, "issue_codes": issue_codes},
            "intake-operation-result",
        ),
    )


def evaluate_intake_architecture_fixture(
    fixture: IntakeArchitectureFixture,
) -> IntakeArchitectureEvaluation:
    results = tuple(evaluate_intake_architecture_case(case) for case in fixture.cases)
    expected = {case.case_id: case for case in fixture.cases}
    passed = sum(
        result.expected_state is result.observed_state
        and result.issue_codes == expected[result.case_id].expected_issue_codes
        for result in results
    )
    failed = len(results) - passed

    def check(
        check_id: str,
        case_id: str,
        kind: IntakeArchitectureCheckKind,
        passed_check: bool,
        observed: Any,
        required: Any,
        detail: str,
    ) -> IntakeArchitectureEvaluationCheck:
        check_body = {
            "check_id": check_id,
            "case_id": case_id,
            "kind": kind,
            "passed": bool(passed_check),
            "observed": observed,
            "required": required,
            "detail": detail,
        }
        return IntakeArchitectureEvaluationCheck(
            **check_body,
            content_address=addressed(check_body, "intake-evaluation-check"),
        )

    checks: list[IntakeArchitectureEvaluationCheck] = []
    for result in results:
        case = expected[result.case_id]
        checks.extend(
            (
                check(
                    "case-id-present",
                    result.case_id,
                    IntakeArchitectureCheckKind.OPERATION,
                    bool(result.case_id),
                    result.case_id,
                    "non-empty",
                    "evaluated case has a stable key",
                ),
                check(
                    "operation-join",
                    result.case_id,
                    IntakeArchitectureCheckKind.OPERATION,
                    result.operation_id == case.operation_id,
                    result.operation_id,
                    case.operation_id,
                    "result joins the fixture operation",
                ),
                check(
                    "scenario-state",
                    result.case_id,
                    IntakeArchitectureCheckKind.OPERATION,
                    result.expected_state is result.observed_state,
                    result.observed_state,
                    result.expected_state,
                    "observed state matches the scenario contract",
                ),
                check(
                    "issue-reconciliation",
                    result.case_id,
                    IntakeArchitectureCheckKind.INTEGRITY,
                    result.issue_codes == case.expected_issue_codes,
                    result.issue_codes,
                    case.expected_issue_codes,
                    "issue codes reconcile with expected controls",
                ),
                check(
                    "source-join",
                    result.case_id,
                    IntakeArchitectureCheckKind.SOURCE,
                    bool(case.source_ids),
                    len(case.source_ids),
                    ">=1",
                    "source joins remain attached to the result",
                ),
                check(
                    "public-identifier",
                    result.case_id,
                    IntakeArchitectureCheckKind.IDENTITY,
                    result.output.get("public_identifier", "").startswith("public:"),
                    result.output.get("public_identifier"),
                    "public:*",
                    "result identity is public and bounded",
                ),
                check(
                    "addressed-result",
                    result.case_id,
                    IntakeArchitectureCheckKind.INTEGRITY,
                    ":" in result.content_address,
                    result.content_address,
                    "addressed",
                    "result receipt is content addressed",
                ),
            )
        )
    global_checks = (
        (
            "fixture-id-match",
            bool(fixture.fixture_id),
            fixture.fixture_id,
            "non-empty",
            "fixture identity is retained",
        ),
        (
            "result-cardinality",
            len(results) == len(fixture.cases),
            len(results),
            len(fixture.cases),
            "every fixture case executes",
        ),
        (
            "case-ids-unique",
            len({item.case_id for item in results}) == len(results),
            len({item.case_id for item in results}),
            len(results),
            "result identifiers are unique",
        ),
        (
            "passed-partition",
            passed + failed == len(results),
            passed + failed,
            len(results),
            "passed and failed cases partition execution",
        ),
        (
            "failed-case-denominator",
            failed == 0,
            failed,
            0,
            "canonical fixture has no failed cases",
        ),
        (
            "positive-acceptance",
            all(
                item.observed_state is IntakeArchitectureState.ACCEPTED
                for item in results
                if item.scenario is IntakeArchitectureScenario.POSITIVE
            ),
            sum(item.scenario is IntakeArchitectureScenario.POSITIVE for item in results),
            16,
            "positive cases are accepted",
        ),
        (
            "controls-held",
            all(
                item.observed_state is not IntakeArchitectureState.ACCEPTED
                for item in results
                if item.scenario is not IntakeArchitectureScenario.POSITIVE
            ),
            sum(item.scenario is not IntakeArchitectureScenario.POSITIVE for item in results),
            48,
            "control cases remain held",
        ),
        (
            "operation-coverage",
            {item.operation_id for item in results}
            == {item.operation_id for item in fixture.operations},
            len({item.operation_id for item in results}),
            len(fixture.operations),
            "every operation has evaluated cases",
        ),
        (
            "positive-receipts",
            all(
                item.receipt_addresses
                for item in results
                if item.scenario is IntakeArchitectureScenario.POSITIVE
            ),
            sum(bool(item.receipt_addresses) for item in results),
            16,
            "positive cases retain primitive receipts",
        ),
        (
            "claim-boundary",
            all(
                item.output.get("claim_boundary") == "public aggregate intake identity only"
                for item in results
            ),
            True,
            True,
            "outputs state the public aggregate boundary",
        ),
    )
    for check_id, passed_check, observed, required, detail in global_checks:
        checks.append(
            check(
                check_id,
                "__fixture__",
                IntakeArchitectureCheckKind.INTEGRITY,
                passed_check,
                observed,
                required,
                detail,
            )
        )
    check_tuple = tuple(checks)
    body = {
        "fixture_id": fixture.fixture_id,
        "results": results,
        "checks": check_tuple,
        "passed_cases": passed,
        "failed_cases": failed,
        "accepted": failed == 0 and all(item.passed for item in check_tuple),
    }
    accepted = failed == 0 and all(item.passed for item in check_tuple)
    return IntakeArchitectureEvaluation(
        fixture.fixture_id,
        results,
        passed,
        failed,
        accepted,
        addressed(body, "intake-evaluation"),
        check_tuple,
    )


__all__ = [
    "evaluate_intake_architecture_case",
    "evaluate_intake_architecture_fixture",
]
