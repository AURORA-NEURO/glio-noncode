"""Deterministic attention and recovery operations for review execution.

The execution report answers *what state the ledger replays to* and the
metrics projection answers *how much operational work has moved*.  This module
adds the operator-facing queue between those views: blocked actions that need
an explicit recovery transition, ready actions that can be started, actions
waiting on declared dependencies, and in-progress actions that need an
explicit next transition.

The queue is a pure projection.  It never appends events, changes the plan,
reorders the ledger, assigns a person, or infers a scientific decision.  Every
item is derived from the public plan action and replayed action state, with a
stable rank, bounded rationale, and content address.
"""

from __future__ import annotations

import csv
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from io import StringIO
from typing import Any

from .errors import ValidationError
from .module_fabric_support import contains_private_key
from .review_workspace_execution import (
    ReviewPlanActionExecution,
    ReviewPlanExecutionStatus,
    ReviewWorkspaceExecutionReport,
)
from .review_workspace_execution_metrics import (
    ReviewWorkspaceExecutionMetrics,
    build_review_workspace_execution_metrics,
)
from .review_workspace_plan import ReviewPlanAction, ReviewWorkspacePlan
from .serialization import canonical_json, content_hash, jsonable


REVIEW_WORKSPACE_EXECUTION_OPERATIONS_VERSION = "review-workspace-execution-operations-v1"
REVIEW_WORKSPACE_EXECUTION_OPERATIONS_SCHEMA_VERSION = (
    "review-workspace-execution-operations-schema-v1"
)
REVIEW_WORKSPACE_EXECUTION_OPERATIONS_QUERY_VERSION = (
    "review-workspace-execution-operations-query-v1"
)
REVIEW_WORKSPACE_EXECUTION_OPERATIONS_DIFF_VERSION = (
    "review-workspace-execution-operations-diff-v1"
)
REVIEW_WORKSPACE_EXECUTION_OPERATIONS_DIFF_SCHEMA_VERSION = (
    "review-workspace-execution-operations-diff-schema-v1"
)
REVIEW_WORKSPACE_EXECUTION_OPERATIONS_MAX_ITEMS = 50_000
REVIEW_WORKSPACE_EXECUTION_OPERATIONS_MAX_RATIONALE = 512
REVIEW_WORKSPACE_EXECUTION_OPERATIONS_MAX_TEXT = 256
REVIEW_WORKSPACE_EXECUTION_OPERATIONS_MAX_PAGE = 500


class ReviewWorkspaceExecutionAttentionKind(StrEnum):
    """Operational queue classes ordered from urgent recovery to waiting work."""

    BLOCKED = "blocked"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    DEPENDENCY_WAIT = "dependency_wait"
    SKIPPED = "skipped"
    QUEUED = "queued"


