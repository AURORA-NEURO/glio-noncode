"""Record identity checks for deterministic operation rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .cohort_alpha_frontier_public_data import CohortAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierIdentityCheck:
    record_id: str
    operation: str
    expected_prefix: str
    prefix_matches: bool
    unique: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierIdentityReport:
    checks: tuple[CohortAlphaFrontierIdentityCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_cohort_alpha_frontier_record_identity(fixture: CohortAlphaFrontierFixture, evaluation: CohortAlphaFrontierEvaluation) -> CohortAlphaFrontierIdentityReport:
    ids = {row.record_id for row in evaluation.rows}
    checks = tuple(CohortAlphaFrontierIdentityCheck(record.record_id, record.operation, record.operation.lower(), record.record_id.lower().startswith(record.operation.lower()), record.record_id in ids, content_hash({"record_id": record.record_id, "operation": record.operation, "prefix": record.operation.lower()}, prefix="alpha-record-identity")) for record in fixture.records)
    return CohortAlphaFrontierIdentityReport(checks, len(checks) == 16 and len(ids) == 16 and all(item.prefix_matches and item.unique for item in checks), content_hash(checks, prefix="alpha-record-identity-report"))


__all__ = ["CohortAlphaFrontierIdentityCheck", "CohortAlphaFrontierIdentityReport", "evaluate_cohort_alpha_frontier_record_identity"]
