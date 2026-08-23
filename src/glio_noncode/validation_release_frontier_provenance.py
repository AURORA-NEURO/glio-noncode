"""Run provenance receipt without secrets or mutable credentials."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseFixture
from .validation_release_frontier_execution_plan import ValidationReleaseExecutionPlan
from .validation_release_frontier_policy import ValidationReleasePolicy


@dataclass(frozen=True, slots=True)
class ValidationReleaseProvenance:
    run_id: str
    fixture_id: str
    fixture_address: str
    plan_address: str
    policy_address: str
    runtime_label: str
    complete: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_provenance(run_id: str, fixture: ValidationReleaseFixture, plan: ValidationReleaseExecutionPlan, policy: ValidationReleasePolicy) -> ValidationReleaseProvenance:
    body = {"run_id": run_id, "fixture_id": fixture.fixture_id, "fixture_address": fixture.content_address, "plan_address": plan.content_address, "policy_address": policy.content_address, "runtime_label": "local-standard-library" , "complete": True}
    return ValidationReleaseProvenance(**body, content_address=content_hash(body))


__all__ = ["ValidationReleaseProvenance", "build_validation_release_provenance"]
