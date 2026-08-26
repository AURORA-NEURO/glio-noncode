"""Typed contracts for the address-only storage-lineage review queue."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

STORAGE_LINEAGE_REVIEW_VERSION = "storage-lineage-review-v1"
STORAGE_LINEAGE_REVIEW_SCHEMA_VERSION = "storage-lineage-review-schema-v1"
STORAGE_LINEAGE_REVIEW_BOUNDARY = "public_storage_lineage_review"
STORAGE_LINEAGE_REVIEW_MAX_ITEMS = 200_000
STORAGE_LINEAGE_REVIEW_DEFAULT_LIMIT = 50
STORAGE_LINEAGE_REVIEW_MAX_LIMIT = 500
STORAGE_LINEAGE_REVIEW_SEVERITIES = ("critical", "high", "medium", "low", "info")
STORAGE_LINEAGE_REVIEW_DISPOSITIONS = ("inspect", "reconcile", "monitor", "accepted")
STORAGE_LINEAGE_REVIEW_ISSUES = (
    "missing-reference",
    "orphan-object",
    "unreachable-node",
    "rejected-node",
    "rejected-edge",
    "empty-graph",
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


def _tuple_text(value: Any, field: str, *, maximum: int = 500) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValidationError(f"{field} must be an array")
    result = tuple(_text(item, f"{field}[]", maximum=maximum) for item in value)
    if tuple(sorted(set(result))) != result:
        raise ValidationError(f"{field} must be sorted and unique")
    return result


class StorageLineageReviewSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class StorageLineageReviewDisposition(StrEnum):
    INSPECT = "inspect"
    RECONCILE = "reconcile"
    MONITOR = "monitor"
    ACCEPTED = "accepted"


class StorageLineageReviewIssue(StrEnum):
    MISSING_REFERENCE = "missing-reference"
    ORPHAN_OBJECT = "orphan-object"
    UNREACHABLE_NODE = "unreachable-node"
    REJECTED_NODE = "rejected-node"
    REJECTED_EDGE = "rejected-edge"
    EMPTY_GRAPH = "empty-graph"


@dataclass(frozen=True, slots=True)
class StorageLineageReviewItem:
    """One stable, non-mutating review recommendation."""

    review_id: str
    target_id: str
    target_kind: str
    issue: StorageLineageReviewIssue
    severity: StorageLineageReviewSeverity
    priority: int
    disposition: StorageLineageReviewDisposition
    rationale: str
    evidence: tuple[str, ...]
    graph_address: str
    accepted: bool
    content_address: str

    def _body(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "target_id": self.target_id,
            "target_kind": self.target_kind,
            "issue": self.issue.value,
            "severity": self.severity.value,
            "priority": self.priority,
            "disposition": self.disposition.value,
            "rationale": self.rationale,
            "evidence": self.evidence,
            "graph_address": self.graph_address,
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        _text(self.review_id, "lineage_review_item.review_id", maximum=260)
        _text(self.target_id, "lineage_review_item.target_id", maximum=320)
        _text(self.target_kind, "lineage_review_item.target_kind", maximum=80)
        if not isinstance(self.issue, StorageLineageReviewIssue):
            raise ValidationError("lineage review issue is invalid")
        if not isinstance(self.severity, StorageLineageReviewSeverity):
            raise ValidationError("lineage review severity is invalid")
        _int(self.priority, "lineage_review_item.priority", minimum=0, maximum=1000)
        if not isinstance(self.disposition, StorageLineageReviewDisposition):
            raise ValidationError("lineage review disposition is invalid")
        _text(self.rationale, "lineage_review_item.rationale", maximum=600)
        _tuple_text(self.evidence, "lineage_review_item.evidence", maximum=360)
        _text(self.graph_address, "lineage_review_item.graph_address", maximum=180)
        _bool(self.accepted, "lineage_review_item.accepted")
        expected = content_hash(self._body(), prefix="storage-lineage-review-item")
        if self.content_address != expected:
            raise ValidationError("lineage review item address does not reconcile")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StorageLineageReviewItem:
        body = _mapping(value, "lineage review item")
        allowed = {
            "review_id", "target_id", "target_kind", "issue", "severity", "priority",
            "disposition", "rationale", "evidence", "graph_address", "accepted",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"lineage review item contains unsupported fields: {sorted(unknown)}")
        try:
            issue = StorageLineageReviewIssue(_text(body.get("issue"), "lineage_review_item.issue", maximum=80))
            severity = StorageLineageReviewSeverity(_text(body.get("severity"), "lineage_review_item.severity", maximum=40))
            disposition = StorageLineageReviewDisposition(_text(body.get("disposition"), "lineage_review_item.disposition", maximum=40))
        except ValueError as exc:
            raise ValidationError("lineage review enum value is invalid") from exc
        return cls(
            review_id=_text(body.get("review_id"), "lineage_review_item.review_id", maximum=260),
            target_id=_text(body.get("target_id"), "lineage_review_item.target_id", maximum=320),
            target_kind=_text(body.get("target_kind"), "lineage_review_item.target_kind", maximum=80),
            issue=issue,
            severity=severity,
            priority=_int(body.get("priority"), "lineage_review_item.priority", minimum=0, maximum=1000),
            disposition=disposition,
            rationale=_text(body.get("rationale"), "lineage_review_item.rationale", maximum=600),
            evidence=_tuple_text(body.get("evidence"), "lineage_review_item.evidence", maximum=360),
            graph_address=_text(body.get("graph_address"), "lineage_review_item.graph_address", maximum=180),
            accepted=_bool(body.get("accepted"), "lineage_review_item.accepted"),
            content_address=_text(body.get("content_address"), "lineage_review_item.content_address", maximum=180),
        )


@dataclass(frozen=True, slots=True)
class StorageLineageReviewQueue:
    """Closed, priority-ordered review projection for a lineage graph."""

    graph_address: str
    items: tuple[StorageLineageReviewItem, ...]
    issue_counts: tuple[tuple[str, int], ...]
    severity_counts: tuple[tuple[str, int], ...]
    accepted: bool
    content_address: str

    def _body(self) -> dict[str, Any]:
        return {
            "storage_lineage_review_version": STORAGE_LINEAGE_REVIEW_VERSION,
            "graph_address": self.graph_address,
            "items": tuple(item.to_dict() for item in self.items),
            "issue_counts": self.issue_counts,
            "severity_counts": self.severity_counts,
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        _text(self.graph_address, "lineage_review_queue.graph_address", maximum=180)
        if len(self.items) > STORAGE_LINEAGE_REVIEW_MAX_ITEMS:
            raise ValidationError("lineage review item count exceeds its contract")
        if tuple(item.graph_address for item in self.items) != (self.graph_address,) * len(self.items):
            raise ValidationError("lineage review item graph identity does not reconcile")
        sort_key = lambda item: (-item.priority, item.review_id)
        if tuple(sorted(self.items, key=sort_key)) != self.items:
            raise ValidationError("lineage review items are not priority ordered")
        for name, count in self.issue_counts:
            if name not in STORAGE_LINEAGE_REVIEW_ISSUES or _int(count, "lineage_review_queue.issue_count", minimum=0) < 0:
                raise ValidationError("lineage review issue counts are invalid")
        for name, count in self.severity_counts:
            if name not in STORAGE_LINEAGE_REVIEW_SEVERITIES or _int(count, "lineage_review_queue.severity_count", minimum=0) < 0:
                raise ValidationError("lineage review severity counts are invalid")
        if tuple(name for name, _count in self.issue_counts) != tuple(sorted(name for name, _count in self.issue_counts)):
            raise ValidationError("lineage review issue counts are not sorted")
        if tuple(name for name, _count in self.severity_counts) != tuple(sorted(name for name, _count in self.severity_counts)):
            raise ValidationError("lineage review severity counts are not sorted")
        _bool(self.accepted, "lineage_review_queue.accepted")
        expected = content_hash(self._body(), prefix="storage-lineage-review-queue")
        if self.content_address != expected:
            raise ValidationError("lineage review queue address does not reconcile")

    @property
    def item_count(self) -> int:
        return len(self.items)

    @property
    def requires_attention(self) -> bool:
        return any(item.disposition is not StorageLineageReviewDisposition.ACCEPTED for item in self.items)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StorageLineageReviewQueue:
        body = _mapping(value, "lineage review queue")
        allowed = {
            "storage_lineage_review_version", "graph_address", "items", "issue_counts",
            "severity_counts", "accepted", "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"lineage review queue contains unsupported fields: {sorted(unknown)}")
        raw_items = body.get("items")
        if not isinstance(raw_items, (list, tuple)):
            raise ValidationError("lineage review queue items must be an array")
        raw_issue = body.get("issue_counts")
        raw_severity = body.get("severity_counts")
        if not isinstance(raw_issue, (list, tuple)) or not isinstance(raw_severity, (list, tuple)):
            raise ValidationError("lineage review counts must be arrays")
        issue_counts = tuple((_text(item[0], "lineage_review_queue.issue_name", maximum=80), _int(item[1], "lineage_review_queue.issue_count", minimum=0)) for item in raw_issue if isinstance(item, (list, tuple)) and len(item) == 2)
        severity_counts = tuple((_text(item[0], "lineage_review_queue.severity_name", maximum=40), _int(item[1], "lineage_review_queue.severity_count", minimum=0)) for item in raw_severity if isinstance(item, (list, tuple)) and len(item) == 2)
        return cls(
            graph_address=_text(body.get("graph_address"), "lineage_review_queue.graph_address", maximum=180),
            items=tuple(StorageLineageReviewItem.from_mapping(item) for item in raw_items),
            issue_counts=issue_counts,
            severity_counts=severity_counts,
            accepted=_bool(body.get("accepted"), "lineage_review_queue.accepted"),
            content_address=_text(body.get("content_address"), "lineage_review_queue.content_address", maximum=180),
        )


__all__ = [
    name
    for name in globals()
    if name.startswith("STORAGE_LINEAGE_REVIEW")
    or name.startswith("StorageLineageReview")
]
