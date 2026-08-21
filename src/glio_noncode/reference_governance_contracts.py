"""Typed contracts for Domain 04 C09–C12 reference governance."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .reference_governance_public_data import ReferenceGovernanceOperation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ReferenceGovernanceContract:
    """Input, output, state, issue, and safety boundary for one operation."""

    capability_id: str
    operation: ReferenceGovernanceOperation
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
            raise ValidationError("governance contract fields must not be empty")
        if len(set(self.required_input_fields)) != len(self.required_input_fields):
            raise ValidationError("governance contract input fields must be unique")
        if len(set(self.output_fields)) != len(self.output_fields):
            raise ValidationError("governance contract output fields must be unique")
        if set(self.accepted_states) & set(self.review_states):
            raise ValidationError("governance accepted and review states must be disjoint")
        if not self.issue_codes:
            raise ValidationError("governance contract requires issue codes")

    def validate_payload(self, payload: Any) -> tuple[str, ...]:
        if not isinstance(payload, dict):
            return ("payload_not_object",)
        return tuple(field for field in self.required_input_fields if field not in payload)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ReferenceGovernanceContractRegistry:
    """Ordered registry with strict capability and operation uniqueness."""

    def __init__(self, contracts: Iterable[ReferenceGovernanceContract]) -> None:
        values = tuple(contracts)
        if not values:
            raise ValidationError("governance contract registry cannot be empty")
        capability_ids = [contract.capability_id for contract in values]
        operations = [contract.operation for contract in values]
        if len(set(capability_ids)) != len(capability_ids):
            raise ValidationError("duplicate governance capability ID")
        if len(set(operations)) != len(operations):
            raise ValidationError("duplicate governance operation")
        self._contracts = values
        self._by_operation = {contract.operation: contract for contract in values}
        self._by_capability = {contract.capability_id: contract for contract in values}

    @property
    def contracts(self) -> tuple[ReferenceGovernanceContract, ...]:
        return self._contracts

    def by_operation(
        self, operation: ReferenceGovernanceOperation | str
    ) -> ReferenceGovernanceContract:
        try:
            key = (
                operation
                if isinstance(operation, ReferenceGovernanceOperation)
                else ReferenceGovernanceOperation(operation)
            )
            return self._by_operation[key]
        except (KeyError, ValueError) as exc:
            raise ValidationError(f"unknown governance operation: {operation}") from exc

    def by_capability(self, capability_id: str) -> ReferenceGovernanceContract:
        try:
            return self._by_capability[capability_id]
        except KeyError as exc:
            raise ValidationError(f"unknown governance capability: {capability_id}") from exc

    def manifest(self) -> dict[str, Any]:
        body = {"contracts": self._contracts}
        return {
            "contracts": [contract.to_dict() for contract in self._contracts],
            "content_address": content_hash(body),
        }


def default_reference_governance_contracts() -> ReferenceGovernanceContractRegistry:
    """Return the four C09–C12 contracts in capability order."""

    definitions = (
        (
            "GNC-D04-C09",
            ReferenceGovernanceOperation.GENE_ALIAS,
            "Gene alias and declared version resolution",
            ("queries", "records", "assembly"),
            ("catalog_state", "record_count", "resolution_state", "match_count", "issue_codes"),
            ("supported",),
            ("ambiguous", "partial", "abstained", "out_of_domain"),
            ("invalid_gene_alias_record", "gene_not_resolved", "gene_match_ambiguous"),
            "HGNC-shaped identifiers, symbols, aliases, assemblies, and versions are "
            "resolved only by declared catalog identity.",
        ),
        (
            "GNC-D04-C10",
            ReferenceGovernanceOperation.POPULATION_FREQUENCY,
            "Population frequency normalization and count retention",
            ("records", "genome_build", "variant_id"),
            (
                "observation_count",
                "summary_count",
                "adaptation_state",
                "issue_codes",
                "frequency_range",
            ),
            ("supported",),
            ("partial", "contradictory", "abstained", "out_of_domain"),
            ("invalid_population_frequency", "genome_build_mismatch"),
            "Public aggregate AC, AN, AF, population, ancestry, and build observations "
            "are descriptive evidence, not clinical classification.",
        ),
        (
            "GNC-D04-C11",
            ReferenceGovernanceOperation.REFERENCE_SNAPSHOT,
            "Content-addressed reference snapshot manifests",
            ("snapshot_id", "assembly", "source_id", "source_version", "resources"),
            ("resource_count", "manifest_hash", "snapshot_state", "issue_codes", "resource_ids"),
            ("supported",),
            ("partial", "contradictory", "abstained"),
            ("invalid_reference_resource", "manifest_hash_mismatch"),
            "Reference manifests retain checksum, size, URI, source version, and license "
            "metadata without fetching resource bytes.",
        ),
        (
            "GNC-D04-C12",
            ReferenceGovernanceOperation.LICENSE_RESTRICTION,
            "License and use-restriction evaluation",
            ("resources", "restrictions", "requested_use"),
            (
                "decision_count",
                "allowed_count",
                "missing_resource_ids",
                "evaluation_state",
                "issue_codes",
            ),
            ("supported",),
            ("partial", "contradictory", "abstained"),
            ("invalid_license_restriction", "conflicting_license_restrictions"),
            "Declared permissions, prohibitions, attribution, redistribution, commercial "
            "terms, and expiry are evaluated conservatively.",
        ),
    )
    contracts: list[ReferenceGovernanceContract] = []
    for definition in definitions:
        (
            capability_id,
            operation,
            title,
            required,
            output,
            accepted,
            review,
            issues,
            boundary,
        ) = definition
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
        contracts.append(ReferenceGovernanceContract(**body, content_address=content_hash(body)))
    return ReferenceGovernanceContractRegistry(contracts)


__all__ = [
    "ReferenceGovernanceContract",
    "ReferenceGovernanceContractRegistry",
    "default_reference_governance_contracts",
]
