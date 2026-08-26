"""Build and evolve an evidence-gated execution ledger for module work."""

from __future__ import annotations

import csv
import io
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

from .errors import ValidationError
from .module_workbench_contracts import (
    ModuleWorkbenchReport,
    ModuleWorkbenchTask,
    ModuleWorkbenchTaskKind,
)
from .module_workbench_execution_contracts import (
    MODULE_WORKBENCH_EXECUTION_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_MAX_LIMIT,
    ModuleWorkbenchExecutionAction,
    ModuleWorkbenchExecutionCommand,
    ModuleWorkbenchExecutionEvent,
    ModuleWorkbenchExecutionEventKind,
    ModuleWorkbenchExecutionItem,
    ModuleWorkbenchExecutionLedger,
    ModuleWorkbenchExecutionRequirement,
    ModuleWorkbenchExecutionState,
    address_module_workbench_execution_event,
    address_module_workbench_execution_item,
    address_module_workbench_execution_ledger,
)
from .module_workbench_portfolio import build_module_workbench_portfolio
from .module_workbench_portfolio_contracts import ModuleWorkbenchPortfolio
from .serialization import canonical_json, content_hash

_KIND_ORDER = {
    ModuleWorkbenchTaskKind.REPAIR_PARSE.value: 0,
    ModuleWorkbenchTaskKind.RESOLVE_DEPENDENCY.value: 1,
    ModuleWorkbenchTaskKind.ADD_TEST.value: 2,
    ModuleWorkbenchTaskKind.ADD_DOCUMENTATION.value: 3,
    ModuleWorkbenchTaskKind.EXPAND_PUBLIC_CONTRACT.value: 4,
    ModuleWorkbenchTaskKind.DECOMPOSE_OVERSIZED.value: 5,
    ModuleWorkbenchTaskKind.REVIEW_INTEGRATION.value: 6,
    ModuleWorkbenchTaskKind.CLOSE_CERTIFICATION.value: 7,
}

_REQUIREMENTS = {
    ModuleWorkbenchTaskKind.REPAIR_PARSE.value: (
        ModuleWorkbenchExecutionRequirement.SOURCE,
        ModuleWorkbenchExecutionRequirement.TEST,
    ),
    ModuleWorkbenchTaskKind.RESOLVE_DEPENDENCY.value: (
        ModuleWorkbenchExecutionRequirement.INTEGRATION,
        ModuleWorkbenchExecutionRequirement.SOURCE,
    ),
    ModuleWorkbenchTaskKind.ADD_TEST.value: (ModuleWorkbenchExecutionRequirement.TEST,),
    ModuleWorkbenchTaskKind.ADD_DOCUMENTATION.value: (
        ModuleWorkbenchExecutionRequirement.DOCUMENTATION,
    ),
    ModuleWorkbenchTaskKind.EXPAND_PUBLIC_CONTRACT.value: (
        ModuleWorkbenchExecutionRequirement.DOCUMENTATION,
        ModuleWorkbenchExecutionRequirement.TEST,
    ),
    ModuleWorkbenchTaskKind.DECOMPOSE_OVERSIZED.value: (
        ModuleWorkbenchExecutionRequirement.REVIEW,
        ModuleWorkbenchExecutionRequirement.TEST,
    ),
    ModuleWorkbenchTaskKind.REVIEW_INTEGRATION.value: (
        ModuleWorkbenchExecutionRequirement.INTEGRATION,
        ModuleWorkbenchExecutionRequirement.REVIEW,
    ),
    ModuleWorkbenchTaskKind.CLOSE_CERTIFICATION.value: (
        ModuleWorkbenchExecutionRequirement.REVIEW,
    ),
}