_RANKS = {
    ReviewWorkspaceExecutionAttentionKind.BLOCKED: 0,
    ReviewWorkspaceExecutionAttentionKind.READY: 1,
    ReviewWorkspaceExecutionAttentionKind.IN_PROGRESS: 2,
    ReviewWorkspaceExecutionAttentionKind.DEPENDENCY_WAIT: 3,
    ReviewWorkspaceExecutionAttentionKind.SKIPPED: 4,
    ReviewWorkspaceExecutionAttentionKind.QUEUED: 5,
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


def _address(body: Any, prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def _optional_text(value: Any, field: str) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _normalize_enum(value: Any, field: str, values: set[str]) -> str | None:
    normalized = _optional_text(value, field)
    if normalized is None:
        return None
    normalized = normalized.casefold()
    if normalized not in values:
        raise ValidationError(f"{field} is invalid")
    return normalized


def _normalize_optional_bool(value: Any, field: str) -> bool | None:
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


def _facet(values: list[str] | tuple[str, ...]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _rationale(kind: ReviewWorkspaceExecutionAttentionKind, action: ReviewPlanActionExecution) -> str:
    values = {
        ReviewWorkspaceExecutionAttentionKind.BLOCKED: (
            "action is blocked and requires an explicit recovery or reopen transition"
        ),
        ReviewWorkspaceExecutionAttentionKind.READY: (
            "action is ready because all declared dependencies are complete"
        ),
        ReviewWorkspaceExecutionAttentionKind.IN_PROGRESS: (
            "action is in progress and requires an explicit completion, block, or skip transition"
        ),
        ReviewWorkspaceExecutionAttentionKind.DEPENDENCY_WAIT: (
            "action is open but waits on declared dependencies"
        ),
        ReviewWorkspaceExecutionAttentionKind.SKIPPED: (
            "action was skipped and requires an explicit reopen transition to resume"
        ),
        ReviewWorkspaceExecutionAttentionKind.QUEUED: "action remains open in the execution queue",
    }
    value = values[kind]
    if len(value) > REVIEW_WORKSPACE_EXECUTION_OPERATIONS_MAX_RATIONALE:
        return value[:REVIEW_WORKSPACE_EXECUTION_OPERATIONS_MAX_RATIONALE]
    return value


def _transition(kind: ReviewWorkspaceExecutionAttentionKind) -> str:
    return {
        ReviewWorkspaceExecutionAttentionKind.BLOCKED: "reopen_or_block",
        ReviewWorkspaceExecutionAttentionKind.READY: "start",
        ReviewWorkspaceExecutionAttentionKind.IN_PROGRESS: "complete_or_block_or_skip",
        ReviewWorkspaceExecutionAttentionKind.DEPENDENCY_WAIT: "complete_dependencies_first",
        ReviewWorkspaceExecutionAttentionKind.SKIPPED: "reopen",
        ReviewWorkspaceExecutionAttentionKind.QUEUED: "inspect",
    }[kind]


def _kind(action: ReviewPlanActionExecution) -> ReviewWorkspaceExecutionAttentionKind:
    if action.status is ReviewPlanExecutionStatus.BLOCKED:
        return ReviewWorkspaceExecutionAttentionKind.BLOCKED
    if action.status is ReviewPlanExecutionStatus.SKIPPED:
        return ReviewWorkspaceExecutionAttentionKind.SKIPPED
    if action.status is ReviewPlanExecutionStatus.IN_PROGRESS:
        return ReviewWorkspaceExecutionAttentionKind.IN_PROGRESS
    if action.unresolved_dependencies:
        return ReviewWorkspaceExecutionAttentionKind.DEPENDENCY_WAIT
    if action.ready:
        return ReviewWorkspaceExecutionAttentionKind.READY
    return ReviewWorkspaceExecutionAttentionKind.QUEUED


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionAttentionItem:
    """One ranked public action in the operational attention queue."""

    rank: int
    action_id: str
    queue_item_id: str
    target_id: str
    title: str
    purpose: str
    lane: str
    action_kind: str
    priority: int
    sequence: int
    status: str
    attention_kind: ReviewWorkspaceExecutionAttentionKind
    ready: bool
    unresolved_dependencies: tuple[str, ...]
    dependency_count: int
    event_count: int
    estimate_units: int
    rationale: str
    recommended_transition: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionOperations:
    """Complete attention queue and operational counters for one execution."""

    execution_id: str
    execution_address: str
    plan_id: str
    plan_address: str
    workspace_id: str
    run_id: str
    case_id: str
    version: str
    operations_version: str
    state: str
    accepted: bool
    queue_count: int
    total_action_count: int
    completed_action_count: int
    blocked_action_ids: tuple[str, ...]
    ready_action_ids: tuple[str, ...]
    in_progress_action_ids: tuple[str, ...]
    dependency_wait_action_ids: tuple[str, ...]
    skipped_action_ids: tuple[str, ...]
    attention_kind_counts: Mapping[str, int]
    lane_queue_counts: Mapping[str, int]
    recommended_action_ids: tuple[str, ...]
    recommended_transition: str
    metrics_address: str
    items: tuple[ReviewWorkspaceExecutionAttentionItem, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionOperationsQuery:
    """Bounded filters for the ranked public execution attention queue."""

    attention_kind: str | None = None
    status: str | None = None
    lane: str | None = None
    action_kind: str | None = None
    action_id: str | None = None
    priority: int | None = None
    text: str | None = None
    ready: bool | None = None
    dependency_action_id: str | None = None
    offset: int = 0
    limit: int | None = 50

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "attention_kind",
            _normalize_enum(
                self.attention_kind,
                "attention_kind",
                {item.value for item in ReviewWorkspaceExecutionAttentionKind},
            ),
        )
        object.__setattr__(
            self,
            "status",
            _normalize_enum(
                self.status,
                "status",
                {item.value for item in ReviewPlanExecutionStatus},
            ),
        )
        for name in ("lane", "action_kind", "action_id", "dependency_action_id"):
            object.__setattr__(self, name, _optional_text(getattr(self, name), name))
        if self.priority is not None and (
            isinstance(self.priority, bool) or not isinstance(self.priority, int)
        ):
            raise ValidationError("operations query priority must be an integer")
        if self.text is not None:
            text = str(self.text).strip()
            if len(text) > REVIEW_WORKSPACE_EXECUTION_OPERATIONS_MAX_TEXT:
                raise ValidationError("operations query text exceeds the bound")
            object.__setattr__(self, "text", text or None)
        else:
            object.__setattr__(self, "text", None)
        object.__setattr__(self, "ready", _normalize_optional_bool(self.ready, "ready"))
        for name in ("offset",):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValidationError(f"operations query {name} must be non-negative")
        if self.limit is not None and (
            isinstance(self.limit, bool)
            or not isinstance(self.limit, int)
            or self.limit < 1
            or self.limit > REVIEW_WORKSPACE_EXECUTION_OPERATIONS_MAX_PAGE
        ):
            raise ValidationError("operations query limit is outside the bound")

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any] | None,
    ) -> "ReviewWorkspaceExecutionOperationsQuery":
        if raw is None:
            return cls()
        if not isinstance(raw, Mapping):
            raise ValidationError("operations query must be an object")
        priority = raw.get("priority")
        return cls(
            attention_kind=raw.get("attention_kind"),
            status=raw.get("status"),
            lane=raw.get("lane"),
            action_kind=raw.get("action_kind"),
            action_id=raw.get("action_id"),
            priority=None if priority in (None, "") else int(priority),
            text=raw.get("text"),
            ready=raw.get("ready"),
            dependency_action_id=raw.get("dependency_action_id"),
            offset=int(raw.get("offset", 0)),
            limit=None if raw.get("limit") is None else int(raw.get("limit", 50)),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionOperationsQueryResult:
    """A deterministic page and complete-match facets for queue queries."""

    execution_address: str
    operations_address: str
    operations_version: str
    operations_query_version: str
    queue_count: int
    query: ReviewWorkspaceExecutionOperationsQuery
    rows: tuple[ReviewWorkspaceExecutionAttentionItem, ...]
    total_count: int
    has_more: bool
    facets: Mapping[str, Mapping[str, int]]
    first_rank: int | None
    last_rank: int | None
    accepted: bool
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionOperationDiff:
    """Queue placement and state change for one action across executions."""

    action_id: str
    left_rank: int | None
    right_rank: int | None
    left_attention_kind: str | None
    right_attention_kind: str | None
    left_status: str | None
    right_status: str | None
    left_lane: str | None
    right_lane: str | None
    left_address: str | None
    right_address: str | None
    rank_changed: bool
    attention_kind_changed: bool
    status_changed: bool
    lane_changed: bool
    changed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionOperationsDiff:
    """Complete deterministic comparison of two attention-queue projections."""

    left_execution_address: str
    right_execution_address: str
    operations_diff_version: str
    left_operations_address: str
    right_operations_address: str
    left_metrics_address: str
    right_metrics_address: str
    queue_count_delta: int
    completed_action_count_delta: int
    left_recommended_transition: str
    right_recommended_transition: str
    recommendation_changed: bool
    added_action_ids: tuple[str, ...]
    removed_action_ids: tuple[str, ...]
    changed_action_ids: tuple[str, ...]
    unchanged_action_ids: tuple[str, ...]
    rank_changed_action_ids: tuple[str, ...]
    attention_kind_changed_action_ids: tuple[str, ...]
    status_changed_action_ids: tuple[str, ...]
    lane_changed_action_ids: tuple[str, ...]
    attention_kind_count_deltas: Mapping[str, int]
    lane_queue_count_deltas: Mapping[str, int]
    action_diffs: tuple[ReviewWorkspaceExecutionOperationDiff, ...]
    accepted: bool
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _item(
    action: ReviewPlanActionExecution,
    declared: ReviewPlanAction,
    metrics: ReviewWorkspaceExecutionMetrics,
    rank: int,
) -> ReviewWorkspaceExecutionAttentionItem:
    attention_kind = _kind(action)
    metric = next((row for row in metrics.action_metrics if row.action_id == action.action_id), None)
    if metric is None:
        raise ValidationError(f"execution metrics are missing action {action.action_id}")
    body = {
        "rank": rank,
        "action_id": action.action_id,
        "queue_item_id": action.queue_item_id,
        "target_id": action.target_id,
        "title": declared.title,
        "purpose": declared.purpose,
        "lane": action.lane,
        "action_kind": action.action_kind,
        "priority": action.priority,
        "sequence": declared.sequence,
        "status": action.status.value,
        "attention_kind": attention_kind,
        "ready": action.ready,
        "unresolved_dependencies": action.unresolved_dependencies,
        "dependency_count": len(declared.depends_on),
        "event_count": metric.event_count,
        "estimate_units": declared.estimate_units,
        "rationale": _rationale(attention_kind, action),
        "recommended_transition": _transition(attention_kind),
    }
    if contains_private_key(body):
        raise ValidationError("execution attention item failed the public boundary")
    return ReviewWorkspaceExecutionAttentionItem(
        **body,
        content_address=_address(body, "review-workspace-execution-attention-item"),
    )


def build_review_workspace_execution_operations(
    plan: ReviewWorkspacePlan,
    report: ReviewWorkspaceExecutionReport,
    metrics: ReviewWorkspaceExecutionMetrics | None = None,
) -> ReviewWorkspaceExecutionOperations:
    """Build a deterministic queue from the accepted plan and replay report."""

    if not isinstance(plan, ReviewWorkspacePlan):
        raise ValidationError("execution operations require a typed source plan")
    if not isinstance(report, ReviewWorkspaceExecutionReport):
        raise ValidationError("execution operations require a typed execution report")
    if not plan.accepted or not report.accepted:
        raise ValidationError("execution operations require accepted plan and report")
    if plan.plan_id != report.plan_id or plan.content_address != report.plan_address:
        raise ValidationError("execution operations plan and report addresses differ")
    selected_metrics = (
        metrics
        if metrics is not None
        else build_review_workspace_execution_metrics(plan, report)
    )
    if not isinstance(selected_metrics, ReviewWorkspaceExecutionMetrics):
        raise ValidationError("execution operations require typed metrics")
    if selected_metrics.execution_address != report.content_address:
        raise ValidationError("execution operations metrics and report addresses differ")
    if len(report.actions) > REVIEW_WORKSPACE_EXECUTION_OPERATIONS_MAX_ITEMS:
        raise ValidationError("execution operations action count exceeds the bound")
    declared = {action.action_id: action for action in plan.actions}
    if set(declared) != {action.action_id for action in report.actions}:
        raise ValidationError("execution operations action closure differs from the plan")
    pending = [action for action in report.actions if action.status is not ReviewPlanExecutionStatus.COMPLETED]
    pending.sort(
        key=lambda action: (
            _RANKS[_kind(action)],
            action.priority,
            declared[action.action_id].sequence,
            action.action_id,
        )
    )
    items = tuple(
        _item(action, declared[action.action_id], selected_metrics, rank)
        for rank, action in enumerate(pending)
    )
    by_kind = Counter(item.attention_kind.value for item in items)
    by_lane = Counter(item.lane for item in items)
    kind_ids = {
        kind: tuple(item.action_id for item in items if item.attention_kind is kind)
        for kind in ReviewWorkspaceExecutionAttentionKind
    }
    if kind_ids[ReviewWorkspaceExecutionAttentionKind.BLOCKED]:
        recommendation = "reopen_or_block"
    elif kind_ids[ReviewWorkspaceExecutionAttentionKind.READY]:
        recommendation = "start"
    elif kind_ids[ReviewWorkspaceExecutionAttentionKind.IN_PROGRESS]:
        recommendation = "complete_or_block_or_skip"
    elif kind_ids[ReviewWorkspaceExecutionAttentionKind.DEPENDENCY_WAIT]:
        recommendation = "complete_dependencies_first"
    elif kind_ids[ReviewWorkspaceExecutionAttentionKind.SKIPPED]:
        recommendation = "reopen"
    else:
        recommendation = "inspect"
    body = {
        "operations_version": REVIEW_WORKSPACE_EXECUTION_OPERATIONS_VERSION,
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
        "queue_count": len(items),
        "total_action_count": report.action_count,
        "completed_action_count": report.completed_count,
        "blocked_action_ids": kind_ids[ReviewWorkspaceExecutionAttentionKind.BLOCKED],
        "ready_action_ids": kind_ids[ReviewWorkspaceExecutionAttentionKind.READY],
        "in_progress_action_ids": kind_ids[ReviewWorkspaceExecutionAttentionKind.IN_PROGRESS],
        "dependency_wait_action_ids": kind_ids[ReviewWorkspaceExecutionAttentionKind.DEPENDENCY_WAIT],
        "skipped_action_ids": kind_ids[ReviewWorkspaceExecutionAttentionKind.SKIPPED],
        "attention_kind_counts": dict(sorted(by_kind.items())),
        "lane_queue_counts": dict(sorted(by_lane.items())),
        "recommended_action_ids": tuple(item.action_id for item in items[:10]),
        "recommended_transition": recommendation,
        "metrics_address": selected_metrics.content_address,
        "items": tuple(item.to_dict() for item in items),
        "warnings": report.warnings,
    }
    if contains_private_key(body):
        raise ValidationError("execution operations failed the public boundary")
    return ReviewWorkspaceExecutionOperations(
        execution_id=report.execution_id,
        execution_address=report.content_address,
        plan_id=plan.plan_id,
        plan_address=plan.content_address,
        workspace_id=report.workspace_id,
        run_id=report.run_id,
        case_id=report.case_id,
        version=report.version,
        operations_version=REVIEW_WORKSPACE_EXECUTION_OPERATIONS_VERSION,
        state=report.state.value,
        accepted=report.accepted,
        queue_count=len(items),
        total_action_count=report.action_count,
        completed_action_count=report.completed_count,
        blocked_action_ids=kind_ids[ReviewWorkspaceExecutionAttentionKind.BLOCKED],
        ready_action_ids=kind_ids[ReviewWorkspaceExecutionAttentionKind.READY],
        in_progress_action_ids=kind_ids[ReviewWorkspaceExecutionAttentionKind.IN_PROGRESS],
        dependency_wait_action_ids=kind_ids[ReviewWorkspaceExecutionAttentionKind.DEPENDENCY_WAIT],
        skipped_action_ids=kind_ids[ReviewWorkspaceExecutionAttentionKind.SKIPPED],
        attention_kind_counts=dict(sorted(by_kind.items())),
        lane_queue_counts=dict(sorted(by_lane.items())),
        recommended_action_ids=tuple(item.action_id for item in items[:10]),
        recommended_transition=recommendation,
        metrics_address=selected_metrics.content_address,
        items=items,
        warnings=report.warnings,
        content_address=_address(body, "review-workspace-execution-operations"),
    )


def review_workspace_execution_operations_json(
    operations: ReviewWorkspaceExecutionOperations,
) -> str:
    """Render canonical operations JSON."""

    return canonical_json(operations.to_dict()) + "\n"


def review_workspace_execution_operations_csv(
    operations: ReviewWorkspaceExecutionOperations,
) -> str:
    """Render the bounded attention queue as deterministic CSV."""

    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "rank",
            "action_id",
            "queue_item_id",
            "target_id",
            "title",
            "purpose",
            "lane",
            "action_kind",
            "priority",
            "sequence",
            "status",
            "attention_kind",
            "ready",
            "unresolved_dependencies",
            "dependency_count",
            "event_count",
            "estimate_units",
            "rationale",
            "recommended_transition",
            "content_address",
        )
    )
    for item in operations.items:
        writer.writerow(
            (
                item.rank,
                item.action_id,
                item.queue_item_id,
                item.target_id,
                item.title,
                item.purpose,
                item.lane,
                item.action_kind,
                item.priority,
                item.sequence,
                item.status,
                item.attention_kind.value,
                str(item.ready).lower(),
                ";".join(item.unresolved_dependencies),
                item.dependency_count,
                item.event_count,
                item.estimate_units,
                item.rationale,
                item.recommended_transition,
                item.content_address,
            )
        )
    return output.getvalue()


