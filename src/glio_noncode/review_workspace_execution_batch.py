"""Optimistic, atomic application of a simulated execution batch.

The execution simulator answers whether a proposed sequence is valid in memory.
This module makes the next step explicit: capture the current replay address,
re-run the proposal sequence against that exact base, and append the resulting
events together through one store transaction.  A stale base, invalid
proposal, duplicate event, or replay failure produces a structured rejection
without a partial validation write.  The operation never accepts raw evidence,
identity, attribution, model metadata, programming-language metadata, or a
scientific decision.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from io import StringIO
from typing import Any

from .errors import StoreError, ValidationError
from .module_fabric_support import contains_private_key
from .review_workspace_execution import (
    ReviewPlanExecutionEvent,
    ReviewPlanExecutionStore,
    ReviewWorkspaceExecutionReport,
    build_persisted_review_workspace_plan_execution,
    review_workspace_execution_report_from_mapping,
)
from .review_workspace_execution_simulation import (
    REVIEW_WORKSPACE_EXECUTION_SIMULATION_MAX_PROPOSALS,
    ReviewWorkspaceExecutionSimulation,
    ReviewWorkspaceExecutionSimulationProposal,
    review_workspace_execution_simulation_from_mapping,
    simulate_review_workspace_plan_execution,
)
from .review_workspace_plan import ReviewWorkspacePlan, build_persisted_review_workspace_plan
from .serialization import canonical_json, content_hash, jsonable


REVIEW_WORKSPACE_EXECUTION_BATCH_VERSION = "review-workspace-execution-batch-v1"
REVIEW_WORKSPACE_EXECUTION_BATCH_SCHEMA_VERSION = "review-workspace-execution-batch-schema-v1"
REVIEW_WORKSPACE_EXECUTION_BATCH_MAX_PROPOSALS = REVIEW_WORKSPACE_EXECUTION_SIMULATION_MAX_PROPOSALS
REVIEW_WORKSPACE_EXECUTION_BATCH_MAX_MESSAGE = 1_000

_FORBIDDEN_KEYS = frozenset(
    {
        "agent",
        "agent_id",
        "assistant",
        "author",
        "contact",
        "credential",
        "email",
        "generated_by",
        "individual",
        "language",
        "model",
        "patient",
        "phone",
        "programming_language",
        "sample",
        "secret",
        "subject",
        "token",
    }
)


def _text(value: Any, field: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValidationError(f"{field} must not be empty")
    return normalized


def _optional_text(value: Any, field: str) -> str | None:
    if value in (None, ""):
        return None
    return _text(value, field)


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return {str(key): item for key, item in value.items()}


def _text_sequence(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValidationError(f"{field} must be an array")
    result = tuple(_text(item, f"{field}[]") for item in value)
    if len(result) != len(set(result)):
        raise ValidationError(f"{field} must not contain duplicates")
    return result


def _private_key_paths(value: Any, path: str = "") -> tuple[str, ...]:
    if isinstance(value, Mapping):
        paths: list[str] = []
        for key, item in value.items():
            key_text = str(key)
            child = f"{path}.{key_text}" if path else key_text
            if key_text.casefold() in _FORBIDDEN_KEYS:
                paths.append(child)
            paths.extend(_private_key_paths(item, child))
        return tuple(paths)
    if isinstance(value, (list, tuple)):
        paths: list[str] = []
        for index, item in enumerate(value):
            paths.extend(_private_key_paths(item, f"{path}[{index}]"))
        return tuple(paths)
    return ()


def _address(value: Any, prefix: str) -> str:
    return content_hash(value, prefix=prefix)


def _address_without_content(body: Mapping[str, Any], prefix: str, field: str) -> str:
    address = _text(body.get("content_address"), field)
    source = {key: item for key, item in body.items() if key != "content_address"}
    if _address(source, prefix) != address:
        raise ValidationError(f"{field} address mismatch")
    return address


def _bounded_message(value: Any, field: str = "message") -> str:
    message = _text(value, field)
    return message[:REVIEW_WORKSPACE_EXECUTION_BATCH_MAX_MESSAGE]


def _proposal_values(
    proposals: Iterable[
        ReviewWorkspaceExecutionSimulationProposal | Mapping[str, Any]
    ],
) -> tuple[ReviewWorkspaceExecutionSimulationProposal, ...]:
    values = tuple(
        item
        if isinstance(item, ReviewWorkspaceExecutionSimulationProposal)
        else ReviewWorkspaceExecutionSimulationProposal.from_mapping(item)
        for item in proposals
    )
    if len(values) > REVIEW_WORKSPACE_EXECUTION_BATCH_MAX_PROPOSALS:
        raise ValidationError("execution batch proposal count exceeds the bound")
    public_values = jsonable(values)
    if _private_key_paths(public_values) or contains_private_key(public_values):
        raise ValidationError("execution batch proposals violate the public boundary")
    return values


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionBatchRequest:
    """A content-addressed request envelope for one optimistic batch."""

    expected_execution_address: str
    expected_event_count: int
    expected_last_event_address: str | None
    proposals: tuple[ReviewWorkspaceExecutionSimulationProposal, ...]
    content_address: str

    def __post_init__(self) -> None:
        if self.expected_event_count < 0:
            raise ValidationError("batch expected_event_count must be non-negative")
        if len(self.proposals) > REVIEW_WORKSPACE_EXECUTION_BATCH_MAX_PROPOSALS:
            raise ValidationError("batch proposal count exceeds the bound")
        if self.expected_event_count == 0 and self.expected_last_event_address is not None:
            raise ValidationError("empty batch base cannot have a last event address")

    def _body(self) -> dict[str, Any]:
        return {
            "batch_version": REVIEW_WORKSPACE_EXECUTION_BATCH_VERSION,
            "expected_execution_address": self.expected_execution_address,
            "expected_event_count": self.expected_event_count,
            "expected_last_event_address": self.expected_last_event_address,
            "proposals": self.proposals,
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ReviewWorkspaceExecutionBatchRequest":
        body = _mapping(value, "execution batch request")
        if _private_key_paths(body) or contains_private_key(body):
            raise ValidationError("execution batch request violates the public boundary")
        version = _text(body.get("batch_version"), "batch.batch_version")
        if version != REVIEW_WORKSPACE_EXECUTION_BATCH_VERSION:
            raise ValidationError("execution batch request version is invalid")
        raw_proposals = body.get("proposals", ())
        if not isinstance(raw_proposals, (list, tuple)):
            raise ValidationError("execution batch request proposals must be an array")
        proposals = _proposal_values(raw_proposals)
        expected_event_count = int(body.get("expected_event_count"))
        expected_last_event_address = _optional_text(
            body.get("expected_last_event_address"),
            "batch.expected_last_event_address",
        )
        expected_execution_address = _text(
            body.get("expected_execution_address"),
            "batch.expected_execution_address",
        )
        values = {
            "expected_execution_address": expected_execution_address,
            "expected_event_count": expected_event_count,
            "expected_last_event_address": expected_last_event_address,
            "proposals": proposals,
        }
        expected = _address(
            {"batch_version": version, **values},
            "review-workspace-execution-batch-request",
        )
        content_address = _text(body.get("content_address"), "batch.content_address")
        if expected != content_address:
            raise ValidationError("execution batch request address does not reconcile")
        return cls(**values, content_address=content_address)


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionBatchResult:
    """The complete outcome of one preflight-and-append operation."""

    batch_version: str
    request_address: str
    base_execution_address: str
    expected_execution_address: str
    expected_event_count: int
    expected_last_event_address: str | None
    final_execution_address: str
    plan_address: str
    execution_id: str
    plan_id: str
    workspace_id: str
    run_id: str
    case_id: str
    accepted: bool
    committed: bool
    no_partial_write: bool
    conflict: bool
    proposal_count: int
    event_count_before: int
    event_count_after: int
    committed_event_ids: tuple[str, ...]
    committed_event_addresses: tuple[str, ...]
    simulation_address: str | None
    failure_code: str | None
    message: str
    simulation: ReviewWorkspaceExecutionSimulation | None
    final_report: ReviewWorkspaceExecutionReport | None
    content_address: str

    def _summary_body(self) -> dict[str, Any]:
        return {
            "batch_version": self.batch_version,
            "request_address": self.request_address,
            "base_execution_address": self.base_execution_address,
            "expected_execution_address": self.expected_execution_address,
            "expected_event_count": self.expected_event_count,
            "expected_last_event_address": self.expected_last_event_address,
            "final_execution_address": self.final_execution_address,
            "plan_address": self.plan_address,
            "execution_id": self.execution_id,
            "plan_id": self.plan_id,
            "workspace_id": self.workspace_id,
            "run_id": self.run_id,
            "case_id": self.case_id,
            "accepted": self.accepted,
            "committed": self.committed,
            "no_partial_write": self.no_partial_write,
            "conflict": self.conflict,
            "proposal_count": self.proposal_count,
            "event_count_before": self.event_count_before,
            "event_count_after": self.event_count_after,
            "committed_event_ids": self.committed_event_ids,
            "committed_event_addresses": self.committed_event_addresses,
            "simulation_address": self.simulation_address,
            "failure_code": self.failure_code,
            "message": self.message,
        }

    def to_dict(
        self,
        *,
        include_simulation: bool = True,
        include_report: bool = False,
    ) -> dict[str, Any]:
        body = self._summary_body() | {"content_address": self.content_address}
        if include_simulation and self.simulation is not None:
            body["simulation"] = self.simulation.to_dict(include_report=include_report)
        elif include_report and self.final_report is not None:
            body["final_report"] = self.final_report
        return jsonable(body)


def _request(
    expected_execution_address: str,
    expected_event_count: int,
    expected_last_event_address: str | None,
    proposals: Iterable[
        ReviewWorkspaceExecutionSimulationProposal | Mapping[str, Any]
    ],
) -> ReviewWorkspaceExecutionBatchRequest:
    values = {
        "expected_execution_address": _text(
            expected_execution_address,
            "batch.expected_execution_address",
        ),
        "expected_event_count": int(expected_event_count),
        "expected_last_event_address": _optional_text(
            expected_last_event_address,
            "batch.expected_last_event_address",
        ),
        "proposals": _proposal_values(proposals),
    }
    body = {"batch_version": REVIEW_WORKSPACE_EXECUTION_BATCH_VERSION, **values}
    return ReviewWorkspaceExecutionBatchRequest(
        **values,
        content_address=_address(body, "review-workspace-execution-batch-request"),
    )


def _failure_code(message: str) -> str:
    text = message.casefold()
    if "stale" in text or "expected" in text and "address" in text:
        return "stale_base"
    if "duplicate" in text:
        return "duplicate_event_id"
    if "write" in text or "manifest" in text:
        return "write_failed"
    if "required checks" in text:
        return "required_checks"
    if "dependencies" in text:
        return "dependencies"
    if "reason" in text:
        return "reason_required"
    return "batch_validation"


def _result(
    *,
    request: ReviewWorkspaceExecutionBatchRequest,
    plan: ReviewWorkspacePlan,
    base_report: ReviewWorkspaceExecutionReport,
    final_report: ReviewWorkspaceExecutionReport,
    accepted: bool,
    committed: bool,
    no_partial_write: bool,
    conflict: bool,
    simulation: ReviewWorkspaceExecutionSimulation | None,
    failure_code: str | None,
    message: str,
    committed_events: tuple[ReviewPlanExecutionEvent, ...] = (),
) -> ReviewWorkspaceExecutionBatchResult:
    body = {
        "batch_version": REVIEW_WORKSPACE_EXECUTION_BATCH_VERSION,
        "request_address": request.content_address,
        "base_execution_address": base_report.content_address,
        "expected_execution_address": request.expected_execution_address,
        "expected_event_count": request.expected_event_count,
        "expected_last_event_address": request.expected_last_event_address,
        "final_execution_address": final_report.content_address,
        "plan_address": plan.content_address,
        "execution_id": final_report.execution_id,
        "plan_id": plan.plan_id,
        "workspace_id": final_report.workspace_id,
        "run_id": final_report.run_id,
        "case_id": final_report.case_id,
        "accepted": accepted,
        "committed": committed,
        "no_partial_write": no_partial_write,
        "conflict": conflict,
        "proposal_count": len(request.proposals),
        "event_count_before": base_report.event_count,
        "event_count_after": final_report.event_count,
        "committed_event_ids": tuple(item.event_id for item in committed_events),
        "committed_event_addresses": tuple(item.content_address for item in committed_events),
        "simulation_address": None if simulation is None else simulation.content_address,
        "failure_code": failure_code,
        "message": _bounded_message(message),
    }
    if contains_private_key(body):
        raise ValidationError("execution batch result failed the public boundary")
    return ReviewWorkspaceExecutionBatchResult(
        **body,
        simulation=simulation,
        final_report=final_report,
        content_address=_address(body, "review-workspace-execution-batch"),
    )


def _base_guard_failure(
    *,
    request: ReviewWorkspaceExecutionBatchRequest,
    plan: ReviewWorkspacePlan,
    report: ReviewWorkspaceExecutionReport,
    message: str,
) -> ReviewWorkspaceExecutionBatchResult:
    return _result(
        request=request,
        plan=plan,
        base_report=report,
        final_report=report,
        accepted=False,
        committed=False,
        no_partial_write=True,
        conflict=True,
        simulation=None,
        failure_code="stale_base",
        message=message,
    )


def append_review_workspace_plan_execution_batch(
    runtime: Any,
    run_id: str,
    proposals: Iterable[
        ReviewWorkspaceExecutionSimulationProposal | Mapping[str, Any]
    ] = (),
    *,
    expected_execution_address: str | None = None,
    expected_event_count: int | None = None,
    expected_last_event_address: str | None = None,
    baseline_run_id: str | None = None,
    plan_config: Any | None = None,
    execution_store: ReviewPlanExecutionStore | None = None,
) -> ReviewWorkspaceExecutionBatchResult:
    """Simulate and append a sequence only if its captured base is current."""

    plan = build_persisted_review_workspace_plan(
        runtime,
        run_id,
        baseline_run_id=baseline_run_id,
        config=plan_config,
    )
    store = execution_store or ReviewPlanExecutionStore(runtime.store.root)
    base_report = build_persisted_review_workspace_plan_execution(
        runtime,
        run_id,
        baseline_run_id=baseline_run_id,
        plan_config=plan_config,
        execution_store=store,
    )
    request = _request(
        expected_execution_address or base_report.content_address,
        base_report.event_count if expected_event_count is None else expected_event_count,
        (
            base_report.events[-1].content_address
            if expected_last_event_address is None
            and expected_event_count is None
            and base_report.events
            else expected_last_event_address
        ),
        proposals,
    )
    if request.expected_execution_address != base_report.content_address:
        return _base_guard_failure(
            request=request,
            plan=plan,
            report=base_report,
            message="execution batch base address is stale",
        )
    if request.expected_event_count != base_report.event_count:
        return _base_guard_failure(
            request=request,
            plan=plan,
            report=base_report,
            message="execution batch event count is stale",
        )
    actual_last = base_report.events[-1].content_address if base_report.events else None
    if request.expected_last_event_address != actual_last:
        return _base_guard_failure(
            request=request,
            plan=plan,
            report=base_report,
            message="execution batch predecessor address is stale",
        )
    simulation = simulate_review_workspace_plan_execution(
        plan,
        base_report,
        request.proposals,
    )
    if not simulation.accepted:
        rejected = next(
            (item for item in simulation.results if item.evaluated and not item.accepted),
            None,
        )
        return _result(
            request=request,
            plan=plan,
            base_report=base_report,
            final_report=base_report,
            accepted=False,
            committed=False,
            no_partial_write=True,
            conflict=False,
            simulation=simulation,
            failure_code=(
                "batch_validation"
                if rejected is None
                else rejected.error_code or "batch_validation"
            ),
            message=(
                "execution batch rejected by simulation"
                if rejected is None
                else rejected.message
            ),
        )
    projected = simulation.final_report or base_report
    committed_events = projected.events[base_report.event_count :]
    if len(committed_events) != len(request.proposals):
        raise ValidationError("execution batch simulation event count does not reconcile")
    if tuple(item.content_address for item in committed_events) != simulation.proposed_event_addresses:
        raise ValidationError("execution batch simulation event addresses do not reconcile")
    if not committed_events:
        return _result(
            request=request,
            plan=plan,
            base_report=base_report,
            final_report=base_report,
            accepted=True,
            committed=False,
            no_partial_write=True,
            conflict=False,
            simulation=simulation,
            failure_code=None,
            message="empty execution batch required no ledger write",
        )
    try:
        final_report = store.append_many(plan, committed_events)
    except StoreError as exc:
        return _result(
            request=request,
            plan=plan,
            base_report=base_report,
            final_report=base_report,
            accepted=False,
            committed=False,
            no_partial_write=False,
            conflict=False,
            simulation=simulation,
            failure_code="write_failed",
            message=str(exc),
        )
    except ValidationError as exc:
        return _result(
            request=request,
            plan=plan,
            base_report=base_report,
            final_report=base_report,
            accepted=False,
            committed=False,
            no_partial_write=True,
            conflict=True,
            simulation=simulation,
            failure_code=_failure_code(str(exc)),
            message=str(exc),
        )
    return _result(
        request=request,
        plan=plan,
        base_report=base_report,
        final_report=final_report,
        accepted=final_report.accepted,
        committed=True,
        no_partial_write=True,
        conflict=False,
        simulation=simulation,
        failure_code=None,
        message="execution batch appended atomically",
        committed_events=committed_events,
    )


def _result_from_mapping(value: Any) -> ReviewWorkspaceExecutionBatchResult:
    body = _mapping(value, "execution batch result")
    if _private_key_paths(body) or contains_private_key(body):
        raise ValidationError("execution batch result violates the public boundary")
    version = _text(body.get("batch_version"), "batch.batch_version")
    if version != REVIEW_WORKSPACE_EXECUTION_BATCH_VERSION:
        raise ValidationError("execution batch result version is invalid")
    simulation = None
    if "simulation" in body:
        simulation = review_workspace_execution_simulation_from_mapping(
            _mapping(body.get("simulation"), "batch.simulation")
        )
    final_report = None
    if "final_report" in body:
        final_report = review_workspace_execution_report_from_mapping(
            _mapping(body.get("final_report"), "batch.final_report")
        )
    values = {
        "batch_version": version,
        "request_address": _text(body.get("request_address"), "batch.request_address"),
        "base_execution_address": _text(
            body.get("base_execution_address"),
            "batch.base_execution_address",
        ),
        "expected_execution_address": _text(
            body.get("expected_execution_address"),
            "batch.expected_execution_address",
        ),
        "expected_event_count": int(body.get("expected_event_count")),
        "expected_last_event_address": _optional_text(
            body.get("expected_last_event_address"),
            "batch.expected_last_event_address",
        ),
        "final_execution_address": _text(
            body.get("final_execution_address"),
            "batch.final_execution_address",
        ),
        "plan_address": _text(body.get("plan_address"), "batch.plan_address"),
        "execution_id": _text(body.get("execution_id"), "batch.execution_id"),
        "plan_id": _text(body.get("plan_id"), "batch.plan_id"),
        "workspace_id": _text(body.get("workspace_id"), "batch.workspace_id"),
        "run_id": _text(body.get("run_id"), "batch.run_id"),
        "case_id": _text(body.get("case_id"), "batch.case_id"),
        "accepted": bool(body.get("accepted")),
        "committed": bool(body.get("committed")),
        "no_partial_write": bool(body.get("no_partial_write")),
        "conflict": bool(body.get("conflict")),
        "proposal_count": int(body.get("proposal_count")),
        "event_count_before": int(body.get("event_count_before")),
        "event_count_after": int(body.get("event_count_after")),
        "committed_event_ids": _text_sequence(
            body.get("committed_event_ids", ()),
            "batch.committed_event_ids",
        ),
        "committed_event_addresses": _text_sequence(
            body.get("committed_event_addresses", ()),
            "batch.committed_event_addresses",
        ),
        "simulation_address": _optional_text(
            body.get("simulation_address"),
            "batch.simulation_address",
        ),
        "failure_code": _optional_text(body.get("failure_code"), "batch.failure_code"),
        "message": _bounded_message(body.get("message")),
    }
    if values["proposal_count"] < 0 or values["proposal_count"] > REVIEW_WORKSPACE_EXECUTION_BATCH_MAX_PROPOSALS:
        raise ValidationError("execution batch proposal count is outside the bound")
    if values["event_count_before"] < 0 or values["event_count_after"] < values["event_count_before"]:
        raise ValidationError("execution batch event counts are invalid")
    if len(values["committed_event_ids"]) != len(values["committed_event_addresses"]):
        raise ValidationError("execution batch committed event arrays do not reconcile")
    if values["committed"] != bool(values["committed_event_ids"]):
        raise ValidationError("execution batch committed flag does not reconcile")
    if values["event_count_after"] != values["event_count_before"] + len(values["committed_event_ids"]):
        raise ValidationError("execution batch event count does not reconcile")
    if values["accepted"] and values["failure_code"] is not None:
        raise ValidationError("accepted execution batch cannot carry a failure code")
    if simulation is not None:
        if values["simulation_address"] != simulation.content_address:
            raise ValidationError("execution batch simulation address does not reconcile")
        if simulation.proposal_count != values["proposal_count"]:
            raise ValidationError("execution batch simulation proposal count does not reconcile")
    elif values["simulation_address"] is not None:
        raise ValidationError("execution batch simulation is missing")
    if final_report is not None and final_report.content_address != values["final_execution_address"]:
        raise ValidationError("execution batch final report address does not reconcile")
    source = {
        key: item
        for key, item in body.items()
        if key not in {"content_address", "simulation", "final_report"}
    }
    content_address = _text(body.get("content_address"), "batch.content_address")
    if _address(source, "review-workspace-execution-batch") != content_address:
        raise ValidationError("execution batch content address does not reconcile")
    return ReviewWorkspaceExecutionBatchResult(
        **values,
        simulation=simulation,
        final_report=final_report,
        content_address=content_address,
    )


def review_workspace_execution_batch_from_mapping(
    value: Mapping[str, Any],
) -> ReviewWorkspaceExecutionBatchResult:
    """Hydrate a batch result and verify its public summary address."""

    return _result_from_mapping(value)


def review_workspace_execution_batch_json(
    result: ReviewWorkspaceExecutionBatchResult,
    *,
    include_simulation: bool = True,
    include_report: bool = False,
) -> str:
    """Render a canonical batch result."""

    return canonical_json(
        result.to_dict(
            include_simulation=include_simulation,
            include_report=include_report,
        )
    ) + "\n"


def review_workspace_execution_batch_csv(
    result: ReviewWorkspaceExecutionBatchResult,
) -> str:
    """Render one stable summary row for a batch operation."""

    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "batch_version",
            "request_address",
            "base_execution_address",
            "final_execution_address",
            "accepted",
            "committed",
            "no_partial_write",
            "conflict",
            "proposal_count",
            "event_count_before",
            "event_count_after",
            "committed_event_ids",
            "failure_code",
            "message",
            "content_address",
        )
    )
    writer.writerow(
        (
            result.batch_version,
            result.request_address,
            result.base_execution_address,
            result.final_execution_address,
            result.accepted,
            result.committed,
            result.no_partial_write,
            result.conflict,
            result.proposal_count,
            result.event_count_before,
            result.event_count_after,
            canonical_json(result.committed_event_ids),
            result.failure_code or "",
            result.message,
            result.content_address,
        )
    )
    return output.getvalue()


def render_review_workspace_execution_batch_markdown(
    result: ReviewWorkspaceExecutionBatchResult,
) -> str:
    """Render an operator-readable batch receipt."""

    lines = [
        "# Review workspace execution batch",
        "",
        f"- Accepted: `{result.accepted}`",
        f"- Committed: `{result.committed}`",
        f"- No partial write: `{result.no_partial_write}`",
        f"- Conflict: `{result.conflict}`",
        f"- Base execution address: `{result.base_execution_address}`",
        f"- Final execution address: `{result.final_execution_address}`",
        f"- Proposals: `{result.proposal_count}`",
        f"- Event count: `{result.event_count_before}` -> `{result.event_count_after}`",
        f"- Failure code: `{result.failure_code or ''}`",
        f"- Message: {result.message}",
        "",
        "Committed event IDs:",
    ]
    lines.extend(f"- `{event_id}`" for event_id in result.committed_event_ids)
    lines.extend(
        (
            "",
            "The batch receipt is content-addressed and the operation replays the "
            "same public state machine used by single-event append.",
            "",
        )
    )
    return "\n".join(lines)


def review_workspace_execution_batch_export_payloads(
    result: ReviewWorkspaceExecutionBatchResult,
) -> dict[str, str]:
    """Return deterministic JSON, Markdown, and CSV batch artifacts."""

    return {
        "review-workspace-execution-batch.json": review_workspace_execution_batch_json(result),
        "review-workspace-execution-batch.md": render_review_workspace_execution_batch_markdown(result),
        "review-workspace-execution-batch.csv": review_workspace_execution_batch_csv(result),
    }


def review_workspace_execution_batch_schema() -> dict[str, Any]:
    """Return the public batch commit contract."""

    return {
        "version": REVIEW_WORKSPACE_EXECUTION_BATCH_SCHEMA_VERSION,
        "batch_version": REVIEW_WORKSPACE_EXECUTION_BATCH_VERSION,
        "type": "object",
        "required": [
            "batch_version",
            "request_address",
            "base_execution_address",
            "expected_execution_address",
            "final_execution_address",
            "accepted",
            "committed",
            "no_partial_write",
            "conflict",
            "proposal_count",
            "event_count_before",
            "event_count_after",
            "committed_event_ids",
            "committed_event_addresses",
            "content_address",
        ],
        "properties": {
            "batch_version": {"const": REVIEW_WORKSPACE_EXECUTION_BATCH_VERSION},
            "request_address": {"type": "string"},
            "base_execution_address": {"type": "string"},
            "expected_execution_address": {"type": "string"},
            "expected_event_count": {"type": "integer", "minimum": 0},
            "expected_last_event_address": {"type": ["string", "null"]},
            "final_execution_address": {"type": "string"},
            "plan_address": {"type": "string"},
            "execution_id": {"type": "string"},
            "plan_id": {"type": "string"},
            "workspace_id": {"type": "string"},
            "run_id": {"type": "string"},
            "case_id": {"type": "string"},
            "accepted": {"type": "boolean"},
            "committed": {"type": "boolean"},
            "no_partial_write": {"type": "boolean"},
            "conflict": {"type": "boolean"},
            "proposal_count": {"type": "integer", "minimum": 0, "maximum": REVIEW_WORKSPACE_EXECUTION_BATCH_MAX_PROPOSALS},
            "event_count_before": {"type": "integer", "minimum": 0},
            "event_count_after": {"type": "integer", "minimum": 0},
            "committed_event_ids": {"type": "array", "uniqueItems": True},
            "committed_event_addresses": {"type": "array", "uniqueItems": True},
            "simulation_address": {"type": ["string", "null"]},
            "failure_code": {"type": ["string", "null"]},
            "message": {"type": "string", "maxLength": REVIEW_WORKSPACE_EXECUTION_BATCH_MAX_MESSAGE},
            "content_address": {"type": "string"},
        },
        "request_contract": {
            "expected_base_guard": True,
            "proposal_source": "review-workspace-execution-simulation-v1",
            "max_proposals": REVIEW_WORKSPACE_EXECUTION_BATCH_MAX_PROPOSALS,
            "content_addressed": True,
        },
        "write_policy": {
            "preflight_before_write": True,
            "single_manifest_refresh": True,
            "validation_rejection_has_no_partial_write": True,
            "stale_base_has_no_partial_write": True,
            "empty_batch_is_noop": True,
        },
        "boundary": {
            "raw_evidence": False,
            "reviewer_identity": False,
            "agent_identity": False,
            "model_metadata": False,
            "programming_language_metadata": False,
            "scientific_decision": False,
        },
    }


def review_workspace_execution_batch_capabilities() -> dict[str, Any]:
    """Return capability metadata for atomic execution batches."""

    return {
        "version": REVIEW_WORKSPACE_EXECUTION_BATCH_VERSION,
        "optimistic_base_guard": True,
        "simulation_backed_preflight": True,
        "atomic_event_sequence_append": True,
        "single_manifest_refresh": True,
        "validation_before_write": True,
        "stale_base_rejection": True,
        "duplicate_event_rejection": True,
        "dependency_and_check_gates_reused": True,
        "empty_batch_noop": True,
        "structured_conflict_receipt": True,
        "json_export": True,
        "csv_export": True,
        "markdown_export": True,
        "bounded_proposals": True,
        "content_addressed": True,
        "public_boundary_audit": True,
        "cli_surface": True,
        "api_surface": True,
    }


__all__ = [
    "REVIEW_WORKSPACE_EXECUTION_BATCH_MAX_MESSAGE",
    "REVIEW_WORKSPACE_EXECUTION_BATCH_MAX_PROPOSALS",
    "REVIEW_WORKSPACE_EXECUTION_BATCH_SCHEMA_VERSION",
    "REVIEW_WORKSPACE_EXECUTION_BATCH_VERSION",
    "ReviewWorkspaceExecutionBatchRequest",
    "ReviewWorkspaceExecutionBatchResult",
    "append_review_workspace_plan_execution_batch",
    "render_review_workspace_execution_batch_markdown",
    "review_workspace_execution_batch_capabilities",
    "review_workspace_execution_batch_csv",
    "review_workspace_execution_batch_export_payloads",
    "review_workspace_execution_batch_from_mapping",
    "review_workspace_execution_batch_json",
    "review_workspace_execution_batch_schema",
]
