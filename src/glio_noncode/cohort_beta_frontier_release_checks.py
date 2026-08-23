"""Release checks collected independently from the main quality gate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .cohort_beta_frontier_claim_boundary import CohortBetaFrontierClaimBoundary
from .cohort_beta_frontier_fixture_eval import CohortBetaFrontierEvaluation
from .cohort_beta_frontier_public_data import CohortBetaFrontierFixture
from .cohort_beta_frontier_replay import CohortBetaFrontierReplayReceipt
from .cohort_beta_frontier_safety import CohortBetaFrontierSafetyReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierReleaseCheckDefinition:
    check_id: str
    title: str
    blocking: bool
    evidence_required: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierReleaseCheckResult:
    check_id: str
    accepted: bool
    observed_value: str
    failure_action: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierReleaseChecks:
    definitions: tuple[CohortBetaFrontierReleaseCheckDefinition, ...]
    results: tuple[CohortBetaFrontierReleaseCheckResult, ...]
    accepted: bool
    blocking_failure_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_beta_frontier_release_check_definitions() -> tuple[CohortBetaFrontierReleaseCheckDefinition, ...]:
    raw = (("fixture-cardinality", "fixture has exactly sixteen bounded paths", True, ("fixture audit",)), ("evaluation-reconciliation", "all expected states reconcile", True, ("evaluation", "reconciliation")), ("safety-report", "publication safety has no failures", True, ("safety report",)), ("claim-boundary", "claim ceiling is attached", True, ("claim boundary",)), ("replay-determinism", "same input returns same address", True, ("replay receipt",)), ("public-source-closure", "all source URLs are public receipts", True, ("source registry",)), ("review-retention", "non-publishable rows are retained", True, ("review queue",)), ("negative-paths", "foreign and contradictory paths are present", False, ("fixture controls",)), ("operation-coverage", "all four operation IDs are represented", True, ("metrics",)), ("report-ceiling", "report includes bounded claim language", True, ("report",)))
    return tuple(CohortBetaFrontierReleaseCheckDefinition(check_id, title, blocking, evidence, content_hash({"check_id": check_id, "title": title, "blocking": blocking, "evidence": evidence}, prefix="release-definition")) for check_id, title, blocking, evidence in raw)


def run_cohort_beta_frontier_release_checks(fixture: CohortBetaFrontierFixture, evaluation: CohortBetaFrontierEvaluation, safety: CohortBetaFrontierSafetyReport, boundary: CohortBetaFrontierClaimBoundary, replay: CohortBetaFrontierReplayReceipt, *, definitions: Iterable[CohortBetaFrontierReleaseCheckDefinition] | None = None) -> CohortBetaFrontierReleaseChecks:
    observed = {"fixture-cardinality": len(fixture.records) == 16, "evaluation-reconciliation": evaluation.accepted, "safety-report": safety.accepted, "claim-boundary": boundary.accepted, "replay-determinism": replay.deterministic, "public-source-closure": all(source.url.startswith("https://") for source in fixture.sources), "review-retention": sum(row.expected_state.value != "supported" for row in fixture.records) == 12, "negative-paths": any(row.expected_state.value == "out_of_domain" for row in fixture.records) and any(row.expected_state.value == "contradictory" for row in fixture.records), "operation-coverage": {row.operation for row in evaluation.rows} == {"C05", "C06", "C07", "C08"}, "report-ceiling": bool(boundary.prohibited_claims)}
    selected = tuple(definitions or default_cohort_beta_frontier_release_check_definitions())
    results = []
    for definition in selected:
        accepted = observed[definition.check_id]
        action = "continue release" if accepted else "hold release and open review"
        results.append(CohortBetaFrontierReleaseCheckResult(definition.check_id, accepted, str(observed[definition.check_id]), action, content_hash({"check_id": definition.check_id, "accepted": accepted, "observed": observed[definition.check_id]}, prefix="release-result")))
    values = tuple(results)
    blocking_failures = sum(not result.accepted for result, definition in zip(values, selected) if definition.blocking)
    return CohortBetaFrontierReleaseChecks(selected, values, blocking_failures == 0, blocking_failures, content_hash({"definitions": selected, "results": values, "blocking_failures": blocking_failures}, prefix="release-checks"))


__all__ = ["CohortBetaFrontierReleaseCheckDefinition", "CohortBetaFrontierReleaseCheckResult", "CohortBetaFrontierReleaseChecks", "default_cohort_beta_frontier_release_check_definitions", "run_cohort_beta_frontier_release_checks"]
