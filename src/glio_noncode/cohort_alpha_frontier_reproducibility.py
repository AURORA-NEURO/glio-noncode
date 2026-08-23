"""Reproducibility receipts for fixture, schema, and release inputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierReleaseManifest, CohortAlphaFrontierReplayReceipt
from .cohort_alpha_frontier_schema_migrations import CohortAlphaFrontierMigrationPlan
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierReproducibilityReceipt:
    receipt_id: str
    fixture_address: str
    schema_address: str
    migration_address: str
    replay_address: str
    release_address: str
    deterministic: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_reproducibility_receipt(fixture_address: str, schema_address: str, migration: CohortAlphaFrontierMigrationPlan, replay: CohortAlphaFrontierReplayReceipt, manifest: CohortAlphaFrontierReleaseManifest) -> CohortAlphaFrontierReproducibilityReceipt:
    deterministic = bool(fixture_address and schema_address and migration.accepted and replay.deterministic and manifest.ready)
    body = {"receipt_id": "cohort-alpha-frontier-reproducibility", "fixture": fixture_address, "schema": schema_address, "migration": migration.content_address, "replay": replay.content_address, "release": manifest.content_address, "deterministic": deterministic}
    return CohortAlphaFrontierReproducibilityReceipt(body["receipt_id"], fixture_address, schema_address, migration.content_address, replay.content_address, manifest.content_address, deterministic, content_hash(body, prefix="alpha-reproducibility"))


__all__ = ["CohortAlphaFrontierReproducibilityReceipt", "build_cohort_alpha_frontier_reproducibility_receipt"]
