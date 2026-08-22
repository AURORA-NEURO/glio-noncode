"""Execution and check accounting for the C05-C08 projection frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable
from .workspace import (
    ResearchWorkspace,
    WorkspaceKind,
    WorkspaceRecord,
    WorkspaceRecordType,
    WorkspaceSection,
    WorkspaceState,
)
from .workspace_beta import (
    CausalChainExplorer,
    EvidenceTableAndFilters,
    EvidenceTableFilter,
    PosteriorDecompositionViewer,
    TopologyViewer,
)
from .workspace_beta_frontier_public_data import (
    BETA_FRONTIER_CONTEXT_KEY,
    BetaFrontierFixture,
    BetaFrontierOperation,
    BetaFrontierRecord,
    BetaFrontierRole,
    default_beta_frontier_fixture,
)


@dataclass(frozen=True, slots=True)
class BetaFrontierExecution:
    """One projection result with compact output for downstream packages."""

    record_id: str
    operation: BetaFrontierOperation
    role: BetaFrontierRole
    state: str
    accepted: bool
    issue_codes: tuple[str, ...]
    output: dict[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierEvaluationCheck:
    """One expected-versus-observed assertion."""

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
class BetaFrontierEvaluation:
    """Full fixture evaluation, including positive and control rows."""

    fixture_id: str
    executions: tuple[BetaFrontierExecution, ...]
    checks: tuple[BetaFrontierEvaluationCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_checks(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def execution_map(self) -> dict[str, BetaFrontierExecution]:
        return {item.record_id: item for item in self.executions}

    def by_operation(self, operation: BetaFrontierOperation) -> tuple[BetaFrontierExecution, ...]:
        return tuple(item for item in self.executions if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed_checks": self.passed_checks,
            "failed_check_ids": list(self.failed_check_ids),
        }


def _workspace(payload: dict[str, Any]) -> ResearchWorkspace:
    records = tuple(
        WorkspaceRecord(
            record_id=str(item["record_id"]),
            record_type=WorkspaceRecordType(str(item["record_type"])),
            label=str(item["label"]),
            context_key=str(item["context_key"]),
            state=WorkspaceState(str(item.get("state", "partial"))),
            source_ids=tuple(str(value) for value in item.get("source_ids", ())),
            chromosome=str(item["chromosome"]) if item.get("chromosome") is not None else None,
            start=int(item["start"]) if item.get("start") is not None else None,
            end=int(item["end"]) if item.get("end") is not None else None,
            tags=tuple(str(value) for value in item.get("tags", ())),
            fields=dict(item.get("fields", {})),
            searchable_text=str(item.get("searchable_text", "")),
            content_address=str(item.get("content_address", content_hash(item))),
        )
        for item in payload.get("records", ())
    )
    sections = tuple(
        WorkspaceSection(
            section_id=str(item["section_id"]),
            title=str(item["title"]),
            record_types=tuple(WorkspaceRecordType(str(value)) for value in item["record_types"]),
            order=int(item["order"]),
            accessible_label=str(item["accessible_label"]),
            description=str(item["description"]),
        )
        for item in payload.get("sections", ())
    )
    body = {
        "workspace_id": str(payload["workspace_id"]),
        "kind": WorkspaceKind(str(payload.get("kind", "case"))),
        "context_key": str(payload["context_key"]),
        "records": records,
        "sections": sections,
        "state": WorkspaceState(str(payload.get("state", "partial"))),
        "warnings": tuple(str(value) for value in payload.get("warnings", ())),
    }
    return ResearchWorkspace(**body, content_address=str(payload.get("content_address", content_hash(body))))


def _topology(record: BetaFrontierRecord) -> tuple[str, dict[str, Any], tuple[str, ...]]:
    payload = record.payload
    result = TopologyViewer().build(
        context_key=str(payload["context_key"]),
        loops=payload.get("loops", ()),
        contacts=payload.get("contacts", ()),
        contact_scores=payload.get("contact_scores", ()),
        activity_results=payload.get("activity_results", ()),
        focus_chromosome=payload.get("focus_chromosome"),
        focus_start=payload.get("focus_start"),
        focus_end=payload.get("focus_end"),
        max_nodes=int(payload.get("max_nodes", 500)),
        max_edges=int(payload.get("max_edges", 1000)),
    )
    state = result.state.value
    issues: list[str] = []
    if payload["context_key"] != BETA_FRONTIER_CONTEXT_KEY or state == "out_of_domain":
        issues.append("context_mismatch")
    if not result.edges and state != "out_of_domain":
        issues.append("no_topology_observations")
    output = result.to_dict() | {
        "node_count": len(result.nodes),
        "edge_count": len(result.edges),
        "observed_edge_count": result.observed_edge_count,
    }
    return state, output, tuple(sorted(set(issues)))


def _causal(record: BetaFrontierRecord) -> tuple[str, dict[str, Any], tuple[str, ...]]:
    payload = record.payload
    result = CausalChainExplorer().explore(
        payload.get("results", ()),
        context_key=str(payload["context_key"]),
    )
    state = result.state.value
    issues: list[str] = []
    if payload["context_key"] != BETA_FRONTIER_CONTEXT_KEY or state == "out_of_domain":
        issues.append("context_mismatch")
    if result.missing_mediator_kinds and state != "out_of_domain":
        issues.append("missing_mediator")
    if state == "contradictory":
        issues.append("contradictory_mediator")
    output = result.to_dict() | {
        "node_count": len(result.nodes),
        "edge_count": len(result.edges),
        "complete": result.complete,
    }
    return state, output, tuple(sorted(set(issues)))


def _posterior(record: BetaFrontierRecord) -> tuple[str, dict[str, Any], tuple[str, ...]]:
    payload = record.payload
    result = PosteriorDecompositionViewer().view(
        payload["posterior"],
        payload.get("components", ()),
        context_key=str(payload["context_key"]),
    )
    state = result.state.value
    issues: list[str] = []
    if any(str(item.get("context_key")) != payload["context_key"] for item in payload.get("components", ())):
        issues.append("foreign_component")
    if result.residual is not None and abs(result.residual) > 0.05:
        issues.append("unreconciled_components")
    if result.evidence_support is None:
        issues.append("missing_support")
    output = result.to_dict() | {
        "component_count": len(result.components),
        "is_reconciled": result.is_reconciled,
    }
    return state, output, tuple(sorted(set(issues)))


def _table_filter(payload: dict[str, Any]) -> EvidenceTableFilter:
    raw = payload.get("filter", {})
    return EvidenceTableFilter(
        text=str(raw.get("text", "")),
        context_key=str(raw["context_key"]) if raw.get("context_key") is not None else None,
        channels=tuple(str(value) for value in raw.get("channels", ())),
        tiers=tuple(str(value) for value in raw.get("tiers", ())),
        source_ids=tuple(str(value) for value in raw.get("source_ids", ())),
        min_confidence=float(raw["min_confidence"]) if raw.get("min_confidence") is not None else None,
        offset=int(raw.get("offset", 0)),
        limit=int(raw.get("limit", 50)),
    )


def _table(record: BetaFrontierRecord) -> tuple[str, dict[str, Any], tuple[str, ...]]:
    payload = record.payload
    workspace = _workspace(payload["workspace"])
    table = EvidenceTableAndFilters().build(workspace, _table_filter(payload))
    state = table.state.value
    issues: list[str] = []
    raw_filter = payload.get("filter", {})
    if raw_filter.get("context_key") != BETA_FRONTIER_CONTEXT_KEY:
        issues.append("context_mismatch")
    if table.total_matches == 0 and not issues:
        issues.append("no_matching_rows")
    if int(raw_filter.get("offset", 0)) > 0 and table.total_matches > 0:
        issues.append("pagination_applied")
    output = table.to_dict() | {
        "row_count": len(table.rows),
        "returned_record_ids": [item.record_id for item in table.rows],
    }
    return state, output, tuple(sorted(set(issues)))


def execute_beta_frontier_record(
    record: BetaFrontierRecord,
    *,
    fixture_context: str = BETA_FRONTIER_CONTEXT_KEY,
) -> BetaFrontierExecution:
    """Execute one fixture row and retain validation failures as data."""

    try:
        if record.operation is BetaFrontierOperation.TOPOLOGY_VIEWPORT:
            state, output, issues = _topology(record)
        elif record.operation is BetaFrontierOperation.CAUSAL_CHAIN:
            state, output, issues = _causal(record)
        elif record.operation is BetaFrontierOperation.POSTERIOR_DECOMPOSITION:
            state, output, issues = _posterior(record)
        elif record.operation is BetaFrontierOperation.EVIDENCE_TABLE:
            state, output, issues = _table(record)
        else:
            raise ValidationError(f"unsupported beta frontier operation: {record.operation}")
        if record.context_key != fixture_context:
            issues = tuple(sorted(set((*issues, "context_mismatch"))))
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        state = "invalid"
        issues = ("invalid_projection_input",)
        output = {"state": state, "error": str(exc), "context_key": record.context_key}
    expected = record.expected_state == state and tuple(sorted(record.expected_issue_codes)) == tuple(sorted(issues))
    accepted = expected and record.role is BetaFrontierRole.POSITIVE
    body = {
        "record_id": record.record_id,
        "operation": record.operation,
        "role": record.role,
        "state": state,
        "accepted": accepted,
        "issue_codes": tuple(sorted(issues)),
        "output": output,
    }
    return BetaFrontierExecution(**body, content_address=content_hash(body))


def _check(
    check_id: str,
    record_id: str | None,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> BetaFrontierEvaluationCheck:
    body = {
        "check_id": check_id,
        "record_id": record_id,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return BetaFrontierEvaluationCheck(**body, content_address=content_hash(body))


def evaluate_beta_frontier_fixture(
    fixture: BetaFrontierFixture | None = None,
) -> BetaFrontierEvaluation:
    """Execute all rows and assert shape, state, role, and address invariants."""

    fixture = fixture or default_beta_frontier_fixture()
    executions = tuple(
        execute_beta_frontier_record(item, fixture_context=fixture.context_key)
        for item in fixture.records
    )
    checks: list[BetaFrontierEvaluationCheck] = []
    for record, execution in zip(fixture.records, executions, strict=True):
        checks.extend(
            (
                _check(f"{record.record_id}:state", record.record_id, execution.state == record.expected_state, execution.state, record.expected_state, "projection state matches fixture"),
                _check(f"{record.record_id}:issues", record.record_id, execution.issue_codes == tuple(sorted(record.expected_issue_codes)), execution.issue_codes, tuple(sorted(record.expected_issue_codes)), "issue vocabulary matches fixture"),
                _check(f"{record.record_id}:role", record.record_id, execution.accepted is (record.role is BetaFrontierRole.POSITIVE), execution.accepted, record.role is BetaFrontierRole.POSITIVE, "positive and control roles remain distinct"),
                _check(f"{record.record_id}:operation", record.record_id, execution.operation is record.operation, execution.operation.value, record.operation.value, "surface operation is retained"),
                _check(f"{record.record_id}:address", record.record_id, execution.content_address.startswith("sha256:"), execution.content_address, "sha256", "execution is content addressed"),
                _check(f"{record.record_id}:output", record.record_id, bool(execution.output), bool(execution.output), True, "projection output is retained"),
            )
        )
    checks.extend(
        (
            _check("global:record-count", None, len(executions) == len(fixture.records), len(executions), len(fixture.records), "every fixture row executed"),
            _check("global:source-count", None, len(fixture.sources) == 5, len(fixture.sources), 5, "five public receipts"),
            _check("global:operation-count", None, set(item.operation for item in executions) == set(BetaFrontierOperation), tuple(sorted({item.operation.value for item in executions})), tuple(item.value for item in BetaFrontierOperation), "all surfaces executed"),
            _check("global:positive-count", None, len(fixture.positive_records) == 4, len(fixture.positive_records), 4, "four positive paths"),
            _check("global:control-count", None, len(fixture.control_records) == 12, len(fixture.control_records), 12, "twelve control paths"),
            _check("global:boundary", None, fixture.evidence_boundary == "public_aggregate_non_patient", fixture.evidence_boundary, "public_aggregate_non_patient", "public aggregate boundary is exact"),
            _check("global:addresses", None, all(item.content_address.startswith("sha256:") for item in executions), True, True, "all results are addressed"),
        )
    )
    body = {
        "fixture_id": fixture.fixture_id,
        "executions": executions,
        "checks": tuple(checks),
        "accepted": all(item.passed for item in checks),
    }
    return BetaFrontierEvaluation(**body, content_address=content_hash(body))


__all__ = [
    "BetaFrontierEvaluation",
    "BetaFrontierEvaluationCheck",
    "BetaFrontierExecution",
    "evaluate_beta_frontier_fixture",
    "execute_beta_frontier_record",
]
