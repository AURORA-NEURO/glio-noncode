"""Strict adapters that bind fixture payloads to the four cohort beta testers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .cohort_beta import FunctionalConvergenceTester, PathwayRegulonConvergenceTester, RegionalBurdenTester, RegulatoryRecurrenceTester
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierAdapterSpec:
    operation: str
    input_shape: str
    output_shape: str
    boundary: str
    required_keys: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierAdapterResult:
    operation: str
    accepted: bool
    normalized: Mapping[str, Any]
    errors: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierAdapterRegistry:
    specs: tuple[CohortBetaFrontierAdapterSpec, ...]
    testers: Mapping[str, Any]
    content_address: str

    def spec(self, operation: str) -> CohortBetaFrontierAdapterSpec:
        return next(item for item in self.specs if item.operation == operation)

    def to_dict(self) -> dict[str, Any]:
        return {"specs": [item.to_dict() for item in self.specs], "content_address": self.content_address}


def _spec(operation: str, input_shape: str, output_shape: str, required_keys: tuple[str, ...]) -> CohortBetaFrontierAdapterSpec:
    body = {"operation": operation, "input_shape": input_shape, "output_shape": output_shape, "boundary": "typed_public_aggregate_adapter", "required_keys": required_keys}
    return CohortBetaFrontierAdapterSpec(**body, content_address=content_hash(body, prefix="adapter"))


def default_cohort_beta_frontier_adapters() -> CohortBetaFrontierAdapterRegistry:
    specs = (_spec("C05", "observations", "RegulatoryRecurrenceResult", ("observations",)), _spec("C06", "regions+observations", "RegionalBurdenResult", ("regions", "observations")), _spec("C07", "functional observations", "FunctionalConvergenceResult", ("observations",)), _spec("C08", "set observations", "PathwayRegulonConvergenceResult", ("observations",)))
    testers = {"C05": RegulatoryRecurrenceTester(), "C06": RegionalBurdenTester(), "C07": FunctionalConvergenceTester(), "C08": PathwayRegulonConvergenceTester()}
    return CohortBetaFrontierAdapterRegistry(specs, testers, content_hash(specs, prefix="adapter-registry"))


def validate_cohort_beta_frontier_payload(operation: str, payload: Mapping[str, Any], registry: CohortBetaFrontierAdapterRegistry | None = None) -> CohortBetaFrontierAdapterResult:
    selected = registry or default_cohort_beta_frontier_adapters()
    spec = selected.spec(operation)
    errors = tuple(f"missing:{key}" for key in spec.required_keys if key not in payload)
    normalized = dict(payload)
    address = content_hash({"operation": operation, "normalized": normalized, "errors": errors}, prefix="adapter-result")
    return CohortBetaFrontierAdapterResult(operation, not errors, normalized, errors, address)


__all__ = ["CohortBetaFrontierAdapterRegistry", "CohortBetaFrontierAdapterResult", "CohortBetaFrontierAdapterSpec", "default_cohort_beta_frontier_adapters", "validate_cohort_beta_frontier_payload"]
