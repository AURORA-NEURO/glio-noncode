"""Content-address and row-identity checks for C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .cohort_alpha_frontier_public_data import CohortAlphaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierIntegrityCheck:
    check_id: str
    observed: int
    accepted: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierIntegrityReport:
    checks: tuple[CohortAlphaFrontierIntegrityCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_cohort_alpha_frontier_integrity(fixture: CohortAlphaFrontierFixture, evaluation: CohortAlphaFrontierEvaluation) -> CohortAlphaFrontierIntegrityReport:
    raw = (("record-identity", len({item.record_id for item in fixture.records}), len(fixture.records) == 16, "record IDs are unique"), ("record-address", len({item.content_address for item in fixture.records}), True, "record addresses are unique"), ("result-address", len({item.content_address for item in evaluation.rows}), len(evaluation.rows) == 16, "result addresses are unique"), ("fixture-address", 1 if fixture.content_address else 0, bool(fixture.content_address), "fixture address is present"), ("evaluation-address", 1 if evaluation.content_address else 0, bool(evaluation.content_address), "evaluation address is present"))
    checks = tuple(CohortAlphaFrontierIntegrityCheck(check_id, observed, accepted, detail, content_hash({"check_id": check_id, "observed": observed, "accepted": accepted}, prefix="alpha-integrity-check")) for check_id, observed, accepted, detail in raw)
    return CohortAlphaFrontierIntegrityReport(checks, all(item.accepted for item in checks), content_hash(checks, prefix="alpha-integrity"))


__all__ = ["CohortAlphaFrontierIntegrityCheck", "CohortAlphaFrontierIntegrityReport", "evaluate_cohort_alpha_frontier_integrity"]
