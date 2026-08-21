"""Declarative operation contracts for the Domain 01 variation evidence slice."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .variation_public_data import VariationRecordKind


class VariationContractFamily(StrEnum):
    """Operation families represented by the variation fixture."""

    NORMALIZATION = "normalization"
    CATEGORICAL = "categorical"
    ANNOTATION = "annotation"
    DECOMPOSITION = "decomposition"
    REPEAT = "repeat"


@dataclass(frozen=True, slots=True)
class VariationOperationContract:
    """Required input/output and state surface for one variation operation."""

    operation: str
    family: VariationContractFamily
    record_kind: VariationRecordKind
    capability_id: str
    required_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    accepted_states: tuple[str, ...]
    review_states: tuple[str, ...]
    evidence_role: str

    def __post_init__(self) -> None:
        for field_name in (
            "operation",
            "capability_id",
            "evidence_role",
        ):
            require_non_empty(getattr(self, field_name), field_name)
        if not self.required_fields:
            raise ValidationError(f"{self.operation} must declare required fields")
        if not self.output_fields:
            raise ValidationError(f"{self.operation} must declare output fields")
        if not self.accepted_states:
            raise ValidationError(f"{self.operation} must declare accepted states")
        if not self.review_states:
            raise ValidationError(f"{self.operation} must declare review states")
        if set(self.accepted_states) & set(self.review_states):
            raise ValidationError(f"{self.operation} state classes must not overlap")

    def accepts_state(self, state: str) -> bool:
        """Return whether a state is a declared operation state."""

        return state in self.accepted_states or state in self.review_states

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class VariationContractRegistry:
    """Validated, deterministic registry for the five variation operations."""

    def __init__(self, contracts: Iterable[VariationOperationContract]) -> None:
        values = tuple(contracts)
        operations = tuple(contract.operation for contract in values)
        capability_ids = tuple(contract.capability_id for contract in values)
        kinds = tuple(contract.record_kind for contract in values)
        if len(operations) != len(set(operations)):
            raise ValidationError("variation operation contract names must be unique")
        if len(capability_ids) != len(set(capability_ids)):
            raise ValidationError("variation capability IDs must be unique")
        if len(kinds) != len(set(kinds)):
            raise ValidationError("variation record kinds must be unique")
        self._contracts = values
        self._by_operation = {contract.operation: contract for contract in values}
        self._by_kind = {contract.record_kind: contract for contract in values}

    @property
    def contracts(self) -> tuple[VariationOperationContract, ...]:
        return self._contracts

    def contract_for_operation(self, operation: str) -> VariationOperationContract:
        try:
            return self._by_operation[operation]
        except KeyError as exc:
            raise ValidationError(f"unknown variation operation: {operation}") from exc

    def contract_for_kind(self, kind: VariationRecordKind) -> VariationOperationContract:
        try:
            return self._by_kind[kind]
        except KeyError as exc:
            raise ValidationError(f"no variation contract for record kind: {kind}") from exc

    def validate_payload(
        self,
        operation: str,
        payload: Mapping[str, Any],
    ) -> tuple[str, ...]:
        """Return missing required fields without executing the operation."""

        contract = self.contract_for_operation(operation)
        if not isinstance(payload, Mapping):
            raise ValidationError(f"{operation} payload must be an object")
        return tuple(field for field in contract.required_fields if field not in payload)

    def manifest(self) -> dict[str, Any]:
        payload = {
            "contract_version": "variation-contracts-v1",
            "contracts": self._contracts,
        }
        return {
            "contract_version": payload["contract_version"],
            "contract_count": len(self._contracts),
            "family_counts": {
                family.value: sum(contract.family == family for contract in self._contracts)
                for family in VariationContractFamily
            },
            "record_kinds": [contract.record_kind.value for contract in self._contracts],
            "capability_ids": [contract.capability_id for contract in self._contracts],
            "contracts": [contract.to_dict() for contract in self._contracts],
            "manifest_address": content_hash(payload),
        }


def default_variation_contract_registry() -> VariationContractRegistry:
    """Return the checked-in five-operation variation contract inventory."""

    return VariationContractRegistry(
        (
            VariationOperationContract(
                "vrs-normalization",
                VariationContractFamily.NORMALIZATION,
                VariationRecordKind.VRS,
                "GNC-D01-C04",
                ("variant_id", "chromosome", "start", "reference", "alternate"),
                ("state", "candidates", "selected_candidate_id", "content_address"),
                ("supported",),
                ("ambiguous", "abstained", "invalid"),
                "VRS-shaped allele and explicit unsupported-class boundary",
            ),
            VariationOperationContract(
                "categorical-normalization",
                VariationContractFamily.CATEGORICAL,
                VariationRecordKind.CATEGORICAL,
                "GNC-D01-C05",
                ("catalog", "query"),
                ("state", "candidates", "selected_category_id", "content_address"),
                ("supported",),
                ("ambiguous", "abstained", "invalid"),
                "declared category, alias, term, and member identity matching",
            ),
            VariationOperationContract(
                "annotation-envelope",
                VariationContractFamily.ANNOTATION,
                VariationRecordKind.ANNOTATION,
                "GNC-D01-C06",
                ("annotation_id", "subject", "statements", "evidence_lines"),
                ("state", "statements", "evidence_lines", "context_key", "content_address"),
                ("supported",),
                ("partial", "abstained", "contradictory", "out_of_domain", "missing"),
                "subject, context, statement, and evidence-line provenance",
            ),
            VariationOperationContract(
                "multiallelic-decomposition",
                VariationContractFamily.DECOMPOSITION,
                VariationRecordKind.MULTIALLELIC,
                "GNC-D01-C07",
                ("variant_id", "chromosome", "position", "reference", "alternates"),
                ("state", "alternates", "children", "input_hash", "content_address"),
                ("supported",),
                ("partial", "abstained", "invalid"),
                "lossless child identity, genotype projection, and symbolic abstention",
            ),
            VariationOperationContract(
                "repeat-aware-normalization",
                VariationContractFamily.REPEAT,
                VariationRecordKind.REPEAT,
                "GNC-D01-C08",
                ("variant", "reference_sequence", "reference_start"),
                ("state", "placements", "selected_placement", "issues", "content_address"),
                ("supported", "ambiguous"),
                ("abstained", "invalid"),
                "bounded reference-window replay and ambiguity preservation",
            ),
        )
    )


__all__ = [
    "VariationContractFamily",
    "VariationOperationContract",
    "VariationContractRegistry",
    "default_variation_contract_registry",
]
