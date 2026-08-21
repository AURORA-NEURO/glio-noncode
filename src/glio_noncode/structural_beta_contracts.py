"""Operation contracts for the Domain 02 C05-C08 beta evidence gate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .structural_beta_public_data import StructuralBetaOperation


@dataclass(frozen=True, slots=True)
class StructuralBetaOperationContract:
    """Declared inputs, outputs, provenance, and review semantics."""

    contract_id: str
    capability_id: str
    operation: StructuralBetaOperation
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
                raise ValidationError(f"beta contract {field_name} must not be empty")
        for field_name in ("input_fields", "output_fields", "required_provenance"):
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValidationError(f"beta contract {field_name} must be unique")

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
class StructuralBetaContractRegistry:
    """Deterministic lookup table for C05-C08."""

    contracts: tuple[StructuralBetaOperationContract, ...]

    def __post_init__(self) -> None:
        if not self.contracts:
            raise ValidationError("beta contract registry must not be empty")
        contract_ids = [contract.contract_id for contract in self.contracts]
        operation_ids = [contract.operation.value for contract in self.contracts]
        if len(contract_ids) != len(set(contract_ids)):
            raise ValidationError("beta contract IDs must be unique")
        if len(operation_ids) != len(set(operation_ids)):
            raise ValidationError("beta contract operations must be unique")

    def get(self, operation: StructuralBetaOperation | str) -> StructuralBetaOperationContract:
        selected = StructuralBetaOperation(operation)
        for contract in self.contracts:
            if contract.operation == selected:
                return contract
        raise ValidationError(f"no beta contract for operation {selected.value}")

    def manifest(self) -> dict[str, Any]:
        body = {
            "schema_version": "structural-beta-contracts-v1",
            "contract_count": len(self.contracts),
            "contracts": tuple(sorted(self.contracts, key=lambda item: item.contract_id)),
        }
        return jsonable(body) | {"content_address": content_hash(body)}


def default_structural_beta_contract_registry() -> StructuralBetaContractRegistry:
    """Return the four C05-C08 operation contracts."""

    return StructuralBetaContractRegistry(
        contracts=(
            StructuralBetaOperationContract(
                contract_id="GNC-D02-C05-contract",
                capability_id="GNC-D02-C05",
                operation=StructuralBetaOperation.FOCAL_AMPLIFICATION,
                input_fields=(
                    "records",
                    "segment_id",
                    "caller_id",
                    "chromosome",
                    "start",
                    "end",
                    "copy_number",
                    "baseline_copy_number",
                    "context_key",
                ),
                output_fields=(
                    "candidates",
                    "left_boundary_support",
                    "right_boundary_support",
                    "boundary_disagreement_bp",
                    "state",
                    "issues",
                    "content_address",
                ),
                required_provenance=(
                    "source_id",
                    "source_version",
                    "raw_hash",
                    "segment_ids",
                    "context_key",
                ),
                accepted_result_states=("supported", "partial", "ambiguous"),
                review_result_states=("abstained", "invalid", "out_of_domain", "ambiguous"),
                safety_notes=(
                    "uncovered sequence is not imputed between observed segments",
                    "caller boundaries remain visible beside the merged interval",
                    "a focal interval is not a gene-level or clinical assertion",
                ),
            ),
            StructuralBetaOperationContract(
                contract_id="GNC-D02-C06-contract",
                capability_id="GNC-D02-C06",
                operation=StructuralBetaOperation.CHROMOTHRIPSIS,
                input_fields=(
                    "records",
                    "event_id",
                    "chromosome",
                    "position",
                    "orientation",
                    "copy_number_state",
                    "min_breakpoints",
                    "max_gap_bp",
                    "context_key",
                ),
                output_fields=(
                    "candidates",
                    "breakpoint_count",
                    "orientation_switches",
                    "copy_number_switches",
                    "evidence_index",
                    "issues",
                    "content_address",
                ),
                required_provenance=(
                    "source_id",
                    "source_version",
                    "raw_hashes",
                    "breakpoint_ids",
                    "context_key",
                ),
                accepted_result_states=("supported", "partial", "ambiguous"),
                review_result_states=("abstained", "invalid", "out_of_domain", "partial"),
                safety_notes=(
                    "the evidence index is descriptive and not a calibrated probability",
                    "missing copy-number oscillation remains partial when required",
                    "cluster boundaries are explicit configuration, not biological truth",
                ),
            ),
            StructuralBetaOperationContract(
                contract_id="GNC-D02-C07-contract",
                capability_id="GNC-D02-C07",
                operation=StructuralBetaOperation.ECDNA,
                input_fields=(
                    "records",
                    "component_id",
                    "is_circular",
                    "junction_count",
                    "copy_number",
                    "linear_evidence",
                    "minimum_junctions",
                    "minimum_copy_number",
                    "context_key",
                ),
                output_fields=(
                    "candidates",
                    "circular_evidence",
                    "amplification_evidence",
                    "conflicting_linear_evidence",
                    "issues",
                    "content_address",
                ),
                required_provenance=(
                    "source_id",
                    "source_version",
                    "raw_hashes",
                    "caller_ids",
                    "context_key",
                ),
                accepted_result_states=("supported", "partial", "ambiguous"),
                review_result_states=("abstained", "invalid", "out_of_domain", "ambiguous"),
                safety_notes=(
                    "circularity requires explicit input evidence",
                    "high copy number alone does not create an ecDNA candidate",
                    "conflicting linear evidence remains visible and ambiguous",
                ),
            ),
            StructuralBetaOperationContract(
                contract_id="GNC-D02-C08-contract",
                capability_id="GNC-D02-C08",
                operation=StructuralBetaOperation.ENHANCER_HIJACKING,
                input_fields=(
                    "records",
                    "event_id",
                    "enhancer_id",
                    "target_gene_id",
                    "context_key",
                    "breakpoint_supported",
                    "activity_supported",
                    "contact_supported",
                    "minimum_evidence_channels",
                ),
                output_fields=(
                    "candidates",
                    "evidence_channels",
                    "alternatives_for_event",
                    "breakpoint_bridge",
                    "issues",
                    "content_address",
                ),
                required_provenance=(
                    "source_id",
                    "source_version",
                    "raw_hashes",
                    "context_key",
                    "event_id",
                ),
                accepted_result_states=("supported", "partial", "ambiguous"),
                review_result_states=("abstained", "invalid", "out_of_domain", "ambiguous"),
                safety_notes=(
                    "nearest-gene proximity cannot create a target relationship",
                    "a structural bridge is required before activity or contact is used",
                    "alternative target genes remain explicit when they share a bridge",
                ),
            ),
        )
    )


__all__ = [
    "StructuralBetaContractRegistry",
    "StructuralBetaOperationContract",
    "default_structural_beta_contract_registry",
]
