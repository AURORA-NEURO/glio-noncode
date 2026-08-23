"""Local deterministic sandbox admission and receipt projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .coordination_architecture_contracts import (
    CoordinationCase,
    CoordinationOperationSpec,
    CoordinationState,
    CoordinationToolSpec,
    addressed,
)
from .module_fabric_support import contains_private_key


@dataclass(frozen=True, slots=True)
class CoordinationSandboxReceipt:
    case_id: str
    tool_id: str
    state: CoordinationState
    network_allowed: bool
    private_key_detected: bool
    handler_registered: bool
    reasons: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "tool_id": self.tool_id,
            "state": self.state,
            "network_allowed": self.network_allowed,
            "private_key_detected": self.private_key_detected,
            "handler_registered": self.handler_registered,
            "reasons": self.reasons,
            "content_address": self.content_address,
        }


def execute_coordination_sandbox(
    case: CoordinationCase,
    spec: CoordinationOperationSpec,
    tool: CoordinationToolSpec,
) -> CoordinationSandboxReceipt:
    reasons: list[str] = []
    private_key_detected = contains_private_key(case.payload)
    if tool.operation_id != spec.operation_id:
        reasons.append("tool_operation_mismatch")
    if not tool.deterministic:
        reasons.append("nondeterministic_tool")
    if tool.network_allowed or case.payload.get("network_requested"):
        reasons.append("network_denied")
    if private_key_detected:
        reasons.append("private_key_detected")
    if not case.payload.get("public_aggregate_only"):
        reasons.append("aggregate_scope_required")
    state = CoordinationState.ACCEPTED if not reasons else CoordinationState.REVIEW
    body = {
        "case_id": case.case_id,
        "tool_id": tool.tool_id,
        "state": state,
        "network_allowed": False,
        "private_key_detected": private_key_detected,
        "handler_registered": tool.operation_id == spec.operation_id,
        "reasons": tuple(sorted(set(reasons))),
    }
    return CoordinationSandboxReceipt(**body, content_address=addressed(body, "coordination-sandbox"))


def sandbox_projection(receipt: CoordinationSandboxReceipt) -> Mapping[str, Any]:
    return {
        "state": receipt.state,
        "network_allowed": receipt.network_allowed,
        "private_key_detected": receipt.private_key_detected,
        "handler_registered": receipt.handler_registered,
        "reason_count": len(receipt.reasons),
    }


__all__ = ["CoordinationSandboxReceipt", "execute_coordination_sandbox", "sandbox_projection"]
