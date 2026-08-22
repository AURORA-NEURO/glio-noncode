"""Explicit operation contracts for the causal-evidence frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_frontier_public_data import CausalFrontierOperation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class CausalFrontierContract:
    contract_id: str
    operation: CausalFrontierOperation
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
        if not self.required_payload_fields or not self.positive_states:
            raise ValueError("causal contracts require fields and positive states")
        if not self.issue_vocabulary or not self.prohibited_claims:
            raise ValueError("causal contracts require issue and claim boundaries")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalFrontierContractRegistry:
    contracts: tuple[CausalFrontierContract, ...]
    content_address: str

    def __post_init__(self) -> None:
        operations = tuple(item.operation for item in self.contracts)
        if len(set(operations)) != len(operations):
            raise ValueError("causal contract operations must be unique")
        if set(operations) != set(CausalFrontierOperation):
            raise ValueError("causal contracts must cover every operation")

    def by_operation(self, operation: CausalFrontierOperation) -> CausalFrontierContract:
        for contract in self.contracts:
            if contract.operation is operation:
                return contract
        raise KeyError(operation)

    def by_id(self, contract_id: str) -> CausalFrontierContract:
        for contract in self.contracts:
            if contract.contract_id == contract_id:
                return contract
        raise KeyError(contract_id)

    def issue_codes(self) -> tuple[str, ...]:
        return tuple(sorted({code for item in self.contracts for code in item.issue_vocabulary}))

    def manifest(self) -> dict[str, Any]:
        return {"contracts": [item.to_dict() for item in self.contracts], "content_address": self.content_address}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _contract(
    contract_id: str,
    operation: CausalFrontierOperation,
    adapter_name: str,
    required_payload_fields: tuple[str, ...],
    positive_states: tuple[str, ...],
    control_states: tuple[str, ...],
    issue_vocabulary: tuple[str, ...],
    prohibited_claims: tuple[str, ...],
) -> CausalFrontierContract:
    body = {
        "contract_id": contract_id,
        "operation": operation,
        "adapter_name": adapter_name,
        "required_payload_fields": required_payload_fields,
        "positive_states": positive_states,
        "control_states": control_states,
        "issue_vocabulary": issue_vocabulary,
        "prohibited_claims": prohibited_claims,
        "public_boundary": "public_aggregate_non_patient",
    }
    return CausalFrontierContract(**body, content_address=content_hash(body))


def default_causal_frontier_contracts() -> CausalFrontierContractRegistry:
    contracts = (
        _contract(
            "GNC-D11-C13-contract-v1",
            CausalFrontierOperation.POSTERIOR_DECOMPOSITION,
            "PosteriorDecompositionEngine",
            ("input_records",),
            ("supported",),
            ("partial", "invalid"),
            ("zero_posterior_mass", "empty_posterior_input", "invalid_posterior_input"),
            ("causal certainty", "clinical outcome", "diagnosis", "pathogenicity", "therapy"),
        ),
        _contract(
            "GNC-D11-C14-contract-v1",
            CausalFrontierOperation.DRIVER_POSTERIOR,
            "RegulatoryDriverHypothesisPosterior",
            ("input_records", "minimum_support"),
            ("supported",),
            ("partial", "invalid"),
            ("low_driver_support", "empty_driver_input", "invalid_driver_input"),
            ("causal driver", "clinical outcome", "diagnosis", "pathogenicity", "therapy"),
        ),
        _contract(
            "GNC-D11-C15-contract-v1",
            CausalFrontierOperation.SELECTIVE_PREDICTION,
            "SelectivePredictionAndAbstention",
            ("input_records", "minimum_score", "maximum_uncertainty"),
            ("supported",),
            ("partial", "invalid"),
            ("selective_prediction_abstention", "prediction_uncertainty_high", "empty_prediction_input"),
            ("clinical prediction", "diagnosis", "pathogenicity", "therapy", "patient-level decision"),
        ),
        _contract(
            "GNC-D11-C16-contract-v1",
            CausalFrontierOperation.DOSSIER_PUBLICATION,
            "CausalDossierPublisher",
            ("input_records", "dossier_id", "hypothesis_ids", "evidence_addresses", "top_hypothesis_id"),
            ("published",),
            ("invalid",),
            ("invalid_dossier_input", "empty_dossier_input"),
            ("causal proof", "clinical outcome", "diagnosis", "pathogenicity", "therapy", "actionability"),
        ),
    )
    return CausalFrontierContractRegistry(contracts, content_hash({"contracts": contracts}))


__all__ = ["CausalFrontierContract", "CausalFrontierContractRegistry", "default_causal_frontier_contracts"]
