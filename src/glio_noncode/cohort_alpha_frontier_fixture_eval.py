"""Deterministic evaluation of C09-C12 alpha records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .cohort_alpha import ClonalityTimingIntegrator, CohortAlphaState, CrossCohortReplicationEngine, PrimaryRecurrenceComparator, TreatmentSelectionSignalDetector
from .cohort_alpha_frontier_public_data import CohortAlphaFrontierFixture, CohortAlphaFrontierRecord, default_cohort_alpha_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierEvaluationRow:
    operation: str
    record_id: str
    expected_state: CohortAlphaState
    observed_state: CohortAlphaState
    accepted: bool
    result: Mapping[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierEvaluation:
    fixture_id: str
    rows: tuple[CohortAlphaFrontierEvaluationRow, ...]
    accepted: bool
    supported_count: int
    control_count: int
    mismatch_count: int
    content_address: str

    def by_operation(self, operation: str) -> tuple[CohortAlphaFrontierEvaluationRow, ...]:
        return tuple(item for item in self.rows if item.operation == operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _evaluate(record: CohortAlphaFrontierRecord, context_key: str) -> Mapping[str, Any]:
    payload = dict(record.payload)
    if record.operation == "C09":
        result = ClonalityTimingIntegrator().integrate(payload["observations"], context_key=context_key, clonal_threshold=float(payload["clonal_threshold"]), subclonal_threshold=float(payload["subclonal_threshold"]))
    elif record.operation == "C10":
        result = PrimaryRecurrenceComparator().compare(payload["observations"], context_key=context_key, change_threshold=float(payload["change_threshold"]))
    elif record.operation == "C11":
        result = TreatmentSelectionSignalDetector().detect(payload["observations"], context_key=context_key, change_threshold=float(payload["change_threshold"]))
    elif record.operation == "C12":
        result = CrossCohortReplicationEngine().replicate(payload["observations"], context_key=context_key, minimum_cohorts=int(payload["minimum_cohorts"]), minimum_concordance=float(payload["minimum_concordance"]))
    else:
        raise ValueError(f"unsupported C09-C12 operation: {record.operation}")
    return result.to_dict()


def evaluate_cohort_alpha_frontier_fixture(fixture: CohortAlphaFrontierFixture | None = None) -> CohortAlphaFrontierEvaluation:
    value = fixture or default_cohort_alpha_frontier_fixture()
    rows: list[CohortAlphaFrontierEvaluationRow] = []
    for record in value.records:
        try:
            result = _evaluate(record, value.context_key)
            observed = CohortAlphaState(str(result["state"]))
            accepted = observed is record.expected_state
        except (KeyError, TypeError, ValueError) as exc:
            result = {"error": str(exc)}
            observed = CohortAlphaState.ABSTAINED
            accepted = False
        body = {"operation": record.operation, "record_id": record.record_id, "expected_state": record.expected_state, "observed_state": observed, "accepted": accepted, "result": result}
        rows.append(CohortAlphaFrontierEvaluationRow(record.operation, record.record_id, record.expected_state, observed, accepted, result, content_hash(body, prefix="alpha-eval-row")))
    values = tuple(rows)
    return CohortAlphaFrontierEvaluation(value.fixture_id, values, all(item.accepted for item in values), sum(item.observed_state is CohortAlphaState.SUPPORTED for item in values), sum(item.expected_state is not CohortAlphaState.SUPPORTED for item in values), sum(not item.accepted for item in values), content_hash({"fixture_id": value.fixture_id, "rows": values}, prefix="alpha-evaluation"))


__all__ = ["CohortAlphaFrontierEvaluation", "CohortAlphaFrontierEvaluationRow", "evaluate_cohort_alpha_frontier_fixture"]
