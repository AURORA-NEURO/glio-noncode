"""Deterministic public aggregate fixture for Domain 16 C01-C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .platform_frontier_contracts import (
    PLATFORM_FRONTIER_BOUNDARY,
    PLATFORM_FRONTIER_CONTEXT_KEY,
    PLATFORM_FRONTIER_VERSION,
    PlatformFrontierFixture,
    PlatformFrontierOperation,
    PlatformFrontierRecord,
    PlatformFrontierRole,
    PlatformFrontierSourceReceipt,
    PlatformFrontierState,
)
from .errors import ValidationError
from .serialization import content_hash, jsonable


PLATFORM_FRONTIER_SOURCE_COUNT = 5
PLATFORM_FRONTIER_POSITIVE_COUNT = 4
PLATFORM_FRONTIER_CONTROL_COUNT = 12
PLATFORM_FRONTIER_RECORD_COUNT = 16


def _source(source_id: str, title: str) -> PlatformFrontierSourceReceipt:
    body = {
        "source_id": source_id,
        "title": title,
        "uri": f"https://example.org/glio-noncode/platform-frontier/{source_id}",
        "access_note": "public aggregate operational receipt; no private row-level data",
    }
    return PlatformFrontierSourceReceipt(**body, content_address=content_hash(body))


def _mission_payload(kind: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "mission_id": f"platform-mission-{kind}",
        "project_id": "glio-noncode",
        "intended_use": "research hypothesis exploration",
        "requested_question": "Which declared observations warrant review?",
        "claim_ceiling": "hypothesis",
        "allowed_source_ids": [],
        "allowed_data_scopes": ["synthetic", "public_reference"],
        "allowed_mutations": ["none", "event_log", "content_addressed_store"],
        "requested_roles": ["A01", "A02"],
        "workflow_id": f"platform-workflow-{kind}",
    }
    if kind == "empty":
        payload["requested_roles"] = []
    if kind == "unknown":
        payload["requested_roles"] = ["A99"]
    if kind == "ceiling":
        payload["requested_roles"] = ["A46"]
        payload["claim_ceiling"] = "observation"
    return payload


def _workflow_step(
    step_id: str,
    kind: str,
    depends_on: tuple[str, ...] = (),
    *,
    network: bool = False,
    deterministic: bool = True,
) -> dict[str, Any]:
    return {
        "step_id": step_id,
        "kind": kind,
        "depends_on": list(depends_on),
        "resource": {
            "cpu": 1.0,
            "memory_gb": 1.0,
            "gpu_count": 0,
            "storage_gb": 1.0,
            "network_egress": network,
            "max_seconds": 60,
        },
        "optional": False,
        "deterministic": deterministic,
        "input_contract": "aggregate_input",
        "output_contract": "aggregate_output",
    }


def _workflow_payload(kind: str) -> dict[str, Any]:
    steps = [
        _workflow_step("ingest", "ingest"),
        _workflow_step("normalize", "normalize", ("ingest",)),
        _workflow_step("review", "review", ("normalize",)),
    ]
    if kind == "cycle":
        steps = [
            _workflow_step("left", "ingest", ("right",)),
            _workflow_step("right", "normalize", ("left",)),
        ]
    if kind == "missing":
        steps = [_workflow_step("review", "review", ("missing-step",))]
    if kind == "warning":
        steps.append(_workflow_step("remote", "evidence", ("review",), network=True, deterministic=False))
    return {"workflow_id": f"platform-workflow-{kind}", "steps": steps, "kind": kind}


def _registry_payload(kind: str) -> dict[str, Any]:
    payload = {
        "tool_id": "A01.inspect",
        "expected_input_contract": "mission_context",
        "expected_output_contract": "inspection_record",
        "expected_tool_count": 96,
        "kind": kind,
    }
    if kind == "missing":
        payload["tool_id"] = "A99.inspect"
    if kind == "contract":
        payload["expected_input_contract"] = "different_contract"
    if kind == "count":
        payload["expected_tool_count"] = 95
    return payload


def _sandbox_payload(kind: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "request_id": f"sandbox-{kind}",
        "role_id": "A01",
        "tool_id": "A01.publish",
        "register_handler": True,
        "input_payload": {"data_scope": "synthetic", "question": "bounded"},
        "kind": kind,
    }
    if kind == "unregistered":
        payload["register_handler"] = False
    if kind == "network":
        payload["role_id"] = "A09"
        payload["tool_id"] = "A09.inspect"
        payload["register_handler"] = False
    if kind == "sensitive":
        payload["input_payload"] = {"data_scope": "synthetic", "name": "hidden"}
    return payload


def _payload(operation: PlatformFrontierOperation, kind: str) -> dict[str, Any]:
    builders = {
        PlatformFrontierOperation.MISSION_PLANNER: _mission_payload,
        PlatformFrontierOperation.WORKFLOW_COMPILER: _workflow_payload,
        PlatformFrontierOperation.TYPED_TOOL_REGISTRY: _registry_payload,
        PlatformFrontierOperation.EXECUTION_SANDBOX: _sandbox_payload,
    }
    return builders[operation](kind)


def _record(
    record_id: str,
    operation: PlatformFrontierOperation,
    role: PlatformFrontierRole,
    kind: str,
    expected: PlatformFrontierState,
    issues: tuple[str, ...],
    source_ids: tuple[str, ...],
    notes: str,
) -> PlatformFrontierRecord:
    body = {
        "record_id": record_id,
        "operation": operation,
        "role": role,
        "context_key": PLATFORM_FRONTIER_CONTEXT_KEY,
        "source_ids": source_ids,
        "payload": _payload(operation, kind),
        "expected_state": expected,
        "expected_issue_codes": issues,
        "notes": notes,
    }
    return PlatformFrontierRecord(**body, content_address=content_hash(body))


def default_platform_frontier_fixture() -> PlatformFrontierFixture:
    """Return one positive and three controls for each C01-C04 operation."""

    sources = tuple(
        _source(*item)
        for item in (
            ("src-planning", "Mission planning aggregate receipt"),
            ("src-workflow", "Workflow compilation aggregate receipt"),
            ("src-registry", "Typed registry aggregate receipt"),
            ("src-sandbox", "Execution isolation aggregate receipt"),
            ("src-platform-control", "Negative platform control receipt"),
        )
    )
    rows = (
        _record("C01-POS-001", PlatformFrontierOperation.MISSION_PLANNER, PlatformFrontierRole.POSITIVE, "positive", PlatformFrontierState.READY, (), ("src-planning",), "declared roles expand to a dependency-complete plan"),
        _record("C01-CTRL-001", PlatformFrontierOperation.MISSION_PLANNER, PlatformFrontierRole.CONTROL, "empty", PlatformFrontierState.ABSTAINED, ("no_roles_requested",), ("src-platform-control",), "an empty request abstains without hidden work"),
        _record("C01-CTRL-002", PlatformFrontierOperation.MISSION_PLANNER, PlatformFrontierRole.CONTROL, "unknown", PlatformFrontierState.REJECTED, ("unknown_role",), ("src-platform-control",), "an unknown role is rejected explicitly"),
        _record("C01-CTRL-003", PlatformFrontierOperation.MISSION_PLANNER, PlatformFrontierRole.CONTROL, "ceiling", PlatformFrontierState.REJECTED, ("claim_ceiling_exceeded",), ("src-platform-control",), "a role above the mission claim ceiling is rejected"),
        _record("C02-POS-001", PlatformFrontierOperation.WORKFLOW_COMPILER, PlatformFrontierRole.POSITIVE, "positive", PlatformFrontierState.READY, (), ("src-workflow",), "a dependency-safe workflow compiles in stable order"),
        _record("C02-CTRL-001", PlatformFrontierOperation.WORKFLOW_COMPILER, PlatformFrontierRole.CONTROL, "cycle", PlatformFrontierState.BLOCKED, ("dependency_cycle",), ("src-platform-control",), "a cycle blocks compilation"),
        _record("C02-CTRL-002", PlatformFrontierOperation.WORKFLOW_COMPILER, PlatformFrontierRole.CONTROL, "missing", PlatformFrontierState.BLOCKED, ("missing_dependency",), ("src-platform-control",), "a missing dependency blocks compilation"),
        _record("C02-CTRL-003", PlatformFrontierOperation.WORKFLOW_COMPILER, PlatformFrontierRole.CONTROL, "warning", PlatformFrontierState.PARTIAL, ("network_or_nondeterminism",), ("src-platform-control",), "network and nondeterministic steps remain review-visible"),
        _record("C03-POS-001", PlatformFrontierOperation.TYPED_TOOL_REGISTRY, PlatformFrontierRole.POSITIVE, "positive", PlatformFrontierState.COMPATIBLE, (), ("src-registry",), "a registered tool matches the declared contracts"),
        _record("C03-CTRL-001", PlatformFrontierOperation.TYPED_TOOL_REGISTRY, PlatformFrontierRole.CONTROL, "missing", PlatformFrontierState.REJECTED, ("tool_not_registered",), ("src-platform-control",), "an unknown tool cannot be resolved"),
        _record("C03-CTRL-002", PlatformFrontierOperation.TYPED_TOOL_REGISTRY, PlatformFrontierRole.CONTROL, "contract", PlatformFrontierState.INCOMPATIBLE, ("input_contract_mismatch",), ("src-platform-control",), "an input contract mismatch remains explicit"),
        _record("C03-CTRL-003", PlatformFrontierOperation.TYPED_TOOL_REGISTRY, PlatformFrontierRole.CONTROL, "count", PlatformFrontierState.INCOMPATIBLE, ("registry_cardinality_mismatch",), ("src-platform-control",), "a registry cardinality mismatch blocks release"),
        _record("C04-POS-001", PlatformFrontierOperation.EXECUTION_SANDBOX, PlatformFrontierRole.POSITIVE, "positive", PlatformFrontierState.ADMITTED, (), ("src-sandbox",), "a registered local handler executes through policy and events"),
        _record("C04-CTRL-001", PlatformFrontierOperation.EXECUTION_SANDBOX, PlatformFrontierRole.CONTROL, "unregistered", PlatformFrontierState.DENIED, ("handler_not_registered",), ("src-platform-control",), "unregistered work is denied before execution"),
        _record("C04-CTRL-002", PlatformFrontierOperation.EXECUTION_SANDBOX, PlatformFrontierRole.CONTROL, "network", PlatformFrontierState.DENIED, ("network_egress_disabled",), ("src-platform-control",), "network work is denied in local isolation"),
        _record("C04-CTRL-003", PlatformFrontierOperation.EXECUTION_SANDBOX, PlatformFrontierRole.CONTROL, "sensitive", PlatformFrontierState.REJECTED, ("direct_identifier",), ("src-platform-control",), "sensitive payload fields are rejected by policy"),
    )
    body = {
        "fixture_id": "platform-frontier-c01-c04",
        "fixture_version": PLATFORM_FRONTIER_VERSION,
        "context_key": PLATFORM_FRONTIER_CONTEXT_KEY,
        "evidence_boundary": PLATFORM_FRONTIER_BOUNDARY,
        "sources": sources,
        "records": rows,
    }
    return PlatformFrontierFixture(**body, content_address=content_hash(body))


@dataclass(frozen=True, slots=True)
class PlatformFrontierDataCheck:
    """One data-boundary check for the platform fixture."""

    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierDataAudit:
    """Aggregate source, role, context, and cardinality audit."""

    fixture_id: str
    checks: tuple[PlatformFrontierDataCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def audit_platform_frontier_data(fixture: PlatformFrontierFixture) -> PlatformFrontierDataAudit:
    values = (
        ("source-count", len(fixture.sources), PLATFORM_FRONTIER_SOURCE_COUNT, "five public source receipts"),
        ("record-count", len(fixture.records), PLATFORM_FRONTIER_RECORD_COUNT, "four rows per operation"),
        ("positive-count", len(fixture.positive_records), PLATFORM_FRONTIER_POSITIVE_COUNT, "one positive per operation"),
        ("control-count", len(fixture.control_records), PLATFORM_FRONTIER_CONTROL_COUNT, "three controls per operation"),
        ("context-closure", all(item.context_key == fixture.context_key for item in fixture.records), True, "all rows retain the exact context"),
        ("boundary", fixture.evidence_boundary, PLATFORM_FRONTIER_BOUNDARY, "aggregate boundary is exact"),
        ("https-sources", all(item.uri.startswith("https://") for item in fixture.sources), True, "source receipts use HTTPS"),
        ("source-ids-unique", len({item.source_id for item in fixture.sources}) == len(fixture.sources), True, "source IDs are unique"),
        ("record-ids-unique", len({item.record_id for item in fixture.records}) == len(fixture.records), True, "record IDs are unique"),
    )
    checks = []
    for check_id, observed, required, detail in values:
        body = {"check_id": check_id, "passed": observed == required, "observed": observed, "required": required, "detail": detail}
        checks.append(PlatformFrontierDataCheck(**body, content_address=content_hash(body)))
    return PlatformFrontierDataAudit(fixture.fixture_id, tuple(checks), all(item.passed for item in checks), content_hash(tuple(checks)))


def load_platform_frontier_fixture(payload: Mapping[str, Any] | None = None) -> PlatformFrontierFixture:
    """Load the bundled fixture or reconstruct a compatible JSON payload."""

    if payload is None:
        return default_platform_frontier_fixture()
    required = {
        "fixture_id": "platform-frontier-c01-c04",
        "fixture_version": PLATFORM_FRONTIER_VERSION,
        "context_key": PLATFORM_FRONTIER_CONTEXT_KEY,
        "evidence_boundary": PLATFORM_FRONTIER_BOUNDARY,
    }
    for key, expected in required.items():
        if payload.get(key) != expected:
            raise ValidationError(f"serialized platform fixture has invalid {key}")
    source_rows = payload.get("sources")
    record_rows = payload.get("records")
    if not isinstance(source_rows, list) or not isinstance(record_rows, list):
        raise ValidationError("serialized platform fixture requires source and record arrays")
    sources = tuple(PlatformFrontierSourceReceipt(**row) for row in source_rows)
    records = []
    for row in record_rows:
        normalized = dict(row)
        normalized["operation"] = PlatformFrontierOperation(row["operation"])
        normalized["role"] = PlatformFrontierRole(row["role"])
        normalized["expected_state"] = PlatformFrontierState(row["expected_state"])
        normalized["source_ids"] = tuple(row["source_ids"])
        normalized["expected_issue_codes"] = tuple(row["expected_issue_codes"])
        records.append(PlatformFrontierRecord(**normalized))
    body = {**required, "sources": sources, "records": tuple(records)}
    fixture = PlatformFrontierFixture(**body, content_address=str(payload.get("content_address", "")))
    if fixture.content_address != content_hash(body):
        raise ValidationError("serialized platform fixture address does not match")
    return fixture


__all__ = [
    "PLATFORM_FRONTIER_CONTROL_COUNT",
    "PLATFORM_FRONTIER_POSITIVE_COUNT",
    "PLATFORM_FRONTIER_RECORD_COUNT",
    "PLATFORM_FRONTIER_SOURCE_COUNT",
    "PlatformFrontierDataAudit",
    "PlatformFrontierDataCheck",
    "audit_platform_frontier_data",
    "default_platform_frontier_fixture",
    "load_platform_frontier_fixture",
]
