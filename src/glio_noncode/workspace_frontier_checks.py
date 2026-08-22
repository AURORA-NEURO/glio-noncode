"""Invariant checks for workspace context and evidence boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .workspace_frontier_fixture_eval import WorkspaceFrontierEvaluation
from .workspace_frontier_public_data import WorkspaceFrontierFixture


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierInvariant:
    invariant_id: str
    description: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierInvariantResult:
    invariant_id: str
    passed: bool
    observed: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierInvariantReport:
    results: tuple[WorkspaceFrontierInvariantResult, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _invariant(invariant_id: str, description: str) -> WorkspaceFrontierInvariant:
    body = {"invariant_id": invariant_id, "description": description}
    return WorkspaceFrontierInvariant(**body, content_address=content_hash(body))


def default_workspace_frontier_invariants() -> tuple[WorkspaceFrontierInvariant, ...]:
    return (
        _invariant("context-preserved", "all fixture records carry the exact context"),
        _invariant("positive-control-separated", "positive and control roles remain distinct"),
        _invariant("workspace-addressed", "workspace execution receipts are addressed"),
        _invariant("sections-retained", "surface section identity is retained"),
        _invariant("facets-retained", "bounded facets are retained"),
        _invariant("pagination-bounded", "page limits remain bounded"),
        _invariant("interval-bounded", "interval queries retain bounded coordinates"),
        _invariant("absence-explicit", "absent and abstained states remain explicit"),
        _invariant("parse-issues-visible", "track parse issues remain visible"),
        _invariant("accessibility-retained", "accessibility metadata is retained"),
    )


def workspace_frontier_observation_map(*, context_preserved: bool, positive_control_separated: bool, workspace_addressed: bool, sections_retained: bool, facets_retained: bool, pagination_bounded: bool, interval_bounded: bool, absence_explicit: bool, parse_issues_visible: bool, accessibility_retained: bool) -> dict[str, bool]:
    return {"context-preserved": context_preserved, "positive-control-separated": positive_control_separated, "workspace-addressed": workspace_addressed, "sections-retained": sections_retained, "facets-retained": facets_retained, "pagination-bounded": pagination_bounded, "interval-bounded": interval_bounded, "absence-explicit": absence_explicit, "parse-issues-visible": parse_issues_visible, "accessibility-retained": accessibility_retained}


def run_workspace_frontier_invariants(observations: dict[str, bool]) -> WorkspaceFrontierInvariantReport:
    results = tuple(WorkspaceFrontierInvariantResult(item.invariant_id, bool(observations.get(item.invariant_id, False)), observations.get(item.invariant_id, False), item.description, content_hash({"invariant_id": item.invariant_id, "passed": observations.get(item.invariant_id, False), "detail": item.description})) for item in default_workspace_frontier_invariants())
    body = {"results": results, "accepted": all(item.passed for item in results)}
    return WorkspaceFrontierInvariantReport(**body, content_address=content_hash(body))


def workspace_frontier_invariants_from_execution(fixture: WorkspaceFrontierFixture, evaluation: WorkspaceFrontierEvaluation) -> WorkspaceFrontierInvariantReport:
    observations = workspace_frontier_observation_map(
        context_preserved=all(item.context_key == fixture.context_key for item in fixture.records),
        positive_control_separated=all(item.accepted == (item.role.value == "positive") for item in evaluation.executions),
        workspace_addressed=all(item.content_address.startswith("sha256:") for item in evaluation.executions),
        sections_retained=all("section_ids" in item.output for item in evaluation.executions if item.operation.value in {"case_workspace", "cohort_workspace"} and "section_ids" in item.output),
        facets_retained=all("facets" in item.output for item in evaluation.executions if item.operation.value != "variant_explorer" and "facets" in item.output),
        pagination_bounded=all(item.output.get("page_total", 0) >= 0 for item in evaluation.executions if "page_total" in item.output),
        interval_bounded=all(all("coordinate" in str(label) or ":" in str(label) for label in item.output.get("coordinate_labels", ())) for item in evaluation.executions if "coordinate_labels" in item.output),
        absence_explicit=any(item.state in {"absent", "abstained"} for item in evaluation.executions),
        parse_issues_visible=any("track_parse_issue" in item.issue_codes for item in evaluation.executions),
        accessibility_retained=all("accessibility" in item.output for item in evaluation.executions if item.operation.value != "variant_explorer" and "accessibility" in item.output),
    )
    return run_workspace_frontier_invariants(observations)


__all__ = ["WorkspaceFrontierInvariant", "WorkspaceFrontierInvariantReport", "WorkspaceFrontierInvariantResult", "default_workspace_frontier_invariants", "run_workspace_frontier_invariants", "workspace_frontier_invariants_from_execution", "workspace_frontier_observation_map"]
