"""Operation contracts for Domain 12 cohort convergence evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_frontier_public_data import CohortFrontierOperation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class CohortFrontierContract:
    contract_id: str
    operation: CohortFrontierOperation
    adapter_name: str
    required_payload_fields: tuple[str, ...]
    positive_states: tuple[str, ...]
    control_states: tuple[str, ...]
    issue_vocabulary: tuple[str, ...]
    prohibited_claims: tuple[str, ...]
    public_boundary: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("contract_id", "adapter_name", "public_boundary", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.required_payload_fields or not self.issue_vocabulary:
            raise ValueError("cohort contracts require fields and issues")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFrontierContractRegistry:
    contracts: tuple[CohortFrontierContract, ...]
    content_address: str

    def __post_init__(self) -> None:
        operations = tuple(item.operation for item in self.contracts)
        if len(set(operations)) != len(operations) or set(operations) != set(CohortFrontierOperation):
            raise ValueError("cohort contracts must cover unique operations")

    def by_operation(self, operation: CohortFrontierOperation) -> CohortFrontierContract:
        return next(item for item in self.contracts if item.operation is operation)

    def issue_codes(self) -> tuple[str, ...]:
        return tuple(sorted({code for item in self.contracts for code in item.issue_vocabulary}))

    def manifest(self) -> dict[str, Any]:
        return {"contracts": [item.to_dict() for item in self.contracts], "content_address": self.content_address}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _contract(contract_id: str, operation: CohortFrontierOperation, adapter_name: str, required: tuple[str, ...], positive: tuple[str, ...], controls: tuple[str, ...], issues: tuple[str, ...], prohibited: tuple[str, ...]) -> CohortFrontierContract:
    body = {"contract_id": contract_id, "operation": operation, "adapter_name": adapter_name, "required_payload_fields": required, "positive_states": positive, "control_states": controls, "issue_vocabulary": issues, "prohibited_claims": prohibited, "public_boundary": "public_aggregate_non_patient"}
    return CohortFrontierContract(**body, content_address=content_hash(body))


def default_cohort_frontier_contracts() -> CohortFrontierContractRegistry:
    contracts = (
        _contract("GNC-D12-C13-contract-v1", CohortFrontierOperation.SUBGROUP_FAIRNESS, "SubgroupFairnessStratifier", ("input_records", "maximum_parity_gap"), ("supported",), ("review", "invalid"), ("parity_gap_high", "empty_fairness_input", "invalid_fairness_input"), ("fair clinical outcome", "individual risk", "diagnosis", "treatment")),
        _contract("GNC-D12-C14-contract-v1", CohortFrontierOperation.TRANSPORTABILITY, "TransportabilityEstimator", ("input_records", "minimum_overlap", "maximum_shift"), ("supported",), ("review", "invalid"), ("target_feature_gap", "distribution_shift_high", "empty_transportability_input", "invalid_transportability_input"), ("generalizes", "clinical outcome", "diagnosis", "treatment")),
        _contract("GNC-D12-C15-contract-v1", CohortFrontierOperation.FEDERATED_SUMMARY, "FederatedSummaryAnalyzer", ("input_records", "privacy_floor"), ("supported",), ("review", "invalid"), ("privacy_floor_violation", "empty_federated_input", "invalid_federated_input"), ("private patient result", "clinical outcome", "diagnosis", "treatment")),
        _contract("GNC-D12-C16-contract-v1", CohortFrontierOperation.COHORT_DISCOVERY, "CohortDiscoveryPublisher", ("input_records", "bundle_id", "analysis_ids"), ("published",), ("invalid",), ("invalid_cohort_discovery_input", "empty_cohort_discovery_input"), ("clinical cohort", "diagnosis", "prognosis", "treatment", "actionability")),
    )
    return CohortFrontierContractRegistry(contracts, content_hash({"contracts": contracts}))


__all__ = ["CohortFrontierContract", "CohortFrontierContractRegistry", "default_cohort_frontier_contracts"]
