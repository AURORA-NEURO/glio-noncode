"""Dataset-level manifest with fixed scope and exclusion boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_public_data import CohortAlphaFrontierDataAudit, CohortAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierDatasetManifest:
    dataset_id: str
    fixture_id: str
    version: str
    context_key: str
    operations: tuple[str, ...]
    record_count: int
    source_count: int
    exclusion_rules: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_dataset_manifest(fixture: CohortAlphaFrontierFixture, audit: CohortAlphaFrontierDataAudit) -> CohortAlphaFrontierDatasetManifest:
    exclusions = ("non-adult context", "post-treatment context", "unreceipted source", "causal or clinical decision claims")
    accepted = audit.accepted and fixture.context_key and len(fixture.operations) == 4 and len(exclusions) == 4
    body = {"dataset_id": "cohort-alpha-frontier-c09-c12", "fixture": fixture.fixture_id, "version": fixture.fixture_version, "context": fixture.context_key, "operations": fixture.operations, "records": len(fixture.records), "sources": len(fixture.sources), "exclusions": exclusions, "accepted": accepted}
    return CohortAlphaFrontierDatasetManifest(body["dataset_id"], fixture.fixture_id, fixture.fixture_version, fixture.context_key, fixture.operations, len(fixture.records), len(fixture.sources), exclusions, accepted, content_hash(body, prefix="alpha-dataset-manifest"))


__all__ = ["CohortAlphaFrontierDatasetManifest", "build_cohort_alpha_frontier_dataset_manifest"]
