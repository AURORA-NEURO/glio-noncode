"""Operation contracts for the C05-C08 projection frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_beta_frontier_public_data import BetaFrontierOperation


@dataclass(frozen=True, slots=True)
class BetaFrontierContract:
    """Input, output, state, and boundary contract for one projection."""

    contract_id: str
    operation: BetaFrontierOperation
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
            raise ValueError("beta frontier contract requires input and output fields")

    def accepts_state(self, state: str) -> bool:
        return state in self.state_values

    def accepts_issue_set(self, issues: tuple[str, ...]) -> bool:
        return set(issues).issubset(self.issue_codes)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierContractRegistry:
    """Addressed registry with operation lookup helpers."""

    contracts: tuple[BetaFrontierContract, ...]
    content_address: str

    def by_operation(self, operation: BetaFrontierOperation) -> BetaFrontierContract:
        return next(item for item in self.contracts if item.operation is operation)

    def issue_codes(self) -> tuple[str, ...]:
        return tuple(sorted({code for item in self.contracts for code in item.issue_codes}))

    def state_values(self) -> tuple[str, ...]:
        return tuple(sorted({value for item in self.contracts for value in item.state_values}))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "issue_codes": list(self.issue_codes()),
            "state_values": list(self.state_values()),
        }


def _contract(
    operation: BetaFrontierOperation,
    inputs: tuple[str, ...],
    outputs: tuple[str, ...],
    issues: tuple[str, ...],
    boundary: str,
) -> BetaFrontierContract:
    body = {
        "contract_id": f"workspace-beta-frontier:{operation.value}",
        "operation": operation,
        "version": "2026.08.d15.c05-c08.v1",
        "required_inputs": inputs,
        "required_outputs": outputs,
        "state_values": ("supported", "partial", "complete", "incomplete", "absent", "abstained", "out_of_domain", "contradictory", "invalid"),
        "issue_codes": issues,
        "research_boundary": boundary,
    }
    return BetaFrontierContract(**body, content_address=content_hash(body))


def default_beta_frontier_contracts() -> BetaFrontierContractRegistry:
    """Return the public contract registry for all four surfaces."""

    contracts = (
        _contract(
            BetaFrontierOperation.TOPOLOGY_VIEWPORT,
            ("context_key", "loops", "contacts", "contact_scores", "activity_results", "focus"),
            ("viewport_id", "nodes", "edges", "state", "focus", "warnings"),
            ("context_mismatch", "invalid_projection_input", "no_topology_observations"),
            "topology edges are bounded research observations and do not establish mechanism",
        ),
        _contract(
            BetaFrontierOperation.CAUSAL_CHAIN,
            ("context_key", "results"),
            ("chain_id", "nodes", "edges", "state", "missing_mediator_kinds", "warnings"),
            ("context_mismatch", "missing_mediator", "contradictory_mediator"),
            "chain joins retain alternative and contradictory summaries without causal probability",
        ),
        _contract(
            BetaFrontierOperation.POSTERIOR_DECOMPOSITION,
            ("context_key", "posterior", "components"),
            ("view_id", "components", "component_total", "residual", "normalized_shares", "warnings"),
            ("foreign_component", "unreconciled_components", "missing_support"),
            "posterior values are declared research proxies with prior, calibration, and residual visible",
        ),
        _contract(
            BetaFrontierOperation.EVIDENCE_TABLE,
            ("context_key", "workspace", "filter"),
            ("table_id", "rows", "total_matches", "facets", "state", "warnings"),
            ("context_mismatch", "no_matching_rows", "pagination_applied"),
            "table filtering changes presentation only and does not alter source evidence state",
        ),
    )
    body = {"contracts": contracts}
    return BetaFrontierContractRegistry(contracts=contracts, content_address=content_hash(body))


__all__ = ["BetaFrontierContract", "BetaFrontierContractRegistry", "default_beta_frontier_contracts"]
