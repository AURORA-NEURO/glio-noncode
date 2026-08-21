"""Operation contracts for the Domain 02 structural evidence boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .structural_public_data import StructuralOperation


@dataclass(frozen=True, slots=True)
class StructuralOperationContract:
    """Declared input/output and review behavior for one structural operation."""

    contract_id: str
    capability_id: str
    operation: StructuralOperation
    input_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    required_provenance: tuple[str, ...]
    accepted_result_states: tuple[str, ...]
    review_result_states: tuple[str, ...]
    safety_notes: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in ("contract_id", "capability_id"):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if not self.input_fields or not self.output_fields:
            raise ValidationError("structural operation contracts require input and output fields")
        if not self.accepted_result_states or not self.review_result_states:
            raise ValidationError("structural operation contracts require accepted and review states")
        if len(self.input_fields) != len(set(self.input_fields)):
            raise ValidationError("structural contract input fields must be unique")
        if len(self.output_fields) != len(set(self.output_fields)):
            raise ValidationError("structural contract output fields must be unique")

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
class StructuralContractRegistry:
    """Deterministic lookup table for C01-C04 contracts."""

    contracts: tuple[StructuralOperationContract, ...]

    def __post_init__(self) -> None:
        if not self.contracts:
            raise ValidationError("structural contract registry must not be empty")
        IDs = [contract.contract_id for contract in self.contracts]
        if len(IDs) != len(set(IDs)):
            raise ValidationError("structural contract IDs must be unique")

    def get(self, operation: StructuralOperation | str) -> StructuralOperationContract:
        selected = StructuralOperation(operation)
        for contract in self.contracts:
            if contract.operation == selected:
                return contract
        raise ValidationError(f"no structural contract for operation {selected.value}")

    def manifest(self) -> dict[str, Any]:
        body = {
            "schema_version": "structural-contracts-v1",
            "contract_count": len(self.contracts),
            "contracts": self.contracts,
        }
        return jsonable(body) | {"content_address": content_hash(body)}


def default_structural_contract_registry() -> StructuralContractRegistry:
    """Return the four contracts used by the public structural fixture."""

    return StructuralContractRegistry(
        contracts=(
            StructuralOperationContract(
                "GNC-D02-C01-contract",
                "GNC-D02-C01",
                StructuralOperation.RECONSTRUCTION,
                (
                    "records",
                    "record_id",
                    "chromosome",
                    "position",
                    "alternate",
                    "info",
                    "sample",
                    "context_key",
                    "source_id",
                ),
                (
                    "events",
                    "issues",
                    "deferred_count",
                    "content_address",
                ),
                ("source_id", "raw_hash", "context_key", "record_ids"),
                ("eventful", "empty"),
                ("error", "warning", "review-issue"),
                (
                    "reciprocal mates are required",
                    "symbolic END is required",
                    "phased paths remain separate from canonical point variants",
                ),
            ),
            StructuralOperationContract(
                "GNC-D02-C02-contract",
                "GNC-D02-C02",
                StructuralOperation.CONSENSUS,
                (
                    "text",
                    "caller_id",
                    "caller_version",
                    "event_id",
                    "chromosome",
                    "start",
                    "end",
                    "event_type",
                    "support",
                    "breakpoint_tolerance",
                ),
                (
                    "observations",
                    "consensus",
                    "issues",
                    "content_address",
                ),
                ("source_id", "raw_hash", "caller_version", "source_line"),
                ("supported", "partial", "ambiguous", "mixed"),
                ("review-issue", "empty"),
                (
                    "caller-level observations remain retained",
                    "median coordinates are reported, not promoted to truth",
                    "disagreement is visible in the result state",
                ),
            ),
            StructuralOperationContract(
                "GNC-D02-C03-contract",
                "GNC-D02-C03",
                StructuralOperation.COMPLEX_RESOLUTION,
                (
                    "events",
                    "event_id",
                    "breakends",
                    "chromosome",
                    "position",
                    "mate_id",
                    "context_key",
                ),
                (
                    "resolutions",
                    "paths",
                    "ambiguities",
                    "issues",
                    "content_address",
                ),
                ("event_ids", "breakpoint_nodes", "context_key", "source_id"),
                ("ambiguous", "partial", "empty"),
                ("review-issue",),
                (
                    "shared loci form components",
                    "alternative paths remain explicit",
                    "no canonical complex identity is selected",
                ),
            ),
            StructuralOperationContract(
                "GNC-D02-C04-contract",
                "GNC-D02-C04",
                StructuralOperation.COPY_NUMBER,
                (
                    "segments",
                    "segment_id",
                    "caller_id",
                    "chromosome",
                    "start",
                    "end",
                    "copy_number",
                    "value_tolerance",
                ),
                (
                    "segments",
                    "caller_ids",
                    "disagreement",
                    "issues",
                    "content_address",
                ),
                ("source_id", "raw_hash", "source_segment_ids", "context_key"),
                ("supported", "ambiguous", "partial", "mixed"),
                ("review-issue", "empty"),
                (
                    "segments are split at every observed boundary",
                    "median copy number is a reported view",
                    "caller disagreement is retained per interval",
                ),
            ),
        )
    )


__all__ = [
    "StructuralContractRegistry",
    "StructuralOperationContract",
    "default_structural_contract_registry",
]