def render_review_workspace_execution_operations_markdown(
    operations: ReviewWorkspaceExecutionOperations,
) -> str:
    """Render a human-readable attention queue."""

    lines = [
        "# Review Workspace Execution Operations",
        "",
        f"- Execution: `{operations.execution_id}`",
        f"- State: `{operations.state}`",
        f"- Queue count: `{operations.queue_count}`",
        f"- Recommended transition: `{operations.recommended_transition}`",
        "",
        "## Attention queue",
        "",
        "| Rank | Action | Lane | Kind | Status | Priority | Dependencies | Recommendation |",
        "| ---: | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for item in operations.items:
        dependencies = ", ".join(item.unresolved_dependencies) or "none"
        lines.append(
            f"| {item.rank} | `{item.action_id}` | {item.lane} | {item.attention_kind.value} | "
            f"{item.status} | {item.priority} | {dependencies} | {item.recommended_transition} |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "This operational queue contains no raw evidence, reviewer identity, agent identity, model metadata, programming-language metadata, or scientific conclusion.",
            "",
        ]
    )
    return "\n".join(lines)


def review_workspace_execution_operations_export_payloads(
    operations: ReviewWorkspaceExecutionOperations,
) -> dict[str, str]:
    """Return exact text payloads for portable operations artifacts."""

    return {
        "review-workspace-execution-operations.json": review_workspace_execution_operations_json(operations),
        "review-workspace-execution-operations.md": render_review_workspace_execution_operations_markdown(operations),
        "review-workspace-execution-operations.csv": review_workspace_execution_operations_csv(operations),
    }


