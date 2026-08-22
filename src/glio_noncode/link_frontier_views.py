"""Review and source views for Domain 10 link frontier evidence."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from .link_frontier_fixture_eval import LinkFrontierEvaluation
from .link_frontier_public_data import LinkFrontierFixture, LinkFrontierOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkFrontierReviewRow:
    record_id: str
    operation: LinkFrontierOperation
    role: str
    state: str
    priority: int
    issue_codes: tuple[str, ...]
    action: str
    context_key: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkFrontierSourceRow:
    source_id: str
    title: str
    uri: str
    source_kind: str
    release: str
    scope: str
    record_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkFrontierView:
    fixture_id: str
    context_key: str
    evidence_boundary: str
    review_queue: tuple[LinkFrontierReviewRow, ...]
    sources: tuple[LinkFrontierSourceRow, ...]
    review_count: int
    source_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_link_frontier_view(fixture: LinkFrontierFixture, evaluation: LinkFrontierEvaluation) -> LinkFrontierView:
    execution_map = evaluation.execution_map()
    review_rows: list[LinkFrontierReviewRow] = []
    for record in fixture.records:
        execution = execution_map[record.record_id]
        if execution.accepted:
            continue
        priority = 3 if execution.state == "invalid" else 2 if execution.issue_codes else 1
        action = "quarantine malformed input" if execution.state == "invalid" else "review threshold or missing evidence"
        body = {
            "record_id": record.record_id,
            "operation": record.operation,
            "role": record.role.value,
            "state": execution.state,
            "priority": priority,
            "issue_codes": execution.issue_codes,
            "action": action,
            "context_key": record.context_key,
        }
        review_rows.append(LinkFrontierReviewRow(**body, content_address=content_hash(body)))
    source_rows: list[LinkFrontierSourceRow] = []
    for source in fixture.sources:
        count = sum(source.source_id in record.source_ids for record in fixture.records)
        body = {
            "source_id": source.source_id,
            "title": source.title,
            "uri": source.uri,
            "source_kind": source.source_kind,
            "release": source.release,
            "scope": source.scope,
            "record_count": count,
        }
        source_rows.append(LinkFrontierSourceRow(**body, content_address=content_hash(body)))
    body = {
        "fixture_id": fixture.fixture_id,
        "context_key": fixture.context_key,
        "evidence_boundary": fixture.evidence_boundary,
        "review_queue": tuple(review_rows),
        "sources": tuple(source_rows),
        "review_count": len(review_rows),
        "source_count": len(source_rows),
    }
    return LinkFrontierView(**body, content_address=content_hash(body))


def filter_link_frontier_review_queue(view: LinkFrontierView, *, operation: LinkFrontierOperation | None = None, minimum_priority: int = 1) -> tuple[LinkFrontierReviewRow, ...]:
    return tuple(item for item in view.review_queue if item.priority >= minimum_priority and (operation is None or item.operation is operation))


def link_frontier_review_summary(view: LinkFrontierView) -> dict[str, Any]:
    states = Counter(item.state for item in view.review_queue)
    operations = Counter(item.operation.value for item in view.review_queue)
    issues = Counter(code for item in view.review_queue for code in item.issue_codes)
    return {
        "fixture_id": view.fixture_id,
        "review_count": view.review_count,
        "source_count": view.source_count,
        "state_counts": dict(sorted(states.items())),
        "operation_counts": dict(sorted(operations.items())),
        "issue_counts": dict(sorted(issues.items())),
        "content_address": content_hash((view.fixture_id, tuple(view.review_queue))),
    }


__all__ = ["LinkFrontierReviewRow", "LinkFrontierSourceRow", "LinkFrontierView", "build_link_frontier_view", "filter_link_frontier_review_queue", "link_frontier_review_summary"]
