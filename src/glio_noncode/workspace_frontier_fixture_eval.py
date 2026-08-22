"""Deterministic execution and check accounting for Domain 15 workspaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_discovery import (
    CohortDiscoveryEvidenceBuilder,
    CohortQuery,
    CohortQueryBuilder,
    CohortVariantRecord,
)
from .errors import ValidationError
from .models import CandidateElement, CaseManifest, ReferenceContext, VariantIdentity
from .regulatory_tracks import RegulatoryTrackParser
from .serialization import content_hash, jsonable
from .workspace import (
    CaseWorkspaceBuilder,
    CohortWorkspaceBuilder,
    RegulatoryTrackBrowser,
    VariantExplorer,
    WorkspaceQuery,
)
from .workspace_frontier_contracts import default_workspace_frontier_contracts
from .workspace_frontier_public_data import (
    WorkspaceFrontierFixture,
    WorkspaceFrontierOperation,
    WorkspaceFrontierRecord,
    WorkspaceFrontierRole,
    default_workspace_frontier_fixture,
)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierExecution:
    record_id: str
    operation: WorkspaceFrontierOperation
    role: WorkspaceFrontierRole
    state: str
    accepted: bool
    issue_codes: tuple[str, ...]
    output: dict[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierEvaluationCheck:
    check_id: str
    record_id: str | None
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierEvaluation:
    fixture_id: str
    executions: tuple[WorkspaceFrontierExecution, ...]
    checks: tuple[WorkspaceFrontierEvaluationCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_checks(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def execution_map(self) -> dict[str, WorkspaceFrontierExecution]:
        return {item.record_id: item for item in self.executions}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed_checks": self.passed_checks,
            "failed_check_ids": list(self.failed_check_ids),
        }


def _context(key: str) -> ReferenceContext:
    parts = key.split("|")
    return ReferenceContext(
        genome_build=parts[0],
        disease_class=parts[1],
        age_group=parts[2],
        cell_state=parts[3],
        territory=parts[4],
        treatment_phase=parts[5],
    )


def _case(payload: dict[str, Any]) -> CaseManifest:
    context = _context(str(payload["context_key"]))
    variants = tuple(VariantIdentity.from_dict(item) for item in payload.get("variants", ()))
    elements = tuple(CandidateElement.from_dict(item, context) for item in payload.get("candidate_elements", ()))
    return CaseManifest(
        case_id=str(payload["case_id"]),
        subject_id=str(payload["subject_id"]),
        context=context,
        variants=variants,
        candidate_elements=elements,
        input_versions=dict(payload.get("input_versions", {})),
    )


def _case_workspace(payload: dict[str, Any], fixture_context: str) -> tuple[str, dict[str, Any], tuple[str, ...]]:
    manifest = _case(payload)
    if manifest.context.key != fixture_context:
        return "out_of_domain", {"workspace_id": f"case:{manifest.case_id}", "context_key": manifest.context.key, "state": "out_of_domain", "record_count": 0, "warnings": ["requested case context is outside the fixture context"]}, ("context_mismatch",)
    workspace = CaseWorkspaceBuilder().build(manifest)
    page = workspace.search(WorkspaceQuery(limit=100))
    issues = ("missing_dossier",) if not payload.get("include_dossier", False) else ()
    output = {
        "workspace_id": workspace.workspace_id,
        "context_key": workspace.context_key,
        "state": workspace.state.value,
        "record_count": len(workspace.records),
        "section_ids": [item.section_id for item in workspace.sections],
        "record_ids": [item.record_id for item in workspace.records],
        "page_total": page.total_matches,
        "facets": page.facets,
        "warnings": list(workspace.warnings),
        "accessibility": payload.get("accessibility", {}),
        "input_address": manifest.content_address,
    }
    return workspace.state.value, output, issues


def _cohort_record(raw: dict[str, Any]) -> CohortVariantRecord:
    return CohortVariantRecord(
        record_id=str(raw["record_id"]),
        variant=VariantIdentity.from_dict(raw["variant"]),
        context_key=str(raw["context_key"]),
        source_id=str(raw["source_id"]),
        sample_id=str(raw["sample_id"]),
        callable=bool(raw.get("callable", True)),
        sequence_context=raw.get("sequence_context"),
        chromatin_features=dict(raw.get("chromatin_features", {})),
        annotations=dict(raw.get("annotations", {})),
    )


def _cohort_workspace(payload: dict[str, Any], fixture_context: str) -> tuple[str, dict[str, Any], tuple[str, ...]]:
    context_key = str(payload["context_key"])
    values = tuple(_cohort_record(item) for item in payload.get("records", ()))
    query = CohortQuery(
        query_id=str(payload["query_id"]),
        context_key=context_key,
        require_callable=bool(payload.get("require_callable", True)),
    )
    result = CohortQueryBuilder().build(query, values)
    evidence = CohortDiscoveryEvidenceBuilder().build(str(payload["evidence_id"]), result)
    workspace = CohortWorkspaceBuilder().build(evidence)
    if context_key != fixture_context:
        state = "out_of_domain"
        issues = ("context_mismatch",)
    else:
        state = workspace.state.value
        issues = () if state == "supported" else ("no_matching_records",)
    page = workspace.search(WorkspaceQuery(limit=100))
    output = {
        "workspace_id": workspace.workspace_id,
        "context_key": context_key,
        "state": state,
        "record_count": len(workspace.records),
        "query_record_count": len(result.records),
        "excluded_count": result.excluded_count,
        "excluded_reasons": result.excluded_reasons,
        "section_ids": [item.section_id for item in workspace.sections],
        "page_total": page.total_matches,
        "facets": page.facets,
        "warnings": list(workspace.warnings),
        "accessibility": payload.get("accessibility", {}),
        "input_address": result.content_address,
    }
    return state, output, issues


def _variant_explorer(payload: dict[str, Any], fixture_context: str) -> tuple[str, dict[str, Any], tuple[str, ...]]:
    case_payload = dict(payload["case"])
    manifest = _case(case_payload)
    workspace = CaseWorkspaceBuilder().build(manifest)
    requested_context = payload.get("context_key")
    detail = VariantExplorer().inspect(workspace, str(payload["variant_id"]), context_key=requested_context)
    state = detail.state.value
    if requested_context is not None and requested_context != fixture_context:
        state = "out_of_domain"
        issues = ("context_mismatch",)
    elif state == "abstained":
        issues = ("variant_absent",)
    else:
        issues = ()
    output = {
        "workspace_id": detail.workspace_id,
        "variant_id": detail.variant_id,
        "state": state,
        "variant_record_id": detail.variant.record_id if detail.variant else None,
        "related_record_ids": list(detail.related_record_ids),
        "related_by_type": detail.related_by_type,
        "warnings": list(detail.warnings),
        "input_address": workspace.content_address,
    }
    return state, output, issues


def _track_browser(payload: dict[str, Any], fixture_context: str) -> tuple[str, dict[str, Any], tuple[str, ...]]:
    batch = RegulatoryTrackParser().parse_text(
        str(payload["text"]),
        source_id=str(payload["source_id"]),
        genome_build=str(payload["genome_build"]),
    )
    workspace = RegulatoryTrackBrowser().build(batch, context_key=str(payload["context_key"]))
    state = workspace.state.value
    issues = ("track_parse_issue",) if batch.issues else ()
    page = workspace.search(WorkspaceQuery(limit=100))
    if str(payload["context_key"]) != fixture_context:
        state = "out_of_domain"
        issues = ("context_mismatch",)
    output = {
        "workspace_id": workspace.workspace_id,
        "context_key": workspace.context_key,
        "state": state,
        "feature_count": len(batch.features),
        "issue_count": len(batch.issues),
        "record_ids": [item.record_id for item in workspace.records],
        "coordinate_labels": [item.coordinate_label for item in workspace.records],
        "page_total": page.total_matches,
        "facets": page.facets,
        "warnings": list(workspace.warnings),
        "accessibility": payload.get("accessibility", {}),
        "input_address": batch.content_address,
    }
    return state, output, issues


def execute_workspace_frontier_record(record: WorkspaceFrontierRecord, *, fixture_context: str = "GRCh38|glioma|adult|stem_like|core|untreated") -> WorkspaceFrontierExecution:
    try:
        if record.operation is WorkspaceFrontierOperation.CASE_WORKSPACE:
            state, output, issues = _case_workspace(record.payload, fixture_context)
        elif record.operation is WorkspaceFrontierOperation.COHORT_WORKSPACE:
            state, output, issues = _cohort_workspace(record.payload, fixture_context)
        elif record.operation is WorkspaceFrontierOperation.VARIANT_EXPLORER:
            state, output, issues = _variant_explorer(record.payload, fixture_context)
        elif record.operation is WorkspaceFrontierOperation.REGULATORY_TRACK_BROWSER:
            state, output, issues = _track_browser(record.payload, fixture_context)
        else:
            raise ValidationError(f"unsupported workspace frontier operation: {record.operation}")
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        state = "invalid"
        if record.operation is WorkspaceFrontierOperation.REGULATORY_TRACK_BROWSER:
            issues = ("invalid_track_input",)
        elif "duplicate variant_id" in str(exc):
            issues = ("duplicate_variant_id",)
        else:
            issues = ("invalid_workspace_input",)
        output = {"state": state, "error": str(exc), "context_key": record.context_key}
    expected = record.expected_state == state and tuple(sorted(record.expected_issue_codes)) == tuple(sorted(issues))
    accepted = record.role is WorkspaceFrontierRole.POSITIVE and expected
    body = {"record_id": record.record_id, "operation": record.operation, "role": record.role, "state": state, "accepted": accepted, "issue_codes": tuple(sorted(issues)), "output": output}
    return WorkspaceFrontierExecution(**body, content_address=content_hash(body))


def _check(check_id: str, record_id: str | None, passed: bool, observed: Any, required: Any, detail: str) -> WorkspaceFrontierEvaluationCheck:
    body = {"check_id": check_id, "record_id": record_id, "passed": passed, "observed": observed, "required": required, "detail": detail}
    return WorkspaceFrontierEvaluationCheck(**body, content_address=content_hash(body))


def evaluate_workspace_frontier_fixture(fixture: WorkspaceFrontierFixture | None = None) -> WorkspaceFrontierEvaluation:
    fixture = fixture or default_workspace_frontier_fixture()
    executions = tuple(execute_workspace_frontier_record(item, fixture_context=fixture.context_key) for item in fixture.records)
    checks: list[WorkspaceFrontierEvaluationCheck] = []
    for record, execution in zip(fixture.records, executions, strict=True):
        checks.extend(
            (
                _check(f"{record.record_id}:state", record.record_id, execution.state == record.expected_state, execution.state, record.expected_state, "workspace state matches fixture"),
                _check(f"{record.record_id}:issues", record.record_id, execution.issue_codes == tuple(sorted(record.expected_issue_codes)), execution.issue_codes, tuple(sorted(record.expected_issue_codes)), "issue vocabulary matches fixture"),
                _check(f"{record.record_id}:role", record.record_id, execution.accepted is (record.role is WorkspaceFrontierRole.POSITIVE), execution.accepted, record.role is WorkspaceFrontierRole.POSITIVE, "positive and control roles remain distinct"),
                _check(f"{record.record_id}:operation", record.record_id, execution.operation is record.operation, execution.operation.value, record.operation.value, "operation is retained"),
                _check(f"{record.record_id}:address", record.record_id, execution.content_address.startswith("sha256:"), execution.content_address, "sha256", "execution is addressed"),
                _check(f"{record.record_id}:context", record.record_id, record.context_key == fixture.context_key, record.context_key, fixture.context_key, "record context is exact"),
                _check(f"{record.record_id}:output", record.record_id, bool(execution.output), bool(execution.output), True, "workspace output is retained"),
            )
        )
    contracts = default_workspace_frontier_contracts()
    checks.extend(
        (
            _check("global:record-count", None, len(executions) == len(fixture.records), len(executions), len(fixture.records), "every record executed"),
            _check("global:source-count", None, len(fixture.sources) == 5, len(fixture.sources), 5, "five public receipts"),
            _check("global:operation-count", None, set(item.operation for item in executions) == set(WorkspaceFrontierOperation), tuple(item.operation.value for item in executions), tuple(item.value for item in WorkspaceFrontierOperation), "all surfaces executed"),
            _check("global:positive-count", None, len(fixture.positive_records) == 4, len(fixture.positive_records), 4, "one positive per surface"),
            _check("global:control-count", None, len(fixture.control_records) == 12, len(fixture.control_records), 12, "three controls per surface"),
            _check("global:issue-vocabulary", None, all(set(item.issue_codes) <= set(contracts.issue_codes()) for item in executions), True, True, "issues are declared"),
            _check("global:addresses", None, all(item.content_address.startswith("sha256:") for item in executions), True, True, "all executions are addressed"),
            _check("global:boundary", None, fixture.evidence_boundary == "public_aggregate_non_patient", fixture.evidence_boundary, "public_aggregate_non_patient", "public boundary is exact"),
        )
    )
    body = {"fixture_id": fixture.fixture_id, "executions": executions, "checks": tuple(checks), "accepted": all(item.passed for item in checks)}
    return WorkspaceFrontierEvaluation(**body, content_address=content_hash(body))


__all__ = [
    "WorkspaceFrontierEvaluation",
    "WorkspaceFrontierEvaluationCheck",
    "WorkspaceFrontierExecution",
    "evaluate_workspace_frontier_fixture",
    "execute_workspace_frontier_record",
]
