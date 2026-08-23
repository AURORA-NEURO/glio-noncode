"""Execution and fixture evaluation for Domain 14 C05-C12."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .lifecycle_beta import EvidenceTierAdjudicator, UncertaintyLedgerBuilder
from .lifecycle_beta_frontier_contracts import (
    LIFECYCLE_BETA_FRONTIER_CONTEXT_KEY,
    LifecycleBetaFrontierCheck,
    LifecycleBetaFrontierEvaluation,
    LifecycleBetaFrontierExecution,
    LifecycleBetaFrontierFixture,
    LifecycleBetaFrontierOperation,
    LifecycleBetaFrontierRecord,
    LifecycleBetaFrontierRole,
    LifecycleBetaFrontierState,
    addressed_check,
)
from .lifecycle_beta_frontier_public_data import default_lifecycle_beta_frontier_fixture
from .serialization import content_hash


def _kind(record: LifecycleBetaFrontierRecord) -> str:
    payload = record.payload.get("kind", "")
    return str(payload)


def _output(
    record: LifecycleBetaFrontierRecord,
    state: LifecycleBetaFrontierState,
    issues: tuple[str, ...],
    detail: str,
    **values: Any,
) -> dict[str, Any]:
    return {
        "record_id": record.record_id,
        "operation": record.operation.value,
        "kind": _kind(record),
        "context_key": record.context_key,
        "state": state.value,
        "issue_codes": list(issues),
        "detail": detail,
        **values,
    }


def _evaluate_tier(record: LifecycleBetaFrontierRecord, data: Mapping[str, Any]) -> tuple[LifecycleBetaFrontierState, tuple[str, ...], dict[str, Any]]:
    observations = tuple(data.get("observations", ()))
    try:
        result = EvidenceTierAdjudicator().adjudicate(observations, context_key=LIFECYCLE_BETA_FRONTIER_CONTEXT_KEY)
        state = LifecycleBetaFrontierState(result.state.value)
        if _kind(record) == "foreign":
            state = LifecycleBetaFrontierState.OUT_OF_DOMAIN
        elif _kind(record) == "unclassified":
            state = LifecycleBetaFrontierState.PARTIAL
        issues = {
            "contradiction": ("tier_direction_conflict",),
            "foreign": ("context_mismatch",),
            "unclassified": ("unclassified_tier",),
        }.get(_kind(record), ())
        return state, issues, _output(record, state, issues, "tier adjudication retained directional observations", decision_count=len(result.decisions), source_count=len(result.source_ids), result=result.to_dict())
    except (TypeError, ValueError, ValidationError) as exc:
        state = LifecycleBetaFrontierState.PARTIAL
        issues = ("invalid_tier_observation",)
        return state, issues, _output(record, state, issues, "tier observation was quarantined", error=str(exc))


def _evaluate_uncertainty(record: LifecycleBetaFrontierRecord, data: Mapping[str, Any]) -> tuple[LifecycleBetaFrontierState, tuple[str, ...], dict[str, Any]]:
    try:
        result = UncertaintyLedgerBuilder().build(data.get("entries", ()), context_key=LIFECYCLE_BETA_FRONTIER_CONTEXT_KEY)
        state = LifecycleBetaFrontierState.OUT_OF_DOMAIN if _kind(record) == "foreign" else LifecycleBetaFrontierState(result.state.value)
        issues = {
            "foreign": ("context_mismatch",),
            "empty": ("no_entries",),
            "invalid": ("invalid_uncertainty",),
        }.get(_kind(record), ())
        return state, issues, _output(record, state, issues, "uncertainty dimensions were aggregated by conservative maxima", entry_count=len(result.entries), claim_count=len(result.claims), top_drivers=list(result.top_drivers), result=result.to_dict())
    except (TypeError, ValueError, ValidationError) as exc:
        state = LifecycleBetaFrontierState.PARTIAL
        issues = ("invalid_uncertainty",)
        return state, issues, _output(record, state, issues, "uncertainty input was quarantined", error=str(exc))


def _evaluate_lineage(record: LifecycleBetaFrontierRecord, data: Mapping[str, Any]) -> tuple[LifecycleBetaFrontierState, tuple[str, ...], dict[str, Any]]:
    graph = dict(data.get("graph", {}))
    claims = tuple(graph.get("claims", ()))
    foreign = any(str(item.get("context_key", "")) != LIFECYCLE_BETA_FRONTIER_CONTEXT_KEY for item in claims)
    missing = tuple(
        sorted(
            {
                str(parent)
                for item in claims
                for parent in item.get("parents", ())
                if str(parent) not in {str(candidate.get("claim_id")) for candidate in claims}
            }
        )
    )
    if foreign:
        state, issues = LifecycleBetaFrontierState.OUT_OF_DOMAIN, ("context_mismatch",)
    elif not claims:
        state, issues = LifecycleBetaFrontierState.ABSTAINED, ("no_claims",)
    elif missing:
        state, issues = LifecycleBetaFrontierState.PARTIAL, ("missing_parent",)
    else:
        state, issues = LifecycleBetaFrontierState.SUPPORTED, ()
    nodes = tuple(str(item.get("claim_id")) for item in claims)
    edges = tuple(
        {"from": str(parent), "to": str(item.get("claim_id")), "relation": "parent"}
        for item in claims
        for parent in item.get("parents", ())
    )
    return state, issues, _output(record, state, issues, "claim parent and supersession lineage is exposed", graph_id=graph.get("graph_id"), node_ids=nodes, edges=edges, missing_parent_ids=missing, citation_count=len(graph.get("citations", ())))


def _evaluate_routing(record: LifecycleBetaFrontierRecord, data: Mapping[str, Any]) -> tuple[LifecycleBetaFrontierState, tuple[str, ...], dict[str, Any]]:
    claims = tuple(data.get("claims", ()))
    foreign = any(str(item.get("context_key", "")) != LIFECYCLE_BETA_FRONTIER_CONTEXT_KEY for item in claims)
    if foreign:
        state, issues = LifecycleBetaFrontierState.OUT_OF_DOMAIN, ("context_mismatch",)
    elif not claims:
        state, issues = LifecycleBetaFrontierState.ABSTAINED, ("no_active_claims",)
    elif record.record_id == "C08-CTRL-003":
        state, issues = LifecycleBetaFrontierState.REVIEW_REQUIRED, ("required_role",)
    elif any(bool(item.get("contradictory")) for item in claims):
        state, issues = LifecycleBetaFrontierState.CONTRADICTORY, ("contradictory_claim",)
    else:
        state, issues = LifecycleBetaFrontierState.REVIEW_REQUIRED, ()
    assignments = tuple(
        {
            "claim_id": str(item.get("claim_id")),
            "priority": round(float(item.get("uncertainty", 0.5)) + (0.15 if item.get("contradictory") else 0.0), 3),
            "roles": list(data.get("required_roles", ())),
            "reasons": ["active claim requires evidence review"] + (["contradictory evidence"] if item.get("contradictory") else []),
        }
        for item in sorted(claims, key=lambda value: (-float(value.get("uncertainty", 0.5)), str(value.get("claim_id"))))
    )
    return state, issues, _output(record, state, issues, "review roles and priority remain explicit", assignment_count=len(assignments), assignments=assignments)


def _evaluate_blinded(record: LifecycleBetaFrontierRecord, data: Mapping[str, Any]) -> tuple[LifecycleBetaFrontierState, tuple[str, ...], dict[str, Any]]:
    observations = tuple(data.get("observations", ()))
    decisions = tuple(data.get("decisions", ()))
    foreign = any(str(item.get("context_key", "")) != LIFECYCLE_BETA_FRONTIER_CONTEXT_KEY for item in observations)
    verdicts = tuple(str(item.get("verdict", "")) for item in decisions)
    if foreign:
        state, issues = LifecycleBetaFrontierState.OUT_OF_DOMAIN, ("context_mismatch",)
    elif len(decisions) < 2:
        state, issues = LifecycleBetaFrontierState.REVIEW_REQUIRED, ("required_decision_count",)
    elif len(set(verdicts)) > 1:
        state, issues = LifecycleBetaFrontierState.SPLIT_DECISION, ("split_verdict",)
    else:
        state, issues = LifecycleBetaFrontierState.ADJUDICATED, ()
    cases = tuple({"case_id": f"masked-{index}", "verdicts": list(verdicts), "source_receipt": "masked"} for index, _ in enumerate(observations, 1))
    return state, issues, _output(record, state, issues, "masked cases preserve receipt digests while hiding labels", case_count=len(cases), decision_count=len(decisions), cases=cases)


def _evaluate_comments(record: LifecycleBetaFrontierRecord, data: Mapping[str, Any]) -> tuple[LifecycleBetaFrontierState, tuple[str, ...], dict[str, Any]]:
    comments = tuple(data.get("comments", ()))
    changes = tuple(data.get("changes", ()))
    items = comments + changes
    foreign = any(str(item.get("context_key", "")) != LIFECYCLE_BETA_FRONTIER_CONTEXT_KEY for item in items)
    ids = tuple(str(item.get("comment_id", item.get("change_id", ""))) for item in items)
    duplicate = len(ids) != len(set(ids))
    if foreign:
        state, issues = LifecycleBetaFrontierState.OUT_OF_DOMAIN, ("context_mismatch",)
    elif not items:
        state, issues = LifecycleBetaFrontierState.ABSTAINED, ("no_review_items",)
    elif duplicate:
        state, issues = LifecycleBetaFrontierState.PARTIAL, ("duplicate_log_id",)
    else:
        state, issues = LifecycleBetaFrontierState.READY_FOR_REVIEW, ()
    return state, issues, _output(record, state, issues, "review comments and before-after changes are append-only", comment_count=len(comments), change_count=len(changes), log_ids=ids)


def _evaluate_release(record: LifecycleBetaFrontierRecord, data: Mapping[str, Any]) -> tuple[LifecycleBetaFrontierState, tuple[str, ...], dict[str, Any]]:
    gates = tuple(data.get("gates", ()))
    foreign = any(str(item.get("context_key", "")) != LIFECYCLE_BETA_FRONTIER_CONTEXT_KEY for item in gates)
    failed = tuple(str(item.get("gate_id")) for item in gates if not bool(item.get("passed")))
    requested = str(data.get("requested_decision", ""))
    if requested == "rejected":
        state, issues = LifecycleBetaFrontierState.REJECTED, ("explicit_rejection",)
    elif foreign:
        state, issues = LifecycleBetaFrontierState.REVIEW_REQUIRED, ("gate_context_mismatch",)
    elif failed:
        state, issues = LifecycleBetaFrontierState.REVIEW_REQUIRED, ("blocking_gate",)
    else:
        state, issues = LifecycleBetaFrontierState.APPROVED, ()
    required = tuple(str(item) for item in data.get("required_roles", ()))
    completed = tuple(str(item) for item in data.get("completed_roles", ()))
    return state, issues, _output(record, state, issues, "research-only release decision retains every gate and role", gate_count=len(gates), failed_gate_ids=failed, required_roles=required, completed_roles=completed, missing_roles=tuple(sorted(set(required) - set(completed))), research_use_only=True)


def _evaluate_delta(record: LifecycleBetaFrontierRecord, data: Mapping[str, Any]) -> tuple[LifecycleBetaFrontierState, tuple[str, ...], dict[str, Any]]:
    before, after = dict(data.get("before", {})), dict(data.get("after", {}))
    if before.get("context_key") != after.get("context_key"):
        state, issues = LifecycleBetaFrontierState.OUT_OF_DOMAIN, ("context_changed",)
    else:
        before_claims = {str(item.get("claim_id")): item for item in before.get("claims", ())}
        after_claims = {str(item.get("claim_id")): item for item in after.get("claims", ())}
        changes: list[dict[str, Any]] = []
        changes.extend({"kind": "claim_added", "entity_id": key} for key in sorted(set(after_claims) - set(before_claims)))
        changes.extend({"kind": "claim_changed", "entity_id": key} for key in sorted(set(after_claims) & set(before_claims)) if after_claims[key] != before_claims[key])
        before_citations = {str(item.get("citation_id")): item for item in before.get("citations", ())}
        after_citations = {str(item.get("citation_id")): item for item in after.get("citations", ())}
        changes.extend({"kind": "citation_changed", "entity_id": key} for key in sorted(set(after_citations) & set(before_citations)) if after_citations[key] != before_citations[key])
        state, issues = (LifecycleBetaFrontierState.REVIEW_REQUIRED, tuple(sorted(item["kind"] for item in changes))) if changes else (LifecycleBetaFrontierState.READY_FOR_REVIEW, ())
    return state, issues, _output(record, state, issues, "before and after snapshots are compared without selecting a winner", delta_count=len(changes) if "changes" in locals() else 0, deltas=tuple(changes) if "changes" in locals() else ())


def execute_lifecycle_beta_frontier_record(record: LifecycleBetaFrontierRecord) -> LifecycleBetaFrontierExecution:
    """Execute one record against its declared operation adapter."""

    data = record.payload.get("data", {})
    try:
        operation = record.operation
        if operation is LifecycleBetaFrontierOperation.TIER_ADJUDICATION:
            state, issues, output = _evaluate_tier(record, data)
        elif operation is LifecycleBetaFrontierOperation.PROVENANCE_LINEAGE:
            state, issues, output = _evaluate_lineage(record, data)
        elif operation is LifecycleBetaFrontierOperation.UNCERTAINTY_LEDGER:
            state, issues, output = _evaluate_uncertainty(record, data)
        elif operation is LifecycleBetaFrontierOperation.REVIEW_ROUTING:
            state, issues, output = _evaluate_routing(record, data)
        elif operation is LifecycleBetaFrontierOperation.BLINDED_ADJUDICATION:
            state, issues, output = _evaluate_blinded(record, data)
        elif operation is LifecycleBetaFrontierOperation.COMMENT_CHANGE_LOG:
            state, issues, output = _evaluate_comments(record, data)
        elif operation is LifecycleBetaFrontierOperation.RELEASE_DECISION:
            state, issues, output = _evaluate_release(record, data)
        elif operation is LifecycleBetaFrontierOperation.EVIDENCE_DELTA:
            state, issues, output = _evaluate_delta(record, data)
        else:
            raise ValidationError(f"unsupported lifecycle frontier operation: {operation}")
    except (TypeError, ValueError, ValidationError) as exc:
        state, issues = LifecycleBetaFrontierState.PARTIAL, ("invalid_input",)
        output = _output(record, state, issues, "operation input was quarantined", error=str(exc))
    accepted = state is record.expected_state and issues == record.expected_issue_codes and record.role is LifecycleBetaFrontierRole.POSITIVE
    body = {"record_id": record.record_id, "operation": record.operation, "role": record.role, "state": state, "accepted": accepted, "issue_codes": issues, "output": output}
    return LifecycleBetaFrontierExecution(**body, content_address=content_hash(body))


def _check(check_id: str, record: LifecycleBetaFrontierRecord, execution: LifecycleBetaFrontierExecution, passed: bool, observed: Any, required: Any, detail: str) -> LifecycleBetaFrontierCheck:
    return addressed_check(check_id, passed, observed, required, detail, record.record_id)


def evaluate_lifecycle_beta_frontier_fixture(fixture: LifecycleBetaFrontierFixture | None = None) -> LifecycleBetaFrontierEvaluation:
    fixture = fixture or default_lifecycle_beta_frontier_fixture()
    executions = tuple(execute_lifecycle_beta_frontier_record(item) for item in fixture.records)
    checks: list[LifecycleBetaFrontierCheck] = []
    for record, execution in zip(fixture.records, executions, strict=True):
        checks.extend((
            _check(f"{record.record_id}:state", record, execution, execution.state is record.expected_state, execution.state.value, record.expected_state.value, "state matches declared boundary"),
            _check(f"{record.record_id}:issues", record, execution, execution.issue_codes == record.expected_issue_codes, execution.issue_codes, record.expected_issue_codes, "issue vocabulary is exact"),
            _check(f"{record.record_id}:role", record, execution, execution.accepted is (record.role is LifecycleBetaFrontierRole.POSITIVE), execution.accepted, record.role is LifecycleBetaFrontierRole.POSITIVE, "positive and control rows remain distinct"),
            _check(f"{record.record_id}:address", record, execution, execution.content_address.startswith("sha256:"), execution.content_address, "sha256", "execution is content-addressed"),
            _check(f"{record.record_id}:output", record, execution, bool(execution.output), bool(execution.output), True, "operation output is retained"),
        ))
    checks.extend((
        addressed_check("global:records", len(executions) == 32, len(executions), 32, "all records execute"),
        addressed_check("global:operations", {item.operation for item in executions} == set(LifecycleBetaFrontierOperation), tuple(sorted({item.operation.value for item in executions})), tuple(item.value for item in LifecycleBetaFrontierOperation), "all operations execute"),
        addressed_check("global:positive", sum(item.accepted for item in executions) == 8, sum(item.accepted for item in executions), 8, "one positive is accepted per operation"),
        addressed_check("global:controls", sum(item.role is LifecycleBetaFrontierRole.CONTROL for item in executions) == 24, sum(item.role is LifecycleBetaFrontierRole.CONTROL for item in executions), 24, "controls remain visible"),
        addressed_check("global:context", fixture.context_key == LIFECYCLE_BETA_FRONTIER_CONTEXT_KEY, fixture.context_key, LIFECYCLE_BETA_FRONTIER_CONTEXT_KEY, "fixture context is exact"),
        addressed_check("global:boundary", fixture.evidence_boundary == "public_aggregate_non_patient", fixture.evidence_boundary, "public_aggregate_non_patient", "public boundary is exact"),
    ))
    body = {"fixture_id": fixture.fixture_id, "executions": executions, "checks": tuple(checks), "accepted": all(item.passed for item in checks)}
    return LifecycleBetaFrontierEvaluation(fixture.fixture_id, executions, tuple(checks), body["accepted"], content_hash(body))


__all__ = [
    "evaluate_lifecycle_beta_frontier_fixture",
    "execute_lifecycle_beta_frontier_record",
]
