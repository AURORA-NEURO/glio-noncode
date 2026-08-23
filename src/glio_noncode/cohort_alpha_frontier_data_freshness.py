"""Freshness assertions for public source receipts and fixture versioning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_public_data import CohortAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierFreshnessCheck:
    source_id: str
    source_version: str
    retrieval_note: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierFreshnessReport:
    fixture_version: str
    checks: tuple[CohortAlphaFrontierFreshnessCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def assess_cohort_alpha_frontier_freshness(fixture: CohortAlphaFrontierFixture) -> CohortAlphaFrontierFreshnessReport:
    checks = tuple(CohortAlphaFrontierFreshnessCheck(source.source_id, source.version, source.retrieval_note, bool(source.version and source.retrieval_note), content_hash({"source": source.source_id, "version": source.version, "note": source.retrieval_note}, prefix="alpha-freshness")) for source in fixture.sources)
    return CohortAlphaFrontierFreshnessReport(fixture.fixture_version, checks, bool(fixture.fixture_version) and len(checks) == 6 and all(item.accepted for item in checks), content_hash({"version": fixture.fixture_version, "checks": checks}, prefix="alpha-freshness-report"))


__all__ = ["CohortAlphaFrontierFreshnessCheck", "CohortAlphaFrontierFreshnessReport", "assess_cohort_alpha_frontier_freshness"]
