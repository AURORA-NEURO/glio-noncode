"""Typed contracts for Domain 05 C01–C04 regulatory atlas operations."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .regulatory_atlas_public_data import RegulatoryAtlasOperation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class RegulatoryAtlasContract:
    """Input, output, state, issue, and safety boundary for an operation."""

    capability_id: str
    operation: RegulatoryAtlasOperation
    title: str
    required_input_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    accepted_states: tuple[str, ...]
    review_states: tuple[str, ...]
    issue_codes: tuple[str, ...]
    boundary: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("capability_id", "title", "boundary", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.required_input_fields or not self.output_fields:
            raise ValidationError("regulatory atlas contract fields cannot be empty")
        if len(set(self.required_input_fields)) != len(self.required_input_fields):
            raise ValidationError("regulatory atlas inputs must be unique")
        if len(set(self.output_fields)) != len(self.output_fields):
            raise ValidationError("regulatory atlas outputs must be unique")
        if set(self.accepted_states) & set(self.review_states):
            raise ValidationError("accepted and review states must be disjoint")
        if not self.issue_codes:
            raise ValidationError("regulatory atlas contract requires issue codes")

    def validate_payload(self, payload: Any) -> tuple[str, ...]:
        if not isinstance(payload, dict):
            return ("payload_not_object",)
        return tuple(field for field in self.required_input_fields if field not in payload)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class RegulatoryAtlasContractRegistry:
    """Ordered contract registry with strict identity uniqueness."""

    def __init__(self, contracts: Iterable[RegulatoryAtlasContract]) -> None:
        values = tuple(contracts)
        if not values:
            raise ValidationError("regulatory atlas contract registry cannot be empty")
        capability_ids = [contract.capability_id for contract in values]
        operations = [contract.operation for contract in values]
        if len(set(capability_ids)) != len(capability_ids):
            raise ValidationError("duplicate regulatory atlas capability")
        if len(set(operations)) != len(operations):
            raise ValidationError("duplicate regulatory atlas operation")
        self._contracts = values
        self._by_operation = {contract.operation: contract for contract in values}
        self._by_capability = {contract.capability_id: contract for contract in values}

    @property
    def contracts(self) -> tuple[RegulatoryAtlasContract, ...]:
        return self._contracts

    def by_operation(self, operation: RegulatoryAtlasOperation | str) -> RegulatoryAtlasContract:
        try:
            key = (
                operation
                if isinstance(operation, RegulatoryAtlasOperation)
                else RegulatoryAtlasOperation(operation)
            )
            return self._by_operation[key]
        except (KeyError, ValueError) as exc:
            raise ValidationError(f"unknown regulatory atlas operation: {operation}") from exc

    def by_capability(self, capability_id: str) -> RegulatoryAtlasContract:
        try:
            return self._by_capability[capability_id]
        except KeyError as exc:
            raise ValidationError(f"unknown regulatory atlas capability: {capability_id}") from exc

    def manifest(self) -> dict[str, Any]:
        body = {"contracts": self._contracts}
        return {
            "contracts": [contract.to_dict() for contract in self._contracts],
            "content_address": content_hash(body),
        }


def default_regulatory_atlas_contracts() -> RegulatoryAtlasContractRegistry:
    """Return the four C01–C04 contracts in capability order."""

    definitions = (
        (
            "GNC-D05-C01",
            RegulatoryAtlasOperation.CCRE_PARSE,
            "ENCODE SCREEN-shaped cCRE track parsing",
            ("input_text", "input_format", "source_id", "profile"),
            ("parse_state", "record_count", "issue_codes", "input_hash", "record_addresses"),
            ("supported",),
            ("partial", "abstained"),
            ("invalid_ccre_row", "invalid_ccre_json"),
            "BED/JSON cCRE records are parsed with source hashes and malformed rows quarantined; no activity is inferred.",
        ),
        (
            "GNC-D05-C02",
            RegulatoryAtlasOperation.BRAIN_CELL_PROFILE,
            "Brain cell-type cCRE profile query",
            ("input_text", "input_format", "source_id", "profile", "query", "context"),
            ("query_state", "match_count", "reason", "match_ids", "context_key"),
            ("supported",),
            ("absent", "out_of_domain", "ambiguous", "abstained"),
            (
                "invalid_ccre_row",
                "no_compatible_ccre",
                "ccre_context_mismatch",
                "ambiguous_ccre_match",
            ),
            "Brain cCRE overlap is context-gated and remains descriptive; absence is not a biological negative.",
        ),
        (
            "GNC-D05-C03",
            RegulatoryAtlasOperation.ADULT_GLIO_PROFILE,
            "Adult glioma cCRE profile query",
            ("input_text", "input_format", "source_id", "profile", "query", "context"),
            ("query_state", "match_count", "reason", "match_ids", "context_key"),
            ("supported",),
            ("absent", "out_of_domain", "ambiguous", "abstained"),
            (
                "invalid_ccre_row",
                "no_compatible_ccre",
                "ccre_context_mismatch",
                "ambiguous_ccre_match",
            ),
            "Adult glioma cCRE overlap retains source and context identity without promotion to activity or causality.",
        ),
        (
            "GNC-D05-C04",
            RegulatoryAtlasOperation.PEDIATRIC_GLIO_PROFILE,
            "Pediatric glioma cCRE profile query",
            ("input_text", "input_format", "source_id", "profile", "query", "context"),
            ("query_state", "match_count", "reason", "match_ids", "context_key"),
            ("supported",),
            ("absent", "out_of_domain", "ambiguous", "abstained"),
            (
                "invalid_ccre_row",
                "no_compatible_ccre",
                "ccre_context_mismatch",
                "ambiguous_ccre_match",
            ),
            "Pediatric glioma context remains age-qualified and is not transported into adult evidence.",
        ),
    )
    contracts: list[RegulatoryAtlasContract] = []
    for definition in definitions:
        capability_id, operation, title, required, output, accepted, review, issues, boundary = (
            definition
        )
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
        contracts.append(RegulatoryAtlasContract(**body, content_address=content_hash(body)))
    return RegulatoryAtlasContractRegistry(contracts)


__all__ = [
    "RegulatoryAtlasContract",
    "RegulatoryAtlasContractRegistry",
    "default_regulatory_atlas_contracts",
]
