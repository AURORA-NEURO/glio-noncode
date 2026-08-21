"""Typed operation contracts for the Domain 04 reference-coordinate plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .reference_coordinate_public_data import ReferenceCoordinateOperation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ReferenceCoordinateContract:
    """A field-level contract for one coordinate operation."""

    operation: ReferenceCoordinateOperation
    capability_id: str
    title: str
    required_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    safety_boundary: str
    issue_codes: tuple[str, ...]
    supported_states: tuple[str, ...]

    def __post_init__(self) -> None:
        require_non_empty(self.capability_id, "capability ID")
        require_non_empty(self.title, "contract title")
        require_non_empty(self.safety_boundary, "safety boundary")
        if not self.required_fields:
            raise ValidationError("contract requires input fields")
        if not self.output_fields:
            raise ValidationError("contract requires output fields")
        if len(set(self.required_fields)) != len(self.required_fields):
            raise ValidationError("contract required fields must be unique")
        if len(set(self.output_fields)) != len(self.output_fields):
            raise ValidationError("contract output fields must be unique")
        if not self.issue_codes:
            raise ValidationError("contract requires issue codes")
        if not self.supported_states:
            raise ValidationError("contract requires supported states")

    def validate_payload(self, payload: dict[str, Any]) -> tuple[str, ...]:
        if not isinstance(payload, dict):
            return ("payload_not_object",)
        return tuple(field for field in self.required_fields if field not in payload)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ReferenceCoordinateContractRegistry:
    """Deterministic registry for C01-C04 operation contracts."""

    def __init__(self, contracts: tuple[ReferenceCoordinateContract, ...]) -> None:
        if not contracts:
            raise ValidationError("contract registry must not be empty")
        operations = tuple(contract.operation for contract in contracts)
        capabilities = tuple(contract.capability_id for contract in contracts)
        if len(set(operations)) != len(operations):
            raise ValidationError("contract operations must be unique")
        if len(set(capabilities)) != len(capabilities):
            raise ValidationError("contract capability IDs must be unique")
        self._contracts = {contract.operation: contract for contract in contracts}

    def get(self, operation: ReferenceCoordinateOperation | str) -> ReferenceCoordinateContract:
        try:
            return self._contracts[ReferenceCoordinateOperation(operation)]
        except (KeyError, ValueError) as exc:
            raise ValidationError(f"unknown reference-coordinate operation: {operation}") from exc

    def all(self) -> tuple[ReferenceCoordinateContract, ...]:
        return tuple(self._contracts[operation] for operation in ReferenceCoordinateOperation)

    def manifest(self) -> dict[str, Any]:
        contracts = tuple(contract.to_dict() for contract in self.all())
        return {
            "registry_version": "reference-coordinate-contracts-2026.08",
            "capability_ids": tuple(contract.capability_id for contract in self.all()),
            "operation_count": len(contracts),
            "contracts": contracts,
            "content_address": content_hash(contracts),
        }


def default_reference_coordinate_contracts() -> ReferenceCoordinateContractRegistry:
    """Return the four release contracts used by the evidence gate."""

    return ReferenceCoordinateContractRegistry(
        (
            ReferenceCoordinateContract(
                operation=ReferenceCoordinateOperation.REFERENCE_REGISTRY,
                capability_id="GNC-D04-C01",
                title="Canonical reference assembly registry",
                required_fields=("query",),
                output_fields=(
                    "resolved_assembly",
                    "canonical_name",
                    "species",
                    "release",
                    "aliases",
                    "content_address",
                ),
                safety_boundary=(
                    "Assembly alias resolution is not sequence validation and does not imply "
                    "that two assemblies are biologically equivalent."
                ),
                issue_codes=(
                    "reference_alias_resolved",
                    "reference_alias_unknown",
                    "reference_alias_ambiguous",
                ),
                supported_states=("supported", "abstained", "invalid"),
            ),
            ReferenceCoordinateContract(
                operation=ReferenceCoordinateOperation.LIFTOVER_CHAIN,
                capability_id="GNC-D04-C02",
                title="Explicit chain segment liftover",
                required_fields=(
                    "chain_text",
                    "source_assembly",
                    "target_assembly",
                    "variant",
                ),
                output_fields=(
                    "parsed_segment_count",
                    "parse_issue_count",
                    "projection_state",
                    "mapping_id",
                    "projected_build",
                    "content_address",
                ),
                safety_boundary=(
                    "Only supplied equal-length segments are used; missing, competing, "
                    "breakend, and cross-species mappings remain reviewable."
                ),
                issue_codes=(
                    "chain_parsed",
                    "chain_parse_issue",
                    "chain_unmapped",
                    "chain_competing",
                    "chain_breakend_abstained",
                ),
                supported_states=("supported", "abstained", "partial", "invalid"),
            ),
            ReferenceCoordinateContract(
                operation=ReferenceCoordinateOperation.LIFTOVER_AMBIGUITY,
                capability_id="GNC-D04-C03",
                title="Liftover ambiguity scorer",
                required_fields=("segments", "query_interval"),
                output_fields=(
                    "candidate_mapping_ids",
                    "candidate_count",
                    "score",
                    "state",
                    "content_address",
                ),
                safety_boundary=(
                    "Competing mapping candidates are retained and never reduced to a chosen "
                    "coordinate by score alone."
                ),
                issue_codes=(
                    "ambiguity_unique",
                    "ambiguity_competing",
                    "ambiguity_absent",
                ),
                supported_states=("supported", "ambiguous", "abstained", "invalid"),
            ),
            ReferenceCoordinateContract(
                operation=ReferenceCoordinateOperation.PANGENOME_COORDINATE,
                capability_id="GNC-D04-C04",
                title="Pangenome path coordinate mapper",
                required_fields=("paths", "query_interval"),
                output_fields=(
                    "candidate_path_ids",
                    "candidate_count",
                    "state",
                    "sequence_ids",
                    "content_address",
                ),
                safety_boundary=(
                    "Declared path containment is reported as coordinate evidence, not as "
                    "sequence identity, haplotype truth, or clinical interpretation."
                ),
                issue_codes=(
                    "pangenome_unique",
                    "pangenome_multiple",
                    "pangenome_absent",
                ),
                supported_states=("supported", "ambiguous", "abstained", "invalid"),
            ),
        )
    )


__all__ = [
    "ReferenceCoordinateContract",
    "ReferenceCoordinateContractRegistry",
    "default_reference_coordinate_contracts",
]