_EVENT_KINDS = {
    ModuleWorkbenchExecutionAction.START: ModuleWorkbenchExecutionEventKind.STARTED,
    ModuleWorkbenchExecutionAction.COMPLETE: ModuleWorkbenchExecutionEventKind.COMPLETED,
    ModuleWorkbenchExecutionAction.BLOCK: ModuleWorkbenchExecutionEventKind.BLOCKED,
    ModuleWorkbenchExecutionAction.UNBLOCK: ModuleWorkbenchExecutionEventKind.UNBLOCKED,
    ModuleWorkbenchExecutionAction.SKIP: ModuleWorkbenchExecutionEventKind.SKIPPED,
    ModuleWorkbenchExecutionAction.REOPEN: ModuleWorkbenchExecutionEventKind.REOPENED,
    ModuleWorkbenchExecutionAction.SUPERSEDE: ModuleWorkbenchExecutionEventKind.SUPERSEDED,
}


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def _item_index(ledger: ModuleWorkbenchExecutionLedger) -> dict[str, int]:
    return {item.task_id: index for index, item in enumerate(ledger.items)}


def _task_index(report: ModuleWorkbenchReport) -> dict[str, ModuleWorkbenchTask]:
    return {task.task_id: task for task in report.tasks}


def _requirements(task: ModuleWorkbenchTask) -> tuple[ModuleWorkbenchExecutionRequirement, ...]:
    values = _REQUIREMENTS.get(
        task.kind.value,
        (ModuleWorkbenchExecutionRequirement.REVIEW,),
    )
    return tuple(sorted(values, key=lambda item: item.value))


def _required_evidence_count(requirements: tuple[ModuleWorkbenchExecutionRequirement, ...]) -> int:
    if ModuleWorkbenchExecutionRequirement.REVIEW in requirements:
        return 2
    return 1


def _prerequisite_map(tasks: tuple[ModuleWorkbenchTask, ...]) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[ModuleWorkbenchTask]] = defaultdict(list)
    for task in tasks:
        grouped[task.module_id].append(task)
    result: dict[str, tuple[str, ...]] = {}
    for _module_id, module_tasks in grouped.items():
        ordered = sorted(
            module_tasks,
            key=lambda item: (_KIND_ORDER.get(item.kind.value, 99), item.task_id),
        )
        previous: str | None = None
        for task in ordered:
            result[task.task_id] = (previous,) if previous else ()
            previous = task.task_id
    return result


def _detail_for(task: ModuleWorkbenchTask, prerequisites: tuple[str, ...]) -> str:
    if prerequisites:
        return (
            f"{task.title}; waiting for {len(prerequisites)} prerequisite task"
            f"{'s' if len(prerequisites) != 1 else ''}"
        )
    return f"{task.title}; ready for execution"


def _item_from_task(
    task: ModuleWorkbenchTask,
    family: str,
    prerequisites: tuple[str, ...],
) -> ModuleWorkbenchExecutionItem:
    requirements = _requirements(task)
    initial_state = (
        ModuleWorkbenchExecutionState.READY
        if not prerequisites
        else ModuleWorkbenchExecutionState.PLANNED
    )
    body = {
        "task_id": task.task_id,
        "module_id": task.module_id,
        "family": family,
        "kind": task.kind.value,
        "priority": task.priority,
        "estimated_impact": task.estimated_impact,
        "prerequisites": prerequisites,
        "requirements": requirements,
        "required_evidence_count": _required_evidence_count(requirements),
        "initial_state": initial_state,
        "state": initial_state,
        "completion_percent": 0.0,
        "event_count": 0,
        "evidence_addresses": (),
        "blockers": (),
        "detail": _detail_for(task, prerequisites),
    }
    return ModuleWorkbenchExecutionItem(
        **body,
        content_address=address_module_workbench_execution_item(
            ModuleWorkbenchExecutionItem(**body, content_address="pending")
        ),
    )


def _counts(items: tuple[ModuleWorkbenchExecutionItem, ...]) -> dict[str, int]:
    counts = Counter(item.state.value for item in items)
    return {
        state.value + "_count": counts.get(state.value, 0)
        for state in ModuleWorkbenchExecutionState
    }


def _completion_percent(items: tuple[ModuleWorkbenchExecutionItem, ...]) -> float:
    if not items:
        return 0.0
    return round(
        sum(item.completion_percent for item in items) / len(items),
        6,
    )


