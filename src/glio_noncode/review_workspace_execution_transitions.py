"""Deterministic transition frontier for review-plan execution.

The execution ledger records transitions, while the operations projection ranks
the work that deserves attention.  This module closes the gap between those
two views: it describes every transition that is structurally possible for
every planned action and explains the additional information required before
an event can be appended.

The frontier is intentionally a read-only projection.  It never appends an
event, mutates a plan, assigns a reviewer, or turns evidence into a scientific
decision.  It is useful for clients that need a safe preflight before calling
the explicit event-writing command.  All rows are deterministic, bounded,
content-addressed, and checked for the public boundary.
"""

from __future__ import annotations

import csv
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from io import StringIO
from typing import Any

from .errors import ValidationError
from .module_fabric_support import contains_private_key
from .review_workspace_execution import (
    ReviewPlanExecutionEvent,
    ReviewPlanExecutionEventKind,
    ReviewPlanExecutionStatus,
    ReviewPlanActionExecution,
    ReviewWorkspaceExecutionReport,
    replay_review_workspace_plan_execution,
)
from .review_workspace_plan import ReviewPlanAction, ReviewWorkspacePlan
from .serialization import canonical_json, content_hash, jsonable


REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_VERSION = "review-workspace-execution-transitions-v1"
REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_SCHEMA_VERSION = (
    "review-workspace-execution-transitions-schema-v1"
)
REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_QUERY_VERSION = (
    "review-workspace-execution-transitions-query-v1"
)
REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_DIFF_VERSION = (
    "review-workspace-execution-transitions-diff-v1"
)
REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_DIFF_SCHEMA_VERSION = (
    "review-workspace-execution-transitions-diff-schema-v1"
)
REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_MAX_ACTIONS = 20_000
REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_MAX_OPTIONS = 100_000
REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_MAX_TEXT = 256
REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_DEFAULT_LIMIT = 50
REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_MAX_LIMIT = 500
REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_MAX_VALUES = 32


class ReviewWorkspaceExecutionTransitionDisposition(StrEnum):
    """Why a transition is or is not appendable right now."""

    AVAILABLE = "available"
    REQUIRES_REASON = "requires_reason"
    REQUIRES_CHECKS = "requires_checks"
    WAITING_DEPENDENCIES = "waiting_dependencies"
    NOT_ALLOWED = "not_allowed"


_EVENT_KINDS = tuple(ReviewPlanExecutionEventKind)
_EVENT_KIND_VALUES = {item.value for item in _EVENT_KINDS}
_STATUS_VALUES = {item.value for item in ReviewPlanExecutionStatus}
_DISPOSITION_VALUES = {item.value for item in ReviewWorkspaceExecutionTransitionDisposition}
_REASON_KINDS = frozenset(
    {
        ReviewPlanExecutionEventKind.BLOCK,
        ReviewPlanExecutionEventKind.SKIP,
        ReviewPlanExecutionEventKind.REOPEN,
    }
)
_DEPENDENCY_KINDS = frozenset(
    {ReviewPlanExecutionEventKind.START, ReviewPlanExecutionEventKind.COMPLETE}
)
_KIND_ORDER = {
    ReviewPlanExecutionEventKind.START: 0,
    ReviewPlanExecutionEventKind.COMPLETE: 1,
    ReviewPlanExecutionEventKind.BLOCK: 2,
    ReviewPlanExecutionEventKind.SKIP: 3,
    ReviewPlanExecutionEventKind.REOPEN: 4,
}

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


