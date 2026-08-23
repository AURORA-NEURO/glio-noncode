"""Freshness and source-receipt checks for platform aggregate data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from .platform_frontier_contracts import PlatformFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierFreshnessReport:
    fixture_id: str
    observed_date: str
    max_age_days: int
    source_count: int
    source_receipts_complete: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_platform_frontier_freshness(fixture: PlatformFrontierFixture, *, observed_date: str | None = None, max_age_days: int = 3650) -> PlatformFrontierFreshnessReport:
    observed_date = observed_date or date.today().isoformat()
    complete = all(item.uri.startswith("https://") and item.content_address.startswith("sha256:") for item in fixture.sources)
    body = {"fixture_id": fixture.fixture_id, "observed_date": observed_date, "max_age_days": max_age_days, "source_count": len(fixture.sources), "source_receipts_complete": complete, "accepted": complete and max_age_days > 0}
    return PlatformFrontierFreshnessReport(**body, content_address=content_hash(body))


__all__ = ["PlatformFrontierFreshnessReport", "evaluate_platform_frontier_freshness"]
