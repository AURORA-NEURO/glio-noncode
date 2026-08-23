"""Deny-by-default policy for D05 atlas context and control scenarios."""

from __future__ import annotations

from dataclasses import dataclass

from .atlas_architecture_contracts import (
    AtlasArchitectureCase,
    AtlasArchitectureCheck,
    AtlasArchitectureCheckKind,
    AtlasArchitectureScenario,
    AtlasArchitectureState,
    addressed,
)


@dataclass(frozen=True, slots=True)
class AtlasArchitecturePolicyDecision:
    case_id: str
    disposition: str
    state: AtlasArchitectureState
    reason_codes: tuple[str, ...]
    adapter_allowed: bool
    content_address: str


@dataclass(frozen=True, slots=True)
class AtlasArchitecturePolicyReport:
    fixture_id: str
    decisions: tuple[AtlasArchitecturePolicyDecision, ...]
    checks: tuple[AtlasArchitectureCheck, ...]
    accepted: bool
    content_address: str


def score_atlas_architecture_policy(
    fixture_id: str,
    cases: tuple[AtlasArchitectureCase, ...],
) -> AtlasArchitecturePolicyReport:
    """Allow exact-context positive cases and hold every declared control."""

    decisions: list[AtlasArchitecturePolicyDecision] = []
    for case in cases:
        if case.scenario is AtlasArchitectureScenario.POSITIVE:
            disposition = "delegate"
            state = AtlasArchitectureState.ACCEPTED
            reasons: tuple[str, ...] = ()
            allowed = True
        else:
            reason = {
                AtlasArchitectureScenario.FOREIGN_CONTEXT: "context_mismatch",
                AtlasArchitectureScenario.MALFORMED_INPUT: "malformed_input",
                AtlasArchitectureScenario.IDENTITY_CONFLICT: "identity_conflict",
            }[case.scenario]
            disposition = "hold_for_review"
            state = AtlasArchitectureState.REVIEW
            reasons = (reason,)
            allowed = False
        body = {
            "case_id": case.case_id,
            "disposition": disposition,
            "state": state,
            "reason_codes": reasons,
            "adapter_allowed": allowed,
        }
        decisions.append(
            AtlasArchitecturePolicyDecision(
                case.case_id,
                disposition,
                state,
                reasons,
                allowed,
                addressed(body, "atlas-policy-decision"),
            )
        )
    checks = (
        _check(
            "positive-delegation",
            sum(item.adapter_allowed for item in decisions) == 16,
            sum(item.adapter_allowed for item in decisions),
            16,
            "sixteen positive records delegate",
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
    body = {
        "fixture_id": fixture_id,
        "decisions": decisions,
        "checks": checks,
        "accepted": accepted,
    }
    return AtlasArchitecturePolicyReport(
        fixture_id,
        tuple(decisions),
        checks,
        accepted,
        addressed(body, "atlas-policy"),
    )


def _check(
    check_id: str, passed: bool, observed: object, required: object, detail: str
) -> AtlasArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": AtlasArchitectureCheckKind.REVIEW,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return AtlasArchitectureCheck(
        check_id,
        AtlasArchitectureCheckKind.REVIEW,
        passed,
        observed,
        required,
        detail,
        addressed(body, "atlas-policy-check"),
    )


__all__ = [
    "AtlasArchitecturePolicyDecision",
    "AtlasArchitecturePolicyReport",
    "score_atlas_architecture_policy",
]
