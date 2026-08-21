"""Typed capability contracts for Domain 06 C13-C16."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_frontier_public_data import SequenceFrontierOperation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class SequenceFrontierContract:
    capability_id: str
    operation: SequenceFrontierOperation
    title: str
    required_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    issue_codes: tuple[str, ...]
    evidence_boundary: str
    accepted_states: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in ("capability_id", "title", "evidence_boundary", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.required_fields or not self.output_fields or not self.issue_codes:
            raise ValueError("sequence frontier contracts require fields and issue vocabulary")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceFrontierContractRegistry:
    contracts: tuple[SequenceFrontierContract, ...]
    content_address: str

    def __post_init__(self) -> None:
        if {item.operation for item in self.contracts} != set(SequenceFrontierOperation):
            raise ValueError("sequence frontier contracts must cover every operation")

    def by_operation(self, operation: SequenceFrontierOperation) -> SequenceFrontierContract:
        for contract in self.contracts:
            if contract.operation is operation:
                return contract
        raise KeyError(operation)

    def manifest(self) -> dict[str, Any]:
        return {
            "contracts": [item.to_dict() for item in self.contracts],
            "content_address": self.content_address,
        }


def _contract(
    capability_id: str,
    operation: SequenceFrontierOperation,
    title: str,
    required: tuple[str, ...],
    outputs: tuple[str, ...],
    issues: tuple[str, ...],
    accepted: tuple[str, ...] = ("accepted",),
) -> SequenceFrontierContract:
    body = {
        "capability_id": capability_id,
        "operation": operation,
        "title": title,
        "required_fields": required,
        "output_fields": outputs,
        "issue_codes": issues,
        "evidence_boundary": "public_aggregate_non_patient",
        "accepted_states": accepted,
    }
    return SequenceFrontierContract(**body, content_address=content_hash(body))


def default_sequence_frontier_contracts() -> SequenceFrontierContractRegistry:
    common = ("input_format", "input_text", "source_id", "source_version", "context_key")
    contracts = (
        _contract(
            "GNC-D06-C13",
            SequenceFrontierOperation.ENHANCER_GRAMMAR,
            "enhancer grammar",
            common + ("minimum_coverage",),
            (
                "state",
                "pair_count",
                "compatible_pair_count",
                "coverage",
                "supported_ids",
                "review_ids",
            ),
            ("grammar_no_motif_hits", "grammar_coverage_below_floor", "sequence_context_mismatch"),
        ),
        _contract(
            "GNC-D06-C14",
            SequenceFrontierOperation.ALLELE_SATURATION,
            "allele saturation",
            common + ("minimum_effect",),
            ("state", "point_count", "positive_effect_ids", "review_ids", "mean_delta"),
            (
                "saturation_uncertainty_above_floor",
                "saturation_no_positive_effect",
                "sequence_context_mismatch",
            ),
        ),
        _contract(
            "GNC-D06-C15",
            SequenceFrontierOperation.ENSEMBLE_DISAGREEMENT,
            "ensemble disagreement",
            common + ("disagreement_threshold", "interval_multiplier"),
            ("state", "prediction_count", "stable_ids", "review_ids", "mean", "disagreement"),
            (
                "ensemble_disagreement_above_floor",
                "ensemble_insufficient_predictions",
                "sequence_context_mismatch",
            ),
        ),
        _contract(
            "GNC-D06-C16",
            SequenceFrontierOperation.SEQUENCE_EVIDENCE_PUBLISH,
            "sequence evidence publication",
            common + ("bundle_id", "model_ids"),
            ("state", "sequence_ids", "records_address", "bundle_address", "model_ids"),
            ("empty_sequence_records", "publish_metadata_invalid", "sequence_context_mismatch"),
            accepted=("published",),
        ),
    )
    return SequenceFrontierContractRegistry(contracts, content_hash({"contracts": contracts}))


__all__ = [
    "SequenceFrontierContract",
    "SequenceFrontierContractRegistry",
    "default_sequence_frontier_contracts",
]
