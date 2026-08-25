"""Deterministic review-work planning over the public workspace projection.

The review workspace is intentionally a read model: it exposes evidence states,
edges, alternatives, provenance, deltas, and a queue, but it does not prescribe
one scientific answer.  This module adds the next operational layer without
changing that boundary.  It converts queue items into bounded descriptive work
steps that a reviewer can inspect, order, and audit.

The plan is not an adjudication record.  It contains no decision, raw evidence
payload, producer metadata, private identifier, or attribution field.  A plan
can be built from a live :class:`ReviewWorkspaceReport` or from the verified
JSON projection reopened from a portable release.  Every derived object is
content-addressed and every dependency is checked before the plan is accepted.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .module_fabric_support import contains_private_key
from .review_workspace import ReviewWorkspaceReport
from .serialization import content_hash, jsonable


REVIEW_WORKSPACE_PLAN_VERSION = "review-workspace-plan-v1"
REVIEW_WORKSPACE_PLAN_SCHEMA_VERSION = "review-workspace-plan-schema-v1"
REVIEW_WORKSPACE_PLAN_MAX_QUEUE_ITEMS = 5_000
REVIEW_WORKSPACE_PLAN_MAX_ACTIONS = 20_000
REVIEW_WORKSPACE_PLAN_MAX_DEPENDENCIES = 40_000
REVIEW_WORKSPACE_PLAN_MAX_LANES = 16
REVIEW_WORKSPACE_PLAN_DEFAULT_MAX_ACTIONS = 2_000
REVIEW_WORKSPACE_PLAN_QUERY_VERSION = "review-workspace-plan-query-v1"
REVIEW_WORKSPACE_PLAN_QUERY_SCHEMA_VERSION = "review-workspace-plan-query-schema-v1"
REVIEW_WORKSPACE_PLAN_QUERY_DEFAULT_LIMIT = 50
REVIEW_WORKSPACE_PLAN_QUERY_MAX_LIMIT = 500
REVIEW_WORKSPACE_PLAN_QUERY_MAX_TEXT = 256
REVIEW_WORKSPACE_PLAN_QUERY_MAX_VALUES = 32

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


class ReviewPlanState(StrEnum):
    """Structural state of a review plan, separate from scientific state."""

    READY = "ready"
    REVIEW = "review"
    ABSTAINED = "abstained"
    BLOCKED = "blocked"


class ReviewPlanLaneKind(StrEnum):
    """Stable lanes used to separate kinds of reviewer work."""

    INTAKE = "intake"
    CONTEXT = "context"
    PROVENANCE = "provenance"
    ALTERNATIVES = "alternatives"
    DISPOSITION = "disposition"


class ReviewPlanActionKind(StrEnum):
    """Descriptive work-step types; none records a scientific decision."""

    INSPECT = "inspect"
    CHECK_CONTEXT = "check_context"
    CHECK_PROVENANCE = "check_provenance"
    COMPARE_ALTERNATIVES = "compare_alternatives"
    PREPARE_DISPOSITION = "prepare_disposition"


@dataclass(frozen=True, slots=True)
class ReviewWorkspacePlanConfig:
    """Bounds and optional work-step policies for deterministic plan synthesis."""

    max_queue_items: int = REVIEW_WORKSPACE_PLAN_MAX_QUEUE_ITEMS
    max_actions: int = REVIEW_WORKSPACE_PLAN_DEFAULT_MAX_ACTIONS
    max_dependencies: int = REVIEW_WORKSPACE_PLAN_MAX_DEPENDENCIES
    include_context_checks: bool = True
    include_provenance_checks: bool = True
    include_alternative_checks: bool = True
    include_disposition_steps: bool = True

    def __post_init__(self) -> None:
        limits = {
            "max_queue_items": REVIEW_WORKSPACE_PLAN_MAX_QUEUE_ITEMS,
            "max_actions": REVIEW_WORKSPACE_PLAN_MAX_ACTIONS,
            "max_dependencies": REVIEW_WORKSPACE_PLAN_MAX_DEPENDENCIES,
        }
        for field_name, ceiling in limits.items():
            value = int(getattr(self, field_name))
            if value < 1 or value > ceiling:
                raise ValidationError(f"{field_name} is outside the plan ceiling")
            object.__setattr__(self, field_name, value)
        for field_name in (
            "include_context_checks",
            "include_provenance_checks",
            "include_alternative_checks",
            "include_disposition_steps",
        ):
            object.__setattr__(self, field_name, bool(getattr(self, field_name)))

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> "ReviewWorkspacePlanConfig":
        if raw is not None and not isinstance(raw, Mapping):
            raise ValidationError("review workspace plan config must be an object")
        value = raw or {}
        keys = (
            "max_queue_items",
            "max_actions",
            "max_dependencies",
            "include_context_checks",
            "include_provenance_checks",
            "include_alternative_checks",
            "include_disposition_steps",
        )
        return cls(**{key: value[key] for key in keys if key in value})

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewPlanAction:
    """One ordered, descriptive step in a reviewer work plan."""

    action_id: str
    queue_item_id: str
    target_id: str
    target_type: str
    action_kind: ReviewPlanActionKind
    lane: ReviewPlanLaneKind
    priority: int
    sequence: int
    title: str
    purpose: str
    required_checks: tuple[str, ...]
    depends_on: tuple[str, ...]
    edge_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    state: str
    estimate_units: int
    content_address: str

    def __post_init__(self) -> None:
        if self.priority not in {0, 1, 2, 3}:
            raise ValidationError("review plan action priority must be between 0 and 3")
        if self.sequence < 0:
            raise ValidationError("review plan action sequence must be non-negative")
        if self.estimate_units < 1:
            raise ValidationError("review plan action estimate must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewPlanLane:
    """Summary of the ordered actions assigned to one work lane."""

    lane: ReviewPlanLaneKind
    action_ids: tuple[str, ...]
    queue_item_ids: tuple[str, ...]
    action_count: int
    priority_counts: Mapping[str, int]
    estimate_units: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewPlanCheck:
    """One structural check supporting plan acceptance."""

    check_id: str
    passed: bool
    required: bool
    observed: Any
    expected: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewWorkspacePlan:
    """Complete public triage plan for one review workspace."""

    plan_id: str
    workspace_id: str
    run_id: str
    case_id: str
    workspace_address: str
    version: str
    state: ReviewPlanState
    accepted: bool
    queue_item_count: int
    action_count: int
    dependency_count: int
    blocking_count: int
    estimate_units: int
    actions: tuple[ReviewPlanAction, ...]
    lanes: tuple[ReviewPlanLane, ...]
    checks: tuple[ReviewPlanCheck, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewWorkspacePlanQuery:
    """Bounded filters over public plan actions."""

    lane: str | None = None
    action_kind: str | None = None
    queue_item_id: str | None = None
    target_id: str | None = None
    target_type: str | None = None
    state: str | None = None
    priorities: tuple[int, ...] = ()
    text: str | None = None
    offset: int = 0
    limit: int | None = REVIEW_WORKSPACE_PLAN_QUERY_DEFAULT_LIMIT

    def __post_init__(self) -> None:
        for field_name in ("lane", "action_kind", "queue_item_id", "target_id", "target_type", "state"):
            value = getattr(self, field_name)
            if value is not None and not str(value).strip():
                raise ValidationError(f"plan query {field_name} must not be blank")
        if len(self.priorities) > REVIEW_WORKSPACE_PLAN_QUERY_MAX_VALUES:
            raise ValidationError("plan query priority values exceed the bound")
        normalized = tuple(sorted({int(value) for value in self.priorities}))
        if any(value not in {0, 1, 2, 3} for value in normalized):
            raise ValidationError("plan query priorities must be between 0 and 3")
        object.__setattr__(self, "priorities", normalized)
        if self.text is not None:
            value = str(self.text).strip()
            if len(value) > REVIEW_WORKSPACE_PLAN_QUERY_MAX_TEXT:
                raise ValidationError("plan query text exceeds the bound")
            object.__setattr__(self, "text", value or None)
        if self.offset < 0:
            raise ValidationError("plan query offset must be non-negative")
        if self.limit is not None and (
            self.limit < 1 or self.limit > REVIEW_WORKSPACE_PLAN_QUERY_MAX_LIMIT
        ):
            raise ValidationError("plan query limit is outside the bound")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> "ReviewWorkspacePlanQuery":
        if raw is None:
            return cls()
        if not isinstance(raw, Mapping):
            raise ValidationError("review workspace plan query must be an object")
        priorities = raw.get("priorities", ())
        if isinstance(priorities, (str, bytes)) or not isinstance(priorities, Sequence):
            raise ValidationError("plan query priorities must be an array")
        return cls(
            lane=raw.get("lane"),
            action_kind=raw.get("action_kind"),
            queue_item_id=raw.get("queue_item_id"),
            target_id=raw.get("target_id"),
            target_type=raw.get("target_type"),
            state=raw.get("state"),
            priorities=tuple(int(value) for value in priorities),
            text=raw.get("text"),
            offset=int(raw.get("offset", 0)),
            limit=None if raw.get("limit") is None else int(raw.get("limit", REVIEW_WORKSPACE_PLAN_QUERY_DEFAULT_LIMIT)),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewWorkspacePlanQueryResult:
    """A deterministic page plus complete-match plan facets."""

    plan_address: str
    query: ReviewWorkspacePlanQuery
    rows: tuple[ReviewPlanAction, ...]
    total_count: int
    has_more: bool
    facets: Mapping[str, Mapping[str, int]]
    accepted: bool
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _text(value: Any, field: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValidationError(f"{field} must not be empty")
    return normalized


def _unique(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


def _public(value: Any) -> Any:
    value = jsonable(value)
    if isinstance(value, Mapping):
        return {
            str(key): _public(item)
            for key, item in value.items()
            if str(key).casefold() not in _FORBIDDEN_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_public(item) for item in value]
    return value


def _address(value: Any, prefix: str) -> str:
    return content_hash(_public(value), prefix=prefix)


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return {str(key): value[key] for key in value}


def _rows(report: ReviewWorkspaceReport | Mapping[str, Any]) -> dict[str, Any]:
    raw = report.to_dict() if isinstance(report, ReviewWorkspaceReport) else report
    body = _mapping(raw, "review workspace report")
    if _has_forbidden(body) or contains_private_key(body):
        raise ValidationError("review workspace plan input violates the public boundary")
    for field in ("workspace_id", "run_id", "case_id", "content_address"):
        _text(body.get(field), f"report.{field}")
    for collection in (
        "hypotheses",
        "edges",
        "evidence",
        "alternatives",
        "deltas",
        "provenance",
        "review_queue",
    ):
        if not isinstance(body.get(collection), list):
            raise ValidationError(f"report.{collection} must be an array")
    return body


def _row_map(values: Sequence[Any], identifier: str, collection: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for value in values:
        row = _mapping(value, f"{collection} row")
        key = _text(row.get(identifier), f"{collection}.{identifier}")
        if key in result:
            raise ValidationError(f"duplicate {collection} identifier: {key}")
        result[key] = row
    return result


def _tuple_field(row: Mapping[str, Any], field: str) -> tuple[str, ...]:
    value = row.get(field, ())
    if not isinstance(value, (list, tuple)):
        raise ValidationError(f"plan row field {field} must be an array")
    return _unique(value)


def _queue_rows(body: Mapping[str, Any], config: ReviewWorkspacePlanConfig) -> tuple[dict[str, Any], ...]:
    values = body["review_queue"]
    if len(values) > config.max_queue_items:
        raise ValidationError("review queue exceeds plan capacity")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in values:
        row = _mapping(value, "review_queue row")
        item_id = _text(row.get("item_id"), "review_queue.item_id")
        if item_id in seen:
            raise ValidationError(f"duplicate review queue identifier: {item_id}")
        seen.add(item_id)
        priority = int(row.get("priority", 3))
        if priority not in {0, 1, 2, 3}:
            raise ValidationError("review queue priority is outside the plan contract")
        result.append(
            {
                "item_id": item_id,
                "item_type": _text(row.get("item_type"), "review_queue.item_type"),
                "target_id": _text(row.get("target_id"), "review_queue.target_id"),
                "priority": priority,
                "reasons": _tuple_field(row, "reasons"),
                "edge_ids": _tuple_field(row, "edge_ids"),
                "evidence_ids": _tuple_field(row, "evidence_ids"),
                "state": _text(row.get("state"), "review_queue.state"),
            }
        )
    return tuple(result)


def _lane_for(action_kind: ReviewPlanActionKind) -> ReviewPlanLaneKind:
    return {
        ReviewPlanActionKind.INSPECT: ReviewPlanLaneKind.INTAKE,
        ReviewPlanActionKind.CHECK_CONTEXT: ReviewPlanLaneKind.CONTEXT,
        ReviewPlanActionKind.CHECK_PROVENANCE: ReviewPlanLaneKind.PROVENANCE,
        ReviewPlanActionKind.COMPARE_ALTERNATIVES: ReviewPlanLaneKind.ALTERNATIVES,
        ReviewPlanActionKind.PREPARE_DISPOSITION: ReviewPlanLaneKind.DISPOSITION,
    }[action_kind]


def _has_reason(reasons: Iterable[str], *terms: str) -> bool:
    haystack = " ".join(reasons).casefold()
    return any(term.casefold() in haystack for term in terms)


def _action_id(item_id: str, action_kind: ReviewPlanActionKind) -> str:
    return f"review-plan:action:{item_id}:{action_kind.value}"


def _make_action(
    *,
    queue: Mapping[str, Any],
    action_kind: ReviewPlanActionKind,
    depends_on: Iterable[str],
    source_ids: Iterable[str],
    sequence: int,
) -> ReviewPlanAction:
    item_id = str(queue["item_id"])
    target_id = str(queue["target_id"])
    item_type = str(queue["item_type"])
    lane = _lane_for(action_kind)
    titles = {
        ReviewPlanActionKind.INSPECT: "Inspect queued review target",
        ReviewPlanActionKind.CHECK_CONTEXT: "Check context fit and scope",
        ReviewPlanActionKind.CHECK_PROVENANCE: "Trace source provenance",
        ReviewPlanActionKind.COMPARE_ALTERNATIVES: "Compare retained alternatives",
        ReviewPlanActionKind.PREPARE_DISPOSITION: "Prepare a review disposition",
    }
    purposes = {
        ReviewPlanActionKind.INSPECT: "Inspect the public row, its stated reason, and its linked evidence without making a scientific decision.",
        ReviewPlanActionKind.CHECK_CONTEXT: "Confirm that the declared context, dimensions, and domain boundaries are explicit for review.",
        ReviewPlanActionKind.CHECK_PROVENANCE: "Trace the source, edge, evidence, and receipt references available in the public projection.",
        ReviewPlanActionKind.COMPARE_ALTERNATIVES: "Keep competing explanations visible and compare their linked public support and gaps.",
        ReviewPlanActionKind.PREPARE_DISPOSITION: "Prepare the information needed for a human disposition; this step does not record the disposition.",
    }
    checks = {
        ReviewPlanActionKind.INSPECT: ("check:queue-target", "check:public-projection"),
        ReviewPlanActionKind.CHECK_CONTEXT: ("check:context-fit", "check:scope-boundary"),
        ReviewPlanActionKind.CHECK_PROVENANCE: ("check:source-provenance", "check:receipt-coverage"),
        ReviewPlanActionKind.COMPARE_ALTERNATIVES: ("check:alternative-coverage", "check:evidence-state"),
        ReviewPlanActionKind.PREPARE_DISPOSITION: ("check:review-state", "check:human-adjudication"),
    }[action_kind]
    estimate = {
        ReviewPlanActionKind.INSPECT: 1,
        ReviewPlanActionKind.CHECK_CONTEXT: 2,
        ReviewPlanActionKind.CHECK_PROVENANCE: 2,
        ReviewPlanActionKind.COMPARE_ALTERNATIVES: 3,
        ReviewPlanActionKind.PREPARE_DISPOSITION: 1,
    }[action_kind]
    body = {
        "action_id": _action_id(item_id, action_kind),
        "queue_item_id": item_id,
        "target_id": target_id,
        "target_type": item_type,
        "action_kind": action_kind,
        "lane": lane,
        "priority": int(queue["priority"]),
        "sequence": sequence,
        "title": titles[action_kind],
        "purpose": purposes[action_kind],
        "required_checks": checks,
        "depends_on": tuple(sorted(set(depends_on))),
        "edge_ids": tuple(queue["edge_ids"]),
        "evidence_ids": tuple(queue["evidence_ids"]),
        "source_ids": _unique(source_ids),
        "state": str(queue["state"]),
        "estimate_units": estimate,
    }
    return ReviewPlanAction(
        **body,
        content_address=_address(body, "review-plan-action"),
    )


def _source_ids_for_queue(
    queue: Mapping[str, Any],
    evidence: Mapping[str, Mapping[str, Any]],
    edges: Mapping[str, Mapping[str, Any]],
) -> tuple[str, ...]:
    source_ids: list[str] = []
    for evidence_id in queue["evidence_ids"]:
        row = evidence.get(evidence_id)
        if row is not None and row.get("source_id") is not None:
            source_ids.append(str(row["source_id"]))
    for edge_id in queue["edge_ids"]:
        row = edges.get(edge_id)
        if row is None:
            continue
        source_ids.extend(_tuple_field(row, "source_ids"))
        if row.get("source_id") is not None:
            source_ids.append(str(row["source_id"]))
    return _unique(source_ids)


def _topological_order(
    actions: Mapping[str, ReviewPlanAction],
    dependencies: Mapping[str, set[str]],
) -> tuple[str, ...]:
    reverse: dict[str, set[str]] = defaultdict(set)
    indegree = {action_id: len(dependencies.get(action_id, set())) for action_id in actions}
    for action_id, required in dependencies.items():
        for dependency in required:
            if dependency in actions:
                reverse[dependency].add(action_id)
    available = [
        action_id
        for action_id, count in indegree.items()
        if count == 0
    ]
    available.sort(key=lambda item: (actions[item].priority, actions[item].target_id, item))
    ordered: list[str] = []
    while available:
        action_id = available.pop(0)
        ordered.append(action_id)
        for follower in sorted(reverse.get(action_id, ())):
            indegree[follower] -= 1
            if indegree[follower] == 0:
                available.append(follower)
        available.sort(key=lambda item: (actions[item].priority, actions[item].target_id, item))
    if len(ordered) != len(actions):
        raise ValidationError("review plan dependency graph contains a cycle")
    return tuple(ordered)


def _empty_plan(
    body: Mapping[str, Any],
    *,
    state: ReviewPlanState,
    accepted: bool,
    warnings: Iterable[str],
) -> ReviewWorkspacePlan:
    workspace_id = _text(body.get("workspace_id"), "report.workspace_id")
    run_id = _text(body.get("run_id"), "report.run_id")
    case_id = _text(body.get("case_id"), "report.case_id")
    workspace_address = _text(body.get("content_address"), "report.content_address")
    warning_values = tuple(dict.fromkeys(str(item) for item in warnings if str(item).strip()))
    checks_body = {
        "check_id": "source:review-workspace-accepted",
        "passed": accepted,
        "required": True,
        "observed": bool(body.get("accepted", False)),
        "expected": True,
        "detail": (
            "source review workspace acceptance was confirmed"
            if accepted
            else "the source review workspace was not accepted; plan rows are withheld"
        ),
    }
    check = ReviewPlanCheck(**checks_body, content_address=_address(checks_body, "review-plan-check"))
    plan_body = {
        "plan_id": f"review-plan:{workspace_id}",
        "workspace_id": workspace_id,
        "run_id": run_id,
        "case_id": case_id,
        "workspace_address": workspace_address,
        "version": REVIEW_WORKSPACE_PLAN_VERSION,
        "state": state,
        "accepted": accepted,
        "queue_item_count": 0,
        "action_count": 0,
        "dependency_count": 0,
        "blocking_count": 0,
        "estimate_units": 0,
        "actions": (),
        "lanes": (),
        "checks": (check,),
        "warnings": warning_values,
    }
    return ReviewWorkspacePlan(
        **plan_body,
        content_address=_address(plan_body, "review-workspace-plan"),
    )


def build_review_workspace_plan(
    report: ReviewWorkspaceReport | Mapping[str, Any],
    *,
    config: ReviewWorkspacePlanConfig | None = None,
) -> ReviewWorkspacePlan:
    """Build a bounded ordered plan from an accepted public review workspace."""

    selected = config or ReviewWorkspacePlanConfig()
    body = _rows(report)
    if not bool(body.get("accepted", False)):
        return _empty_plan(
            body,
            state=ReviewPlanState.BLOCKED,
            accepted=False,
            warnings=(
                "review workspace was not accepted; plan details were withheld",
                *tuple(str(item) for item in body.get("warnings", ()) if str(item).strip()),
            ),
        )
    queue_rows = _queue_rows(body, selected)
    if not queue_rows:
        return _empty_plan(
            body,
            state=ReviewPlanState.READY,
            accepted=True,
            warnings=("review queue is empty; no work steps were generated",),
        )

    evidence = _row_map(body["evidence"], "evidence_id", "evidence")
    edges = _row_map(body["edges"], "edge_id", "edges")
    hypotheses = _row_map(body["hypotheses"], "hypothesis_id", "hypotheses")
    alternatives = _row_map(body["alternatives"], "alternative_id", "alternatives")
    actions: dict[str, ReviewPlanAction] = {}
    dependencies: dict[str, set[str]] = {}
    action_ids_by_queue: dict[str, dict[ReviewPlanActionKind, str]] = {}
    warnings: list[str] = [
        "plan steps are descriptive review work and do not record a scientific decision",
        "the plan exposes only the accepted public workspace projection",
    ]

    for queue in sorted(queue_rows, key=lambda row: (row["priority"], row["item_type"], row["target_id"], row["item_id"])):
        source_ids = _source_ids_for_queue(queue, evidence, edges)
        item_actions: dict[ReviewPlanActionKind, str] = {}
        inspect = _make_action(
            queue=queue,
            action_kind=ReviewPlanActionKind.INSPECT,
            depends_on=(),
            source_ids=source_ids,
            sequence=0,
        )
        actions[inspect.action_id] = inspect
        dependencies[inspect.action_id] = set()
        item_actions[ReviewPlanActionKind.INSPECT] = inspect.action_id
        reasons = queue["reasons"]
        if selected.include_context_checks and (
            _has_reason(reasons, "context", "scope", "domain", "fit")
            or queue["item_type"] in {"hypothesis", "evidence"}
        ):
            context = _make_action(
                queue=queue,
                action_kind=ReviewPlanActionKind.CHECK_CONTEXT,
                depends_on=(inspect.action_id,),
                source_ids=source_ids,
                sequence=0,
            )
            actions[context.action_id] = context
            dependencies[context.action_id] = {inspect.action_id}
            item_actions[ReviewPlanActionKind.CHECK_CONTEXT] = context.action_id
        if selected.include_provenance_checks and (queue["evidence_ids"] or queue["edge_ids"] or source_ids):
            provenance = _make_action(
                queue=queue,
                action_kind=ReviewPlanActionKind.CHECK_PROVENANCE,
                depends_on=(inspect.action_id,),
                source_ids=source_ids,
                sequence=0,
            )
            actions[provenance.action_id] = provenance
            dependencies[provenance.action_id] = {inspect.action_id}
            item_actions[ReviewPlanActionKind.CHECK_PROVENANCE] = provenance.action_id
        hypothesis = hypotheses.get(queue["target_id"])
        related_alternative_ids = _tuple_field(hypothesis or {}, "alternative_ids")
        has_alternatives = bool(related_alternative_ids) or any(
            row.get("hypothesis_id") == queue["target_id"] for row in alternatives.values()
        )
        if selected.include_alternative_checks and queue["item_type"] == "hypothesis" and has_alternatives:
            prerequisite_ids = [inspect.action_id]
            context_id = item_actions.get(ReviewPlanActionKind.CHECK_CONTEXT)
            if context_id:
                prerequisite_ids.append(context_id)
            comparison = _make_action(
                queue=queue,
                action_kind=ReviewPlanActionKind.COMPARE_ALTERNATIVES,
                depends_on=prerequisite_ids,
                source_ids=source_ids,
                sequence=0,
            )
            actions[comparison.action_id] = comparison
            dependencies[comparison.action_id] = set(prerequisite_ids)
            item_actions[ReviewPlanActionKind.COMPARE_ALTERNATIVES] = comparison.action_id
        if selected.include_disposition_steps:
            prerequisite_ids = tuple(item_actions.values())
            disposition = _make_action(
                queue=queue,
                action_kind=ReviewPlanActionKind.PREPARE_DISPOSITION,
                depends_on=prerequisite_ids,
                source_ids=source_ids,
                sequence=0,
            )
            actions[disposition.action_id] = disposition
            dependencies[disposition.action_id] = set(prerequisite_ids)
            item_actions[ReviewPlanActionKind.PREPARE_DISPOSITION] = disposition.action_id
        action_ids_by_queue[queue["item_id"]] = item_actions

    # A hypothesis work item must follow the queued evidence inspections that
    # it references.  This is an operational dependency, not a causal claim.
    evidence_inspections = {
        queue["target_id"]: action_ids_by_queue.get(queue["item_id"], {}).get(ReviewPlanActionKind.INSPECT)
        for queue in queue_rows
        if queue["item_type"] == "evidence"
    }
    for queue in queue_rows:
        if queue["item_type"] != "hypothesis":
            continue
        inspect_id = action_ids_by_queue[queue["item_id"]][ReviewPlanActionKind.INSPECT]
        for evidence_id in queue["evidence_ids"]:
            dependency = evidence_inspections.get(evidence_id)
            if dependency and dependency != inspect_id:
                dependencies[inspect_id].add(dependency)
        disposition_id = action_ids_by_queue[queue["item_id"]].get(ReviewPlanActionKind.PREPARE_DISPOSITION)
        if disposition_id:
            dependencies[disposition_id].add(inspect_id)

    dependency_count = sum(len(values) for values in dependencies.values())
    if dependency_count > selected.max_dependencies:
        raise ValidationError("review plan dependency ceiling was exceeded")
    if len(actions) > selected.max_actions:
        raise ValidationError("review plan action ceiling was exceeded")
    ordered_ids = _topological_order(actions, dependencies)
    ordered_action_values: list[ReviewPlanAction] = []
    for sequence, action_id in enumerate(ordered_ids):
        action_body = actions[action_id].to_dict()
        action_body.update(
            {
                "action_kind": actions[action_id].action_kind,
                "lane": actions[action_id].lane,
                "depends_on": tuple(sorted(dependencies[action_id])),
                "sequence": sequence,
            }
        )
        action_body.pop("content_address", None)
        ordered_action_values.append(
            ReviewPlanAction(
                **action_body,
                content_address=_address(action_body, "review-plan-action"),
            )
        )
    ordered_actions = tuple(ordered_action_values)
    action_by_id = {item.action_id: item for item in ordered_actions}
    lane_values: list[ReviewPlanLane] = []
    for lane in ReviewPlanLaneKind:
        values = tuple(item for item in ordered_actions if item.lane is lane)
        if not values:
            continue
        priority_counts = {
            str(priority): sum(item.priority == priority for item in values)
            for priority in range(4)
            if any(item.priority == priority for item in values)
        }
        lane_body = {
            "lane": lane,
            "action_ids": tuple(item.action_id for item in values),
            "queue_item_ids": tuple(sorted({item.queue_item_id for item in values})),
            "action_count": len(values),
            "priority_counts": priority_counts,
            "estimate_units": sum(item.estimate_units for item in values),
        }
        lane_values.append(ReviewPlanLane(**lane_body, content_address=_address(lane_body, "review-plan-lane")))

    checks: list[ReviewPlanCheck] = []
    queue_ids = {row["item_id"] for row in queue_rows}
    checks_data = (
        (
            "source:review-workspace-accepted",
            True,
            bool(body.get("accepted", False)),
            True,
            "source workspace acceptance is required before plan rows are exposed",
        ),
        (
            "plan:queue-closure",
            True,
            {item.queue_item_id for item in ordered_actions} == queue_ids,
            True,
            "every queue item has at least one ordered action",
        ),
        (
            "plan:dependency-closure",
            True,
            all(dependency in action_by_id for values in dependencies.values() for dependency in values),
            True,
            "every dependency references an action in the plan",
        ),
        (
            "plan:topological-order",
            True,
            all(
                action_by_id[dependency].sequence < action.sequence
                for action in ordered_actions
                for dependency in action.depends_on
            ),
            True,
            "dependencies precede dependent actions",
        ),
        (
            "plan:lane-closure",
            True,
            {item.action_id for lane in lane_values for item in (action_by_id[action_id] for action_id in lane.action_ids)}
            == set(action_by_id),
            True,
            "every action belongs to exactly one emitted lane",
        ),
        (
            "plan:public-boundary",
            True,
            not _has_forbidden({"actions": ordered_actions, "lanes": lane_values, "checks": checks}),
            True,
            "derived plan output contains no forbidden public keys",
        ),
        (
            "plan:bounded",
            True,
            len(ordered_actions) <= selected.max_actions and dependency_count <= selected.max_dependencies,
            True,
            "action and dependency counts stay inside configured bounds",
        ),
    )
    for check_id, required, observed, expected, detail in checks_data:
        check_body = {
            "check_id": check_id,
            "passed": bool(observed == expected),
            "required": required,
            "observed": observed,
            "expected": expected,
            "detail": detail,
        }
        checks.append(ReviewPlanCheck(**check_body, content_address=_address(check_body, "review-plan-check")))
    accepted = all(not check.required or check.passed for check in checks)
    blocking_count = sum(item.priority == 0 for item in ordered_actions)
    plan_state = ReviewPlanState.REVIEW if queue_rows else ReviewPlanState.READY
    plan_body = {
        "plan_id": f"review-plan:{body['workspace_id']}",
        "workspace_id": _text(body["workspace_id"], "report.workspace_id"),
        "run_id": _text(body["run_id"], "report.run_id"),
        "case_id": _text(body["case_id"], "report.case_id"),
        "workspace_address": _text(body["content_address"], "report.content_address"),
        "version": REVIEW_WORKSPACE_PLAN_VERSION,
        "state": plan_state,
        "accepted": accepted,
        "queue_item_count": len(queue_rows),
        "action_count": len(ordered_actions),
        "dependency_count": dependency_count,
        "blocking_count": blocking_count,
        "estimate_units": sum(item.estimate_units for item in ordered_actions),
        "actions": ordered_actions,
        "lanes": tuple(lane_values),
        "checks": tuple(checks),
        "warnings": tuple(warnings),
    }
    return ReviewWorkspacePlan(
        **plan_body,
        content_address=_address(plan_body, "review-workspace-plan"),
    )


def build_persisted_review_workspace_plan(
    runtime: Any,
    run_id: str,
    *,
    baseline_run_id: str | None = None,
    workspace_config: Any | None = None,
    config: ReviewWorkspacePlanConfig | None = None,
) -> ReviewWorkspacePlan:
    """Build a plan from a replay-gated persisted review workspace."""

    from .review_workspace import ReviewWorkspaceConfig, build_persisted_review_workspace

    if workspace_config is not None and not isinstance(workspace_config, ReviewWorkspaceConfig):
        workspace_config = ReviewWorkspaceConfig.from_mapping(workspace_config)
    report = build_persisted_review_workspace(
        runtime,
        run_id,
        baseline_run_id=baseline_run_id,
        config=workspace_config,
    )
    return build_review_workspace_plan(report, config=config)


def _has_forbidden(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            str(key).casefold() in _FORBIDDEN_KEYS or _has_forbidden(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_has_forbidden(item) for item in value)
    return False


def _action_matches(action: ReviewPlanAction, query: ReviewWorkspacePlanQuery) -> bool:
    if query.lane and action.lane.value != str(query.lane).strip().casefold():
        return False
    if query.action_kind and action.action_kind.value != str(query.action_kind).strip().casefold():
        return False
    if query.queue_item_id and action.queue_item_id != str(query.queue_item_id).strip():
        return False
    if query.target_id and action.target_id != str(query.target_id).strip():
        return False
    if query.target_type and action.target_type != str(query.target_type).strip():
        return False
    if query.state and action.state != str(query.state).strip():
        return False
    if query.priorities and action.priority not in query.priorities:
        return False
    if query.text:
        haystack = " ".join(
            (
                action.action_id,
                action.queue_item_id,
                action.target_id,
                action.target_type,
                action.action_kind.value,
                action.lane.value,
                action.title,
                action.purpose,
                action.state,
                *action.required_checks,
            )
        ).casefold()
        if str(query.text).casefold() not in haystack:
            return False
    return True


def _facet(rows: Iterable[ReviewPlanAction], key: str) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        value = getattr(row, key)
        normalized = value.value if isinstance(value, StrEnum) else str(value)
        counts[normalized] += 1
    return dict(sorted(counts.items()))


def query_review_workspace_plan(
    plan: ReviewWorkspacePlan,
    query: ReviewWorkspacePlanQuery | Mapping[str, Any] | None = None,
) -> ReviewWorkspacePlanQueryResult:
    """Filter a plan with deterministic pagination and complete-match facets."""

    if not isinstance(plan, ReviewWorkspacePlan):
        raise ValidationError("plan query requires a typed review workspace plan")
    selected = query if isinstance(query, ReviewWorkspacePlanQuery) else ReviewWorkspacePlanQuery.from_mapping(query)
    matched = tuple(action for action in plan.actions if _action_matches(action, selected))
    if selected.limit is None:
        page = matched[selected.offset :]
    else:
        page = matched[selected.offset : selected.offset + selected.limit]
    facets = {
        "lanes": _facet(matched, "lane"),
        "action_kinds": _facet(matched, "action_kind"),
        "priorities": _facet(matched, "priority"),
        "states": _facet(matched, "state"),
        "target_types": _facet(matched, "target_type"),
    }
    body = {
        "plan_address": plan.content_address,
        "query": selected,
        "rows": page,
        "total_count": len(matched),
        "has_more": selected.offset + len(page) < len(matched),
        "facets": facets,
        "accepted": plan.accepted,
        "warnings": plan.warnings,
    }
    return ReviewWorkspacePlanQueryResult(
        plan_address=plan.content_address,
        query=selected,
        rows=page,
        total_count=len(matched),
        has_more=selected.offset + len(page) < len(matched),
        facets=facets,
        accepted=plan.accepted,
        warnings=plan.warnings,
        content_address=_address(body, "review-workspace-plan-query"),
    )


def review_workspace_plan_schema() -> dict[str, Any]:
    """Return the machine-readable triage-plan contract."""

    return {
        "version": REVIEW_WORKSPACE_PLAN_SCHEMA_VERSION,
        "plan_version": REVIEW_WORKSPACE_PLAN_VERSION,
        "states": [item.value for item in ReviewPlanState],
        "lanes": [item.value for item in ReviewPlanLaneKind],
        "action_kinds": [item.value for item in ReviewPlanActionKind],
        "action_fields": [
            "action_id",
            "queue_item_id",
            "target_id",
            "target_type",
            "action_kind",
            "lane",
            "priority",
            "sequence",
            "title",
            "purpose",
            "required_checks",
            "depends_on",
            "edge_ids",
            "evidence_ids",
            "source_ids",
            "state",
            "estimate_units",
            "content_address",
        ],
        "checks": [
            "source:review-workspace-accepted",
            "plan:queue-closure",
            "plan:dependency-closure",
            "plan:topological-order",
            "plan:lane-closure",
            "plan:public-boundary",
            "plan:bounded",
        ],
        "boundary": [
            "plan actions are descriptive and do not record reviewer decisions",
            "raw evidence payloads are not copied into plan output",
            "source, edge, evidence, and receipt IDs remain aggregate references",
            "agent, assistant, model, programming-language, private, subject, and contact keys are rejected",
        ],
        "limits": {
            "max_queue_items": REVIEW_WORKSPACE_PLAN_MAX_QUEUE_ITEMS,
            "max_actions": REVIEW_WORKSPACE_PLAN_MAX_ACTIONS,
            "max_dependencies": REVIEW_WORKSPACE_PLAN_MAX_DEPENDENCIES,
            "query_default_limit": REVIEW_WORKSPACE_PLAN_QUERY_DEFAULT_LIMIT,
            "query_max_limit": REVIEW_WORKSPACE_PLAN_QUERY_MAX_LIMIT,
        },
    }


def review_workspace_plan_capabilities() -> dict[str, Any]:
    """Return operational plan capabilities without case-specific rows."""

    return {
        "version": REVIEW_WORKSPACE_PLAN_VERSION,
        "queue_to_action_expansion": True,
        "dependency_ordering": True,
        "cross_queue_evidence_dependencies": True,
        "lane_summaries": True,
        "structural_checks": True,
        "bounded_pagination": True,
        "complete_match_facets": True,
        "deterministic_content_addresses": True,
        "offline_compatible": True,
        "public_boundary": {
            "raw_payloads": False,
            "private_identifiers": False,
            "attribution_fields": False,
            "scientific_decisions": False,
        },
        "filters": [
            "lane",
            "action_kind",
            "queue_item_id",
            "target_id",
            "target_type",
            "state",
            "priorities",
            "text",
        ],
    }


__all__ = [
    "REVIEW_WORKSPACE_PLAN_DEFAULT_MAX_ACTIONS",
    "REVIEW_WORKSPACE_PLAN_MAX_ACTIONS",
    "REVIEW_WORKSPACE_PLAN_MAX_DEPENDENCIES",
    "REVIEW_WORKSPACE_PLAN_MAX_LANES",
    "REVIEW_WORKSPACE_PLAN_MAX_QUEUE_ITEMS",
    "REVIEW_WORKSPACE_PLAN_QUERY_DEFAULT_LIMIT",
    "REVIEW_WORKSPACE_PLAN_QUERY_MAX_LIMIT",
    "REVIEW_WORKSPACE_PLAN_QUERY_MAX_TEXT",
    "REVIEW_WORKSPACE_PLAN_QUERY_MAX_VALUES",
    "REVIEW_WORKSPACE_PLAN_QUERY_SCHEMA_VERSION",
    "REVIEW_WORKSPACE_PLAN_QUERY_VERSION",
    "REVIEW_WORKSPACE_PLAN_SCHEMA_VERSION",
    "REVIEW_WORKSPACE_PLAN_VERSION",
    "ReviewPlanAction",
    "ReviewPlanActionKind",
    "ReviewPlanCheck",
    "ReviewPlanLane",
    "ReviewPlanLaneKind",
    "ReviewPlanState",
    "ReviewWorkspacePlan",
    "ReviewWorkspacePlanConfig",
    "ReviewWorkspacePlanQuery",
    "ReviewWorkspacePlanQueryResult",
    "build_persisted_review_workspace_plan",
    "build_review_workspace_plan",
    "query_review_workspace_plan",
    "review_workspace_plan_capabilities",
    "review_workspace_plan_schema",
]
