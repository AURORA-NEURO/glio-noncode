"""Dataset manifest separating public source receipts from aggregate rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta_frontier_public_data import CohortBetaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierDatasetEntry:
    dataset_id: str
    source_id: str
    scope: str
    row_count: int
    context_key: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierDatasetManifest:
    entries: tuple[CohortBetaFrontierDatasetEntry, ...]
    closed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_dataset_manifest(fixture: CohortBetaFrontierFixture) -> CohortBetaFrontierDatasetManifest:
    entries = tuple(CohortBetaFrontierDatasetEntry(f"dataset:{source.source_id}", source.source_id, "public aggregate receipt", sum(source.source_id in record.source_ids for record in fixture.records), fixture.context_key, content_hash({"source_id": source.source_id, "fixture": fixture.fixture_id}, prefix="dataset")) for source in fixture.sources)
    return CohortBetaFrontierDatasetManifest(entries, all(item.row_count >= 0 for item in entries) and len(entries) == len(fixture.sources), content_hash(entries, prefix="dataset-manifest"))


__all__ = ["CohortBetaFrontierDatasetEntry", "CohortBetaFrontierDatasetManifest", "build_cohort_beta_frontier_dataset_manifest"]