def _operation_text(item: ReviewWorkspaceExecutionAttentionItem) -> str:
    return " ".join(
        (
            item.action_id,
            item.queue_item_id,
            item.target_id,
            item.title,
            item.purpose,
            item.lane,
            item.action_kind,
            str(item.priority),
            str(item.sequence),
            item.status,
            item.attention_kind.value,
            " ".join(item.unresolved_dependencies),
            item.rationale,
            item.recommended_transition,
            item.content_address,
        )
    ).casefold()


def _operation_matches(
    item: ReviewWorkspaceExecutionAttentionItem,
    query: ReviewWorkspaceExecutionOperationsQuery,
) -> bool:
    if query.attention_kind is not None and item.attention_kind.value != query.attention_kind:
        return False
    if query.status is not None and item.status != query.status:
        return False
    if query.lane is not None and item.lane != query.lane:
        return False
    if query.action_kind is not None and item.action_kind != query.action_kind:
        return False
    if query.action_id is not None and item.action_id != query.action_id:
        return False
    if query.priority is not None and item.priority != query.priority:
        return False
    if query.ready is not None and item.ready is not query.ready:
        return False
    if (
        query.dependency_action_id is not None
        and query.dependency_action_id not in item.unresolved_dependencies
    ):
        return False
    if query.text is not None and query.text.casefold() not in _operation_text(item):
        return False
    return True


