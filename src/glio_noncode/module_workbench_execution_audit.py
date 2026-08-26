"""Independent invariant audit and bounded exports for execution ledgers."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_audit_contracts import (
    MODULE_WORKBENCH_EXECUTION_AUDIT_BOUNDARY,
    MODULE_WORKBENCH_EXECUTION_AUDIT_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_AUDIT_MAX_LIMIT,
    MODULE_WORKBENCH_EXECUTION_AUDIT_VERSION,
    ModuleWorkbenchExecutionAudit,
    ModuleWorkbenchExecutionAuditCheck,
    ModuleWorkbenchExecutionAuditPlane,
    address_module_workbench_execution_audit,
    address_module_workbench_execution_audit_check,
)
from .module_workbench_execution_contracts import (
    ModuleWorkbenchExecutionEventKind,
    ModuleWorkbenchExecutionLedger,
    ModuleWorkbenchExecutionState,
    address_module_workbench_execution_event,
    address_module_workbench_execution_item,
    address_module_workbench_execution_ledger,
)
from .serialization import canonical_json, content_hash, jsonable

_FORBIDDEN_KEYS = frozenset(
    {
        "agent",
        "agent_id",
        "agent_name",
        "author",
        "author_id",
        "author_name",
        "email",
        "generated_by",
        "language",
        "model",
        "model_id",
        "model_name",
        "model_version",
        "programming_language",
    }
)

_EVENT_TRANSITIONS = {
    ModuleWorkbenchExecutionEventKind.STARTED: {
        (ModuleWorkbenchExecutionState.READY, ModuleWorkbenchExecutionState.IN_PROGRESS),
    },
    ModuleWorkbenchExecutionEventKind.COMPLETED: {
        (ModuleWorkbenchExecutionState.IN_PROGRESS, ModuleWorkbenchExecutionState.COMPLETED),
    },
    ModuleWorkbenchExecutionEventKind.BLOCKED: {
        (ModuleWorkbenchExecutionState.PLANNED, ModuleWorkbenchExecutionState.BLOCKED),
        (ModuleWorkbenchExecutionState.READY, ModuleWorkbenchExecutionState.BLOCKED),
        (ModuleWorkbenchExecutionState.IN_PROGRESS, ModuleWorkbenchExecutionState.BLOCKED),
    },
    ModuleWorkbenchExecutionEventKind.UNBLOCKED: {
        (ModuleWorkbenchExecutionState.BLOCKED, ModuleWorkbenchExecutionState.READY),
    },
    ModuleWorkbenchExecutionEventKind.SKIPPED: {
        (ModuleWorkbenchExecutionState.PLANNED, ModuleWorkbenchExecutionState.SKIPPED),
        (ModuleWorkbenchExecutionState.READY, ModuleWorkbenchExecutionState.SKIPPED),
        (ModuleWorkbenchExecutionState.IN_PROGRESS, ModuleWorkbenchExecutionState.SKIPPED),
        (ModuleWorkbenchExecutionState.BLOCKED, ModuleWorkbenchExecutionState.SKIPPED),
    },
    ModuleWorkbenchExecutionEventKind.REOPENED: {
        (ModuleWorkbenchExecutionState.COMPLETED, ModuleWorkbenchExecutionState.READY),
        (ModuleWorkbenchExecutionState.SKIPPED, ModuleWorkbenchExecutionState.READY),
    },
    ModuleWorkbenchExecutionEventKind.SUPERSEDED: {
        (ModuleWorkbenchExecutionState.PLANNED, ModuleWorkbenchExecutionState.SUPERSEDED),
        (ModuleWorkbenchExecutionState.READY, ModuleWorkbenchExecutionState.SUPERSEDED),
        (ModuleWorkbenchExecutionState.IN_PROGRESS, ModuleWorkbenchExecutionState.SUPERSEDED),
        (ModuleWorkbenchExecutionState.BLOCKED, ModuleWorkbenchExecutionState.SUPERSEDED),
    },
}


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def _check(
    check_id: str,
    plane: ModuleWorkbenchExecutionAuditPlane,
    passed: bool,
    observed: Any,
    expected: Any,
    detail: str,
) -> ModuleWorkbenchExecutionAuditCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "expected": expected,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionAuditCheck(**body, content_address="pending")
    return ModuleWorkbenchExecutionAuditCheck(
        **body,
        content_address=address_module_workbench_execution_audit_check(provisional),
    )


def _all_keys(value: Any) -> tuple[str, ...]:
    value = jsonable(value)
    keys: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            keys.append(str(key))
            keys.extend(_all_keys(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            keys.extend(_all_keys(item))
    return tuple(keys)


def _address_check(value: ModuleWorkbenchExecutionLedger) -> bool:
    return (
        all(
            address_module_workbench_execution_item(item) == item.content_address
            for item in value.items
        )
        and all(
            address_module_workbench_execution_event(event) == event.content_address
            for event in value.events
        )
        and address_module_workbench_execution_ledger(value) == value.content_address
    )


def _event_sequence_check(value: ModuleWorkbenchExecutionLedger) -> tuple[bool, list[str]]:
    ids = [event.event_id for event in value.events]
    task_ids = {item.task_id for item in value.items}
    details: list[str] = []
    if tuple(event.sequence for event in value.events) != tuple(range(1, len(value.events) + 1)):
        details.append("event sequences are not contiguous")
    if len(ids) != len(set(ids)):
        details.append("event IDs are duplicated")
    if any(event.task_id not in task_ids for event in value.events):
        details.append("event references an unknown task")
    return not details, details


def _transition_graph_check(value: ModuleWorkbenchExecutionLedger) -> tuple[bool, list[str]]:
    states = {item.task_id: item.initial_state for item in value.items}
    details: list[str] = []
    for event in value.events:
        current = states.get(event.task_id)
        if current is None:
            details.append(f"unknown task at sequence {event.sequence}")
            continue
        if current is not event.from_state:
            details.append(f"from-state mismatch at sequence {event.sequence}")
        if (event.from_state, event.to_state) not in _EVENT_TRANSITIONS.get(event.kind, set()):
            details.append(f"invalid transition at sequence {event.sequence}")
        states[event.task_id] = event.to_state
    details.extend(
        f"final state mismatch for {item.task_id}"
        for item in value.items
        if states.get(item.task_id) is not item.state
    )
    return not details, details


def _prerequisite_check(value: ModuleWorkbenchExecutionLedger) -> tuple[bool, list[str]]:
    by_id = {item.task_id: item for item in value.items}
    details: list[str] = []
    for item in value.items:
        if item.task_id in item.prerequisites:
            details.append(f"self dependency for {item.task_id}")
        for prerequisite in item.prerequisites:
            if prerequisite not in by_id:
                details.append(f"unknown prerequisite {prerequisite} for {item.task_id}")
        if item.state in {
            ModuleWorkbenchExecutionState.READY,
            ModuleWorkbenchExecutionState.IN_PROGRESS,
            ModuleWorkbenchExecutionState.COMPLETED,
        } and any(
            prerequisite not in by_id
            or by_id[prerequisite].state is not ModuleWorkbenchExecutionState.COMPLETED
            for prerequisite in item.prerequisites
        ):
            details.append(f"ineligible prerequisite closure for {item.task_id}")
    graph = {item.task_id: item.prerequisites for item in value.items}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visiting:
            details.append(f"prerequisite cycle at {task_id}")
            return
        if task_id in visited:
            return
        visiting.add(task_id)
        for prerequisite in graph.get(task_id, ()):
            visit(prerequisite)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in graph:
        visit(task_id)
    return not details, details


def _evidence_check(value: ModuleWorkbenchExecutionLedger) -> tuple[bool, list[str]]:
    details: list[str] = []
    for item in value.items:
        if (
            item.state is ModuleWorkbenchExecutionState.COMPLETED
            and len(item.evidence_addresses) < item.required_evidence_count
        ):
            details.append(f"completed task lacks evidence: {item.task_id}")
        if (
            item.state
            in {
                ModuleWorkbenchExecutionState.BLOCKED,
                ModuleWorkbenchExecutionState.SUPERSEDED,
            }
            and not item.blockers
        ):
            details.append(f"terminal exception lacks blocker: {item.task_id}")
    return not details, details


def _count_check(value: ModuleWorkbenchExecutionLedger) -> tuple[bool, dict[str, int]]:
    observed = {
        state.value + "_count": sum(item.state is state for item in value.items)
        for state in ModuleWorkbenchExecutionState
    }
    expected = {
        state.value + "_count": getattr(value, state.value + "_count")
        for state in ModuleWorkbenchExecutionState
    }
    return observed == expected, {key: observed[key] - expected[key] for key in observed}


def _conservation_check(value: ModuleWorkbenchExecutionLedger) -> tuple[bool, dict[str, int]]:
    expected_events = sum(item.event_count for item in value.items)
    observed = {
        "item_count": len(value.items),
        "declared_task_count": value.total_task_count,
        "event_count": len(value.events),
        "declared_event_count": expected_events,
    }
    return (
        len(value.items) == value.total_task_count and len(value.events) == expected_events
    ), observed


def audit_module_workbench_execution(
    value: ModuleWorkbenchExecutionLedger,
) -> ModuleWorkbenchExecutionAudit:
    """Run independent address, graph, evidence, and boundary checks."""

    if not isinstance(value, ModuleWorkbenchExecutionLedger):
        raise ValidationError("execution audit requires a typed ledger")
    event_sequence_passed, event_sequence_detail = _event_sequence_check(value)
    transition_passed, transition_detail = _transition_graph_check(value)
    prerequisite_passed, prerequisite_detail = _prerequisite_check(value)
    evidence_passed, evidence_detail = _evidence_check(value)
    count_passed, count_detail = _count_check(value)
    conservation_passed, conservation_detail = _conservation_check(value)
    keys = tuple(sorted(set(_all_keys(value))))
    forbidden = tuple(sorted(key for key in keys if key.casefold() in _FORBIDDEN_KEYS))
    checks = tuple(
        sorted(
            (
                _check(
                    "addresses",
                    ModuleWorkbenchExecutionAuditPlane.ADDRESSES,
                    _address_check(value),
                    True,
                    True,
                    "nested item, event, and ledger content addresses are stable",
                ),
                _check(
                    "boundary-keys",
                    ModuleWorkbenchExecutionAuditPlane.BOUNDARY_KEYS,
                    not forbidden,
                    list(forbidden),
                    [],
                    "public execution output contains no forbidden identity or language keys",
                ),
                _check(
                    "conservation",
                    ModuleWorkbenchExecutionAuditPlane.CONSERVATION,
                    conservation_passed,
                    conservation_detail,
                    "item and event totals agree with their declarations",
                    "all declared items and event references are conserved",
                ),
                _check(
                    "evidence",
                    ModuleWorkbenchExecutionAuditPlane.EVIDENCE,
                    evidence_passed,
                    evidence_detail,
                    [],
                    "completion and exception states retain required evidence or blocker detail",
                ),
                _check(
                    "event-sequence",
                    ModuleWorkbenchExecutionAuditPlane.EVENT_SEQUENCE,
                    event_sequence_passed,
                    event_sequence_detail,
                    [],
                    "event sequence is contiguous, unique, and task-addressed",
                ),
                _check(
                    "prerequisites",
                    ModuleWorkbenchExecutionAuditPlane.PREREQUISITES,
                    prerequisite_passed,
                    prerequisite_detail,
                    [],
                    "prerequisite references are known, acyclic, and respected by active states",
                ),
                _check(
                    "state-counts",
                    ModuleWorkbenchExecutionAuditPlane.STATE_COUNTS,
                    count_passed,
                    count_detail,
                    {state.value + "_count": 0 for state in ModuleWorkbenchExecutionState},
                    "state counts match the item rows",
                ),
                _check(
                    "transition-graph",
                    ModuleWorkbenchExecutionAuditPlane.TRANSITION_GRAPH,
                    transition_passed,
                    transition_detail,
                    [],
                    "event transitions reconstruct the persisted final state",
                ),
            ),
            key=lambda item: item.check_id,
        )
    )
    body = {
        "ledger_address": value.content_address,
        "checks": checks,
        "check_count": len(checks),
        "passed_count": sum(item.passed for item in checks),
        "failed_count": sum(not item.passed for item in checks),
        "accepted": value.accepted and all(item.passed for item in checks),
    }
    provisional = ModuleWorkbenchExecutionAudit(**body, content_address="pending")
    return ModuleWorkbenchExecutionAudit(
        **body,
        content_address=address_module_workbench_execution_audit(provisional),
    )


def verify_module_workbench_execution_audit(
    value: ModuleWorkbenchExecutionAudit,
) -> ModuleWorkbenchExecutionAudit:
    """Verify nested and aggregate audit addresses."""

    if not isinstance(value, ModuleWorkbenchExecutionAudit):
        raise ValidationError("execution audit verification requires a typed audit")
    for check in value.checks:
        if address_module_workbench_execution_audit_check(check) != check.content_address:
            raise ValidationError(f"execution audit check address mismatch: {check.check_id}")
    body = value.to_dict()
    body.pop("content_address", None)
    if _address(body, "module-workbench-execution-audit") != value.content_address:
        raise ValidationError("execution audit address mismatch")
    return value


def query_module_workbench_execution_audit(
    value: ModuleWorkbenchExecutionAudit,
    *,
    plane: str | None = None,
    passed: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_AUDIT_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return a bounded audit check page."""

    if not isinstance(value, ModuleWorkbenchExecutionAudit):
        raise ValidationError("execution audit query requires a typed audit")
    if offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_EXECUTION_AUDIT_MAX_LIMIT:
        raise ValidationError("execution audit paging is invalid")
    rows = [item.to_dict() for item in value.checks]
    if plane:
        rows = [item for item in rows if item.get("plane") == plane]
    if passed is not None:
        rows = [item for item in rows if item.get("passed") is passed]
    if text:
        rows = [item for item in rows if text.casefold() in canonical_json(item).casefold()]
    body = {
        "audit_address": value.content_address,
        "query": {"plane": plane, "passed": passed, "text": text},
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "accepted": value.accepted,
    }
    return body | {"content_address": _address(body, "module-workbench-execution-audit-query")}


