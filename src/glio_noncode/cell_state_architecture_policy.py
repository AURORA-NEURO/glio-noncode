"""Context, identity, and review policy for D08 control cases."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .cell_state_architecture_contracts import (
    CellStateArchitectureCase,
    CellStateArchitectureScenario,
)

D08_CONTROL_ORDER = ("context_mismatch", "malformed_input", "identity_conflict")
D08_POLICY_VERSION = "d08-control-policy.v1"


def classify_cell_state_architecture_case(case: CellStateArchitectureCase) -> dict[str, Any]:
    """Return the policy decision without executing an operation."""
    scenario = case.scenario
    if scenario is CellStateArchitectureScenario.POSITIVE:
        return {
            "disposition": "delegate",
            "blocking": False,
            "reason_codes": (),
            "priority": "normal",
        }
    if scenario is CellStateArchitectureScenario.FOREIGN_CONTEXT:
        return {
            "disposition": "hold",
            "blocking": True,
            "reason_codes": ("context_mismatch",),
            "priority": "high",
        }
    if scenario is CellStateArchitectureScenario.MALFORMED_INPUT:
        return {
            "disposition": "hold",
            "blocking": True,
            "reason_codes": ("malformed_input",),
            "priority": "high",
        }
    if scenario is CellStateArchitectureScenario.IDENTITY_CONFLICT:
        return {
            "disposition": "hold",
            "blocking": True,
            "reason_codes": ("identity_conflict",),
            "priority": "critical",
        }
    return {
        "disposition": "abstain",
        "blocking": True,
        "reason_codes": ("unsupported_scenario",),
        "priority": "critical",
    }


def policy_matrix() -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "policy_version": D08_POLICY_VERSION,
            "scenario": scenario.value,
            **classify_cell_state_architecture_case(_policy_case(scenario)),
        }
        for scenario in CellStateArchitectureScenario
    )


def _policy_case(scenario: CellStateArchitectureScenario) -> CellStateArchitectureCase:
    """Small object used solely to keep the policy table on the same enum path."""
    return CellStateArchitectureCase(
        case_id=f"policy-{scenario.value}",
        operation_id="policy",
        capability_id="policy",
        operation=__import__(
            "glio_noncode.cell_state_architecture_contracts",
            fromlist=["CellStateArchitectureOperation"],
        ).CellStateArchitectureOperation.DISEASE_ONTOLOGY,
        family=__import__(
            "glio_noncode.cell_state_architecture_contracts",
            fromlist=["CellStateArchitectureFamily"],
        ).CellStateArchitectureFamily.CONTEXT,
        plane=__import__(
            "glio_noncode.cell_state_architecture_contracts",
            fromlist=["CellStateArchitecturePlane"],
        ).CellStateArchitecturePlane.TAXONOMY,
        scenario=scenario,
        context_key="policy",
        source_ids=("policy",),
        payload={"policy": True},
        expected_state=__import__(
            "glio_noncode.cell_state_architecture_contracts",
            fromlist=["CellStateArchitectureState"],
        ).CellStateArchitectureState.ACCEPTED
        if scenario is CellStateArchitectureScenario.POSITIVE
        else __import__(
            "glio_noncode.cell_state_architecture_contracts",
            fromlist=["CellStateArchitectureState"],
        ).CellStateArchitectureState.REVIEW,
        expected_result_state="policy",
        expected_issue_codes=(),
        expected_counts={},
        description="policy matrix row",
        content_address="sha256:policy",
    )


def policy_decision_for_payload(payload: Mapping[str, Any]) -> str:
    if payload.get("identity_conflict"):
        return "hold_identity_conflict"
    if payload.get("malformed"):
        return "hold_malformed_input"
    return "delegate_exact_context"


__all__ = [
    "D08_CONTROL_ORDER",
    "D08_POLICY_VERSION",
    "classify_cell_state_architecture_case",
    "policy_decision_for_payload",
    "policy_matrix",
]
