"""Operation contracts for the Domain 02 C09-C12 evidence gate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .structural_haplotype_public_data import StructuralHaplotypeOperation


@dataclass(frozen=True, slots=True)
class StructuralHaplotypeOperationContract:
    """Declared inputs, outputs, provenance, and review semantics."""

    contract_id: str
    capability_id: str
    operation: StructuralHaplotypeOperation
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
                raise ValidationError(f"structural haplotype contract {field_name} must not be empty")
        for field_name in ("input_fields", "output_fields", "required_provenance"):
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValidationError(f"structural haplotype contract {field_name} must be unique")

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
class StructuralHaplotypeContractRegistry:
    """Deterministic lookup table for C09-C12."""

    contracts: tuple[StructuralHaplotypeOperationContract, ...]

    def __post_init__(self) -> None:
        if not self.contracts:
            raise ValidationError("structural haplotype contract registry must not be empty")
        contract_ids = [contract.contract_id for contract in self.contracts]
        operation_ids = [contract.operation.value for contract in self.contracts]
        if len(contract_ids) != len(set(contract_ids)):
            raise ValidationError("structural haplotype contract IDs must be unique")
        if len(operation_ids) != len(set(operation_ids)):
            raise ValidationError("structural haplotype contract operations must be unique")

    def get(self, operation: StructuralHaplotypeOperation | str) -> StructuralHaplotypeOperationContract:
        selected = StructuralHaplotypeOperation(operation)
        for contract in self.contracts:
            if contract.operation == selected:
                return contract
        raise ValidationError(f"no structural haplotype contract for operation {selected.value}")

    def manifest(self) -> dict[str, Any]:
        body = {
            "schema_version": "structural-haplotype-contracts-v1",
            "contract_count": len(self.contracts),
            "contracts": tuple(sorted(self.contracts, key=lambda item: item.contract_id)),
        }
        return jsonable(body) | {"content_address": content_hash(body)}


def default_structural_haplotype_contract_registry() -> StructuralHaplotypeContractRegistry:
    """Return the four C09-C12 operation contracts."""

    return StructuralHaplotypeContractRegistry(
        contracts=(
            StructuralHaplotypeOperationContract(
                contract_id="GNC-D02-C09-contract",
                capability_id="GNC-D02-C09",
                operation=StructuralHaplotypeOperation.PHASED_HAPLOTYPE,
                input_fields=(
                    "records",
                    "observation_id",
                    "sample_id",
                    "chromosome",
                    "start",
                    "end",
                    "reference",
                    "alternate",
                    "genotype",
                    "phase_set",
                    "context_key",
                ),
                output_fields=(
                    "haplotypes",
                    "allele_calls",
                    "phase_complete",
                    "unphased_observations",
                    "issues",
                    "content_address",
                ),
                required_provenance=(
                    "source_id",
                    "source_version",
                    "raw_hash",
                    "observation_ids",
                    "context_key",
                ),
                accepted_result_states=("supported", "partial", "ambiguous"),
                review_result_states=("abstained", "invalid", "out_of_domain", "ambiguous", "partial"),
                safety_notes=(
                    "only explicitly phased genotype fields enter haplotype paths",
                    "unphased observations remain separate from assembled paths",
                    "paths retain allele calls but do not reconstruct sequence or infer read-backed phase",
                ),
            ),
            StructuralHaplotypeOperationContract(
                contract_id="GNC-D02-C10-contract",
                capability_id="GNC-D02-C10",
                operation=StructuralHaplotypeOperation.ALLELE_AWARE_SV,
                input_fields=(
                    "records",
                    "event_id",
                    "sample_id",
                    "chromosome",
                    "start",
                    "end",
                    "kind",
                    "alternate",
                    "genotype",
                    "allele_index",
                    "copy_number",
                    "support",
                    "context_key",
                ),
                output_fields=(
                    "events",
                    "allele_index",
                    "dosage",
                    "zygosity",
                    "copy_number",
                    "support",
                    "issues",
                    "content_address",
                ),
                required_provenance=(
                    "source_id",
                    "source_version",
                    "raw_hashes",
                    "event_id",
                    "context_key",
                ),
                accepted_result_states=("supported", "partial", "ambiguous"),
                review_result_states=("abstained", "invalid", "out_of_domain", "contradictory", "partial"),
                safety_notes=(
                    "declared genotype dosage is retained without inferring copy-number phasing",
                    "conflicting coordinates remain contradictory beside a bounded representative",
                    "allele-aware events are not collapsed into a single non-allelic event",
                ),
            ),
            StructuralHaplotypeOperationContract(
                contract_id="GNC-D02-C11-contract",
                capability_id="GNC-D02-C11",
                operation=StructuralHaplotypeOperation.PANGENOME_PROJECTION,
                input_fields=(
                    "queries",
                    "nodes",
                    "query_id",
                    "node_id",
                    "path_id",
                    "chromosome",
                    "start",
                    "end",
                    "orientation",
                    "max_candidates_per_query",
                    "context_key",
                ),
                output_fields=(
                    "matches",
                    "relation",
                    "overlap_bp",
                    "overlap_fraction",
                    "unmapped_query_ids",
                    "issues",
                    "content_address",
                ),
                required_provenance=(
                    "source_id",
                    "source_version",
                    "raw_hash",
                    "node_ids",
                    "path_ids",
                    "context_key",
                ),
                accepted_result_states=("supported", "partial", "ambiguous"),
                review_result_states=("abstained", "invalid", "out_of_domain", "ambiguous", "partial"),
                safety_notes=(
                    "projection uses supplied coordinate and path overlap only",
                    "multiple paths remain multiple mappings for reviewer inspection",
                    "coordinate overlap is not sequence homology or graph equivalence",
                ),
            ),
            StructuralHaplotypeOperationContract(
                contract_id="GNC-D02-C12-contract",
                capability_id="GNC-D02-C12",
                operation=StructuralHaplotypeOperation.REPEAT_MOBILE_ANNOTATION,
                input_fields=(
                    "queries",
                    "annotations",
                    "query_id",
                    "annotation_id",
                    "chromosome",
                    "start",
                    "end",
                    "family",
                    "class_name",
                    "subfamily",
                    "strand",
                    "min_overlap_fraction",
                    "context_key",
                ),
                output_fields=(
                    "hits",
                    "relation",
                    "overlap_bp",
                    "overlap_fraction",
                    "unannotated_query_ids",
                    "issues",
                    "content_address",
                ),
                required_provenance=(
                    "source_id",
                    "source_version",
                    "raw_hash",
                    "annotation_ids",
                    "context_key",
                ),
                accepted_result_states=("supported", "partial", "ambiguous"),
                review_result_states=("abstained", "invalid", "out_of_domain", "ambiguous", "partial"),
                safety_notes=(
                    "repeat labels are inherited from supplied annotation sources",
                    "overlap fractions are calculated against the requested interval and flank",
                    "annotation overlap does not derive transposition or sequence mechanism",
                ),
            ),
        )
    )


__all__ = [
    "StructuralHaplotypeContractRegistry",
    "StructuralHaplotypeOperationContract",
    "default_structural_haplotype_contract_registry",
]
