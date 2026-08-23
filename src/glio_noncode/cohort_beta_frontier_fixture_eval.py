"""Deterministic fixture evaluation for recurrence, burden, function, and sets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .cohort_beta import CohortBetaState, FunctionalConvergenceTester, PathwayRegulonConvergenceTester, RegionalBurdenTester, RegulatoryRecurrenceTester
from .cohort_beta_frontier_public_data import CohortBetaFrontierFixture, CohortBetaFrontierRecord, default_cohort_beta_frontier_fixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierEvaluationRow:
    operation: str
    record_id: str
    expected_state: CohortBetaState
    observed_state: CohortBetaState
    accepted: bool
    result: Mapping[str, Any]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierEvaluation:
    fixture_id: str
    rows: tuple[CohortBetaFrontierEvaluationRow, ...]
    accepted: bool
    supported_count: int
    control_count: int
    mismatch_count: int
    content_address: str

    def by_operation(self, operation: str) -> tuple[CohortBetaFrontierEvaluationRow, ...]:
        return tuple(item for item in self.rows if item.operation == operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _evaluate(record: CohortBetaFrontierRecord, context_key: str) -> Mapping[str, Any]:
    payload = dict(record.payload)
    if record.operation == "C05":
        result = RegulatoryRecurrenceTester().test(payload["observations"], context_key=context_key, minimum_recurrent_samples=int(payload["minimum_recurrent_samples"]), hotspot_window_bp=int(payload["hotspot_window_bp"]), minimum_hotspot_variants=int(payload["minimum_hotspot_variants"]), minimum_hotspot_samples=int(payload["minimum_hotspot_samples"]))
    elif record.operation == "C06":
        result = RegionalBurdenTester().test(payload["regions"], payload["observations"], region_id="reg-c06", context_key=context_key, background_rate=payload["background_rate"])
    elif record.operation == "C07":
        result = FunctionalConvergenceTester().test(payload["observations"], context_key=context_key, minimum_observed_variants=int(payload["minimum_observed_variants"]), ambiguity_margin=float(payload["ambiguity_margin"]))
    elif record.operation == "C08":
        result = PathwayRegulonConvergenceTester().test(payload["observations"], context_key=context_key, set_kind=payload["set_kind"], minimum_genes=int(payload["minimum_genes"]), ambiguity_margin=float(payload["ambiguity_margin"]))
    else:
        raise ValueError(f"unsupported C05-C08 operation: {record.operation}")
    return result.to_dict()


def evaluate_cohort_beta_frontier_fixture(fixture: CohortBetaFrontierFixture | None = None) -> CohortBetaFrontierEvaluation:
    value = fixture or default_cohort_beta_frontier_fixture()
    rows: list[CohortBetaFrontierEvaluationRow] = []
    for record in value.records:
        try:
            result = _evaluate(record, value.context_key)
            observed = CohortBetaState(str(result["state"]))
            accepted = observed is record.expected_state
            warnings = tuple(str(item) for item in result.get("warnings", ()))
        except (KeyError, TypeError, ValueError) as exc:
            result = {"error": str(exc)}
            observed = CohortBetaState.ABSTAINED
            accepted = False
            warnings = ("fixture execution failed",)
        body = {"operation": record.operation, "record_id": record.record_id, "expected_state": record.expected_state, "observed_state": observed, "accepted": accepted, "result": result}
        rows.append(CohortBetaFrontierEvaluationRow(record.operation, record.record_id, record.expected_state, observed, accepted, result, warnings, content_hash(body, prefix="evaluation-row")))
    values = tuple(rows)
    body = {"fixture_id": value.fixture_id, "rows": values}
    return CohortBetaFrontierEvaluation(value.fixture_id, values, all(item.accepted for item in values), sum(item.observed_state is CohortBetaState.SUPPORTED for item in values), sum(item.expected_state is not CohortBetaState.SUPPORTED for item in values), sum(not item.accepted for item in values), content_hash(body, prefix="evaluation"))


__all__ = ["CohortBetaFrontierEvaluation", "CohortBetaFrontierEvaluationRow", "evaluate_cohort_beta_frontier_fixture"]
