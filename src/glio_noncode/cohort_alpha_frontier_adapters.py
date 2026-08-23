"""Strict operation adapters for C09-C12 payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .cohort_alpha import ClonalityTimingIntegrator, CrossCohortReplicationEngine, PrimaryRecurrenceComparator, TreatmentSelectionSignalDetector
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierAdapterSpec:
    operation: str
    required_keys: tuple[str, ...]
    output_type: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierAdapterResult:
    operation: str
    accepted: bool
    normalized: Mapping[str, Any]
    errors: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierAdapterRegistry:
    specs: tuple[CohortAlphaFrontierAdapterSpec, ...]
    testers: Mapping[str, Any]
    content_address: str

    def spec(self, operation: str) -> CohortAlphaFrontierAdapterSpec:
        return next(item for item in self.specs if item.operation == operation)

    def to_dict(self) -> dict[str, Any]:
        return {"specs": [item.to_dict() for item in self.specs], "content_address": self.content_address}


def default_cohort_alpha_frontier_adapters() -> CohortAlphaFrontierAdapterRegistry:
    specs = (CohortAlphaFrontierAdapterSpec("C09", ("observations", "clonal_threshold", "subclonal_threshold"), "ClonalityTimingReport", content_hash("C09", prefix="alpha-adapter")), CohortAlphaFrontierAdapterSpec("C10", ("observations", "change_threshold"), "PrimaryRecurrenceComparatorReport", content_hash("C10", prefix="alpha-adapter")), CohortAlphaFrontierAdapterSpec("C11", ("observations", "change_threshold"), "TreatmentSelectionReport", content_hash("C11", prefix="alpha-adapter")), CohortAlphaFrontierAdapterSpec("C12", ("observations", "minimum_cohorts", "minimum_concordance"), "CrossCohortReplicationReport", content_hash("C12", prefix="alpha-adapter")))
    testers = {"C09": ClonalityTimingIntegrator(), "C10": PrimaryRecurrenceComparator(), "C11": TreatmentSelectionSignalDetector(), "C12": CrossCohortReplicationEngine()}
    return CohortAlphaFrontierAdapterRegistry(specs, testers, content_hash(specs, prefix="alpha-adapters"))


def validate_cohort_alpha_frontier_payload(operation: str, payload: Mapping[str, Any], registry: CohortAlphaFrontierAdapterRegistry | None = None) -> CohortAlphaFrontierAdapterResult:
    selected = registry or default_cohort_alpha_frontier_adapters()
    spec = selected.spec(operation)
    errors = tuple(f"missing:{key}" for key in spec.required_keys if key not in payload)
    return CohortAlphaFrontierAdapterResult(operation, not errors, dict(payload), errors, content_hash({"operation": operation, "payload": payload, "errors": errors}, prefix="alpha-adapter-result"))


__all__ = ["CohortAlphaFrontierAdapterRegistry", "CohortAlphaFrontierAdapterResult", "CohortAlphaFrontierAdapterSpec", "default_cohort_alpha_frontier_adapters", "validate_cohort_alpha_frontier_payload"]