def query_review_workspace_execution_operations(
    operations: ReviewWorkspaceExecutionOperations,
    query: ReviewWorkspaceExecutionOperationsQuery | Mapping[str, Any] | None = None,
) -> ReviewWorkspaceExecutionOperationsQueryResult:
    """Return a stable page over the ranked attention queue."""

    if not isinstance(operations, ReviewWorkspaceExecutionOperations):
        raise ValidationError("operations query requires a typed operations projection")
    selected = (
        query
        if isinstance(query, ReviewWorkspaceExecutionOperationsQuery)
        else ReviewWorkspaceExecutionOperationsQuery.from_mapping(query)
    )
    boundary_valid = not contains_private_key(operations.to_dict())
    matched = tuple(item for item in operations.items if _operation_matches(item, selected))
    page_matches = (
        matched[selected.offset:]
        if selected.limit is None
        else matched[selected.offset : selected.offset + selected.limit]
    )
    rows = tuple(page_matches)
    facets = {
        "attention_kinds": _facet([item.attention_kind.value for item in matched]),
        "statuses": _facet([item.status for item in matched]),
        "lanes": _facet([item.lane for item in matched]),
        "action_kinds": _facet([item.action_kind for item in matched]),
        "priorities": _facet([str(item.priority) for item in matched]),
        "dependencies": _facet(
            [dependency for item in matched for dependency in item.unresolved_dependencies]
        ),
    }
    body = {
        "operations_query_version": REVIEW_WORKSPACE_EXECUTION_OPERATIONS_QUERY_VERSION,
        "execution_address": operations.execution_address,
        "operations_address": operations.content_address,
        "operations_version": operations.operations_version,
        "queue_count": operations.queue_count,
        "query": selected,
        "rows": rows,
        "total_count": len(matched),
        "has_more": selected.offset + len(rows) < len(matched),
        "facets": facets,
        "first_rank": rows[0].rank if rows else None,
        "last_rank": rows[-1].rank if rows else None,
        "accepted": operations.accepted and boundary_valid,
        "warnings": operations.warnings,
    }
    return ReviewWorkspaceExecutionOperationsQueryResult(
        execution_address=operations.execution_address,
        operations_address=operations.content_address,
        operations_version=operations.operations_version,
        operations_query_version=REVIEW_WORKSPACE_EXECUTION_OPERATIONS_QUERY_VERSION,
        queue_count=operations.queue_count,
        query=selected,
        rows=rows,
        total_count=len(matched),
        has_more=selected.offset + len(rows) < len(matched),
        facets=facets,
        first_rank=rows[0].rank if rows else None,
        last_rank=rows[-1].rank if rows else None,
        accepted=operations.accepted and boundary_valid,
        warnings=operations.warnings,
        content_address=content_hash(body, prefix="review-workspace-execution-operations-query"),
    )


