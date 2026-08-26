"""Append-only, dependency-aware execution for review-workspace plans.

``review_workspace_plan`` creates a deterministic checklist.  This module
provides the durable operational state that checklist needs without mutating a
scientific dossier: callers append explicit start, complete, block, skip, and
reopen events; the current state is reconstructed by replaying the event chain.

The ledger is intentionally narrow.  It stores plan and action addresses,
typed transition names, public check identifiers, bounded reasons, and
declared reference addresses.  It never stores raw evidence, a reviewer or
agent identity, model metadata, programming-language metadata, or a scientific
decision.  Completion is allowed only after every plan dependency is complete
and the action's declared public checks have been named in the completion
event.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import StoreError, ValidationError
from .module_fabric_support import contains_private_key
from .review_workspace_plan import (
    ReviewPlanAction,
    ReviewWorkspacePlan,
)
from .serialization import canonical_json, content_hash, hash_bytes, jsonable


REVIEW_WORKSPACE_EXECUTION_VERSION = "review-workspace-execution-v1"
REVIEW_WORKSPACE_EXECUTION_SCHEMA_VERSION = "review-workspace-execution-schema-v1"
REVIEW_WORKSPACE_EXECUTION_EVENT_VERSION = "review-workspace-execution-event-v1"
REVIEW_WORKSPACE_EXECUTION_MAX_EVENTS = 50_000
REVIEW_WORKSPACE_EXECUTION_MAX_REASON = 1_000
REVIEW_WORKSPACE_EXECUTION_MAX_REFERENCES = 64
REVIEW_WORKSPACE_EXECUTION_LEDGER_DIR = "review-plan-execution"
REVIEW_WORKSPACE_EXECUTION_EVENTS_FILE = "events.jsonl"
REVIEW_WORKSPACE_EXECUTION_MANIFEST_FILE = "manifest.json"

_SAFE_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_KEYS = frozenset(
    {
        "agent",
        "agent_id",
        "agent_name",
        "assistant",
        "assistant_id",
        "assistant_name",
        "author",
        "author_id",
        "author_name",
        "contact",
        "contact_name",
        "credential",
        "credential_value",
        "email",
        "generated_by",
        "individual",
        "individual_id",
        "language",
        "medical_record_number",
        "model",
        "model_id",
        "model_name",
        "model_version",
        "participant",
        "participant_id",
        "patient",
        "patient_id",
        "phone",
        "programming_language",
        "produced_by",
        "sample",
        "sample_id",
        "secret",
        "secret_key",
        "subject",
        "subject_id",
        "token",
    }
)


class ReviewPlanExecutionStatus(StrEnum):
    """Current status of one plan action or the aggregate execution."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class ReviewPlanExecutionEventKind(StrEnum):
    """Allowed append-only transitions."""

    START = "start"
    COMPLETE = "complete"
    BLOCK = "block"
    SKIP = "skip"
    REOPEN = "reopen"


