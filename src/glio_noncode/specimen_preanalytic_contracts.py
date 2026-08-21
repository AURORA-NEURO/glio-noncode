"""Typed operation contracts for Domain 03 C13-C16."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .specimen_preanalytic_public_data import SpecimenPreanalyticOperation


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticOperationContract:
    """Input/output and state boundary for one specimen operation."""

    contract_id: str
    contract_version: str
    operation: SpecimenPreanalyticOperation
    required_input_fields: tuple[str, ...]
    optional_input_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    positive_states: tuple[str, ...]
    review_states: tuple[str, ...]
    safety_boundary: str

    def __post_init__(self) -> None:
        for field in ("contract_id", "contract_version", "safety_boundary"):
            require_non_empty(str(getattr(self, field)), f"contract {field}")
        if not self.required_input_fields or not self.output_fields:
            raise ValidationError("contract input and output fields must not be empty")
        if len(set(self.required_input_fields)) != len(self.required_input_fields):
            raise ValidationError("contract required fields must be unique")
        if len(set(self.output_fields)) != len(self.output_fields):
            raise ValidationError("contract output fields must be unique")
        if set(self.required_input_fields) & set(self.optional_input_fields):
            raise ValidationError("required and optional fields must be disjoint")
        if not self.positive_states or not self.review_states:
            raise ValidationError("contract state sets must not be empty")
        if set(self.positive_states) & set(self.review_states):
            raise ValidationError("positive and review states must be disjoint")

    def accepts_result_state(self, state: str) -> bool:
        return state in self.positive_states or state in self.review_states

    def required_fields_present(self, payload: dict[str, Any]) -> bool:
        return all(
            field in payload and payload[field] not in (None, "", ())
            for field in self.required_input_fields
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticContractRegistry:
    """Stable lookup and manifest for the four operation contracts."""

    contracts: tuple[SpecimenPreanalyticOperationContract, ...]
    content_address: str

    def __post_init__(self) -> None:
        operations = [contract.operation for contract in self.contracts]
        if len(set(operations)) != len(operations):
            raise ValidationError("contract operations must be unique")
        if {item.value for item in operations} != {
            item.value for item in SpecimenPreanalyticOperation
        }:
            raise ValidationError("registry must cover all four specimen operations")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("contract manifest must be addressed")

    def get(
        self, operation: SpecimenPreanalyticOperation | str
    ) -> SpecimenPreanalyticOperationContract:
        target = SpecimenPreanalyticOperation(operation)
        for contract in self.contracts:
            if contract.operation == target:
                return contract
        raise KeyError(target.value)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "contract_count": len(self.contracts),
            "operation_ids": tuple(contract.operation.value for contract in self.contracts),
        }


def default_specimen_preanalytic_contracts() -> SpecimenPreanalyticContractRegistry:
    """Return the deterministic C13-C16 contract registry."""

    contracts = (
        SpecimenPreanalyticOperationContract(
            "specimen-preanalytic-c13",
            "specimen-preanalytic-contract-v1",
            SpecimenPreanalyticOperation.PREANALYTIC_QUALITY,
            ("specimen_id", "ischemia_minutes", "storage_temperature_c", "rna_integrity"),
            ("thresholds", "source_id"),
            ("pass_ids", "review_ids", "quality_scores", "failed_metrics"),
            ("accepted",),
            ("review",),
            "Threshold assessment retains missing metrics and does not establish clinical fitness.",
        ),
        SpecimenPreanalyticOperationContract(
            "specimen-preanalytic-c14",
            "specimen-preanalytic-contract-v1",
            SpecimenPreanalyticOperation.ASSAY_LINEAGE,
            ("node_id", "specimen_id", "protocol_id", "assay", "operator_id", "started_at"),
            ("parent_node_id",),
            ("nodes", "root_ids", "conflict_ids"),
            ("accepted",),
            ("review",),
            (
                "Declared assay derivation is retained without authenticating custody "
                "or biological ancestry."
            ),
        ),
        SpecimenPreanalyticOperationContract(
            "specimen-preanalytic-c15",
            "specimen-preanalytic-contract-v1",
            SpecimenPreanalyticOperation.IDENTITY_ADJUDICATION,
            ("specimen_id", "observed_identities"),
            ("minimum_agreement",),
            ("accepted_ids", "review_ids", "agreements", "conflicting_identities"),
            ("accepted",),
            ("review",),
            "Agreement and conflict are reported; no specimen identity is authenticated.",
        ),
        SpecimenPreanalyticOperationContract(
            "specimen-preanalytic-c16",
            "specimen-preanalytic-contract-v1",
            SpecimenPreanalyticOperation.CONTEXT_ENVELOPE,
            (
                "envelope_id",
                "specimen_ids",
                "lineage_address",
                "quality_address",
                "identity_address",
            ),
            ("context_key",),
            ("publication_address", "state", "specimen_ids"),
            ("published",),
            ("review",),
            (
                "Publication requires constituent receipt addresses and does not convert "
                "them into a clinical conclusion."
            ),
        ),
    )
    body = {"contracts": contracts}
    return SpecimenPreanalyticContractRegistry(contracts, content_hash(body))


def specimen_preanalytic_contract_manifest() -> dict[str, Any]:
    return default_specimen_preanalytic_contracts().to_dict()


__all__ = [
    "SpecimenPreanalyticContractRegistry",
    "SpecimenPreanalyticOperationContract",
    "default_specimen_preanalytic_contracts",
    "specimen_preanalytic_contract_manifest",
]