def _evidence_coverage_percent(items: tuple[ModuleWorkbenchExecutionItem, ...]) -> float:
    if not items:
        return 0.0
    total_required = sum(item.required_evidence_count for item in items)
    if not total_required:
        return 100.0
    total_present = sum(
        min(len(item.evidence_addresses), item.required_evidence_count) for item in items
    )
    return round(total_present / total_required * 100.0, 6)


def _ledger(
    report_address: str,
    portfolio_address: str,
    items: tuple[ModuleWorkbenchExecutionItem, ...],
    events: tuple[ModuleWorkbenchExecutionEvent, ...],
    accepted: bool,
) -> ModuleWorkbenchExecutionLedger:
    count_values = _counts(items)
    body = {
        "report_address": report_address,
        "portfolio_address": portfolio_address,
        "items": items,
        "events": events,
        "total_task_count": len(items),
        **count_values,
        "completion_percent": _completion_percent(items),
        "evidence_coverage_percent": _evidence_coverage_percent(items),
        "accepted": accepted,
    }
    provisional = ModuleWorkbenchExecutionLedger(**body, content_address="pending")
    return ModuleWorkbenchExecutionLedger(
        **body,
        content_address=address_module_workbench_execution_ledger(provisional),
    )


def build_module_workbench_execution(
    report: ModuleWorkbenchReport,
    portfolio: ModuleWorkbenchPortfolio | None = None,
) -> ModuleWorkbenchExecutionLedger:
    """Create a deterministic ready/planned ledger from a workbench portfolio."""

    if not isinstance(report, ModuleWorkbenchReport):
        raise ValidationError("execution requires a typed workbench report")
    selected = portfolio or build_module_workbench_portfolio(report)
    if not isinstance(selected, ModuleWorkbenchPortfolio):
        raise ValidationError("execution requires a typed portfolio")
    if selected.report_address != report.content_address:
        raise ValidationError("execution portfolio does not belong to report")
    task_by_id = _task_index(report)
    missing = sorted(
        item.task_id for item in selected.selected_tasks if item.task_id not in task_by_id
    )
    if missing:
        raise ValidationError(f"execution portfolio contains unknown tasks: {missing[:3]}")
    selected_tasks = tuple(selected.selected_tasks)
    prerequisites = _prerequisite_map(selected_tasks)
    families = {item.module_id: item.family for item in report.assessments}
    items = tuple(
        sorted(
            (
                _item_from_task(
                    task_by_id[task.task_id],
                    families.get(task.module_id, "unknown"),
                    prerequisites.get(task.task_id, ()),
                )
                for task in selected_tasks
            ),
            key=lambda item: item.task_id,
        )
    )
    return _ledger(
        report.content_address,
        selected.content_address,
        items,
        (),
        report.accepted and selected.accepted,
    )


def verify_module_workbench_execution(
    value: ModuleWorkbenchExecutionLedger,
) -> ModuleWorkbenchExecutionLedger:
    """Verify every item, event, and the aggregate ledger address."""

    if not isinstance(value, ModuleWorkbenchExecutionLedger):
        raise ValidationError("execution verification requires a typed ledger")
    for item in value.items:
        if address_module_workbench_execution_item(item) != item.content_address:
            raise ValidationError(f"execution item address mismatch: {item.task_id}")
    for event in value.events:
        if address_module_workbench_execution_event(event) != event.content_address:
            raise ValidationError(f"execution event address mismatch: {event.event_id}")
    body = value.to_dict()
    body.pop("content_address", None)
    if _address(body, "module-workbench-execution-ledger") != value.content_address:
        raise ValidationError("execution ledger address mismatch")
    return value


def _state_is_terminal(state: ModuleWorkbenchExecutionState) -> bool:
    return state in {
        ModuleWorkbenchExecutionState.COMPLETED,
        ModuleWorkbenchExecutionState.SKIPPED,
        ModuleWorkbenchExecutionState.SUPERSEDED,
    }