def _text(value: Any, field: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValidationError(f"{field} must not be empty")
    return normalized


def _optional_text(value: Any, field: str) -> str | None:
    if value in (None, ""):
        return None
    return _text(value, field)


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return {str(key): item for key, item in value.items()}


def _text_sequence(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValidationError(f"{field} must be an array")
    result = tuple(_text(item, f"{field}[]") for item in value)
    if len(set(result)) != len(result):
        raise ValidationError(f"{field} must not contain duplicates")
    return result


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


def _address(value: Any, prefix: str) -> str:
    return content_hash(_public(value), prefix=prefix)


def _address_without_content(body: Mapping[str, Any], prefix: str, field: str) -> str:
    address = _text(body.get("content_address"), field)
    source = {key: item for key, item in body.items() if key != "content_address"}
    if _address(source, prefix) != address:
        raise ValidationError(f"{field} address mismatch")
    return address


def _status(value: Any, field: str) -> ReviewPlanExecutionStatus:
    try:
        return ReviewPlanExecutionStatus(_text(value, field))
    except ValueError as exc:
        raise ValidationError(f"{field} is invalid") from exc


def _kind(value: Any, field: str) -> ReviewPlanExecutionEventKind:
    try:
        return ReviewPlanExecutionEventKind(_text(value, field))
    except ValueError as exc:
        raise ValidationError(f"{field} is invalid") from exc


def _disposition(value: Any, field: str) -> ReviewWorkspaceExecutionTransitionDisposition:
    try:
        return ReviewWorkspaceExecutionTransitionDisposition(_text(value, field))
    except ValueError as exc:
        raise ValidationError(f"{field} is invalid") from exc


def _allowed(status: ReviewPlanExecutionStatus, kind: ReviewPlanExecutionEventKind) -> bool:
    """Mirror the append-only state machine without exposing a private helper."""

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


def _resulting_status(kind: ReviewPlanExecutionEventKind) -> ReviewPlanExecutionStatus:
    return {
        ReviewPlanExecutionEventKind.START: ReviewPlanExecutionStatus.IN_PROGRESS,
        ReviewPlanExecutionEventKind.COMPLETE: ReviewPlanExecutionStatus.COMPLETED,
        ReviewPlanExecutionEventKind.BLOCK: ReviewPlanExecutionStatus.BLOCKED,
        ReviewPlanExecutionEventKind.SKIP: ReviewPlanExecutionStatus.SKIPPED,
        ReviewPlanExecutionEventKind.REOPEN: ReviewPlanExecutionStatus.OPEN,
    }[kind]


def _transition_id(action_id: str, kind: ReviewPlanExecutionEventKind) -> str:
    return f"review-execution-transition:{action_id}:{kind.value}"


def _rationale(
    kind: ReviewPlanExecutionEventKind,
    disposition: ReviewWorkspaceExecutionTransitionDisposition,
    action: ReviewPlanActionExecution,
    missing_dependencies: tuple[str, ...],
    required_checks: tuple[str, ...],
) -> str:
    if disposition is ReviewWorkspaceExecutionTransitionDisposition.NOT_ALLOWED:
        return f"{kind.value} is not allowed from the current {action.status.value} state"
    if disposition is ReviewWorkspaceExecutionTransitionDisposition.WAITING_DEPENDENCIES:
        joined = ", ".join(missing_dependencies)
        return f"complete declared dependencies before {kind.value}: {joined}"
    if disposition is ReviewWorkspaceExecutionTransitionDisposition.REQUIRES_CHECKS:
        joined = ", ".join(required_checks)
        return f"record required public checks on the {kind.value} event: {joined}"
    if disposition is ReviewWorkspaceExecutionTransitionDisposition.REQUIRES_REASON:
        return f"supply a bounded public reason before appending {kind.value}"
    if kind is ReviewPlanExecutionEventKind.START:
        return "action is open and dependency-ready; a start event may be appended"
    if kind is ReviewPlanExecutionEventKind.COMPLETE:
        return "action is eligible to complete once its declared checks are supplied"
    return f"{kind.value} may be appended from the current action state"


def _recommended_kind(action: ReviewPlanActionExecution) -> ReviewPlanExecutionEventKind | None:
    if action.status in {
        ReviewPlanExecutionStatus.COMPLETED,
        ReviewPlanExecutionStatus.BLOCKED,
        ReviewPlanExecutionStatus.SKIPPED,
    }:
        return ReviewPlanExecutionEventKind.REOPEN
    if action.status is ReviewPlanExecutionStatus.IN_PROGRESS:
        return ReviewPlanExecutionEventKind.COMPLETE
    if action.ready:
        return ReviewPlanExecutionEventKind.START
    return ReviewPlanExecutionEventKind.START


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionTransitionOption:
    """One possible event transition and its append preconditions."""

    transition_id: str
    action_id: str
    kind: ReviewPlanExecutionEventKind
    from_status: ReviewPlanExecutionStatus
    to_status: ReviewPlanExecutionStatus
    disposition: ReviewWorkspaceExecutionTransitionDisposition
    allowed_by_state: bool
    executable_without_additional_input: bool
    permitted: bool
    ready: bool
    priority: int
    sequence: int
    lane: str
    action_kind: str
    last_event_id: str | None
    previous_event_address: str | None
    required_check_ids: tuple[str, ...]
    missing_dependency_ids: tuple[str, ...]
    requires_reason: bool
    rationale: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionTransitionAction:
    """All transition options for one action, in event-kind order."""

    action_id: str
    queue_item_id: str
    target_id: str
    title: str
    purpose: str
    lane: str
    action_kind: str
    priority: int
    sequence: int
    status: ReviewPlanExecutionStatus
    ready: bool
    unresolved_dependencies: tuple[str, ...]
    last_event_id: str | None
    previous_event_address: str | None
    recommended_transition_id: str | None
    recommended_kind: ReviewPlanExecutionEventKind | None
    options: tuple[ReviewWorkspaceExecutionTransitionOption, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionTransitions:
    """Complete deterministic transition frontier for an execution report."""

    execution_id: str
    execution_address: str
    plan_id: str
    plan_address: str
    workspace_id: str
    run_id: str
    case_id: str
    version: str
    state: str
    accepted: bool
    action_count: int
    option_count: int
    executable_option_count: int
    permitted_option_count: int
    requires_reason_count: int
    requires_checks_count: int
    waiting_dependency_count: int
    not_allowed_count: int
    ready_action_ids: tuple[str, ...]
    completion_ready_action_ids: tuple[str, ...]
    blocked_action_ids: tuple[str, ...]
    recommended_action_ids: tuple[str, ...]
    recommended_transition_ids: tuple[str, ...]
    status_counts: Mapping[str, int]
    transition_counts: Mapping[str, int]
    disposition_counts: Mapping[str, int]
    actions: tuple[ReviewWorkspaceExecutionTransitionAction, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        body = {
            "transitions_version": REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_VERSION,
            "execution_id": self.execution_id,
            "execution_address": self.execution_address,
            "plan_id": self.plan_id,
            "plan_address": self.plan_address,
            "workspace_id": self.workspace_id,
            "run_id": self.run_id,
            "case_id": self.case_id,
            "version": self.version,
            "state": self.state,
            "accepted": self.accepted,
            "action_count": self.action_count,
            "option_count": self.option_count,
            "executable_option_count": self.executable_option_count,
            "permitted_option_count": self.permitted_option_count,
            "requires_reason_count": self.requires_reason_count,
            "requires_checks_count": self.requires_checks_count,
            "waiting_dependency_count": self.waiting_dependency_count,
            "not_allowed_count": self.not_allowed_count,
            "ready_action_ids": self.ready_action_ids,
            "completion_ready_action_ids": self.completion_ready_action_ids,
            "blocked_action_ids": self.blocked_action_ids,
            "recommended_action_ids": self.recommended_action_ids,
            "recommended_transition_ids": self.recommended_transition_ids,
            "status_counts": self.status_counts,
            "transition_counts": self.transition_counts,
            "disposition_counts": self.disposition_counts,
            "actions": self.actions,
            "warnings": self.warnings,
            "content_address": self.content_address,
        }
        return jsonable(body)


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionTransitionsQuery:
    """Bounded filters over transition options."""

    action_id: str | None = None
    kind: str | None = None
    disposition: str | None = None
    status: str | None = None
    lane: str | None = None
    action_kind: str | None = None
    priorities: tuple[int, ...] = ()
    executable: bool | None = None
    permitted: bool | None = None
    text: str | None = None
    offset: int = 0
    limit: int | None = REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_DEFAULT_LIMIT

    def __post_init__(self) -> None:
        for field_name in ("action_id", "kind", "disposition", "status", "lane", "action_kind"):
            value = getattr(self, field_name)
            if value is not None and not str(value).strip():
                raise ValidationError(f"transition query {field_name} must not be blank")
        if self.kind is not None and str(self.kind).strip().casefold() not in _EVENT_KIND_VALUES:
            raise ValidationError("transition query kind is invalid")
        if self.disposition is not None and str(self.disposition).strip().casefold() not in _DISPOSITION_VALUES:
            raise ValidationError("transition query disposition is invalid")
        if self.status is not None and str(self.status).strip().casefold() not in _STATUS_VALUES:
            raise ValidationError("transition query status is invalid")
        if len(self.priorities) > REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_MAX_VALUES:
            raise ValidationError("transition query priorities exceed the bound")
        normalized_priorities = tuple(sorted({int(value) for value in self.priorities}))
        if any(value not in {0, 1, 2, 3} for value in normalized_priorities):
            raise ValidationError("transition query priorities must be between 0 and 3")
        object.__setattr__(self, "priorities", normalized_priorities)
        if self.text is not None:
            normalized_text = str(self.text).strip()
            if len(normalized_text) > REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_MAX_TEXT:
                raise ValidationError("transition query text exceeds the bound")
            object.__setattr__(self, "text", normalized_text or None)
        if self.offset < 0:
            raise ValidationError("transition query offset must be non-negative")
        if self.limit is not None and (
            self.limit < 1 or self.limit > REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_MAX_LIMIT
        ):
            raise ValidationError("transition query limit is outside the bound")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> "ReviewWorkspaceExecutionTransitionsQuery":
        if raw is None:
            return cls()
        if not isinstance(raw, Mapping):
            raise ValidationError("transition query must be an object")
        priorities = raw.get("priorities", ())
        if isinstance(priorities, (str, bytes)) or not isinstance(priorities, (list, tuple)):
            raise ValidationError("transition query priorities must be an array")
        return cls(
            action_id=raw.get("action_id"),
            kind=raw.get("kind"),
            disposition=raw.get("disposition"),
            status=raw.get("status"),
            lane=raw.get("lane"),
            action_kind=raw.get("action_kind"),
            priorities=tuple(int(value) for value in priorities),
            executable=_optional_bool(raw.get("executable"), "transition query executable"),
            permitted=_optional_bool(raw.get("permitted"), "transition query permitted"),
            text=raw.get("text"),
            offset=int(raw.get("offset", 0)),
            limit=(
                None
                if raw.get("limit") is None
                else int(raw.get("limit", REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_DEFAULT_LIMIT))
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionTransitionsQueryResult:
    """A bounded transition page with complete-match facets."""

    execution_address: str
    query: ReviewWorkspaceExecutionTransitionsQuery
    rows: tuple[ReviewWorkspaceExecutionTransitionOption, ...]
    total_count: int
    has_more: bool
    facets: Mapping[str, Mapping[str, int]]
    accepted: bool
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionTransitionActionDiff:
    """Per-action frontier movement between two execution snapshots."""

    action_id: str
    left_status: str | None
    right_status: str | None
    left_ready: bool | None
    right_ready: bool | None
    left_recommended_transition_id: str | None
    right_recommended_transition_id: str | None
    left_option_count: int
    right_option_count: int
    changed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionTransitionsDiff:
    """Deterministic option, action, and aggregate frontier comparison."""

    left_execution_address: str
    right_execution_address: str
    added_transition_ids: tuple[str, ...]
    removed_transition_ids: tuple[str, ...]
    changed_transition_ids: tuple[str, ...]
    unchanged_transition_ids: tuple[str, ...]
    action_diffs: tuple[ReviewWorkspaceExecutionTransitionActionDiff, ...]
    count_deltas: Mapping[str, int]
    recommendation_changed: bool
    left_recommended_transition_ids: tuple[str, ...]
    right_recommended_transition_ids: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _optional_bool(value: Any, field: str) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().casefold()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValidationError(f"{field} must be boolean")


def _event_map(report: ReviewWorkspaceExecutionReport) -> dict[str, ReviewPlanExecutionEvent]:
    result: dict[str, ReviewPlanExecutionEvent] = {}
    for event in report.events:
        if event.event_id in result:
            raise ValidationError(f"execution transition input has duplicate event: {event.event_id}")
        result[event.event_id] = event
    return result


def _last_events(
    report: ReviewWorkspaceExecutionReport,
) -> dict[str, ReviewPlanExecutionEvent]:
    result: dict[str, ReviewPlanExecutionEvent] = {}
    for event in report.events:
        result[event.action_id] = event
    return result


def _option(
    action: ReviewPlanAction,
    execution: ReviewPlanActionExecution,
    kind: ReviewPlanExecutionEventKind,
    last_event: ReviewPlanExecutionEvent | None,
) -> ReviewWorkspaceExecutionTransitionOption:
    allowed = _allowed(execution.status, kind)
    missing_dependencies = (
        execution.unresolved_dependencies if kind in _DEPENDENCY_KINDS else ()
    )
    required_checks = action.required_checks if kind is ReviewPlanExecutionEventKind.COMPLETE else ()
    requires_reason = kind in _REASON_KINDS
    if not allowed:
        disposition = ReviewWorkspaceExecutionTransitionDisposition.NOT_ALLOWED
    elif missing_dependencies:
        disposition = ReviewWorkspaceExecutionTransitionDisposition.WAITING_DEPENDENCIES
    elif required_checks:
        disposition = ReviewWorkspaceExecutionTransitionDisposition.REQUIRES_CHECKS
    elif requires_reason:
        disposition = ReviewWorkspaceExecutionTransitionDisposition.REQUIRES_REASON
    else:
        disposition = ReviewWorkspaceExecutionTransitionDisposition.AVAILABLE
    permitted = allowed
    executable = allowed and disposition is ReviewWorkspaceExecutionTransitionDisposition.AVAILABLE
    body = {
        "transition_id": _transition_id(action.action_id, kind),
        "action_id": action.action_id,
        "kind": kind,
        "from_status": execution.status,
        "to_status": _resulting_status(kind),
        "disposition": disposition,
        "allowed_by_state": allowed,
        "executable_without_additional_input": executable,
        "permitted": permitted,
        "ready": execution.ready,
        "priority": action.priority,
        "sequence": action.sequence,
        "lane": action.lane,
        "action_kind": action.action_kind,
        "last_event_id": None if last_event is None else last_event.event_id,
        "previous_event_address": None if last_event is None else last_event.content_address,
        "required_check_ids": required_checks,
        "missing_dependency_ids": missing_dependencies,
        "requires_reason": requires_reason,
        "rationale": _rationale(kind, disposition, execution, missing_dependencies, required_checks),
    }
    if contains_private_key(body):
        raise ValidationError("execution transition option failed the public boundary")
    return ReviewWorkspaceExecutionTransitionOption(
        **body,
        content_address=_address(body, "review-workspace-execution-transition-option"),
    )


def _action_frontier(
    action: ReviewPlanAction,
    execution: ReviewPlanActionExecution,
    last_event: ReviewPlanExecutionEvent | None,
) -> ReviewWorkspaceExecutionTransitionAction:
    options = tuple(
        _option(action, execution, kind, last_event)
        for kind in sorted(_EVENT_KINDS, key=lambda item: _KIND_ORDER[item])
    )
    recommended_kind = _recommended_kind(execution)
    recommended = next(
        (item for item in options if item.kind is recommended_kind),
        None,
    )
    body = {
        "action_id": action.action_id,
        "queue_item_id": action.queue_item_id,
        "target_id": action.target_id,
        "title": action.title,
        "purpose": action.purpose,
        "lane": action.lane,
        "action_kind": action.action_kind,
        "priority": action.priority,
        "sequence": action.sequence,
        "status": execution.status,
        "ready": execution.ready,
        "unresolved_dependencies": execution.unresolved_dependencies,
        "last_event_id": None if last_event is None else last_event.event_id,
        "previous_event_address": None if last_event is None else last_event.content_address,
        "recommended_transition_id": None if recommended is None else recommended.transition_id,
        "recommended_kind": recommended_kind,
        "options": options,
    }
    if contains_private_key(body):
        raise ValidationError("execution transition action failed the public boundary")
    return ReviewWorkspaceExecutionTransitionAction(
        **body,
        content_address=_address(body, "review-workspace-execution-transition-action"),
    )


def build_review_workspace_execution_transitions(
    plan: ReviewWorkspacePlan,
    report: ReviewWorkspaceExecutionReport,
) -> ReviewWorkspaceExecutionTransitions:
    """Build the complete transition frontier from a replay-verified report."""

    if not isinstance(plan, ReviewWorkspacePlan):
        raise ValidationError("execution transitions require a typed source plan")
    if not isinstance(report, ReviewWorkspaceExecutionReport):
        raise ValidationError("execution transitions require a typed execution report")
    if not plan.accepted or not report.accepted:
        raise ValidationError("execution transitions require accepted plan and report")
    if plan.plan_id != report.plan_id or plan.content_address != report.plan_address:
        raise ValidationError("execution transitions plan and report addresses differ")
    replayed = replay_review_workspace_plan_execution(plan, report.events)
    if replayed.to_dict() != report.to_dict():
        raise ValidationError("execution transitions report does not replay against the plan")
    if len(plan.actions) > REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_MAX_ACTIONS:
        raise ValidationError("execution transition action count exceeds the bound")
    if len(report.actions) != len(plan.actions):
        raise ValidationError("execution transition action closure differs from the plan")
    plan_by_id = {item.action_id: item for item in plan.actions}
    execution_by_id = {item.action_id: item for item in report.actions}
    if set(plan_by_id) != set(execution_by_id):
        raise ValidationError("execution transition action IDs differ between plan and report")
    if len(execution_by_id) != len(report.actions):
        raise ValidationError("execution transition report contains duplicate action IDs")
    _event_map(report)
    last_events = _last_events(report)
    actions = tuple(
        _action_frontier(
            plan_by_id[action_id],
            execution_by_id[action_id],
            last_events.get(action_id),
        )
        for action_id in sorted(plan_by_id, key=lambda item: plan_by_id[item].sequence)
    )
    options = tuple(item for action in actions for item in action.options)
    if len(options) > REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_MAX_OPTIONS:
        raise ValidationError("execution transition option count exceeds the bound")
    by_kind = Counter(item.kind.value for item in options)
    by_disposition = Counter(item.disposition.value for item in options)
    status_counts = Counter(item.status.value for item in actions)
    ready_ids = tuple(item.action_id for item in actions if item.ready)
    completion_ready_ids = tuple(
        item.action_id
        for item in actions
        if any(
            option.kind is ReviewPlanExecutionEventKind.COMPLETE
            and option.allowed_by_state
            and not option.missing_dependency_ids
            for option in item.options
        )
    )
    blocked_ids = tuple(
        item.action_id
        for item in actions
        if item.status is ReviewPlanExecutionStatus.BLOCKED
    )
    recommended_ids = tuple(
        item.action_id for item in actions if item.recommended_transition_id is not None
    )
    recommended_transition_ids = tuple(
        item.recommended_transition_id
        for item in actions
        if item.recommended_transition_id is not None
    )
    body = {
        "transitions_version": REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_VERSION,
        "execution_id": report.execution_id,
        "execution_address": report.content_address,
        "plan_id": plan.plan_id,
        "plan_address": plan.content_address,
        "workspace_id": report.workspace_id,
        "run_id": report.run_id,
        "case_id": report.case_id,
        "version": report.version,
        "state": report.state.value,
        "accepted": report.accepted,
        "action_count": len(actions),
        "option_count": len(options),
        "executable_option_count": sum(item.executable_without_additional_input for item in options),
        "permitted_option_count": sum(item.permitted for item in options),
        "requires_reason_count": by_disposition[ReviewWorkspaceExecutionTransitionDisposition.REQUIRES_REASON.value],
        "requires_checks_count": by_disposition[ReviewWorkspaceExecutionTransitionDisposition.REQUIRES_CHECKS.value],
        "waiting_dependency_count": by_disposition[ReviewWorkspaceExecutionTransitionDisposition.WAITING_DEPENDENCIES.value],
        "not_allowed_count": by_disposition[ReviewWorkspaceExecutionTransitionDisposition.NOT_ALLOWED.value],
        "ready_action_ids": ready_ids,
        "completion_ready_action_ids": completion_ready_ids,
        "blocked_action_ids": blocked_ids,
        "recommended_action_ids": recommended_ids,
        "recommended_transition_ids": recommended_transition_ids,
        "status_counts": dict(sorted(status_counts.items())),
        "transition_counts": dict(sorted(by_kind.items())),
        "disposition_counts": dict(sorted(by_disposition.items())),
        "actions": actions,
        "warnings": report.warnings,
    }
    if contains_private_key(body):
        raise ValidationError("execution transitions failed the public boundary")
    return ReviewWorkspaceExecutionTransitions(
        execution_id=report.execution_id,
        execution_address=report.content_address,
        plan_id=plan.plan_id,
        plan_address=plan.content_address,
        workspace_id=report.workspace_id,
        run_id=report.run_id,
        case_id=report.case_id,
        version=report.version,
        state=report.state.value,
        accepted=report.accepted,
        action_count=len(actions),
        option_count=len(options),
        executable_option_count=sum(item.executable_without_additional_input for item in options),
        permitted_option_count=sum(item.permitted for item in options),
        requires_reason_count=by_disposition[ReviewWorkspaceExecutionTransitionDisposition.REQUIRES_REASON.value],
        requires_checks_count=by_disposition[ReviewWorkspaceExecutionTransitionDisposition.REQUIRES_CHECKS.value],
        waiting_dependency_count=by_disposition[ReviewWorkspaceExecutionTransitionDisposition.WAITING_DEPENDENCIES.value],
        not_allowed_count=by_disposition[ReviewWorkspaceExecutionTransitionDisposition.NOT_ALLOWED.value],
        ready_action_ids=ready_ids,
        completion_ready_action_ids=completion_ready_ids,
        blocked_action_ids=blocked_ids,
        recommended_action_ids=recommended_ids,
        recommended_transition_ids=recommended_transition_ids,
        status_counts=dict(sorted(status_counts.items())),
        transition_counts=dict(sorted(by_kind.items())),
        disposition_counts=dict(sorted(by_disposition.items())),
        actions=actions,
        warnings=report.warnings,
        content_address=_address(body, "review-workspace-execution-transitions"),
    )


def _option_from_mapping(value: Any) -> ReviewWorkspaceExecutionTransitionOption:
    body = _mapping(value, "execution transition option")
    option = ReviewWorkspaceExecutionTransitionOption(
        transition_id=_text(body.get("transition_id"), "transition.transition_id"),
        action_id=_text(body.get("action_id"), "transition.action_id"),
        kind=_kind(body.get("kind"), "transition.kind"),
        from_status=_status(body.get("from_status"), "transition.from_status"),
        to_status=_status(body.get("to_status"), "transition.to_status"),
        disposition=_disposition(body.get("disposition"), "transition.disposition"),
        allowed_by_state=bool(body.get("allowed_by_state")),
        executable_without_additional_input=bool(body.get("executable_without_additional_input")),
        permitted=bool(body.get("permitted")),
        ready=bool(body.get("ready")),
        priority=int(body.get("priority")),
        sequence=int(body.get("sequence")),
        lane=_text(body.get("lane"), "transition.lane"),
        action_kind=_text(body.get("action_kind"), "transition.action_kind"),
        last_event_id=_optional_text(body.get("last_event_id"), "transition.last_event_id"),
        previous_event_address=_optional_text(
            body.get("previous_event_address"), "transition.previous_event_address"
        ),
        required_check_ids=_text_sequence(
            body.get("required_check_ids", ()), "transition.required_check_ids"
        ),
        missing_dependency_ids=_text_sequence(
            body.get("missing_dependency_ids", ()), "transition.missing_dependency_ids"
        ),
        requires_reason=bool(body.get("requires_reason")),
        rationale=_text(body.get("rationale"), "transition.rationale"),
        content_address=_address_without_content(
            body, "review-workspace-execution-transition-option", "transition.content_address"
        ),
    )
    if option.transition_id != _transition_id(option.action_id, option.kind):
        raise ValidationError("transition ID does not reconcile")
    if option.to_status is not _resulting_status(option.kind):
        raise ValidationError("transition resulting status does not reconcile")
    if option.permitted != option.allowed_by_state:
        raise ValidationError("transition permitted flag does not reconcile")
    if option.executable_without_additional_input and option.disposition is not ReviewWorkspaceExecutionTransitionDisposition.AVAILABLE:
        raise ValidationError("transition executable flag does not reconcile")
    return option


def _action_from_mapping(value: Any) -> ReviewWorkspaceExecutionTransitionAction:
    body = _mapping(value, "execution transition action")
    raw_options = body.get("options", ())
    if not isinstance(raw_options, (list, tuple)):
        raise ValidationError("transition action options must be an array")
    options = tuple(_option_from_mapping(item) for item in raw_options)
    action = ReviewWorkspaceExecutionTransitionAction(
        action_id=_text(body.get("action_id"), "transition action.action_id"),
        queue_item_id=_text(body.get("queue_item_id"), "transition action.queue_item_id"),
        target_id=_text(body.get("target_id"), "transition action.target_id"),
        title=_text(body.get("title"), "transition action.title"),
        purpose=_text(body.get("purpose"), "transition action.purpose"),
        lane=_text(body.get("lane"), "transition action.lane"),
        action_kind=_text(body.get("action_kind"), "transition action.action_kind"),
        priority=int(body.get("priority")),
        sequence=int(body.get("sequence")),
        status=_status(body.get("status"), "transition action.status"),
        ready=bool(body.get("ready")),
        unresolved_dependencies=_text_sequence(
            body.get("unresolved_dependencies", ()), "transition action.unresolved_dependencies"
        ),
        last_event_id=_optional_text(body.get("last_event_id"), "transition action.last_event_id"),
        previous_event_address=_optional_text(
            body.get("previous_event_address"), "transition action.previous_event_address"
        ),
        recommended_transition_id=_optional_text(
            body.get("recommended_transition_id"), "transition action.recommended_transition_id"
        ),
        recommended_kind=(
            None
            if body.get("recommended_kind") in (None, "")
            else _kind(body.get("recommended_kind"), "transition action.recommended_kind")
        ),
        options=options,
        content_address=_address_without_content(
            body, "review-workspace-execution-transition-action", "transition action.content_address"
        ),
    )
    option_ids = tuple(item.transition_id for item in options)
    if len(set(option_ids)) != len(option_ids):
        raise ValidationError("transition action contains duplicate option IDs")
    if {item.kind.value for item in options} != _EVENT_KIND_VALUES:
        raise ValidationError("transition action must expose every event kind exactly once")
    if any(item.action_id != action.action_id for item in options):
        raise ValidationError("transition action option names a different action")
    if action.recommended_transition_id not in set(option_ids) | {None}:
        raise ValidationError("transition action recommendation is not in its options")
    if action.recommended_kind is not None:
        selected = next(
            (item for item in options if item.kind is action.recommended_kind),
            None,
        )
        if selected is None or selected.transition_id != action.recommended_transition_id:
            raise ValidationError("transition action recommendation does not reconcile")
    return action


def review_workspace_execution_transitions_from_mapping(
    value: Mapping[str, Any],
) -> ReviewWorkspaceExecutionTransitions:
    """Hydrate a transition artifact and verify all nested addresses and counts."""

    body = _mapping(value, "execution transitions")
    if contains_private_key(body) or any(
        str(key).casefold() in _FORBIDDEN_KEYS for key in body
    ):
        raise ValidationError("execution transitions violate the public boundary")
    raw_actions = body.get("actions", ())
    if not isinstance(raw_actions, (list, tuple)):
        raise ValidationError("execution transitions actions must be an array")
    actions = tuple(_action_from_mapping(item) for item in raw_actions)
    action_ids = tuple(item.action_id for item in actions)
    if len(set(action_ids)) != len(action_ids):
        raise ValidationError("execution transitions contain duplicate action IDs")
    options = tuple(item for action in actions for item in action.options)
    option_ids = tuple(item.transition_id for item in options)
    if len(set(option_ids)) != len(option_ids):
        raise ValidationError("execution transitions contain duplicate transition IDs")
    status_counts = dict(sorted(Counter(item.status.value for item in actions).items()))
    kind_counts = dict(sorted(Counter(item.kind.value for item in options).items()))
    disposition_counts = dict(sorted(Counter(item.disposition.value for item in options).items()))
    expected_counts = {
        "action_count": len(actions),
        "option_count": len(options),
        "executable_option_count": sum(item.executable_without_additional_input for item in options),
        "permitted_option_count": sum(item.permitted for item in options),
        "requires_reason_count": disposition_counts.get(
            ReviewWorkspaceExecutionTransitionDisposition.REQUIRES_REASON.value, 0
        ),
        "requires_checks_count": disposition_counts.get(
            ReviewWorkspaceExecutionTransitionDisposition.REQUIRES_CHECKS.value, 0
        ),
        "waiting_dependency_count": disposition_counts.get(
            ReviewWorkspaceExecutionTransitionDisposition.WAITING_DEPENDENCIES.value, 0
        ),
        "not_allowed_count": disposition_counts.get(
            ReviewWorkspaceExecutionTransitionDisposition.NOT_ALLOWED.value, 0
        ),
    }
    for field, expected in expected_counts.items():
        if int(body.get(field, -1)) != expected:
            raise ValidationError(f"execution transitions {field} does not reconcile")
    values = {
        "execution_id": _text(body.get("execution_id"), "transitions.execution_id"),
        "execution_address": _text(body.get("execution_address"), "transitions.execution_address"),
        "plan_id": _text(body.get("plan_id"), "transitions.plan_id"),
        "plan_address": _text(body.get("plan_address"), "transitions.plan_address"),
        "workspace_id": _text(body.get("workspace_id"), "transitions.workspace_id"),
        "run_id": _text(body.get("run_id"), "transitions.run_id"),
        "case_id": _text(body.get("case_id"), "transitions.case_id"),
        "version": _text(body.get("version"), "transitions.version"),
        "state": _text(body.get("state"), "transitions.state"),
        "accepted": bool(body.get("accepted")),
        **expected_counts,
        "ready_action_ids": _text_sequence(body.get("ready_action_ids", ()), "transitions.ready_action_ids"),
        "completion_ready_action_ids": _text_sequence(
            body.get("completion_ready_action_ids", ()), "transitions.completion_ready_action_ids"
        ),
        "blocked_action_ids": _text_sequence(
            body.get("blocked_action_ids", ()), "transitions.blocked_action_ids"
        ),
        "recommended_action_ids": _text_sequence(
            body.get("recommended_action_ids", ()), "transitions.recommended_action_ids"
        ),
        "recommended_transition_ids": _text_sequence(
            body.get("recommended_transition_ids", ()), "transitions.recommended_transition_ids"
        ),
        "status_counts": {str(key): int(item) for key, item in _mapping(body.get("status_counts", {}), "transitions.status_counts").items()},
        "transition_counts": {str(key): int(item) for key, item in _mapping(body.get("transition_counts", {}), "transitions.transition_counts").items()},
        "disposition_counts": {str(key): int(item) for key, item in _mapping(body.get("disposition_counts", {}), "transitions.disposition_counts").items()},
        "actions": actions,
        "warnings": _text_sequence(body.get("warnings", ()), "transitions.warnings"),
    }
    if values["status_counts"] != status_counts:
        raise ValidationError("execution transitions status counts do not reconcile")
    if values["transition_counts"] != kind_counts:
        raise ValidationError("execution transitions transition counts do not reconcile")
    if values["disposition_counts"] != disposition_counts:
        raise ValidationError("execution transitions disposition counts do not reconcile")
    expected_ready = tuple(item.action_id for item in actions if item.ready)
    expected_completion = tuple(
        item.action_id
        for item in actions
        if any(
            option.kind is ReviewPlanExecutionEventKind.COMPLETE
            and option.allowed_by_state
            and not option.missing_dependency_ids
            for option in item.options
        )
    )
    expected_blocked = tuple(
        item.action_id for item in actions if item.status is ReviewPlanExecutionStatus.BLOCKED
    )
    expected_recommended = tuple(
        item.action_id for item in actions if item.recommended_transition_id is not None
    )
    expected_recommended_transitions = tuple(
        item.recommended_transition_id
        for item in actions
        if item.recommended_transition_id is not None
    )
    if values["ready_action_ids"] != expected_ready:
        raise ValidationError("execution transitions ready IDs do not reconcile")
    if values["completion_ready_action_ids"] != expected_completion:
        raise ValidationError("execution transitions completion IDs do not reconcile")
    if values["blocked_action_ids"] != expected_blocked:
        raise ValidationError("execution transitions blocked IDs do not reconcile")
    if values["recommended_action_ids"] != expected_recommended:
        raise ValidationError("execution transitions recommended IDs do not reconcile")
    if values["recommended_transition_ids"] != expected_recommended_transitions:
        raise ValidationError("execution transitions recommendation IDs do not reconcile")
    expected_body = dict(values)
    transitions_version = _text(
        body.get("transitions_version"), "transitions.transitions_version"
    )
    if transitions_version != REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_VERSION:
        raise ValidationError("execution transitions version is invalid")
    expected_body["transitions_version"] = transitions_version
    content_address = _address_without_content(
        body, "review-workspace-execution-transitions", "transitions.content_address"
    )
    expected_body.pop("content_address", None)
    if _address(expected_body, "review-workspace-execution-transitions") != content_address:
        raise ValidationError("execution transitions content address does not reconcile")
    return ReviewWorkspaceExecutionTransitions(**values, content_address=content_address)


def _option_text(item: ReviewWorkspaceExecutionTransitionOption) -> str:
    return " ".join(
        (
            item.transition_id,
            item.action_id,
            item.kind.value,
            item.from_status.value,
            item.to_status.value,
            item.disposition.value,
            item.lane,
            item.action_kind,
            item.rationale,
            *item.required_check_ids,
            *item.missing_dependency_ids,
        )
    ).casefold()


def _matches(
    item: ReviewWorkspaceExecutionTransitionOption,
    query: ReviewWorkspaceExecutionTransitionsQuery,
) -> bool:
    if query.action_id and item.action_id != str(query.action_id).strip():
        return False
    if query.kind and item.kind.value != str(query.kind).strip().casefold():
        return False
    if query.disposition and item.disposition.value != str(query.disposition).strip().casefold():
        return False
    if query.status and item.from_status.value != str(query.status).strip().casefold():
        return False
    if query.lane and item.lane != str(query.lane).strip().casefold():
        return False
    if query.action_kind and item.action_kind != str(query.action_kind).strip().casefold():
        return False
    if query.priorities and item.priority not in query.priorities:
        return False
    if query.executable is not None and item.executable_without_additional_input is not query.executable:
        return False
    if query.permitted is not None and item.permitted is not query.permitted:
        return False
    if query.text and str(query.text).casefold() not in _option_text(item):
        return False
    return True


def _facets(items: Iterable[ReviewWorkspaceExecutionTransitionOption]) -> dict[str, dict[str, int]]:
    values = tuple(items)
    return {
        "kinds": dict(sorted(Counter(item.kind.value for item in values).items())),
        "dispositions": dict(sorted(Counter(item.disposition.value for item in values).items())),
        "statuses": dict(sorted(Counter(item.from_status.value for item in values).items())),
        "lanes": dict(sorted(Counter(item.lane for item in values).items())),
        "action_kinds": dict(sorted(Counter(item.action_kind for item in values).items())),
        "priorities": dict(sorted(Counter(str(item.priority) for item in values).items())),
    }


def query_review_workspace_execution_transitions(
    transitions: ReviewWorkspaceExecutionTransitions,
    query: ReviewWorkspaceExecutionTransitionsQuery | Mapping[str, Any] | None = None,
) -> ReviewWorkspaceExecutionTransitionsQueryResult:
    """Return a bounded transition page and complete-match facets."""

    if not isinstance(transitions, ReviewWorkspaceExecutionTransitions):
        raise ValidationError("transition query requires a typed transition frontier")
    selected = (
        query
        if isinstance(query, ReviewWorkspaceExecutionTransitionsQuery)
        else ReviewWorkspaceExecutionTransitionsQuery.from_mapping(query)
    )
    values = tuple(
        item
        for action in transitions.actions
        for item in action.options
        if _matches(item, selected)
    )
    page = values[selected.offset:] if selected.limit is None else values[
        selected.offset : selected.offset + selected.limit
    ]
    body = {
        "execution_address": transitions.execution_address,
        "query": selected,
        "rows": page,
        "total_count": len(values),
        "has_more": selected.offset + len(page) < len(values),
        "facets": _facets(values),
        "accepted": transitions.accepted,
        "warnings": transitions.warnings,
    }
    return ReviewWorkspaceExecutionTransitionsQueryResult(
        execution_address=transitions.execution_address,
        query=selected,
        rows=tuple(page),
        total_count=len(values),
        has_more=selected.offset + len(page) < len(values),
        facets=body["facets"],
        accepted=transitions.accepted,
        warnings=transitions.warnings,
        content_address=_address(body, "review-workspace-execution-transitions-query"),
    )


def review_workspace_execution_transitions_json(
    transitions: ReviewWorkspaceExecutionTransitions,
) -> str:
    """Render canonical transition-frontier JSON."""

    return canonical_json(transitions.to_dict()) + "\n"


def review_workspace_execution_transitions_csv(
    transitions: ReviewWorkspaceExecutionTransitions,
) -> str:
    """Render all transition options as deterministic CSV."""

    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "transition_id",
            "action_id",
            "kind",
            "from_status",
            "to_status",
            "disposition",
            "allowed_by_state",
            "executable_without_additional_input",
            "permitted",
            "ready",
            "priority",
            "sequence",
            "lane",
            "action_kind",
            "last_event_id",
            "previous_event_address",
            "required_check_ids",
            "missing_dependency_ids",
            "requires_reason",
            "rationale",
            "content_address",
        )
    )
    for action in transitions.actions:
        for item in action.options:
            writer.writerow(
                (
                    item.transition_id,
                    item.action_id,
                    item.kind.value,
                    item.from_status.value,
                    item.to_status.value,
                    item.disposition.value,
                    item.allowed_by_state,
                    item.executable_without_additional_input,
                    item.permitted,
                    item.ready,
                    item.priority,
                    item.sequence,
                    item.lane,
                    item.action_kind,
                    item.last_event_id or "",
                    item.previous_event_address or "",
                    ";".join(item.required_check_ids),
                    ";".join(item.missing_dependency_ids),
                    item.requires_reason,
                    item.rationale,
                    item.content_address,
                )
            )
    return output.getvalue()


def render_review_workspace_execution_transitions_markdown(
    transitions: ReviewWorkspaceExecutionTransitions,
) -> str:
    """Render an operator-readable transition frontier without payloads."""

    lines = [
        "# Review workspace execution transitions",
        "",
        f"- Execution: `{transitions.execution_id}`",
        f"- Execution address: `{transitions.execution_address}`",
        f"- State: `{transitions.state}`",
        f"- Actions: `{transitions.action_count}`",
        f"- Transition options: `{transitions.option_count}`",
        f"- Executable without additional input: `{transitions.executable_option_count}`",
        f"- Permitted with declared input: `{transitions.permitted_option_count}`",
        f"- Waiting on dependencies: `{transitions.waiting_dependency_count}`",
        f"- Requiring checks: `{transitions.requires_checks_count}`",
        f"- Requiring a reason: `{transitions.requires_reason_count}`",
        "",
        "| Sequence | Action | Status | Kind | Disposition | Precondition | Address |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for action in transitions.actions:
        for item in action.options:
            lines.append(
                f"| {item.sequence} | `{item.action_id}` | `{item.from_status.value}` | "
                f"`{item.kind.value}` | `{item.disposition.value}` | "
                f"{item.rationale} | `{item.content_address}` |"
            )
    lines.extend(
        (
            "",
            "This is a read-only preflight projection. Appending an event remains "
            "an explicit operation and still replays the full ledger.",
            "",
        )
    )
    return "\n".join(lines)


def review_workspace_execution_transitions_export_payloads(
    transitions: ReviewWorkspaceExecutionTransitions,
) -> dict[str, str]:
    """Return the canonical transition artifacts used by releases and CLI clients."""

    return {
        "review-workspace-execution-transitions.json": review_workspace_execution_transitions_json(
            transitions
        ),
        "review-workspace-execution-transitions.csv": review_workspace_execution_transitions_csv(
            transitions
        ),
        "review-workspace-execution-transitions.md": render_review_workspace_execution_transitions_markdown(
            transitions
        ),
    }


def _option_map(
    transitions: ReviewWorkspaceExecutionTransitions,
) -> dict[str, ReviewWorkspaceExecutionTransitionOption]:
    result: dict[str, ReviewWorkspaceExecutionTransitionOption] = {}
    for action in transitions.actions:
        for option in action.options:
            if option.transition_id in result:
                raise ValidationError(f"duplicate transition ID: {option.transition_id}")
            result[option.transition_id] = option
    return result


def _action_map(
    transitions: ReviewWorkspaceExecutionTransitions,
) -> dict[str, ReviewWorkspaceExecutionTransitionAction]:
    result: dict[str, ReviewWorkspaceExecutionTransitionAction] = {}
    for action in transitions.actions:
        if action.action_id in result:
            raise ValidationError(f"duplicate transition action ID: {action.action_id}")
        result[action.action_id] = action
    return result


def _action_diff(
    action_id: str,
    left: ReviewWorkspaceExecutionTransitionAction | None,
    right: ReviewWorkspaceExecutionTransitionAction | None,
) -> ReviewWorkspaceExecutionTransitionActionDiff:
    body = {
        "action_id": action_id,
        "left_status": None if left is None else left.status.value,
        "right_status": None if right is None else right.status.value,
        "left_ready": None if left is None else left.ready,
        "right_ready": None if right is None else right.ready,
        "left_recommended_transition_id": (
            None if left is None else left.recommended_transition_id
        ),
        "right_recommended_transition_id": (
            None if right is None else right.recommended_transition_id
        ),
        "left_option_count": 0 if left is None else len(left.options),
        "right_option_count": 0 if right is None else len(right.options),
    }
    return ReviewWorkspaceExecutionTransitionActionDiff(
        **body,
        changed=(
            body["left_status"] != body["right_status"]
            or body["left_ready"] != body["right_ready"]
            or body["left_recommended_transition_id"]
            != body["right_recommended_transition_id"]
            or body["left_option_count"] != body["right_option_count"]
        ),
        content_address=_address(body, "review-workspace-execution-transition-action-diff"),
    )


def diff_review_workspace_execution_transitions(
    left: ReviewWorkspaceExecutionTransitions,
    right: ReviewWorkspaceExecutionTransitions,
) -> ReviewWorkspaceExecutionTransitionsDiff:
    """Compare transition options and recommendations across two snapshots."""

    if not isinstance(left, ReviewWorkspaceExecutionTransitions) or not isinstance(
        right, ReviewWorkspaceExecutionTransitions
    ):
        raise ValidationError("transition diff requires typed transition frontiers")
    left_options = _option_map(left)
    right_options = _option_map(right)
    left_ids = set(left_options)
    right_ids = set(right_options)
    added = tuple(sorted(right_ids - left_ids))
    removed = tuple(sorted(left_ids - right_ids))
    common = left_ids & right_ids
    changed = tuple(
        sorted(item for item in common if left_options[item].content_address != right_options[item].content_address)
    )
    unchanged = tuple(sorted(common - set(changed)))
    left_actions = _action_map(left)
    right_actions = _action_map(right)
    action_diffs = tuple(
        _action_diff(item, left_actions.get(item), right_actions.get(item))
        for item in sorted(set(left_actions) | set(right_actions))
    )
    count_fields = (
        "action_count",
        "option_count",
        "executable_option_count",
        "permitted_option_count",
        "requires_reason_count",
        "requires_checks_count",
        "waiting_dependency_count",
        "not_allowed_count",
    )
    count_deltas = {
        field: int(getattr(right, field)) - int(getattr(left, field))
        for field in count_fields
    }
    body = {
        "diff_version": REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_DIFF_VERSION,
        "left_execution_address": left.execution_address,
        "right_execution_address": right.execution_address,
        "added_transition_ids": added,
        "removed_transition_ids": removed,
        "changed_transition_ids": changed,
        "unchanged_transition_ids": unchanged,
        "action_diffs": tuple(item.to_dict() for item in action_diffs),
        "count_deltas": count_deltas,
        "recommendation_changed": left.recommended_transition_ids != right.recommended_transition_ids,
        "left_recommended_transition_ids": left.recommended_transition_ids,
        "right_recommended_transition_ids": right.recommended_transition_ids,
        "accepted": left.accepted and right.accepted,
    }
    return ReviewWorkspaceExecutionTransitionsDiff(
        left_execution_address=left.execution_address,
        right_execution_address=right.execution_address,
        added_transition_ids=added,
        removed_transition_ids=removed,
        changed_transition_ids=changed,
        unchanged_transition_ids=unchanged,
        action_diffs=action_diffs,
        count_deltas=count_deltas,
        recommendation_changed=body["recommendation_changed"],
        left_recommended_transition_ids=left.recommended_transition_ids,
        right_recommended_transition_ids=right.recommended_transition_ids,
        accepted=left.accepted and right.accepted,
        content_address=_address(body, "review-workspace-execution-transitions-diff"),
    )


def review_workspace_execution_transitions_schema() -> dict[str, Any]:
    """Return the public schema and reconciliation rules."""

    return {
        "version": REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_SCHEMA_VERSION,
        "type": "object",
        "required": [
            "transitions_version",
            "execution_id",
            "execution_address",
            "plan_id",
            "plan_address",
            "actions",
            "option_count",
            "accepted",
            "content_address",
        ],
        "properties": {
            "transitions_version": {
                "const": REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_VERSION
            },
            "execution_id": {"type": "string"},
            "execution_address": {"type": "string"},
            "plan_id": {"type": "string"},
            "plan_address": {"type": "string"},
            "workspace_id": {"type": "string"},
            "run_id": {"type": "string"},
            "case_id": {"type": "string"},
            "state": {
                "type": "string",
                "enum": [item.value for item in ReviewPlanExecutionStatus],
            },
            "accepted": {"type": "boolean"},
            "action_count": {"type": "integer", "minimum": 0},
            "option_count": {"type": "integer", "minimum": 0},
            "executable_option_count": {"type": "integer", "minimum": 0},
            "permitted_option_count": {"type": "integer", "minimum": 0},
            "ready_action_ids": {"type": "array", "uniqueItems": True},
            "completion_ready_action_ids": {"type": "array", "uniqueItems": True},
            "blocked_action_ids": {"type": "array", "uniqueItems": True},
            "recommended_action_ids": {"type": "array", "uniqueItems": True},
            "recommended_transition_ids": {"type": "array", "uniqueItems": True},
            "status_counts": {"type": "object"},
            "transition_counts": {
                "type": "object",
                "properties": {item.value: {"type": "integer", "minimum": 0} for item in _EVENT_KINDS},
            },
            "disposition_counts": {
                "type": "object",
                "properties": {
                    item.value: {"type": "integer", "minimum": 0}
                    for item in ReviewWorkspaceExecutionTransitionDisposition
                },
            },
            "actions": {"type": "array", "maxItems": REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_MAX_ACTIONS},
            "warnings": {"type": "array"},
            "content_address": {"type": "string"},
        },
        "option_contract": {
            "all_event_kinds_are_explicit": True,
            "state_machine_reconciled": True,
            "dependency_preconditions_explicit": True,
            "required_check_preconditions_explicit": True,
            "reason_preconditions_explicit": True,
            "previous_event_address_exposed": True,
            "bounded_rationale": True,
            "content_addressed": True,
        },
        "query": {
            "version": REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_QUERY_VERSION,
            "filters": [
                "action_id",
                "kind",
                "disposition",
                "status",
                "lane",
                "action_kind",
                "priorities",
                "executable",
                "permitted",
                "text",
                "offset",
                "limit",
            ],
            "max_limit": REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_MAX_LIMIT,
            "complete_match_facets": [
                "kinds",
                "dispositions",
                "statuses",
                "lanes",
                "action_kinds",
                "priorities",
            ],
        },
        "diff": {
            "version": REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_DIFF_VERSION,
            "schema_version": REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_DIFF_SCHEMA_VERSION,
            "delta_direction": "right minus left for aggregate counts",
            "transition_address_changes": True,
            "action_recommendation_changes": True,
        },
        "boundary": {
            "raw_evidence": False,
            "reviewer_identity": False,
            "agent_identity": False,
            "model_metadata": False,
            "programming_language_metadata": False,
            "scientific_decision": False,
        },
    }


def review_workspace_execution_transitions_capabilities() -> dict[str, Any]:
    """Return capability metadata without execution-specific rows."""

    return {
        "version": REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_VERSION,
        "all_state_machine_options": True,
        "state_machine_preflight": True,
        "dependency_preflight": True,
        "required_check_preflight": True,
        "reason_preflight": True,
        "previous_event_address": True,
        "deterministic_recommendations": True,
        "bounded_query": True,
        "complete_match_facets": True,
        "json_export": True,
        "csv_export": True,
        "markdown_export": True,
        "content_addressed": True,
        "public_boundary_audit": True,
        "transition_diff": True,
        "action_diff": True,
        "aggregate_deltas": True,
        "read_only": True,
    }


def review_workspace_execution_transitions_diff_schema() -> dict[str, Any]:
    """Return the standalone transition-diff contract."""

    return {
        "version": REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_DIFF_SCHEMA_VERSION,
        "type": "object",
        "required": [
            "diff_version",
            "left_execution_address",
            "right_execution_address",
            "added_transition_ids",
            "removed_transition_ids",
            "changed_transition_ids",
            "unchanged_transition_ids",
            "action_diffs",
            "count_deltas",
            "recommendation_changed",
            "accepted",
            "content_address",
        ],
        "properties": {
            "diff_version": {"const": REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_DIFF_VERSION},
            "left_execution_address": {"type": "string"},
            "right_execution_address": {"type": "string"},
            "added_transition_ids": {"type": "array", "uniqueItems": True},
            "removed_transition_ids": {"type": "array", "uniqueItems": True},
            "changed_transition_ids": {"type": "array", "uniqueItems": True},
            "unchanged_transition_ids": {"type": "array", "uniqueItems": True},
            "action_diffs": {"type": "array"},
            "count_deltas": {"type": "object"},
            "recommendation_changed": {"type": "boolean"},
            "accepted": {"type": "boolean"},
            "content_address": {"type": "string"},
        },
        "delta_direction": "right minus left for count_deltas",
    }


def review_workspace_execution_transitions_diff_capabilities() -> dict[str, Any]:
    """Return capability metadata for transition comparisons."""

    return {
        "version": REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_DIFF_VERSION,
        "added_removed_changed_unchanged_options": True,
        "per_action_recommendation_diff": True,
        "aggregate_count_deltas": True,
        "right_minus_left_deltas": True,
        "deterministic_ordering": True,
        "content_addressed": True,
        "public_boundary_audit": True,
    }


__all__ = [
    "REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_DEFAULT_LIMIT",
    "REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_DIFF_SCHEMA_VERSION",
    "REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_DIFF_VERSION",
    "REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_MAX_ACTIONS",
    "REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_MAX_LIMIT",
    "REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_MAX_OPTIONS",
    "REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_MAX_TEXT",
    "REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_SCHEMA_VERSION",
    "REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_QUERY_VERSION",
    "REVIEW_WORKSPACE_EXECUTION_TRANSITIONS_VERSION",
    "ReviewWorkspaceExecutionTransitionActionDiff",
    "ReviewWorkspaceExecutionTransitionAction",
    "ReviewWorkspaceExecutionTransitionDisposition",
    "ReviewWorkspaceExecutionTransitionOption",
    "ReviewWorkspaceExecutionTransitions",
    "ReviewWorkspaceExecutionTransitionsDiff",
    "ReviewWorkspaceExecutionTransitionsQuery",
    "ReviewWorkspaceExecutionTransitionsQueryResult",
    "build_review_workspace_execution_transitions",
    "diff_review_workspace_execution_transitions",
    "query_review_workspace_execution_transitions",
    "render_review_workspace_execution_transitions_markdown",
    "review_workspace_execution_transitions_capabilities",
    "review_workspace_execution_transitions_csv",
    "review_workspace_execution_transitions_diff_capabilities",
    "review_workspace_execution_transitions_diff_schema",
    "review_workspace_execution_transitions_export_payloads",
    "review_workspace_execution_transitions_from_mapping",
    "review_workspace_execution_transitions_json",
    "review_workspace_execution_transitions_schema",
]
