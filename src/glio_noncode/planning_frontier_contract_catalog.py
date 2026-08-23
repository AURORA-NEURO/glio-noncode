"""Operation contract catalog used by reviewers and integrations.

The catalog is separate from execution so consumers can inspect field shape,
boundary, accepted states, issue vocabulary, and evidence obligations without
running a planner.  It intentionally describes planning behavior rather than
claiming a biological result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .planning_frontier_contracts import PlanningOperation, PlanningState
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningContractEntry:
    operation: PlanningOperation
    capability_id: str
    purpose: str
    required_inputs: tuple[str, ...]
    optional_inputs: tuple[str, ...]
    output_fields: tuple[str, ...]
    issue_codes: tuple[str, ...]
    states: tuple[PlanningState, ...]
    evidence_boundary: str
    non_claims: tuple[str, ...]
    content_address: str

    def missing_fields(self, payload: Mapping[str, Any]) -> tuple[str, ...]:
        return tuple(field for field in self.required_inputs if field not in payload)

    def accepts_state(self, state: PlanningState | str) -> bool:
        selected = state if isinstance(state, PlanningState) else PlanningState(str(state))
        return selected in self.states

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningContractCatalog:
    entries: tuple[PlanningContractEntry, ...]
    catalog_version: str
    accepted: bool
    content_address: str

    def for_operation(self, operation: PlanningOperation | str) -> PlanningContractEntry:
        selected = operation if isinstance(operation, PlanningOperation) else PlanningOperation(str(operation))
        return next(item for item in self.entries if item.operation is selected)

    def validate(self, operation: PlanningOperation | str, payload: Mapping[str, Any]) -> dict[str, Any]:
        entry = self.for_operation(operation)
        missing = entry.missing_fields(payload)
        body = {"operation": entry.operation, "valid": not missing, "missing_fields": missing, "contract_address": entry.content_address}
        return body | {"content_address": content_hash(body, prefix="planning-contract-validation")}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


COMMON_STATES = tuple(PlanningState)
COMMON_NON_CLAIMS = (
    "does not establish model fidelity",
    "does not establish guide activity",
    "does not establish assay validity",
    "does not establish safety or clinical utility",
)


def _entry(operation: PlanningOperation, capability_id: str, purpose: str, required: tuple[str, ...], optional: tuple[str, ...], outputs: tuple[str, ...], issues: tuple[str, ...]) -> PlanningContractEntry:
    body = {
        "operation": operation,
        "capability_id": capability_id,
        "purpose": purpose,
        "required_inputs": required,
        "optional_inputs": optional,
        "output_fields": outputs,
        "issue_codes": issues,
        "states": COMMON_STATES,
        "evidence_boundary": "public_aggregate_planning_evidence",
        "non_claims": COMMON_NON_CLAIMS,
    }
    return PlanningContractEntry(**body, content_address=content_hash(body, prefix="planning-contract"))


def build_planning_contract_catalog() -> PlanningContractCatalog:
    entries = (
        _entry(PlanningOperation.MODEL_ELIGIBILITY, "GNC-D13-C09", "match declared model support to an exact context", ("request_id", "context_key", "model_system", "observations", "minimum_evidence_strength"), ("controls", "readouts"), ("state", "results", "eligible_count", "issue_codes"), ("context_mismatch", "context_not_declared_supported", "evidence_below_threshold", "no_model_observations", "no_declared_eligible_model_system")),
        _entry(PlanningOperation.GUIDE_OLIGO, "GNC-D13-C10", "adapt public guide and oligo rows with lossless identity", ("source_id", "source_version", "input_format", "text"), ("context_key",), ("state", "observations", "quarantined", "issue_codes"), ("invalid_guide_oligo_row", "context_mismatch", "empty_source")),
        _entry(PlanningOperation.CONTROLS_RANDOMIZATION, "GNC-D13-C11", "create reproducible control and replicate assignments", ("plan_id", "context_key", "targets", "control_types", "biological_replicates", "technical_replicates", "randomization_seed"), (), ("state", "assignments", "target_ids", "issue_codes"), ("context_mismatch", "missing_target_id", "no_targets", "control_types_missing")),
        _entry(PlanningOperation.POWER_REPLICATION, "GNC-D13-C12", "estimate repetitions from supplied effect and noise proxies", ("request_id", "context_key", "observations"), (), ("state", "results", "required_replicates", "replicate_shortfall", "issue_codes"), ("context_mismatch", "invalid_power_row", "no_power_observations")),
    )
    accepted = tuple(item.operation for item in entries) == tuple(PlanningOperation) and all(item.non_claims for item in entries)
    body = {"entries": entries, "catalog_version": "2026.08.d13-c09-c12.catalog.v1", "accepted": accepted}
    return PlanningContractCatalog(entries, body["catalog_version"], accepted, content_hash(body, prefix="planning-contract-catalog"))


__all__ = ["PlanningContractCatalog", "PlanningContractEntry", "build_planning_contract_catalog"]