def _prerequisites_complete(
    item: ModuleWorkbenchExecutionItem,
    items: Mapping[str, ModuleWorkbenchExecutionItem],
) -> bool:
    return all(
        prerequisite in items
        and items[prerequisite].state is ModuleWorkbenchExecutionState.COMPLETED
        for prerequisite in item.prerequisites
    )


def _transition_target(
    item: ModuleWorkbenchExecutionItem,
    command: ModuleWorkbenchExecutionCommand,
    items: Mapping[str, ModuleWorkbenchExecutionItem],
) -> tuple[ModuleWorkbenchExecutionState, float, tuple[str, ...], tuple[str, ...]]:
    state = item.state
    action = command.action
    if action is ModuleWorkbenchExecutionAction.START:
        if state is not ModuleWorkbenchExecutionState.READY:
            raise ValidationError("only ready tasks can start")
        if not _prerequisites_complete(item, items):
            raise ValidationError("task prerequisites are not complete")
        return (
            ModuleWorkbenchExecutionState.IN_PROGRESS,
            50.0,
            item.blockers,
            item.evidence_addresses,
        )
    if action is ModuleWorkbenchExecutionAction.COMPLETE:
        if state is not ModuleWorkbenchExecutionState.IN_PROGRESS:
            raise ValidationError("only in-progress tasks can complete")
        if command.requirement is not None and command.requirement not in item.requirements:
            raise ValidationError("completion requirement is not declared by task")
        evidence = tuple(sorted(set(item.evidence_addresses + command.evidence_addresses)))
        if len(evidence) < item.required_evidence_count:
            raise ValidationError("completion requires the declared evidence count")
        return ModuleWorkbenchExecutionState.COMPLETED, 100.0, (), evidence
    if action is ModuleWorkbenchExecutionAction.BLOCK:
        if _state_is_terminal(state):
            raise ValidationError("terminal tasks cannot be blocked")
        blockers = tuple(sorted(set(item.blockers + (command.detail,))))
        return (
            ModuleWorkbenchExecutionState.BLOCKED,
            item.completion_percent,
            blockers,
            item.evidence_addresses,
        )
    if action is ModuleWorkbenchExecutionAction.UNBLOCK:
        if state is not ModuleWorkbenchExecutionState.BLOCKED:
            raise ValidationError("only blocked tasks can be unblocked")
        if not _prerequisites_complete(item, items):
            raise ValidationError("task prerequisites are not complete")
        return ModuleWorkbenchExecutionState.READY, 0.0, (), item.evidence_addresses
    if action is ModuleWorkbenchExecutionAction.SKIP:
        if _state_is_terminal(state):
            raise ValidationError("terminal tasks cannot be skipped")
        return ModuleWorkbenchExecutionState.SKIPPED, 0.0, (), item.evidence_addresses
    if action is ModuleWorkbenchExecutionAction.REOPEN:
        if state not in {
            ModuleWorkbenchExecutionState.COMPLETED,
            ModuleWorkbenchExecutionState.SKIPPED,
        }:
            raise ValidationError("only completed or skipped tasks can be reopened")
        if not _prerequisites_complete(item, items):
            raise ValidationError("task prerequisites are not complete")
        return ModuleWorkbenchExecutionState.READY, 0.0, (), ()
    if action is ModuleWorkbenchExecutionAction.SUPERSEDE:
        if _state_is_terminal(state):
            raise ValidationError("terminal tasks cannot be superseded")
        return (
            ModuleWorkbenchExecutionState.SUPERSEDED,
            0.0,
            (command.detail,),
            item.evidence_addresses,
        )
    raise ValidationError("unsupported execution action")


