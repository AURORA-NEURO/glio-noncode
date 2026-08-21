"""Operation contracts for the specimen beta frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .specimen_beta_frontier_public_data import SpecimenBetaFrontierOperation


@dataclass(frozen=True, slots=True)
class SpecimenBetaFrontierOperationContract:
    """Declared input, state, and safety boundary for one adapter."""

    capability_id: str
    operation: SpecimenBetaFrontierOperation
    input_fields: tuple[str, ...]
    positive_result_states: tuple[str, ...]
    review_result_states: tuple[str, ...]
    safety_notes: tuple[str, ...]
    contract_version: str = "specimen-beta-contract-v1"

    def __post_init__(self) -> None:
        require_non_empty(self.capability_id, "beta contract capability ID")
        if not self.input_fields or not self.positive_result_states:
            raise ValidationError("beta contract requires input and positive states")
        if not self.safety_notes:
            raise ValidationError("beta contract requires safety notes")
        if set(self.positive_result_states) & set(self.review_result_states):
            raise ValidationError("beta contract state sets must be disjoint")

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
class SpecimenBetaFrontierContractRegistry:
    """Deterministic registry containing exactly one contract per operation."""

    contracts: tuple[SpecimenBetaFrontierOperationContract, ...]

    def __post_init__(self) -> None:
        operations = tuple(contract.operation for contract in self.contracts)
        if len(operations) != len(set(operations)):
            raise ValidationError("beta contract operations must be unique")
        expected = set(SpecimenBetaFrontierOperation)
        if set(operations) != expected:
            raise ValidationError("beta contract registry must cover all operations")

    def get(
        self, operation: SpecimenBetaFrontierOperation | str
    ) -> SpecimenBetaFrontierOperationContract:
        try:
            normalized = SpecimenBetaFrontierOperation(str(operation))
        except ValueError as exc:
            raise ValidationError(f"unknown beta contract operation: {operation}") from exc
        for contract in self.contracts:
            if contract.operation == normalized:
                return contract
        raise ValidationError(f"unknown beta contract operation: {operation}")

    @property
    def content_address(self) -> str:
        return content_hash(self.contracts)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "content_address": self.content_address,
            "contract_count": len(self.contracts),
        }


def default_specimen_beta_frontier_contracts() -> SpecimenBetaFrontierContractRegistry:
    """Return the four release contracts used by the quality gate."""

    return SpecimenBetaFrontierContractRegistry(
        contracts=(
            SpecimenBetaFrontierOperationContract(
                capability_id="GNC-D03-C05",
                operation=SpecimenBetaFrontierOperation.ORIGIN,
                input_fields=(
                    "variant_id",
                    "relationship",
                    "tumor_alt_fraction",
                    "normal_alt_fraction",
                    "present_in_normal",
                ),
                positive_result_states=("supported",),
                review_result_states=("ambiguous", "partial", "abstained", "invalid"),
                safety_notes=(
                    "tumor and normal channels remain separate",
                    "conflicting origin observations remain uncertain",
                    "classification is research evidence and not a clinical diagnosis",
                ),
            ),
            SpecimenBetaFrontierOperationContract(
                capability_id="GNC-D03-C06",
                operation=SpecimenBetaFrontierOperation.MOSAICISM,
                input_fields=(
                    "variant_id",
                    "tissue_id",
                    "alternate_fraction",
                    "contamination_fraction",
                ),
                positive_result_states=("supported",),
                review_result_states=("partial", "ambiguous", "abstained", "invalid"),
                safety_notes=(
                    "repeated tissues are evidence of recurrence rather than proof of mosaicism",
                    "uncalibrated posterior-shaped values remain explicitly uncalibrated",
                    "contamination signals reduce confidence and remain visible",
                ),
            ),
            SpecimenBetaFrontierOperationContract(
                capability_id="GNC-D03-C07",
                operation=SpecimenBetaFrontierOperation.CANCER_CELL_FRACTION,
                input_fields=(
                    "sample_id",
                    "purity",
                    "variant_allele_fraction",
                    "total_copy_number",
                    "alternate_copy_number",
                ),
                positive_result_states=("supported",),
                review_result_states=("partial", "abstained", "invalid"),
                safety_notes=(
                    "purity and copy-number assumptions are retained with each estimate",
                    "raw CCF values outside the model range are not silently clamped",
                    "the interval is a measurement aid and not a calibrated confidence claim",
                ),
            ),
            SpecimenBetaFrontierOperationContract(
                capability_id="GNC-D03-C08",
                operation=SpecimenBetaFrontierOperation.SUBCLONE,
                input_fields=("sample_id", "variant_id", "estimated_ccf"),
                positive_result_states=("supported",),
                review_result_states=("ambiguous", "partial", "abstained", "invalid"),
                safety_notes=(
                    "clusters are relative within-sample CCF groups",
                    "boundary assignments remain ambiguous instead of being forced",
                    "clusters do not claim phylogeny, mutation order, or named biology",
                ),
            ),
        )
    )


__all__ = [
    "SpecimenBetaFrontierContractRegistry",
    "SpecimenBetaFrontierOperationContract",
    "default_specimen_beta_frontier_contracts",
]
