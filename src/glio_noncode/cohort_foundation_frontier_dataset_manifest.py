"""Dataset-level manifest for the public aggregate fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_public_data import CohortFoundationFixture


@dataclass(frozen=True, slots=True)
class CohortFoundationDatasetManifest:
    manifest_id: str
    fixture_id: str
    fixture_version: str
    boundary: str
    context_key: str
    foreign_context_key: str
    source_ids: tuple[str, ...]
    record_count: int
    positive_count: int
    control_count: int
    operation_counts: dict[str, int]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_foundation_frontier_dataset_manifest(fixture: CohortFoundationFixture) -> CohortFoundationDatasetManifest:
    operation_counts = {operation.value: len(fixture.records_for(operation)) for operation in sorted({item.operation for item in fixture.records}, key=lambda item: item.value)}
    body = {"manifest_id": "cohort-foundation-frontier-dataset", "fixture_id": fixture.fixture_id, "version": fixture.fixture_version, "boundary": fixture.boundary, "context": fixture.context_key, "foreign": fixture.foreign_context_key, "sources": tuple(item.source_id for item in fixture.sources), "records": len(fixture.records), "positive": len(fixture.positive_records), "controls": len(fixture.control_records), "operations": operation_counts}
    return CohortFoundationDatasetManifest(body["manifest_id"], fixture.fixture_id, fixture.fixture_version, fixture.boundary, fixture.context_key, fixture.foreign_context_key, tuple(item.source_id for item in fixture.sources), len(fixture.records), len(fixture.positive_records), len(fixture.control_records), operation_counts, content_hash(body))


__all__ = ["CohortFoundationDatasetManifest", "build_cohort_foundation_frontier_dataset_manifest"]
