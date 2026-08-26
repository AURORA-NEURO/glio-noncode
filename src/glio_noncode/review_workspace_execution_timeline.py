"""Bounded, typed timeline projections for review-plan execution ledgers.

The execution report already contains the complete replayed event chain, but
the original query contract was deliberately action-oriented.  This module
turns the chain into a first-class read model without introducing a second
store or a second ordering.  Every row keeps its ledger sequence, event
address, predecessor address, transition kind, public check references, and
the user-supplied occurrence instant.  Filtering is performed against the
verified replay projection, pagination is stable, and result addresses cover
the complete query contract.

The timeline is operational metadata only.  It does not expose raw evidence,
reviewer identity, agent identity, model metadata, programming-language
metadata, private contact fields, or a scientific conclusion.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .errors import ValidationError
from .module_fabric_support import contains_private_key
from .review_workspace_execution import (
    REVIEW_WORKSPACE_EXECUTION_MAX_EVENTS,
    ReviewPlanExecutionEvent,
    ReviewPlanExecutionEventKind,
    ReviewWorkspaceExecutionReport,
)
from .serialization import content_hash, jsonable


REVIEW_WORKSPACE_EXECUTION_TIMELINE_VERSION = "review-workspace-execution-timeline-v1"
REVIEW_WORKSPACE_EXECUTION_TIMELINE_SCHEMA_VERSION = (
    "review-workspace-execution-timeline-schema-v1"
)
REVIEW_WORKSPACE_EXECUTION_TIMELINE_QUERY_VERSION = (
    "review-workspace-execution-timeline-query-v1"
)
REVIEW_WORKSPACE_EXECUTION_TIMELINE_MAX_TEXT = 256
REVIEW_WORKSPACE_EXECUTION_TIMELINE_MAX_PAGE = 500

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
        raise ValidationError(f"{field} must not be blank")
    return normalized


def _optional_text(value: Any, field: str) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _parse_instant(value: Any, field: str) -> str:
    normalized = _text(value, field)
    iso_value = normalized[:-1] + "+00:00" if normalized.endswith("Z") else normalized
    try:
        parsed = datetime.fromisoformat(iso_value)
    except ValueError as exc:
        raise ValidationError(f"{field} must be an ISO-8601 instant") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat()


def _normalize_kind(value: Any) -> str | None:
    normalized = _optional_text(value, "kind")
    if normalized is None:
        return None
    normalized = normalized.casefold()
    if normalized not in {item.value for item in ReviewPlanExecutionEventKind}:
        raise ValidationError("timeline query kind is invalid")
    return normalized


def _facet(values: list[str] | tuple[str, ...]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionTimelineQuery:
    """Bounded filters for the ordered public execution event stream."""

    kind: str | None = None
    action_id: str | None = None
    event_id: str | None = None
    check_id: str | None = None
    reference_address: str | None = None
    text: str | None = None
    occurred_from: str | None = None
    occurred_to: str | None = None
    sequence_start: int = 0
    sequence_end: int | None = None
    offset: int = 0
    limit: int | None = 50

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _normalize_kind(self.kind))
        for name in (
            "action_id",
            "event_id",
            "check_id",
            "reference_address",
        ):
            value = _optional_text(getattr(self, name), name)
            object.__setattr__(self, name, value)
        if self.text is not None:
            text = str(self.text).strip()
            if len(text) > REVIEW_WORKSPACE_EXECUTION_TIMELINE_MAX_TEXT:
                raise ValidationError("timeline query text exceeds the bound")
            object.__setattr__(self, "text", text or None)
        else:
            object.__setattr__(self, "text", None)
        occurred_from = (
            None
            if self.occurred_from is None
            else _parse_instant(self.occurred_from, "occurred_from")
        )
        occurred_to = (
            None
            if self.occurred_to is None
            else _parse_instant(self.occurred_to, "occurred_to")
        )
        if occurred_from is not None and occurred_to is not None and occurred_from > occurred_to:
            raise ValidationError("timeline query occurred_from must not be after occurred_to")
        object.__setattr__(self, "occurred_from", occurred_from)
        object.__setattr__(self, "occurred_to", occurred_to)
        for name in ("sequence_start", "offset"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValidationError(f"timeline query {name} must be non-negative")
        if self.sequence_end is not None:
            if (
                isinstance(self.sequence_end, bool)
                or not isinstance(self.sequence_end, int)
                or self.sequence_end < self.sequence_start
            ):
                raise ValidationError("timeline query sequence_end is outside the sequence range")
        if self.limit is not None and (
            isinstance(self.limit, bool)
            or not isinstance(self.limit, int)
            or self.limit < 1
            or self.limit > REVIEW_WORKSPACE_EXECUTION_TIMELINE_MAX_PAGE
        ):
            raise ValidationError("timeline query limit is outside the bound")

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any] | None,
    ) -> "ReviewWorkspaceExecutionTimelineQuery":
        if raw is None:
            return cls()
        if not isinstance(raw, Mapping):
            raise ValidationError("timeline query must be an object")
        return cls(
            kind=raw.get("kind", raw.get("event_kind")),
            action_id=raw.get("action_id"),
            event_id=raw.get("event_id"),
            check_id=raw.get("check_id"),
            reference_address=raw.get("reference_address"),
            text=raw.get("text"),
            occurred_from=raw.get("occurred_from"),
            occurred_to=raw.get("occurred_to"),
            sequence_start=int(raw.get("sequence_start", 0)),
            sequence_end=(
                None
                if raw.get("sequence_end") is None
                else int(raw.get("sequence_end"))
            ),
            offset=int(raw.get("offset", 0)),
            limit=None if raw.get("limit") is None else int(raw.get("limit", 50)),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionTimelineRow:
    """One sequence-preserving row in an execution event timeline."""

    sequence: int
    event: ReviewPlanExecutionEvent
    content_address: str

    def __post_init__(self) -> None:
        if (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence < 0
        ):
            raise ValidationError("timeline row sequence must be non-negative")
        if not isinstance(self.event, ReviewPlanExecutionEvent):
            raise ValidationError("timeline row requires a typed execution event")

    @classmethod
    def build(cls, sequence: int, event: ReviewPlanExecutionEvent) -> "ReviewWorkspaceExecutionTimelineRow":
        body = {"sequence": sequence, "event": event.to_dict()}
        return cls(
            sequence=sequence,
            event=event,
            content_address=content_hash(body, prefix="review-workspace-execution-timeline-row"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "event": self.event.to_dict(),
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionTimelineResult:
    """A deterministic, bounded event timeline page and complete-match facets."""

    execution_address: str
    query: ReviewWorkspaceExecutionTimelineQuery
    rows: tuple[ReviewWorkspaceExecutionTimelineRow, ...]
    total_count: int
    has_more: bool
    facets: Mapping[str, Mapping[str, int]]
    first_sequence: int | None
    last_sequence: int | None
    accepted: bool
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _event_text(event: ReviewPlanExecutionEvent) -> str:
    return " ".join(
        (
            event.event_id,
            event.plan_id,
            event.plan_address,
            event.action_id,
            event.kind.value,
            event.occurred_at,
            event.reason,
            *event.check_ids,
            *event.reference_addresses,
            event.previous_event_address or "",
            event.content_address,
        )
    ).casefold()


def _event_matches(
    sequence: int,
    event: ReviewPlanExecutionEvent,
    query: ReviewWorkspaceExecutionTimelineQuery,
) -> bool:
    if query.kind is not None and event.kind.value != query.kind:
        return False
    if query.action_id is not None and event.action_id != query.action_id:
        return False
    if query.event_id is not None and event.event_id != query.event_id:
        return False
    if query.check_id is not None and query.check_id not in event.check_ids:
        return False
    if query.reference_address is not None and query.reference_address not in event.reference_addresses:
        return False
    if sequence < query.sequence_start:
        return False
    if query.sequence_end is not None and sequence > query.sequence_end:
        return False
    if query.occurred_from is not None and event.occurred_at < query.occurred_from:
        return False
    if query.occurred_to is not None and event.occurred_at > query.occurred_to:
        return False
    if query.text is not None and query.text.casefold() not in _event_text(event):
        return False
    return True


def query_review_workspace_execution_timeline(
    report: ReviewWorkspaceExecutionReport,
    query: ReviewWorkspaceExecutionTimelineQuery | Mapping[str, Any] | None = None,
) -> ReviewWorkspaceExecutionTimelineResult:
    """Return a stable page over the report's replay-verified event chain."""

    if not isinstance(report, ReviewWorkspaceExecutionReport):
        raise ValidationError("timeline query requires a typed execution report")
    selected = (
        query
        if isinstance(query, ReviewWorkspaceExecutionTimelineQuery)
        else ReviewWorkspaceExecutionTimelineQuery.from_mapping(query)
    )
    boundary_valid = not contains_private_key(report.to_dict())
    matched = tuple(
        (sequence, event)
        for sequence, event in enumerate(report.events)
        if _event_matches(sequence, event, selected)
    )
    page_matches = (
        matched[selected.offset:]
        if selected.limit is None
        else matched[selected.offset : selected.offset + selected.limit]
    )
    rows = tuple(ReviewWorkspaceExecutionTimelineRow.build(sequence, event) for sequence, event in page_matches)
    matched_events = [event for _, event in matched]
    facets = {
        "kinds": _facet([event.kind.value for event in matched_events]),
        "action_ids": _facet([event.action_id for event in matched_events]),
        "check_ids": _facet([check_id for event in matched_events for check_id in event.check_ids]),
        "reference_addresses": _facet(
            [address for event in matched_events for address in event.reference_addresses]
        ),
    }
    body = {
        "timeline_version": REVIEW_WORKSPACE_EXECUTION_TIMELINE_VERSION,
        "execution_address": report.content_address,
        "query": selected,
        "rows": rows,
        "total_count": len(matched),
        "has_more": selected.offset + len(rows) < len(matched),
        "facets": facets,
        "first_sequence": rows[0].sequence if rows else None,
        "last_sequence": rows[-1].sequence if rows else None,
        "accepted": report.accepted and boundary_valid,
        "warnings": report.warnings,
    }
    return ReviewWorkspaceExecutionTimelineResult(
        execution_address=report.content_address,
        query=selected,
        rows=rows,
        total_count=len(matched),
        has_more=selected.offset + len(rows) < len(matched),
        facets=facets,
        first_sequence=rows[0].sequence if rows else None,
        last_sequence=rows[-1].sequence if rows else None,
        accepted=report.accepted and boundary_valid,
        warnings=report.warnings,
        content_address=content_hash(body, prefix="review-workspace-execution-timeline-query"),
    )


