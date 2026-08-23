"""Recoverable actions for held validation planning rows."""

from typing import Any

from .validation_beta_frontier_governance import ValidationBetaFrontierPolicy, ValidationBetaFrontierQualityGate, ValidationBetaFrontierReleaseManifest


def build_validation_beta_frontier_recovery_plan(policy: ValidationBetaFrontierPolicy, quality: ValidationBetaFrontierQualityGate, release: ValidationBetaFrontierReleaseManifest) -> dict[str, Any]:
    actions = tuple({"record_id": decision.record_id, "action": "inspect_and_repair" if decision.disposition != "publish" else "retain_receipt", "reason": decision.reasons[0]} for decision in policy.decisions)
    return {"executable": bool(quality.accepted), "release_state": release.state, "actions": actions, "review_count": policy.review_count, "quarantine_count": policy.quarantine_count}


__all__ = ["build_validation_beta_frontier_recovery_plan"]
