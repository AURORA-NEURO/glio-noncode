"""Cross-run portfolio and release-readiness projections.

The run catalog, review queue, workspace history, and release builders each
answer a different operational question.  A portfolio row joins those public
projections for one persisted run without returning raw dossier payloads.  It
is designed for dashboards, offline triage, and handoff planning: operators can
see replay integrity, current workspace state, review timing, and portable
release readiness in one deterministic document.

Portfolio acceptance means that the row was reconstructed without a projection
contract error and contains only public metadata.  ``release_accepted`` is kept
separate: a valid, review-pending run is inspectable but is not release-ready.
The projection remains descriptive research infrastructure and never makes a
clinical or treatment decision.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .errors import StoreError, ValidationError
from .module_fabric_support import contains_private_key
from .review_operations import (
    REVIEW_DUE_STATES,
    REVIEW_OPERATIONS_DEFAULT_DUE_SOON_HOURS,
    build_review_operations_closure,
)
from .run_catalog import inspect_run
from .run_workspace import _has_forbidden_key
from .runtime import CaseRuntime
from .serialization import content_hash
from .workspace_history import WorkspaceHistory, build_persisted_workspace_history
from .workspace_release import WorkspaceReleaseBundle, build_workspace_release_bundle

RUN_PORTFOLIO_VERSION = "run-portfolio-v1"
RUN_PORTFOLIO_DEFAULT_LIMIT = 25
RUN_PORTFOLIO_MAX_LIMIT = 100
RUN_PORTFOLIO_RELEASE_STATES = ("ready", "blocked", "unavailable")

_DUE_ORDER = {
    "overdue": 0,
    "invalid": 1,
    "due_soon": 2,
    "undated": 3,
    "scheduled": 4,
    "completed": 5,
}


def _text(value: Any) -> str:
    return str(value).strip()


def _unique_warnings(*groups: Any) -> tuple[str, ...]:
    values: list[str] = []
    for group in groups:
        if isinstance(group, str):
            candidates = (group,)
        elif isinstance(group, (list, tuple, set)):
            candidates = group
        else:
            candidates = ()
        for value in candidates:
            warning = _text(value)
            if warning and warning not in values:
                values.append(warning)
    return tuple(values)


@dataclass(frozen=True, slots=True)
class RunPortfolioRow:
    """One public operational row joining persisted run projections."""

    run_id: str
    case_id: str
    dossier_address: str
    created_at: str
    status: str
    review_state: str | None
    reviewer: str | None
    queue_id: str | None
    queue_state: str
    due_state: str
    due_at: str | None
    priority_score: int
    priority_band: str
    integrity_accepted: bool
    workspace_accepted: bool
    workspace_state: str
    snapshot_count: int
    transition_count: int
    workspace_history_address: str | None
    release_id: str | None
    release_state: str
    release_accepted: bool
    release_failed_check_ids: tuple[str, ...]
    warning_count: int
    warnings: tuple[str, ...]
    accepted: bool
    content_address: str

    @property
    def release_ready(self) -> bool:
        """Return whether this row has a portable accepted handoff."""

        return self.release_accepted and self.release_state == "ready"

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "case_id": self.case_id,
            "dossier_address": self.dossier_address,
            "created_at": self.created_at,
            "status": self.status,
            "review_state": self.review_state,
            "reviewer": self.reviewer,
            "queue_id": self.queue_id,
            "queue_state": self.queue_state,
            "due_state": self.due_state,
            "due_at": self.due_at,
            "priority_score": self.priority_score,
            "priority_band": self.priority_band,
            "integrity_accepted": self.integrity_accepted,
            "workspace_accepted": self.workspace_accepted,
            "workspace_state": self.workspace_state,
            "snapshot_count": self.snapshot_count,
            "transition_count": self.transition_count,
            "workspace_history_address": self.workspace_history_address,
            "release_id": self.release_id,
            "release_state": self.release_state,
            "release_accepted": self.release_accepted,
            "release_ready": self.release_ready,
            "release_failed_check_ids": list(self.release_failed_check_ids),
            "warning_count": self.warning_count,
            "warnings": list(self.warnings),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class RunPortfolio:
    """Bounded or complete cross-run portfolio projection."""

    as_of: str
    due_soon_hours: int
    rows: tuple[RunPortfolioRow, ...]
    total_count: int
    offset: int
    limit: int | None
    has_more: bool
    filters: Mapping[str, Any]
    counts: Mapping[str, Any]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "portfolio_version": RUN_PORTFOLIO_VERSION,
            "as_of": self.as_of,
            "due_soon_hours": self.due_soon_hours,
            "rows": [item.to_dict() for item in self.rows],
            "count": len(self.rows),
            "total_count": self.total_count,
            "offset": self.offset,
            "limit": self.limit,
            "has_more": self.has_more,
            "filters": dict(self.filters),
            "counts": dict(self.counts),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _operation_fields(operation: Mapping[str, Any] | None) -> dict[str, Any]:
    """Extract stable operational fields without exposing the queue payload."""

    source = operation or {}
    return {
        "case_id": _text(source.get("case_id", "")),
        "created_at": _text(source.get("created_at", "")),
        "status": _text(source.get("queue_item", {}).get("status", ""))
        if isinstance(source.get("queue_item"), Mapping)
        else "",
        "review_state": source.get("review_state") if source.get("review_state") else None,
        "reviewer": source.get("reviewer") if source.get("reviewer") else None,
        "queue_id": source.get("queue_id") if source.get("queue_id") else None,
        "queue_state": _text(source.get("queue_state", "blocked")) or "blocked",
        "due_state": _text(source.get("due_state", "invalid")) or "invalid",
        "due_at": source.get("due_at") if source.get("due_at") else None,
        "priority_score": int(source.get("priority_score", 0) or 0),
        "priority_band": _text(source.get("priority_band", "low")) or "low",
        "accepted": bool(source.get("accepted", False)),
        "warnings": source.get("warnings", ()),
    }


def _release_fields(
    history: WorkspaceHistory | None,
    bundle: WorkspaceReleaseBundle | None,
    error: str | None,
) -> dict[str, Any]:
    if bundle is not None:
        return {
            "workspace_accepted": bool(history and history.accepted),
            "workspace_state": (
                history.snapshots[history.current_snapshot_index].workspace_state
                if history
                and history.snapshots
                and 0 <= history.current_snapshot_index < len(history.snapshots)
                else "blocked"
            ),
            "snapshot_count": history.snapshot_count if history else 0,
            "transition_count": history.transition_count if history else 0,
            "workspace_history_address": history.content_address if history else None,
            "release_id": bundle.release_id,
            "release_state": bundle.state,
            "release_accepted": bundle.accepted,
            "release_failed_check_ids": bundle.failed_check_ids,
            "warnings": history.warnings if history else (),
        }
    return {
        "workspace_accepted": False,
        "workspace_state": "unavailable",
        "snapshot_count": 0,
        "transition_count": 0,
        "workspace_history_address": None,
        "release_id": None,
        "release_state": "unavailable",
        "release_accepted": False,
        "release_failed_check_ids": (),
        "warnings": (error or "workspace release projection was unavailable",),
    }


def _row_from_run(
    runtime: CaseRuntime,
    run_record: Mapping[str, Any],
    operation: Mapping[str, Any] | None,
) -> RunPortfolioRow:
    run_id = _text(run_record.get("run_id", ""))
    operational = _operation_fields(operation)
    warnings: tuple[str, ...] = ()
    integrity_accepted = False
    dossier_address = ""
    try:
        inspection = inspect_run(runtime, run_id)
        summary = inspection.summary
        integrity_accepted = inspection.accepted
        dossier_address = summary.dossier_address
        operational.update(
            {
                "case_id": summary.case_id,
                "created_at": summary.created_at,
                "status": summary.status,
            }
        )
        warnings = _unique_warnings(summary.warnings)
    except (AttributeError, KeyError, StoreError, TypeError, ValueError) as exc:
        warnings = _unique_warnings(f"run inspection failed: {exc}")

    history: WorkspaceHistory | None = None
    bundle: WorkspaceReleaseBundle | None = None
    release_error: str | None = None
    try:
        history = build_persisted_workspace_history(runtime, run_id)
        bundle = build_workspace_release_bundle(history)
    except (AttributeError, KeyError, StoreError, TypeError, ValueError, ValidationError) as exc:
        release_error = f"workspace release projection failed: {exc}"

    release = _release_fields(history, bundle, release_error)
    warnings = _unique_warnings(
        warnings,
        operational.get("warnings", ()),
        release.get("warnings", ()),
        bundle.failed_check_ids if bundle is not None else (),
    )
    accepted = (
        integrity_accepted
        and bool(operational.get("accepted", False))
        and not _has_forbidden_key(release)
        and not contains_private_key(release)
    )
    body = {
        "run_id": run_id,
        "case_id": _text(operational.get("case_id", "")),
        "dossier_address": dossier_address,
        "created_at": _text(operational.get("created_at", "")),
        "status": _text(operational.get("status", "")),
        "review_state": operational.get("review_state"),
        "reviewer": operational.get("reviewer"),
        "queue_id": operational.get("queue_id"),
        "queue_state": _text(operational.get("queue_state", "blocked")),
        "due_state": _text(operational.get("due_state", "invalid")),
        "due_at": operational.get("due_at"),
        "priority_score": int(operational.get("priority_score", 0)),
        "priority_band": _text(operational.get("priority_band", "low")),
        "integrity_accepted": integrity_accepted,
        **{key: value for key, value in release.items() if key != "warnings"},
        "warning_count": len(warnings),
        "warnings": warnings,
        "accepted": accepted,
    }
    return RunPortfolioRow(
        **body,
        content_address=content_hash(body, prefix="run-portfolio-row"),
    )


def _validate_filters(
    *,
    offset: int,
    limit: int | None,
    due_state: str | None,
    release_state: str | None,
) -> None:
    if offset < 0:
        raise ValidationError("offset must be non-negative")
    if limit is not None and (limit < 1 or limit > RUN_PORTFOLIO_MAX_LIMIT):
        raise ValidationError(f"limit must be between 1 and {RUN_PORTFOLIO_MAX_LIMIT}")
    if due_state is not None and due_state not in REVIEW_DUE_STATES:
        raise ValidationError(f"due_state must be one of: {', '.join(REVIEW_DUE_STATES)}")
    if release_state is not None and release_state not in RUN_PORTFOLIO_RELEASE_STATES:
        raise ValidationError(
            f"release_state must be one of: {', '.join(RUN_PORTFOLIO_RELEASE_STATES)}"
        )


def _counts(rows: tuple[RunPortfolioRow, ...]) -> dict[str, Any]:
    status_counts = Counter(item.status or "unknown" for item in rows)
    due_counts = Counter(item.due_state or "invalid" for item in rows)
    release_counts = Counter(item.release_state or "unavailable" for item in rows)
    review_counts = Counter(item.review_state or "missing" for item in rows)
    return {
        "total": len(rows),
        "accepted": sum(item.accepted for item in rows),
        "integrity_accepted": sum(item.integrity_accepted for item in rows),
        "workspace_accepted": sum(item.workspace_accepted for item in rows),
        "release_ready": sum(item.release_ready for item in rows),
        "release_blocked": sum(item.release_state == "blocked" for item in rows),
        "status": dict(sorted(status_counts.items())),
        "due_state": {state: due_counts.get(state, 0) for state in REVIEW_DUE_STATES},
        "review_state": dict(sorted(review_counts.items())),
        "release_state": {
            state: release_counts.get(state, 0) for state in RUN_PORTFOLIO_RELEASE_STATES
        },
    }


def _build_portfolio_rows(
    runtime: CaseRuntime,
    *,
    as_of: str | datetime | None,
    due_soon_hours: int,
) -> tuple[tuple[RunPortfolioRow, ...], bool, str]:
    closure = build_review_operations_closure(
        runtime,
        as_of=as_of,
        due_soon_hours=due_soon_hours,
    )
    report = closure.get("report", {})
    operation_rows = report.get("rows", ()) if isinstance(report, Mapping) else ()
    operation_map = {
        _text(item.get("run_id", "")): item
        for item in operation_rows
        if isinstance(item, Mapping) and _text(item.get("run_id", ""))
    }
    rows = tuple(
        _row_from_run(runtime, record, operation_map.get(_text(record.get("run_id", ""))))
        for record in runtime.store.list_runs()
    )
    rows = tuple(
        sorted(
            rows,
            key=lambda item: (
                _DUE_ORDER.get(item.due_state, 99),
                -item.priority_score,
                item.created_at,
                item.run_id,
            ),
        )
    )
    as_of_value = _text(report.get("as_of", "")) if isinstance(report, Mapping) else ""
    return rows, bool(closure.get("accepted", False)), as_of_value


def build_run_portfolio(
    runtime: CaseRuntime,
    *,
    case_id: str | None = None,
    status: str | None = None,
    reviewer: str | None = None,
    due_state: str | None = None,
    release_state: str | None = None,
    text: str | None = None,
    release_ready_only: bool = False,
    as_of: str | datetime | None = None,
    due_soon_hours: int = REVIEW_OPERATIONS_DEFAULT_DUE_SOON_HOURS,
    offset: int = 0,
    limit: int | None = RUN_PORTFOLIO_DEFAULT_LIMIT,
) -> RunPortfolio:
    """Build a bounded cross-run portfolio with release readiness metadata."""

    _validate_filters(
        offset=offset,
        limit=limit,
        due_state=due_state,
        release_state=release_state,
    )
    if due_soon_hours < 1:
        raise ValidationError("due_soon_hours must be positive")
    all_rows, operations_accepted, as_of_value = _build_portfolio_rows(
        runtime,
        as_of=as_of,
        due_soon_hours=due_soon_hours,
    )
    normalized_text = text.strip().lower() if text else None
    matched: list[RunPortfolioRow] = []
    for row in all_rows:
        if case_id is not None and row.case_id != case_id:
            continue
        if status is not None and row.status != status:
            continue
        if reviewer is not None and row.reviewer != reviewer:
            continue
        if due_state is not None and row.due_state != due_state:
            continue
        if release_state is not None and row.release_state != release_state:
            continue
        if release_ready_only and not row.release_ready:
            continue
        haystack = " ".join(
            (
                row.run_id,
                row.case_id,
                row.status,
                row.review_state or "",
                row.reviewer or "",
                row.queue_state,
                row.due_state,
                row.release_state,
                *row.warnings,
            )
        ).lower()
        if normalized_text is not None and normalized_text not in haystack:
            continue
        matched.append(row)
    selected = tuple(matched[offset:] if limit is None else matched[offset : offset + limit])
    has_more = False if limit is None else offset + len(selected) < len(matched)
    filters = {
        "case_id": case_id,
        "status": status,
        "reviewer": reviewer,
        "due_state": due_state,
        "release_state": release_state,
        "text": text,
        "release_ready_only": release_ready_only,
    }
    counts = _counts(tuple(matched))
    body = {
        "as_of": as_of_value,
        "due_soon_hours": due_soon_hours,
        "rows": [item.to_dict() for item in selected],
        "total_count": len(matched),
        "offset": offset,
        "limit": limit,
        "has_more": has_more,
        "filters": filters,
        "counts": counts,
        "operations_accepted": operations_accepted,
    }
    accepted = operations_accepted and all(item.accepted for item in all_rows)
    accepted = accepted and not _has_forbidden_key(body) and not contains_private_key(body)
    return RunPortfolio(
        as_of=as_of_value,
        due_soon_hours=due_soon_hours,
        rows=selected,
        total_count=len(matched),
        offset=offset,
        limit=limit,
        has_more=has_more,
        filters=filters,
        counts=counts,
        accepted=accepted,
        content_address=content_hash(body | {"accepted": accepted}, prefix="run-portfolio"),
    )


def build_run_portfolio_closure(
    runtime: CaseRuntime,
    *,
    as_of: str | datetime | None = None,
    due_soon_hours: int = REVIEW_OPERATIONS_DEFAULT_DUE_SOON_HOURS,
) -> dict[str, Any]:
    """Build an unbounded portfolio closure for offline operational handoff."""

    portfolio = build_run_portfolio(
        runtime,
        as_of=as_of,
        due_soon_hours=due_soon_hours,
        limit=None,
    )
    closure = portfolio.to_dict()
    closure["complete"] = True
    closure["content_address"] = content_hash(closure, prefix="run-portfolio-closure")
    return closure


__all__ = [
    "RUN_PORTFOLIO_DEFAULT_LIMIT",
    "RUN_PORTFOLIO_MAX_LIMIT",
    "RUN_PORTFOLIO_RELEASE_STATES",
    "RUN_PORTFOLIO_VERSION",
    "RunPortfolio",
    "RunPortfolioRow",
    "build_run_portfolio",
    "build_run_portfolio_closure",
]