def _operation_map(
    operations: ReviewWorkspaceExecutionOperations,
) -> dict[str, ReviewWorkspaceExecutionAttentionItem]:
    result: dict[str, ReviewWorkspaceExecutionAttentionItem] = {}
    for item in operations.items:
        if item.action_id in result:
            raise ValidationError(f"duplicate operations action identifier: {item.action_id}")
        result[item.action_id] = item
    return result


def _delta_counts(
    left: Mapping[str, int],
    right: Mapping[str, int],
) -> dict[str, int]:
    return {
        key: right.get(key, 0) - left.get(key, 0)
        for key in sorted(set(left) | set(right))
        if right.get(key, 0) - left.get(key, 0) != 0
    }


def _operation_diff(
    action_id: str,
    left: ReviewWorkspaceExecutionAttentionItem | None,
    right: ReviewWorkspaceExecutionAttentionItem | None,
) -> ReviewWorkspaceExecutionOperationDiff:
    left_rank = None if left is None else left.rank
    right_rank = None if right is None else right.rank
    left_attention_kind = None if left is None else left.attention_kind.value
    right_attention_kind = None if right is None else right.attention_kind.value
    left_status = None if left is None else left.status
    right_status = None if right is None else right.status
    left_lane = None if left is None else left.lane
    right_lane = None if right is None else right.lane
    body = {
        "action_id": action_id,
        "left_rank": left_rank,
        "right_rank": right_rank,
        "left_attention_kind": left_attention_kind,
        "right_attention_kind": right_attention_kind,
        "left_status": left_status,
        "right_status": right_status,
        "left_lane": left_lane,
        "right_lane": right_lane,
        "left_address": None if left is None else left.content_address,
        "right_address": None if right is None else right.content_address,
        "rank_changed": left is not None and right is not None and left_rank != right_rank,
        "attention_kind_changed": (
            left is not None and right is not None and left_attention_kind != right_attention_kind
        ),
        "status_changed": left is not None and right is not None and left_status != right_status,
        "lane_changed": left is not None and right is not None and left_lane != right_lane,
        "changed": (None if left is None else left.content_address)
        != (None if right is None else right.content_address),
    }
    if contains_private_key(body):
        raise ValidationError("execution operations diff failed the public boundary")
    return ReviewWorkspaceExecutionOperationDiff(
        **body,
        content_address=content_hash(body, prefix="review-workspace-execution-operation-diff"),
    )


