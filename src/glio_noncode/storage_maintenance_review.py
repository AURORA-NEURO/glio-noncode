"""Prioritized review queue projections for storage maintenance plans.

Maintenance actions are diagnostics, not execution instructions. A reviewer
still needs a stable order, route, and compact explanation for each item. This
module derives that queue from the addressed plan using only action kind,
severity, reversibility, target metadata, and aggregate byte estimates. It has
no clock, no mutable assignment state, and no mutation path back into storage.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from io import StringIO
from typing import Any

from .errors import ValidationError
from .release_assurance_support import text_matches
from .serialization import canonical_json, content_hash, jsonable
from .storage_maintenance_contracts import (
    StorageMaintenanceActionKind,
    StorageMaintenancePlan,
    StorageMaintenanceSeverity,
    StorageMaintenanceState,
)

STORAGE_MAINTENANCE_REVIEW_VERSION = "storage-maintenance-review-v1"
STORAGE_MAINTENANCE_REVIEW_SCHEMA_VERSION = "storage-maintenance-review-schema-v1"
STORAGE_MAINTENANCE_REVIEW_BOUNDARY = "public_storage_maintenance_review"
STORAGE_MAINTENANCE_REVIEW_DEFAULT_LIMIT = 50
STORAGE_MAINTENANCE_REVIEW_MAX_LIMIT = 500
STORAGE_MAINTENANCE_REVIEW_DISPOSITIONS = ("clear", "review", "blocked")
STORAGE_MAINTENANCE_REVIEW_ROUTES = (
    "none",
    "quarantine",
    "recovery",
    "repair",
    "replay",
    "reopen",
)


def _text(value: Any, field: str, *, maximum: int = 500) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    result = str(value).strip()
    if not result:
        raise ValidationError(f"{field} must not be empty")
    if len(result) > maximum:
        raise ValidationError(f"{field} exceeds the maximum length")
    return result


def _optional_text(value: Any, field: str, *, maximum: int = 500) -> str | None:
    if value is None:
        return None
    return _text(value, field, maximum=maximum)


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return {str(key): item for key, item in value.items()}


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _int(value: Any, field: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be an integer")
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"{field} must be an integer") from exc
    if result < minimum or (maximum is not None and result > maximum):
        bound = f"between {minimum} and {maximum}" if maximum is not None else f"at least {minimum}"
        raise ValidationError(f"{field} must be {bound}")
    return result


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(dict(body), prefix=prefix)


class StorageMaintenanceReviewDisposition(StrEnum):
    CLEAR = "clear"
    REVIEW = "review"
    BLOCKED = "blocked"


def _route_for(kind: StorageMaintenanceActionKind) -> str:
    return {
        StorageMaintenanceActionKind.NO_ACTION: "none",
        StorageMaintenanceActionKind.QUARANTINE_ORPHAN: "quarantine",
        StorageMaintenanceActionKind.QUARANTINE_UNEXPECTED: "quarantine",
        StorageMaintenanceActionKind.RESTORE_MISSING_OBJECT: "recovery",
        StorageMaintenanceActionKind.REPAIR_INVALID_OBJECT: "repair",
        StorageMaintenanceActionKind.REPLAY_RUN: "replay",
        StorageMaintenanceActionKind.REOPEN_BATCH: "reopen",
    }[kind]


def _priority_for(
    kind: StorageMaintenanceActionKind,
    severity: StorageMaintenanceSeverity,
) -> int:
    if severity is StorageMaintenanceSeverity.CRITICAL:
        return 400
    if kind in {
        StorageMaintenanceActionKind.RESTORE_MISSING_OBJECT,
        StorageMaintenanceActionKind.REPAIR_INVALID_OBJECT,
        StorageMaintenanceActionKind.REPLAY_RUN,
        StorageMaintenanceActionKind.REOPEN_BATCH,
    }:
        return 300
    if severity is StorageMaintenanceSeverity.HIGH:
        return 300
    if severity is StorageMaintenanceSeverity.MODERATE:
        return 200
    return 0


def _disposition_for(
    plan: StorageMaintenancePlan,
    kind: StorageMaintenanceActionKind,
) -> StorageMaintenanceReviewDisposition:
    if (
        kind is StorageMaintenanceActionKind.NO_ACTION
        and plan.state is StorageMaintenanceState.CLEAN
    ):
        return StorageMaintenanceReviewDisposition.CLEAR
    if kind in {
        StorageMaintenanceActionKind.RESTORE_MISSING_OBJECT,
        StorageMaintenanceActionKind.REPAIR_INVALID_OBJECT,
        StorageMaintenanceActionKind.REPLAY_RUN,
        StorageMaintenanceActionKind.REOPEN_BATCH,
    }:
        return StorageMaintenanceReviewDisposition.BLOCKED
    return StorageMaintenanceReviewDisposition.REVIEW


@dataclass(frozen=True, slots=True)
class StorageMaintenanceReviewItem:
    """One stable prioritized reviewer row derived from an action."""

    review_id: str
    plan_id: str
    plan_address: str
    action_id: str
    kind: StorageMaintenanceActionKind
    severity: StorageMaintenanceSeverity
    disposition: StorageMaintenanceReviewDisposition
    route: str
    priority: int
    target_path: str | None
    target_address: str | None
    reason: str
    reversible: bool
    approval_required: bool
    estimated_bytes: int
    review_only: bool
    accepted: bool
    content_address: str

    def _body(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "plan_id": self.plan_id,
            "plan_address": self.plan_address,
            "action_id": self.action_id,
            "kind": self.kind,
            "severity": self.severity,
            "disposition": self.disposition,
            "route": self.route,
            "priority": self.priority,
            "target_path": self.target_path,
            "target_address": self.target_address,
            "reason": self.reason,
            "reversible": self.reversible,
            "approval_required": self.approval_required,
            "estimated_bytes": self.estimated_bytes,
            "review_only": self.review_only,
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        _text(self.review_id, "maintenance_review_item.review_id", maximum=180)
        _text(self.plan_id, "maintenance_review_item.plan_id", maximum=180)
        _text(self.plan_address, "maintenance_review_item.plan_address", maximum=180)
        _text(self.action_id, "maintenance_review_item.action_id", maximum=180)
        if not isinstance(self.kind, StorageMaintenanceActionKind):
            raise ValidationError("maintenance review item kind is invalid")
        if not isinstance(self.severity, StorageMaintenanceSeverity):
            raise ValidationError("maintenance review item severity is invalid")
        if not isinstance(self.disposition, StorageMaintenanceReviewDisposition):
            raise ValidationError("maintenance review item disposition is invalid")
        if self.route not in STORAGE_MAINTENANCE_REVIEW_ROUTES:
            raise ValidationError("maintenance review item route is invalid")
        _int(self.priority, "maintenance_review_item.priority", minimum=0, maximum=400)
        _optional_text(self.target_path, "maintenance_review_item.target_path", maximum=500)
        _optional_text(self.target_address, "maintenance_review_item.target_address", maximum=180)
        _text(self.reason, "maintenance_review_item.reason", maximum=500)
        for field in ("reversible", "approval_required", "review_only", "accepted"):
            _bool(getattr(self, field), f"maintenance_review_item.{field}")
        if not self.review_only:
            raise ValidationError("maintenance review item must remain review-only")
        _int(self.estimated_bytes, "maintenance_review_item.estimated_bytes", minimum=0)
        expected = _address(self._body(), "storage-maintenance-review-item")
        if expected != self.content_address:
            raise ValidationError("maintenance review item content address does not reconcile")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StorageMaintenanceReviewItem:
        body = _mapping(value, "maintenance review item")
        allowed = {
            "review_id",
            "plan_id",
            "plan_address",
            "action_id",
            "kind",
            "severity",
            "disposition",
            "route",
            "priority",
            "target_path",
            "target_address",
            "reason",
            "reversible",
            "approval_required",
            "estimated_bytes",
            "review_only",
            "accepted",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(
                f"maintenance review item contains unsupported fields: {sorted(unknown)}"
            )
        try:
            kind = StorageMaintenanceActionKind(body.get("kind"))
            severity = StorageMaintenanceSeverity(body.get("severity"))
            disposition = StorageMaintenanceReviewDisposition(body.get("disposition"))
        except ValueError as exc:
            raise ValidationError("maintenance review item enum value is invalid") from exc
        return cls(
            review_id=_text(
                body.get("review_id"), "maintenance_review_item.review_id", maximum=180
            ),
            plan_id=_text(body.get("plan_id"), "maintenance_review_item.plan_id", maximum=180),
            plan_address=_text(
                body.get("plan_address"), "maintenance_review_item.plan_address", maximum=180
            ),
            action_id=_text(
                body.get("action_id"), "maintenance_review_item.action_id", maximum=180
            ),
            kind=kind,
            severity=severity,
            disposition=disposition,
            route=_text(body.get("route"), "maintenance_review_item.route", maximum=40),
            priority=_int(
                body.get("priority"), "maintenance_review_item.priority", minimum=0, maximum=400
            ),
            target_path=_optional_text(
                body.get("target_path"), "maintenance_review_item.target_path", maximum=500
            ),
            target_address=_optional_text(
                body.get("target_address"), "maintenance_review_item.target_address", maximum=180
            ),
            reason=_text(body.get("reason"), "maintenance_review_item.reason", maximum=500),
            reversible=_bool(body.get("reversible"), "maintenance_review_item.reversible"),
            approval_required=_bool(
                body.get("approval_required"), "maintenance_review_item.approval_required"
            ),
            estimated_bytes=_int(
                body.get("estimated_bytes"), "maintenance_review_item.estimated_bytes", minimum=0
            ),
            review_only=_bool(body.get("review_only"), "maintenance_review_item.review_only"),
            accepted=_bool(body.get("accepted"), "maintenance_review_item.accepted"),
            content_address=_text(
                body.get("content_address"), "maintenance_review_item.content_address"
            ),
        )


@dataclass(frozen=True, slots=True)
class StorageMaintenanceReviewQueue:
    """Closed, ordered reviewer projection for a maintenance plan."""

    plan_id: str
    plan_address: str
    state: StorageMaintenanceState
    items: tuple[StorageMaintenanceReviewItem, ...]
    accepted: bool
    content_address: str

    def _body(self) -> dict[str, Any]:
        return {
            "storage_maintenance_review_version": STORAGE_MAINTENANCE_REVIEW_VERSION,
            "plan_id": self.plan_id,
            "plan_address": self.plan_address,
            "state": self.state,
            "items": tuple(item.to_dict() for item in self.items),
            "accepted": self.accepted,
        }

    @property
    def item_count(self) -> int:
        return len(self.items)

    @property
    def blocked_count(self) -> int:
        return sum(
            item.disposition is StorageMaintenanceReviewDisposition.BLOCKED for item in self.items
        )

    @property
    def review_count(self) -> int:
        return sum(
            item.disposition is StorageMaintenanceReviewDisposition.REVIEW for item in self.items
        )

    def __post_init__(self) -> None:
        _text(self.plan_id, "maintenance_review_queue.plan_id", maximum=180)
        _text(self.plan_address, "maintenance_review_queue.plan_address", maximum=180)
        if not isinstance(self.state, StorageMaintenanceState):
            raise ValidationError("maintenance review queue state is invalid")
        if not self.items:
            raise ValidationError("maintenance review queue must contain at least one item")
        ids = tuple(item.review_id for item in self.items)
        if len(set(ids)) != len(ids):
            raise ValidationError("maintenance review item IDs must be unique")
        if any(
            item.plan_id != self.plan_id or item.plan_address != self.plan_address
            for item in self.items
        ):
            raise ValidationError("maintenance review queue item identity does not reconcile")
        ordered = tuple(sorted(self.items, key=lambda item: (-item.priority, item.review_id)))
        if ordered != self.items:
            raise ValidationError("maintenance review queue must be priority ordered")
        _bool(self.accepted, "maintenance_review_queue.accepted")
        expected = _address(self._body(), "storage-maintenance-review-queue")
        if expected != self.content_address:
            raise ValidationError("maintenance review queue content address does not reconcile")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            self._body()
            | {
                "boundary": STORAGE_MAINTENANCE_REVIEW_BOUNDARY,
                "item_count": self.item_count,
                "blocked_count": self.blocked_count,
                "review_count": self.review_count,
                "content_address": self.content_address,
            }
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StorageMaintenanceReviewQueue:
        body = _mapping(value, "maintenance review queue")
        allowed = {
            "storage_maintenance_review_version",
            "plan_id",
            "plan_address",
            "state",
            "items",
            "accepted",
            "boundary",
            "item_count",
            "blocked_count",
            "review_count",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(
                f"maintenance review queue contains unsupported fields: {sorted(unknown)}"
            )
        if body.get("storage_maintenance_review_version") != STORAGE_MAINTENANCE_REVIEW_VERSION:
            raise ValidationError("maintenance review queue version is invalid")
        raw_items = body.get("items")
        if not isinstance(raw_items, (list, tuple)):
            raise ValidationError("maintenance review queue items must be an array")
        try:
            state = StorageMaintenanceState(body.get("state"))
        except ValueError as exc:
            raise ValidationError("maintenance review queue state is invalid") from exc
        result = cls(
            plan_id=_text(body.get("plan_id"), "maintenance_review_queue.plan_id", maximum=180),
            plan_address=_text(
                body.get("plan_address"), "maintenance_review_queue.plan_address", maximum=180
            ),
            state=state,
            items=tuple(StorageMaintenanceReviewItem.from_mapping(item) for item in raw_items),
            accepted=_bool(body.get("accepted"), "maintenance_review_queue.accepted"),
            content_address=_text(
                body.get("content_address"), "maintenance_review_queue.content_address"
            ),
        )
        if body.get("boundary") not in (None, STORAGE_MAINTENANCE_REVIEW_BOUNDARY):
            raise ValidationError("maintenance review queue boundary is invalid")
        if body.get("item_count") != result.item_count:
            raise ValidationError("maintenance review queue item count does not reconcile")
        if body.get("blocked_count") != result.blocked_count:
            raise ValidationError("maintenance review queue blocked count does not reconcile")
        if body.get("review_count") != result.review_count:
            raise ValidationError("maintenance review queue review count does not reconcile")
        return result


@dataclass(frozen=True, slots=True)
class StorageMaintenanceReviewQuery:
    """Bounded, addressable review queue page."""

    plan_id: str
    queue_address: str
    filters: dict[str, Any]
    total: int
    offset: int
    limit: int
    items: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"has_more": self.has_more}


def _as_plan(value: StorageMaintenancePlan | Mapping[str, Any]) -> StorageMaintenancePlan:
    if isinstance(value, StorageMaintenancePlan):
        return value
    return StorageMaintenancePlan.from_mapping(value)


def _item(plan: StorageMaintenancePlan, action: Any) -> StorageMaintenanceReviewItem:
    disposition = _disposition_for(plan, action.kind)
    body = {
        "review_id": f"storage-maintenance-review-{action.action_id}",
        "plan_id": plan.plan_id,
        "plan_address": plan.content_address,
        "action_id": action.action_id,
        "kind": action.kind,
        "severity": action.severity,
        "disposition": disposition,
        "route": _route_for(action.kind),
        "priority": _priority_for(action.kind, action.severity),
        "target_path": action.target_path,
        "target_address": action.target_address,
        "reason": action.reason,
        "reversible": action.reversible,
        "approval_required": action.approval_required,
        "estimated_bytes": action.estimated_bytes,
        "review_only": action.review_only,
        "accepted": plan.accepted,
    }
    return StorageMaintenanceReviewItem(
        **body,
        content_address=content_hash(body, prefix="storage-maintenance-review-item"),
    )


def build_storage_maintenance_review_queue(
    plan: StorageMaintenancePlan | Mapping[str, Any],
) -> StorageMaintenanceReviewQueue:
    """Build the deterministic priority queue without creating assignments."""

    selected = _as_plan(plan)
    items = tuple(
        sorted(
            (_item(selected, action) for action in selected.actions),
            key=lambda item: (-item.priority, item.review_id),
        )
    )
    body = {
        "storage_maintenance_review_version": STORAGE_MAINTENANCE_REVIEW_VERSION,
        "plan_id": selected.plan_id,
        "plan_address": selected.content_address,
        "state": selected.state,
        "items": tuple(item.to_dict() for item in items),
        "accepted": selected.accepted,
    }
    return StorageMaintenanceReviewQueue(
        plan_id=selected.plan_id,
        plan_address=selected.content_address,
        state=selected.state,
        items=items,
        accepted=selected.accepted,
        content_address=content_hash(body, prefix="storage-maintenance-review-queue"),
    )


def query_storage_maintenance_review(
    queue: StorageMaintenanceReviewQueue | Mapping[str, Any],
    *,
    disposition: str | None = None,
    route: str | None = None,
    priority_min: int = 0,
    text: str | None = None,
    offset: int = 0,
    limit: int = STORAGE_MAINTENANCE_REVIEW_DEFAULT_LIMIT,
) -> StorageMaintenanceReviewQuery:
    """Return a bounded reviewer page with explicit routing filters."""

    selected = (
        queue
        if isinstance(queue, StorageMaintenanceReviewQueue)
        else StorageMaintenanceReviewQueue.from_mapping(queue)
    )
    disposition_filter = (
        None if disposition is None else _text(disposition, "disposition", maximum=40).lower()
    )
    route_filter = None if route is None else _text(route, "route", maximum=40).lower()
    priority_min = _int(priority_min, "priority_min", minimum=0, maximum=400)
    offset = _int(offset, "offset", minimum=0)
    limit = _int(limit, "limit", minimum=1, maximum=STORAGE_MAINTENANCE_REVIEW_MAX_LIMIT)
    text_filter = None if text is None else _text(text, "text", maximum=240).lower()
    if (
        disposition_filter is not None
        and disposition_filter not in STORAGE_MAINTENANCE_REVIEW_DISPOSITIONS
    ):
        raise ValidationError(f"unsupported maintenance review disposition: {disposition_filter}")
    if route_filter is not None and route_filter not in STORAGE_MAINTENANCE_REVIEW_ROUTES:
        raise ValidationError(f"unsupported maintenance review route: {route_filter}")
    items = selected.items
    if disposition_filter is not None:
        items = tuple(item for item in items if item.disposition.value == disposition_filter)
    if route_filter is not None:
        items = tuple(item for item in items if item.route == route_filter)
    items = tuple(item for item in items if item.priority >= priority_min)
    if text_filter:
        items = tuple(item for item in items if text_matches(item.to_dict(), text_filter))
    total = len(items)
    page = items[offset : offset + limit]
    filters = {
        "disposition": disposition,
        "route": route,
        "priority_min": priority_min,
        "text": text,
    }
    body = {
        "plan_id": selected.plan_id,
        "queue_address": selected.content_address,
        "filters": filters,
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": tuple(item.to_dict() for item in page),
        "accepted": selected.accepted,
    }
    return StorageMaintenanceReviewQuery(
        **body,
        content_address=content_hash(body, prefix="storage-maintenance-review-query"),
    )


def storage_maintenance_review_json(
    queue: StorageMaintenanceReviewQueue | Mapping[str, Any],
) -> str:
    """Serialize the queue as canonical JSON."""

    selected = (
        queue
        if isinstance(queue, StorageMaintenanceReviewQueue)
        else StorageMaintenanceReviewQueue.from_mapping(queue)
    )
    return canonical_json(selected.to_dict())


def storage_maintenance_review_csv(
    queue: StorageMaintenanceReviewQueue | Mapping[str, Any],
) -> str:
    """Serialize review rows as deterministic CSV."""

    selected = (
        queue
        if isinstance(queue, StorageMaintenanceReviewQueue)
        else StorageMaintenanceReviewQueue.from_mapping(queue)
    )
    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "review_id",
            "plan_id",
            "plan_address",
            "action_id",
            "kind",
            "severity",
            "disposition",
            "route",
            "priority",
            "target_path",
            "target_address",
            "reason",
            "reversible",
            "approval_required",
            "estimated_bytes",
            "review_only",
            "accepted",
            "content_address",
        )
    )
    for item in selected.items:
        writer.writerow(
            (
                item.review_id,
                item.plan_id,
                item.plan_address,
                item.action_id,
                item.kind.value,
                item.severity.value,
                item.disposition.value,
                item.route,
                item.priority,
                item.target_path or "",
                item.target_address or "",
                item.reason,
                str(item.reversible).lower(),
                str(item.approval_required).lower(),
                item.estimated_bytes,
                str(item.review_only).lower(),
                str(item.accepted).lower(),
                item.content_address,
            )
        )
    return output.getvalue()


def storage_maintenance_review_markdown(
    queue: StorageMaintenanceReviewQueue | Mapping[str, Any],
) -> str:
    """Serialize the queue as a reviewer-oriented Markdown table."""

    selected = (
        queue
        if isinstance(queue, StorageMaintenanceReviewQueue)
        else StorageMaintenanceReviewQueue.from_mapping(queue)
    )
    lines = [
        "# Storage maintenance review queue",
        "",
        f"- Plan: `{selected.plan_id}`",
        f"- Address: `{selected.plan_address}`",
        f"- State: `{selected.state.value}`",
        f"- Accepted: `{str(selected.accepted).lower()}`",
        f"- Items: {selected.item_count}",
        f"- Blocked: {selected.blocked_count}",
        f"- Review: {selected.review_count}",
        "",
        "| Priority | Disposition | Route | Kind | Target | Reason |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| {item.priority} | `{item.disposition.value}` | `{item.route}` | "
        f"`{item.kind.value}` | `{item.target_path or item.target_address or '-'}` | "
        f"{item.reason} |"
        for item in selected.items
    )
    return "\n".join(lines) + "\n"


def storage_maintenance_review_capabilities() -> dict[str, Any]:
    """Describe deterministic review-queue projections."""

    return {
        "version": STORAGE_MAINTENANCE_REVIEW_VERSION,
        "schema_version": STORAGE_MAINTENANCE_REVIEW_SCHEMA_VERSION,
        "boundary": STORAGE_MAINTENANCE_REVIEW_BOUNDARY,
        "priority_order": True,
        "route_projection": True,
        "blocked_projection": True,
        "bounded_query": True,
        "json_export": True,
        "csv_export": True,
        "markdown_export": True,
        "assignment_state": False,
        "execution_state": False,
        "timestamp_free": True,
        "dispositions": STORAGE_MAINTENANCE_REVIEW_DISPOSITIONS,
        "routes": STORAGE_MAINTENANCE_REVIEW_ROUTES,
    }


def storage_maintenance_review_schema() -> dict[str, Any]:
    """Return the closed review queue schema."""

    return {
        "version": STORAGE_MAINTENANCE_REVIEW_SCHEMA_VERSION,
        "type": "object",
        "boundary": STORAGE_MAINTENANCE_REVIEW_BOUNDARY,
        "required": (
            "storage_maintenance_review_version",
            "plan_id",
            "plan_address",
            "state",
            "items",
            "accepted",
            "content_address",
        ),
        "dispositions": STORAGE_MAINTENANCE_REVIEW_DISPOSITIONS,
        "routes": STORAGE_MAINTENANCE_REVIEW_ROUTES,
        "priority_order": "descending priority then review ID",
        "review_only": True,
        "assignment_state": False,
    }


__all__ = [
    name
    for name in globals()
    if name.startswith("STORAGE_MAINTENANCE_REVIEW")
    or name.startswith("StorageMaintenanceReview")
    or name.startswith("build_storage_maintenance_review")
    or name.startswith("query_storage_maintenance_review")
    or name.startswith("storage_maintenance_review")
]
