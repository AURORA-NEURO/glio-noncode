"""Deterministic public aggregate fixture for Domain 16 C05-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import (
    CONTROL_FRONTIER_BOUNDARY,
    CONTROL_FRONTIER_CONTEXT_KEY,
    CONTROL_FRONTIER_VERSION,
    ControlFrontierFixture,
    ControlFrontierOperation,
    ControlFrontierRecord,
    ControlFrontierRole,
    ControlFrontierSourceReceipt,
    ControlFrontierState,
)
from .errors import ValidationError
from .serialization import content_hash, jsonable


CONTROL_FRONTIER_SOURCE_COUNT = 9
CONTROL_FRONTIER_POSITIVE_COUNT = 8
CONTROL_FRONTIER_CONTROL_COUNT = 24


def _source(source_id: str, title: str) -> ControlFrontierSourceReceipt:
    body = {
        "source_id": source_id,
        "title": title,
        "uri": f"https://example.org/glio-noncode/control-frontier/{source_id}",
        "access_note": "public aggregate operational receipt; no row-level private data",
    }
    return ControlFrontierSourceReceipt(**body, content_address=content_hash(body))


def _policy_payload(kind: str) -> dict[str, Any]:
    context = CONTROL_FRONTIER_CONTEXT_KEY
    payload = {
        "request_id": f"policy-{kind}",
        "role_id": "role-policy-review",
        "tool_id": "control.policy.inspect",
        "claim_ceiling": "hypothesis",
        "mission_ceiling": "hypothesis",
        "allowed_source_ids": ["src-policy"],
        "request_source_ids": ["src-policy"],
        "data_scope": "public_reference",
        "allowed_data_scopes": ["public_reference", "aggregate_operational"],
        "mutation_scope": "none",
        "allowed_mutations": ["none", "event_log"],
        "network_requested": False,
        "sensitive_paths": [],
        "context_key": context,
        "kind": kind,
    }
    if kind == "sensitive":
        payload["sensitive_paths"] = ["payload.private_value"]
    if kind == "source_gap":
        payload["request_source_ids"] = ["src-undeclared"]
    if kind == "mutation":
        payload["mutation_scope"] = "write_private_store"
    return payload


def _budget_payload(kind: str) -> dict[str, Any]:
    common = {"cpu": 1.0, "memory_gb": 1.0, "gpu_count": 0, "storage_gb": 1.0, "max_seconds": 10}
    items: list[dict[str, Any]] = [
        {"item_id": "budget-root", "priority": 10, "cost_units": 1.0, "resource": common, "output_contract": "receipt"},
        {"item_id": "budget-child", "priority": 8, "cost_units": 1.0, "depends_on": ["budget-root"], "resource": {**common, "max_seconds": 15}, "output_contract": "receipt"},
    ]
    if kind == "capacity":
        items.append({"item_id": "budget-too-large", "priority": 20, "cost_units": 1.0, "resource": {**common, "cpu": 8.0}, "output_contract": "receipt"})
    if kind == "network":
        items.append({"item_id": "budget-network", "priority": 5, "cost_units": 1.0, "network_egress": True, "resource": {**common, "network_egress": True}, "output_contract": "receipt"})
    if kind == "cycle":
        items = [
            {"item_id": "budget-a", "depends_on": ["budget-b"], "resource": common},
            {"item_id": "budget-b", "depends_on": ["budget-a"], "resource": common},
        ]
    return {
        "items": items,
        "limits": {"max_invocations": 4, "max_network_requests": 0, "max_seconds": 60, "max_cost_units": 8.0},
        "capacity": {"cpu": 2.0, "memory_gb": 4.0, "gpu_count": 0, "storage_gb": 10.0, "network_egress": False, "max_seconds": 60},
        "schedule_id": f"schedule-{kind}",
        "kind": kind,
    }


def _fallback_payload(kind: str) -> dict[str, Any]:
    payload = {
        "request": {
            "request_id": f"fallback-{kind}",
            "failed_operation_id": "primary.operation",
            "failure_code": "source_unavailable" if kind != "non_retryable" else "handler_failure",
            "retryable": kind != "non_retryable",
            "available_inputs": ["case", "context"],
            "network_allowed": False,
            "require_deterministic": True,
            "requested_output_contract": "receipt",
            "remaining_cost_units": 4.0,
        },
        "candidates": [
            {"candidate_id": "fallback-repeat", "operation_id": "primary.operation", "priority": 100, "output_contract": "receipt"},
            {"candidate_id": "fallback-network", "operation_id": "network.operation", "priority": 80, "network_egress": True, "output_contract": "receipt"},
            {"candidate_id": "fallback-selected", "operation_id": "local.operation", "priority": 60, "required_inputs": ["case"], "output_contract": "receipt", "cost_units": 1.0},
        ],
        "kind": kind,
    }
    if kind == "network":
        payload["candidates"] = [{**payload["candidates"][0], "candidate_id": "fallback-network-only", "operation_id": "network.operation", "network_egress": True}]
    if kind == "missing_input":
        payload["candidates"] = [{**payload["candidates"][0], "candidate_id": "fallback-missing-input", "operation_id": "local.operation", "required_inputs": ["missing"]}]
    return payload


def _review_payload(kind: str) -> dict[str, Any]:
    blockers = ["source_boundary"] if kind == "blocked" else []
    items = [{
        "item_id": "review-ready",
        "request_id": "review-ready",
        "execution_role_id": "role-review",
        "tool_id": "control.review.route",
        "state": "abstained",
        "reasons": ["declared_review"],
        "blockers": blockers,
        "reviewer_roles": ["domain_reviewer"],
        "priority": 80,
        "source_ids": ["src-review"],
        "summary": "aggregate review item",
        "requires_review": True,
    }]
    if kind == "omitted":
        items.extend({**items[0], "item_id": f"review-{index}", "request_id": f"review-{index}", "priority": index} for index in range(1, 5))
    if kind == "empty":
        items[0]["requires_review"] = False
    return {"items": items, "required_roles": ["domain_reviewer"], "max_review_candidates": 2, "queue_id": f"queue-{kind}", "kind": kind}


def _ledger_payload(kind: str) -> dict[str, Any]:
    events = [
        {"event_id": "ledger-1", "kind": "requested", "message": "request received"},
        {"event_id": "ledger-2", "kind": "planned", "message": "plan retained"},
        {"event_id": "ledger-3", "kind": "admitted", "message": "policy admitted"},
        {"event_id": "ledger-4", "kind": "started", "message": "execution started"},
        {"event_id": "ledger-5", "kind": "completed", "message": "receipt completed"},
    ]
    if kind == "invalid_transition":
        events[-1] = {"event_id": "ledger-5", "kind": "requested", "message": "invalid restart"}
    if kind == "duplicate":
        events.append({"event_id": "ledger-4", "kind": "checkpoint", "message": "duplicate ID"})
    if kind == "foreign":
        events[2]["context_key"] = "GRCh38|glioma|pediatric|stem_like|core|untreated"
    return {"execution_id": f"execution-{kind}", "context_key": CONTROL_FRONTIER_CONTEXT_KEY, "events": events, "kind": kind}


def _model_payload(kind: str) -> dict[str, Any]:
    context = CONTROL_FRONTIER_CONTEXT_KEY
    records = [{
        "model_id": "model-control-frontier",
        "version": "v2",
        "model_family": "bounded-evidence",
        "artifact_digest": "sha256:model-control-frontier-v2",
        "input_contract": "aggregate-input",
        "output_contract": "aggregate-receipt",
        "supported_contexts": [context],
        "status": "validated",
        "source_ids": ["src-model"],
        "license_id": "research",
        "evaluation_receipt": "sha256:model-evaluation",
    }]
    query = {"model_id": "model-control-frontier", "context_key": context, "input_contract": "aggregate-input", "output_contract": "aggregate-receipt"}
    if kind == "foreign":
        query["context_key"] = "GRCh38|glioma|pediatric|stem_like|core|untreated"
    if kind == "contract":
        query["input_contract"] = "different-input"
    if kind == "missing":
        query["model_id"] = "missing-model"
    return {"records": records, "query": query, "kind": kind}


def _reference_payload(kind: str) -> dict[str, Any]:
    context = CONTROL_FRONTIER_CONTEXT_KEY
    records = [{
        "dataset_id": "reference-control-frontier",
        "version": "v1",
        "reference_kind": "aggregate-reference",
        "source_uri": "https://example.org/glio-noncode/reference/control-frontier",
        "checksum": "sha256:reference-control-frontier",
        "format": "json",
        "schema_hash": "sha256:reference-schema",
        "supported_contexts": [context],
        "coordinate_system": "GRCh38",
        "license_id": "research",
        "status": "available",
        "source_ids": ["src-reference"],
        "retrieval_receipt": "sha256:reference-retrieval",
    }]
    query = {"dataset_id": "reference-control-frontier", "context_key": context, "coordinate_system": "GRCh38", "license_id": "research"}
    if kind == "foreign":
        query["context_key"] = "GRCh38|glioma|pediatric|stem_like|core|untreated"
    if kind == "coordinate":
        query["coordinate_system"] = "hg19"
    if kind == "license":
        query["license_id"] = "restricted"
    if kind == "missing":
        query["dataset_id"] = "missing-reference"
    return {"records": records, "query": query, "kind": kind}


def _drift_payload(kind: str) -> dict[str, Any]:
    context = CONTROL_FRONTIER_CONTEXT_KEY
    observations = [{
        "observation_id": "drift-ready",
        "monitor_id": "monitor-control-frontier",
        "feature_id": "feature-stable",
        "context_key": context,
        "metric": "mean_delta",
        "reference_value": 0.10,
        "current_value": 0.12,
        "watch_threshold": 0.10,
        "drift_threshold": 0.30,
        "in_domain": True,
        "support_score": 0.92,
        "source_ids": ["src-monitor"],
        "raw_hash": "sha256:drift-ready",
    }]
    if kind == "watch":
        observations[0] = {**observations[0], "feature_id": "feature-watch", "current_value": 0.25, "raw_hash": "sha256:drift-watch"}
    if kind == "drift":
        observations[0] = {**observations[0], "feature_id": "feature-drift", "current_value": 0.70, "raw_hash": "sha256:drift-drift"}
    if kind == "ood":
        observations[0] = {**observations[0], "feature_id": "feature-ood", "in_domain": False, "raw_hash": "sha256:drift-ood"}
    if kind == "foreign":
        observations[0] = {**observations[0], "context_key": "GRCh38|glioma|pediatric|stem_like|core|untreated"}
    return {"monitor_id": "monitor-control-frontier", "context_key": context, "observations": observations, "kind": kind}


def _payload(operation: ControlFrontierOperation, kind: str) -> dict[str, Any]:
    return {
        ControlFrontierOperation.POLICY_CLAIM_GATE: _policy_payload,
        ControlFrontierOperation.BUDGET_RESOURCE_SCHEDULER: _budget_payload,
        ControlFrontierOperation.DETERMINISTIC_FALLBACK: _fallback_payload,
        ControlFrontierOperation.HUMAN_REVIEW_ROUTER: _review_payload,
        ControlFrontierOperation.EXECUTION_LEDGER: _ledger_payload,
        ControlFrontierOperation.MODEL_REGISTRY: _model_payload,
        ControlFrontierOperation.DATA_REFERENCE_REGISTRY: _reference_payload,
        ControlFrontierOperation.DRIFT_OOD_MONITOR: _drift_payload,
    }[operation](kind)


def _record(record_id: str, operation: ControlFrontierOperation, role: ControlFrontierRole, kind: str, expected: ControlFrontierState, issues: tuple[str, ...], source_ids: tuple[str, ...], notes: str) -> ControlFrontierRecord:
    body = {
        "record_id": record_id,
        "operation": operation,
        "role": role,
        "context_key": CONTROL_FRONTIER_CONTEXT_KEY,
        "source_ids": source_ids,
        "payload": _payload(operation, kind),
        "expected_state": expected,
        "expected_issue_codes": issues,
        "notes": notes,
    }
    return ControlFrontierRecord(**body, content_address=content_hash(body))


def default_control_frontier_fixture() -> ControlFrontierFixture:
    """Return 32 rows: one accepted path and three controls per operation."""

    sources = tuple(_source(*item) for item in (
        ("src-policy", "Policy and claim aggregate receipt"),
        ("src-budget", "Budget schedule aggregate receipt"),
        ("src-fallback", "Fallback route aggregate receipt"),
        ("src-review", "Human review aggregate receipt"),
        ("src-ledger", "Execution ledger aggregate receipt"),
        ("src-model", "Model registry aggregate receipt"),
        ("src-reference", "Data reference aggregate receipt"),
        ("src-monitor", "Drift monitor aggregate receipt"),
        ("src-control", "Negative control aggregate receipt"),
    ))
    rows = (
        _record("C05-POS-001", ControlFrontierOperation.POLICY_CLAIM_GATE, ControlFrontierRole.POSITIVE, "positive", ControlFrontierState.SUPPORTED, (), ("src-policy",), "declared public scope passes the claim gate"),
        _record("C05-CTRL-001", ControlFrontierOperation.POLICY_CLAIM_GATE, ControlFrontierRole.CONTROL, "sensitive", ControlFrontierState.BLOCKED, ("sensitive_input",), ("src-control",), "sensitive path blocks admission"),
        _record("C05-CTRL-002", ControlFrontierOperation.POLICY_CLAIM_GATE, ControlFrontierRole.CONTROL, "source_gap", ControlFrontierState.BLOCKED, ("source_allowlist_gap",), ("src-control",), "undeclared source is not admitted"),
        _record("C05-CTRL-003", ControlFrontierOperation.POLICY_CLAIM_GATE, ControlFrontierRole.CONTROL, "mutation", ControlFrontierState.BLOCKED, ("mutation_scope_denied",), ("src-control",), "unapproved mutation remains blocked"),
        _record("C06-POS-001", ControlFrontierOperation.BUDGET_RESOURCE_SCHEDULER, ControlFrontierRole.POSITIVE, "positive", ControlFrontierState.READY, (), ("src-budget",), "dependency-safe work fits declared capacity"),
        _record("C06-CTRL-001", ControlFrontierOperation.BUDGET_RESOURCE_SCHEDULER, ControlFrontierRole.CONTROL, "capacity", ControlFrontierState.PARTIAL, ("capacity_exceeded",), ("src-control",), "oversized work is rejected"),
        _record("C06-CTRL-002", ControlFrontierOperation.BUDGET_RESOURCE_SCHEDULER, ControlFrontierRole.CONTROL, "network", ControlFrontierState.PARTIAL, ("network_limit",), ("src-control",), "network work is deferred"),
        _record("C06-CTRL-003", ControlFrontierOperation.BUDGET_RESOURCE_SCHEDULER, ControlFrontierRole.CONTROL, "cycle", ControlFrontierState.BLOCKED, ("dependency_cycle",), ("src-control",), "cycles block schedule construction"),
        _record("C07-POS-001", ControlFrontierOperation.DETERMINISTIC_FALLBACK, ControlFrontierRole.POSITIVE, "positive", ControlFrontierState.SELECTED, (), ("src-fallback",), "highest eligible local alternative is selected"),
        _record("C07-CTRL-001", ControlFrontierOperation.DETERMINISTIC_FALLBACK, ControlFrontierRole.CONTROL, "non_retryable", ControlFrontierState.BLOCKED, ("non_retryable_failure",), ("src-control",), "non-retryable failure remains blocked"),
        _record("C07-CTRL-002", ControlFrontierOperation.DETERMINISTIC_FALLBACK, ControlFrontierRole.CONTROL, "network", ControlFrontierState.ABSTAINED, ("no_eligible_candidate",), ("src-control",), "network-only candidate is not silently used"),
        _record("C07-CTRL-003", ControlFrontierOperation.DETERMINISTIC_FALLBACK, ControlFrontierRole.CONTROL, "missing_input", ControlFrontierState.ABSTAINED, ("no_eligible_candidate",), ("src-control",), "missing input remains explicit"),
        _record("C08-POS-001", ControlFrontierOperation.HUMAN_REVIEW_ROUTER, ControlFrontierRole.POSITIVE, "positive", ControlFrontierState.READY, (), ("src-review",), "review item routes with declared role and no blocker"),
        _record("C08-CTRL-001", ControlFrontierOperation.HUMAN_REVIEW_ROUTER, ControlFrontierRole.CONTROL, "blocked", ControlFrontierState.BLOCKED, ("review_blocker",), ("src-control",), "blocked review item remains blocked"),
        _record("C08-CTRL-002", ControlFrontierOperation.HUMAN_REVIEW_ROUTER, ControlFrontierRole.CONTROL, "omitted", ControlFrontierState.PARTIAL, ("queue_bounded",), ("src-control",), "bounded queue retains omitted IDs"),
        _record("C08-CTRL-003", ControlFrontierOperation.HUMAN_REVIEW_ROUTER, ControlFrontierRole.CONTROL, "empty", ControlFrontierState.EMPTY, ("no_review_items",), ("src-control",), "non-review outcomes produce an empty queue"),
        _record("C09-POS-001", ControlFrontierOperation.EXECUTION_LEDGER, ControlFrontierRole.POSITIVE, "positive", ControlFrontierState.COMPLETED, (), ("src-ledger",), "valid event history replays to completion"),
        _record("C09-CTRL-001", ControlFrontierOperation.EXECUTION_LEDGER, ControlFrontierRole.CONTROL, "invalid_transition", ControlFrontierState.BLOCKED, ("invalid_event_transition",), ("src-control",), "invalid transition is retained"),
        _record("C09-CTRL-002", ControlFrontierOperation.EXECUTION_LEDGER, ControlFrontierRole.CONTROL, "duplicate", ControlFrontierState.PARTIAL, ("duplicate_event_id",), ("src-control",), "duplicate event is not appended"),
        _record("C09-CTRL-003", ControlFrontierOperation.EXECUTION_LEDGER, ControlFrontierRole.CONTROL, "foreign", ControlFrontierState.OUT_OF_DOMAIN, ("context_mismatch",), ("src-control",), "foreign event is outside the ledger context"),
        _record("C10-POS-001", ControlFrontierOperation.MODEL_REGISTRY, ControlFrontierRole.POSITIVE, "positive", ControlFrontierState.COMPATIBLE, (), ("src-model",), "validated model matches context and contracts"),
        _record("C10-CTRL-001", ControlFrontierOperation.MODEL_REGISTRY, ControlFrontierRole.CONTROL, "foreign", ControlFrontierState.OUT_OF_DOMAIN, ("context_not_supported",), ("src-control",), "foreign model context is blocked"),
        _record("C10-CTRL-002", ControlFrontierOperation.MODEL_REGISTRY, ControlFrontierRole.CONTROL, "contract", ControlFrontierState.BLOCKED, ("input_contract_mismatch",), ("src-control",), "input contract mismatch is explicit"),
        _record("C10-CTRL-003", ControlFrontierOperation.MODEL_REGISTRY, ControlFrontierRole.CONTROL, "missing", ControlFrontierState.ABSTAINED, ("model_version_not_registered",), ("src-control",), "missing model abstains"),
        _record("C11-POS-001", ControlFrontierOperation.DATA_REFERENCE_REGISTRY, ControlFrontierRole.POSITIVE, "positive", ControlFrontierState.COMPATIBLE, (), ("src-reference",), "reference matches coordinate and license"),
        _record("C11-CTRL-001", ControlFrontierOperation.DATA_REFERENCE_REGISTRY, ControlFrontierRole.CONTROL, "foreign", ControlFrontierState.OUT_OF_DOMAIN, ("context_not_supported",), ("src-control",), "foreign reference context is blocked"),
        _record("C11-CTRL-002", ControlFrontierOperation.DATA_REFERENCE_REGISTRY, ControlFrontierRole.CONTROL, "coordinate", ControlFrontierState.BLOCKED, ("coordinate_system_mismatch",), ("src-control",), "coordinate mismatch is explicit"),
        _record("C11-CTRL-003", ControlFrontierOperation.DATA_REFERENCE_REGISTRY, ControlFrontierRole.CONTROL, "missing", ControlFrontierState.ABSTAINED, ("dataset_version_not_registered",), ("src-control",), "missing reference abstains"),
        _record("C12-POS-001", ControlFrontierOperation.DRIFT_OOD_MONITOR, ControlFrontierRole.POSITIVE, "positive", ControlFrontierState.READY, (), ("src-monitor",), "in-domain feature remains within watch thresholds"),
        _record("C12-CTRL-001", ControlFrontierOperation.DRIFT_OOD_MONITOR, ControlFrontierRole.CONTROL, "watch", ControlFrontierState.WATCH, ("metric_exceeds_watch_threshold",), ("src-control",), "watch signal remains distinct from drift"),
        _record("C12-CTRL-002", ControlFrontierOperation.DRIFT_OOD_MONITOR, ControlFrontierRole.CONTROL, "drift", ControlFrontierState.DRIFT, ("metric_exceeds_drift_threshold",), ("src-control",), "drift signal requires review"),
        _record("C12-CTRL-003", ControlFrontierOperation.DRIFT_OOD_MONITOR, ControlFrontierRole.CONTROL, "ood", ControlFrontierState.OUT_OF_DOMAIN, ("declared_out_of_domain",), ("src-control",), "out-of-domain support is not transported"),
    )
    body = {
        "fixture_id": "control-frontier-c05-c12",
        "fixture_version": CONTROL_FRONTIER_VERSION,
        "context_key": CONTROL_FRONTIER_CONTEXT_KEY,
        "evidence_boundary": CONTROL_FRONTIER_BOUNDARY,
        "sources": sources,
        "records": rows,
    }
    return ControlFrontierFixture(**body, content_address=content_hash(body))


@dataclass(frozen=True, slots=True)
class ControlFrontierDataCheck:
    """One public-data integrity check."""

    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierDataAudit:
    """Audit of source, context, role, and record cardinality."""

    fixture_id: str
    checks: tuple[ControlFrontierDataCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def audit_control_frontier_data(fixture: ControlFrontierFixture) -> ControlFrontierDataAudit:
    """Audit aggregate boundaries before operation execution."""

    values = (
        ("source-count", len(fixture.sources), CONTROL_FRONTIER_SOURCE_COUNT, "public source count"),
        ("record-count", len(fixture.records), 32, "four rows per operation"),
        ("positive-count", len(fixture.positive_records), CONTROL_FRONTIER_POSITIVE_COUNT, "one positive per operation"),
        ("control-count", len(fixture.control_records), CONTROL_FRONTIER_CONTROL_COUNT, "three controls per operation"),
        ("context-closure", all(item.context_key == fixture.context_key for item in fixture.records), True, "all rows retain exact context"),
        ("boundary", fixture.evidence_boundary, CONTROL_FRONTIER_BOUNDARY, "aggregate boundary is exact"),
        ("https-sources", all(item.uri.startswith("https://") for item in fixture.sources), True, "source receipts use HTTPS"),
        ("source-ids-unique", len({item.source_id for item in fixture.sources}) == len(fixture.sources), True, "source IDs are unique"),
    )
    checks = []
    for check_id, observed, required, detail in values:
        passed = observed == required
        body = {"check_id": check_id, "passed": passed, "observed": observed, "required": required, "detail": detail}
        checks.append(ControlFrontierDataCheck(**body, content_address=content_hash(body)))
    return ControlFrontierDataAudit(fixture.fixture_id, tuple(checks), all(item.passed for item in checks), content_hash(tuple(checks)))


def load_control_frontier_fixture(payload: Mapping[str, Any] | None = None) -> ControlFrontierFixture:
    """Load the bundled fixture or a serialized compatible fixture."""

    if payload is None:
        return default_control_frontier_fixture()
    required = {
        "fixture_id": "control-frontier-c05-c12",
        "fixture_version": CONTROL_FRONTIER_VERSION,
        "context_key": CONTROL_FRONTIER_CONTEXT_KEY,
        "evidence_boundary": CONTROL_FRONTIER_BOUNDARY,
    }
    for key, expected in required.items():
        if payload.get(key) != expected:
            raise ValidationError(f"serialized control frontier fixture has invalid {key}")
    source_rows = payload.get("sources")
    record_rows = payload.get("records")
    if not isinstance(source_rows, list) or not isinstance(record_rows, list):
        raise ValidationError("serialized control frontier fixture requires source and record arrays")
    sources = tuple(ControlFrontierSourceReceipt(**row) for row in source_rows)
    records = []
    for row in record_rows:
        normalized = dict(row)
        normalized["operation"] = ControlFrontierOperation(row["operation"])
        normalized["role"] = ControlFrontierRole(row["role"])
        normalized["expected_state"] = ControlFrontierState(row["expected_state"])
        normalized["source_ids"] = tuple(row["source_ids"])
        normalized["expected_issue_codes"] = tuple(row["expected_issue_codes"])
        records.append(ControlFrontierRecord(**normalized))
    records = tuple(records)
    body = {**required, "sources": sources, "records": records}
    fixture = ControlFrontierFixture(**body, content_address=str(payload.get("content_address", "")))
    if fixture.content_address != content_hash(body):
        raise ValidationError("serialized control frontier fixture content address does not match")
    return fixture


__all__ = [
    "CONTROL_FRONTIER_CONTROL_COUNT",
    "CONTROL_FRONTIER_POSITIVE_COUNT",
    "CONTROL_FRONTIER_SOURCE_COUNT",
    "ControlFrontierDataAudit",
    "ControlFrontierDataCheck",
    "audit_control_frontier_data",
    "default_control_frontier_fixture",
    "load_control_frontier_fixture",
]
