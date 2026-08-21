"""Typed contracts for Domain 05 C13-C16 frontier atlas operations."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .frontier_atlas_public_data import FrontierAtlasOperation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class FrontierAtlasContract:
    capability_id: str
    operation: FrontierAtlasOperation
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
            raise ValidationError("frontier atlas contract fields cannot be empty")
        if len(set(self.required_input_fields)) != len(self.required_input_fields) or len(
            set(self.output_fields)
        ) != len(self.output_fields):
            raise ValidationError("frontier atlas contract fields must be unique")
        if set(self.accepted_states) & set(self.review_states):
            raise ValidationError("frontier atlas accepted and review states must be disjoint")
        if not self.issue_codes:
            raise ValidationError("frontier atlas contract requires issue codes")

    def validate_payload(self, payload: Any) -> tuple[str, ...]:
        if not isinstance(payload, dict):
            return ("payload_not_object",)
        return tuple(field for field in self.required_input_fields if field not in payload)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class FrontierAtlasContractRegistry:
    """Unique operation and capability lookup."""

    def __init__(self, contracts: Iterable[FrontierAtlasContract]) -> None:
        values = tuple(contracts)
        if not values:
            raise ValidationError("frontier atlas contract registry cannot be empty")
        if len({contract.capability_id for contract in values}) != len(values) or len(
            {contract.operation for contract in values}
        ) != len(values):
            raise ValidationError("frontier atlas contracts must have unique identities")
        self._contracts = values
        self._by_operation = {contract.operation: contract for contract in values}
        self._by_capability = {contract.capability_id: contract for contract in values}

    @property
    def contracts(self) -> tuple[FrontierAtlasContract, ...]:
        return self._contracts

    def by_operation(self, operation: FrontierAtlasOperation | str) -> FrontierAtlasContract:
        try:
            key = (
                operation
                if isinstance(operation, FrontierAtlasOperation)
                else FrontierAtlasOperation(operation)
            )
            return self._by_operation[key]
        except (KeyError, ValueError) as exc:
            raise ValidationError(f"unknown frontier atlas operation: {operation}") from exc

    def by_capability(self, capability_id: str) -> FrontierAtlasContract:
        try:
            return self._by_capability[capability_id]
        except KeyError as exc:
            raise ValidationError(f"unknown frontier atlas capability: {capability_id}") from exc

    def manifest(self) -> dict[str, Any]:
        body = {"contracts": self._contracts}
        return {
            "contracts": [contract.to_dict() for contract in self._contracts],
            "content_address": content_hash(body),
        }


def _contract(
    capability_id: str,
    operation: FrontierAtlasOperation,
    title: str,
    required: tuple[str, ...],
    outputs: tuple[str, ...],
    issues: tuple[str, ...],
    boundary: str,
    accepted: tuple[str, ...] = ("accepted",),
) -> FrontierAtlasContract:
    body = {
        "capability_id": capability_id,
        "operation": operation,
        "title": title,
        "required_input_fields": required,
        "output_fields": outputs,
        "accepted_states": accepted,
        "review_states": ("review", "out_of_domain", "abstained", "invalid"),
        "issue_codes": issues,
        "boundary": boundary,
    }
    return FrontierAtlasContract(**body, content_address=content_hash(body))


def default_frontier_atlas_contracts() -> FrontierAtlasContractRegistry:
    """Return explicit contracts for C13-C16."""

    common = ("input_text", "input_format", "source_id", "source_version")
    return FrontierAtlasContractRegistry(
        (
            _contract(
                "GNC-D05-C13",
                FrontierAtlasOperation.BOUNDARY_ATLAS,
                "Insulator and boundary atlas",
                common + ("minimum_support",),
                ("state", "observation_count", "strong_boundary_ids", "review_ids", "issue_codes"),
                (
                    "invalid_boundary_interval",
                    "boundary_low_support",
                    "boundary_context_mismatch",
                    "unknown_boundary_orientation",
                ),
                "Boundary evidence retains interval, support, orientation, and context review; it is not a causal chromatin-domain claim.",
            ),
            _contract(
                "GNC-D05-C14",
                FrontierAtlasOperation.HOTSPOT_ATLAS,
                "Independent-source regulatory hotspot atlas",
                common + ("minimum_support_count", "minimum_concordance"),
                ("state", "observation_count", "supported_ids", "review_ids", "issue_codes"),
                (
                    "insufficient_hotspot_sources",
                    "hotspot_direction_disagreement",
                    "hotspot_context_mismatch",
                ),
                "Hotspot aggregation preserves independent source and direction evidence without selecting an unsupported mechanism.",
            ),
            _contract(
                "GNC-D05-C15",
                FrontierAtlasOperation.EVIDENCE_TIER,
                "Atlas evidence-tier adjudication",
                common + ("high_source_count", "high_consistency", "medium_consistency"),
                ("state", "decision_count", "high_confidence_ids", "review_ids", "issue_codes"),
                ("no_evidence_sources", "low_evidence_tier", "tier_context_mismatch"),
                "Evidence tiers are transparent review labels, not probabilities or clinical confidence.",
            ),
            _contract(
                "GNC-D05-C16",
                FrontierAtlasOperation.SNAPSHOT_PUBLISH,
                "Versioned atlas snapshot publisher",
                common + ("snapshot_id", "atlas_type", "version", "schema_version"),
                ("state", "record_count", "records_address", "snapshot_address", "issue_codes"),
                (
                    "empty_snapshot_records",
                    "snapshot_context_mismatch",
                    "snapshot_metadata_invalid",
                ),
                "Snapshots publish only context-qualified content addresses and are not clinical releases.",
            ),
        )
    )


__all__ = [
    "FrontierAtlasContract",
    "FrontierAtlasContractRegistry",
    "default_frontier_atlas_contracts",
]
