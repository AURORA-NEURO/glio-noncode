"""Threshold and evidence rules for the C09-C12 release surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha import CohortAlphaState
from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierThresholdRule:
    rule_id: str
    operation: str
    metric: str
    minimum: float
    maximum: float | None
    unit: str
    rationale: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierThresholdAssessment:
    rule_id: str
    operation: str
    observed: float
    accepted: bool
    state: CohortAlphaState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierThresholdReport:
    rules: tuple[CohortAlphaFrontierThresholdRule, ...]
    assessments: tuple[CohortAlphaFrontierThresholdAssessment, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _rule(rule_id: str, operation: str, metric: str, minimum: float, maximum: float | None, unit: str, rationale: str) -> CohortAlphaFrontierThresholdRule:
    body = {"rule_id": rule_id, "operation": operation, "metric": metric, "minimum": minimum, "maximum": maximum, "unit": unit, "rationale": rationale}
    return CohortAlphaFrontierThresholdRule(rule_id, operation, metric, minimum, maximum, unit, rationale, content_hash(body, prefix="alpha-threshold-rule"))


def default_cohort_alpha_frontier_thresholds() -> tuple[CohortAlphaFrontierThresholdRule, ...]:
    return (
        _rule("C09-clonal-share", "C09", "clonal_share", 0.0, 1.0, "fraction", "bounded clonal fraction"),
        _rule("C09-subclonal-share", "C09", "subclonal_share", 0.0, 1.0, "fraction", "bounded subclonal fraction"),
        _rule("C10-primary-change", "C10", "primary_change", 0.0, 1.0, "fraction", "bounded recurrence change"),
        _rule("C11-selection-change", "C11", "selection_change", 0.0, 1.0, "fraction", "bounded exposure selection change"),
        _rule("C12-concordance", "C12", "concordance", 0.0, 1.0, "fraction", "bounded cross-cohort concordance"),
        _rule("all-row-count", "ALL", "row_count", 16.0, 16.0, "rows", "fixture cardinality is fixed"),
    )


def assess_cohort_alpha_frontier_thresholds(evaluation: CohortAlphaFrontierEvaluation, rules: tuple[CohortAlphaFrontierThresholdRule, ...] | None = None) -> CohortAlphaFrontierThresholdReport:
    selected = rules or default_cohort_alpha_frontier_thresholds()
    assessments: list[CohortAlphaFrontierThresholdAssessment] = []
    for rule in selected:
        rows = tuple(row for row in evaluation.rows if rule.operation in {"ALL", row.operation})
        if rule.metric == "row_count":
            observed = float(len(rows)) if rule.operation != "ALL" else float(len(evaluation.rows))
        else:
            supported = sum(row.observed_state is CohortAlphaState.SUPPORTED for row in rows)
            observed = supported / max(1, len(rows))
        accepted = rule.minimum <= observed and (rule.maximum is None or observed <= rule.maximum)
        state = CohortAlphaState.SUPPORTED if accepted else CohortAlphaState.PARTIAL
        assessments.append(CohortAlphaFrontierThresholdAssessment(rule.rule_id, rule.operation, round(observed, 6), accepted, state, content_hash({"rule": rule.rule_id, "observed": observed, "accepted": accepted}, prefix="alpha-threshold")))
    values = tuple(assessments)
    return CohortAlphaFrontierThresholdReport(tuple(selected), values, all(item.accepted for item in values), content_hash(values, prefix="alpha-threshold-report"))


__all__ = ["CohortAlphaFrontierThresholdAssessment", "CohortAlphaFrontierThresholdReport", "CohortAlphaFrontierThresholdRule", "assess_cohort_alpha_frontier_thresholds", "default_cohort_alpha_frontier_thresholds"]
