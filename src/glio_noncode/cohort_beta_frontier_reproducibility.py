"""Reproducibility receipt covering fixture, schema, and runtime addresses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta_frontier_public_data import CohortBetaFrontierFixture
from .cohort_beta_frontier_schema import CohortBetaFrontierSchemaReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierReproducibilityReceipt:
    fixture_address: str
    schema_address: str
    code_version: str
    deterministic_inputs: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_reproducibility_receipt(fixture: CohortBetaFrontierFixture, schema: CohortBetaFrontierSchemaReport, *, code_version: str = "0.1.0") -> CohortBetaFrontierReproducibilityReceipt:
    inputs = (fixture.content_address, schema.content_address, fixture.fixture_version, schema.version)
    return CohortBetaFrontierReproducibilityReceipt(fixture.content_address, schema.content_address, code_version, inputs, all(bool(item) for item in inputs), content_hash({"inputs": inputs, "code_version": code_version}, prefix="reproducibility"))


__all__ = ["CohortBetaFrontierReproducibilityReceipt", "build_cohort_beta_frontier_reproducibility_receipt"]
