"""Contract registry for the four Domain 15 workspace surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_frontier_public_data import WorkspaceFrontierOperation


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierContract:
    contract_id: str
    operation: WorkspaceFrontierOperation
    version: str
    required_inputs: tuple[str, ...]
    required_outputs: tuple[str, ...]
    state_values: tuple[str, ...]
    issue_codes: tuple[str, ...]
    research_boundary: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("contract_id", "version", "research_boundary", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.required_inputs or not self.required_outputs:
            raise ValueError("workspace frontier contract requires input and output fields")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierContractRegistry:
    contracts: tuple[WorkspaceFrontierContract, ...]
    content_address: str

    def by_operation(self, operation: WorkspaceFrontierOperation) -> WorkspaceFrontierContract:
        return next(item for item in self.contracts if item.operation is operation)

    def issue_codes(self) -> tuple[str, ...]:
        return tuple(sorted({code for contract in self.contracts for code in contract.issue_codes}))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"issue_codes": list(self.issue_codes())}


def _contract(operation: WorkspaceFrontierOperation, inputs: tuple[str, ...], outputs: tuple[str, ...], issues: tuple[str, ...], boundary: str) -> WorkspaceFrontierContract:
    body = {
        "contract_id": f"workspace-frontier:{operation.value}",
        "operation": operation,
        "version": "2026.08.d15.v1",
        "required_inputs": inputs,
        "required_outputs": outputs,
        "state_values": ("supported", "partial", "absent", "abstained", "out_of_domain", "invalid"),
        "issue_codes": issues,
        "research_boundary": boundary,
    }
    return WorkspaceFrontierContract(**body, content_address=content_hash(body))


def default_workspace_frontier_contracts() -> WorkspaceFrontierContractRegistry:
    contracts = (
        _contract(
            WorkspaceFrontierOperation.CASE_WORKSPACE,
            ("case_id", "context_key", "variants", "candidate_elements", "accessibility"),
            ("workspace_id", "section_ids", "record_ids", "facets", "warnings", "input_address"),
            ("context_mismatch", "invalid_workspace_input", "duplicate_variant_id", "missing_dossier"),
            "case navigation is a research read model and never a diagnostic or treatment surface",
        ),
        _contract(
            WorkspaceFrontierOperation.COHORT_WORKSPACE,
            ("evidence_id", "query_id", "context_key", "records", "require_callable"),
            ("workspace_id", "query_record_count", "excluded_count", "section_ids", "facets"),
            ("context_mismatch", "no_matching_records", "invalid_workspace_input"),
            "cohort recurrence, callable counts, and matched controls are descriptive research outputs",
        ),
        _contract(
            WorkspaceFrontierOperation.VARIANT_EXPLORER,
            ("case", "variant_id"),
            ("workspace_id", "variant_record_id", "related_record_ids", "related_by_type", "warnings"),
            ("context_mismatch", "variant_absent", "invalid_workspace_input"),
            "only declared relationships are returned; proximity is not a mechanism claim",
        ),
        _contract(
            WorkspaceFrontierOperation.REGULATORY_TRACK_BROWSER,
            ("source_id", "genome_build", "text", "context_key", "accessibility"),
            ("workspace_id", "feature_count", "issue_count", "coordinate_labels", "facets"),
            ("context_mismatch", "track_parse_issue", "invalid_track_input"),
            "interval overlap is annotation navigation and does not establish activity or causality",
        ),
    )
    body = {"contracts": contracts}
    return WorkspaceFrontierContractRegistry(contracts=contracts, content_address=content_hash(body))


__all__ = [
    "WorkspaceFrontierContract",
    "WorkspaceFrontierContractRegistry",
    "default_workspace_frontier_contracts",
]
