"""Operation contracts and prohibited inference boundaries for C05-C08."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierContract:
    capability_id: str
    operation: str
    title: str
    required_fields: tuple[str, ...]
    positive_states: tuple[str, ...]
    control_states: tuple[str, ...]
    review_triggers: tuple[str, ...]
    prohibited_claims: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierContractRegistry:
    contracts: tuple[CohortBetaFrontierContract, ...]
    content_address: str

    def by_operation(self, operation: str) -> CohortBetaFrontierContract:
        return next(item for item in self.contracts if item.operation == operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _contract(capability_id: str, operation: str, title: str, required_fields: tuple[str, ...], review_triggers: tuple[str, ...], prohibited_claims: tuple[str, ...]) -> CohortBetaFrontierContract:
    body = {"capability_id": capability_id, "operation": operation, "title": title, "required_fields": required_fields, "positive_states": ("supported",), "control_states": ("absent", "partial", "out_of_domain", "contradictory"), "review_triggers": review_triggers, "prohibited_claims": prohibited_claims}
    return CohortBetaFrontierContract(**body, content_address=content_hash(body, prefix="contract"))


def default_cohort_beta_frontier_contracts() -> CohortBetaFrontierContractRegistry:
    values = (_contract("GNC-D12-C05", "C05", "regulatory recurrence and hotspot test", ("observations", "context_key", "minimum_recurrent_samples", "hotspot_window_bp"), ("callable_space_incomplete", "context_mismatch", "small_sample"), ("driver", "clinical risk", "causal mechanism", "significance")), _contract("GNC-D12-C06", "C06", "regional burden test", ("regions", "observations", "callable_bases", "background_rate"), ("missing_comparator", "callable_space_incomplete", "context_mismatch"), ("p-value", "enrichment significance", "clinical effect", "causal mechanism")), _contract("GNC-D12-C07", "C07", "functional convergence test", ("observations", "feature_id", "support", "is_control"), ("missing_controls", "feature_tie", "context_mismatch"), ("functional proof", "causal effect", "treatment response", "clinical outcome")), _contract("GNC-D12-C08", "C08", "pathway and regulon convergence test", ("observations", "set_id", "set_kind", "direction"), ("direction_conflict", "set_definition_change", "context_mismatch"), ("pathway causality", "therapeutic target", "clinical prediction", "significance")))
    return CohortBetaFrontierContractRegistry(values, content_hash(values, prefix="contracts"))


__all__ = ["CohortBetaFrontierContract", "CohortBetaFrontierContractRegistry", "default_cohort_beta_frontier_contracts"]
