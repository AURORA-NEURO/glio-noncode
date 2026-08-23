"""Contracts and claim ceilings for Domain 12 C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierContract:
    capability_id: str
    operation: str
    title: str
    required_fields: tuple[str, ...]
    review_triggers: tuple[str, ...]
    prohibited_claims: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierContractRegistry:
    contracts: tuple[CohortAlphaFrontierContract, ...]
    content_address: str

    def by_operation(self, operation: str) -> CohortAlphaFrontierContract:
        return next(item for item in self.contracts if item.operation == operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _contract(capability_id: str, operation: str, title: str, fields: tuple[str, ...], triggers: tuple[str, ...], prohibited: tuple[str, ...]) -> CohortAlphaFrontierContract:
    body = {"capability_id": capability_id, "operation": operation, "title": title, "required_fields": fields, "review_triggers": triggers, "prohibited_claims": prohibited}
    return CohortAlphaFrontierContract(**body, content_address=content_hash(body, prefix="alpha-contract"))


def default_cohort_alpha_frontier_contracts() -> CohortAlphaFrontierContractRegistry:
    values = (_contract("GNC-D12-C09", "C09", "clonality and timing integration", ("variant_id", "sample_id", "cancer_cell_fraction", "phase", "timepoint", "context_key"), ("missing_ccf", "phase_gap", "foreign_context"), ("clonal evolution", "tumor lineage proof", "clinical prognosis")), _contract("GNC-D12-C10", "C10", "primary and recurrence comparator", ("variant_id", "locus_id", "phase", "frequency", "context_key"), ("missing_phase", "sampling_shift", "foreign_context"), ("recurrence causation", "prognosis", "treatment effect")), _contract("GNC-D12-C11", "C11", "treatment selection signal", ("variant_id", "treatment_id", "selection_phase", "frequency", "context_key"), ("missing_pre", "missing_post", "response_confounding", "foreign_context"), ("resistance", "benefit", "response prediction", "treatment recommendation")), _contract("GNC-D12-C12", "C12", "cross-cohort replication", ("feature_id", "cohort_id", "effect", "support", "sample_count", "context_key"), ("cohort_gap", "direction_disagreement", "sample_floor", "foreign_context"), ("transportability", "generalization", "clinical validity", "significance")))
    return CohortAlphaFrontierContractRegistry(values, content_hash(values, prefix="alpha-contracts"))


__all__ = ["CohortAlphaFrontierContract", "CohortAlphaFrontierContractRegistry", "default_cohort_alpha_frontier_contracts"]
