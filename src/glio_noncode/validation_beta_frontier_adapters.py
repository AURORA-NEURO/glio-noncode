"""Strict adapter registry for validation-beta frontier operation inputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .serialization import content_hash, jsonable, require_non_empty
from .validation_beta_frontier_contracts import default_validation_beta_frontier_contracts
from .validation_beta_frontier_public_data import ValidationBetaFrontierOperation


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierAdapterSpec:
    operation: ValidationBetaFrontierOperation
    adapter_id: str
    input_format: str
    required_keys: tuple[str, ...]
    normalization_notes: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.adapter_id, "adapter_id")
        require_non_empty(self.input_format, "input_format")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierAdapterResult:
    operation: ValidationBetaFrontierOperation
    adapter_id: str
    accepted: bool
    normalized_payload: Mapping[str, Any]
    issues: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierAdapterRegistry:
    specs: tuple[ValidationBetaFrontierAdapterSpec, ...]
    content_address: str

    def for_operation(self, operation: ValidationBetaFrontierOperation | str) -> ValidationBetaFrontierAdapterSpec:
        selected = operation.value if isinstance(operation, ValidationBetaFrontierOperation) else str(operation)
        for spec in self.specs:
            if spec.operation.value == selected:
                return spec
        raise KeyError(selected)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_validation_beta_frontier_adapters() -> ValidationBetaFrontierAdapterRegistry:
    """Return one deterministic adapter specification per operation."""

    contracts = default_validation_beta_frontier_contracts()
    notes = {
        ValidationBetaFrontierOperation.CRISPR_DESIGN: ("targets are parsed as ValidationBetaTarget records", "CRISPRi and CRISPRa modes are evaluated independently"),
        ValidationBetaFrontierOperation.BASE_EDITING: ("reference and alternate alleles are retained", "single-base chemistry gates remain explicit"),
        ValidationBetaFrontierOperation.PRIME_EDITING: ("PBS and RTT lengths remain declared inputs", "long edits are held before candidate generation"),
        ValidationBetaFrontierOperation.ALLELE_REPORTER: ("reference and alternate constructs remain paired", "construct budget is applied after pairing"),
        ValidationBetaFrontierOperation.MODEL_ELIGIBILITY: ("context fields are not inferred", "model-system filters are exact"),
        ValidationBetaFrontierOperation.GUIDE_OLIGO: ("TSV/JSON source text is adapted losslessly", "malformed rows retain row-level hashes"),
        ValidationBetaFrontierOperation.CONTROLS_RANDOMIZATION: ("seeds and replicate counts are explicit", "assignment order is deterministic but not execution"),
        ValidationBetaFrontierOperation.POWER_REPLICATION: ("effect and variance remain visible", "normal approximation is labeled as a planning proxy"),
    }
    specs: list[ValidationBetaFrontierAdapterSpec] = []
    for operation in ValidationBetaFrontierOperation:
        contract = contracts.for_operation(operation)
        body = {"operation": operation, "adapter_id": f"validation-beta-{operation.value}-adapter", "input_format": "mapping", "required_keys": contract.input_fields, "normalization_notes": notes[operation]}
        specs.append(ValidationBetaFrontierAdapterSpec(**body, content_address=content_hash(body, prefix="validation-beta-adapter")))
    body = {"specs": tuple(specs)}
    return ValidationBetaFrontierAdapterRegistry(specs=tuple(specs), content_address=content_hash(body, prefix="validation-beta-adapter-registry"))


def validate_validation_beta_frontier_payload(
    operation: ValidationBetaFrontierOperation | str,
    payload: Mapping[str, Any],
) -> ValidationBetaFrontierAdapterResult:
    """Validate and shallow-normalize a payload before execution."""

    spec = default_validation_beta_frontier_adapters().for_operation(operation)
    issues = tuple(key for key in spec.required_keys if key not in payload)
    normalized = dict(payload) if not issues else {}
    body = {"operation": spec.operation, "adapter_id": spec.adapter_id, "accepted": not issues, "normalized_payload": normalized, "issues": issues}
    return ValidationBetaFrontierAdapterResult(**body, content_address=content_hash(body, prefix="validation-beta-adapter-result"))


__all__ = [
    "ValidationBetaFrontierAdapterRegistry",
    "ValidationBetaFrontierAdapterResult",
    "ValidationBetaFrontierAdapterSpec",
    "default_validation_beta_frontier_adapters",
    "validate_validation_beta_frontier_payload",
]
