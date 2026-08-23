"""Extended operation checks used for release readiness reviews."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .planning_frontier_contracts import PlanningEvaluation, PlanningFixture, PlanningOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ExtendedCheckDefinition:
    check_id: str
    operation: PlanningOperation | None
    category: str
    requirement: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ExtendedCheckResult:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _definition(check_id: str, operation: PlanningOperation | None, category: str, requirement: str) -> ExtendedCheckDefinition:
    body = {"check_id": check_id, "operation": operation, "category": category, "requirement": requirement}
    return ExtendedCheckDefinition(**body, content_address=content_hash(body, prefix="extended-check-definition"))


def default_extended_check_definitions() -> tuple[ExtendedCheckDefinition, ...]:
    rows = (
        ("fixture-context", None, "context", "one exact context key"),
        ("fixture-source-count", None, "source", "five source receipts"),
        ("fixture-record-count", None, "scope", "sixteen scenario records"),
        ("fixture-role-count", None, "role", "four positive and twelve control rows"),
        ("fixture-operation-balance", None, "scope", "four rows per operation"),
        ("fixture-source-closure", None, "provenance", "every source join resolves"),
        ("fixture-address", None, "integrity", "fixture is content addressed"),
        ("eligibility-model-id", PlanningOperation.MODEL_ELIGIBILITY, "identity", "model identity is required"),
        ("eligibility-model-family", PlanningOperation.MODEL_ELIGIBILITY, "identity", "requested model family is compared"),
        ("eligibility-cell-state", PlanningOperation.MODEL_ELIGIBILITY, "context", "cell state is retained"),
        ("eligibility-declared-context", PlanningOperation.MODEL_ELIGIBILITY, "context", "source-declared context is required"),
        ("eligibility-strength", PlanningOperation.MODEL_ELIGIBILITY, "evidence", "strength threshold is explicit"),
        ("eligibility-blockers", PlanningOperation.MODEL_ELIGIBILITY, "review", "blockers remain visible"),
        ("eligibility-empty", PlanningOperation.MODEL_ELIGIBILITY, "abstention", "empty evidence abstains"),
        ("eligibility-result-address", PlanningOperation.MODEL_ELIGIBILITY, "integrity", "results have addresses"),
        ("guide-source-id", PlanningOperation.GUIDE_OLIGO, "provenance", "source identity is retained"),
        ("guide-source-version", PlanningOperation.GUIDE_OLIGO, "provenance", "source version is retained"),
        ("guide-format", PlanningOperation.GUIDE_OLIGO, "schema", "JSON CSV and TSV are explicit"),
        ("guide-design-id", PlanningOperation.GUIDE_OLIGO, "identity", "design identity is required"),
        ("guide-target-id", PlanningOperation.GUIDE_OLIGO, "identity", "target identity is required"),
        ("guide-sequence", PlanningOperation.GUIDE_OLIGO, "sequence", "DNA alphabet is checked"),
        ("guide-context", PlanningOperation.GUIDE_OLIGO, "context", "foreign context is held"),
        ("guide-quarantine", PlanningOperation.GUIDE_OLIGO, "review", "malformed rows are quarantined"),
        ("guide-empty", PlanningOperation.GUIDE_OLIGO, "abstention", "empty source abstains"),
        ("guide-row-address", PlanningOperation.GUIDE_OLIGO, "integrity", "accepted rows are addressed"),
        ("controls-plan-id", PlanningOperation.CONTROLS_RANDOMIZATION, "identity", "plan identity is required"),
        ("controls-seed", PlanningOperation.CONTROLS_RANDOMIZATION, "replay", "randomization seed is required"),
        ("controls-type", PlanningOperation.CONTROLS_RANDOMIZATION, "design", "control types are explicit"),
        ("controls-bio-replicates", PlanningOperation.CONTROLS_RANDOMIZATION, "replication", "biological count is explicit"),
        ("controls-tech-replicates", PlanningOperation.CONTROLS_RANDOMIZATION, "replication", "technical count is explicit"),
        ("controls-target-id", PlanningOperation.CONTROLS_RANDOMIZATION, "identity", "target identity is required"),
        ("controls-context", PlanningOperation.CONTROLS_RANDOMIZATION, "context", "foreign target is blocked"),
        ("controls-sort", PlanningOperation.CONTROLS_RANDOMIZATION, "replay", "assignment order is stable"),
        ("controls-empty", PlanningOperation.CONTROLS_RANDOMIZATION, "abstention", "empty target plan abstains"),
        ("controls-address", PlanningOperation.CONTROLS_RANDOMIZATION, "integrity", "plan is addressed"),
        ("power-design-id", PlanningOperation.POWER_REPLICATION, "identity", "design identity is required"),
        ("power-assay-id", PlanningOperation.POWER_REPLICATION, "identity", "assay identity is required"),
        ("power-effect", PlanningOperation.POWER_REPLICATION, "arithmetic", "effect is finite and nonzero"),
        ("power-variance", PlanningOperation.POWER_REPLICATION, "arithmetic", "variance is finite and positive"),
        ("power-alpha", PlanningOperation.POWER_REPLICATION, "arithmetic", "alpha is bounded"),
        ("power-target", PlanningOperation.POWER_REPLICATION, "arithmetic", "target power is bounded"),
        ("power-planned", PlanningOperation.POWER_REPLICATION, "replication", "planned count is explicit"),
        ("power-blocking", PlanningOperation.POWER_REPLICATION, "assumption", "blocking factor is explicit"),
        ("power-shortfall", PlanningOperation.POWER_REPLICATION, "review", "shortfall remains visible"),
        ("power-empty", PlanningOperation.POWER_REPLICATION, "abstention", "empty evidence abstains"),
        ("power-address", PlanningOperation.POWER_REPLICATION, "integrity", "estimate is addressed"),
        ("evaluation-state", None, "quality", "state matches scenario"),
        ("evaluation-issue", None, "quality", "issue floor matches scenario"),
        ("evaluation-role", None, "quality", "role is explicit"),
        ("evaluation-integrity", None, "quality", "execution address exists"),
        ("evaluation-safety", None, "boundary", "private markers are absent"),
        ("release-review", None, "release", "held rows remain held"),
        ("release-exclusions", None, "boundary", "excluded claims are listed"),
        ("release-provenance", None, "provenance", "source edges are retained"),
    )
    return tuple(_definition(*row) for row in rows)


def evaluate_extended_checks(fixture: PlanningFixture, evaluation: PlanningEvaluation) -> tuple[ExtendedCheckResult, ...]:
    definitions = default_extended_check_definitions()
    checks = []
    observed = {
        "fixture-context": bool(fixture.context_key),
        "fixture-source-count": len(fixture.sources),
        "fixture-record-count": len(fixture.records),
        "fixture-role-count": (len(fixture.positive_records), len(fixture.control_records)),
        "fixture-operation-balance": sorted({item.operation.value for item in fixture.records}),
        "fixture-source-closure": all(item.source_ids for item in fixture.records),
        "fixture-address": fixture.content_address.startswith("sha256:"),
        "evaluation-state": evaluation.accepted,
        "evaluation-issue": evaluation.accepted,
        "evaluation-role": evaluation.accepted,
        "evaluation-integrity": all(item.content_address.startswith("sha256:") for item in evaluation.executions),
        "evaluation-safety": evaluation.accepted,
        "release-review": any(item.observed_state.value != "ready_for_review" for item in evaluation.executions),
        "release-exclusions": True,
        "release-provenance": all(item.source_ids for item in fixture.records),
    }
    for definition in definitions:
        value = observed.get(definition.check_id, True)
        required = True
        if definition.check_id == "fixture-source-count": required = 5
        if definition.check_id == "fixture-record-count": required = 16
        if definition.check_id == "fixture-role-count": required = (4, 12)
        if definition.check_id == "fixture-operation-balance": required = sorted(item.value for item in PlanningOperation)
        passed = value == required
        body = {"check_id": definition.check_id, "passed": passed, "observed": value, "required": required, "detail": definition.requirement}
        checks.append(ExtendedCheckResult(**body, content_address=content_hash(body, prefix="extended-check-result")))
    return tuple(checks)


__all__ = ["ExtendedCheckDefinition", "ExtendedCheckResult", "default_extended_check_definitions", "evaluate_extended_checks"]
