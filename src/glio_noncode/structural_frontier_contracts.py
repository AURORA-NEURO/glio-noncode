"""Operation contracts for the Domain 02 C13-C16 evidence gate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .structural_frontier_public_data import StructuralFrontierOperation


@dataclass(frozen=True, slots=True)
class StructuralFrontierOperationContract:
    """Declared inputs, outputs, provenance, and review semantics."""

    contract_id: str
    capability_id: str
    operation: StructuralFrontierOperation
    input_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    required_provenance: tuple[str, ...]
    accepted_result_states: tuple[str, ...]
    review_result_states: tuple[str, ...]
    safety_notes: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in ("contract_id", "capability_id"):
            require_non_empty(str(getattr(self, field_name)), field_name)
        for field_name in (
            "input_fields",
            "output_fields",
            "required_provenance",
            "accepted_result_states",
            "review_result_states",
            "safety_notes",
        ):
            if not getattr(self, field_name):
                raise ValidationError(f"structural frontier contract {field_name} must not be empty")
        for field_name in ("input_fields", "output_fields", "required_provenance"):
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValidationError(f"structural frontier contract {field_name} must be unique")

    @property
    def content_address(self) -> str:
        return content_hash(jsonable(self))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"content_address": self.content_address}

    def accepts(self, state: str) -> bool:
        return state in self.accepted_result_states

    def reviews(self, state: str) -> bool:
        return state in self.review_result_states


@dataclass(frozen=True, slots=True)
class StructuralFrontierContractRegistry:
    """Deterministic lookup table for C13-C16."""

    contracts: tuple[StructuralFrontierOperationContract, ...]

    def __post_init__(self) -> None:
        if not self.contracts:
            raise ValidationError("structural frontier contract registry must not be empty")
        contract_ids = [contract.contract_id for contract in self.contracts]
        operation_ids = [contract.operation.value for contract in self.contracts]
        if len(contract_ids) != len(set(contract_ids)):
            raise ValidationError("structural frontier contract IDs must be unique")
        if len(operation_ids) != len(set(operation_ids)):
            raise ValidationError("structural frontier contract operations must be unique")

    def get(self, operation: StructuralFrontierOperation | str) -> StructuralFrontierOperationContract:
        selected = StructuralFrontierOperation(operation)
        for contract in self.contracts:
            if contract.operation == selected:
                return contract
        raise ValidationError(f"no structural frontier contract for operation {selected.value}")

    def manifest(self) -> dict[str, Any]:
        body = {
            "schema_version": "structural-frontier-contracts-v1",
            "contract_count": len(self.contracts),
            "contracts": tuple(sorted(self.contracts, key=lambda item: item.contract_id)),
        }
        return jsonable(body) | {"content_address": content_hash(body)}


def default_structural_frontier_contract_registry() -> StructuralFrontierContractRegistry:
    """Return the four C13-C16 operation contracts."""

    return StructuralFrontierContractRegistry(
        contracts=(
            StructuralFrontierOperationContract(
                contract_id="GNC-D02-C13-contract",
                capability_id="GNC-D02-C13",
                operation=StructuralFrontierOperation.TANDEM_REPEAT,
                input_fields=(
                    "records",
                    "repeat_id",
                    "chromosome",
                    "start",
                    "end",
                    "motif",
                    "reference_units",
                    "observed_units",
                    "uncertainty_units",
                    "minimum_motif_length",
                    "context_key",
                ),
                output_fields=(
                    "observations",
                    "copy_delta",
                    "expanded_ids",
                    "contracted_ids",
                    "review_ids",
                    "issues",
                    "content_address",
                ),
                required_provenance=(
                    "source_id",
                    "raw_hash",
                    "repeat_id",
                    "context_key",
                    "measurement_uncertainty",
                ),
                accepted_result_states=("accepted",),
                review_result_states=("review", "blocked"),
                safety_notes=(
                    "copy delta is classified only after comparison with stated measurement uncertainty",
                    "invalid motifs and intervals remain review observations",
                    "repeat expansion is not a clinical, pathogenicity, or transposition claim",
                ),
            ),
            StructuralFrontierOperationContract(
                contract_id="GNC-D02-C14-contract",
                capability_id="GNC-D02-C14",
                operation=StructuralFrontierOperation.COMPOUND_HAPLOTYPE,
                input_fields=(
                    "records",
                    "haplotype_id",
                    "variant_ids",
                    "observed_variant_ids",
                    "phase_state",
                    "minimum_completeness",
                    "context_key",
                ),
                output_fields=(
                    "evaluations",
                    "missing_variant_ids",
                    "completeness",
                    "compatible_ids",
                    "review_ids",
                    "issues",
                    "content_address",
                ),
                required_provenance=(
                    "variant_ids",
                    "observed_variant_ids",
                    "phase_state",
                    "context_key",
                ),
                accepted_result_states=("accepted",),
                review_result_states=("review", "blocked"),
                safety_notes=(
                    "required and observed variant sets remain separately visible",
                    "phase unknown is retained rather than converted into cis or trans",
                    "completeness does not establish biological linkage or causal effect",
                ),
            ),
            StructuralFrontierOperationContract(
                contract_id="GNC-D02-C15-contract",
                capability_id="GNC-D02-C15",
                operation=StructuralFrontierOperation.BREAKPOINT_UNCERTAINTY,
                input_fields=(
                    "records",
                    "breakpoint_id",
                    "chromosome",
                    "left_min",
                    "left_max",
                    "right_min",
                    "right_max",
                    "confidence",
                    "minimum_confidence",
                    "context_key",
                ),
                output_fields=(
                    "intervals",
                    "propagated_uncertainty_bp",
                    "high_confidence_ids",
                    "review_ids",
                    "issues",
                    "content_address",
                ),
                required_provenance=(
                    "source_id",
                    "breakpoint_id",
                    "left_interval",
                    "right_interval",
                    "confidence",
                    "context_key",
                ),
                accepted_result_states=("accepted",),
                review_result_states=("review", "blocked"),
                safety_notes=(
                    "left and right breakpoint interval widths are propagated without narrowing",
                    "inverted bounds remain blocking review evidence",
                    "confidence is a declared input threshold, not a calibrated posterior",
                ),
            ),
            StructuralFrontierOperationContract(
                contract_id="GNC-D02-C16-contract",
                capability_id="GNC-D02-C16",
                operation=StructuralFrontierOperation.STRUCTURAL_EVIDENCE_EXPORT,
                input_fields=(
                    "evidence",
                    "bundle_id",
                    "variant_id",
                    "evidence_type",
                    "source_id",
                    "required_fields",
                    "context_key",
                ),
                output_fields=(
                    "bundle_id",
                    "evidence",
                    "source_ids",
                    "evidence_count",
                    "state",
                    "content_address",
                ),
                required_provenance=(
                    "source_ids",
                    "variant_ids",
                    "evidence_types",
                    "context_key",
                    "bundle_id",
                ),
                accepted_result_states=("published",),
                review_result_states=("blocked", "invalid"),
                safety_notes=(
                    "required evidence identity and source accounting are mandatory",
                    "rows are sorted deterministically before the bundle address is calculated",
                    "export is a publication envelope, not a truth-set or clinical interpretation",
                ),
            ),
        )
    )


__all__ = [
    "StructuralFrontierContractRegistry",
    "StructuralFrontierOperationContract",
    "default_structural_frontier_contract_registry",
]
