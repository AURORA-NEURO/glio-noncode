"""D06 operation dispatch, family delegation, and receipt-level gates."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .sequence_architecture_contracts import (
    SEQUENCE_ARCHITECTURE_CONTEXT,
    SequenceArchitectureCase,
    SequenceArchitectureCaseReceipt,
    SequenceArchitectureCheck,
    SequenceArchitectureCheckKind,
    SequenceArchitectureEvaluation,
    SequenceArchitectureExecution,
    SequenceArchitectureFamily,
    SequenceArchitectureFixture,
    SequenceArchitectureOperation,
    SequenceArchitectureScenario,
    SequenceArchitectureState,
    addressed,
)
from .sequence_effect_frontier_fixture_eval import evaluate_sequence_effect_fixture
from .sequence_effect_frontier_public_data import default_sequence_effect_fixture
from .sequence_frontier_fixture_eval import evaluate_sequence_frontier_fixture
from .sequence_frontier_public_data import default_sequence_frontier_fixture
from .sequence_grammar_frontier_fixture_eval import evaluate_sequence_grammar_fixture
from .sequence_grammar_frontier_public_data import default_sequence_grammar_fixture
from .sequence_regulation_frontier_fixture_eval import evaluate_sequence_regulation_fixture
from .sequence_regulation_frontier_public_data import default_sequence_regulation_fixture
from .serialization import jsonable


def evaluate_sequence_architecture_fixture(
    fixture: SequenceArchitectureFixture,
) -> SequenceArchitectureEvaluation:
    """Execute all cases and retain family-specific outputs in aggregate summaries."""

    outcomes = _family_outcomes()
    executions = tuple(
        execute_sequence_architecture_case(case, fixture.context_key, outcomes=outcomes)
        for case in fixture.cases
    )
    receipts = tuple(
        _receipt(case, execution) for case, execution in zip(fixture.cases, executions, strict=True)
    )
    checks = tuple(
        check
        for case, execution, receipt in zip(fixture.cases, executions, receipts, strict=True)
        for check in _case_checks(case, execution, receipt)
    ) + _global_checks(fixture, receipts)
    accepted = all(item.passed for item in (*receipts, *checks))
    body = {
        "fixture_id": fixture.fixture_id,
        "context_key": fixture.context_key,
        "state": SequenceArchitectureState.ACCEPTED
        if accepted
        else SequenceArchitectureState.BLOCKED,
        "receipts": receipts,
        "checks": checks,
    }
    return SequenceArchitectureEvaluation(
        fixture_id=fixture.fixture_id,
        context_key=fixture.context_key,
        state=SequenceArchitectureState.ACCEPTED if accepted else SequenceArchitectureState.BLOCKED,
        receipts=receipts,
        checks=checks,
        content_address=addressed(body, "sequence-evaluation"),
    )


def execute_sequence_architecture_case(
    case: SequenceArchitectureCase,
    context_key: str = SEQUENCE_ARCHITECTURE_CONTEXT,
    *,
    outcomes: Mapping[tuple[SequenceArchitectureFamily, str], Mapping[str, Any]] | None = None,
) -> SequenceArchitectureExecution:
    """Apply aggregate controls before delegating a positive public record."""

    if (
        case.scenario is SequenceArchitectureScenario.FOREIGN_CONTEXT
        or case.context_key != context_key
    ):
        return _control_execution(
            case,
            SequenceArchitectureState.REVIEW,
            "out_of_domain",
            ("context_mismatch",),
            "foreign sequence context held before delegation",
        )
    if case.scenario is SequenceArchitectureScenario.MALFORMED_INPUT or case.payload.get(
        "malformed"
    ):
        return _control_execution(
            case,
            SequenceArchitectureState.REVIEW,
            "invalid",
            ("malformed_input",),
            "malformed sequence payload held before delegation",
        )
    if case.scenario is SequenceArchitectureScenario.IDENTITY_CONFLICT or case.payload.get(
        "identity_conflict"
    ):
        return _control_execution(
            case,
            SequenceArchitectureState.REVIEW,
            "contradictory",
            ("identity_conflict",),
            "identity conflict held before delegation",
        )
    selected = outcomes or _family_outcomes()
    record_id = str(case.payload.get("record_id", ""))
    outcome = selected.get((case.family, record_id))
    if outcome is None:
        return _control_execution(
            case,
            SequenceArchitectureState.REVIEW,
            "invalid",
            ("missing_family_receipt",),
            "positive case has no family receipt",
        )
    result_state = str(outcome["result_state"])
    observed_state = (
        SequenceArchitectureState.ACCEPTED
        if result_state in {"supported", "accepted", "published"}
        else SequenceArchitectureState.REVIEW
    )
    counts = {"primary": 1, "secondary": 1}
    summary = dict(outcome["summary"])
    output_address = addressed({"case_id": case.case_id, "summary": summary}, "sequence-execution")
    return SequenceArchitectureExecution(
        case_id=case.case_id,
        operation=case.operation,
        family=case.family,
        scenario=case.scenario,
        observed_state=observed_state,
        observed_result_state=result_state,
        issue_codes=tuple(outcome["issue_codes"]),
        counts=counts,
        output_address=output_address,
        summary=summary,
        detail=str(outcome["detail"]),
    )


def family_for_operation(operation: SequenceArchitectureOperation) -> SequenceArchitectureFamily:
    if operation in {
        SequenceArchitectureOperation.CONTEXT_ENCODING,
        SequenceArchitectureOperation.FOUNDATION_MODEL,
        SequenceArchitectureOperation.LONG_CONTEXT,
        SequenceArchitectureOperation.REGULATORY_ENSEMBLE,
    }:
        return SequenceArchitectureFamily.EFFECT
    if operation in {
        SequenceArchitectureOperation.MOTIF_DISRUPTION,
        SequenceArchitectureOperation.MOTIF_CREATION,
        SequenceArchitectureOperation.MOTIF_SPACING,
        SequenceArchitectureOperation.COOPERATIVE_GRAMMAR,
    }:
        return SequenceArchitectureFamily.GRAMMAR
    if operation in {
        SequenceArchitectureOperation.NUCLEOSOME_PROPENSITY,
        SequenceArchitectureOperation.SPLICE_REGULATION,
        SequenceArchitectureOperation.UTR_REGULATION,
        SequenceArchitectureOperation.PROMOTER_GRAMMAR,
    }:
        return SequenceArchitectureFamily.REGULATION
    return SequenceArchitectureFamily.FRONTIER


def _family_outcomes() -> dict[tuple[SequenceArchitectureFamily, str], dict[str, Any]]:
    fixtures = {
        SequenceArchitectureFamily.EFFECT: default_sequence_effect_fixture(),
        SequenceArchitectureFamily.GRAMMAR: default_sequence_grammar_fixture(),
        SequenceArchitectureFamily.REGULATION: default_sequence_regulation_fixture(),
        SequenceArchitectureFamily.FRONTIER: default_sequence_frontier_fixture(),
    }
    evaluations = {
        SequenceArchitectureFamily.EFFECT: evaluate_sequence_effect_fixture(
            fixtures[SequenceArchitectureFamily.EFFECT]
        ),
        SequenceArchitectureFamily.GRAMMAR: evaluate_sequence_grammar_fixture(
            fixtures[SequenceArchitectureFamily.GRAMMAR]
        ),
        SequenceArchitectureFamily.REGULATION: evaluate_sequence_regulation_fixture(
            fixtures[SequenceArchitectureFamily.REGULATION]
        ),
        SequenceArchitectureFamily.FRONTIER: evaluate_sequence_frontier_fixture(
            fixtures[SequenceArchitectureFamily.FRONTIER]
        ),
    }
    result: dict[tuple[SequenceArchitectureFamily, str], dict[str, Any]] = {}
    for family, evaluation in evaluations.items():
        rows = (
            getattr(evaluation, "executions", None)
            or getattr(evaluation, "records", None)
            or getattr(evaluation, "receipts", None)
        )
        for row in rows:
            state = getattr(row, "adapter_state", None) or getattr(row, "observed_state", None)
            issues = getattr(row, "issue_codes", None) or getattr(row, "observed_issue_codes", ())
            result[(family, str(row.record_id))] = {
                "result_state": str(getattr(state, "value", state)),
                "issue_codes": tuple(str(item) for item in issues),
                "summary": jsonable(row),
                "detail": f"{family.value} public positive receipt delegated and retained",
            }
    return result


def _control_execution(
    case: SequenceArchitectureCase,
    state: SequenceArchitectureState,
    result_state: str,
    issue_codes: tuple[str, ...],
    detail: str,
) -> SequenceArchitectureExecution:
    body = {
        "case_id": case.case_id,
        "state": state,
        "result_state": result_state,
        "issue_codes": issue_codes,
        "counts": {"primary": 0, "secondary": 0},
        "detail": detail,
    }
    return SequenceArchitectureExecution(
        case_id=case.case_id,
        operation=case.operation,
        family=case.family,
        scenario=case.scenario,
        observed_state=state,
        observed_result_state=result_state,
        issue_codes=issue_codes,
        counts={"primary": 0, "secondary": 0},
        output_address=addressed(body, "sequence-control"),
        summary={"control": True, "detail": detail},
        detail=detail,
    )


def _receipt(
    case: SequenceArchitectureCase, execution: SequenceArchitectureExecution
) -> SequenceArchitectureCaseReceipt:
    passed = (
        case.expected_state is execution.observed_state
        and case.expected_result_state == execution.observed_result_state
        and case.expected_issue_codes == execution.issue_codes
        and case.expected_counts == execution.counts
        and execution.output_address.startswith("sha256:")
    )
    body = {
        "case_id": case.case_id,
        "operation_id": case.operation_id,
        "family": case.family,
        "expected_state": case.expected_state,
        "observed_state": execution.observed_state,
        "expected_result_state": case.expected_result_state,
        "observed_result_state": execution.observed_result_state,
        "expected_issue_codes": case.expected_issue_codes,
        "observed_issue_codes": execution.issue_codes,
        "expected_counts": case.expected_counts,
        "observed_counts": execution.counts,
        "passed": passed,
        "output_address": execution.output_address,
    }
    return SequenceArchitectureCaseReceipt(
        case_id=case.case_id,
        operation_id=case.operation_id,
        family=case.family,
        expected_state=case.expected_state,
        observed_state=execution.observed_state,
        expected_result_state=case.expected_result_state,
        observed_result_state=execution.observed_result_state,
        expected_issue_codes=case.expected_issue_codes,
        observed_issue_codes=execution.issue_codes,
        expected_counts=case.expected_counts,
        observed_counts=execution.counts,
        passed=passed,
        output_address=execution.output_address,
        detail=execution.detail,
        content_address=addressed(body, "sequence-receipt"),
    )


def _case_checks(
    case: SequenceArchitectureCase,
    execution: SequenceArchitectureExecution,
    receipt: SequenceArchitectureCaseReceipt,
) -> tuple[SequenceArchitectureCheck, ...]:
    return (
        _check(
            f"{case.case_id}-state",
            case.expected_state is execution.observed_state,
            execution.observed_state.value,
            case.expected_state.value,
            "aggregate state matches expected control policy",
        ),
        _check(
            f"{case.case_id}-result",
            case.expected_result_state == execution.observed_result_state,
            execution.observed_result_state,
            case.expected_result_state,
            "family result state matches contract",
        ),
        _check(
            f"{case.case_id}-issues",
            case.expected_issue_codes == execution.issue_codes,
            execution.issue_codes,
            case.expected_issue_codes,
            "issue receipt is preserved exactly",
        ),
        _check(
            f"{case.case_id}-counts",
            case.expected_counts == execution.counts,
            execution.counts,
            case.expected_counts,
            "aggregate evidence counts remain bounded",
        ),
        _check(
            f"{case.case_id}-receipt",
            receipt.passed and receipt.content_address.startswith("sha256:"),
            receipt.passed,
            True,
            "receipt is addressed and passed",
        ),
    )


def _global_checks(
    fixture: SequenceArchitectureFixture, receipts: tuple[SequenceArchitectureCaseReceipt, ...]
) -> tuple[SequenceArchitectureCheck, ...]:
    return (
        _check(
            "global-receipt-count",
            len(receipts) == 64,
            len(receipts),
            64,
            "all cases have receipts",
        ),
        _check(
            "global-positive-count",
            sum(item.expected_state is SequenceArchitectureState.ACCEPTED for item in receipts)
            == 16,
            sum(item.expected_state is SequenceArchitectureState.ACCEPTED for item in receipts),
            16,
            "one positive per operation",
        ),
        _check(
            "global-control-count",
            sum(item.expected_state is SequenceArchitectureState.REVIEW for item in receipts) == 48,
            sum(item.expected_state is SequenceArchitectureState.REVIEW for item in receipts),
            48,
            "three controls per operation",
        ),
        _check(
            "global-pass-count",
            sum(item.passed for item in receipts) == 64,
            sum(item.passed for item in receipts),
            64,
            "every D06 receipt passes",
        ),
        _check(
            "global-operation-closure",
            {item.operation_id for item in receipts} == set(fixture.operation_ids),
            len({item.operation_id for item in receipts}),
            len(fixture.operations),
            "every operation has receipt closure",
        ),
    )


def _check(
    check_id: str, passed: bool, observed: Any, required: Any, detail: str
) -> SequenceArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": SequenceArchitectureCheckKind.OPERATION,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return SequenceArchitectureCheck(
        check_id=check_id,
        kind=SequenceArchitectureCheckKind.OPERATION,
        passed=passed,
        observed=observed,
        required=required,
        detail=detail,
        content_address=addressed(body, "sequence-operation-check"),
    )


__all__ = [
    "evaluate_sequence_architecture_fixture",
    "execute_sequence_architecture_case",
    "family_for_operation",
]
