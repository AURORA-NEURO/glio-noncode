"""Typed contracts for Domain 05 C09-C12 evidence adapters."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .atlas_alpha_evidence_public_data import AtlasAlphaEvidenceOperation
from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceContract:
    """Input, output, review states, issue vocabulary, and boundary."""

    capability_id: str
    operation: AtlasAlphaEvidenceOperation
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
            raise ValidationError("atlas alpha contract fields cannot be empty")
        if len(set(self.required_input_fields)) != len(self.required_input_fields):
            raise ValidationError("atlas alpha input fields must be unique")
        if len(set(self.output_fields)) != len(self.output_fields):
            raise ValidationError("atlas alpha output fields must be unique")
        if set(self.accepted_states) & set(self.review_states):
            raise ValidationError("atlas alpha accepted and review states must be disjoint")
        if not self.issue_codes:
            raise ValidationError("atlas alpha contract requires issue codes")

    def validate_payload(self, payload: Any) -> tuple[str, ...]:
        if not isinstance(payload, dict):
            return ("payload_not_object",)
        return tuple(field for field in self.required_input_fields if field not in payload)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class AtlasAlphaEvidenceContractRegistry:
    """Unique ordered capability and operation lookup."""

    def __init__(self, contracts: Iterable[AtlasAlphaEvidenceContract]) -> None:
        values = tuple(contracts)
        if not values:
            raise ValidationError("atlas alpha contract registry cannot be empty")
        capability_ids = [contract.capability_id for contract in values]
        operations = [contract.operation for contract in values]
        if len(set(capability_ids)) != len(capability_ids):
            raise ValidationError("duplicate atlas alpha capability")
        if len(set(operations)) != len(operations):
            raise ValidationError("duplicate atlas alpha operation")
        self._contracts = values
        self._by_operation = {contract.operation: contract for contract in values}
        self._by_capability = {contract.capability_id: contract for contract in values}

    @property
    def contracts(self) -> tuple[AtlasAlphaEvidenceContract, ...]:
        return self._contracts

    def by_operation(
        self, operation: AtlasAlphaEvidenceOperation | str
    ) -> AtlasAlphaEvidenceContract:
        try:
            key = (
                operation
                if isinstance(operation, AtlasAlphaEvidenceOperation)
                else AtlasAlphaEvidenceOperation(operation)
            )
            return self._by_operation[key]
        except (KeyError, ValueError) as exc:
            raise ValidationError(f"unknown atlas alpha operation: {operation}") from exc

    def by_capability(self, capability_id: str) -> AtlasAlphaEvidenceContract:
        try:
            return self._by_capability[capability_id]
        except KeyError as exc:
            raise ValidationError(f"unknown atlas alpha capability: {capability_id}") from exc

    def manifest(self) -> dict[str, Any]:
        return {
            "contracts": [contract.to_dict() for contract in self._contracts],
            "content_address": content_hash({"contracts": self._contracts}),
        }


def _contract(
    capability_id: str,
    operation: AtlasAlphaEvidenceOperation,
    title: str,
    required: tuple[str, ...],
    outputs: tuple[str, ...],
    issue_codes: tuple[str, ...],
    boundary: str,
) -> AtlasAlphaEvidenceContract:
    body = {
        "capability_id": capability_id,
        "operation": operation,
        "title": title,
        "required_input_fields": required,
        "output_fields": outputs,
        "accepted_states": ("supported",),
        "review_states": ("partial", "ambiguous", "abstained", "out_of_domain"),
        "issue_codes": issue_codes,
        "boundary": boundary,
    }
    return AtlasAlphaEvidenceContract(**body, content_address=content_hash(body))


def default_atlas_alpha_evidence_contracts() -> AtlasAlphaEvidenceContractRegistry:
    """Return the four explicit C09-C12 contracts."""

    common = ("input_text", "input_format", "source_id", "source_version")
    return AtlasAlphaEvidenceContractRegistry(
        (
            _contract(
                "GNC-D05-C09",
                AtlasAlphaEvidenceOperation.OPEN_CHROMATIN,
                "Open-chromatin track harmonizer",
                common + ("spread_tolerance", "minimum_signal"),
                (
                    "harmonization_state",
                    "observation_count",
                    "interval_count",
                    "signal_spreads",
                    "replicate_ids",
                    "issue_codes",
                ),
                (
                    "invalid_open_chromatin_row",
                    "context_mismatch",
                    "open_chromatin_signal_disagreement",
                ),
                "Accessibility intervals are descriptive observations and do not imply activity or causality.",
            ),
            _contract(
                "GNC-D05-C10",
                AtlasAlphaEvidenceOperation.METHYLATION,
                "Coverage-aware methylation track harmonizer",
                common + ("spread_tolerance",),
                (
                    "harmonization_state",
                    "observation_count",
                    "interval_count",
                    "coverage_totals",
                    "fraction_spreads",
                    "issue_codes",
                ),
                (
                    "invalid_methylation_row",
                    "context_mismatch",
                    "methylation_zero_coverage",
                    "methylation_fraction_disagreement",
                ),
                "Methylation fractions retain coverage and do not by themselves establish silencing.",
            ),
            _contract(
                "GNC-D05-C11",
                AtlasAlphaEvidenceOperation.REGULATORY_ROLE,
                "Enhancer-promoter-silencer role classifier",
                common + ("role_threshold", "methylation_silencer_threshold"),
                (
                    "classification_state",
                    "classification_count",
                    "roles",
                    "missing_channels",
                    "target_gene_ids",
                    "issue_codes",
                ),
                (
                    "invalid_regulatory_role_row",
                    "context_mismatch",
                    "regulatory_role_missing_channels",
                    "regulatory_role_ambiguity",
                ),
                "Role labels combine declared channels and are research classifications.",
            ),
            _contract(
                "GNC-D05-C12",
                AtlasAlphaEvidenceOperation.SUPER_ENHANCER,
                "Super-enhancer candidate atlas",
                common + ("minimum_constituents", "merge_gap_bp", "rank_quantile"),
                (
                    "atlas_state",
                    "constituent_count",
                    "candidate_count",
                    "candidate_ids",
                    "target_gene_ids",
                    "issue_codes",
                ),
                (
                    "invalid_enhancer_row",
                    "context_mismatch",
                    "no_super_enhancer_candidate",
                    "super_enhancer_partial_activity",
                ),
                "Ranked interval groupings are candidates, not causal regulatory claims.",
            ),
        )
    )


__all__ = [
    "AtlasAlphaEvidenceContract",
    "AtlasAlphaEvidenceContractRegistry",
    "default_atlas_alpha_evidence_contracts",
]
