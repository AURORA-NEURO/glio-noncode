"""Operation contracts for Domain 10 link-evidence frontier evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_frontier_public_data import LinkFrontierOperation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class LinkFrontierContract:
    contract_id: str
    operation: LinkFrontierOperation
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
            raise ValueError("link contracts require fields and positive states")
        if not self.issue_vocabulary:
            raise ValueError("link contracts require issue vocabulary")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkFrontierContractRegistry:
    contracts: tuple[LinkFrontierContract, ...]
    content_address: str

    def __post_init__(self) -> None:
        operations = tuple(item.operation for item in self.contracts)
        if len(set(operations)) != len(operations):
            raise ValueError("link contract operations must be unique")
        if set(operations) != set(LinkFrontierOperation):
            raise ValueError("link contracts must cover all operations")

    def by_operation(self, operation: LinkFrontierOperation) -> LinkFrontierContract:
        for contract in self.contracts:
            if contract.operation is operation:
                return contract
        raise KeyError(operation)

    def by_id(self, contract_id: str) -> LinkFrontierContract:
        for contract in self.contracts:
            if contract.contract_id == contract_id:
                return contract
        raise KeyError(contract_id)

    def manifest(self) -> dict[str, Any]:
        return {"contracts": [item.to_dict() for item in self.contracts], "content_address": self.content_address}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _contract(
    contract_id: str,
    operation: LinkFrontierOperation,
    adapter_name: str,
    required_payload_fields: tuple[str, ...],
    positive_states: tuple[str, ...],
    control_states: tuple[str, ...],
    issue_vocabulary: tuple[str, ...],
    prohibited_claims: tuple[str, ...],
) -> LinkFrontierContract:
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
    return LinkFrontierContract(**body, content_address=content_hash(body))


def default_link_frontier_contracts() -> LinkFrontierContractRegistry:
    contracts = (
        _contract(
            "GNC-D10-C13-contract-v1",
            LinkFrontierOperation.DEPENDENCE_CORRECTION,
            "LinkEvidenceDependenceCorrector",
            ("input_records",),
            ("supported",),
            ("partial", "invalid"),
            ("zero_corrected_support", "empty_dependence_input", "invalid_dependence_input"),
            ("causal", "clinical", "diagnostic", "pathogenicity", "actionability"),
        ),
        _contract(
            "GNC-D10-C14-contract-v1",
            LinkFrontierOperation.TARGET_GENE_RANKING,
            "TargetGeneRanker",
            ("input_records",),
            ("supported",),
            ("partial", "invalid"),
            ("zero_rank_support", "empty_rank_input", "invalid_rank_input"),
            ("causal_target", "clinical", "diagnostic", "pathogenicity", "actionability"),
        ),
        _contract(
            "GNC-D10-C15-contract-v1",
            LinkFrontierOperation.CALIBRATION_ABSTENTION,
            "LinkCalibrationAndAbstention",
            ("input_records", "maximum_uncertainty", "maximum_calibration_error"),
            ("supported",),
            ("partial", "invalid"),
            ("link_uncertainty_high", "link_calibration_error_high", "empty_calibration_input"),
            ("causal_probability", "clinical", "diagnostic", "pathogenicity", "actionability"),
        ),
        _contract(
            "GNC-D10-C16-contract-v1",
            LinkFrontierOperation.EVIDENCE_PUBLICATION,
            "LinkEvidencePublisher",
            ("input_records", "bundle_id"),
            ("published",),
            ("invalid",),
            ("publication_context_mismatch", "invalid_publication_input", "empty_publication_input"),
            ("causal_regulation", "clinical", "diagnostic", "pathogenicity", "treatment", "actionability"),
        ),
    )
    return LinkFrontierContractRegistry(contracts, content_hash({"contracts": contracts}))


__all__ = [
    "LinkFrontierContract",
    "LinkFrontierContractRegistry",
    "default_link_frontier_contracts",
]
