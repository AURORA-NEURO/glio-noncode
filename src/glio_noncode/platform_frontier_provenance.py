"""Provenance receipt joining input, registry, policy, and workflow addresses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .mission_runtime import MissionPlan
from .platform_frontier_policy import PlatformFrontierPolicy
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierProvenanceReceipt:
    run_id: str
    input_addresses: tuple[str, ...]
    registry_address: str
    policy_address: str
    plan_address: str
    reference_build: str
    complete: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_platform_frontier_provenance(run_id: str, plan: MissionPlan, policy: PlatformFrontierPolicy, *, input_addresses: tuple[str, ...] = ("sha256:platform-input",), reference_build: str = "platform-v1") -> PlatformFrontierProvenanceReceipt:
    body = {"run_id": run_id, "input_addresses": input_addresses, "registry_address": plan.registry_address, "policy_address": policy.content_address, "plan_address": plan.content_address, "reference_build": reference_build, "complete": bool(input_addresses) and plan.registry_address.startswith("sha256:") and policy.content_address.startswith("sha256:") and plan.content_address.startswith("sha256:")}
    return PlatformFrontierProvenanceReceipt(**body, content_address=content_hash(body))


__all__ = ["PlatformFrontierProvenanceReceipt", "build_platform_frontier_provenance"]
