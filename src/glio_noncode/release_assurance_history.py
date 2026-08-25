"""Append-only audit history for whole-product release assurance."""

from __future__ import annotations

from .release_assurance_checkpoint import build_release_assurance_checkpoint
from .release_assurance_contracts import (
    ReleaseAssuranceHistory,
    ReleaseAssuranceHistoryEvent,
    ReleaseAssurancePlane,
    ReleaseAssuranceReviewQueue,
    ReleaseAssuranceRuntimeReport,
    ReleaseAssuranceState,
    check,
)
from .release_assurance_review import build_release_assurance_review_queue
from .release_assurance_support import csv_payload, markdown_payload, text_matches
from .serialization import content_hash


def _event(
    sequence: int,
    event_type: str,
    topic: str,
    state: ReleaseAssuranceState,
    input_address: str,
    output_address: str,
    accepted: bool,
) -> ReleaseAssuranceHistoryEvent:
    body = {
        "sequence": sequence,
        "event_id": f"history:{sequence:03d}:{event_type}:{topic}",
        "event_type": event_type,
        "topic": topic,
        "state": state,
        "input_address": input_address,
        "output_address": output_address,
        "accepted": accepted,
    }
    return ReleaseAssuranceHistoryEvent(
        **body,
        content_address=content_hash(body, prefix="release-assurance-history-event"),
    )


def build_release_assurance_history(
    runtime: ReleaseAssuranceRuntimeReport,
    *,
    review_queue: ReleaseAssuranceReviewQueue | None = None,
) -> ReleaseAssuranceHistory:
    """Build an append-only history from runtime, checkpoint, and review rows."""

    checkpoint = build_release_assurance_checkpoint(runtime)
    review = review_queue or build_release_assurance_review_queue(runtime)
    events: list[ReleaseAssuranceHistoryEvent] = []
    previous = runtime.snapshot.content_address
    for stage in runtime.stages:
        events.append(_event(
            len(events) + 1,
            "runtime-stage",
            stage.stage_id,
            stage.state,
            previous,
            stage.output_address,
            stage.state is ReleaseAssuranceState.READY,
        ))
        previous = stage.output_address
    for component, address, accepted in checkpoint.component_addresses:
        events.append(_event(
            len(events) + 1,
            "checkpoint-component",
            component,
            ReleaseAssuranceState.READY if accepted else ReleaseAssuranceState.BLOCKED,
            previous,
            address,
            accepted,
        ))
        previous = address
    for item in review.items:
        events.append(_event(
            len(events) + 1,
            "review-item",
            item.review_id,
            item.state,
            previous,
            item.content_address,
            item.accepted,
        ))
        previous = item.content_address
    accepted = runtime.accepted and checkpoint.accepted and review.accepted and all(item.accepted for item in events)
    body = {
        "bundle_id": runtime.snapshot.bundle_id,
        "run_id": runtime.run_id,
        "events": events,
        "accepted": accepted,
    }
    return ReleaseAssuranceHistory(
        runtime.snapshot.bundle_id,
        runtime.run_id,
        tuple(events),
        accepted,
        content_hash(body, prefix="release-assurance-history"),
    )


def audit_release_assurance_history(
    history: ReleaseAssuranceHistory,
    runtime: ReleaseAssuranceRuntimeReport,
) -> tuple:
    """Audit append-only sequence, identity, addresses, and run linkage."""

    ids = tuple(item.event_id for item in history.events)
    sequences = tuple(item.sequence for item in history.events)
    body = {
        "bundle_id": history.bundle_id,
        "run_id": history.run_id,
        "events": history.events,
        "accepted": history.accepted,
    }
    expected_address = content_hash(body, prefix="release-assurance-history")
    return (
        check("history:bundle", "history", ReleaseAssurancePlane.RUNTIME,
              history.bundle_id == runtime.snapshot.bundle_id, history.bundle_id,
              runtime.snapshot.bundle_id, "history bundle matches runtime"),
        check("history:run", "history", ReleaseAssurancePlane.RUNTIME,
              history.run_id == runtime.run_id, history.run_id, runtime.run_id,
              "history run matches runtime"),
        check("history:non-empty", "history", ReleaseAssurancePlane.RUNTIME,
              bool(history.events), len(history.events), ">0", "history retains events"),
        check("history:sequence", "history", ReleaseAssurancePlane.RUNTIME,
              sequences == tuple(range(1, len(sequences) + 1)), sequences[:3],
              "contiguous", "history is append-only and contiguous"),
        check("history:identities", "history", ReleaseAssurancePlane.RUNTIME,
              len(ids) == len(set(ids)), len(ids), len(set(ids)), "history identifiers are unique"),
        check("history:addresses", "history", ReleaseAssurancePlane.PUBLIC_BOUNDARY,
              all(item.input_address and item.output_address for item in history.events),
              sum(bool(item.input_address and item.output_address) for item in history.events),
              len(history.events), "every history event has input and output addresses"),
        check("history:accepted", "history", ReleaseAssurancePlane.RUNTIME,
              history.accepted == all(item.accepted for item in history.events),
              history.accepted, all(item.accepted for item in history.events),
              "history acceptance follows events"),
        check("history:address", "history", ReleaseAssurancePlane.PUBLIC_BOUNDARY,
              history.content_address == expected_address, history.content_address,
              expected_address, "history address is reproducible"),
    )


def query_release_assurance_history(
    history: ReleaseAssuranceHistory,
    *,
    event_type: str | None = None,
    state: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[ReleaseAssuranceHistoryEvent, ...]:
    """Return a bounded ordered history page."""

    if offset < 0 or limit < 1 or limit > 500:
        raise ValueError("release-assurance history pagination is outside its contract")
    rows = history.events
    if event_type:
        rows = tuple(item for item in rows if item.event_type == event_type)
    if state:
        rows = tuple(item for item in rows if item.state.value == state)
    if text:
        rows = tuple(item for item in rows if text_matches(item.to_dict(), text))
    return rows[offset : offset + limit]


def export_release_assurance_history_csv(history: ReleaseAssuranceHistory) -> bytes:
    """Export append-only history rows with stable columns."""

    return csv_payload(item.to_dict() for item in history.events)


def export_release_assurance_history_markdown(history: ReleaseAssuranceHistory) -> bytes:
    """Export a reviewer table for the append-only history."""

    return markdown_payload(
        "Release assurance history",
        (item.to_dict() for item in history.events),
    )


__all__ = [
    "audit_release_assurance_history",
    "build_release_assurance_history",
    "export_release_assurance_history_csv",
    "export_release_assurance_history_markdown",
    "query_release_assurance_history",
]
