"""Provenance receipt joining source, policy, plan, and release addresses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_contracts import DeploymentFrontierFixture
from .deployment_frontier_execution_plan import DeploymentFrontierExecutionPlan
from .deployment_frontier_policy import DeploymentFrontierPolicy
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierProvenanceReceipt:
    run_id: str
    source_addresses: tuple[str, ...]
    policy_address: str
    plan_address: str
    fixture_address: str
    complete: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_deployment_frontier_provenance(run_id: str, fixture: DeploymentFrontierFixture, plan: DeploymentFrontierExecutionPlan, policy: DeploymentFrontierPolicy) -> DeploymentFrontierProvenanceReceipt:
    sources = tuple(item.content_address for item in fixture.sources)
    body = {"run_id": run_id, "source_addresses": sources, "policy_address": policy.content_address, "plan_address": plan.content_address, "fixture_address": fixture.content_address, "complete": bool(sources) and all(item.startswith("sha256:") for item in sources) and policy.content_address.startswith("sha256:") and plan.content_address.startswith("sha256:")}
    return DeploymentFrontierProvenanceReceipt(**body, content_address=deployment_address(body))


__all__ = ["DeploymentFrontierProvenanceReceipt", "build_deployment_frontier_provenance"]