def query_review_workspace_execution_events(
    report: ReviewWorkspaceExecutionReport,
    query: ReviewWorkspaceExecutionTimelineQuery | Mapping[str, Any] | None = None,
) -> ReviewWorkspaceExecutionTimelineResult:
    """Readable alias for callers that prefer the event-oriented name."""

    return query_review_workspace_execution_timeline(report, query)


def review_workspace_execution_timeline_schema() -> dict[str, Any]:
    """Return the public contract for timeline filters and result semantics."""

    return {
        "version": REVIEW_WORKSPACE_EXECUTION_TIMELINE_SCHEMA_VERSION,
        "timeline_version": REVIEW_WORKSPACE_EXECUTION_TIMELINE_VERSION,
        "query_version": REVIEW_WORKSPACE_EXECUTION_TIMELINE_QUERY_VERSION,
        "type": "ordered_event_timeline",
        "ordering": {
            "field": "sequence",
            "direction": "ascending",
            "meaning": "zero-based position in the replay-verified append-only ledger",
        },
        "event_kinds": [item.value for item in ReviewPlanExecutionEventKind],
        "filters": {
            "kind": "exact event transition kind",
            "action_id": "exact action identifier",
            "event_id": "exact event identifier",
            "check_id": "event contains check identifier",
            "reference_address": "event contains public reference address",
            "text": "case-insensitive bounded search across public event fields",
            "occurred_from": "inclusive UTC instant lower bound",
            "occurred_to": "inclusive UTC instant upper bound",
            "sequence_start": "inclusive zero-based sequence lower bound",
            "sequence_end": "inclusive zero-based sequence upper bound",
            "offset": "bounded page offset",
            "limit": "bounded page size",
        },
        "result": {
            "rows": "typed event rows with sequence and row address",
            "facets": ["kinds", "action_ids", "check_ids", "reference_addresses"],
            "complete_match_facets": True,
            "has_more": True,
            "first_sequence": True,
            "last_sequence": True,
        },
        "limits": {
            "max_events": REVIEW_WORKSPACE_EXECUTION_MAX_EVENTS,
            "max_text": REVIEW_WORKSPACE_EXECUTION_TIMELINE_MAX_TEXT,
            "max_page": REVIEW_WORKSPACE_EXECUTION_TIMELINE_MAX_PAGE,
        },
        "boundary": {
            "raw_evidence": False,
            "reviewer_identity": False,
            "agent_identity": False,
            "model_metadata": False,
            "programming_language_metadata": False,
            "scientific_decision": False,
            "forbidden_keys": sorted(_FORBIDDEN_KEYS),
        },
    }


