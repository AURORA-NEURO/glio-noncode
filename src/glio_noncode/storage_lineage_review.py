"""Build and query a deterministic, non-mutating lineage review queue."""

from __future__ import annotations

import csv
from collections.abc import Mapping
from io import StringIO
from typing import Any

from .errors import ValidationError
from .release_assurance_support import text_matches
from .serialization import canonical_json, content_hash
from .storage_lineage import build_storage_lineage
from .storage_lineage_contracts import StorageLineageGraph, StorageLineageNodeKind
from .storage_lineage_review_contracts import (
    STORAGE_LINEAGE_REVIEW_BOUNDARY,
    STORAGE_LINEAGE_REVIEW_DEFAULT_LIMIT,
    STORAGE_LINEAGE_REVIEW_DISPOSITIONS,
    STORAGE_LINEAGE_REVIEW_ISSUES,
    STORAGE_LINEAGE_REVIEW_MAX_LIMIT,
    STORAGE_LINEAGE_REVIEW_SCHEMA_VERSION,
    STORAGE_LINEAGE_REVIEW_SEVERITIES,
    STORAGE_LINEAGE_REVIEW_VERSION,
    StorageLineageReviewDisposition,
    StorageLineageReviewIssue,
    StorageLineageReviewItem,
    StorageLineageReviewQueue,
    StorageLineageReviewSeverity,
)
from .runtime import CaseRuntime


def _text(value: Any, field: str, *, maximum: int = 500) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    result = str(value).strip()
    if not result:
        raise ValidationError(f"{field} must not be empty")
    if len(result) > maximum:
        raise ValidationError(f"{field} exceeds the maximum length")
    return result


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


def _as_graph(value: StorageLineageGraph | CaseRuntime | Mapping[str, Any]) -> StorageLineageGraph:
    if isinstance(value, StorageLineageGraph):
        return value
    if isinstance(value, CaseRuntime):
        return build_storage_lineage(value)
    if isinstance(value, Mapping):
        return StorageLineageGraph.from_mapping(value)
    raise ValidationError("lineage review requires a graph or case runtime")


def _make_item(
    *,
    graph: StorageLineageGraph,
    target_id: str,
    target_kind: str,
    issue: StorageLineageReviewIssue,
    severity: StorageLineageReviewSeverity,
    priority: int,
    disposition: StorageLineageReviewDisposition,
    rationale: str,
    evidence: tuple[str, ...],
) -> StorageLineageReviewItem:
    review_id = f"storage-lineage-review-{len(evidence):02d}-{priority:04d}-{target_id}"
    body = {
        "review_id": review_id,
        "target_id": target_id,
        "target_kind": target_kind,
        "issue": issue.value,
        "severity": severity.value,
        "priority": priority,
        "disposition": disposition.value,
        "rationale": rationale,
        "evidence": tuple(sorted(evidence)),
        "graph_address": graph.content_address,
        "accepted": disposition is StorageLineageReviewDisposition.ACCEPTED,
    }
    return StorageLineageReviewItem(
        review_id=review_id,
        target_id=target_id,
        target_kind=target_kind,
        issue=issue,
        severity=severity,
        priority=priority,
        disposition=disposition,
        rationale=rationale,
        evidence=tuple(sorted(evidence)),
        graph_address=graph.content_address,
        accepted=disposition is StorageLineageReviewDisposition.ACCEPTED,
        content_address=content_hash(body, prefix="storage-lineage-review-item"),
    )


def _item_for_node(graph: StorageLineageGraph, node: Any) -> StorageLineageReviewItem | None:
    if node.kind is StorageLineageNodeKind.MISSING:
        return _make_item(
            graph=graph,
            target_id=node.node_id,
            target_kind=node.kind.value,
            issue=StorageLineageReviewIssue.MISSING_REFERENCE,
            severity=StorageLineageReviewSeverity.CRITICAL,
            priority=100,
            disposition=StorageLineageReviewDisposition.RECONCILE,
            rationale="A persisted pointer or reference names an address that is not present in the object store.",
            evidence=(node.address or node.node_id, f"incoming:{node.in_degree}"),
        )
    if node.kind is StorageLineageNodeKind.ORPHAN:
        return _make_item(
            graph=graph,
            target_id=node.node_id,
            target_kind=node.kind.value,
            issue=StorageLineageReviewIssue.ORPHAN_OBJECT,
            severity=StorageLineageReviewSeverity.HIGH,
            priority=80,
            disposition=StorageLineageReviewDisposition.INSPECT,
            rationale="An accepted object is present in storage but has no reachable pointer from a run or batch root.",
            evidence=(node.address or node.node_id, f"incoming:{node.in_degree}", f"outgoing:{node.out_degree}"),
        )
    if not node.accepted:
        return _make_item(
            graph=graph,
            target_id=node.node_id,
            target_kind=node.kind.value,
            issue=StorageLineageReviewIssue.REJECTED_NODE,
            severity=StorageLineageReviewSeverity.HIGH,
            priority=75,
            disposition=StorageLineageReviewDisposition.INSPECT,
            rationale="The graph node failed its storage acceptance contract and should not be treated as trusted provenance.",
            evidence=(f"depth:{node.depth}", f"incoming:{node.in_degree}", f"outgoing:{node.out_degree}"),
        )
    if not node.root and node.depth == 0:
        return _make_item(
            graph=graph,
            target_id=node.node_id,
            target_kind=node.kind.value,
            issue=StorageLineageReviewIssue.UNREACHABLE_NODE,
            severity=StorageLineageReviewSeverity.MEDIUM,
            priority=60,
            disposition=StorageLineageReviewDisposition.MONITOR,
            rationale="The node is not reachable from a persisted run or batch root in the current graph projection.",
            evidence=(f"depth:{node.depth}", f"incoming:{node.in_degree}", f"outgoing:{node.out_degree}"),
        )
    return None


