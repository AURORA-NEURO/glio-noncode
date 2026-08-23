"""Research-use policy and decision wording for planning outputs."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class ValidationDesignPolicy:
    policy_id: str
    permitted_uses: tuple[str, ...]
    prohibited_claims: tuple[str, ...]
    state_actions: dict[str, str]
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def default_validation_design_policy() -> ValidationDesignPolicy:
    body = {"policy_id": "validation-design-research-use-v1", "permitted_uses": ("assay planning", "evidence gap review", "construct packaging", "aggregate reproducibility"), "prohibited_claims": ("clinical efficacy", "individual diagnosis", "causal certainty", "patient-level inference"), "state_actions": {"ready": "retain plan", "routed": "retain route", "packaged": "retain manifest", "review": "assign reviewer", "blocked": "quarantine context", "rejected": "repair payload"}}
    return ValidationDesignPolicy(**body, content_address=content_hash(body))

__all__ = ["ValidationDesignPolicy", "default_validation_design_policy"]
