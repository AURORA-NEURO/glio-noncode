"""Freshness receipt for source portals; no network is fetched during replay."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseFixture


@dataclass(frozen=True, slots=True)
class ValidationReleaseFreshnessReport:
    source_count: int
    source_versions_present: bool
    network_fetch_performed: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_validation_release_freshness(fixture: ValidationReleaseFixture) -> ValidationReleaseFreshnessReport:
    body = {"source_count": len(fixture.sources), "source_versions_present": all(bool(item.version) for item in fixture.sources), "network_fetch_performed": False, "accepted": all(bool(item.version) for item in fixture.sources)}
    return ValidationReleaseFreshnessReport(**body, content_address=content_hash(body))


__all__ = ["ValidationReleaseFreshnessReport", "evaluate_validation_release_freshness"]