def diff_review_workspace_execution_operations(
    left: ReviewWorkspaceExecutionOperations,
    right: ReviewWorkspaceExecutionOperations,
) -> ReviewWorkspaceExecutionOperationsDiff:
    """Compare two verified attention queues without reordering either queue."""

    if not isinstance(left, ReviewWorkspaceExecutionOperations):
        raise ValidationError("operations diff requires a typed left projection")
    if not isinstance(right, ReviewWorkspaceExecutionOperations):
        raise ValidationError("operations diff requires a typed right projection")
    if contains_private_key(left.to_dict()) or contains_private_key(right.to_dict()):
        raise ValidationError("operations diff failed the public boundary")
    left_rows = _operation_map(left)
    right_rows = _operation_map(right)
    action_ids = sorted(set(left_rows) | set(right_rows))
    action_diffs = tuple(_operation_diff(action_id, left_rows.get(action_id), right_rows.get(action_id)) for action_id in action_ids)
    added = tuple(sorted(set(right_rows) - set(left_rows)))
    removed = tuple(sorted(set(left_rows) - set(right_rows)))
    common = set(left_rows) & set(right_rows)
    changed = tuple(sorted(action_id for action_id in common if left_rows[action_id].content_address != right_rows[action_id].content_address))
    unchanged = tuple(sorted(action_id for action_id in common if left_rows[action_id].content_address == right_rows[action_id].content_address))
    rank_changed = tuple(sorted(action_id for action_id in common if left_rows[action_id].rank != right_rows[action_id].rank))
    attention_kind_changed = tuple(
        sorted(
            action_id
            for action_id in common
            if left_rows[action_id].attention_kind != right_rows[action_id].attention_kind
        )
    )
    status_changed = tuple(sorted(action_id for action_id in common if left_rows[action_id].status != right_rows[action_id].status))
    lane_changed = tuple(sorted(action_id for action_id in common if left_rows[action_id].lane != right_rows[action_id].lane))
    warnings = tuple(dict.fromkeys((*left.warnings, *right.warnings)))
    body = {
        "operations_diff_version": REVIEW_WORKSPACE_EXECUTION_OPERATIONS_DIFF_VERSION,
        "left_execution_address": left.execution_address,
        "right_execution_address": right.execution_address,
        "left_operations_address": left.content_address,
        "right_operations_address": right.content_address,
        "left_metrics_address": left.metrics_address,
        "right_metrics_address": right.metrics_address,
        "queue_count_delta": right.queue_count - left.queue_count,
        "completed_action_count_delta": right.completed_action_count - left.completed_action_count,
        "left_recommended_transition": left.recommended_transition,
        "right_recommended_transition": right.recommended_transition,
        "recommendation_changed": left.recommended_transition != right.recommended_transition,
        "added_action_ids": added,
        "removed_action_ids": removed,
        "changed_action_ids": changed,
        "unchanged_action_ids": unchanged,
        "rank_changed_action_ids": rank_changed,
        "attention_kind_changed_action_ids": attention_kind_changed,
        "status_changed_action_ids": status_changed,
        "lane_changed_action_ids": lane_changed,
        "attention_kind_count_deltas": _delta_counts(left.attention_kind_counts, right.attention_kind_counts),
        "lane_queue_count_deltas": _delta_counts(left.lane_queue_counts, right.lane_queue_counts),
        "action_diffs": tuple(item.to_dict() for item in action_diffs),
        "accepted": left.accepted and right.accepted,
        "warnings": warnings,
    }
    if contains_private_key(body):
        raise ValidationError("execution operations diff failed the public boundary")
    constructor_body = dict(body)
    constructor_body["action_diffs"] = action_diffs
    return ReviewWorkspaceExecutionOperationsDiff(
        **constructor_body,
        content_address=content_hash(body, prefix="review-workspace-execution-operations-diff"),
    )