def _updated_item(
    item: ModuleWorkbenchExecutionItem,
    command: ModuleWorkbenchExecutionCommand,
    items: Mapping[str, ModuleWorkbenchExecutionItem],
) -> ModuleWorkbenchExecutionItem:
    target, completion, blockers, evidence = _transition_target(item, command, items)
    body = {
        "task_id": item.task_id,
        "module_id": item.module_id,
        "family": item.family,
        "kind": item.kind,
        "priority": item.priority,
        "estimated_impact": item.estimated_impact,
        "prerequisites": item.prerequisites,
        "requirements": item.requirements,
        "required_evidence_count": item.required_evidence_count,
        "initial_state": item.initial_state,
        "state": target,
        "completion_percent": completion,
        "event_count": item.event_count + 1,
        "evidence_addresses": tuple(sorted(set(evidence))),
        "blockers": tuple(sorted(set(blockers))),
        "detail": command.detail,
    }
    return ModuleWorkbenchExecutionItem(
        **body,
        content_address=address_module_workbench_execution_item(
            ModuleWorkbenchExecutionItem(**body, content_address="pending")
        ),
    )


def _event(
    sequence: int,
    item: ModuleWorkbenchExecutionItem,
    updated: ModuleWorkbenchExecutionItem,
    command: ModuleWorkbenchExecutionCommand,
) -> ModuleWorkbenchExecutionEvent:
    body = {
        "event_id": f"{item.task_id}#{sequence}#{command.action.value}",
        "sequence": sequence,
        "task_id": item.task_id,
        "from_state": item.state,
        "to_state": updated.state,
        "kind": _EVENT_KINDS[command.action],
        "detail": command.detail,
        "evidence_addresses": command.evidence_addresses,
    }
    return ModuleWorkbenchExecutionEvent(
        **body,
        content_address=address_module_workbench_execution_event(
            ModuleWorkbenchExecutionEvent(**body, content_address="pending")
        ),
    )


def apply_module_workbench_execution_command(
    ledger: ModuleWorkbenchExecutionLedger,
    command: ModuleWorkbenchExecutionCommand,
) -> ModuleWorkbenchExecutionLedger:
    """Apply one validated command and return a new addressed ledger."""

    verify_module_workbench_execution(ledger)
    if not isinstance(command, ModuleWorkbenchExecutionCommand):
        raise ValidationError("execution command must be typed")
    index = _item_index(ledger)
    if command.task_id not in index:
        raise ValidationError(f"unknown execution task: {command.task_id}")
    item = ledger.items[index[command.task_id]]
    items_by_id = {entry.task_id: entry for entry in ledger.items}
    updated = _updated_item(item, command, items_by_id)
    rows = list(ledger.items)
    rows[index[command.task_id]] = updated
    event = _event(len(ledger.events) + 1, item, updated, command)
    return _ledger(
        ledger.report_address,
        ledger.portfolio_address,
        tuple(rows),
        (*ledger.events, event),
        ledger.accepted,
    )


def apply_module_workbench_execution_commands(
    ledger: ModuleWorkbenchExecutionLedger,
    commands: Iterable[ModuleWorkbenchExecutionCommand],
) -> ModuleWorkbenchExecutionLedger:
    """Apply commands in order, retaining an addressable event sequence."""

    current = ledger
    for command in commands:
        current = apply_module_workbench_execution_command(current, command)
    return current


def execution_command(
    task_id: str,
    action: ModuleWorkbenchExecutionAction | str,
    detail: str,
    *,
    evidence_addresses: tuple[str, ...] = (),
    requirement: ModuleWorkbenchExecutionRequirement | str | None = None,
) -> ModuleWorkbenchExecutionCommand:
    """Convenience constructor for callers and small integrations."""

    selected_action = (
        action
        if isinstance(action, ModuleWorkbenchExecutionAction)
        else ModuleWorkbenchExecutionAction(action)
    )
    selected_requirement = (
        None
        if requirement is None
        else requirement
        if isinstance(requirement, ModuleWorkbenchExecutionRequirement)
        else ModuleWorkbenchExecutionRequirement(requirement)
    )
    return ModuleWorkbenchExecutionCommand(
        task_id=task_id,
        action=selected_action,
        detail=detail,
        evidence_addresses=evidence_addresses,
        requirement=selected_requirement,
    )


