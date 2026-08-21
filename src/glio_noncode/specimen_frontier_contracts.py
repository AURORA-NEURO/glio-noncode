"""Operation contracts for the Domain 03 C01-C04 evidence gate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .specimen_frontier_public_data import SpecimenFrontierOperation


@dataclass(frozen=True, slots=True)
class SpecimenFrontierOperationContract:
    """Declared inputs, outputs, provenance, and review semantics."""

    contract_id: str
    capability_id: str
    operation: SpecimenFrontierOperation
    input_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    required_provenance: tuple[str, ...]
    accepted_result_states: tuple[str, ...]
    review_result_states: tuple[str, ...]
    safety_notes: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in ("contract_id", "capability_id"):
            require_non_empty(str(getattr(self, field_name)), field_name)
        for field_name in (
            "input_fields",
            "output_fields",
            "required_provenance",
            "accepted_result_states",
            "review_result_states",
            "safety_notes",
        ):
            if not getattr(self, field_name):
                raise ValidationError(f"specimen frontier contract {field_name} must not be empty")
        for field_name in ("input_fields", "output_fields", "required_provenance"):
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValidationError(f"specimen frontier contract {field_name} must be unique")

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
class SpecimenFrontierContractRegistry:
    """Deterministic lookup table for C01-C04."""

    contracts: tuple[SpecimenFrontierOperationContract, ...]

    def __post_init__(self) -> None:
        if not self.contracts:
            raise ValidationError("specimen frontier contract registry must not be empty")
        contract_ids = [contract.contract_id for contract in self.contracts]
        operation_ids = [contract.operation.value for contract in self.contracts]
        if len(contract_ids) != len(set(contract_ids)):
            raise ValidationError("specimen frontier contract IDs must be unique")
        if len(operation_ids) != len(set(operation_ids)):
            raise ValidationError("specimen frontier contract operations must be unique")

    def get(self, operation: SpecimenFrontierOperation | str) -> SpecimenFrontierOperationContract:
        try:
            selected = SpecimenFrontierOperation(operation)
        except ValueError as exc:
            raise ValidationError(f"unknown specimen frontier operation: {operation}") from exc
        for contract in self.contracts:
            if contract.operation == selected:
                return contract
        raise ValidationError(f"no specimen frontier contract for operation {selected.value}")

    def manifest(self) -> dict[str, Any]:
        body = {
            "schema_version": "specimen-frontier-contracts-v1",
            "contract_count": len(self.contracts),
            "contracts": tuple(sorted(self.contracts, key=lambda item: item.contract_id)),
        }
        return jsonable(body) | {"content_address": content_hash(body)}


def default_specimen_frontier_contract_registry() -> SpecimenFrontierContractRegistry:
    """Return the four C01-C04 operation contracts."""

    return SpecimenFrontierContractRegistry(
        contracts=(
            SpecimenFrontierOperationContract(
                contract_id="GNC-D03-C01-contract",
                capability_id="GNC-D03-C01",
                operation=SpecimenFrontierOperation.ONTOLOGY_MAPPING,
                input_fields=(
                    "records",
                    "sample_id",
                    "specimen_id",
                    "subject_id",
                    "relationship",
                    "specimen_type",
                    "timepoint",
                    "context_key",
                ),
                output_fields=(
                    "observations",
                    "mappings",
                    "ambiguous",
                    "partial",
                    "issues",
                    "content_address",
                ),
                required_provenance=(
                    "source_id",
                    "observation_id",
                    "sample_id",
                    "raw_hash",
                    "context_key",
                ),
                accepted_result_states=("supported",),
                review_result_states=("partial", "ambiguous", "invalid"),
                safety_notes=(
                    "declared sample labels are mapped without inventing a subject relationship",
                    "conflicting subject or relationship labels remain ambiguous review evidence",
                    "ontology mapping is not a clinical identity assertion or specimen diagnosis",
                ),
            ),
            SpecimenFrontierOperationContract(
                contract_id="GNC-D03-C02-contract",
                capability_id="GNC-D03-C02",
                operation=SpecimenFrontierOperation.MATCHED_NORMAL,
                input_fields=(
                    "records",
                    "tumor_sample_id",
                    "normal_sample_id",
                    "subject_id",
                    "relationship",
                    "timepoint",
                    "context_key",
                ),
                output_fields=(
                    "tumors",
                    "supported",
                    "ambiguous",
                    "abstained",
                    "issues",
                    "content_address",
                ),
                required_provenance=(
                    "source_id",
                    "tumor_observation_id",
                    "normal_observation_id",
                    "subject_id",
                    "context_key",
                ),
                accepted_result_states=("supported",),
                review_result_states=("ambiguous", "abstained", "invalid"),
                safety_notes=(
                    "a normal is matched only when the same declared subject identifier is present",
                    "one-to-many normals remain ambiguous and are never selected by ordering",
                    "a missing normal is abstention, not evidence that a sample is tumor-only",
                ),
            ),
            SpecimenFrontierOperationContract(
                contract_id="GNC-D03-C03-contract",
                capability_id="GNC-D03-C03",
                operation=SpecimenFrontierOperation.PURITY_PLOIDY,
                input_fields=(
                    "text",
                    "sample_id",
                    "caller_id",
                    "caller_version",
                    "purity",
                    "ploidy",
                    "input_format",
                    "context_key",
                ),
                output_fields=(
                    "records",
                    "issues",
                    "percent_normalized",
                    "input_hash",
                    "content_address",
                ),
                required_provenance=(
                    "source_id",
                    "input_hash",
                    "raw_hash",
                    "caller_id",
                    "caller_version",
                    "context_key",
                ),
                accepted_result_states=("accepted",),
                review_result_states=("review", "invalid"),
                safety_notes=(
                    "percentage purity values are normalized to fractions without changing "
                    "source hashes",
                    "malformed rows are quarantined with source line and raw row addresses",
                    "purity and ploidy are measurements with caller provenance, not treatment "
                    "conclusions",
                ),
            ),
            SpecimenFrontierOperationContract(
                contract_id="GNC-D03-C04-contract",
                capability_id="GNC-D03-C04",
                operation=SpecimenFrontierOperation.SAMPLE_INTEGRITY,
                input_fields=(
                    "fingerprints",
                    "sample_id",
                    "declared_subject_id",
                    "observed_subject_id",
                    "contamination_fraction",
                    "discordance_rate",
                    "marker_count",
                    "context_key",
                ),
                output_fields=(
                    "fingerprints",
                    "clear",
                    "watch",
                    "flagged",
                    "abstained",
                    "issues",
                    "content_address",
                ),
                required_provenance=(
                    "source_id",
                    "sample_id",
                    "declared_subject_id",
                    "observed_subject_id",
                    "raw_hash",
                    "context_key",
                ),
                accepted_result_states=("clear",),
                review_result_states=("watch", "flagged", "abstained", "invalid"),
                safety_notes=(
                    "declared-versus-observed conflicts are flagged without claiming a "
                    "laboratory cause",
                    "incomplete fingerprint metrics abstain rather than becoming a clear result",
                    "thresholds are configurable triage parameters and are not external "
                    "calibration",
                ),
            ),
        )
    )


__all__ = [
    "SpecimenFrontierContractRegistry",
    "SpecimenFrontierOperationContract",
    "default_specimen_frontier_contract_registry",
]
