"""Aggregate policy scoring for positive and held D06 cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_architecture_contracts import (
    SequenceArchitectureCase,
    SequenceArchitectureCheck,
    SequenceArchitectureCheckKind,
    SequenceArchitectureScenario,
    SequenceArchitectureState,
    addressed,
)


@dataclass(frozen=True, slots=True)
class SequenceArchitecturePolicyDecision:
    case_id: str
    scenario: SequenceArchitectureScenario
    state: SequenceArchitectureState
    result_state: str
    issue_codes: tuple[str, ...]
    delegated: bool
    content_address: str


@dataclass(frozen=True, slots=True)
class SequenceArchitecturePolicyReport:
    fixture_id: str
    decisions: tuple[SequenceArchitecturePolicyDecision, ...]
    checks: tuple[SequenceArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        from .serialization import jsonable

        return jsonable(self)


def score_sequence_architecture_policy(
    fixture_id: str, cases: tuple[SequenceArchitectureCase, ...]
) -> SequenceArchitecturePolicyReport:
    decisions = tuple(_decision(case) for case in cases)
    checks = (
        _check(
            "policy-case-count",
            len(decisions) == 64,
            len(decisions),
            64,
            "all D06 cases receive policy decisions",
        ),
        _check(
            "policy-positive-delegation",
            sum(item.delegated for item in decisions) == 16,
            sum(item.delegated for item in decisions),
            16,
            "only positive cases delegate to family adapters",
        ),
        _check(
            "policy-foreign-hold",
            sum(
                item.scenario is SequenceArchitectureScenario.FOREIGN_CONTEXT
                and item.state is SequenceArchitectureState.REVIEW
                for item in decisions
            )
            == 16,
            sum(
                item.scenario is SequenceArchitectureScenario.FOREIGN_CONTEXT
                and item.state is SequenceArchitectureState.REVIEW
                for item in decisions
            ),
            16,
            "foreign contexts are held",
        ),
        _check(
            "policy-malformed-hold",
            sum(
                item.scenario is SequenceArchitectureScenario.MALFORMED_INPUT
                and item.state is SequenceArchitectureState.REVIEW
                for item in decisions
            )
            == 16,
            sum(
                item.scenario is SequenceArchitectureScenario.MALFORMED_INPUT
                and item.state is SequenceArchitectureState.REVIEW
                for item in decisions
            ),
            16,
            "malformed input is held",
        ),
        _check(
            "policy-identity-hold",
            sum(
                item.scenario is SequenceArchitectureScenario.IDENTITY_CONFLICT
                and item.state is SequenceArchitectureState.REVIEW
                for item in decisions
            )
            == 16,
            sum(
                item.scenario is SequenceArchitectureScenario.IDENTITY_CONFLICT
                and item.state is SequenceArchitectureState.REVIEW
                for item in decisions
            ),
            16,
            "identity conflicts are held",
        ),
    )
    body = {"fixture_id": fixture_id, "decisions": decisions, "checks": checks}
    return SequenceArchitecturePolicyReport(
        fixture_id=fixture_id,
        decisions=decisions,
        checks=checks,
        accepted=all(item.passed for item in checks),
        content_address=addressed(body, "sequence-policy"),
    )


def _decision(case: SequenceArchitectureCase) -> SequenceArchitecturePolicyDecision:
    if case.scenario is SequenceArchitectureScenario.POSITIVE:
        state, result, issues, delegated = (
            SequenceArchitectureState.ACCEPTED,
            case.expected_result_state,
            case.expected_issue_codes,
            True,
        )
    elif case.scenario is SequenceArchitectureScenario.FOREIGN_CONTEXT:
        state, result, issues, delegated = (
            SequenceArchitectureState.REVIEW,
            "out_of_domain",
            ("context_mismatch",),
            False,
        )
    elif case.scenario is SequenceArchitectureScenario.MALFORMED_INPUT:
        state, result, issues, delegated = (
            SequenceArchitectureState.REVIEW,
            "invalid",
            ("malformed_input",),
            False,
        )
    else:
        state, result, issues, delegated = (
            SequenceArchitectureState.REVIEW,
            "contradictory",
            ("identity_conflict",),
            False,
        )
    body = {
        "case_id": case.case_id,
        "scenario": case.scenario,
        "state": state,
        "result_state": result,
        "issue_codes": issues,
        "delegated": delegated,
    }
    return SequenceArchitecturePolicyDecision(
        case_id=case.case_id,
        scenario=case.scenario,
        state=state,
        result_state=result,
        issue_codes=issues,
        delegated=delegated,
        content_address=addressed(body, "sequence-policy-decision"),
    )


def _check(
    check_id: str, passed: bool, observed: Any, required: Any, detail: str
) -> SequenceArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": SequenceArchitectureCheckKind.CONTEXT,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return SequenceArchitectureCheck(
        check_id=check_id,
        kind=SequenceArchitectureCheckKind.CONTEXT,
        passed=passed,
        observed=observed,
        required=required,
        detail=detail,
        content_address=addressed(body, "sequence-policy-check"),
    )


__all__ = [
    "SequenceArchitecturePolicyDecision",
    "SequenceArchitecturePolicyReport",
    "score_sequence_architecture_policy",
]
