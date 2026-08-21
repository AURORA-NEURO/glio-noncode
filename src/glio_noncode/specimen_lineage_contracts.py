"""Operation contracts for the Domain 03 C09-C12 evidence gate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .specimen_lineage_public_data import SpecimenLineageOperation


@dataclass(frozen=True, slots=True)
class SpecimenLineageOperationContract:
    """Declared fields, result states, and safety boundary for one operation."""

    capability_id: str
    operation: SpecimenLineageOperation
    input_fields: tuple[str, ...]
    positive_result_states: tuple[str, ...]
    review_result_states: tuple[str, ...]
    safety_notes: tuple[str, ...]
    contract_version: str = "specimen-lineage-contract-v1"

    def __post_init__(self) -> None:
        require_non_empty(self.capability_id, "lineage contract capability ID")
        if not self.input_fields or not self.positive_result_states:
            raise ValidationError("lineage contract requires input and positive states")
        if not self.safety_notes:
            raise ValidationError("lineage contract requires safety notes")
        if set(self.positive_result_states) & set(self.review_result_states):
            raise ValidationError("lineage contract state sets must be disjoint")

    @property
    def content_address(self) -> str:
        return content_hash(
            {
                "capability_id": self.capability_id,
                "operation": self.operation,
                "input_fields": self.input_fields,
                "positive_result_states": self.positive_result_states,
                "review_result_states": self.review_result_states,
                "safety_notes": self.safety_notes,
                "contract_version": self.contract_version,
            }
        )

    def accepts_result_state(self, state: str) -> bool:
        return state in self.positive_result_states or state in self.review_result_states

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"content_address": self.content_address}


@dataclass(frozen=True, slots=True)
class SpecimenLineageContractRegistry:
    """Exactly one contract per C09-C12 operation."""

    contracts: tuple[SpecimenLineageOperationContract, ...]

    def __post_init__(self) -> None:
        operations = tuple(contract.operation for contract in self.contracts)
        if len(operations) != len(set(operations)):
            raise ValidationError("lineage contract operations must be unique")
        if set(operations) != set(SpecimenLineageOperation):
            raise ValidationError("lineage contract registry must cover all operations")

    def get(self, operation: SpecimenLineageOperation | str) -> SpecimenLineageOperationContract:
        try:
            normalized = SpecimenLineageOperation(str(operation))
        except ValueError as exc:
            raise ValidationError(f"unknown lineage contract operation: {operation}") from exc
        for contract in self.contracts:
            if contract.operation == normalized:
                return contract
        raise ValidationError(f"unknown lineage contract operation: {operation}")

    @property
    def content_address(self) -> str:
        return content_hash(self.contracts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contracts": tuple(contract.to_dict() for contract in self.contracts),
            "content_address": self.content_address,
            "contract_count": len(self.contracts),
            "schema_version": "specimen-lineage-contracts-v1",
        }


def default_specimen_lineage_contracts() -> SpecimenLineageContractRegistry:
    """Return the release contracts for specimen lineage and context."""

    return SpecimenLineageContractRegistry(
        contracts=(
            SpecimenLineageOperationContract(
                capability_id="GNC-D03-C09",
                operation=SpecimenLineageOperation.REGION_LINEAGE,
                input_fields=(
                    "region_id",
                    "sample_id",
                    "case_id",
                    "parent_region_id",
                    "relationship",
                    "context_key",
                ),
                positive_result_states=("supported",),
                review_result_states=(
                    "partial",
                    "ambiguous",
                    "contradictory",
                    "abstained",
                    "out_of_domain",
                ),
                safety_notes=(
                    "only declared parent edges are materialized",
                    "missing parents and cycles remain visible",
                    "a region graph does not authenticate specimen origin or prove clonal ancestry",
                ),
            ),
            SpecimenLineageOperationContract(
                capability_id="GNC-D03-C10",
                operation=SpecimenLineageOperation.LONGITUDINAL_LINKING,
                input_fields=(
                    "specimen_id",
                    "sample_id",
                    "case_id",
                    "collection_time",
                    "predecessor_specimen_id",
                    "tissue",
                ),
                positive_result_states=("supported",),
                review_result_states=(
                    "partial",
                    "ambiguous",
                    "contradictory",
                    "abstained",
                    "out_of_domain",
                ),
                safety_notes=(
                    "same-case boundaries are preserved",
                    "declared predecessors take precedence over ordered time",
                    "temporal links do not establish evolution, response, or resistance",
                ),
            ),
            SpecimenLineageOperationContract(
                capability_id="GNC-D03-C11",
                operation=SpecimenLineageOperation.PHASE_MAPPING,
                input_fields=(
                    "specimen_id",
                    "case_id",
                    "collection_time",
                    "phase",
                    "predecessor_specimen_id",
                ),
                positive_result_states=("supported",),
                review_result_states=(
                    "partial",
                    "ambiguous",
                    "contradictory",
                    "abstained",
                    "out_of_domain",
                ),
                safety_notes=(
                    "explicit labels are retained with their evidence basis",
                    "later time alone does not become recurrence",
                    "conflicting labels remain contradictory instead of being resolved silently",
                ),
            ),
            SpecimenLineageOperationContract(
                capability_id="GNC-D03-C12",
                operation=SpecimenLineageOperation.TREATMENT_CONTEXT,
                input_fields=(
                    "specimen_id",
                    "case_id",
                    "collection_time",
                    "exposure_id",
                    "therapy_id",
                    "start_time",
                    "end_time",
                ),
                positive_result_states=("supported",),
                review_result_states=(
                    "partial",
                    "ambiguous",
                    "contradictory",
                    "abstained",
                    "out_of_domain",
                ),
                safety_notes=(
                    "only same-case declared intervals are joined",
                    "overlapping exposures remain ambiguous",
                    "temporal proximity is bookkeeping and does not establish treatment "
                    "response or causality",
                ),
            ),
        )
    )


__all__ = [
    "SpecimenLineageContractRegistry",
    "SpecimenLineageOperationContract",
    "default_specimen_lineage_contracts",
]
