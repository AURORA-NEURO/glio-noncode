"""Closed capability contracts for Domain 11 C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_alpha_frontier_public_data import CausalAlphaFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierContract:
    """Input, output, failure, and claim boundary for one operation."""

    contract_id: str
    capability_id: str
    operation: CausalAlphaFrontierOperation
    required_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    issue_codes: tuple[str, ...]
    limitation: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"contract_id": self.contract_id, "capability_id": self.capability_id, "operation": self.operation, "required_fields": self.required_fields, "output_fields": self.output_fields, "issue_codes": self.issue_codes, "limitation": self.limitation}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierContractReport:
    """Contract registry acceptance report."""

    contracts: tuple[CausalAlphaFrontierContract, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_capability(self, capability_id: str) -> CausalAlphaFrontierContract:
        return next(item for item in self.contracts if item.capability_id == capability_id)

    def for_operation(self, operation: CausalAlphaFrontierOperation | str) -> CausalAlphaFrontierContract:
        value = CausalAlphaFrontierOperation(str(operation))
        return next(item for item in self.contracts if item.operation is value)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"contracts": [item.to_dict() for item in self.contracts], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_alpha_frontier_contracts() -> CausalAlphaFrontierContractReport:
    contracts = (
        CausalAlphaFrontierContract("causal-alpha-c09-contract", "GNC-D11-C09", CausalAlphaFrontierOperation.MEDIATION_SENSITIVITY, ("mediator_kind", "source_node", "target_node", "context_key", "evidence"), ("base_state", "sensitivity_state", "maximum_absolute_delta", "robust_to_source_omission", "leave_one_out"), ("context_mismatch", "minimum_sources", "invalid_mediator_row"), "source omission measures robustness of a bounded mediator summary, not causal identification"),
        CausalAlphaFrontierContract("causal-alpha-c10-contract", "GNC-D11-C10", CausalAlphaFrontierOperation.CONFOUNDING_CHECKLIST, ("context_key", "required_confounder_ids", "observations"), ("state", "adjudications", "missing_confounder_ids", "unresolved_confounder_ids"), ("context_mismatch", "invalid_confounder_row"), "a completed checklist does not prove absence of unmeasured confounding"),
        CausalAlphaFrontierContract("causal-alpha-c11-contract", "GNC-D11-C11", CausalAlphaFrontierOperation.DEPENDENCE_CORRECTION, ("context_key", "observations"), ("state", "independent_group_count", "selected_evidence_ids", "duplicate_evidence_ids", "corrected_support"), ("context_mismatch", "invalid_dependence_row"), "declared dependence grouping is not a posterior and produces only a bounded support proxy"),
        CausalAlphaFrontierContract("causal-alpha-c12-contract", "GNC-D11-C12", CausalAlphaFrontierOperation.NEGATIVE_EVIDENCE, ("context_key", "observations"), ("state", "positive_evidence_ids", "negative_evidence_ids", "negative_control_ids", "negative_coverage"), ("context_mismatch", "invalid_negative_evidence_row"), "negative controls and measured negatives do not prove absence"),
    )
    return CausalAlphaFrontierContractReport(contracts, len(contracts) == 4 and {item.operation for item in contracts} == set(CausalAlphaFrontierOperation))


__all__ = ["CausalAlphaFrontierContract", "CausalAlphaFrontierContractReport", "build_causal_alpha_frontier_contracts"]
