"""Conservative policy decisions at the specimen architecture boundary."""

from __future__ import annotations

from dataclasses import dataclass

from .specimen_architecture_contracts import (
    SpecimenArchitectureCase,
    SpecimenArchitectureCheck,
    SpecimenArchitectureCheckKind,
    SpecimenArchitectureScenario,
    SpecimenArchitectureState,
    addressed,
)


@dataclass(frozen=True, slots=True)
class SpecimenArchitecturePolicyDecision:
    case_id: str
    disposition: str
    state: SpecimenArchitectureState
    reason_codes: tuple[str, ...]
    adapter_allowed: bool
    content_address: str


@dataclass(frozen=True, slots=True)
class SpecimenArchitecturePolicyReport:
    fixture_id: str
    decisions: tuple[SpecimenArchitecturePolicyDecision, ...]
    checks: tuple[SpecimenArchitectureCheck, ...]
    accepted: bool
    content_address: str


def score_specimen_architecture_policy(
    fixture_id: str,
    cases: tuple[SpecimenArchitectureCase, ...],
) -> SpecimenArchitecturePolicyReport:
    """Classify positive, context, malformed, and identity cases."""

    decisions: list[SpecimenArchitecturePolicyDecision] = []
    for case in cases:
        if case.scenario is SpecimenArchitectureScenario.POSITIVE:
            disposition = "delegate"
            state = SpecimenArchitectureState.ACCEPTED
            reasons: tuple[str, ...] = ()
            allowed = True
        else:
            reason_by_scenario = {
                SpecimenArchitectureScenario.FOREIGN_CONTEXT: "context_mismatch",
                SpecimenArchitectureScenario.MALFORMED_INPUT: "malformed_input",
                SpecimenArchitectureScenario.IDENTITY_CONFLICT: "identity_conflict",
            }
            disposition = "hold_for_review"
            state = SpecimenArchitectureState.REVIEW
            reasons = (reason_by_scenario[case.scenario],)
            allowed = False
        body = {
            "case_id": case.case_id,
            "disposition": disposition,
            "state": state,
            "reason_codes": reasons,
            "adapter_allowed": allowed,
        }
        decisions.append(
            SpecimenArchitecturePolicyDecision(
                case_id=case.case_id,
                disposition=disposition,
                state=state,
                reason_codes=reasons,
                adapter_allowed=allowed,
                content_address=addressed(body, "specimen-policy-decision"),
            )
        )
    checks = (
        _check(
            "positive-delegation",
            sum(item.adapter_allowed for item in decisions) == 16,
            sum(item.adapter_allowed for item in decisions),
            16,
            "all positives delegate exactly once",
        ),
        _check(
            "control-hold",
            sum(not item.adapter_allowed for item in decisions) == 48,
            sum(not item.adapter_allowed for item in decisions),
            48,
            "all controls are held before adapter dispatch",
        ),
        _check(
            "policy-identity",
            len({item.case_id for item in decisions}) == len(decisions),
            len({item.case_id for item in decisions}),
            len(decisions),
            "policy decisions are one-to-one with cases",
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {
        "fixture_id": fixture_id,
        "decisions": decisions,
        "checks": checks,
        "accepted": accepted,
    }
    return SpecimenArchitecturePolicyReport(
        fixture_id, tuple(decisions), checks, accepted, addressed(body, "specimen-policy")
    )


def _check(
    check_id: str, passed: bool, observed: object, required: object, detail: str
) -> SpecimenArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": SpecimenArchitectureCheckKind.REVIEW,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return SpecimenArchitectureCheck(
        check_id,
        SpecimenArchitectureCheckKind.REVIEW,
        passed,
        observed,
        required,
        detail,
        addressed(body, "specimen-policy-check"),
    )


__all__ = [
    "SpecimenArchitecturePolicyDecision",
    "SpecimenArchitecturePolicyReport",
    "score_specimen_architecture_policy",
]
