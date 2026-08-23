"""Control coverage summary by operation and boundary type."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierEvaluation, LifecycleBetaFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierControlCoverage:
    operation: LifecycleBetaFrontierOperation
    control_count: int
    issue_count: int
    distinct_states: tuple[str, ...]
    covers_context: bool
    covers_empty_or_missing: bool
    covers_contradiction_or_change: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierControlReport:
    rows: tuple[LifecycleBetaFrontierControlCoverage, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_lifecycle_beta_frontier_control_coverage(evaluation: LifecycleBetaFrontierEvaluation) -> LifecycleBetaFrontierControlReport:
    rows = []
    for operation in LifecycleBetaFrontierOperation:
        controls = tuple(item for item in evaluation.by_operation(operation) if item.role.value == "control")
        issues = tuple(issue for item in controls for issue in item.issue_codes)
        body = {"operation": operation, "control_count": len(controls), "issue_count": len(issues), "distinct_states": tuple(sorted({item.state.value for item in controls})), "covers_context": any("context" in item for item in issues), "covers_empty_or_missing": any(item in issues for item in ("no_claims", "no_entries", "no_active_claims", "no_review_items", "required_decision_count", "unclassified_tier", "missing_parent", "invalid_uncertainty")) or any(str(item.output.get("kind")) in {"stable", "empty"} for item in controls), "covers_contradiction_or_change": any(item in issues for item in ("tier_direction_conflict", "split_verdict", "claim_changed", "claim_added", "citation_changed", "blocking_gate", "duplicate_log_id", "explicit_rejection"))}
        rows.append(LifecycleBetaFrontierControlCoverage(**body, content_address=content_hash(body)))
    accepted = all(item.control_count == 3 and item.covers_context and (item.covers_empty_or_missing or item.covers_contradiction_or_change) for item in rows)
    return LifecycleBetaFrontierControlReport(tuple(rows), accepted, content_hash({"rows": tuple(rows), "accepted": accepted}))


__all__ = ["LifecycleBetaFrontierControlCoverage", "LifecycleBetaFrontierControlReport", "build_lifecycle_beta_frontier_control_coverage"]
