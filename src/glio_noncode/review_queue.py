"""Deterministic operational review queue for persisted case runs.

The queue is a projection over replay-verified runs.  It does not change a
dossier by itself; assignment changes are appended by ``CaseRuntime`` as
``review_assigned`` events and therefore remain visible in the same history,
comparison, and release surfaces as scientific review decisions.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from .errors import StoreError
from .models import ReviewState
from .module_fabric_support import contains_private_key
from .run_catalog import inspect_run
from .runtime import CaseRuntime
from .serialization import content_hash

REVIEW_QUEUE_VERSION = "review-queue-v1"
REVIEW_QUEUE_DEFAULT_LIMIT = 25
REVIEW_QUEUE_MAX_LIMIT = 100
REVIEW_QUEUE_SCOPES = ("open", "all", "assigned", "unassigned", "completed", "blocked")
REVIEW_PRIORITY_BANDS = ("critical", "high", "normal", "low")


@dataclass(frozen=True, slots=True)
class ReviewAssignmentView:
    """Public projection of the latest assignment event for a run."""

    assignment_id: str
    run_id: str
    case_id: str
    reviewer: str
    queue_id: str
    due_at: str
    note: str
    created_at: str
    address_valid: bool
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.assignment_id and self.reviewer and self.address_valid)

    def to_dict(self) -> dict[str, Any]:
        return {
            "assignment_id": self.assignment_id,
            "run_id": self.run_id,
            "case_id": self.case_id,
            "reviewer": self.reviewer,
            "queue_id": self.queue_id,
            "due_at": self.due_at,
            "note": self.note,
            "created_at": self.created_at,
            "address_valid": self.address_valid,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class ReviewQueueItem:
    """One prioritized run waiting for or completing human review."""

    run_id: str
    case_id: str
    dossier_id: str
    dossier_address: str
    created_at: str
    status: str
    review_state: str | None
    review_id: str | None
    reviewer: str | None
    queue_state: str
    assignment: ReviewAssignmentView | None
    priority_score: int
    priority_band: str
    priority_reasons: tuple[str, ...]
    hypothesis_count: int
    evidence_count: int
    experiment_count: int
    warning_count: int
    event_count: int
    integrity_accepted: bool
    accepted: bool
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "case_id": self.case_id,
            "dossier_id": self.dossier_id,
            "dossier_address": self.dossier_address,
            "created_at": self.created_at,
            "status": self.status,
            "review_state": self.review_state,
            "review_id": self.review_id,
            "reviewer": self.reviewer,
            "queue_state": self.queue_state,
            "assignment": self.assignment.to_dict() if self.assignment else None,
            "priority_score": self.priority_score,
            "priority_band": self.priority_band,
            "priority_reasons": list(self.priority_reasons),
            "hypothesis_count": self.hypothesis_count,
            "evidence_count": self.evidence_count,
            "experiment_count": self.experiment_count,
            "warning_count": self.warning_count,
            "event_count": self.event_count,
            "integrity_accepted": self.integrity_accepted,
            "accepted": self.accepted,
            "warnings": list(self.warnings),
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class ReviewQueuePage:
    """Bounded deterministic queue page with filter evidence."""

    rows: tuple[ReviewQueueItem, ...]
    total_count: int
    offset: int
    limit: int
    has_more: bool
    scope: str
    filters: dict[str, Any]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "queue_version": REVIEW_QUEUE_VERSION,
            "rows": [item.to_dict() for item in self.rows],
            "count": len(self.rows),
            "total_count": self.total_count,
            "offset": self.offset,
            "limit": self.limit,
            "has_more": self.has_more,
            "scope": self.scope,
            "filters": self.filters,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _assignment_from_event(raw_event: dict[str, Any]) -> ReviewAssignmentView | None:
    if raw_event.get("event_type") != "review_assigned":
        return None
    payload = raw_event.get("payload")
    if not isinstance(payload, dict):
        return None
    body = {key: value for key, value in payload.items() if key != "content_address"}
    address = str(payload.get("content_address", ""))
    address_valid = content_hash(body, prefix="review-assignment") == address
    return ReviewAssignmentView(
        assignment_id=str(payload.get("assignment_id", "")),
        run_id=str(payload.get("run_id", "")),
        case_id=str(payload.get("case_id", "")),
        reviewer=str(payload.get("reviewer", "")),
        queue_id=str(payload.get("queue_id", "")),
        due_at=str(payload.get("due_at", "")),
        note=str(payload.get("note", "")),
        created_at=str(payload.get("created_at", "")),
        address_valid=address_valid,
        content_address=address or content_hash(body, prefix="review-assignment"),
    )


def _latest_assignment(event_record: dict[str, Any]) -> ReviewAssignmentView | None:
    latest: ReviewAssignmentView | None = None
    events = event_record.get("events", ())
    if not isinstance(events, (list, tuple)):
        return None
    for raw_event in events:
        if isinstance(raw_event, dict):
            assignment = _assignment_from_event(raw_event)
            if assignment is not None:
                latest = assignment
    return latest


def _priority(
    raw_dossier: dict[str, Any],
    *,
    queue_state: str,
    assignment: ReviewAssignmentView | None,
) -> tuple[int, str, tuple[str, ...]]:
    review = raw_dossier.get("review")
    review_state = str(review.get("state")) if isinstance(review, dict) and review.get("state") else None
    warnings = tuple(raw_dossier.get("warnings", ()))
    hypotheses = tuple(item for item in raw_dossier.get("hypotheses", ()) if isinstance(item, dict))
    evidence = tuple(item for item in raw_dossier.get("evidence", ()) if isinstance(item, dict))
    score = 0
    reasons: list[str] = []
    if queue_state == "blocked":
        score += 200
        reasons.append("integrity_blocked")
    elif review_state == ReviewState.RETURNED.value:
        score += 145
        reasons.append("review_returned")
    elif review_state == ReviewState.PENDING.value:
        score += 135
        reasons.append("review_pending")
    elif review_state is None:
        score += 125
        reasons.append("review_missing")
    elif review_state in {ReviewState.ACCEPTED.value, ReviewState.REJECTED.value}:
        reasons.append("review_completed")
    else:
        score += 100
        reasons.append("review_state_unrecognized")

    warning_points = min(25, len(warnings) * 5)
    if warning_points:
        score += warning_points
        reasons.append("runtime_warnings")
    high_support = sum(float(item.get("support", 0.0)) >= 0.75 for item in hypotheses)
    if high_support:
        points = min(20, high_support * 5)
        score += points
        reasons.append("high_support_hypothesis")
    high_uncertainty = sum(float(item.get("uncertainty", 0.0)) >= 0.5 for item in hypotheses)
    if high_uncertainty:
        points = min(20, high_uncertainty * 5)
        score += points
        reasons.append("high_uncertainty_hypothesis")
    abstained = sum(str(item.get("state", "")) == "abstained" for item in evidence)
    if abstained:
        score += min(20, abstained * 5)
        reasons.append("abstained_evidence")
    if queue_state in {"unassigned", "blocked"}:
        score += 10
        reasons.append("no_active_assignment")
    if queue_state == "completed":
        score = 0
    if score >= 170:
        band = "critical"
    elif score >= 130:
        band = "high"
    elif score >= 80:
        band = "normal"
    else:
        band = "low"
    return score, band, tuple(dict.fromkeys(reasons))


def _blocked_item(run_record: dict[str, Any], reason: str) -> ReviewQueueItem:
    run_id = str(run_record.get("run_id", ""))
    body = {
        "run_id": run_id,
        "case_id": "",
        "dossier_id": "",
        "dossier_address": str(run_record.get("dossier_address", "")),
        "created_at": "",
        "status": "",
        "review_state": None,
        "review_id": None,
        "reviewer": None,
        "queue_state": "blocked",
        "assignment": None,
        "priority_score": 210,
        "priority_band": "critical",
        "priority_reasons": ("integrity_blocked",),
        "hypothesis_count": 0,
        "evidence_count": 0,
        "experiment_count": 0,
        "warning_count": 0,
        "event_count": 0,
        "integrity_accepted": False,
        "accepted": False,
        "warnings": (reason,),
    }
    return ReviewQueueItem(**body, content_address=content_hash(body, prefix="review-queue-item"))


def _item_from_inspection(inspection: Any) -> ReviewQueueItem:
    raw = inspection.dossier_record
    review = raw.get("review") if isinstance(raw, dict) else None
    review_state = str(review.get("state")) if isinstance(review, dict) and review.get("state") else None
    review_id = str(review.get("review_id")) if isinstance(review, dict) and review.get("review_id") else None
    assignment = _latest_assignment(inspection.event_record)
    assignment_matches = assignment is None or (
        assignment.run_id == inspection.summary.run_id
        and assignment.case_id == str(raw.get("case_id", ""))
        and assignment.accepted
    )
    if review_state in {ReviewState.ACCEPTED.value, ReviewState.REJECTED.value}:
        queue_state = "completed"
    elif not inspection.accepted or not assignment_matches:
        queue_state = "blocked"
    elif assignment is not None:
        queue_state = "assigned"
    else:
        queue_state = "unassigned"
    reviewer = assignment.reviewer if assignment else (
        str(review.get("reviewer")) if isinstance(review, dict) and review.get("reviewer") else None
    )
    score, band, reasons = _priority(raw, queue_state=queue_state, assignment=assignment)
    warnings = tuple(str(item) for item in raw.get("warnings", ()))
    if assignment is not None and not assignment_matches:
        warnings += ("latest review assignment does not match the persisted run or has an invalid address",)
    body = {
        "run_id": inspection.summary.run_id,
        "case_id": str(raw.get("case_id", "")),
        "dossier_id": str(raw.get("dossier_id", "")),
        "dossier_address": inspection.summary.dossier_address,
        "created_at": str(raw.get("created_at", "")),
        "status": str(raw.get("status", "")),
        "review_state": review_state,
        "review_id": review_id,
        "reviewer": reviewer,
        "queue_state": queue_state,
        "assignment": assignment,
        "priority_score": score,
        "priority_band": band,
        "priority_reasons": reasons,
        "hypothesis_count": len(raw.get("hypotheses", ())),
        "evidence_count": len(raw.get("evidence", ())),
        "experiment_count": len(raw.get("experiments", ())),
        "warning_count": len(warnings),
        "event_count": len(inspection.event_record.get("events", ())),
        "integrity_accepted": inspection.accepted,
        "accepted": inspection.accepted and assignment_matches,
        "warnings": warnings,
    }
    return ReviewQueueItem(**body, content_address=content_hash(body, prefix="review-queue-item"))


def _scope_match(item: ReviewQueueItem, scope: str) -> bool:
    if scope == "all":
        return True
    if scope == "open":
        return item.queue_state in {"unassigned", "assigned", "blocked"}
    return item.queue_state == scope


def _collect_review_items(runtime: CaseRuntime) -> list[ReviewQueueItem]:
    """Reopen every indexed run once and convert failures into blocked rows."""

    items: list[ReviewQueueItem] = []
    for run_record in runtime.store.list_runs():
        try:
            item = _item_from_inspection(inspect_run(runtime, str(run_record.get("run_id", ""))))
        except (AttributeError, KeyError, StoreError, TypeError, ValueError) as exc:
            item = _blocked_item(run_record, f"run inspection failed: {exc}")
        items.append(item)
    items.sort(key=lambda item: (-item.priority_score, item.created_at, item.run_id))
    return items


def build_review_queue_page(
    runtime: CaseRuntime,
    *,
    scope: str = "open",
    case_id: str | None = None,
    status: str | None = None,
    reviewer: str | None = None,
    queue_id: str | None = None,
    priority_band: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = REVIEW_QUEUE_DEFAULT_LIMIT,
) -> ReviewQueuePage:
    """Build a bounded priority page over all persisted review work."""

    if scope not in REVIEW_QUEUE_SCOPES:
        raise ValueError(f"scope must be one of: {', '.join(REVIEW_QUEUE_SCOPES)}")
    if priority_band is not None and priority_band not in REVIEW_PRIORITY_BANDS:
        raise ValueError(f"priority_band must be one of: {', '.join(REVIEW_PRIORITY_BANDS)}")
    if offset < 0:
        raise ValueError("offset must be non-negative")
    if limit < 1 or limit > REVIEW_QUEUE_MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {REVIEW_QUEUE_MAX_LIMIT}")
    normalized_text = text.strip().lower() if text else None
    all_items = _collect_review_items(runtime)
    selected_items: list[ReviewQueueItem] = []
    filters = {
        "case_id": case_id,
        "status": status,
        "reviewer": reviewer,
        "queue_id": queue_id,
        "priority_band": priority_band,
        "text": text,
    }
    for item in all_items:
        if not _scope_match(item, scope):
            continue
        if case_id is not None and item.case_id != case_id:
            continue
        if status is not None and item.status != status:
            continue
        if reviewer is not None and item.reviewer != reviewer:
            continue
        if queue_id is not None and (item.assignment is None or item.assignment.queue_id != queue_id):
            continue
        if priority_band is not None and item.priority_band != priority_band:
            continue
        haystack = " ".join(
            (item.run_id, item.case_id, item.dossier_id, item.status, item.reviewer or "", *item.priority_reasons)
        ).lower()
        if normalized_text is not None and normalized_text not in haystack:
            continue
        selected_items.append(item)
    selected = tuple(selected_items[offset : offset + limit])
    body = {
        "rows": selected,
        "total_count": len(selected_items),
        "offset": offset,
        "limit": limit,
        "has_more": offset + len(selected) < len(selected_items),
        "scope": scope,
        "filters": filters,
    }
    public_body = {key: value for key, value in body.items() if key != "rows"} | {
        "rows": [item.to_dict() for item in selected]
    }
    accepted = all(item.accepted for item in all_items) and not contains_private_key(public_body)
    return ReviewQueuePage(
        rows=selected,
        total_count=len(selected_items),
        offset=offset,
        limit=limit,
        has_more=body["has_more"],
        scope=scope,
        filters=filters,
        accepted=accepted,
        content_address=content_hash(body | {"accepted": accepted}, prefix="review-queue-page"),
    )


def build_review_queue_closure(runtime: CaseRuntime) -> dict[str, Any]:
    """Return a complete queue projection with operational counters."""

    all_items = tuple(_collect_review_items(runtime))
    accepted = all(item.accepted for item in all_items)
    page_body = {
        "rows": all_items,
        "total_count": len(all_items),
        "offset": 0,
        "limit": max(REVIEW_QUEUE_DEFAULT_LIMIT, len(all_items)),
        "has_more": False,
        "scope": "all",
        "filters": {
            "case_id": None,
            "status": None,
            "reviewer": None,
            "queue_id": None,
            "priority_band": None,
            "text": None,
        },
    }
    page_accepted = accepted and not contains_private_key(page_body)
    page = ReviewQueuePage(
        rows=all_items,
        total_count=len(all_items),
        offset=0,
        limit=page_body["limit"],
        has_more=False,
        scope="all",
        filters=page_body["filters"],
        accepted=page_accepted,
        content_address=content_hash(page_body | {"accepted": page_accepted}, prefix="review-queue-page"),
    )
    state_counts = Counter(item.queue_state for item in page.rows)
    band_counts = Counter(item.priority_band for item in page.rows)
    review_counts = Counter(item.review_state or "missing" for item in page.rows)
    summary = {
        "total_count": page.total_count,
        "queue_state_counts": dict(sorted(state_counts.items())),
        "priority_band_counts": dict(sorted(band_counts.items())),
        "review_state_counts": dict(sorted(review_counts.items())),
        "accepted_count": sum(item.accepted for item in page.rows),
        "blocked_count": state_counts.get("blocked", 0),
    }
    closure = {
        "queue_version": REVIEW_QUEUE_VERSION,
        "accepted": page.accepted,
        "page": page.to_dict(),
        "summary": summary,
    }
    closure["content_address"] = content_hash(closure, prefix="review-queue-closure")
    return closure


__all__ = [
    "REVIEW_PRIORITY_BANDS",
    "REVIEW_QUEUE_DEFAULT_LIMIT",
    "REVIEW_QUEUE_MAX_LIMIT",
    "REVIEW_QUEUE_SCOPES",
    "REVIEW_QUEUE_VERSION",
    "ReviewAssignmentView",
    "ReviewQueueItem",
    "ReviewQueuePage",
    "build_review_queue_closure",
    "build_review_queue_page",
]
