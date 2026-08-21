"""Typed contracts for Domain 05 C05–C08 molecular atlas operations."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .molecular_atlas_public_data import MolecularAtlasOperation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class MolecularAtlasContract:
    """Input, output, state, issue, and interpretation boundary."""

    capability_id: str
    operation: MolecularAtlasOperation
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
            raise ValidationError("molecular atlas contract fields cannot be empty")
        if len(set(self.required_input_fields)) != len(self.required_input_fields):
            raise ValidationError("molecular atlas inputs must be unique")
        if len(set(self.output_fields)) != len(self.output_fields):
            raise ValidationError("molecular atlas outputs must be unique")
        if set(self.accepted_states) & set(self.review_states):
            raise ValidationError("molecular atlas accepted and review states must be disjoint")
        if not self.issue_codes:
            raise ValidationError("molecular atlas contract requires issue codes")

    def validate_payload(self, payload: Any) -> tuple[str, ...]:
        if not isinstance(payload, dict):
            return ("payload_not_object",)
        return tuple(field for field in self.required_input_fields if field not in payload)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class MolecularAtlasContractRegistry:
    """Ordered registry with unique capability and operation identities."""

    def __init__(self, contracts: Iterable[MolecularAtlasContract]) -> None:
        values = tuple(contracts)
        if not values:
            raise ValidationError("molecular atlas contract registry cannot be empty")
        capability_ids = [contract.capability_id for contract in values]
        operations = [contract.operation for contract in values]
        if len(set(capability_ids)) != len(capability_ids):
            raise ValidationError("duplicate molecular atlas capability")
        if len(set(operations)) != len(operations):
            raise ValidationError("duplicate molecular atlas operation")
        self._contracts = values
        self._by_operation = {contract.operation: contract for contract in values}
        self._by_capability = {contract.capability_id: contract for contract in values}

    @property
    def contracts(self) -> tuple[MolecularAtlasContract, ...]:
        return self._contracts

    def by_operation(self, operation: MolecularAtlasOperation | str) -> MolecularAtlasContract:
        try:
            key = (
                operation
                if isinstance(operation, MolecularAtlasOperation)
                else MolecularAtlasOperation(operation)
            )
            return self._by_operation[key]
        except (KeyError, ValueError) as exc:
            raise ValidationError(f"unknown molecular atlas operation: {operation}") from exc

    def by_capability(self, capability_id: str) -> MolecularAtlasContract:
        try:
            return self._by_capability[capability_id]
        except KeyError as exc:
            raise ValidationError(f"unknown molecular atlas capability: {capability_id}") from exc

    def manifest(self) -> dict[str, Any]:
        body = {"contracts": self._contracts}
        return {
            "contracts": [contract.to_dict() for contract in self._contracts],
            "content_address": content_hash(body),
        }


def default_molecular_atlas_contracts() -> MolecularAtlasContractRegistry:
    """Return the four C05–C08 contracts in capability order."""

    query_inputs = (
        "input_text",
        "input_format",
        "source_id",
        "source_version",
        "molecular_state",
        "query",
        "context",
    )
    query_outputs = (
        "query_state",
        "match_count",
        "reason",
        "match_ids",
        "context_key",
        "molecular_state",
    )
    definitions = (
        (
            "GNC-D05-C05",
            MolecularAtlasOperation.IDH_MUTANT_PROFILE,
            "IDH-mutant molecular-state atlas profile",
            query_inputs,
            query_outputs,
            ("supported",),
            ("abstained", "out_of_domain", "ambiguous"),
            (
                "invalid_state_atlas_row",
                "no_state_atlas_overlap",
                "state_context_mismatch",
                "ambiguous_state_match",
            ),
            "IDH-mutant evidence remains state- and context-qualified; overlap is not a causal or clinical call.",
        ),
        (
            "GNC-D05-C06",
            MolecularAtlasOperation.IDH_WILDTYPE_PROFILE,
            "IDH-wildtype molecular-state atlas profile",
            query_inputs,
            query_outputs,
            ("supported",),
            ("abstained", "out_of_domain", "ambiguous"),
            (
                "invalid_state_atlas_row",
                "no_state_atlas_overlap",
                "state_context_mismatch",
                "ambiguous_state_match",
            ),
            "IDH-wildtype evidence is not borrowed from IDH-mutant or another context.",
        ),
        (
            "GNC-D05-C07",
            MolecularAtlasOperation.H3K27_ALTERED_PROFILE,
            "H3K27-altered molecular-state atlas profile",
            query_inputs,
            query_outputs,
            ("supported",),
            ("abstained", "out_of_domain", "ambiguous"),
            (
                "invalid_state_atlas_row",
                "no_state_atlas_overlap",
                "state_context_mismatch",
                "ambiguous_state_match",
            ),
            "H3K27-altered context remains age, territory, and cell-state qualified.",
        ),
        (
            "GNC-D05-C08",
            MolecularAtlasOperation.HISTONE_HARMONIZATION,
            "Replicate-aware histone-mark track harmonization",
            ("input_text", "input_format", "source_id", "source_version", "spread_tolerance"),
            (
                "harmonization_state",
                "interval_count",
                "median_signal",
                "signal_spread",
                "replicate_ids",
                "issue_codes",
            ),
            ("supported",),
            ("partial", "ambiguous", "abstained"),
            ("invalid_histone_row", "histone_single_replicate", "histone_signal_disagreement"),
            "Histone signal is a descriptive replicate summary, not a calibrated activity estimate.",
        ),
    )
    contracts: list[MolecularAtlasContract] = []
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
        contracts.append(MolecularAtlasContract(**body, content_address=content_hash(body)))
    return MolecularAtlasContractRegistry(contracts)


__all__ = [
    "MolecularAtlasContract",
    "MolecularAtlasContractRegistry",
    "default_molecular_atlas_contracts",
]