def _item_for_edge(graph: StorageLineageGraph, edge: Any) -> StorageLineageReviewItem | None:
    if edge.accepted:
        return None
    return _make_item(
        graph=graph,
        target_id=edge.edge_id,
        target_kind=edge.kind.value,
        issue=StorageLineageReviewIssue.REJECTED_EDGE,
        severity=StorageLineageReviewSeverity.HIGH,
        priority=70,
        disposition=StorageLineageReviewDisposition.INSPECT,
        rationale="The graph edge points to an unresolved address and cannot establish trusted reachability.",
        evidence=(edge.source_id, edge.target_id, edge.field),
    )


def build_storage_lineage_review_queue(
    source: StorageLineageGraph | CaseRuntime | Mapping[str, Any],
) -> StorageLineageReviewQueue:
    """Build priority-ordered recommendations without changing the store."""

    graph = _as_graph(source)
    items: list[StorageLineageReviewItem] = []
    for node in graph.nodes:
        item = _item_for_node(graph, node)
        if item is not None:
            items.append(item)
    for edge in graph.edges:
        item = _item_for_edge(graph, edge)
        if item is not None:
            items.append(item)
    if not graph.nodes:
        items.append(
            _make_item(
                graph=graph,
                target_id="storage-lineage:empty",
                target_kind="graph",
                issue=StorageLineageReviewIssue.EMPTY_GRAPH,
                severity=StorageLineageReviewSeverity.INFO,
                priority=10,
                disposition=StorageLineageReviewDisposition.MONITOR,
                rationale="The storage root is structurally empty; there is no persisted provenance to inspect.",
                evidence=("node_count:0", "edge_count:0"),
            )
        )
    items.sort(key=lambda item: (-item.priority, item.review_id))
    issue_counts = tuple(
        (name, sum(item.issue.value == name for item in items))
        for name in sorted(STORAGE_LINEAGE_REVIEW_ISSUES)
        if any(item.issue.value == name for item in items)
    )
    severity_counts = tuple(
        (name, sum(item.severity.value == name for item in items))
        for name in sorted(STORAGE_LINEAGE_REVIEW_SEVERITIES)
        if any(item.severity.value == name for item in items)
    )
    body = {
        "storage_lineage_review_version": STORAGE_LINEAGE_REVIEW_VERSION,
        "graph_address": graph.content_address,
        "items": tuple(item.to_dict() for item in items),
        "issue_counts": issue_counts,
        "severity_counts": severity_counts,
        "accepted": graph.accepted,
    }
    return StorageLineageReviewQueue(
        graph_address=graph.content_address,
        items=tuple(items),
        issue_counts=issue_counts,
        severity_counts=severity_counts,
        accepted=graph.accepted,
        content_address=content_hash(body, prefix="storage-lineage-review-queue"),
    )


def query_storage_lineage_review(
    source: StorageLineageReviewQueue | StorageLineageGraph | CaseRuntime | Mapping[str, Any],
    *,
    issue: str | None = None,
    severity: str | None = None,
    disposition: str | None = None,
    priority_min: int = 0,
    text: str | None = None,
    offset: int = 0,
    limit: int = STORAGE_LINEAGE_REVIEW_DEFAULT_LIMIT,
) -> tuple[StorageLineageReviewItem, ...]:
    """Return a bounded review page with explicit filters."""

    if isinstance(source, StorageLineageReviewQueue):
        queue = source
    elif isinstance(source, Mapping):
        queue = StorageLineageReviewQueue.from_mapping(source)
    else:
        queue = build_storage_lineage_review_queue(source)
    if issue is not None:
        issue = _text(issue, "issue", maximum=80).lower()
        if issue not in STORAGE_LINEAGE_REVIEW_ISSUES:
            raise ValidationError(f"unsupported lineage review issue: {issue}")
    if severity is not None:
        severity = _text(severity, "severity", maximum=40).lower()
        if severity not in STORAGE_LINEAGE_REVIEW_SEVERITIES:
            raise ValidationError(f"unsupported lineage review severity: {severity}")
    if disposition is not None:
        disposition = _text(disposition, "disposition", maximum=40).lower()
        if disposition not in STORAGE_LINEAGE_REVIEW_DISPOSITIONS:
            raise ValidationError(f"unsupported lineage review disposition: {disposition}")
    priority_min = _int(priority_min, "priority_min", minimum=0, maximum=1000)
    offset = _int(offset, "offset", minimum=0)
    limit = _int(limit, "limit", minimum=1, maximum=STORAGE_LINEAGE_REVIEW_MAX_LIMIT)
    selected = tuple(item for item in queue.items if item.priority >= priority_min)
    if issue is not None:
        selected = tuple(item for item in selected if item.issue.value == issue)
    if severity is not None:
        selected = tuple(item for item in selected if item.severity.value == severity)
    if disposition is not None:
        selected = tuple(item for item in selected if item.disposition.value == disposition)
    if text is not None:
        text_value = _text(text, "text", maximum=240).lower()
        selected = tuple(item for item in selected if text_matches(item.to_dict(), text_value))
    return selected[offset : offset + limit]


