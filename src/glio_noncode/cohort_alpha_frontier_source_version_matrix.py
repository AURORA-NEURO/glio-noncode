"""Source-version matrix retaining retrieval notes and scope version."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_public_data import CohortAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierSourceVersionRow:
    source_id: str
    source_version: str
    fixture_version: str
    retrieval_note: str
    same_release_window: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierSourceVersionMatrix:
    rows: tuple[CohortAlphaFrontierSourceVersionRow, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_source_version_matrix(fixture: CohortAlphaFrontierFixture) -> CohortAlphaFrontierSourceVersionMatrix:
    rows = tuple(CohortAlphaFrontierSourceVersionRow(source.source_id, source.version, fixture.fixture_version, source.retrieval_note, bool(source.version and fixture.fixture_version), content_hash({"source": source.source_id, "source_version": source.version, "fixture_version": fixture.fixture_version, "note": source.retrieval_note}, prefix="alpha-source-version")) for source in fixture.sources)
    return CohortAlphaFrontierSourceVersionMatrix(rows, len(rows) == 6 and all(item.same_release_window for item in rows), content_hash(rows, prefix="alpha-source-version-matrix"))


__all__ = ["CohortAlphaFrontierSourceVersionMatrix", "CohortAlphaFrontierSourceVersionRow", "build_cohort_alpha_frontier_source_version_matrix"]
