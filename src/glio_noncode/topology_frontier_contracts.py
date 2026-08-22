"""Operation contracts for Domain 09 topology frontier evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .topology_frontier_public_data import TopologyFrontierOperation


@dataclass(frozen=True, slots=True)
class TopologyFrontierContract:
    contract_id: str
    operation: TopologyFrontierOperation
    adapter_name: str
    required_payload_fields: tuple[str, ...]
    positive_states: tuple[str, ...]
    control_states: tuple[str, ...]
    issue_vocabulary: tuple[str, ...]
    prohibited_claims: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in ("contract_id", "adapter_name", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.required_payload_fields or not self.positive_states:
            raise ValueError("topology contracts require fields and positive states")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyFrontierContractRegistry:
    contracts: tuple[TopologyFrontierContract, ...]
    content_address: str

    def __post_init__(self) -> None:
        operations = tuple(item.operation for item in self.contracts)
        if len(set(operations)) != len(operations):
            raise ValueError("topology contract operations must be unique")
        if set(operations) != set(TopologyFrontierOperation):
            raise ValueError("topology contracts must cover all operations")

    def by_operation(self, operation: TopologyFrontierOperation) -> TopologyFrontierContract:
        for contract in self.contracts:
            if contract.operation is operation:
                return contract
        raise KeyError(operation)

    def manifest(self) -> dict[str, Any]:
        return {
            "contracts": [item.to_dict() for item in self.contracts],
            "content_address": self.content_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _contract(
    contract_id: str,
    operation: TopologyFrontierOperation,
    adapter_name: str,
    required_payload_fields: tuple[str, ...],
    positive_states: tuple[str, ...],
    control_states: tuple[str, ...],
    issue_vocabulary: tuple[str, ...],
    prohibited_claims: tuple[str, ...],
) -> TopologyFrontierContract:
    body = {
        "contract_id": contract_id,
        "operation": operation,
        "adapter_name": adapter_name,
        "required_payload_fields": required_payload_fields,
        "positive_states": positive_states,
        "control_states": control_states,
        "issue_vocabulary": issue_vocabulary,
        "prohibited_claims": prohibited_claims,
    }
    return TopologyFrontierContract(**body, content_address=content_hash(body))


def default_topology_frontier_contracts() -> TopologyFrontierContractRegistry:
    contracts = (
        _contract(
            "GNC-D09-C13-contract-v1",
            TopologyFrontierOperation.ECDNA_CONTACT,
            "EcDNARegulatoryContactModel",
            ("input_text", "minimum_contact_score", "minimum_sources"),
            ("supported",),
            ("partial", "out_of_domain", "invalid"),
            ("context_mismatch", "ecDNA_context_mismatch", "weak_ecDNA_contact", "insufficient_ecDNA_sources", "invalid_ecdna_record"),
            ("clinical", "diagnostic", "causal_regulatory_link", "actionability"),
        ),
        _contract(
            "GNC-D09-C14-contract-v1",
            TopologyFrontierOperation.COMPARTMENT_SWITCH,
            "CompartmentSwitchEstimator",
            ("input_text", "switch_threshold"),
            ("supported",),
            ("partial", "out_of_domain", "invalid"),
            ("context_mismatch", "invalid_compartment_record"),
            ("causal_state_transition", "clinical", "diagnostic", "actionability"),
        ),
        _contract(
            "GNC-D09-C15-contract-v1",
            TopologyFrontierOperation.TOPOLOGY_TRANSPORT,
            "TopologyUncertaintyTransportModel",
            ("input_text", "minimum_effective_signal"),
            ("supported",),
            ("partial", "out_of_domain", "invalid"),
            ("context_mismatch", "weak_transported_signal", "topology_path_disconnected", "invalid_topology_path"),
            ("causal_pathway", "enhancer_target_link", "clinical", "actionability"),
        ),
        _contract(
            "GNC-D09-C16-contract-v1",
            TopologyFrontierOperation.EVIDENCE_PUBLICATION,
            "ThreeDEvidencePublisher",
            ("input_text", "bundle_id", "assay_ids"),
            ("supported",),
            ("partial", "out_of_domain", "invalid"),
            ("context_mismatch", "missing_assay_ids", "empty_3d_evidence", "invalid_3d_evidence"),
            ("causal_regulation", "clinical", "diagnostic", "treatment", "actionability"),
        ),
    )
    return TopologyFrontierContractRegistry(contracts, content_hash({"contracts": contracts}))


__all__ = [
    "TopologyFrontierContract",
    "TopologyFrontierContractRegistry",
    "default_topology_frontier_contracts",
]