def storage_lineage_review_json(
    source: StorageLineageReviewQueue | StorageLineageGraph | CaseRuntime | Mapping[str, Any],
) -> str:
    if isinstance(source, StorageLineageReviewQueue):
        queue = source
    elif isinstance(source, Mapping):
        queue = StorageLineageReviewQueue.from_mapping(source)
    else:
        queue = build_storage_lineage_review_queue(source)
    return canonical_json(queue.to_dict())


def storage_lineage_review_csv(
    source: StorageLineageReviewQueue | StorageLineageGraph | CaseRuntime | Mapping[str, Any],
) -> str:
    if isinstance(source, StorageLineageReviewQueue):
        queue = source
    elif isinstance(source, Mapping):
        queue = StorageLineageReviewQueue.from_mapping(source)
    else:
        queue = build_storage_lineage_review_queue(source)
    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("review_id", "target_id", "target_kind", "issue", "severity", "priority", "disposition", "rationale", "evidence", "graph_address", "accepted", "content_address"))
    for item in queue.items:
        writer.writerow((item.review_id, item.target_id, item.target_kind, item.issue.value, item.severity.value, item.priority, item.disposition.value, item.rationale, "|".join(item.evidence), item.graph_address, str(item.accepted).lower(), item.content_address))
    return output.getvalue()


def storage_lineage_review_markdown(
    source: StorageLineageReviewQueue | StorageLineageGraph | CaseRuntime | Mapping[str, Any],
) -> str:
    queue = source if isinstance(source, StorageLineageReviewQueue) else build_storage_lineage_review_queue(source)
    lines = [
        "# Storage lineage review queue",
        "",
        f"- Graph: `{queue.graph_address}`",
        f"- Queue: `{queue.content_address}`",
        f"- Items: {queue.item_count}",
        f"- Requires attention: `{str(queue.requires_attention).lower()}`",
        "",
        "| Priority | Severity | Issue | Disposition | Target | Rationale |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| {item.priority} | `{item.severity.value}` | `{item.issue.value}` | `{item.disposition.value}` | `{item.target_id}` | {item.rationale} |"
        for item in queue.items
    )
    return "\n".join(lines) + "\n"


def storage_lineage_review_capabilities() -> dict[str, Any]:
    return {
        "version": STORAGE_LINEAGE_REVIEW_VERSION,
        "schema_version": STORAGE_LINEAGE_REVIEW_SCHEMA_VERSION,
        "boundary": STORAGE_LINEAGE_REVIEW_BOUNDARY,
        "missing_reference_review": True,
        "orphan_review": True,
        "unreachable_review": True,
        "rejected_state_review": True,
        "priority_ordering": True,
        "bounded_query": True,
        "csv_export": True,
        "markdown_export": True,
        "payload_exposure": False,
        "mutation": False,
        "timestamp_free": True,
        "issues": STORAGE_LINEAGE_REVIEW_ISSUES,
        "severities": STORAGE_LINEAGE_REVIEW_SEVERITIES,
        "dispositions": STORAGE_LINEAGE_REVIEW_DISPOSITIONS,
    }


def storage_lineage_review_schema() -> dict[str, Any]:
    return {
        "version": STORAGE_LINEAGE_REVIEW_SCHEMA_VERSION,
        "type": "object",
        "boundary": STORAGE_LINEAGE_REVIEW_BOUNDARY,
        "required": (
            "storage_lineage_review_version", "graph_address", "items", "issue_counts",
            "severity_counts", "accepted", "content_address",
        ),
        "item_required": (
            "review_id", "target_id", "target_kind", "issue", "severity", "priority",
            "disposition", "rationale", "evidence", "graph_address", "accepted", "content_address",
        ),
        "issues": STORAGE_LINEAGE_REVIEW_ISSUES,
        "severities": STORAGE_LINEAGE_REVIEW_SEVERITIES,
        "dispositions": STORAGE_LINEAGE_REVIEW_DISPOSITIONS,
        "payload_exposure": False,
        "timestamp_free": True,
    }


__all__ = [
    name
    for name in globals()
    if name.startswith("STORAGE_LINEAGE_")
    or name.startswith("StorageLineageReview")
    or name.startswith("build_storage_lineage_review")
    or name.startswith("query_storage_lineage_review")
    or name.startswith("storage_lineage_review")
]
