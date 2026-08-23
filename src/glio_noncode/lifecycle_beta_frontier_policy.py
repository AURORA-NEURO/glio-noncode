"""Research-use policy boundaries for the Domain 14 beta frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierState
from .serialization import content_hash, jsonable


LIFECYCLE_BETA_FRONTIER_ALLOWED_USES = (
    "aggregate fixture rehearsal",
    "research evidence review",
    "provenance and uncertainty inspection",
    "reproducible software quality validation",
)
LIFECYCLE_BETA_FRONTIER_EXCLUDED_USES = (
    "patient-level inference",
    "clinical diagnosis",
    "treatment selection",
    "causal authorization",
    "automatic dossier promotion",
)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierPolicyCheck:
    check_id: str
    state: LifecycleBetaFrontierState
    allowed: bool
    reason: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierPolicy:
    policy_id: str
    version: str
    allowed_uses: tuple[str, ...]
    excluded_uses: tuple[str, ...]
    checks: tuple[LifecycleBetaFrontierPolicyCheck, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_lifecycle_beta_frontier_policy() -> LifecycleBetaFrontierPolicy:
    states = tuple(LifecycleBetaFrontierState)
    checks = []
    for state in states:
        allowed = state in {LifecycleBetaFrontierState.SUPPORTED, LifecycleBetaFrontierState.READY_FOR_REVIEW, LifecycleBetaFrontierState.ADJUDICATED, LifecycleBetaFrontierState.APPROVED}
        body = {"check_id": f"state:{state.value}", "state": state, "allowed": allowed, "reason": "state remains bounded to research review" if allowed else "state requires explicit review and cannot be promoted"}
        checks.append(LifecycleBetaFrontierPolicyCheck(**body, content_address=content_hash(body)))
    body = {"policy_id": "lifecycle-beta-frontier-policy", "version": "2026.08.v1", "allowed_uses": LIFECYCLE_BETA_FRONTIER_ALLOWED_USES, "excluded_uses": LIFECYCLE_BETA_FRONTIER_EXCLUDED_USES, "checks": tuple(checks)}
    return LifecycleBetaFrontierPolicy(**body, content_address=content_hash(body))


def evaluate_lifecycle_beta_frontier_policy(state: LifecycleBetaFrontierState | str, policy: LifecycleBetaFrontierPolicy | None = None) -> LifecycleBetaFrontierPolicyCheck:
    policy = policy or default_lifecycle_beta_frontier_policy()
    selected = state if isinstance(state, LifecycleBetaFrontierState) else LifecycleBetaFrontierState(str(state))
    return next(item for item in policy.checks if item.state is selected)


__all__ = [
    "LIFECYCLE_BETA_FRONTIER_ALLOWED_USES",
    "LIFECYCLE_BETA_FRONTIER_EXCLUDED_USES",
    "LifecycleBetaFrontierPolicy",
    "LifecycleBetaFrontierPolicyCheck",
    "default_lifecycle_beta_frontier_policy",
    "evaluate_lifecycle_beta_frontier_policy",
]
