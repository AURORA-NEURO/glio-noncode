"""Research-use policy for workbench release artifacts."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class WorkbenchReleasePolicy:
    allowed_states: tuple[str, ...]
    prohibited_claims: tuple[str, ...]
    aggregate_only: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def default_workbench_release_policy() -> WorkbenchReleasePolicy:
    body = {"allowed_states": ("ready", "reviewed", "exported", "searched", "passed", "review", "blocked", "rejected", "abstained"), "prohibited_claims": ("clinical efficacy", "individual diagnosis", "causal certainty"), "aggregate_only": True}
    return WorkbenchReleasePolicy(**body, content_address=content_hash(body))

__all__ = ["WorkbenchReleasePolicy", "default_workbench_release_policy"]
