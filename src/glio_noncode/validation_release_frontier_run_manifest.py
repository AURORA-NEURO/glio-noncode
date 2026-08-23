"""Run manifest joining plan and provenance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_execution_plan import ValidationReleaseExecutionPlan
from .validation_release_frontier_provenance import ValidationReleaseProvenance


@dataclass(frozen=True, slots=True)
class ValidationReleaseRunManifest:
    run_id: str
    stages: tuple[str, ...]
    plan_address: str
    provenance_address: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_run_manifest(run_id: str, plan: ValidationReleaseExecutionPlan, provenance: ValidationReleaseProvenance, stages: tuple[str, ...]) -> ValidationReleaseRunManifest:
    body = {"run_id": run_id, "stages": stages, "plan_address": plan.content_address, "provenance_address": provenance.content_address, "accepted": bool(run_id and stages and provenance.complete)}
    return ValidationReleaseRunManifest(**body, content_address=content_hash(body))


__all__ = ["ValidationReleaseRunManifest", "build_validation_release_run_manifest"]
