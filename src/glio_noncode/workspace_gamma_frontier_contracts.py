"""Typed contracts for the C09-C12 collaboration frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_gamma_frontier_public_data import GammaFrontierOperation


@dataclass(frozen=True, slots=True)
class GammaFrontierContract:
    """Input, output, state, issue, and boundary contract for one surface."""

    contract_id: str
    operation: GammaFrontierOperation
    version: str
    required_inputs: tuple[str, ...]
    required_outputs: tuple[str, ...]
    state_values: tuple[str, ...]
    issue_codes: tuple[str, ...]
    research_boundary: str
    review_questions: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in ("contract_id", "version", "research_boundary", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.required_inputs or not self.required_outputs or not self.review_questions:
            raise ValueError(
                "gamma frontier contract requires inputs, outputs, and review questions"
            )

    def accepts_state(self, state: str) -> bool:
        return state in self.state_values

    def accepts_issue_set(self, issues: tuple[str, ...]) -> bool:
        return set(issues).issubset(self.issue_codes)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierContractRegistry:
    """Lookup registry for the four typed surface contracts."""

    contracts: tuple[GammaFrontierContract, ...]
    content_address: str

    def by_operation(self, operation: GammaFrontierOperation) -> GammaFrontierContract:
        return next(item for item in self.contracts if item.operation is operation)

    def issue_codes(self) -> tuple[str, ...]:
        return tuple(sorted({code for item in self.contracts for code in item.issue_codes}))

    def state_values(self) -> tuple[str, ...]:
        return tuple(sorted({value for item in self.contracts for value in item.state_values}))

    def review_questions(self) -> tuple[str, ...]:
        return tuple(question for item in self.contracts for question in item.review_questions)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "issue_codes": list(self.issue_codes()),
            "state_values": list(self.state_values()),
            "review_question_count": len(self.review_questions()),
        }


def _contract(
    operation: GammaFrontierOperation,
    inputs: tuple[str, ...],
    outputs: tuple[str, ...],
    issues: tuple[str, ...],
    boundary: str,
    questions: tuple[str, ...],
) -> GammaFrontierContract:
    body = {
        "contract_id": f"workspace-gamma-frontier:{operation.value}",
        "operation": operation,
        "version": "2026.08.d15.c09-c12.v1",
        "required_inputs": inputs,
        "required_outputs": outputs,
        "state_values": (
            "ready_for_review",
            "review_required",
            "partial",
            "blocked",
            "out_of_domain",
            "abstained",
            "allowed",
            "denied",
            "verified",
            "expired",
        ),
        "issue_codes": issues,
        "research_boundary": boundary,
        "review_questions": questions,
    }
    return GammaFrontierContract(**body, content_address=content_hash(body))


def default_gamma_frontier_contracts() -> GammaFrontierContractRegistry:
    """Return the complete public contract registry."""

    contracts = (
        _contract(
            GammaFrontierOperation.EXPERIMENT_BOARD,
            ("context_key", "cards"),
            ("columns", "dependency_edges", "blocked_card_ids", "state", "issues"),
            ("context_mismatch", "unknown_dependency", "invalid_experiment_card"),
            (
                "board metadata groups declared validation work and does not run or approve "
                "experiments"
            ),
            ("Are cards in the exact context?", "Are blockers and dependencies visible?"),
        ),
        _contract(
            GammaFrontierOperation.LAUNCH_PLAN,
            ("context_key", "requests"),
            ("launches", "parameter_hash", "network_policy", "state", "issues"),
            (
                "context_mismatch",
                "invalid_launch_request",
                "resource_profile_not_allowed",
                "runtime_not_allowed",
            ),
            (
                "launch plans describe bounded execution inputs and do not execute code or "
                "grant data access"
            ),
            (
                "Is the runtime explicitly allowed?",
                "Is network access disabled or review-required?",
            ),
        ),
        _contract(
            GammaFrontierOperation.SHAREABLE_SNAPSHOT,
            ("context_key", "snapshot_payload", "signing_secret"),
            ("snapshot_id", "signature_valid", "payload_hash_valid", "expired", "state"),
            ("snapshot_context_mismatch", "snapshot_signature_invalid", "snapshot_expired"),
            (
                "HMAC integrity proves shared-secret possession and does not establish identity "
                "or scientific validity"
            ),
            ("Is the context exact?", "Is the audience and expiry reviewed separately?"),
        ),
        _contract(
            GammaFrontierOperation.COLLABORATION_ACCESS,
            ("workspace_id", "context_key", "members", "requests"),
            ("decisions", "policy_receipt", "state", "issues"),
            (
                "context_mismatch",
                "inactive_member",
                "unknown_member",
                "invalid_collaboration_request",
            ),
            (
                "application permissions are deny-by-default research policy and do not replace "
                "institutional controls"
            ),
            ("Is the member active in this context?", "Does the role explicitly grant the action?"),
        ),
    )
    body = {"contracts": contracts}
    return GammaFrontierContractRegistry(contracts=contracts, content_address=content_hash(body))


__all__ = [
    "GammaFrontierContract",
    "GammaFrontierContractRegistry",
    "default_gamma_frontier_contracts",
]