def module_workbench_execution_audit_json(
    value: ModuleWorkbenchExecutionAudit,
) -> str:
    """Serialize an audit as canonical JSON."""

    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_audit_csv(
    value: ModuleWorkbenchExecutionAudit,
) -> str:
    """Export audit checks as deterministic CSV."""

    output = io.StringIO(newline="")
    fields = ("check_id", "plane", "passed", "observed", "expected", "detail", "content_address")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for check in value.checks:
        writer.writerow(
            {
                "check_id": check.check_id,
                "plane": check.plane.value,
                "passed": check.passed,
                "observed": canonical_json(check.observed),
                "expected": canonical_json(check.expected),
                "detail": check.detail,
                "content_address": check.content_address,
            }
        )
    return output.getvalue()


def module_workbench_execution_audit_schema() -> dict[str, Any]:
    """Describe the independent audit contract."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_AUDIT_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_AUDIT_BOUNDARY,
        "planes": [plane.value for plane in ModuleWorkbenchExecutionAuditPlane],
        "resources": ["checks", "summary"],
        "check_count": 8,
        "timestamp_free": True,
        "identity_free": True,
    }


def module_workbench_execution_audit_capabilities() -> dict[str, Any]:
    """Advertise the independent audit surface."""

    operations = (
        "verify_item_addresses",
        "verify_event_addresses",
        "verify_ledger_address",
        "audit_event_sequence",
        "audit_transition_graph",
        "audit_prerequisite_closure",
        "audit_evidence_requirements",
        "audit_state_counts",
        "audit_item_event_conservation",
        "audit_boundary_keys",
        "query_checks",
        "export_json",
        "export_csv",
        "verify_audit_address",
    )
    return {
        "version": MODULE_WORKBENCH_EXECUTION_AUDIT_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "independent_from_builder": True,
        "deterministic": True,
    }


__all__ = [
    "audit_module_workbench_execution",
    "module_workbench_execution_audit_capabilities",
    "module_workbench_execution_audit_csv",
    "module_workbench_execution_audit_json",
    "module_workbench_execution_audit_schema",
    "query_module_workbench_execution_audit",
    "verify_module_workbench_execution_audit",
]
