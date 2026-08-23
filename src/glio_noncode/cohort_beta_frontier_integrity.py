"""Address and duplicate integrity checks for fixture and evaluations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_beta_frontier_fixture_eval import CohortBetaFrontierEvaluation
from .cohort_beta_frontier_public_data import CohortBetaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierIntegrityCheck:
    check_id: str
    accepted: bool
    observed: int
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierIntegrityReport:
    checks: tuple[CohortBetaFrontierIntegrityCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_cohort_beta_frontier_integrity(fixture: CohortBetaFrontierFixture, evaluation: CohortBetaFrontierEvaluation) -> CohortBetaFrontierIntegrityReport:
    checks_raw = (("unique-record-addresses", len({item.content_address for item in fixture.records}) == len(fixture.records), len(fixture.records), "record addresses are unique"), ("unique-evaluation-addresses", len({item.content_address for item in evaluation.rows}) == len(evaluation.rows), len(evaluation.rows), "result addresses are unique"), ("fixture-address", bool(fixture.content_address), 1, "fixture has a content address"), ("evaluation-address", bool(evaluation.content_address), 1, "evaluation has a content address"))
    checks = tuple(CohortBetaFrontierIntegrityCheck(check_id, accepted, observed, detail, content_hash({"check_id": check_id, "accepted": accepted, "observed": observed}, prefix="integrity-check")) for check_id, accepted, observed, detail in checks_raw)
    return CohortBetaFrontierIntegrityReport(checks, all(item.accepted for item in checks), content_hash(checks, prefix="integrity"))


__all__ = ["CohortBetaFrontierIntegrityCheck", "CohortBetaFrontierIntegrityReport", "evaluate_cohort_beta_frontier_integrity"]
