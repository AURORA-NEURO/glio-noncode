"""Run manifest for deployment frontier runtime execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_execution_plan import DeploymentFrontierExecutionPlan
from .deployment_frontier_provenance import DeploymentFrontierProvenanceReceipt
from .deployment_frontier_support import deployment_address
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierRunManifest:
    run_id: str
    plan_address: str
    provenance_address: str
    stage_ids: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_deployment_frontier_run_manifest(run_id: str, plan: DeploymentFrontierExecutionPlan, provenance: DeploymentFrontierProvenanceReceipt, stage_ids: tuple[str, ...]) -> DeploymentFrontierRunManifest:
    body = {"run_id": run_id, "plan_address": plan.content_address, "provenance_address": provenance.content_address, "stage_ids": stage_ids, "accepted": plan.accepted and provenance.complete and bool(stage_ids)}
    return DeploymentFrontierRunManifest(**body, content_address=deployment_address(body))


__all__ = ["DeploymentFrontierRunManifest", "build_deployment_frontier_run_manifest"]
