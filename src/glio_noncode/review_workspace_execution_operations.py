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
REVIEW_WORKSPACE_EXECUTION_OPERATIONS_MAX_ITEMS = 50_000
REVIEW_WORKSPACE_EXECUTION_OPERATIONS_MAX_RATIONALE = 512


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


def review_workspace_execution_operations_schema() -> dict[str, Any]:
    """Return the operations queue contract."""

    return {
        "version": REVIEW_WORKSPACE_EXECUTION_OPERATIONS_SCHEMA_VERSION,
        "operations_version": REVIEW_WORKSPACE_EXECUTION_OPERATIONS_VERSION,
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
        "limits": {
            "max_items": REVIEW_WORKSPACE_EXECUTION_OPERATIONS_MAX_ITEMS,
            "max_rationale": REVIEW_WORKSPACE_EXECUTION_OPERATIONS_MAX_RATIONALE,
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
    }


__all__ = [
    "REVIEW_WORKSPACE_EXECUTION_OPERATIONS_MAX_ITEMS",
    "REVIEW_WORKSPACE_EXECUTION_OPERATIONS_MAX_RATIONALE",
    "REVIEW_WORKSPACE_EXECUTION_OPERATIONS_SCHEMA_VERSION",
    "REVIEW_WORKSPACE_EXECUTION_OPERATIONS_VERSION",
    "ReviewWorkspaceExecutionAttentionItem",
    "ReviewWorkspaceExecutionAttentionKind",
    "ReviewWorkspaceExecutionOperations",
    "build_review_workspace_execution_operations",
    "render_review_workspace_execution_operations_markdown",
    "review_workspace_execution_operations_capabilities",
    "review_workspace_execution_operations_csv",
    "review_workspace_execution_operations_export_payloads",
    "review_workspace_execution_operations_json",
    "review_workspace_execution_operations_schema",
]
