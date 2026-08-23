"""Stable function-level API contract for the C09-C12 runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierApiOperation:
    operation_id: str
    method: str
    input_shape: str
    output_shape: str
    error_behavior: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierApiContract:
    version: str
    operations: tuple[CohortAlphaFrontierApiOperation, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_alpha_frontier_api_contract() -> CohortAlphaFrontierApiContract:
    raw = (("evaluate", "evaluate_cohort_alpha_frontier_fixture", "fixture", "evaluation", "typed validation failure"), ("quality", "evaluate_cohort_alpha_frontier_quality", "evaluation plus contracts and schema", "quality gate", "blocking check"), ("replay", "replay_cohort_alpha_frontier", "fixture", "replay receipt", "determinism failure"), ("pipeline", "run_cohort_alpha_frontier_pipeline", "optional fixture", "runtime report", "stage failure"), ("report", "build_cohort_alpha_frontier_report", "evaluation plus release objects", "markdown and structured report", "report gate"))
    operations = tuple(CohortAlphaFrontierApiOperation(operation_id, method, input_shape, output_shape, error_behavior, content_hash({"id": operation_id, "method": method, "input": input_shape, "output": output_shape, "error": error_behavior}, prefix="alpha-api-operation")) for operation_id, method, input_shape, output_shape, error_behavior in raw)
    return CohortAlphaFrontierApiContract("1", operations, len(operations) == 5 and all(item.method and item.output_shape for item in operations), content_hash(operations, prefix="alpha-api-contract"))


__all__ = ["CohortAlphaFrontierApiContract", "CohortAlphaFrontierApiOperation", "default_cohort_alpha_frontier_api_contract"]
