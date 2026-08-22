"""Operation contracts for the context track release boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_context_frontier_public_data import ChromatinContextFrontierOperation
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierContract:
    contract_id: str
    operation: ChromatinContextFrontierOperation
    input_shape: tuple[str, ...]
    output_shape: tuple[str, ...]
    refusal_paths: tuple[str, ...]
    evidence_boundary: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.contract_id or not self.input_shape or not self.output_shape:
            raise ValidationError("context contract is incomplete")
        if not self.refusal_paths or not self.evidence_boundary:
            raise ValidationError("context contract requires refusal paths")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierContractReport:
    contracts: tuple[ChromatinContextFrontierContract, ...]
    accepted: bool
    unique_operations: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.contracts) != 4:
            raise ValidationError("four context contracts are required")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def for_operation(
        self, operation: ChromatinContextFrontierOperation
    ) -> ChromatinContextFrontierContract:
        for item in self.contracts:
            if item.operation is operation:
                return item
        raise KeyError(operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_chromatin_context_frontier_contracts(
    evidence_boundary: str = "public_aggregate_non_patient",
) -> ChromatinContextFrontierContractReport:
    common_refusals = (
        "context_mismatch",
        "malformed_row",
        "missing_measurement",
        "unsupported_transport",
    )
    contracts = (
        ChromatinContextFrontierContract(
            "d07-c01-track-retrieval",
            ChromatinContextFrontierOperation.TRACK_RETRIEVAL,
            ("track_text", "track_kind", "coordinate", "context_key", "source_receipt"),
            ("state", "observations", "median_signal", "replicate_spread", "issues"),
            common_refusals,
            evidence_boundary,
        ),
        ChromatinContextFrontierContract(
            "d07-c02-accessibility-delta",
            ChromatinContextFrontierOperation.ACCESSIBILITY_DELTA,
            ("reference_signal", "alternate_signal", "assay", "context_key", "source_receipt"),
            ("state", "delta", "relative_delta", "replicate_count", "limitations"),
            ("context_mismatch", "missing_measurement", "zero_baseline", "unsupported_transport"),
            evidence_boundary,
        ),
        ChromatinContextFrontierContract(
            "d07-c03-histone-context",
            ChromatinContextFrontierOperation.HISTONE_CONTEXT,
            ("track_text", "mark", "coordinate", "context_key", "source_receipt"),
            ("state", "mark_metadata", "replicate_spread", "issues"),
            common_refusals,
            evidence_boundary,
        ),
        ChromatinContextFrontierContract(
            "d07-c04-h3k27ac",
            ChromatinContextFrontierOperation.H3K27AC_ACTIVITY,
            ("track_text", "element_id", "coordinate", "context_key", "source_receipt"),
            ("state", "signal", "replicate_count", "limitations"),
            common_refusals + ("target_linkage_missing",),
            evidence_boundary,
        ),
    )
    accepted = (
        evidence_boundary == "public_aggregate_non_patient"
        and len({item.operation for item in contracts}) == 4
        and all(item.evidence_boundary == evidence_boundary for item in contracts)
    )
    return ChromatinContextFrontierContractReport(
        contracts, accepted, len({item.operation for item in contracts})
    )


__all__ = [
    "ChromatinContextFrontierContract",
    "ChromatinContextFrontierContractReport",
    "build_chromatin_context_frontier_contracts",
]
