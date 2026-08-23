"""Assertions for JSON projection and public export closure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierEvaluation
from .lifecycle_beta_frontier_exports import lifecycle_beta_frontier_export_payload
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierProjectionAssertion:
    assertion_id: str
    passed: bool
    observed_type: str
    required_keys: tuple[str, ...]
    missing_keys: tuple[str, ...]
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierProjectionReport:
    assertions: tuple[LifecycleBetaFrontierProjectionAssertion, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def assert_lifecycle_beta_frontier_projection(evaluation: LifecycleBetaFrontierEvaluation) -> LifecycleBetaFrontierProjectionReport:
    payload = lifecycle_beta_frontier_export_payload(evaluation)
    required = ("fixture_id", "executions", "checks", "accepted", "content_address")
    missing = tuple(item for item in required if item not in payload)
    body = {"assertion_id": "evaluation-json-projection", "passed": not missing and isinstance(payload["executions"], list), "observed_type": type(payload.get("executions")).__name__, "required_keys": required, "missing_keys": missing, "detail": "nested enum and dataclass values project to JSON-compatible values"}
    assertion = LifecycleBetaFrontierProjectionAssertion(**body, content_address=content_hash(body))
    return LifecycleBetaFrontierProjectionReport((assertion,), assertion.passed, content_hash({"assertions": (assertion,)}))


__all__ = ["LifecycleBetaFrontierProjectionAssertion", "LifecycleBetaFrontierProjectionReport", "assert_lifecycle_beta_frontier_projection"]