def _query_rows(
    value: ModuleWorkbenchExecutionLedger,
    resource: str,
) -> list[dict[str, Any]]:
    if resource == "items":
        return [item.to_dict() for item in value.items]
    if resource == "events":
        return [event.to_dict() for event in value.events]
    if resource == "blockers":
        return [
            {
                "task_id": item.task_id,
                "module_id": item.module_id,
                "family": item.family,
                "state": item.state,
                "blockers": list(item.blockers),
                "detail": item.detail,
                "content_address": item.content_address,
            }
            for item in value.items
            if item.blockers
        ]
    if resource == "summary":
        return [value.to_dict(include_items=False, include_events=False)]
    raise ValidationError("execution resource must be items, events, blockers, or summary")


def query_module_workbench_execution(
    value: ModuleWorkbenchExecutionLedger,
    *,
    resource: str = "items",
    task_id: str | None = None,
    module_id: str | None = None,
    family: str | None = None,
    state: str | None = None,
    kind: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return a bounded item, event, blocker, or summary projection."""

    if not isinstance(value, ModuleWorkbenchExecutionLedger):
        raise ValidationError("execution query requires a typed ledger")
    if offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_EXECUTION_MAX_LIMIT:
        raise ValidationError("execution paging is invalid")
    rows = _query_rows(value, resource)
    if task_id:
        rows = [item for item in rows if item.get("task_id") == task_id]
    if module_id:
        rows = [item for item in rows if item.get("module_id") == module_id]
    if family:
        rows = [item for item in rows if item.get("family") == family]
    if state:
        rows = [item for item in rows if item.get("state") == state]
    if kind:
        rows = [item for item in rows if item.get("kind") == kind]
    if text:
        folded = text.casefold()
        rows = [item for item in rows if folded in canonical_json(item).casefold()]
    body = {
        "ledger_address": value.content_address,
        "query": {
            "resource": resource,
            "task_id": task_id,
            "module_id": module_id,
            "family": family,
            "state": state,
            "kind": kind,
            "text": text,
        },
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "accepted": value.accepted,
    }
    return body | {"content_address": _address(body, "module-workbench-execution-query")}


def module_workbench_execution_json(value: ModuleWorkbenchExecutionLedger) -> str:
    """Serialize the complete execution ledger as canonical JSON."""

    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_csv(
    value: ModuleWorkbenchExecutionLedger,
    resource: str = "items",
) -> str:
    """Export bounded item or event rows as deterministic CSV."""

    output = io.StringIO(newline="")
    if resource == "items":
        fields = (
            "task_id",
            "module_id",
            "family",
            "kind",
            "priority",
            "state",
            "completion_percent",
            "event_count",
            "required_evidence_count",
            "evidence_count",
            "prerequisite_count",
            "blocker_count",
            "detail",
            "content_address",
        )
        writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for item in value.items:
            writer.writerow(
                {
                    "task_id": item.task_id,
                    "module_id": item.module_id,
                    "family": item.family,
                    "kind": item.kind,
                    "priority": item.priority,
                    "state": item.state.value,
                    "completion_percent": item.completion_percent,
                    "event_count": item.event_count,
                    "required_evidence_count": item.required_evidence_count,
                    "evidence_count": len(item.evidence_addresses),
                    "prerequisite_count": len(item.prerequisites),
                    "blocker_count": len(item.blockers),
                    "detail": item.detail,
                    "content_address": item.content_address,
                }
            )
        return output.getvalue()
    if resource == "events":
        fields = (
            "sequence",
            "event_id",
            "task_id",
            "from_state",
            "to_state",
            "kind",
            "detail",
            "evidence_count",
            "content_address",
        )
        writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for event in value.events:
            writer.writerow(
                {
                    "sequence": event.sequence,
                    "event_id": event.event_id,
                    "task_id": event.task_id,
                    "from_state": event.from_state.value,
                    "to_state": event.to_state.value,
                    "kind": event.kind.value,
                    "detail": event.detail,
                    "evidence_count": len(event.evidence_addresses),
                    "content_address": event.content_address,
                }
            )
        return output.getvalue()
    raise ValidationError("execution CSV resource must be items or events")


def render_module_workbench_execution_markdown(
    value: ModuleWorkbenchExecutionLedger,
) -> str:
    """Render a review-oriented execution ledger without private identity data."""

    lines = [
        "# Module Workbench Execution",
        "",
        f"- Ledger: `{value.content_address}`",
        f"- Tasks: {value.total_task_count}",
        f"- Events: {len(value.events)}",
        f"- Completion: {value.completion_percent:.2f}%",
        f"- Evidence coverage: {value.evidence_coverage_percent:.2f}%",
        f"- Accepted: `{str(value.accepted).lower()}`",
        "",
        "## State distribution",
        "",
        "| State | Count |",
        "| --- | ---: |",
    ]
    for state in ModuleWorkbenchExecutionState:
        lines.append(f"| {state.value} | {getattr(value, state.value + '_count')} |")
    lines.extend(
        (
            "",
            "## Task ledger",
            "",
            "| Task | Module | State | Evidence | Detail |",
            "| --- | --- | --- | ---: | --- |",
        )
    )
    for item in value.items:
        lines.append(
            f"| `{item.task_id}` | `{item.module_id}` | `{item.state.value}` | "
            f"{len(item.evidence_addresses)}/{item.required_evidence_count} | {item.detail} |"
        )
    if value.events:
        lines.extend(
            (
                "",
                "## Transition history",
                "",
                "| # | Task | From | To | Detail |",
                "| ---: | --- | --- | --- | --- |",
            )
        )
        for event in value.events:
            lines.append(
                f"| {event.sequence} | `{event.task_id}` | `{event.from_state.value}` | "
                f"`{event.to_state.value}` | {event.detail} |"
            )
    return "\n".join(lines) + "\n"


def module_workbench_execution_schema() -> dict[str, Any]:
    """Describe execution fields, lifecycle, and deterministic guarantees."""

    return {
        "version": "module-workbench-execution-v1",
        "boundary": "public_aggregate_module_workbench_execution",
        "states": [state.value for state in ModuleWorkbenchExecutionState],
        "actions": [action.value for action in ModuleWorkbenchExecutionAction],
        "event_kinds": [kind.value for kind in ModuleWorkbenchExecutionEventKind],
        "requirements": [requirement.value for requirement in ModuleWorkbenchExecutionRequirement],
        "resources": ["items", "events", "blockers", "summary"],
        "transition_rules": {
            "start": "ready -> in_progress when prerequisites are completed",
            "complete": "in_progress -> completed with required evidence",
            "block": "planned, ready, or in_progress -> blocked with detail",
            "unblock": "blocked -> ready when prerequisites are completed",
            "skip": "non-terminal -> skipped with detail",
            "reopen": "completed or skipped -> ready after prerequisites are completed",
            "supersede": "non-terminal -> superseded with detail",
        },
        "ordering": "items by task ID; events by contiguous sequence",
        "path_free": True,
        "timestamp_free": True,
        "identity_free": True,
    }


def module_workbench_execution_capabilities() -> dict[str, Any]:
    """Advertise the operational execution surface."""

    operations = (
        "build_execution_ledger",
        "derive_prerequisites",
        "classify_requirements",
        "start_task",
        "complete_task_with_evidence",
        "block_task",
        "unblock_task",
        "skip_task",
        "reopen_task",
        "supersede_task",
        "append_addressed_event",
        "replay_ordered_commands",
        "query_items",
        "query_events",
        "query_blockers",
        "summarize_progress",
        "export_json",
        "export_items_csv",
        "export_events_csv",
        "render_markdown",
        "verify_nested_addresses",
    )
    return {
        "version": "module-workbench-execution-v1",
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "append_only_events": True,
        "evidence_gated_completion": True,
        "read_only_projection": True,
    }


__all__ = [
    "apply_module_workbench_execution_command",
    "apply_module_workbench_execution_commands",
    "build_module_workbench_execution",
    "execution_command",
    "module_workbench_execution_capabilities",
    "module_workbench_execution_csv",
    "module_workbench_execution_json",
    "module_workbench_execution_schema",
    "query_module_workbench_execution",
    "render_module_workbench_execution_markdown",
    "verify_module_workbench_execution",
]
