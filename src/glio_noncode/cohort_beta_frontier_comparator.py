"""Comparator accounting for callable, matched, and control spaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .cohort_beta import CohortBetaState
from .cohort_beta_frontier_fixture_eval import CohortBetaFrontierEvaluation
from .cohort_beta_frontier_public_data import CohortBetaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierComparatorDefinition:
    operation: str
    comparator_id: str
    numerator: str
    denominator: str
    matching_keys: tuple[str, ...]
    exclusion_rules: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierComparatorReceipt:
    operation: str
    comparator_id: str
    observed_units: int
    comparator_units: int
    callable_units: int | None
    contrast: float | None
    state: str
    limitation: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierComparatorReport:
    definitions: tuple[CohortBetaFrontierComparatorDefinition, ...]
    receipts: tuple[CohortBetaFrontierComparatorReceipt, ...]
    accepted: bool
    content_address: str

    def receipt_for(self, operation: str) -> CohortBetaFrontierComparatorReceipt:
        return next(item for item in self.receipts if item.operation == operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_beta_frontier_comparator_definitions() -> tuple[CohortBetaFrontierComparatorDefinition, ...]:
    raw = (("C05", "distinct-sample-recurrence", "recurrent variants", "callable observations", ("context_key", "sample_id"), ("foreign context", "non-callable rows")), ("C06", "callable-regional-burden", "distinct regional variants", "callable bases", ("context_key", "region_id"), ("foreign context", "outside region")), ("C07", "matched-functional-control", "observed feature support", "control feature support", ("context_key", "feature_id", "feature_class"), ("missing controls", "foreign context")), ("C08", "matched-set-control", "observed set membership", "control set membership", ("context_key", "set_id", "set_kind"), ("missing controls", "foreign context")))
    return tuple(CohortBetaFrontierComparatorDefinition(operation, comparator_id, numerator, denominator, matching, exclusions, content_hash({"operation": operation, "comparator_id": comparator_id, "matching": matching}, prefix="comparator-definition")) for operation, comparator_id, numerator, denominator, matching, exclusions in raw)


def _receipt(definition: CohortBetaFrontierComparatorDefinition, row: Any) -> CohortBetaFrontierComparatorReceipt:
    result = row.result
    state = str(result.get("state", row.observed_state.value))
    if definition.operation == "C05":
        observed = int(result.get("observed_variant_count", 0))
        comparator = len(result.get("recurrent_variant_ids", ()))
        callable_units = observed
        contrast = None if not observed else round(comparator / observed, 9)
        limitation = "recurrence fraction is descriptive and not calibrated enrichment"
    elif definition.operation == "C06":
        observed = int(result.get("observed_variant_count", 0))
        expected = result.get("expected_count")
        comparator = 0 if expected is None else int(round(float(expected), 0))
        callable_units = int(result.get("callable_bases", 0)) or None
        contrast = result.get("excess_ratio")
        limitation = "regional contrast depends on callable-space and comparator definition"
    elif definition.operation == "C07":
        observed = int(result.get("observed_variant_count", 0))
        comparator = sum(int(feature.get("control_variant_count", 0)) for feature in result.get("features", ()))
        callable_units = None
        contrast = result.get("convergence_score")
        limitation = "functional support is a bounded feature contrast"
    else:
        observed = int(result.get("observed_variant_count", 0))
        comparator = sum(int(summary.get("control_gene_count", 0)) for summary in result.get("sets", ()))
        callable_units = None
        contrast = result.get("convergence_score")
        limitation = "set convergence depends on versioned membership definitions"
    body = {"operation": definition.operation, "comparator_id": definition.comparator_id, "observed": observed, "comparator": comparator, "callable": callable_units, "contrast": contrast, "state": state}
    return CohortBetaFrontierComparatorReceipt(definition.operation, definition.comparator_id, observed, comparator, callable_units, None if contrast is None else float(contrast), state, limitation, content_hash(body, prefix="comparator-receipt"))


def build_cohort_beta_frontier_comparator_report(fixture: CohortBetaFrontierFixture, evaluation: CohortBetaFrontierEvaluation, definitions: Iterable[CohortBetaFrontierComparatorDefinition] | None = None) -> CohortBetaFrontierComparatorReport:
    selected = tuple(definitions or default_cohort_beta_frontier_comparator_definitions())
    receipts = []
    for definition in selected:
        candidates = tuple(row for row in evaluation.rows if row.operation == definition.operation and row.observed_state is CohortBetaState.SUPPORTED)
        row = candidates[0] if candidates else next(row for row in evaluation.rows if row.operation == definition.operation)
        receipts.append(_receipt(definition, row))
    values = tuple(receipts)
    return CohortBetaFrontierComparatorReport(selected, values, len(selected) == 4 and len(values) == 4 and all(item.state for item in values), content_hash({"definitions": selected, "receipts": values, "fixture": fixture.fixture_id}, prefix="comparator-report"))


def compare_cohort_beta_frontier_receipts(left: CohortBetaFrontierComparatorReceipt, right: CohortBetaFrontierComparatorReceipt) -> dict[str, Any]:
    return {"operation": left.operation, "same_comparator": left.comparator_id == right.comparator_id, "observed_delta": left.observed_units - right.observed_units, "comparator_delta": left.comparator_units - right.comparator_units, "contrast_delta": None if left.contrast is None or right.contrast is None else round(left.contrast - right.contrast, 9)}


__all__ = ["CohortBetaFrontierComparatorDefinition", "CohortBetaFrontierComparatorReceipt", "CohortBetaFrontierComparatorReport", "build_cohort_beta_frontier_comparator_report", "compare_cohort_beta_frontier_receipts", "default_cohort_beta_frontier_comparator_definitions"]
