"""Deny-by-default scenario policy for public reference composition."""

from __future__ import annotations

from dataclasses import dataclass

from .reference_architecture_contracts import (
    ReferenceArchitectureCase,
    ReferenceArchitectureCheck,
    ReferenceArchitectureCheckKind,
    ReferenceArchitectureScenario,
    ReferenceArchitectureState,
    addressed,
)


@dataclass(frozen=True, slots=True)
class ReferenceArchitecturePolicyDecision:
    case_id: str
    disposition: str
    state: ReferenceArchitectureState
    reason_codes: tuple[str, ...]
    adapter_allowed: bool
    content_address: str


@dataclass(frozen=True, slots=True)
class ReferenceArchitecturePolicyReport:
    fixture_id: str
    decisions: tuple[ReferenceArchitecturePolicyDecision, ...]
    checks: tuple[ReferenceArchitectureCheck, ...]
    accepted: bool
    content_address: str


def score_reference_architecture_policy(
    fixture_id: str, cases: tuple[ReferenceArchitectureCase, ...]
) -> ReferenceArchitecturePolicyReport:
    """Allow exact-context positives and hold every explicit control."""

    decisions: list[ReferenceArchitecturePolicyDecision] = []
    for case in cases:
        if case.scenario is ReferenceArchitectureScenario.POSITIVE:
            disposition, state, reasons, allowed = (
                "delegate",
                ReferenceArchitectureState.ACCEPTED,
                (),
                True,
            )
        else:
            reason = {
                ReferenceArchitectureScenario.FOREIGN_CONTEXT: "context_mismatch",
                ReferenceArchitectureScenario.MALFORMED_INPUT: "malformed_input",
                ReferenceArchitectureScenario.IDENTITY_CONFLICT: "identity_conflict",
            }[case.scenario]
            disposition, state, reasons, allowed = (
                "hold_for_review",
                ReferenceArchitectureState.REVIEW,
                (reason,),
                False,
            )
        body = {
            "case_id": case.case_id,
            "disposition": disposition,
            "state": state,
            "reason_codes": reasons,
            "adapter_allowed": allowed,
        }
        decisions.append(
            ReferenceArchitecturePolicyDecision(
                case.case_id,
                disposition,
                state,
                reasons,
                allowed,
                addressed(body, "reference-policy-decision"),
            )
        )
    checks = (
        _check(
            "positive-delegation",
            sum(item.adapter_allowed for item in decisions) == 16,
            sum(item.adapter_allowed for item in decisions),
            16,
            "sixteen positives delegate",
        ),
        _check(
            "control-hold",
            sum(not item.adapter_allowed for item in decisions) == 48,
            sum(not item.adapter_allowed for item in decisions),
            48,
            "forty-eight controls are held",
        ),
        _check(
            "decision-identity",
            len({item.case_id for item in decisions}) == len(decisions),
            len({item.case_id for item in decisions}),
            len(decisions),
            "one policy decision per case",
        ),
    )
    accepted = all(item.passed for item in checks)
    return ReferenceArchitecturePolicyReport(
        fixture_id,
        tuple(decisions),
        checks,
        accepted,
        addressed(
            {
                "fixture_id": fixture_id,
                "decisions": decisions,
                "checks": checks,
                "accepted": accepted,
            },
            "reference-policy",
        ),
    )


def _check(
    check_id: str, passed: bool, observed: object, required: object, detail: str
) -> ReferenceArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": ReferenceArchitectureCheckKind.REVIEW,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ReferenceArchitectureCheck(
        check_id,
        ReferenceArchitectureCheckKind.REVIEW,
        passed,
        observed,
        required,
        detail,
        addressed(body, "reference-policy-check"),
    )


__all__ = [
    "ReferenceArchitecturePolicyDecision",
    "ReferenceArchitecturePolicyReport",
    "score_reference_architecture_policy",
]
