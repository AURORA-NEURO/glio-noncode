"""Typed operation contracts for the Domain 13 validation-beta frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .serialization import content_hash, jsonable, require_non_empty
from .validation_beta_frontier_public_data import (
    ValidationBetaFrontierOperation,
)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierContract:
    operation: ValidationBetaFrontierOperation
    capability_ids: tuple[str, ...]
    input_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    accepted_states: tuple[str, ...]
    issue_codes: tuple[str, ...]
    evidence_boundary: str
    research_only: bool
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.operation.value, "operation")
        if not self.capability_ids or not self.input_fields or not self.output_fields:
            raise ValueError("validation beta frontier contracts require closed fields")
        if not self.accepted_states:
            raise ValueError("validation beta frontier contracts require state declarations")
        if not self.research_only:
            raise ValueError("validation beta frontier contracts must remain research-only")

    def validate_payload(self, payload: Mapping[str, Any]) -> tuple[str, ...]:
        """Return missing input fields without executing a planner."""

        if not isinstance(payload, Mapping):
            return ("payload_not_an_object",)
        return tuple(field for field in self.input_fields if field not in payload)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierContractRegistry:
    contracts: tuple[ValidationBetaFrontierContract, ...]
    content_address: str

    def __post_init__(self) -> None:
        if len(self.contracts) != len(ValidationBetaFrontierOperation):
            raise ValueError("validation beta frontier contract registry is not operation-closed")
        operations = tuple(item.operation for item in self.contracts)
        if len(set(operations)) != len(operations):
            raise ValueError("validation beta frontier contracts must have unique operations")

    def for_operation(self, operation: ValidationBetaFrontierOperation | str) -> ValidationBetaFrontierContract:
        selected = ValidationBetaFrontierOperation(str(operation.value if isinstance(operation, ValidationBetaFrontierOperation) else operation))
        for contract in self.contracts:
            if contract.operation is selected:
                return contract
        raise KeyError(selected.value)

    def manifest(self) -> dict[str, Any]:
        return {
            "contract_count": len(self.contracts),
            "contracts": tuple(item.to_dict() for item in self.contracts),
            "content_address": self.content_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.manifest()


def _contract(
    operation: ValidationBetaFrontierOperation,
    capability_id: str,
    inputs: tuple[str, ...],
    outputs: tuple[str, ...],
    issue_codes: tuple[str, ...],
) -> ValidationBetaFrontierContract:
    body = {
        "operation": operation,
        "capability_ids": (capability_id,),
        "input_fields": inputs,
        "output_fields": outputs,
        "accepted_states": ("ready_for_review", "partial", "blocked", "ambiguous", "out_of_domain", "abstained"),
        "issue_codes": issue_codes,
        "evidence_boundary": "public_aggregate_research_planning",
        "research_only": True,
    }
    return ValidationBetaFrontierContract(**body, content_address=content_hash(body, prefix="validation-beta-contract"))


def default_validation_beta_frontier_contracts() -> ValidationBetaFrontierContractRegistry:
    """Return the eight operation contracts in stable capability order."""

    contracts = (
        _contract(
            ValidationBetaFrontierOperation.CRISPR_DESIGN,
            "GNC-D13-C05",
            ("targets", "modes", "constraints"),
            ("state", "modes", "target_ids", "warnings"),
            ("context_mismatch", "max_guides_exceeded", "no_validation_targets", "no_candidate_meets_declared_constraints"),
        ),
        _contract(
            ValidationBetaFrontierOperation.BASE_EDITING,
            "GNC-D13-C06",
            ("targets", "constraints"),
            ("state", "modes", "target_ids", "warnings"),
            ("context_mismatch", "unsupported_base_edit_substitution", "no_validation_targets"),
        ),
        _contract(
            ValidationBetaFrontierOperation.PRIME_EDITING,
            "GNC-D13-C07",
            ("targets", "constraints"),
            ("state", "modes", "target_ids", "warnings"),
            ("context_mismatch", "edit_exceeds_prime_editing_length", "prime_editing_flank_shortage", "no_validation_targets"),
        ),
        _contract(
            ValidationBetaFrontierOperation.ALLELE_REPORTER,
            "GNC-D13-C08",
            ("targets", "constraints"),
            ("state", "modes", "target_ids", "warnings"),
            ("context_mismatch", "max_constructs_exceeded", "no_validation_targets"),
        ),
        _contract(
            ValidationBetaFrontierOperation.MODEL_ELIGIBILITY,
            "GNC-D13-C09",
            ("observations", "model_system", "minimum_evidence_strength"),
            ("state", "results", "issues", "warnings"),
            ("context_mismatch", "context_not_declared_supported", "no_declared_eligible_model_system"),
        ),
        _contract(
            ValidationBetaFrontierOperation.GUIDE_OLIGO,
            "GNC-D13-C10",
            ("source_id", "source_version", "input_format", "text"),
            ("state", "observations", "issues", "warnings"),
            ("invalid_guide_oligo_row", "context_mismatch"),
        ),
        _contract(
            ValidationBetaFrontierOperation.CONTROLS_RANDOMIZATION,
            "GNC-D13-C11",
            ("targets", "plan_id", "control_types", "biological_replicates", "technical_replicates", "randomization_seed"),
            ("state", "assignments", "target_ids", "blockers", "warnings"),
            ("context_mismatch", "missing_target_id", "no_targets"),
        ),
        _contract(
            ValidationBetaFrontierOperation.POWER_REPLICATION,
            "GNC-D13-C12",
            ("observations",),
            ("state", "results", "issues", "warnings"),
            ("context_mismatch", "invalid_power_row"),
        ),
    )
    body = {"contracts": contracts}
    return ValidationBetaFrontierContractRegistry(
        contracts=contracts,
        content_address=content_hash(body, prefix="validation-beta-contract-registry"),
    )


def validate_validation_beta_frontier_payload(
    operation: ValidationBetaFrontierOperation | str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate one payload against its declared contract."""

    registry = default_validation_beta_frontier_contracts()
    contract = registry.for_operation(operation)
    missing = contract.validate_payload(payload)
    body = {
        "operation": contract.operation,
        "valid": not missing,
        "missing_fields": missing,
        "contract_address": contract.content_address,
    }
    return body | {"content_address": content_hash(body, prefix="validation-beta-payload-validation")}


__all__ = [
    "ValidationBetaFrontierContract",
    "ValidationBetaFrontierContractRegistry",
    "default_validation_beta_frontier_contracts",
    "validate_validation_beta_frontier_payload",
]