def review_workspace_execution_operations_schema() -> dict[str, Any]:
    """Return the operations queue contract."""

    return {
        "version": REVIEW_WORKSPACE_EXECUTION_OPERATIONS_SCHEMA_VERSION,
        "operations_version": REVIEW_WORKSPACE_EXECUTION_OPERATIONS_VERSION,
        "query_version": REVIEW_WORKSPACE_EXECUTION_OPERATIONS_QUERY_VERSION,
        "diff_version": REVIEW_WORKSPACE_EXECUTION_OPERATIONS_DIFF_VERSION,
        "type": "execution_attention_queue",
        "attention_kinds": [item.value for item in ReviewWorkspaceExecutionAttentionKind],
        "ordering": ["attention_rank", "plan_priority", "plan_sequence", "action_id"],
        "queue_semantics": {
            "completed_actions_included": False,
            "append_only_ledger_mutated": False,
            "recommended_transition_is_instruction": True,
            "recommendation_is_scientific_decision": False,
        },
        "required_fields": [
            "execution_address",
            "plan_address",
            "metrics_address",
            "items",
            "content_address",
        ],
        "filters": {
            "attention_kind": "exact queue class",
            "status": "exact public execution status",
            "lane": "exact plan lane",
            "action_kind": "exact plan action kind",
            "action_id": "exact plan action identifier",
            "priority": "exact integer plan priority",
            "text": "case-insensitive bounded search across public queue fields",
            "ready": "whether the action is dependency-ready",
            "dependency_action_id": "queue row contains this unresolved dependency",
            "offset": "bounded page offset",
            "limit": "bounded page size",
        },
        "result": {
            "rows": "typed ranked attention items",
            "facets": [
                "attention_kinds",
                "statuses",
                "lanes",
                "action_kinds",
                "priorities",
                "dependencies",
            ],
            "complete_match_facets": True,
            "has_more": True,
            "first_rank": True,
            "last_rank": True,
        },
        "limits": {
            "max_items": REVIEW_WORKSPACE_EXECUTION_OPERATIONS_MAX_ITEMS,
            "max_rationale": REVIEW_WORKSPACE_EXECUTION_OPERATIONS_MAX_RATIONALE,
            "max_text": REVIEW_WORKSPACE_EXECUTION_OPERATIONS_MAX_TEXT,
            "max_page": REVIEW_WORKSPACE_EXECUTION_OPERATIONS_MAX_PAGE,
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


def review_workspace_execution_operations_capabilities() -> dict[str, Any]:
    """Return operations capability metadata without action rows."""

    return {
        "version": REVIEW_WORKSPACE_EXECUTION_OPERATIONS_VERSION,
        "blocked_work_queue": True,
        "ready_work_queue": True,
        "dependency_wait_queue": True,
        "in_progress_recovery_queue": True,
        "deterministic_ranking": True,
        "recommended_transition_projection": True,
        "metrics_linkage": True,
        "json_csv_markdown_exports": True,
        "content_addressed": True,
        "public_boundary_audit": True,
        "offline_reproducible": True,
        "bounded_query": True,
        "query_pagination": True,
        "complete_match_facets": True,
        "attention_kind_filtering": True,
        "dependency_filtering": True,
        "case_insensitive_public_text_search": True,
        "operations_diff": True,
        "per_action_queue_movement": True,
        "aggregate_queue_deltas": True,
    }


def review_workspace_execution_operations_diff_schema() -> dict[str, Any]:
    """Return the public contract for comparing attention queues."""

    return {
        "version": REVIEW_WORKSPACE_EXECUTION_OPERATIONS_DIFF_SCHEMA_VERSION,
        "operations_diff_version": REVIEW_WORKSPACE_EXECUTION_OPERATIONS_DIFF_VERSION,
        "type": "execution_operations_diff",
        "delta_direction": "right minus left for numeric counts",
        "per_action_fields": [
            "left_rank",
            "right_rank",
            "left_attention_kind",
            "right_attention_kind",
            "left_status",
            "right_status",
            "left_lane",
            "right_lane",
            "left_address",
            "right_address",
            "rank_changed",
            "attention_kind_changed",
            "status_changed",
            "lane_changed",
        ],
        "aggregate_fields": [
            "queue_count_delta",
            "completed_action_count_delta",
            "attention_kind_count_deltas",
            "lane_queue_count_deltas",
            "recommendation_changed",
        ],
        "action_sets": [
            "added_action_ids",
            "removed_action_ids",
            "changed_action_ids",
            "unchanged_action_ids",
            "rank_changed_action_ids",
            "attention_kind_changed_action_ids",
            "status_changed_action_ids",
            "lane_changed_action_ids",
        ],
        "content_addressed": True,
        "public_boundary": {
            "raw_evidence": False,
            "reviewer_identity": False,
            "agent_identity": False,
            "model_metadata": False,
            "programming_language_metadata": False,
            "scientific_decision": False,
        },
    }


def review_workspace_execution_operations_diff_capabilities() -> dict[str, Any]:
    """Return capability metadata for queue comparisons."""

    return {
        "version": REVIEW_WORKSPACE_EXECUTION_OPERATIONS_DIFF_VERSION,
        "per_action_queue_movement": True,
        "rank_change_detection": True,
        "attention_kind_change_detection": True,
        "status_change_detection": True,
        "lane_change_detection": True,
        "aggregate_count_deltas": True,
        "recommendation_change_detection": True,
        "added_removed_action_sets": True,
        "deterministic_content_address": True,
        "public_boundary_audit": True,
    }


__all__ = [
    "REVIEW_WORKSPACE_EXECUTION_OPERATIONS_DIFF_SCHEMA_VERSION",
    "REVIEW_WORKSPACE_EXECUTION_OPERATIONS_DIFF_VERSION",
    "REVIEW_WORKSPACE_EXECUTION_OPERATIONS_MAX_ITEMS",
    "REVIEW_WORKSPACE_EXECUTION_OPERATIONS_MAX_RATIONALE",
    "REVIEW_WORKSPACE_EXECUTION_OPERATIONS_MAX_TEXT",
    "REVIEW_WORKSPACE_EXECUTION_OPERATIONS_MAX_PAGE",
    "REVIEW_WORKSPACE_EXECUTION_OPERATIONS_QUERY_VERSION",
    "REVIEW_WORKSPACE_EXECUTION_OPERATIONS_SCHEMA_VERSION",
    "REVIEW_WORKSPACE_EXECUTION_OPERATIONS_VERSION",
    "ReviewWorkspaceExecutionAttentionItem",
    "ReviewWorkspaceExecutionAttentionKind",
    "ReviewWorkspaceExecutionOperations",
    "ReviewWorkspaceExecutionOperationDiff",
    "ReviewWorkspaceExecutionOperationsDiff",
    "ReviewWorkspaceExecutionOperationsQuery",
    "ReviewWorkspaceExecutionOperationsQueryResult",
    "build_review_workspace_execution_operations",
    "query_review_workspace_execution_operations",
    "diff_review_workspace_execution_operations",
    "render_review_workspace_execution_operations_markdown",
    "review_workspace_execution_operations_capabilities",
    "review_workspace_execution_operations_diff_capabilities",
    "review_workspace_execution_operations_diff_schema",
    "review_workspace_execution_operations_csv",
    "review_workspace_execution_operations_export_payloads",
    "review_workspace_execution_operations_json",
    "review_workspace_execution_operations_schema",
]
