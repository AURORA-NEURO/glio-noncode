"""Scenario coverage for context-qualified workspace behavior."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_frontier_public_data import WorkspaceFrontierOperation


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierScenario:
    scenario_id: str
    operation: WorkspaceFrontierOperation
    context_mode: str
    data_mode: str
    access_mode: str
    expected_state: str
    expected_issue_codes: tuple[str, ...]
    review_required: bool
    description: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.scenario_id, "scenario_id")
        require_non_empty(self.description, "description")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierScenarioMatrix:
    scenarios: tuple[WorkspaceFrontierScenario, ...]
    dimensions: tuple[str, ...]
    content_address: str

    @property
    def review_scenarios(self) -> tuple[WorkspaceFrontierScenario, ...]:
        return tuple(item for item in self.scenarios if item.review_required)

    @property
    def by_operation(self) -> dict[str, int]:
        return {operation.value: sum(item.operation is operation for item in self.scenarios) for operation in WorkspaceFrontierOperation}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"review_count": len(self.review_scenarios), "by_operation": self.by_operation}


def _scenario(scenario_id: str, operation: WorkspaceFrontierOperation, context_mode: str, data_mode: str, access_mode: str, expected_state: str, issues: tuple[str, ...], review_required: bool, description: str) -> WorkspaceFrontierScenario:
    body = {"scenario_id": scenario_id, "operation": operation, "context_mode": context_mode, "data_mode": data_mode, "access_mode": access_mode, "expected_state": expected_state, "expected_issue_codes": issues, "review_required": review_required, "description": description}
    return WorkspaceFrontierScenario(**body, content_address=content_hash(body))


def build_workspace_frontier_scenario_matrix() -> WorkspaceFrontierScenarioMatrix:
    scenarios = (
        _scenario("case-exact-complete", WorkspaceFrontierOperation.CASE_WORKSPACE, "exact", "variants-and-elements", "accessible", "partial", ("missing_dossier",), True, "case navigation retains incomplete optional sections"),
        _scenario("case-exact-with-dossier", WorkspaceFrontierOperation.CASE_WORKSPACE, "exact", "dossier-complete", "accessible", "supported", (), False, "complete case projection can be rendered"),
        _scenario("case-context-mismatch", WorkspaceFrontierOperation.CASE_WORKSPACE, "mismatch", "variants", "accessible", "out_of_domain", ("context_mismatch",), True, "case context mismatch withholds records"),
        _scenario("case-no-variants", WorkspaceFrontierOperation.CASE_WORKSPACE, "exact", "empty", "accessible", "invalid", ("invalid_workspace_input",), True, "empty case input is rejected"),
        _scenario("case-duplicate-variant", WorkspaceFrontierOperation.CASE_WORKSPACE, "exact", "duplicate", "accessible", "invalid", ("duplicate_variant_id",), True, "duplicate identities remain invalid"),
        _scenario("case-keyboard", WorkspaceFrontierOperation.CASE_WORKSPACE, "exact", "variants", "keyboard", "partial", ("missing_dossier",), True, "keyboard order is retained as metadata"),
        _scenario("case-focus", WorkspaceFrontierOperation.CASE_WORKSPACE, "exact", "variants", "focus-boundary", "partial", ("missing_dossier",), True, "focus boundary is explicit"),
        _scenario("case-reading-order", WorkspaceFrontierOperation.CASE_WORKSPACE, "exact", "variants", "reading-order", "partial", ("missing_dossier",), True, "reading order remains explicit for clients"),
        _scenario("cohort-exact", WorkspaceFrontierOperation.COHORT_WORKSPACE, "exact", "selected", "accessible", "supported", (), False, "selected rows remain separate from summaries"),
        _scenario("cohort-ood", WorkspaceFrontierOperation.COHORT_WORKSPACE, "mismatch", "selected", "accessible", "out_of_domain", ("context_mismatch",), True, "cohort context mismatch is withheld"),
        _scenario("cohort-empty", WorkspaceFrontierOperation.COHORT_WORKSPACE, "exact", "empty", "accessible", "absent", ("no_matching_records",), True, "empty cohort selection is absent"),
        _scenario("cohort-non-callable", WorkspaceFrontierOperation.COHORT_WORKSPACE, "exact", "non-callable", "accessible", "absent", ("no_matching_records",), True, "callability excludes a row"),
        _scenario("cohort-pagination", WorkspaceFrontierOperation.COHORT_WORKSPACE, "exact", "selected", "paged", "supported", (), False, "bounded paging is deterministic"),
        _scenario("cohort-facets", WorkspaceFrontierOperation.COHORT_WORKSPACE, "exact", "selected", "facets", "supported", (), False, "facets expose source and record type"),
        _scenario("cohort-labels", WorkspaceFrontierOperation.COHORT_WORKSPACE, "exact", "selected", "labels", "supported", (), False, "row and summary labels are supplied"),
        _scenario("variant-present", WorkspaceFrontierOperation.VARIANT_EXPLORER, "exact", "present", "accessible", "supported", (), False, "present variant resolves"),
        _scenario("variant-absent", WorkspaceFrontierOperation.VARIANT_EXPLORER, "exact", "absent", "accessible", "abstained", ("variant_absent",), True, "absent variant is not inferred"),
        _scenario("variant-ood", WorkspaceFrontierOperation.VARIANT_EXPLORER, "mismatch", "present", "accessible", "out_of_domain", ("context_mismatch",), True, "variant request context is gated"),
        _scenario("variant-invalid", WorkspaceFrontierOperation.VARIANT_EXPLORER, "exact", "invalid", "accessible", "invalid", ("invalid_workspace_input",), True, "malformed case blocks detail"),
        _scenario("variant-related", WorkspaceFrontierOperation.VARIANT_EXPLORER, "exact", "related", "accessible", "supported", (), False, "declared relationship groups are deterministic"),
        _scenario("variant-coordinate", WorkspaceFrontierOperation.VARIANT_EXPLORER, "exact", "present", "coordinate", "supported", (), False, "canonical coordinate is retained"),
        _scenario("variant-labels", WorkspaceFrontierOperation.VARIANT_EXPLORER, "exact", "present", "labels", "supported", (), False, "detail warnings and labels remain visible"),
        _scenario("track-valid", WorkspaceFrontierOperation.REGULATORY_TRACK_BROWSER, "exact", "valid", "accessible", "supported", (), False, "valid intervals become searchable records"),
        _scenario("track-parse-issue", WorkspaceFrontierOperation.REGULATORY_TRACK_BROWSER, "exact", "malformed-row", "accessible", "partial", ("track_parse_issue",), True, "parse issues remain visible beside features"),
        _scenario("track-ood", WorkspaceFrontierOperation.REGULATORY_TRACK_BROWSER, "mismatch", "valid", "accessible", "out_of_domain", ("context_mismatch",), True, "track context mismatch withholds results"),
        _scenario("track-empty", WorkspaceFrontierOperation.REGULATORY_TRACK_BROWSER, "exact", "empty", "accessible", "invalid", ("invalid_track_input",), True, "empty track input is rejected"),
        _scenario("track-overlap", WorkspaceFrontierOperation.REGULATORY_TRACK_BROWSER, "exact", "valid", "interval", "supported", (), False, "interval overlap is bounded"),
        _scenario("track-facets", WorkspaceFrontierOperation.REGULATORY_TRACK_BROWSER, "exact", "valid", "facets", "supported", (), False, "track facets expose source and state"),
        _scenario("track-coordinates", WorkspaceFrontierOperation.REGULATORY_TRACK_BROWSER, "exact", "valid", "coordinates", "supported", (), False, "coordinate labels are stable"),
        _scenario("track-source", WorkspaceFrontierOperation.REGULATORY_TRACK_BROWSER, "exact", "valid", "source-receipt", "supported", (), False, "source row hashes remain attached"),
        _scenario("track-keyboard", WorkspaceFrontierOperation.REGULATORY_TRACK_BROWSER, "exact", "valid", "keyboard", "supported", (), False, "interval records remain keyboard addressable"),
        _scenario("track-issues-label", WorkspaceFrontierOperation.REGULATORY_TRACK_BROWSER, "exact", "malformed-row", "labels", "partial", ("track_parse_issue",), True, "parse issue labels remain available"),
        _scenario("track-boundary", WorkspaceFrontierOperation.REGULATORY_TRACK_BROWSER, "exact", "valid", "boundary", "supported", (), False, "annotation-only boundary is visible"),
    )
    dimensions = ("operation", "context_mode", "data_mode", "access_mode", "expected_state", "review_required")
    body = {"scenarios": scenarios, "dimensions": dimensions}
    return WorkspaceFrontierScenarioMatrix(scenarios=scenarios, dimensions=dimensions, content_address=content_hash(body))


__all__ = [
    "WorkspaceFrontierScenario",
    "WorkspaceFrontierScenarioMatrix",
    "build_workspace_frontier_scenario_matrix",
]
