"""Manifest of fixture controls and their expected state boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .cohort_beta_frontier_public_data import CohortBetaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierManifestRow:
    record_id: str
    operation: str
    control_class: str
    expected_state: str
    source_ids: tuple[str, ...]
    context_key: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierFixtureManifest:
    fixture_id: str
    rows: tuple[CohortBetaFrontierManifestRow, ...]
    positive_count: int
    control_count: int
    accepted: bool
    content_address: str

    def for_operation(self, operation: str) -> tuple[CohortBetaFrontierManifestRow, ...]:
        return tuple(item for item in self.rows if item.operation == operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_fixture_manifest(fixture: CohortBetaFrontierFixture) -> CohortBetaFrontierFixtureManifest:
    rows = tuple(CohortBetaFrontierManifestRow(record.record_id, record.operation, record.control_class, record.expected_state.value, record.source_ids, fixture.foreign_context_key if record.control_class == "foreign_context" else fixture.context_key, content_hash({"record_id": record.record_id, "operation": record.operation, "expected_state": record.expected_state}, prefix="manifest-row")) for record in fixture.records)
    return CohortBetaFrontierFixtureManifest(fixture.fixture_id, rows, sum(item.expected_state == "supported" for item in rows), sum(item.expected_state != "supported" for item in rows), len(rows) == 16 and len({item.record_id for item in rows}) == 16, content_hash({"fixture": fixture.fixture_id, "rows": rows}, prefix="fixture-manifest"))


def manifest_summary(manifest: CohortBetaFrontierFixtureManifest) -> Mapping[str, Any]:
    return {"fixture_id": manifest.fixture_id, "positive_count": manifest.positive_count, "control_count": manifest.control_count, "accepted": manifest.accepted, "operations": {operation: len(manifest.for_operation(operation)) for operation in ("C05", "C06", "C07", "C08")}}


__all__ = ["CohortBetaFrontierFixtureManifest", "CohortBetaFrontierManifestRow", "build_cohort_beta_frontier_fixture_manifest", "manifest_summary"]
