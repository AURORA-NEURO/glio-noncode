"""Declared parameter receipt for deterministic execution."""

from typing import Any

from .serialization import content_hash


def build_validation_beta_frontier_parameter_receipt(*, context_key: str, run_id: str, minimum_evidence_strength: float = 0.5, randomization_seed: str = "public-seed-1") -> dict[str, Any]:
    body = {"context_key": context_key, "run_id": run_id, "minimum_evidence_strength": minimum_evidence_strength, "randomization_seed": randomization_seed, "normal_approximation": "two-sided normal planning proxy"}
    return body | {"content_address": content_hash(body, prefix="validation-beta-parameters")}


__all__ = ["build_validation_beta_frontier_parameter_receipt"]
