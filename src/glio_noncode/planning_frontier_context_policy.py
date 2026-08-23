"""Exact-context policy shared by all four planning operations."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .planning_frontier_contracts import PLANNING_FRONTIER_CONTEXT_KEY
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ContextPolicyDecision:
    requested_context: str
    observed_context: str
    matches: bool
    disposition: str
    issue_code: str | None
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def decide_context(observed_context: str, requested_context: str = PLANNING_FRONTIER_CONTEXT_KEY) -> ContextPolicyDecision:
    matches = str(observed_context) == requested_context
    body = {"requested_context": requested_context, "observed_context": str(observed_context), "matches": matches, "disposition": "accepted" if matches else "blocked", "issue_code": None if matches else "context_mismatch"}
    return ContextPolicyDecision(**body, content_address=content_hash(body, prefix="context-policy"))
__all__ = ["ContextPolicyDecision", "decide_context"]
