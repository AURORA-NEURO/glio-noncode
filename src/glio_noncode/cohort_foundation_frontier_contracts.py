"""Operation contracts and explicit claim boundaries for C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_public_data import CohortFoundationOperation


@dataclass(frozen=True, slots=True)
class CohortFoundationContract:
    contract_id: str
    operation: CohortFoundationOperation
    capability_id: str
    required_fields: tuple[str, ...]
    positive_states: tuple[str, ...]
    control_states: tuple[str, ...]
    review_issues: tuple[str, ...]
    prohibited_claims: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationContractRegistry:
    contracts: tuple[CohortFoundationContract, ...]
    content_address: str

    def __post_init__(self) -> None:
        if {item.operation for item in self.contracts} != set(CohortFoundationOperation):
            raise ValueError("cohort foundation contracts must cover all operations")

    def by_operation(self, operation: CohortFoundationOperation) -> CohortFoundationContract:
        return next(item for item in self.contracts if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _contract(
    contract_id: str,
    operation: CohortFoundationOperation,
    capability_id: str,
    required_fields: tuple[str, ...],
    positive_states: tuple[str, ...],
    control_states: tuple[str, ...],
    review_issues: tuple[str, ...],
    prohibited_claims: tuple[str, ...],
) -> CohortFoundationContract:
    body = {"contract_id": contract_id, "operation": operation, "capability_id": capability_id, "required_fields": required_fields, "positive_states": positive_states, "control_states": control_states, "review_issues": review_issues, "prohibited_claims": prohibited_claims}
    return CohortFoundationContract(**body, content_address=content_hash(body))


def default_cohort_foundation_frontier_contracts() -> CohortFoundationContractRegistry:
    values = (
        _contract("GNC-D12-C01-contract-v1", CohortFoundationOperation.COHORT_QUERY, "GNC-D12-C01", ("query_id", "rows", "context_key"), ("supported",), ("partial", "absent", "out_of_domain"), ("excluded_records", "context_mismatch", "empty_selection"), ("clinical cohort", "diagnosis", "prognosis", "treatment")),
        _contract("GNC-D12-C02-contract-v1", CohortFoundationOperation.BACKGROUND_RATE, "GNC-D12-C02", ("background_records", "callable_intervals", "target_callable_bases"), ("supported",), ("partial", "abstained", "out_of_domain"), ("zero_observation", "missing_callable_intervals", "context_mismatch"), ("p-value", "significance", "risk", "clinical outcome")),
        _contract("GNC-D12-C03-contract-v1", CohortFoundationOperation.SEQUENCE_CONTROL, "GNC-D12-C03", ("target", "candidates", "max_controls", "max_distance"), ("supported",), ("partial", "absent", "out_of_domain"), ("insufficient_controls", "no_matching_control", "context_mismatch"), ("causal null", "clinical effect", "diagnosis", "treatment")),
        _contract("GNC-D12-C04-contract-v1", CohortFoundationOperation.CHROMATIN_CONTROL, "GNC-D12-C04", ("target", "candidates", "feature_ranges", "max_controls", "max_distance"), ("supported",), ("partial", "absent", "out_of_domain"), ("insufficient_controls", "no_matching_control", "context_mismatch"), ("causal null", "clinical effect", "diagnosis", "treatment")),
    )
    return CohortFoundationContractRegistry(values, content_hash(values))


__all__ = ["CohortFoundationContract", "CohortFoundationContractRegistry", "default_cohort_foundation_frontier_contracts"]
