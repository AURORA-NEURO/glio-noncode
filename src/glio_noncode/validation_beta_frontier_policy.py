"""Policy disposition helpers for positive and control planning paths."""

from typing import Any

from .validation_beta_frontier_fixture_eval import ValidationBetaFrontierEvaluation
from .validation_beta_frontier_governance import ValidationBetaFrontierPolicy, materialize_validation_beta_frontier_policy


def validation_beta_frontier_policy_summary(policy: ValidationBetaFrontierPolicy) -> dict[str, Any]:
    return {
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "decision_count": len(policy.decisions),
        "publish_count": policy.publish_count,
        "review_count": policy.review_count,
        "quarantine_count": policy.quarantine_count,
        "content_address": policy.content_address,
    }


__all__ = ["ValidationBetaFrontierPolicy", "materialize_validation_beta_frontier_policy", "validation_beta_frontier_policy_summary"]