def review_workspace_execution_timeline_capabilities() -> dict[str, Any]:
    """Return capability metadata without case-specific event rows."""

    return {
        "version": REVIEW_WORKSPACE_EXECUTION_TIMELINE_VERSION,
        "ordered_event_rows": True,
        "sequence_pagination": True,
        "transition_filtering": True,
        "action_and_check_facets": True,
        "reference_address_filtering": True,
        "occurrence_range_filtering": True,
        "case_insensitive_public_text_search": True,
        "complete_match_facets": True,
        "deterministic_content_address": True,
        "replay_projection_only": True,
        "public_boundary_audit": True,
        "api_read_surface": True,
        "cli_read_surface": True,
    }


__all__ = [
    "REVIEW_WORKSPACE_EXECUTION_TIMELINE_MAX_PAGE",
    "REVIEW_WORKSPACE_EXECUTION_TIMELINE_MAX_TEXT",
    "REVIEW_WORKSPACE_EXECUTION_TIMELINE_QUERY_VERSION",
    "REVIEW_WORKSPACE_EXECUTION_TIMELINE_SCHEMA_VERSION",
    "REVIEW_WORKSPACE_EXECUTION_TIMELINE_VERSION",
    "ReviewWorkspaceExecutionTimelineQuery",
    "ReviewWorkspaceExecutionTimelineResult",
    "ReviewWorkspaceExecutionTimelineRow",
    "query_review_workspace_execution_events",
    "query_review_workspace_execution_timeline",
    "review_workspace_execution_timeline_capabilities",
    "review_workspace_execution_timeline_schema",
]
