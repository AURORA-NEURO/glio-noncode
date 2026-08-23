"""Compliance boundary checks for public aggregate validation planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseFixture


@dataclass(frozen=True, slots=True)
class ValidationReleaseComplianceReport:
    checks: dict[str, bool]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_validation_release_compliance(fixture: ValidationReleaseFixture) -> ValidationReleaseComplianceReport:
    checks = {"public_sources": all(item.uri.startswith("https://") for item in fixture.sources), "aggregate_boundary": fixture.evidence_boundary == "public_aggregate_validation_release_planning", "patient_level_excluded": not any("patient" in str(item.payload).lower() for item in fixture.records), "context_declared": bool(fixture.context_key), "source_links_closed": all(item.source_ids for item in fixture.records)}
    return ValidationReleaseComplianceReport(checks, all(checks.values()), content_hash(checks))


__all__ = ["ValidationReleaseComplianceReport", "evaluate_validation_release_compliance"]
