"""Typed contracts for Domain 04 C05–C08 reference annotation operations."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .reference_annotation_public_data import ReferenceAnnotationOperation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ReferenceAnnotationContract:
    """Input, output, state, and safety boundary for one annotation operation."""

    capability_id: str
    operation: ReferenceAnnotationOperation
    title: str
    required_input_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    accepted_states: tuple[str, ...]
    review_states: tuple[str, ...]
    issue_codes: tuple[str, ...]
    boundary: str
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "capability_id",
            "title",
            "boundary",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.required_input_fields or not self.output_fields:
            raise ValidationError("annotation contract fields must not be empty")
        if len(set(self.required_input_fields)) != len(self.required_input_fields):
            raise ValidationError("annotation contract input fields must be unique")
        if len(set(self.output_fields)) != len(self.output_fields):
            raise ValidationError("annotation contract output fields must be unique")
        if set(self.accepted_states) & set(self.review_states):
            raise ValidationError("annotation accepted and review states must be disjoint")
        if not self.issue_codes:
            raise ValidationError("annotation contract requires issue codes")

    def validate_payload(self, payload: Any) -> tuple[str, ...]:
        if not isinstance(payload, dict):
            return ("payload_not_object",)
        return tuple(field for field in self.required_input_fields if field not in payload)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ReferenceAnnotationContractRegistry:
    """Ordered registry with strict operation and capability uniqueness."""

    def __init__(self, contracts: Iterable[ReferenceAnnotationContract]) -> None:
        values = tuple(contracts)
        if not values:
            raise ValidationError("annotation contract registry cannot be empty")
        capability_ids = [contract.capability_id for contract in values]
        operations = [contract.operation for contract in values]
        if len(set(capability_ids)) != len(capability_ids):
            raise ValidationError("duplicate annotation capability ID")
        if len(set(operations)) != len(operations):
            raise ValidationError("duplicate annotation operation")
        self._contracts = values
        self._by_operation = {contract.operation: contract for contract in values}
        self._by_capability = {contract.capability_id: contract for contract in values}

    @property
    def contracts(self) -> tuple[ReferenceAnnotationContract, ...]:
        return self._contracts

    def by_operation(
        self, operation: ReferenceAnnotationOperation | str
    ) -> ReferenceAnnotationContract:
        try:
            key = (
                operation
                if isinstance(operation, ReferenceAnnotationOperation)
                else ReferenceAnnotationOperation(operation)
            )
            return self._by_operation[key]
        except (KeyError, ValueError) as exc:
            raise ValidationError(f"unknown annotation operation: {operation}") from exc

    def by_capability(self, capability_id: str) -> ReferenceAnnotationContract:
        try:
            return self._by_capability[capability_id]
        except KeyError as exc:
            raise ValidationError(f"unknown annotation capability: {capability_id}") from exc

    def manifest(self) -> dict[str, Any]:
        body = {"contracts": self._contracts}
        return {
            "contracts": [contract.to_dict() for contract in self._contracts],
            "content_address": content_hash(body),
        }


def default_reference_annotation_contracts() -> ReferenceAnnotationContractRegistry:
    """Return the four C05–C08 contracts in capability order."""

    definitions = (
        (
            "GNC-D04-C05",
            ReferenceAnnotationOperation.GENCODE_TRANSCRIPT,
            "GENCODE transcript catalog and exact versioned resolution",
            ("input_text", "input_format", "query", "assembly"),
            ("catalog_state", "record_count", "resolution_state", "match_count", "issue_codes"),
            ("supported",),
            ("ambiguous", "abstained"),
            ("invalid_gencode_row", "transcript_not_resolved", "ambiguous_transcript_match"),
            "Public GENCODE release-shaped annotation is parsed and resolved by declared identifiers; transcript choice is never inferred.",  # noqa: E501
        ),
        (
            "GNC-D04-C06",
            ReferenceAnnotationOperation.MANE_TRANSCRIPT,
            "MANE matched transcript catalog and cross-identifier resolution",
            ("input_text", "input_format", "query"),
            ("catalog_state", "record_count", "resolution_state", "match_count", "issue_codes"),
            ("supported",),
            ("ambiguous", "abstained"),
            ("invalid_mane_row", "mane_not_resolved", "ambiguous_mane_match"),
            "Public MANE-shaped records preserve RefSeq and Ensembl identifiers, status, and ambiguity without selecting a preferred row.",  # noqa: E501
        ),
        (
            "GNC-D04-C07",
            ReferenceAnnotationOperation.REGULATORY_ONTOLOGY,
            "Regulatory ontology catalog and declared identifier normalization",
            ("input_text", "input_format", "query"),
            ("catalog_state", "term_count", "normalization_state", "match_count", "issue_codes"),
            ("supported",),
            ("ambiguous", "abstained"),
            ("invalid_regulatory_term", "term_not_resolved", "term_match_ambiguous"),
            "Relation Ontology-shaped terms are matched only by declared IDs, labels, and aliases; lexical similarity is out of scope.",  # noqa: E501
        ),
        (
            "GNC-D04-C08",
            ReferenceAnnotationOperation.DISEASE_ONTOLOGY,
            "Disease ontology mapping and one-to-many target retention",
            ("input_text", "input_format", "query"),
            ("catalog_state", "mapping_count", "mapping_state", "match_count", "issue_codes"),
            ("supported",),
            ("ambiguous", "abstained"),
            ("disease_not_resolved", "disease_mapping_ambiguous", "invalid_disease_mapping"),
            "Mondo-shaped mappings preserve source identity and target plurality; mapping is terminology identity, not a clinical conclusion.",  # noqa: E501
        ),
    )
    contracts: list[ReferenceAnnotationContract] = []
    for (
        capability_id,
        operation,
        title,
        required,
        output,
        accepted,
        review,
        issues,
        boundary,
    ) in definitions:
        body = {
            "capability_id": capability_id,
            "operation": operation,
            "title": title,
            "required_input_fields": required,
            "output_fields": output,
            "accepted_states": accepted,
            "review_states": review,
            "issue_codes": issues,
            "boundary": boundary,
        }
        contracts.append(ReferenceAnnotationContract(**body, content_address=content_hash(body)))
    return ReferenceAnnotationContractRegistry(contracts)


__all__ = [
    "ReferenceAnnotationContract",
    "ReferenceAnnotationContractRegistry",
    "default_reference_annotation_contracts",
]