@dataclass(frozen=True, slots=True)
class ReviewPlanExecutionEvent:
    """One public, hash-addressed event in the execution ledger."""

    event_id: str
    plan_id: str
    plan_address: str
    action_id: str
    kind: ReviewPlanExecutionEventKind
    occurred_at: str
    reason: str
    check_ids: tuple[str, ...]
    reference_addresses: tuple[str, ...]
    previous_event_address: str | None
    content_address: str

    def __post_init__(self) -> None:
        if not self.event_id.strip():
            raise ValidationError("execution event_id must not be empty")
        if len(self.reason) > REVIEW_WORKSPACE_EXECUTION_MAX_REASON:
            raise ValidationError("execution event reason exceeds the bound")
        if len(self.reference_addresses) > REVIEW_WORKSPACE_EXECUTION_MAX_REFERENCES:
            raise ValidationError("execution event reference count exceeds the bound")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewPlanActionExecution:
    """Replayed state and readiness for one planned action."""

    action_id: str
    queue_item_id: str
    target_id: str
    lane: str
    action_kind: str
    priority: int
    status: ReviewPlanExecutionStatus
    ready: bool
    unresolved_dependencies: tuple[str, ...]
    event_ids: tuple[str, ...]
    last_event_id: str | None
    started_at: str | None
    completed_at: str | None
    reason: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewExecutionCheck:
    """One invariant supporting an accepted replay projection."""

    check_id: str
    passed: bool
    required: bool
    observed: Any
    expected: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionReport:
    """Complete replay projection for one review-plan execution ledger."""

    execution_id: str
    plan_id: str
    plan_address: str
    workspace_id: str
    run_id: str
    case_id: str
    version: str
    state: ReviewPlanExecutionStatus
    accepted: bool
    event_count: int
    action_count: int
    open_count: int
    in_progress_count: int
    completed_count: int
    blocked_count: int
    skipped_count: int
    dependency_wait_count: int
    next_action_ids: tuple[str, ...]
    blocked_action_ids: tuple[str, ...]
    events: tuple[ReviewPlanExecutionEvent, ...]
    actions: tuple[ReviewPlanActionExecution, ...]
    checks: tuple[ReviewExecutionCheck, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionQuery:
    """Bounded action/event filters for execution progress."""

    status: str | None = None
    lane: str | None = None
    action_kind: str | None = None
    action_id: str | None = None
    event_kind: str | None = None
    priority: int | None = None
    text: str | None = None
    offset: int = 0
    limit: int | None = 50

    def __post_init__(self) -> None:
        for name in ("status", "lane", "action_kind", "action_id", "event_kind"):
            value = getattr(self, name)
            if value is not None and not str(value).strip():
                raise ValidationError(f"execution query {name} must not be blank")
        if self.status is not None and str(self.status).strip().casefold() not in {
            item.value for item in ReviewPlanExecutionStatus
        }:
            raise ValidationError("execution query status is invalid")
        if self.event_kind is not None and str(self.event_kind).strip().casefold() not in {
            item.value for item in ReviewPlanExecutionEventKind
        }:
            raise ValidationError("execution query event_kind is invalid")
        if self.priority is not None and self.priority not in {0, 1, 2, 3}:
            raise ValidationError("execution query priority must be between 0 and 3")
        if self.text is not None:
            normalized = str(self.text).strip()
            if len(normalized) > 256:
                raise ValidationError("execution query text exceeds the bound")
            object.__setattr__(self, "text", normalized or None)
        if self.offset < 0:
            raise ValidationError("execution query offset must be non-negative")
        if self.limit is not None and (self.limit < 1 or self.limit > 500):
            raise ValidationError("execution query limit is outside the bound")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> "ReviewWorkspaceExecutionQuery":
        if raw is None:
            return cls()
        if not isinstance(raw, Mapping):
            raise ValidationError("execution query must be an object")
        return cls(
            status=raw.get("status"),
            lane=raw.get("lane"),
            action_kind=raw.get("action_kind"),
            action_id=raw.get("action_id"),
            event_kind=raw.get("event_kind"),
            priority=None if raw.get("priority") is None else int(raw["priority"]),
            text=raw.get("text"),
            offset=int(raw.get("offset", 0)),
            limit=None if raw.get("limit") is None else int(raw.get("limit", 50)),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionQueryResult:
    """Deterministic action page with complete-match facets."""

    execution_address: str
    query: ReviewWorkspaceExecutionQuery
    rows: tuple[ReviewPlanActionExecution, ...]
    total_count: int
    has_more: bool
    facets: Mapping[str, Mapping[str, int]]
    accepted: bool
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _text(value: Any, field: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValidationError(f"{field} must not be empty")
    return normalized


def _unique(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


def _public(value: Any) -> Any:
    value = jsonable(value)
    if isinstance(value, Mapping):
        return {
            str(key): _public(item)
            for key, item in value.items()
            if str(key).casefold() not in _FORBIDDEN_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_public(item) for item in value]
    return value


def _has_forbidden(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            str(key).casefold() in _FORBIDDEN_KEYS or _has_forbidden(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_has_forbidden(item) for item in value)
    return False


def _address(value: Any, prefix: str) -> str:
    return content_hash(_public(value), prefix=prefix)


def _parse_instant(value: Any, field: str) -> str:
    text = _text(value, field)
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValidationError(f"{field} must be an ISO-8601 instant") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat()


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return {str(key): value[key] for key in value}


def _text_sequence(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValidationError(f"{field} must be an array")
    result = tuple(_text(item, f"{field}[]") for item in value)
    if len(set(result)) != len(result):
        raise ValidationError(f"{field} must not contain duplicates")
    return result


def _optional_instant(value: Any, field: str) -> str | None:
    if value in (None, ""):
        return None
    return _parse_instant(value, field)


def _address_without_content(body: Mapping[str, Any], prefix: str, field: str) -> str:
    address = _text(body.get("content_address"), field)
    source = {key: value for key, value in body.items() if key != "content_address"}
    expected = _address(source, prefix)
    if address != expected:
        raise ValidationError(f"{field} address mismatch")
    return address


def _action_execution_from_mapping(value: Mapping[str, Any]) -> ReviewPlanActionExecution:
    body = _mapping(value, "execution action")
    status_text = _text(body.get("status"), "execution action.status")
    try:
        status = ReviewPlanExecutionStatus(status_text)
    except ValueError as exc:
        raise ValidationError("execution action.status is invalid") from exc
    unresolved = _text_sequence(body.get("unresolved_dependencies", ()), "execution action.unresolved_dependencies")
    event_ids = _text_sequence(body.get("event_ids", ()), "execution action.event_ids")
    content_address = _address_without_content(body, "review-plan-action-execution", "execution action.content_address")
    return ReviewPlanActionExecution(
        action_id=_text(body.get("action_id"), "execution action.action_id"),
        queue_item_id=_text(body.get("queue_item_id"), "execution action.queue_item_id"),
        target_id=_text(body.get("target_id"), "execution action.target_id"),
        lane=_text(body.get("lane"), "execution action.lane"),
        action_kind=_text(body.get("action_kind"), "execution action.action_kind"),
        priority=int(body.get("priority")),
        status=status,
        ready=bool(body.get("ready")),
        unresolved_dependencies=unresolved,
        event_ids=event_ids,
        last_event_id=(None if body.get("last_event_id") in (None, "") else _text(body.get("last_event_id"), "execution action.last_event_id")),
        started_at=_optional_instant(body.get("started_at"), "execution action.started_at"),
        completed_at=_optional_instant(body.get("completed_at"), "execution action.completed_at"),
        reason=str(body.get("reason", "")).strip(),
        content_address=content_address,
    )


def _execution_check_from_mapping(value: Mapping[str, Any]) -> ReviewExecutionCheck:
    body = _mapping(value, "execution check")
    content_address = _address_without_content(body, "review-execution-check", "execution check.content_address")
    return ReviewExecutionCheck(
        check_id=_text(body.get("check_id"), "execution check.check_id"),
        passed=bool(body.get("passed")),
        required=bool(body.get("required")),
        observed=body.get("observed"),
        expected=body.get("expected"),
        detail=str(body.get("detail", "")).strip(),
        content_address=content_address,
    )


def review_workspace_execution_report_from_mapping(value: Mapping[str, Any]) -> ReviewWorkspaceExecutionReport:
    """Hydrate one execution report and independently verify derived addresses."""

    body = _mapping(value, "execution report")
    if _has_forbidden(body) or contains_private_key(body):
        raise ValidationError("execution report violates the public boundary")
    raw_events = body.get("events", ())
    raw_actions = body.get("actions", ())
    raw_checks = body.get("checks", ())
    if not isinstance(raw_events, (list, tuple)) or not isinstance(raw_actions, (list, tuple)) or not isinstance(raw_checks, (list, tuple)):
        raise ValidationError("execution report nested collections are invalid")
    events = tuple(
        review_plan_execution_event_from_mapping(_mapping(item, "execution report event"))
        for item in raw_events
    )
    actions = tuple(
        _action_execution_from_mapping(_mapping(item, "execution report action"))
        for item in raw_actions
    )
    checks = tuple(
        _execution_check_from_mapping(_mapping(item, "execution report check"))
        for item in raw_checks
    )
    event_ids = tuple(item.event_id for item in events)
    action_ids = tuple(item.action_id for item in actions)
    if len(set(event_ids)) != len(event_ids):
        raise ValidationError("execution report contains duplicate event IDs")
    if len(set(action_ids)) != len(action_ids):
        raise ValidationError("execution report contains duplicate action IDs")
    previous_address: str | None = None
    previous_time: str | None = None
    for event in events:
        if event.previous_event_address != previous_address:
            raise ValidationError("execution report event chain is not contiguous")
        if previous_time is not None and event.occurred_at < previous_time:
            raise ValidationError("execution report event timestamps are not monotonic")
        previous_address = event.content_address
        previous_time = event.occurred_at
    plan_id = _text(body.get("plan_id"), "execution report.plan_id")
    plan_address = _text(body.get("plan_address"), "execution report.plan_address")
    if any(item.plan_id != plan_id or item.plan_address != plan_address for item in events):
        raise ValidationError("execution report events do not share the report plan")
    state_text = _text(body.get("state"), "execution report.state")
    try:
        state = ReviewPlanExecutionStatus(state_text)
    except ValueError as exc:
        raise ValidationError("execution report.state is invalid") from exc
    warnings = _text_sequence(body.get("warnings", ()), "execution report.warnings")
    expected_counts = {
        "event_count": len(events),
        "action_count": len(actions),
        "open_count": sum(item.status is ReviewPlanExecutionStatus.OPEN for item in actions),
        "in_progress_count": sum(item.status is ReviewPlanExecutionStatus.IN_PROGRESS for item in actions),
        "completed_count": sum(item.status is ReviewPlanExecutionStatus.COMPLETED for item in actions),
        "blocked_count": sum(item.status is ReviewPlanExecutionStatus.BLOCKED for item in actions),
        "skipped_count": sum(item.status is ReviewPlanExecutionStatus.SKIPPED for item in actions),
        "dependency_wait_count": sum(
            bool(item.unresolved_dependencies) and item.status is ReviewPlanExecutionStatus.OPEN
            for item in actions
        ),
    }
    for field, expected in expected_counts.items():
        try:
            observed = int(body.get(field))
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"execution report.{field} is invalid") from exc
        if observed != expected:
            raise ValidationError(f"execution report.{field} does not reconcile")
    next_action_ids = _text_sequence(body.get("next_action_ids", ()), "execution report.next_action_ids")
    blocked_action_ids = _text_sequence(body.get("blocked_action_ids", ()), "execution report.blocked_action_ids")
    if next_action_ids != tuple(item.action_id for item in actions if item.ready):
        raise ValidationError("execution report.next_action_ids does not reconcile")
    if blocked_action_ids != tuple(item.action_id for item in actions if item.status is ReviewPlanExecutionStatus.BLOCKED):
        raise ValidationError("execution report.blocked_action_ids does not reconcile")
    projected = {
        "execution_id": _text(body.get("execution_id"), "execution report.execution_id"),
        "plan_id": plan_id,
        "plan_address": plan_address,
        "workspace_id": _text(body.get("workspace_id"), "execution report.workspace_id"),
        "run_id": _text(body.get("run_id"), "execution report.run_id"),
        "case_id": _text(body.get("case_id"), "execution report.case_id"),
        "version": _text(body.get("version"), "execution report.version"),
        "state": state,
        "accepted": bool(body.get("accepted")),
        **expected_counts,
        "next_action_ids": next_action_ids,
        "blocked_action_ids": blocked_action_ids,
        "events": events,
        "actions": actions,
        "checks": checks,
        "warnings": warnings,
    }
    expected_execution_id = f"review-plan-execution:{plan_address}"
    if projected["execution_id"] != expected_execution_id:
        raise ValidationError("execution report.execution_id does not reconcile")
    content_address = _address_without_content(body, "review-workspace-execution", "execution report.content_address")
    if _address(projected, "review-workspace-execution") != content_address:
        raise ValidationError("execution report content address does not reconcile")
    return ReviewWorkspaceExecutionReport(**projected, content_address=content_address)


def _plan_actions(plan: ReviewWorkspacePlan) -> dict[str, ReviewPlanAction]:
    actions = {item.action_id: item for item in plan.actions}
    if len(actions) != len(plan.actions):
        raise ValidationError("review plan contains duplicate action identifiers")
    if any(action.content_address == "" for action in actions.values()):
        raise ValidationError("review plan contains an unaddressed action")
    return actions


def _event_body(event: ReviewPlanExecutionEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "plan_id": event.plan_id,
        "plan_address": event.plan_address,
        "action_id": event.action_id,
        "kind": event.kind,
        "occurred_at": event.occurred_at,
        "reason": event.reason,
        "check_ids": event.check_ids,
        "reference_addresses": event.reference_addresses,
        "previous_event_address": event.previous_event_address,
    }


def _validate_event_address(event: ReviewPlanExecutionEvent) -> None:
    expected = _address(_event_body(event), "review-plan-execution-event")
    if event.content_address != expected:
        raise ValidationError(f"execution event address mismatch: {event.event_id}")


def review_plan_execution_event_from_mapping(value: Mapping[str, Any]) -> ReviewPlanExecutionEvent:
    """Hydrate and verify one serialized public event."""

    body = _mapping(value, "execution event")
    if _has_forbidden(body) or contains_private_key(body):
        raise ValidationError("execution event violates the public boundary")
    try:
        kind = ReviewPlanExecutionEventKind(_text(body.get("kind"), "event.kind"))
    except ValueError as exc:
        raise ValidationError("execution event kind is invalid") from exc
    checks = body.get("check_ids", ())
    references = body.get("reference_addresses", ())
    if not isinstance(checks, (list, tuple)) or not isinstance(references, (list, tuple)):
        raise ValidationError("execution event arrays are invalid")
    reason = str(body.get("reason", "")).strip()
    event = ReviewPlanExecutionEvent(
        event_id=_text(body.get("event_id"), "event.event_id"),
        plan_id=_text(body.get("plan_id"), "event.plan_id"),
        plan_address=_text(body.get("plan_address"), "event.plan_address"),
        action_id=_text(body.get("action_id"), "event.action_id"),
        kind=kind,
        occurred_at=_parse_instant(body.get("occurred_at"), "event.occurred_at"),
        reason=reason,
        check_ids=_unique(checks),
        reference_addresses=_unique(references),
        previous_event_address=(
            None
            if body.get("previous_event_address") in (None, "")
            else _text(body.get("previous_event_address"), "event.previous_event_address")
        ),
        content_address=_text(body.get("content_address"), "event.content_address"),
    )
    _validate_event_address(event)
    return event


def build_review_plan_execution_event(
    *,
    plan: ReviewWorkspacePlan,
    action_id: str,
    event_id: str,
    kind: ReviewPlanExecutionEventKind | str,
    occurred_at: str,
    reason: str = "",
    check_ids: Iterable[str] = (),
    reference_addresses: Iterable[str] = (),
    previous_event_address: str | None = None,
) -> ReviewPlanExecutionEvent:
    """Create one addressed transition after validating its public fields."""

    actions = _plan_actions(plan)
    normalized_action = _text(action_id, "action_id")
    if normalized_action not in actions:
        raise ValidationError(f"execution event names unknown action: {normalized_action}")
    try:
        selected_kind = ReviewPlanExecutionEventKind(
            kind.value if isinstance(kind, ReviewPlanExecutionEventKind) else str(kind)
        )
    except ValueError as exc:
        raise ValidationError("execution event kind is invalid") from exc
    normalized_reason = str(reason).strip()
    if len(normalized_reason) > REVIEW_WORKSPACE_EXECUTION_MAX_REASON:
        raise ValidationError("execution event reason exceeds the bound")
    event = ReviewPlanExecutionEvent(
        event_id=_text(event_id, "event_id"),
        plan_id=plan.plan_id,
        plan_address=plan.content_address,
        action_id=normalized_action,
        kind=selected_kind,
        occurred_at=_parse_instant(occurred_at, "occurred_at"),
        reason=normalized_reason,
        check_ids=_unique(check_ids),
        reference_addresses=_unique(reference_addresses),
        previous_event_address=previous_event_address,
        content_address="",
    )
    body = _event_body(event)
    return ReviewPlanExecutionEvent(
        **body,
        content_address=_address(body, "review-plan-execution-event"),
    )


def _empty_report(plan: ReviewWorkspacePlan, *, accepted: bool, warnings: Iterable[str]) -> ReviewWorkspaceExecutionReport:
    warnings_value = tuple(dict.fromkeys(str(item) for item in warnings if str(item).strip()))
    check_body = {
        "check_id": "source:review-workspace-plan-accepted",
        "passed": accepted,
        "required": True,
        "observed": plan.accepted,
        "expected": True,
        "detail": (
            "source review plan is accepted"
            if accepted
            else "source review plan is not accepted; execution rows are withheld"
        ),
    }
    check = ReviewExecutionCheck(**check_body, content_address=_address(check_body, "review-execution-check"))
    body = {
        "execution_id": f"review-plan-execution:{plan.content_address}",
        "plan_id": plan.plan_id,
        "plan_address": plan.content_address,
        "workspace_id": plan.workspace_id,
        "run_id": plan.run_id,
        "case_id": plan.case_id,
        "version": REVIEW_WORKSPACE_EXECUTION_VERSION,
        "state": ReviewPlanExecutionStatus.OPEN if accepted else ReviewPlanExecutionStatus.BLOCKED,
        "accepted": accepted,
        "event_count": 0,
        "action_count": 0,
        "open_count": 0,
        "in_progress_count": 0,
        "completed_count": 0,
        "blocked_count": 0,
        "skipped_count": 0,
        "dependency_wait_count": 0,
        "next_action_ids": (),
        "blocked_action_ids": (),
        "events": (),
        "actions": (),
        "checks": (check,),
        "warnings": warnings_value,
    }
    return ReviewWorkspaceExecutionReport(
        **body,
        content_address=_address(body, "review-workspace-execution"),
    )


def _transition_allowed(
    status: ReviewPlanExecutionStatus,
    kind: ReviewPlanExecutionEventKind,
) -> bool:
    if kind is ReviewPlanExecutionEventKind.START:
        return status is ReviewPlanExecutionStatus.OPEN
    if kind is ReviewPlanExecutionEventKind.COMPLETE:
        return status in {ReviewPlanExecutionStatus.OPEN, ReviewPlanExecutionStatus.IN_PROGRESS}
    if kind is ReviewPlanExecutionEventKind.BLOCK:
        return status in {ReviewPlanExecutionStatus.OPEN, ReviewPlanExecutionStatus.IN_PROGRESS}
    if kind is ReviewPlanExecutionEventKind.SKIP:
        return status in {ReviewPlanExecutionStatus.OPEN, ReviewPlanExecutionStatus.IN_PROGRESS}
    if kind is ReviewPlanExecutionEventKind.REOPEN:
        return status in {
            ReviewPlanExecutionStatus.COMPLETED,
            ReviewPlanExecutionStatus.BLOCKED,
            ReviewPlanExecutionStatus.SKIPPED,
        }
    return False


def _status_for(kind: ReviewPlanExecutionEventKind) -> ReviewPlanExecutionStatus:
    return {
        ReviewPlanExecutionEventKind.START: ReviewPlanExecutionStatus.IN_PROGRESS,
        ReviewPlanExecutionEventKind.COMPLETE: ReviewPlanExecutionStatus.COMPLETED,
        ReviewPlanExecutionEventKind.BLOCK: ReviewPlanExecutionStatus.BLOCKED,
        ReviewPlanExecutionEventKind.SKIP: ReviewPlanExecutionStatus.SKIPPED,
        ReviewPlanExecutionEventKind.REOPEN: ReviewPlanExecutionStatus.OPEN,
    }[kind]


def _action_execution(
    action: ReviewPlanAction,
    *,
    status: ReviewPlanExecutionStatus,
    event_ids: Sequence[str],
    last_event_id: str | None,
    started_at: str | None,
    completed_at: str | None,
    reason: str,
    statuses: Mapping[str, ReviewPlanExecutionStatus],
) -> ReviewPlanActionExecution:
    unresolved = tuple(
        dependency
        for dependency in action.depends_on
        if statuses.get(dependency) is not ReviewPlanExecutionStatus.COMPLETED
    )
    ready = status is ReviewPlanExecutionStatus.OPEN and not unresolved
    body = {
        "action_id": action.action_id,
        "queue_item_id": action.queue_item_id,
        "target_id": action.target_id,
        "lane": action.lane,
        "action_kind": action.action_kind,
        "priority": action.priority,
        "status": status,
        "ready": ready,
        "unresolved_dependencies": unresolved,
        "event_ids": tuple(event_ids),
        "last_event_id": last_event_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "reason": reason,
    }
    return ReviewPlanActionExecution(
        **body,
        content_address=_address(body, "review-plan-action-execution"),
    )


def replay_review_workspace_plan_execution(
    plan: ReviewWorkspacePlan,
    events: Iterable[ReviewPlanExecutionEvent | Mapping[str, Any]] = (),
) -> ReviewWorkspaceExecutionReport:
    """Replay a transition sequence and return dependency-aware progress."""

    if not isinstance(plan, ReviewWorkspacePlan):
        raise ValidationError("execution replay requires a typed review workspace plan")
    if not plan.accepted:
        return _empty_report(
            plan,
            accepted=False,
            warnings=("review workspace plan was not accepted; execution details were withheld",),
        )
    actions = _plan_actions(plan)
    if len(actions) > REVIEW_WORKSPACE_EXECUTION_MAX_EVENTS:
        raise ValidationError("review plan action count exceeds execution capacity")
    selected_events: list[ReviewPlanExecutionEvent] = []
    statuses = {action_id: ReviewPlanExecutionStatus.OPEN for action_id in actions}
    event_ids_by_action: dict[str, list[str]] = defaultdict(list)
    last_event_by_action: dict[str, str] = {}
    started_at: dict[str, str] = {}
    completed_at: dict[str, str] = {}
    reasons: dict[str, str] = {}
    seen_event_ids: set[str] = set()
    previous_address: str | None = None
    previous_time: str | None = None
    transition_valid = True
    dependency_valid = True
    chain_valid = True
    transition_error: str | None = None
    for raw_event in events:
        event = (
            raw_event
            if isinstance(raw_event, ReviewPlanExecutionEvent)
            else review_plan_execution_event_from_mapping(_mapping(raw_event, "execution event"))
        )
        _validate_event_address(event)
        if event.event_id in seen_event_ids:
            raise ValidationError(f"duplicate execution event ID: {event.event_id}")
        seen_event_ids.add(event.event_id)
        if event.plan_id != plan.plan_id or event.plan_address != plan.content_address:
            raise ValidationError(f"execution event references a different plan: {event.event_id}")
        if event.previous_event_address != previous_address:
            chain_valid = False
            raise ValidationError(f"execution event chain does not link at {event.event_id}")
        if previous_time is not None and event.occurred_at < previous_time:
            chain_valid = False
            raise ValidationError(f"execution event time moved backward at {event.event_id}")
        previous_address = event.content_address
        previous_time = event.occurred_at
        if event.action_id not in actions:
            raise ValidationError(f"execution event names unknown action: {event.action_id}")
        action = actions[event.action_id]
        current = statuses[event.action_id]
        if not _transition_allowed(current, event.kind):
            transition_valid = False
            transition_error = (
                f"transition {event.kind.value} is not allowed from {current.value} "
                f"for {event.action_id}"
            )
            raise ValidationError(transition_error)
        if event.kind in {ReviewPlanExecutionEventKind.BLOCK, ReviewPlanExecutionEventKind.SKIP, ReviewPlanExecutionEventKind.REOPEN} and not event.reason:
            raise ValidationError(f"execution event {event.kind.value} requires a reason")
        if event.kind is ReviewPlanExecutionEventKind.COMPLETE:
            missing = tuple(
                dependency
                for dependency in action.depends_on
                if statuses[dependency] is not ReviewPlanExecutionStatus.COMPLETED
            )
            if missing:
                dependency_valid = False
                raise ValidationError(
                    f"cannot complete {action.action_id}; dependencies are not complete: {', '.join(missing)}"
                )
            missing_checks = tuple(
                check_id for check_id in action.required_checks if check_id not in event.check_ids
            )
            if missing_checks:
                dependency_valid = False
                raise ValidationError(
                    f"cannot complete {action.action_id}; required checks are not recorded: {', '.join(missing_checks)}"
                )
        statuses[event.action_id] = _status_for(event.kind)
        event_ids_by_action[event.action_id].append(event.event_id)
        last_event_by_action[event.action_id] = event.event_id
        if event.kind is ReviewPlanExecutionEventKind.START:
            started_at.setdefault(event.action_id, event.occurred_at)
        elif event.kind is ReviewPlanExecutionEventKind.COMPLETE:
            completed_at[event.action_id] = event.occurred_at
        elif event.kind is ReviewPlanExecutionEventKind.REOPEN:
            started_at.pop(event.action_id, None)
            completed_at.pop(event.action_id, None)
        if event.reason:
            reasons[event.action_id] = event.reason
        selected_events.append(event)
        if len(selected_events) > REVIEW_WORKSPACE_EXECUTION_MAX_EVENTS:
            raise ValidationError("execution event count exceeds the bound")

    action_rows = tuple(
        _action_execution(
            action,
            status=statuses[action_id],
            event_ids=event_ids_by_action.get(action_id, ()),
            last_event_id=last_event_by_action.get(action_id),
            started_at=started_at.get(action_id),
            completed_at=completed_at.get(action_id),
            reason=reasons.get(action_id, ""),
            statuses=statuses,
        )
        for action_id, action in sorted(actions.items(), key=lambda item: item[1].sequence)
    )
    next_actions = tuple(
        item.action_id for item in action_rows if item.ready
    )
    blocked_actions = tuple(
        item.action_id for item in action_rows if item.status is ReviewPlanExecutionStatus.BLOCKED
    )
    counts = {
        status.value: sum(item.status is status for item in action_rows)
        for status in ReviewPlanExecutionStatus
    }
    dependency_wait_count = sum(
        bool(item.unresolved_dependencies)
        and item.status is ReviewPlanExecutionStatus.OPEN
        for item in action_rows
    )
    if not action_rows:
        state = ReviewPlanExecutionStatus.OPEN
    elif blocked_actions:
        state = ReviewPlanExecutionStatus.BLOCKED
    elif counts[ReviewPlanExecutionStatus.COMPLETED.value] == len(action_rows):
        state = ReviewPlanExecutionStatus.COMPLETED
    elif selected_events:
        state = ReviewPlanExecutionStatus.IN_PROGRESS
    else:
        state = ReviewPlanExecutionStatus.OPEN
    checks_data = (
        (
            "source:review-workspace-plan-accepted",
            True,
            plan.accepted,
            True,
            "execution requires an accepted public plan",
        ),
        (
            "execution:event-chain",
            chain_valid,
            chain_valid,
            True,
            "events link to the preceding content address in order",
        ),
        (
            "execution:transition-state",
            transition_valid,
            transition_valid,
            True,
            transition_error or "every transition is allowed by the state machine",
        ),
        (
            "execution:dependency-order",
            dependency_valid,
            dependency_valid,
            True,
            "completed actions have completed dependencies and declared checks",
        ),
        (
            "execution:public-boundary",
            not _has_forbidden(jsonable({"events": selected_events, "actions": action_rows})),
            True,
            True,
            "replayed output contains no forbidden public keys",
        ),
        (
            "execution:event-bound",
            len(selected_events) <= REVIEW_WORKSPACE_EXECUTION_MAX_EVENTS,
            len(selected_events),
            REVIEW_WORKSPACE_EXECUTION_MAX_EVENTS,
            "event count remains inside the replay bound",
        ),
    )
    checks: list[ReviewExecutionCheck] = []
    for check_id, passed, observed, expected, detail in checks_data:
        check_body = {
            "check_id": check_id,
            "passed": bool(passed),
            "required": True,
            "observed": observed,
            "expected": expected,
            "detail": detail,
        }
        checks.append(ReviewExecutionCheck(**check_body, content_address=_address(check_body, "review-execution-check")))
    accepted = plan.accepted and all(item.passed for item in checks)
    warnings = (
        "execution state is an operational projection and does not change scientific evidence",
        "completion requires explicit public check identifiers and completed dependencies",
    )
    body = {
        "execution_id": f"review-plan-execution:{plan.content_address}",
        "plan_id": plan.plan_id,
        "plan_address": plan.content_address,
        "workspace_id": plan.workspace_id,
        "run_id": plan.run_id,
        "case_id": plan.case_id,
        "version": REVIEW_WORKSPACE_EXECUTION_VERSION,
        "state": state,
        "accepted": accepted,
        "event_count": len(selected_events),
        "action_count": len(action_rows),
        "open_count": counts[ReviewPlanExecutionStatus.OPEN.value],
        "in_progress_count": counts[ReviewPlanExecutionStatus.IN_PROGRESS.value],
        "completed_count": counts[ReviewPlanExecutionStatus.COMPLETED.value],
        "blocked_count": counts[ReviewPlanExecutionStatus.BLOCKED.value],
        "skipped_count": counts[ReviewPlanExecutionStatus.SKIPPED.value],
        "dependency_wait_count": dependency_wait_count,
        "next_action_ids": next_actions,
        "blocked_action_ids": blocked_actions,
        "events": tuple(selected_events),
        "actions": action_rows,
        "checks": tuple(checks),
        "warnings": warnings,
    }
    return ReviewWorkspaceExecutionReport(
        **body,
        content_address=_address(body, "review-workspace-execution"),
    )


def _ledger_digest(plan: ReviewWorkspacePlan) -> str:
    prefix, _, digest = plan.content_address.partition(":")
    if prefix != "review-workspace-plan" or not _SAFE_DIGEST.fullmatch(digest):
        raise ValidationError("review plan address is not a safe ledger identity")
    return digest


def _safe_file(path: Path, *, directory: bool = False) -> None:
    if path.is_symlink():
        raise StoreError(f"execution ledger path is a symlink: {path}")
    if directory and path.exists() and not path.is_dir():
        raise StoreError(f"execution ledger path is not a directory: {path}")


def _canonical_event_line(event: ReviewPlanExecutionEvent) -> bytes:
    return (canonical_json(event.to_dict()) + "\n").encode("utf-8")


def _manifest_body(
    plan: ReviewWorkspacePlan,
    events: Sequence[ReviewPlanExecutionEvent],
    event_bytes: bytes,
) -> dict[str, Any]:
    return {
        "execution_version": REVIEW_WORKSPACE_EXECUTION_VERSION,
        "event_version": REVIEW_WORKSPACE_EXECUTION_EVENT_VERSION,
        "plan_id": plan.plan_id,
        "plan_address": plan.content_address,
        "workspace_id": plan.workspace_id,
        "run_id": plan.run_id,
        "case_id": plan.case_id,
        "event_count": len(events),
        "byte_count": len(event_bytes),
        "line_count": len(event_bytes.splitlines()),
        "first_event_address": events[0].content_address if events else None,
        "last_event_address": events[-1].content_address if events else None,
        "events_address": hash_bytes(event_bytes, prefix="review-plan-execution-events"),
    }


class ReviewPlanExecutionStore:
    """Filesystem store for one plan's append-only event ledger."""

    def __init__(self, data_root: str | Path) -> None:
        self.data_root = Path(data_root)
        self.root = self.data_root / REVIEW_WORKSPACE_EXECUTION_LEDGER_DIR

    def _directory(self, plan: ReviewWorkspacePlan) -> Path:
        return self.root / _ledger_digest(plan)

    def _paths(self, plan: ReviewWorkspacePlan) -> tuple[Path, Path, Path]:
        directory = self._directory(plan)
        return (
            directory,
            directory / REVIEW_WORKSPACE_EXECUTION_EVENTS_FILE,
            directory / REVIEW_WORKSPACE_EXECUTION_MANIFEST_FILE,
        )

    def read_events(self, plan: ReviewWorkspacePlan) -> tuple[ReviewPlanExecutionEvent, ...]:
        """Verify and reopen the ledger; a tampered or partial ledger fails closed."""

        directory, events_path, manifest_path = self._paths(plan)
        if not directory.exists():
            return ()
        _safe_file(directory, directory=True)
        if not events_path.is_file() or not manifest_path.is_file():
            raise StoreError("execution ledger is missing its event or manifest file")
        _safe_file(events_path)
        _safe_file(manifest_path)
        allowed = {REVIEW_WORKSPACE_EXECUTION_EVENTS_FILE, REVIEW_WORKSPACE_EXECUTION_MANIFEST_FILE}
        unexpected = {path.name for path in directory.iterdir()} - allowed
        if unexpected:
            raise StoreError(f"execution ledger has unexpected files: {sorted(unexpected)}")
        try:
            event_bytes = events_path.read_bytes()
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise StoreError(f"execution ledger is unreadable: {exc}") from exc
        if not isinstance(manifest, Mapping):
            raise StoreError("execution ledger manifest must be an object")
        events: list[ReviewPlanExecutionEvent] = []
        if event_bytes:
            if not event_bytes.endswith(b"\n"):
                raise StoreError("execution ledger event file must end with a newline")
            for line in event_bytes.splitlines():
                try:
                    raw = json.loads(line.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise StoreError(f"execution ledger contains invalid event JSON: {exc}") from exc
                if not isinstance(raw, Mapping):
                    raise StoreError("execution ledger event must be an object")
                try:
                    events.append(review_plan_execution_event_from_mapping(raw))
                except ValidationError as exc:
                    raise StoreError(f"execution ledger event failed validation: {exc}") from exc
        if len(events) > REVIEW_WORKSPACE_EXECUTION_MAX_EVENTS:
            raise StoreError("execution ledger exceeds the event bound")
        expected_manifest = _manifest_body(plan, events, event_bytes)
        for key, expected in expected_manifest.items():
            if manifest.get(key) != expected:
                raise StoreError(f"execution ledger manifest mismatch at {key}")
        expected_manifest_address = _address(expected_manifest, "review-plan-execution-manifest")
        if manifest.get("manifest_address") != expected_manifest_address:
            raise StoreError("execution ledger manifest address mismatch")
        try:
            replay_review_workspace_plan_execution(plan, events)
        except ValidationError as exc:
            raise StoreError(f"execution ledger replay failed: {exc}") from exc
        return tuple(events)

    def append(
        self,
        plan: ReviewWorkspacePlan,
        event: ReviewPlanExecutionEvent,
    ) -> ReviewWorkspaceExecutionReport:
        """Append one valid event and atomically refresh the manifest."""

        return self.append_many(plan, (event,))

    def append_many(
        self,
        plan: ReviewWorkspacePlan,
        events: Iterable[ReviewPlanExecutionEvent],
    ) -> ReviewWorkspaceExecutionReport:
        """Append a prevalidated sequence with one durable manifest refresh.

        All event, chain, duplicate-ID, replay, and capacity checks run before
        the event file is replaced.  A rejected sequence therefore leaves the
        existing event bytes and manifest untouched.
        """

        pending = tuple(events)
        existing = self.read_events(plan)
        previous = existing[-1].content_address if existing else None
        seen_event_ids = {item.event_id for item in existing}
        for event in pending:
            if event.plan_id != plan.plan_id or event.plan_address != plan.content_address:
                raise ValidationError("execution event does not belong to the supplied plan")
            _validate_event_address(event)
            if event.previous_event_address != previous:
                raise ValidationError(
                    "execution event previous address does not match the ledger tail"
                )
            if event.event_id in seen_event_ids:
                raise ValidationError("execution event ID already exists in the ledger")
            seen_event_ids.add(event.event_id)
            previous = event.content_address
        if len(existing) + len(pending) > REVIEW_WORKSPACE_EXECUTION_MAX_EVENTS:
            raise ValidationError("execution event count exceeds the bound")
        report = replay_review_workspace_plan_execution(plan, (*existing, *pending))
        directory, events_path, manifest_path = self._paths(plan)
        _safe_file(self.root, directory=True)
        self.root.mkdir(parents=True, exist_ok=True)
        directory.mkdir(parents=True, exist_ok=True)
        _safe_file(directory, directory=True)
        old_bytes = events_path.read_bytes() if events_path.exists() else b""
        new_bytes = old_bytes + b"".join(_canonical_event_line(event) for event in pending)
        temporary_events = events_path.with_suffix(".tmp")
        temporary_events.write_bytes(new_bytes)
        temporary_events.replace(events_path)
        manifest_body = _manifest_body(plan, (*existing, *pending), new_bytes)
        manifest = manifest_body | {
            "manifest_address": _address(manifest_body, "review-plan-execution-manifest")
        }
        temporary_manifest = manifest_path.with_suffix(".tmp")
        temporary_manifest.write_text(canonical_json(manifest), encoding="utf-8")
        temporary_manifest.replace(manifest_path)
        return report

    def report(self, plan: ReviewWorkspacePlan) -> ReviewWorkspaceExecutionReport:
        """Reopen the current ledger and replay it against the supplied plan."""

        return replay_review_workspace_plan_execution(plan, self.read_events(plan))


def build_persisted_review_workspace_plan_execution(
    runtime: Any,
    run_id: str,
    *,
    baseline_run_id: str | None = None,
    plan_config: Any | None = None,
    execution_store: ReviewPlanExecutionStore | None = None,
) -> ReviewWorkspaceExecutionReport:
    """Build a replayed execution report from a persisted run and local ledger."""

    from .review_workspace_plan import build_persisted_review_workspace_plan

    plan = build_persisted_review_workspace_plan(
        runtime,
        run_id,
        baseline_run_id=baseline_run_id,
        config=plan_config,
    )
    store = execution_store or ReviewPlanExecutionStore(runtime.store.root)
    return store.report(plan)


def append_persisted_review_workspace_plan_event(
    runtime: Any,
    run_id: str,
    event: ReviewPlanExecutionEvent,
    *,
    baseline_run_id: str | None = None,
    plan_config: Any | None = None,
    execution_store: ReviewPlanExecutionStore | None = None,
) -> ReviewWorkspaceExecutionReport:
    """Append an event only after rebuilding the current replay-gated plan."""

    from .review_workspace_plan import build_persisted_review_workspace_plan

    plan = build_persisted_review_workspace_plan(
        runtime,
        run_id,
        baseline_run_id=baseline_run_id,
        config=plan_config,
    )
    store = execution_store or ReviewPlanExecutionStore(runtime.store.root)
    return store.append(plan, event)


def _facet(values: Iterable[Any], key: str) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for value in values:
        item = getattr(value, key)
        normalized = item.value if isinstance(item, StrEnum) else str(item)
        counts[normalized] += 1
    return dict(sorted(counts.items()))


def _execution_action_matches(
    action: ReviewPlanActionExecution,
    event_by_action: Mapping[str, tuple[ReviewPlanExecutionEvent, ...]],
    query: ReviewWorkspaceExecutionQuery,
) -> bool:
    if query.status and action.status.value != str(query.status).strip().casefold():
        return False
    if query.lane and action.lane != str(query.lane).strip().casefold():
        return False
    if query.action_kind and action.action_kind != str(query.action_kind).strip().casefold():
        return False
    if query.action_id and action.action_id != str(query.action_id).strip():
        return False
    if query.priority is not None and action.priority != query.priority:
        return False
    events = event_by_action.get(action.action_id, ())
    if query.event_kind and not any(item.kind.value == str(query.event_kind).strip().casefold() for item in events):
        return False
    if query.text:
        haystack = " ".join(
            (
                action.action_id,
                action.queue_item_id,
                action.target_id,
                action.lane,
                action.action_kind,
                action.status.value,
                action.reason,
                *action.event_ids,
            )
        ).casefold()
        if str(query.text).casefold() not in haystack:
            return False
    return True


def query_review_workspace_execution(
    report: ReviewWorkspaceExecutionReport,
    query: ReviewWorkspaceExecutionQuery | Mapping[str, Any] | None = None,
) -> ReviewWorkspaceExecutionQueryResult:
    """Return a bounded action page and facets over the replayed execution."""

    if not isinstance(report, ReviewWorkspaceExecutionReport):
        raise ValidationError("execution query requires a typed execution report")
    selected = query if isinstance(query, ReviewWorkspaceExecutionQuery) else ReviewWorkspaceExecutionQuery.from_mapping(query)
    events_by_action: dict[str, list[ReviewPlanExecutionEvent]] = defaultdict(list)
    for event in report.events:
        events_by_action[event.action_id].append(event)
    matched = tuple(
        action
        for action in report.actions
        if _execution_action_matches(action, events_by_action, selected)
    )
    page = matched[selected.offset:] if selected.limit is None else matched[selected.offset : selected.offset + selected.limit]
    body = {
        "execution_address": report.content_address,
        "query": selected,
        "rows": page,
        "total_count": len(matched),
        "has_more": selected.offset + len(page) < len(matched),
        "facets": {
            "statuses": _facet(matched, "status"),
            "lanes": _facet(matched, "lane"),
            "action_kinds": _facet(matched, "action_kind"),
            "priorities": _facet(matched, "priority"),
        },
        "accepted": report.accepted,
        "warnings": report.warnings,
    }
    return ReviewWorkspaceExecutionQueryResult(
        execution_address=report.content_address,
        query=selected,
        rows=page,
        total_count=len(matched),
        has_more=selected.offset + len(page) < len(matched),
        facets=body["facets"],
        accepted=report.accepted,
        warnings=report.warnings,
        content_address=_address(body, "review-workspace-execution-query"),
    )


def review_workspace_execution_schema() -> dict[str, Any]:
    """Return the machine-readable execution contract."""

    return {
        "version": REVIEW_WORKSPACE_EXECUTION_SCHEMA_VERSION,
        "execution_version": REVIEW_WORKSPACE_EXECUTION_VERSION,
        "event_version": REVIEW_WORKSPACE_EXECUTION_EVENT_VERSION,
        "statuses": [item.value for item in ReviewPlanExecutionStatus],
        "event_kinds": [item.value for item in ReviewPlanExecutionEventKind],
        "transition_rules": {
            "start": ["open"],
            "complete": ["open", "in_progress"],
            "block": ["open", "in_progress"],
            "skip": ["open", "in_progress"],
            "reopen": ["completed", "blocked", "skipped"],
        },
        "completion_requirements": [
            "accepted review workspace plan",
            "all declared action dependencies completed",
            "all declared action required_checks named in the completion event",
            "valid event chain and public boundary",
        ],
        "storage": {
            "directory": REVIEW_WORKSPACE_EXECUTION_LEDGER_DIR,
            "events_file": REVIEW_WORKSPACE_EXECUTION_EVENTS_FILE,
            "manifest_file": REVIEW_WORKSPACE_EXECUTION_MANIFEST_FILE,
            "append_only": True,
            "exact_byte_manifest": True,
        },
        "boundary": [
            "events store public action and check references only",
            "raw evidence payloads are never stored",
            "reviewer, agent, assistant, model, programming-language, private, subject, and contact keys are rejected",
            "execution progress is not a scientific decision or an aggregate evidence score",
        ],
        "limits": {
            "max_events": REVIEW_WORKSPACE_EXECUTION_MAX_EVENTS,
            "max_reason": REVIEW_WORKSPACE_EXECUTION_MAX_REASON,
            "max_references": REVIEW_WORKSPACE_EXECUTION_MAX_REFERENCES,
        },
        "query_views": ["actions", "events", "metrics"],
        "event_timeline": {
            "schema_version": "review-workspace-execution-timeline-schema-v1",
            "query_version": "review-workspace-execution-timeline-query-v1",
            "ordering": "ascending zero-based ledger sequence",
            "facets": ["kinds", "action_ids", "check_ids", "reference_addresses"],
            "replay_projection_only": True,
        },
        "metrics_projection": {
            "schema_version": "review-workspace-execution-metrics-schema-v1",
            "derived_from": ["typed_source_plan", "replay_verified_report"],
            "integer_basis_points": True,
        },
    }


def review_workspace_execution_capabilities() -> dict[str, Any]:
    """Return execution capabilities without case-specific rows."""

    return {
        "version": REVIEW_WORKSPACE_EXECUTION_VERSION,
        "append_only_events": True,
        "hash_chained_replay": True,
        "dependency_aware_completion": True,
        "required_check_confirmation": True,
        "reopen_and_recovery": True,
        "exact_byte_manifest_verification": True,
        "bounded_queries_and_facets": True,
        "event_timeline_query": True,
        "sequence_aware_pagination": True,
        "event_check_and_reference_facets": True,
        "metrics_projection": True,
        "deterministic_exports": True,
        "cli_write_surface": True,
        "api_read_surface": True,
        "public_boundary": {
            "raw_payloads": False,
            "reviewer_identity": False,
            "agent_identity": False,
            "model_metadata": False,
            "programming_language_metadata": False,
            "scientific_decision": False,
        },
    }


__all__ = [
    "REVIEW_WORKSPACE_EXECUTION_EVENT_VERSION",
    "REVIEW_WORKSPACE_EXECUTION_EVENTS_FILE",
    "REVIEW_WORKSPACE_EXECUTION_LEDGER_DIR",
    "REVIEW_WORKSPACE_EXECUTION_MANIFEST_FILE",
    "REVIEW_WORKSPACE_EXECUTION_MAX_EVENTS",
    "REVIEW_WORKSPACE_EXECUTION_MAX_REASON",
    "REVIEW_WORKSPACE_EXECUTION_MAX_REFERENCES",
    "REVIEW_WORKSPACE_EXECUTION_SCHEMA_VERSION",
    "REVIEW_WORKSPACE_EXECUTION_VERSION",
    "ReviewExecutionCheck",
    "ReviewPlanActionExecution",
    "ReviewPlanExecutionEvent",
    "ReviewPlanExecutionEventKind",
    "ReviewPlanExecutionStatus",
    "ReviewPlanExecutionStore",
    "ReviewWorkspaceExecutionQuery",
    "ReviewWorkspaceExecutionQueryResult",
    "ReviewWorkspaceExecutionReport",
    "append_persisted_review_workspace_plan_event",
    "build_persisted_review_workspace_plan_execution",
    "build_review_plan_execution_event",
    "query_review_workspace_execution",
    "replay_review_workspace_plan_execution",
    "review_plan_execution_event_from_mapping",
    "review_workspace_execution_report_from_mapping",
    "review_workspace_execution_capabilities",
    "review_workspace_execution_schema",
]
