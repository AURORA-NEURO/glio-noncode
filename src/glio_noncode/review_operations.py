"""Deterministic SLA, aging, and reviewer-workload projections.

The review queue answers which persisted runs exist and how they are prioritized.
This module adds the operational clock around that queue without mutating a run:
each row receives an explicit due-state, age, remaining-time calculation, and
next action, while workload rows aggregate the same public evidence by reviewer
and queue.  Callers can supply ``as_of`` to make a report reproducible; the
default is the current UTC instant for interactive use.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from .errors import ValidationError
from .module_fabric_support import contains_private_key
from .review_queue import REVIEW_PRIORITY_BANDS, REVIEW_QUEUE_SCOPES, build_review_queue_closure
from .runtime import CaseRuntime
from .serialization import content_hash, utc_now

REVIEW_OPERATIONS_VERSION = "review-operations-v1"
REVIEW_OPERATIONS_DEFAULT_DUE_SOON_HOURS = 48
REVIEW_OPERATIONS_MAX_DUE_SOON_HOURS = 720
REVIEW_OPERATIONS_DEFAULT_LIMIT = 50
REVIEW_OPERATIONS_MAX_LIMIT = 500
REVIEW_DUE_STATES = ("completed", "overdue", "due_soon", "scheduled", "undated", "invalid")
REVIEW_OPERATIONAL_ACTIONS = (
    "none",
    "integrity_review",
    "escalate_overdue",
    "confirm_capacity",
    "assign_due_date",
    "repair_assignment",
    "monitor_schedule",
    "assign_reviewer",
    "review_case",
)

_DUE_ORDER = {
    "overdue": 0,
    "invalid": 1,
    "due_soon": 2,
    "undated": 3,
    "scheduled": 4,
    "completed": 5,
}


def _parse_instant(value: str | datetime | None, *, field: str, required: bool = False) -> datetime | None:
    """Parse an ISO instant and normalize it to timezone-aware UTC."""

    if value is None:
        if required:
            raise ValidationError(f"{field} must not be empty")
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if not text:
            if required:
                raise ValidationError(f"{field} must not be empty")
            return None
        normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValidationError(f"{field} must be an ISO-8601 instant") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _format_instant(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _require_choice(value: str | None, name: str, choices: tuple[str, ...]) -> None:
    if value is not None and value not in choices:
        raise ValidationError(f"{name} must be one of: {', '.join(choices)}")


def _row_assignment(row: dict[str, Any]) -> dict[str, Any]:
    assignment = row.get("assignment")
    return assignment if isinstance(assignment, dict) else {}


def _operational_action(queue_state: str, due_state: str) -> str:
    if queue_state == "completed" or due_state == "completed":
        return "none"
    if queue_state == "blocked":
        return "integrity_review"
    if due_state == "overdue":
        return "escalate_overdue"
    if due_state == "invalid":
        return "repair_assignment"
    if due_state == "due_soon":
        return "confirm_capacity"
    if queue_state == "unassigned":
        return "assign_reviewer"
    if due_state == "undated":
        return "assign_due_date"
    return "monitor_schedule"


def _due_projection(
    row: dict[str, Any],
    *,
    as_of: datetime,
    due_soon_cutoff: datetime,
) -> tuple[str, int, int | None, str, tuple[str, ...], bool]:
    """Return due state, age, remaining time, action, warnings, and validity."""

    warnings = tuple(str(item) for item in row.get("warnings", ()) if str(item))
    created_at = str(row.get("created_at", "")).strip()
    created_valid = True
    try:
        created = _parse_instant(created_at, field="created_at", required=True)
        age_seconds = max(0, int((as_of - created).total_seconds())) if created else 0
    except ValidationError:
        created_valid = False
        age_seconds = 0
        warnings += ("created_at is not a valid ISO-8601 instant",)

    queue_state = str(row.get("queue_state", ""))
    if queue_state == "completed":
        return "completed", age_seconds, None, "none", warnings, created_valid

    assignment = _row_assignment(row)
    due_text = str(assignment.get("due_at", "")).strip()
    if not due_text:
        return "undated", age_seconds, None, _operational_action(queue_state, "undated"), warnings, created_valid
    try:
        due_at = _parse_instant(due_text, field="due_at", required=True)
    except ValidationError:
        warnings += ("due_at is not a valid ISO-8601 instant",)
        return "invalid", age_seconds, None, "repair_assignment", warnings, False
    due_seconds = int((due_at - as_of).total_seconds())
    if due_at <= as_of:
        state = "overdue"
    elif due_at <= due_soon_cutoff:
        state = "due_soon"
    else:
        state = "scheduled"
    valid = created_valid and not any(
        item == "due_at is not a valid ISO-8601 instant" for item in warnings
    )
    return state, age_seconds, due_seconds, _operational_action(queue_state, state), warnings, valid


@dataclass(frozen=True, slots=True)
class ReviewOperationItem:
    """One queue row with reproducible SLA and operational metadata."""

    run_id: str
    case_id: str
    queue_state: str
    review_state: str | None
    reviewer: str | None
    queue_id: str | None
    assignment_id: str | None
    priority_score: int
    priority_band: str
    created_at: str
    due_at: str | None
    due_state: str
    age_seconds: int
    due_in_seconds: int | None
    operational_action: str
    queue_item: dict[str, Any]
    warnings: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "case_id": self.case_id,
            "queue_state": self.queue_state,
            "review_state": self.review_state,
            "reviewer": self.reviewer,
            "queue_id": self.queue_id,
            "assignment_id": self.assignment_id,
            "priority_score": self.priority_score,
            "priority_band": self.priority_band,
            "created_at": self.created_at,
            "due_at": self.due_at,
            "due_state": self.due_state,
            "age_seconds": self.age_seconds,
            "due_in_seconds": self.due_in_seconds,
            "operational_action": self.operational_action,
            "queue_item": self.queue_item,
            "warnings": list(self.warnings),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class ReviewWorkload:
    """Aggregate open and completed work for one reviewer and queue."""

    reviewer: str
    queue_id: str
    total_count: int
    open_count: int
    assigned_count: int
    unassigned_count: int
    completed_count: int
    blocked_count: int
    overdue_count: int
    due_soon_count: int
    critical_count: int
    total_priority: int
    oldest_open_created_at: str | None
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "reviewer": self.reviewer,
            "queue_id": self.queue_id,
            "total_count": self.total_count,
            "open_count": self.open_count,
            "assigned_count": self.assigned_count,
            "unassigned_count": self.unassigned_count,
            "completed_count": self.completed_count,
            "blocked_count": self.blocked_count,
            "overdue_count": self.overdue_count,
            "due_soon_count": self.due_soon_count,
            "critical_count": self.critical_count,
            "total_priority": self.total_priority,
            "oldest_open_created_at": self.oldest_open_created_at,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class ReviewOperationsReport:
    """Bounded, as-of review operations report."""

    as_of: str
    due_soon_hours: int
    due_soon_cutoff: str
    rows: tuple[ReviewOperationItem, ...]
    workloads: tuple[ReviewWorkload, ...]
    total_count: int
    offset: int
    limit: int | None
    has_more: bool
    scope: str
    filters: dict[str, Any]
    counts: dict[str, int]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "operations_version": REVIEW_OPERATIONS_VERSION,
            "as_of": self.as_of,
            "due_soon_hours": self.due_soon_hours,
            "due_soon_cutoff": self.due_soon_cutoff,
            "rows": [item.to_dict() for item in self.rows],
            "workloads": [item.to_dict() for item in self.workloads],
            "count": len(self.rows),
            "total_count": self.total_count,
            "offset": self.offset,
            "limit": self.limit,
            "has_more": self.has_more,
            "scope": self.scope,
            "filters": self.filters,
            "counts": self.counts,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _operation_from_row(row: dict[str, Any], *, as_of: datetime, due_soon_cutoff: datetime) -> ReviewOperationItem:
    assignment = _row_assignment(row)
    due_state, age_seconds, due_in_seconds, action, warnings, temporal_valid = _due_projection(
        row,
        as_of=as_of,
        due_soon_cutoff=due_soon_cutoff,
    )
    queue_state = str(row.get("queue_state", ""))
    body = {
        "run_id": str(row.get("run_id", "")),
        "case_id": str(row.get("case_id", "")),
        "queue_state": queue_state,
        "review_state": str(row["review_state"]) if row.get("review_state") is not None else None,
        "reviewer": str(row["reviewer"]) if row.get("reviewer") is not None else None,
        "queue_id": str(assignment["queue_id"]) if assignment.get("queue_id") else None,
        "assignment_id": str(assignment["assignment_id"]) if assignment.get("assignment_id") else None,
        "priority_score": int(row.get("priority_score", 0)),
        "priority_band": str(row.get("priority_band", "low")),
        "created_at": str(row.get("created_at", "")),
        "due_at": str(assignment["due_at"]) if assignment.get("due_at") else None,
        "due_state": due_state,
        "age_seconds": age_seconds,
        "due_in_seconds": due_in_seconds,
        "operational_action": action,
        "queue_item": dict(row),
        "warnings": warnings,
        "accepted": bool(row.get("accepted", False)) and temporal_valid,
    }
    return ReviewOperationItem(**body, content_address=content_hash(body, prefix="review-operation-item"))


def _scope_matches(row: ReviewOperationItem, scope: str) -> bool:
    if scope == "all":
        return True
    if scope == "open":
        return row.queue_state in {"unassigned", "assigned", "blocked"}
    return row.queue_state == scope


def _workload_for_rows(rows: tuple[ReviewOperationItem, ...]) -> tuple[ReviewWorkload, ...]:
    groups: dict[tuple[str, str], list[ReviewOperationItem]] = defaultdict(list)
    for row in rows:
        reviewer = row.reviewer or "unassigned"
        queue_id = row.queue_id or "unassigned"
        groups[(reviewer, queue_id)].append(row)
    workloads: list[ReviewWorkload] = []
    for (reviewer, queue_id), group in groups.items():
        open_rows = [item for item in group if item.queue_state != "completed"]
        body = {
            "reviewer": reviewer,
            "queue_id": queue_id,
            "total_count": len(group),
            "open_count": len(open_rows),
            "assigned_count": sum(item.queue_state == "assigned" for item in group),
            "unassigned_count": sum(item.queue_state == "unassigned" for item in group),
            "completed_count": sum(item.queue_state == "completed" for item in group),
            "blocked_count": sum(item.queue_state == "blocked" for item in group),
            "overdue_count": sum(item.due_state == "overdue" for item in open_rows),
            "due_soon_count": sum(item.due_state == "due_soon" for item in open_rows),
            "critical_count": sum(item.priority_band == "critical" for item in open_rows),
            "total_priority": sum(item.priority_score for item in open_rows),
            "oldest_open_created_at": min((item.created_at for item in open_rows), default=None),
        }
        public_body = body | {"accepted": all(item.accepted for item in group)}
        workloads.append(
            ReviewWorkload(
                **body,
                accepted=public_body["accepted"] and not contains_private_key(public_body),
                content_address=content_hash(public_body, prefix="review-workload"),
            )
        )
    workloads.sort(
        key=lambda item: (
            -item.overdue_count,
            -item.critical_count,
            -item.total_priority,
            item.reviewer,
            item.queue_id,
        )
    )
    return tuple(workloads)


def _build_operations(
    runtime: CaseRuntime,
    *,
    scope: str,
    reviewer: str | None,
    queue_id: str | None,
    due_state: str | None,
    priority_band: str | None,
    text: str | None,
    as_of: str | datetime | None,
    due_soon_hours: int,
    offset: int,
    limit: int | None,
) -> ReviewOperationsReport:
    _require_choice(scope, "scope", REVIEW_QUEUE_SCOPES)
    _require_choice(due_state, "due_state", REVIEW_DUE_STATES)
    _require_choice(priority_band, "priority_band", REVIEW_PRIORITY_BANDS)
    if offset < 0:
        raise ValidationError("offset must be non-negative")
    if limit is not None and (limit < 1 or limit > REVIEW_OPERATIONS_MAX_LIMIT):
        raise ValidationError(f"limit must be between 1 and {REVIEW_OPERATIONS_MAX_LIMIT}")
    if due_soon_hours < 1 or due_soon_hours > REVIEW_OPERATIONS_MAX_DUE_SOON_HOURS:
        raise ValidationError(
            f"due_soon_hours must be between 1 and {REVIEW_OPERATIONS_MAX_DUE_SOON_HOURS}"
        )
    as_of_dt = _parse_instant(as_of, field="as_of") or utc_now()
    due_soon_cutoff = as_of_dt + timedelta(hours=due_soon_hours)
    closure = build_review_queue_closure(runtime)
    queue_rows = closure.get("page", {}).get("rows", ())
    all_items = tuple(
        _operation_from_row(row, as_of=as_of_dt, due_soon_cutoff=due_soon_cutoff)
        for row in queue_rows
        if isinstance(row, dict)
    )
    normalized_text = text.strip().lower() if text else None
    matched: list[ReviewOperationItem] = []
    filters = {
        "reviewer": reviewer,
        "queue_id": queue_id,
        "due_state": due_state,
        "priority_band": priority_band,
        "text": text,
    }
    for item in all_items:
        if not _scope_matches(item, scope):
            continue
        if reviewer is not None and item.reviewer != reviewer:
            continue
        if queue_id is not None and item.queue_id != queue_id:
            continue
        if due_state is not None and item.due_state != due_state:
            continue
        if priority_band is not None and item.priority_band != priority_band:
            continue
        haystack = " ".join(
            (
                item.run_id,
                item.case_id,
                item.queue_state,
                item.review_state or "",
                item.reviewer or "",
                item.queue_id or "",
                item.due_state,
                item.operational_action,
            )
        ).lower()
        if normalized_text is not None and normalized_text not in haystack:
            continue
        matched.append(item)
    matched.sort(
        key=lambda item: (
            _DUE_ORDER.get(item.due_state, 99),
            -item.priority_score,
            item.created_at,
            item.run_id,
        )
    )
    selected = tuple(matched[offset:] if limit is None else matched[offset : offset + limit])
    has_more = False if limit is None else offset + len(selected) < len(matched)
    due_counts = Counter(item.due_state for item in matched)
    counts = {state: due_counts.get(state, 0) for state in REVIEW_DUE_STATES}
    counts.update(
        {
            "total": len(matched),
            "open": sum(item.queue_state != "completed" for item in matched),
            "completed": sum(item.queue_state == "completed" for item in matched),
            "blocked": sum(item.queue_state == "blocked" for item in matched),
            "accepted": sum(item.accepted for item in matched),
        }
    )
    workloads = _workload_for_rows(tuple(matched))
    body = {
        "as_of": _format_instant(as_of_dt),
        "due_soon_hours": due_soon_hours,
        "due_soon_cutoff": _format_instant(due_soon_cutoff),
        "rows": selected,
        "workloads": workloads,
        "total_count": len(matched),
        "offset": offset,
        "limit": limit,
        "has_more": has_more,
        "scope": scope,
        "filters": filters,
        "counts": counts,
    }
    public_body = body | {
        "rows": [item.to_dict() for item in selected],
        "workloads": [item.to_dict() for item in workloads],
    }
    accepted = bool(closure.get("accepted", False)) and all(item.accepted for item in all_items)
    accepted = accepted and not contains_private_key(public_body)
    return ReviewOperationsReport(
        as_of=str(body["as_of"]),
        due_soon_hours=due_soon_hours,
        due_soon_cutoff=str(body["due_soon_cutoff"]),
        rows=selected,
        workloads=workloads,
        total_count=len(matched),
        offset=offset,
        limit=limit,
        has_more=has_more,
        scope=scope,
        filters=filters,
        counts=counts,
        accepted=accepted,
        content_address=content_hash(body | {"accepted": accepted}, prefix="review-operations-report"),
    )


def build_review_operations_report(
    runtime: CaseRuntime,
    *,
    scope: str = "open",
    reviewer: str | None = None,
    queue_id: str | None = None,
    due_state: str | None = None,
    priority_band: str | None = None,
    text: str | None = None,
    as_of: str | datetime | None = None,
    due_soon_hours: int = REVIEW_OPERATIONS_DEFAULT_DUE_SOON_HOURS,
    offset: int = 0,
    limit: int | None = REVIEW_OPERATIONS_DEFAULT_LIMIT,
) -> ReviewOperationsReport:
    """Build a bounded, reproducible operational report over the queue."""

    return _build_operations(
        runtime,
        scope=scope,
        reviewer=reviewer,
        queue_id=queue_id,
        due_state=due_state,
        priority_band=priority_band,
        text=text,
        as_of=as_of,
        due_soon_hours=due_soon_hours,
        offset=offset,
        limit=limit,
    )


def build_review_operations_closure(
    runtime: CaseRuntime,
    *,
    as_of: str | datetime | None = None,
    due_soon_hours: int = REVIEW_OPERATIONS_DEFAULT_DUE_SOON_HOURS,
) -> dict[str, Any]:
    """Build an unbounded content-addressed operational closure."""

    report = _build_operations(
        runtime,
        scope="all",
        reviewer=None,
        queue_id=None,
        due_state=None,
        priority_band=None,
        text=None,
        as_of=as_of,
        due_soon_hours=due_soon_hours,
        offset=0,
        limit=None,
    )
    closure = {
        "operations_version": REVIEW_OPERATIONS_VERSION,
        "accepted": report.accepted,
        "report": report.to_dict(),
    }
    closure["content_address"] = content_hash(closure, prefix="review-operations-closure")
    return closure


__all__ = [
    "REVIEW_DUE_STATES",
    "REVIEW_OPERATIONS_DEFAULT_DUE_SOON_HOURS",
    "REVIEW_OPERATIONS_DEFAULT_LIMIT",
    "REVIEW_OPERATIONS_MAX_DUE_SOON_HOURS",
    "REVIEW_OPERATIONS_MAX_LIMIT",
    "REVIEW_OPERATIONS_VERSION",
    "REVIEW_OPERATIONAL_ACTIONS",
    "ReviewOperationItem",
    "ReviewOperationsReport",
    "ReviewWorkload",
    "build_review_operations_closure",
    "build_review_operations_report",
]
