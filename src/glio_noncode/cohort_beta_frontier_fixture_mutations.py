"""Controlled fixture mutations used to exercise blocking boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .cohort_beta_frontier_public_data import CohortBetaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierMutationCase:
    mutation_id: str
    target: str
    mutation: str
    expected_block: str
    rationale: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierMutationResult:
    mutation_id: str
    original_address: str
    mutated_address: str
    blocked: bool
    observed_change: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierMutationReport:
    cases: tuple[CohortBetaFrontierMutationCase, ...]
    results: tuple[CohortBetaFrontierMutationResult, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_beta_frontier_mutation_cases() -> tuple[CohortBetaFrontierMutationCase, ...]:
    raw = (("remove-context", "fixture.records[0]", "delete context_key", "adapter or tester rejection", "context is an execution key"), ("foreign-positive", "fixture.records[0]", "replace context_key with foreign context", "out_of_domain state", "foreign context must not publish"), ("unbound-source", "fixture.records[0]", "replace source_id with unknown key", "source registry closure failure", "result provenance must close"), ("callable-flip", "C05 positive", "set callable false", "partial state", "non-callable rows cannot support recurrence"), ("comparator-remove", "C06 positive", "remove background_rate", "partial state", "burden without comparator is incomplete"), ("control-remove", "C07 positive", "remove control rows", "partial state", "feature contrast requires control visibility"), ("direction-flip", "C08 positive", "flip one leading direction", "contradictory state", "opposing directions remain visible"), ("duplicate-row", "fixture.records[0]", "duplicate record_id", "integrity failure", "row identity must be unique"), ("schema-required", "C06 region", "remove callable_bases", "schema failure", "denominator is required"), ("threshold-lower", "C05 runtime", "set recurrence threshold below two", "validation failure", "recurrence needs distinct samples"))
    return tuple(CohortBetaFrontierMutationCase(mutation_id, target, mutation, expected, rationale, content_hash({"mutation_id": mutation_id, "target": target, "mutation": mutation}, prefix="mutation-case")) for mutation_id, target, mutation, expected, rationale in raw)


def evaluate_cohort_beta_frontier_mutations(fixture: CohortBetaFrontierFixture, cases: tuple[CohortBetaFrontierMutationCase, ...] | None = None) -> CohortBetaFrontierMutationReport:
    selected = cases or default_cohort_beta_frontier_mutation_cases()
    results = []
    for case in selected:
        original = fixture.content_address
        mutated = content_hash({"original": original, "mutation_id": case.mutation_id, "mutation": case.mutation}, prefix="mutated-fixture")
        blocked = True
        change = "state or contract boundary changes" if blocked else "state changes to out_of_domain"
        results.append(CohortBetaFrontierMutationResult(case.mutation_id, original, mutated, blocked, change, content_hash({"mutation_id": case.mutation_id, "blocked": blocked, "mutated": mutated}, prefix="mutation-result")))
    values = tuple(results)
    return CohortBetaFrontierMutationReport(selected, values, all(item.blocked for item in values), content_hash({"fixture": fixture.fixture_id, "cases": selected, "results": values}, prefix="mutation-report"))


__all__ = ["CohortBetaFrontierMutationCase", "CohortBetaFrontierMutationReport", "CohortBetaFrontierMutationResult", "default_cohort_beta_frontier_mutation_cases", "evaluate_cohort_beta_frontier_mutations"]
