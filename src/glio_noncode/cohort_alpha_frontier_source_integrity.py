"""Source integrity checks for URL, version, and receipt closure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_public_data import CohortAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierSourceIntegrityRow:
    source_id: str
    url_ok: bool
    version_ok: bool
    address_ok: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierSourceIntegrityReport:
    rows: tuple[CohortAlphaFrontierSourceIntegrityRow, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_cohort_alpha_frontier_source_integrity(fixture: CohortAlphaFrontierFixture) -> CohortAlphaFrontierSourceIntegrityReport:
    rows = []
    for source in fixture.sources:
        url_ok = source.url.startswith("https://")
        version_ok = bool(source.version)
        address_ok = bool(source.content_address)
        rows.append(CohortAlphaFrontierSourceIntegrityRow(source.source_id, url_ok, version_ok, address_ok, url_ok and version_ok and address_ok, content_hash({"source": source.source_id, "url": url_ok, "version": version_ok, "address": address_ok}, prefix="alpha-source-integrity")))
    values = tuple(rows)
    return CohortAlphaFrontierSourceIntegrityReport(values, len(values) == 6 and all(item.accepted for item in values), content_hash(values, prefix="alpha-source-integrity-report"))


__all__ = ["CohortAlphaFrontierSourceIntegrityReport", "CohortAlphaFrontierSourceIntegrityRow", "evaluate_cohort_alpha_frontier_source_integrity"]
