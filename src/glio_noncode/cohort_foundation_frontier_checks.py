"""Invariant checks that prevent silent degradation of cohort controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_fixture_eval import CohortFoundationEvaluation
from .cohort_foundation_frontier_policy import CohortFoundationDisposition, CohortFoundationPolicy
from .cohort_foundation_frontier_public_data import CohortFoundationFixture, CohortFoundationOperation, CohortFoundationRole
from .cohort_foundation_frontier_reconciliation import CohortFoundationReconciliation


@dataclass(frozen=True, slots=True)
class CohortFoundationInvariant:
    invariant_id: str
    description: str
    blocking: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationInvariantResult:
    invariant_id: str
    passed: bool
    blocking: bool
    observed: Any
    expected: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationInvariantReport:
    report_id: str
    invariants: tuple[CohortFoundationInvariant, ...]
    results: tuple[CohortFoundationInvariantResult, ...]
    accepted: bool
    content_address: str

    @property
    def failures(self) -> tuple[CohortFoundationInvariantResult, ...]:
        return tuple(item for item in self.results if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_foundation_frontier_invariants() -> tuple[CohortFoundationInvariant, ...]:
    values = (
        ("records-have-sources", "every record cites at least one declared source", True),
        ("operation-complete", "all four operations are represented", True),
        ("positive-complete", "each operation has one positive path", True),
        ("control-complete", "each operation has three control paths", True),
        ("evaluation-cardinality", "evaluation count equals fixture count", True),
        ("state-reconciled", "expected and actual states reconcile", True),
        ("foreign-quarantined", "foreign-context records are quarantined", True),
        ("supported-descriptive", "supported records are descriptively allowed", True),
        ("review-visible", "partial and absent paths enter review", True),
        ("context-preserved", "fixture contexts are not rewritten", True),
        ("execution-addressed", "every execution has a content address", True),
        ("no-clinical-claims", "policy contracts retain prohibited claims", True),
    )
    return tuple(CohortFoundationInvariant(item[0], item[1], item[2], content_hash(item)) for item in values)


def run_cohort_foundation_frontier_invariants(fixture: CohortFoundationFixture, evaluation: CohortFoundationEvaluation, policy: CohortFoundationPolicy, reconciliation: CohortFoundationReconciliation) -> CohortFoundationInvariantReport:
    source_ids = {item.source_id for item in fixture.sources}
    values: tuple[tuple[str, bool, Any, Any, str], ...] = (
        ("records-have-sources", all(set(item.source_ids) <= source_ids for item in fixture.records), all(set(item.source_ids) <= source_ids for item in fixture.records), True, "source closure"),
        ("operation-complete", {item.operation for item in fixture.records} == set(CohortFoundationOperation), {item.operation for item in fixture.records}, set(CohortFoundationOperation), "operation coverage"),
        ("positive-complete", all(sum(item.role is CohortFoundationRole.POSITIVE for item in fixture.records_for(operation)) == 1 for operation in CohortFoundationOperation), all(sum(item.role is CohortFoundationRole.POSITIVE for item in fixture.records_for(operation)) == 1 for operation in CohortFoundationOperation), True, "positive balance"),
        ("control-complete", all(sum(item.role is CohortFoundationRole.CONTROL for item in fixture.records_for(operation)) >= 3 for operation in CohortFoundationOperation), all(sum(item.role is CohortFoundationRole.CONTROL for item in fixture.records_for(operation)) >= 3 for operation in CohortFoundationOperation), True, "control balance"),
        ("evaluation-cardinality", len(evaluation.executions) == len(fixture.records), len(evaluation.executions), len(fixture.records), "execution cardinality"),
        ("state-reconciled", reconciliation.reconciled, reconciliation.reconciled, True, "state reconciliation"),
        ("foreign-quarantined", all(policy.decision_for(item.record_id).disposition is CohortFoundationDisposition.QUARANTINE for item in evaluation.executions if item.actual_state == "out_of_domain"), True, True, "foreign state policy"),
        ("supported-descriptive", all(policy.decision_for(item.record_id).disposition is CohortFoundationDisposition.ALLOW_DESCRIPTIVE for item in evaluation.executions if item.actual_state == "supported"), True, True, "supported policy"),
        ("review-visible", all(policy.decision_for(item.record_id).disposition is CohortFoundationDisposition.REVIEW for item in evaluation.executions if item.actual_state in {"partial", "absent", "abstained"}), True, True, "review policy"),
        ("context-preserved", all(item.context_key in {fixture.context_key, fixture.foreign_context_key} for item in fixture.records), True, True, "context closure"),
        ("execution-addressed", all(bool(item.content_address) for item in evaluation.executions), True, True, "execution addresses"),
        ("no-clinical-claims", all(contract for decision in policy.decisions for contract in decision.prohibited_claims), True, True, "claim ceiling"),
    )
    definitions = default_cohort_foundation_frontier_invariants()
    results = tuple(CohortFoundationInvariantResult(invariant_id, passed, definitions[index].blocking, observed, expected, detail, content_hash((invariant_id, passed, observed, expected, detail))) for index, (invariant_id, passed, observed, expected, detail) in enumerate(values))
    body = {"report_id": "cohort-foundation-frontier-invariants", "invariants": definitions, "results": results}
    return CohortFoundationInvariantReport(body["report_id"], definitions, results, all(item.passed for item in results), content_hash(body))


def cohort_foundation_frontier_observation_map(report: CohortFoundationInvariantReport) -> dict[str, bool]:
    return {item.invariant_id: item.passed for item in report.results}


__all__ = ["CohortFoundationInvariant", "CohortFoundationInvariantReport", "CohortFoundationInvariantResult", "cohort_foundation_frontier_observation_map", "default_cohort_foundation_frontier_invariants", "run_cohort_foundation_frontier_invariants"]
