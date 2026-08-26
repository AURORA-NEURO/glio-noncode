"""Side-effect-free simulation of proposed review-plan execution transitions.

The execution ledger is deliberately append-only, so clients should be able to
answer a practical question before writing: *what would this sequence of
transitions do, and where would it fail?*  This module provides that answer
without opening the ledger for writing.  A caller supplies a bounded sequence
of public transition proposals.  Each proposal is compiled into the same
addressed event type used by the explicit append command and is replayed
against the accumulated hypothetical sequence.

Simulation is conservative.  The first invalid proposal stops the hypothetical
sequence, later proposals are reported as not evaluated, and the baseline
report remains untouched.  Successful simulations expose the projected
execution address together with derived metrics, operations, and transition
frontier addresses.  No evidence payload, identity, attribution, model
metadata, programming-language metadata, or scientific decision is accepted or
created by this module.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from io import StringIO
from typing import Any

from .errors import ValidationError
from .module_fabric_support import contains_private_key
from .review_workspace_execution import (
    REVIEW_WORKSPACE_EXECUTION_MAX_REASON,
    REVIEW_WORKSPACE_EXECUTION_MAX_REFERENCES,
    ReviewPlanExecutionEventKind,
    ReviewPlanExecutionStatus,
    ReviewWorkspaceExecutionReport,
    build_review_plan_execution_event,
    replay_review_workspace_plan_execution,
    review_workspace_execution_report_from_mapping,
)
from .review_workspace_execution_metrics import (
    ReviewWorkspaceExecutionMetrics,
    build_review_workspace_execution_metrics,
)
from .review_workspace_execution_operations import (
    ReviewWorkspaceExecutionOperations,
    build_review_workspace_execution_operations,
)
from .review_workspace_execution_transitions import (
    ReviewWorkspaceExecutionTransitionDisposition,
    ReviewWorkspaceExecutionTransitions,
    build_review_workspace_execution_transitions,
)
from .review_workspace_plan import ReviewPlanAction, ReviewWorkspacePlan
from .serialization import canonical_json, content_hash, jsonable


REVIEW_WORKSPACE_EXECUTION_SIMULATION_VERSION = "review-workspace-execution-simulation-v1"
REVIEW_WORKSPACE_EXECUTION_SIMULATION_SCHEMA_VERSION = (
    "review-workspace-execution-simulation-schema-v1"
)
REVIEW_WORKSPACE_EXECUTION_SIMULATION_MAX_PROPOSALS = 500
REVIEW_WORKSPACE_EXECUTION_SIMULATION_MAX_EVENT_ID = 256
REVIEW_WORKSPACE_EXECUTION_SIMULATION_MAX_MESSAGE = 1_000

_EVENT_KIND_VALUES = {item.value for item in ReviewPlanExecutionEventKind}
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
    if len(set(result)) != len(result):
        raise ValidationError(f"{field} must not contain duplicates")
    return result


def _address(value: Any, prefix: str) -> str:
    return content_hash(value, prefix=prefix)


def _address_without_content(body: Mapping[str, Any], prefix: str, field: str) -> str:
    address = _text(body.get("content_address"), field)
    source = {key: item for key, item in body.items() if key != "content_address"}
    if _address(source, prefix) != address:
        raise ValidationError(f"{field} address mismatch")
    return address


def _private_key_paths(value: Any, path: str = "") -> tuple[str, ...]:
    if isinstance(value, Mapping):
        result: list[str] = []
        for key, item in value.items():
            key_text = str(key)
            child = f"{path}.{key_text}" if path else key_text
            if key_text.casefold() in _FORBIDDEN_KEYS:
                result.append(child)
            result.extend(_private_key_paths(item, child))
        return tuple(result)
    if isinstance(value, (list, tuple)):
        result = []
        for index, item in enumerate(value):
            result.extend(_private_key_paths(item, f"{path}[{index}]"))
        return tuple(result)
    return ()


def _bounded_message(value: Any, field: str = "message") -> str:
    normalized = _text(value, field)
    if len(normalized) > REVIEW_WORKSPACE_EXECUTION_SIMULATION_MAX_MESSAGE:
        return normalized[:REVIEW_WORKSPACE_EXECUTION_SIMULATION_MAX_MESSAGE]
    return normalized


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionSimulationProposal:
    """One public transition request used only for hypothetical replay."""

    action_id: str
    kind: str
    event_id: str
    occurred_at: str
    reason: str
    check_ids: tuple[str, ...]
    reference_addresses: tuple[str, ...]
    expected_previous_event_address: str | None
    content_address: str

    def __post_init__(self) -> None:
        if len(self.event_id) > REVIEW_WORKSPACE_EXECUTION_SIMULATION_MAX_EVENT_ID:
            raise ValidationError("simulation proposal event_id exceeds the bound")
        if len(self.reason) > REVIEW_WORKSPACE_EXECUTION_MAX_REASON:
            raise ValidationError("simulation proposal reason exceeds the bound")
        if len(self.reference_addresses) > REVIEW_WORKSPACE_EXECUTION_MAX_REFERENCES:
            raise ValidationError("simulation proposal reference count exceeds the bound")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @classmethod
    def from_mapping(
        cls,
        value: Mapping[str, Any],
    ) -> "ReviewWorkspaceExecutionSimulationProposal":
        body = _mapping(value, "simulation proposal")
        if _private_key_paths(body):
            raise ValidationError("simulation proposal violates the public boundary")
        reason = str(body.get("reason", "")).strip()
        checks = _text_sequence(body.get("check_ids", ()), "simulation proposal.check_ids")
        references = _text_sequence(
            body.get("reference_addresses", ()),
            "simulation proposal.reference_addresses",
        )
        kind = _text(body.get("kind"), "simulation proposal.kind").casefold()
        proposal_body = {
            "action_id": _text(body.get("action_id"), "simulation proposal.action_id"),
            "kind": kind,
            "event_id": _text(body.get("event_id"), "simulation proposal.event_id"),
            "occurred_at": _text(
                body.get("occurred_at"),
                "simulation proposal.occurred_at",
            ),
            "reason": reason,
            "check_ids": checks,
            "reference_addresses": references,
            "expected_previous_event_address": _optional_text(
                body.get("expected_previous_event_address"),
                "simulation proposal.expected_previous_event_address",
            ),
        }
        return cls(
            **proposal_body,
            content_address=_address(
                proposal_body,
                "review-workspace-execution-simulation-proposal",
            ),
        )


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionSimulationResult:
    """Outcome of one evaluated or intentionally skipped proposal."""

    proposal_index: int
    action_id: str
    kind: str
    event_id: str
    evaluated: bool
    accepted: bool
    prior_status: str | None
    resulting_status: str | None
    preflight_disposition: str | None
    previous_event_address: str | None
    event_address: str | None
    resulting_execution_address: str | None
    error_code: str | None
    message: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceExecutionSimulation:
    """Bounded hypothetical execution with derived projected receipts."""

    base_execution_address: str
    plan_address: str
    execution_id: str
    plan_id: str
    workspace_id: str
    run_id: str
    case_id: str
    accepted: bool
    no_side_effects: bool
    proposal_count: int
    evaluated_count: int
    accepted_proposal_count: int
    rejected_proposal_count: int
    stopped_on_error: bool
    rejected_proposal_index: int | None
    projected_event_count: int
    projected_state: str
    final_execution_address: str
    final_metrics_address: str
    final_operations_address: str
    final_transitions_address: str
    applied_event_ids: tuple[str, ...]
    proposed_event_addresses: tuple[str, ...]
    proposals: tuple[ReviewWorkspaceExecutionSimulationProposal, ...]
    results: tuple[ReviewWorkspaceExecutionSimulationResult, ...]
    warnings: tuple[str, ...]
    final_report: ReviewWorkspaceExecutionReport | None
    content_address: str

    def _summary_body(self) -> dict[str, Any]:
        return {
            "simulation_version": REVIEW_WORKSPACE_EXECUTION_SIMULATION_VERSION,
            "base_execution_address": self.base_execution_address,
            "plan_address": self.plan_address,
            "execution_id": self.execution_id,
            "plan_id": self.plan_id,
            "workspace_id": self.workspace_id,
            "run_id": self.run_id,
            "case_id": self.case_id,
            "accepted": self.accepted,
            "no_side_effects": self.no_side_effects,
            "proposal_count": self.proposal_count,
            "evaluated_count": self.evaluated_count,
            "accepted_proposal_count": self.accepted_proposal_count,
            "rejected_proposal_count": self.rejected_proposal_count,
            "stopped_on_error": self.stopped_on_error,
            "rejected_proposal_index": self.rejected_proposal_index,
            "projected_event_count": self.projected_event_count,
            "projected_state": self.projected_state,
            "final_execution_address": self.final_execution_address,
            "final_metrics_address": self.final_metrics_address,
            "final_operations_address": self.final_operations_address,
            "final_transitions_address": self.final_transitions_address,
            "applied_event_ids": self.applied_event_ids,
            "proposed_event_addresses": self.proposed_event_addresses,
            "proposals": self.proposals,
            "results": self.results,
            "warnings": self.warnings,
        }

    def to_dict(self, *, include_report: bool = False) -> dict[str, Any]:
        body = self._summary_body()
        body["content_address"] = self.content_address
        if include_report and self.final_report is not None:
            body["final_report"] = self.final_report
        return jsonable(body)


def _proposal_values(
    proposals: Iterable[
        ReviewWorkspaceExecutionSimulationProposal | Mapping[str, Any]
    ],
) -> tuple[ReviewWorkspaceExecutionSimulationProposal, ...]:
    values = tuple(
        proposal
        if isinstance(proposal, ReviewWorkspaceExecutionSimulationProposal)
        else ReviewWorkspaceExecutionSimulationProposal.from_mapping(proposal)
        for proposal in proposals
    )
    if len(values) > REVIEW_WORKSPACE_EXECUTION_SIMULATION_MAX_PROPOSALS:
        raise ValidationError("execution simulation proposal count exceeds the bound")
    if _private_key_paths(jsonable(values)) or contains_private_key(jsonable(values)):
        raise ValidationError("execution simulation proposals violate the public boundary")
    return values


def _action_map(
    report: ReviewWorkspaceExecutionReport,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for action in report.actions:
        if action.action_id in result:
            raise ValidationError(f"simulation report has duplicate action: {action.action_id}")
        result[action.action_id] = action
    return result


def _plan_action_map(plan: ReviewWorkspacePlan) -> dict[str, ReviewPlanAction]:
    result: dict[str, ReviewPlanAction] = {}
    for action in plan.actions:
        if action.action_id in result:
            raise ValidationError(f"simulation plan has duplicate action: {action.action_id}")
        result[action.action_id] = action
    return result


def _error_code(message: str) -> str:
    text = message.casefold()
    if "stale" in text or "predecessor" in text:
        return "stale_predecessor"
    if "required checks" in text or "check identifiers" in text:
        return "required_checks"
    if "dependencies" in text:
        return "dependencies"
    if "requires a reason" in text or ("reason" in text and "event" in text):
        return "reason_required"
    if "not allowed" in text or "transition" in text and "invalid" in text:
        return "invalid_transition"
    if "different plan" in text:
        return "plan_mismatch"
    if "duplicate" in text:
        return "duplicate_event_id"
    if "iso-8601" in text or "occurred" in text:
        return "invalid_timestamp"
    return "validation_error"


def _result(
    *,
    index: int,
    proposal: ReviewWorkspaceExecutionSimulationProposal,
    evaluated: bool,
    accepted: bool,
    prior_status: ReviewPlanExecutionStatus | None = None,
    resulting_status: ReviewPlanExecutionStatus | None = None,
    preflight_disposition: ReviewWorkspaceExecutionTransitionDisposition | None = None,
    previous_event_address: str | None = None,
    event_address: str | None = None,
    resulting_execution_address: str | None = None,
    error_code: str | None = None,
    message: str,
) -> ReviewWorkspaceExecutionSimulationResult:
    body = {
        "proposal_index": index,
        "action_id": proposal.action_id,
        "kind": proposal.kind,
        "event_id": proposal.event_id,
        "evaluated": evaluated,
        "accepted": accepted,
        "prior_status": None if prior_status is None else prior_status.value,
        "resulting_status": None if resulting_status is None else resulting_status.value,
        "preflight_disposition": (
            None if preflight_disposition is None else preflight_disposition.value
        ),
        "previous_event_address": previous_event_address,
        "event_address": event_address,
        "resulting_execution_address": resulting_execution_address,
        "error_code": error_code,
        "message": _bounded_message(message),
    }
    return ReviewWorkspaceExecutionSimulationResult(
        **body,
        content_address=_address(body, "review-workspace-execution-simulation-result"),
    )


def _transition_option(
    transitions: ReviewWorkspaceExecutionTransitions,
    proposal: ReviewWorkspaceExecutionSimulationProposal,
) -> Any | None:
    if proposal.kind not in _EVENT_KIND_VALUES:
        return None
    for action in transitions.actions:
        if action.action_id != proposal.action_id:
            continue
        return next(
            (item for item in action.options if item.kind.value == proposal.kind),
            None,
        )
    return None


def _baseline_projection(
    plan: ReviewWorkspacePlan,
    report: ReviewWorkspaceExecutionReport,
) -> tuple[
    ReviewWorkspaceExecutionMetrics,
    ReviewWorkspaceExecutionOperations,
    ReviewWorkspaceExecutionTransitions,
]:
    metrics = build_review_workspace_execution_metrics(plan, report)
    operations = build_review_workspace_execution_operations(plan, report, metrics)
    transitions = build_review_workspace_execution_transitions(plan, report)
    return metrics, operations, transitions


def simulate_review_workspace_plan_execution(
    plan: ReviewWorkspacePlan,
    report: ReviewWorkspaceExecutionReport,
    proposals: Iterable[
        ReviewWorkspaceExecutionSimulationProposal | Mapping[str, Any]
    ] = (),
) -> ReviewWorkspaceExecutionSimulation:
    """Replay proposed events in memory and return a bounded diagnostic result."""

    if not isinstance(plan, ReviewWorkspacePlan):
        raise ValidationError("execution simulation requires a typed source plan")
    if not isinstance(report, ReviewWorkspaceExecutionReport):
        raise ValidationError("execution simulation requires a typed execution report")
    if not plan.accepted or not report.accepted:
        raise ValidationError("execution simulation requires accepted plan and report")
    if plan.plan_id != report.plan_id or plan.content_address != report.plan_address:
        raise ValidationError("execution simulation plan and report addresses differ")
    replayed_baseline = replay_review_workspace_plan_execution(plan, report.events)
    if replayed_baseline.to_dict() != report.to_dict():
        raise ValidationError("execution simulation baseline does not replay against the plan")
    plan_actions = _plan_action_map(plan)
    current_report = report
    current_events = list(report.events)
    selected = _proposal_values(proposals)
    results: list[ReviewWorkspaceExecutionSimulationResult] = []
    applied_event_ids: list[str] = []
    proposed_event_addresses: list[str] = []
    stopped = False
    rejected_index: int | None = None
    evaluated_count = 0
    rejected_count = 0
    for index, proposal in enumerate(selected):
        if stopped:
            results.append(
                _result(
                    index=index,
                    proposal=proposal,
                    evaluated=False,
                    accepted=False,
                    error_code="not_evaluated",
                    message="proposal was not evaluated after an earlier proposal failed",
                )
            )
            continue
        evaluated_count += 1
        action_row = _action_map(current_report).get(proposal.action_id)
        previous_address = current_events[-1].content_address if current_events else None
        try:
            if proposal.action_id not in plan_actions:
                raise ValidationError(f"simulation names unknown action: {proposal.action_id}")
            if action_row is None:
                raise ValidationError(f"simulation report omits action: {proposal.action_id}")
            transition_frontier = build_review_workspace_execution_transitions(
                plan,
                current_report,
            )
            option = _transition_option(transition_frontier, proposal)
            if proposal.kind not in _EVENT_KIND_VALUES:
                raise ValidationError(f"simulation event kind is invalid: {proposal.kind}")
            if proposal.expected_previous_event_address not in (None, previous_address):
                raise ValidationError("simulation proposal predecessor is stale")
            event = build_review_plan_execution_event(
                plan=plan,
                action_id=proposal.action_id,
                event_id=proposal.event_id,
                kind=proposal.kind,
                occurred_at=proposal.occurred_at,
                reason=proposal.reason,
                check_ids=proposal.check_ids,
                reference_addresses=proposal.reference_addresses,
                previous_event_address=previous_address,
            )
            proposed_event_addresses.append(event.content_address)
            projected_events = (*current_events, event)
            projected = replay_review_workspace_plan_execution(plan, projected_events)
            resulting_action = _action_map(projected)[proposal.action_id]
            results.append(
                _result(
                    index=index,
                    proposal=proposal,
                    evaluated=True,
                    accepted=True,
                    prior_status=action_row.status,
                    resulting_status=resulting_action.status,
                    preflight_disposition=(
                        None if option is None else option.disposition
                    ),
                    previous_event_address=previous_address,
                    event_address=event.content_address,
                    resulting_execution_address=projected.content_address,
                    message="proposal replayed successfully in memory",
                )
            )
            current_events.append(event)
            current_report = projected
            applied_event_ids.append(event.event_id)
        except ValidationError as exc:
            rejected_count += 1
            stopped = True
            rejected_index = index
            transition_frontier = None
            try:
                transition_frontier = build_review_workspace_execution_transitions(
                    plan,
                    current_report,
                )
            except ValidationError:
                transition_frontier = None
            option = (
                None
                if transition_frontier is None
                else _transition_option(transition_frontier, proposal)
            )
            results.append(
                _result(
                    index=index,
                    proposal=proposal,
                    evaluated=True,
                    accepted=False,
                    prior_status=None if action_row is None else action_row.status,
                    preflight_disposition=(
                        None if option is None else option.disposition
                    ),
                    previous_event_address=previous_address,
                    error_code=_error_code(str(exc)),
                    message=str(exc),
                )
            )
    metrics, operations, transitions = _baseline_projection(plan, current_report)
    accepted = not stopped and len(results) == len(selected)
    warnings = (
        "simulation is read-only and does not append events to the execution ledger",
        "a rejected proposal stops evaluation of later proposals",
        "successful proposals are hypothetical until explicitly appended and replayed",
    )
    body = {
        "simulation_version": REVIEW_WORKSPACE_EXECUTION_SIMULATION_VERSION,
        "base_execution_address": report.content_address,
        "plan_address": plan.content_address,
        "execution_id": report.execution_id,
        "plan_id": plan.plan_id,
        "workspace_id": report.workspace_id,
        "run_id": report.run_id,
        "case_id": report.case_id,
        "accepted": accepted,
        "no_side_effects": True,
        "proposal_count": len(selected),
        "evaluated_count": evaluated_count,
        "accepted_proposal_count": len(applied_event_ids),
        "rejected_proposal_count": rejected_count,
        "stopped_on_error": stopped,
        "rejected_proposal_index": rejected_index,
        "projected_event_count": current_report.event_count,
        "projected_state": current_report.state.value,
        "final_execution_address": current_report.content_address,
        "final_metrics_address": metrics.content_address,
        "final_operations_address": operations.content_address,
        "final_transitions_address": transitions.content_address,
        "applied_event_ids": tuple(applied_event_ids),
        "proposed_event_addresses": tuple(proposed_event_addresses),
        "proposals": selected,
        "results": tuple(results),
        "warnings": warnings,
    }
    if contains_private_key(body):
        raise ValidationError("execution simulation failed the public boundary")
    return ReviewWorkspaceExecutionSimulation(
        base_execution_address=report.content_address,
        plan_address=plan.content_address,
        execution_id=report.execution_id,
        plan_id=plan.plan_id,
        workspace_id=report.workspace_id,
        run_id=report.run_id,
        case_id=report.case_id,
        accepted=accepted,
        no_side_effects=True,
        proposal_count=len(selected),
        evaluated_count=evaluated_count,
        accepted_proposal_count=len(applied_event_ids),
        rejected_proposal_count=rejected_count,
        stopped_on_error=stopped,
        rejected_proposal_index=rejected_index,
        projected_event_count=current_report.event_count,
        projected_state=current_report.state.value,
        final_execution_address=current_report.content_address,
        final_metrics_address=metrics.content_address,
        final_operations_address=operations.content_address,
        final_transitions_address=transitions.content_address,
        applied_event_ids=tuple(applied_event_ids),
        proposed_event_addresses=tuple(proposed_event_addresses),
        proposals=selected,
        results=tuple(results),
        warnings=warnings,
        final_report=current_report,
        content_address=_address(body, "review-workspace-execution-simulation"),
    )


def _proposal_from_mapping(value: Any) -> ReviewWorkspaceExecutionSimulationProposal:
    return ReviewWorkspaceExecutionSimulationProposal.from_mapping(
        _mapping(value, "simulation proposal")
    )


def _result_from_mapping(value: Any) -> ReviewWorkspaceExecutionSimulationResult:
    body = _mapping(value, "simulation result")
    content_address = _address_without_content(
        body,
        "review-workspace-execution-simulation-result",
        "simulation result.content_address",
    )
    return ReviewWorkspaceExecutionSimulationResult(
        proposal_index=int(body.get("proposal_index")),
        action_id=_text(body.get("action_id"), "simulation result.action_id"),
        kind=_text(body.get("kind"), "simulation result.kind"),
        event_id=_text(body.get("event_id"), "simulation result.event_id"),
        evaluated=bool(body.get("evaluated")),
        accepted=bool(body.get("accepted")),
        prior_status=_optional_text(body.get("prior_status"), "simulation result.prior_status"),
        resulting_status=_optional_text(
            body.get("resulting_status"),
            "simulation result.resulting_status",
        ),
        preflight_disposition=_optional_text(
            body.get("preflight_disposition"),
            "simulation result.preflight_disposition",
        ),
        previous_event_address=_optional_text(
            body.get("previous_event_address"),
            "simulation result.previous_event_address",
        ),
        event_address=_optional_text(body.get("event_address"), "simulation result.event_address"),
        resulting_execution_address=_optional_text(
            body.get("resulting_execution_address"),
            "simulation result.resulting_execution_address",
        ),
        error_code=_optional_text(body.get("error_code"), "simulation result.error_code"),
        message=_bounded_message(body.get("message")),
        content_address=content_address,
    )


def review_workspace_execution_simulation_from_mapping(
    value: Mapping[str, Any],
) -> ReviewWorkspaceExecutionSimulation:
    """Hydrate and verify a simulation summary artifact."""

    body = _mapping(value, "execution simulation")
    if _private_key_paths(body):
        raise ValidationError("execution simulation violates the public boundary")
    version = _text(body.get("simulation_version"), "simulation.simulation_version")
    if version != REVIEW_WORKSPACE_EXECUTION_SIMULATION_VERSION:
        raise ValidationError("execution simulation version is invalid")
    raw_proposals = body.get("proposals", ())
    raw_results = body.get("results", ())
    if not isinstance(raw_proposals, (list, tuple)) or not isinstance(raw_results, (list, tuple)):
        raise ValidationError("execution simulation proposals and results must be arrays")
    proposals = tuple(_proposal_from_mapping(item) for item in raw_proposals)
    results = tuple(_result_from_mapping(item) for item in raw_results)
    if len(proposals) != int(body.get("proposal_count", -1)):
        raise ValidationError("execution simulation proposal count does not reconcile")
    if len(results) != len(proposals):
        raise ValidationError("execution simulation result count does not reconcile")
    proposal_indexes = tuple(item.proposal_index for item in results)
    if proposal_indexes != tuple(range(len(results))):
        raise ValidationError("execution simulation result indexes are not contiguous")
    accepted_results = tuple(item for item in results if item.accepted)
    evaluated_results = tuple(item for item in results if item.evaluated)
    if len(evaluated_results) != int(body.get("evaluated_count", -1)):
        raise ValidationError("execution simulation evaluated count does not reconcile")
    if len(accepted_results) != int(body.get("accepted_proposal_count", -1)):
        raise ValidationError("execution simulation accepted count does not reconcile")
    rejected_results = tuple(item for item in results if item.evaluated and not item.accepted)
    if len(rejected_results) != int(body.get("rejected_proposal_count", -1)):
        raise ValidationError("execution simulation rejected count does not reconcile")
    expected_stopped = bool(rejected_results)
    if bool(body.get("stopped_on_error")) != expected_stopped:
        raise ValidationError("execution simulation stopped flag does not reconcile")
    rejected_index = body.get("rejected_proposal_index")
    expected_index = rejected_results[0].proposal_index if rejected_results else None
    if rejected_index != expected_index:
        raise ValidationError("execution simulation rejected index does not reconcile")
    warnings = _text_sequence(body.get("warnings", ()), "simulation.warnings")
    values = {
        "base_execution_address": _text(body.get("base_execution_address"), "simulation.base_execution_address"),
        "plan_address": _text(body.get("plan_address"), "simulation.plan_address"),
        "execution_id": _text(body.get("execution_id"), "simulation.execution_id"),
        "plan_id": _text(body.get("plan_id"), "simulation.plan_id"),
        "workspace_id": _text(body.get("workspace_id"), "simulation.workspace_id"),
        "run_id": _text(body.get("run_id"), "simulation.run_id"),
        "case_id": _text(body.get("case_id"), "simulation.case_id"),
        "accepted": bool(body.get("accepted")),
        "no_side_effects": bool(body.get("no_side_effects")),
        "proposal_count": len(proposals),
        "evaluated_count": len(evaluated_results),
        "accepted_proposal_count": len(accepted_results),
        "rejected_proposal_count": len(rejected_results),
        "stopped_on_error": expected_stopped,
        "rejected_proposal_index": expected_index,
        "projected_event_count": int(body.get("projected_event_count")),
        "projected_state": _text(body.get("projected_state"), "simulation.projected_state"),
        "final_execution_address": _text(body.get("final_execution_address"), "simulation.final_execution_address"),
        "final_metrics_address": _text(body.get("final_metrics_address"), "simulation.final_metrics_address"),
        "final_operations_address": _text(body.get("final_operations_address"), "simulation.final_operations_address"),
        "final_transitions_address": _text(body.get("final_transitions_address"), "simulation.final_transitions_address"),
        "applied_event_ids": _text_sequence(body.get("applied_event_ids", ()), "simulation.applied_event_ids"),
        "proposed_event_addresses": _text_sequence(body.get("proposed_event_addresses", ()), "simulation.proposed_event_addresses"),
        "proposals": proposals,
        "results": results,
        "warnings": warnings,
    }
    if not values["no_side_effects"]:
        raise ValidationError("execution simulation must declare no_side_effects")
    if tuple(item.event_id for item in accepted_results) != values["applied_event_ids"]:
        raise ValidationError("execution simulation applied event IDs do not reconcile")
    if len(values["proposed_event_addresses"]) != len(accepted_results):
        raise ValidationError("execution simulation proposed event addresses do not reconcile")
    source = {
        key: item
        for key, item in body.items()
        if key not in {"content_address", "final_report"}
    }
    content_address = _text(body.get("content_address"), "simulation.content_address")
    if _address(source, "review-workspace-execution-simulation") != content_address:
        raise ValidationError("execution simulation content address does not reconcile")
    final_report = None
    if "final_report" in body:
        final_report = review_workspace_execution_report_from_mapping(
            _mapping(body.get("final_report"), "simulation.final_report")
        )
        if final_report.content_address != values["final_execution_address"]:
            raise ValidationError("simulation final report address does not reconcile")
    if bool(values["accepted"]) != (not expected_stopped and len(accepted_results) == len(proposals)):
        raise ValidationError("execution simulation accepted flag does not reconcile")
    return ReviewWorkspaceExecutionSimulation(
        **values,
        final_report=final_report,
        content_address=content_address,
    )


def review_workspace_execution_simulation_json(
    simulation: ReviewWorkspaceExecutionSimulation,
    *,
    include_report: bool = False,
) -> str:
    """Render canonical simulation JSON."""

    return canonical_json(simulation.to_dict(include_report=include_report)) + "\n"


def review_workspace_execution_simulation_csv(
    simulation: ReviewWorkspaceExecutionSimulation,
) -> str:
    """Render proposal outcomes as deterministic CSV."""

    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "proposal_index",
            "action_id",
            "kind",
            "event_id",
            "evaluated",
            "accepted",
            "prior_status",
            "resulting_status",
            "preflight_disposition",
            "previous_event_address",
            "event_address",
            "resulting_execution_address",
            "error_code",
            "message",
            "content_address",
        )
    )
    for item in simulation.results:
        writer.writerow(
            (
                item.proposal_index,
                item.action_id,
                item.kind,
                item.event_id,
                item.evaluated,
                item.accepted,
                item.prior_status or "",
                item.resulting_status or "",
                item.preflight_disposition or "",
                item.previous_event_address or "",
                item.event_address or "",
                item.resulting_execution_address or "",
                item.error_code or "",
                item.message,
                item.content_address,
            )
        )
    return output.getvalue()


def render_review_workspace_execution_simulation_markdown(
    simulation: ReviewWorkspaceExecutionSimulation,
) -> str:
    """Render an operator-readable simulation report."""

    lines = [
        "# Review workspace execution simulation",
        "",
        f"- Accepted: `{simulation.accepted}`",
        f"- No side effects: `{simulation.no_side_effects}`",
        f"- Base execution address: `{simulation.base_execution_address}`",
        f"- Final execution address: `{simulation.final_execution_address}`",
        f"- Proposals: `{simulation.proposal_count}`",
        f"- Evaluated: `{simulation.evaluated_count}`",
        f"- Accepted proposals: `{simulation.accepted_proposal_count}`",
        f"- Rejected proposals: `{simulation.rejected_proposal_count}`",
        f"- Projected state: `{simulation.projected_state}`",
        f"- Projected event count: `{simulation.projected_event_count}`",
        "",
        "| # | Action | Kind | Evaluated | Accepted | Preflight | Error | Message |",
        "| ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in simulation.results:
        lines.append(
            f"| {item.proposal_index} | `{item.action_id}` | `{item.kind}` | "
            f"{item.evaluated} | {item.accepted} | "
            f"`{item.preflight_disposition or ''}` | "
            f"`{item.error_code or ''}` | {item.message} |"
        )
    lines.extend(
        (
            "",
            "This report is a hypothetical replay. It does not append to the "
            "ledger; successful proposals must still be explicitly appended and replayed.",
            "",
        )
    )
    return "\n".join(lines)


def review_workspace_execution_simulation_export_payloads(
    simulation: ReviewWorkspaceExecutionSimulation,
) -> dict[str, str]:
    """Return canonical JSON, Markdown, and CSV simulation artifacts."""

    return {
        "review-workspace-execution-simulation.json": review_workspace_execution_simulation_json(
            simulation
        ),
        "review-workspace-execution-simulation.md": render_review_workspace_execution_simulation_markdown(
            simulation
        ),
        "review-workspace-execution-simulation.csv": review_workspace_execution_simulation_csv(
            simulation
        ),
    }


def review_workspace_execution_simulation_schema() -> dict[str, Any]:
    """Return the public simulation contract."""

    return {
        "version": REVIEW_WORKSPACE_EXECUTION_SIMULATION_SCHEMA_VERSION,
        "type": "object",
        "required": [
            "simulation_version",
            "base_execution_address",
            "plan_address",
            "proposal_count",
            "results",
            "accepted",
            "no_side_effects",
            "content_address",
        ],
        "properties": {
            "simulation_version": {"const": REVIEW_WORKSPACE_EXECUTION_SIMULATION_VERSION},
            "base_execution_address": {"type": "string"},
            "plan_address": {"type": "string"},
            "execution_id": {"type": "string"},
            "plan_id": {"type": "string"},
            "workspace_id": {"type": "string"},
            "run_id": {"type": "string"},
            "case_id": {"type": "string"},
            "accepted": {"type": "boolean"},
            "no_side_effects": {"const": True},
            "proposal_count": {"type": "integer", "minimum": 0, "maximum": REVIEW_WORKSPACE_EXECUTION_SIMULATION_MAX_PROPOSALS},
            "evaluated_count": {"type": "integer", "minimum": 0},
            "accepted_proposal_count": {"type": "integer", "minimum": 0},
            "rejected_proposal_count": {"type": "integer", "minimum": 0},
            "stopped_on_error": {"type": "boolean"},
            "rejected_proposal_index": {"type": ["integer", "null"]},
            "projected_event_count": {"type": "integer", "minimum": 0},
            "projected_state": {"type": "string"},
            "final_execution_address": {"type": "string"},
            "final_metrics_address": {"type": "string"},
            "final_operations_address": {"type": "string"},
            "final_transitions_address": {"type": "string"},
            "applied_event_ids": {"type": "array", "uniqueItems": True},
            "proposed_event_addresses": {"type": "array", "uniqueItems": True},
            "proposals": {"type": "array", "maxItems": REVIEW_WORKSPACE_EXECUTION_SIMULATION_MAX_PROPOSALS},
            "results": {"type": "array", "maxItems": REVIEW_WORKSPACE_EXECUTION_SIMULATION_MAX_PROPOSALS},
            "warnings": {"type": "array"},
            "content_address": {"type": "string"},
        },
        "proposal_contract": {
            "fields": [
                "action_id",
                "kind",
                "event_id",
                "occurred_at",
                "reason",
                "check_ids",
                "reference_addresses",
                "expected_previous_event_address",
            ],
            "event_kinds": sorted(_EVENT_KIND_VALUES),
            "automatic_predecessor_linking": True,
            "stale_predecessor_detection": True,
            "bounded": True,
        },
        "failure_policy": {
            "first_failure_stops_sequence": True,
            "later_proposals_reported_not_evaluated": True,
            "baseline_is_unchanged": True,
        },
        "projected_receipts": {
            "execution": True,
            "metrics": True,
            "operations": True,
            "transitions": True,
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


def review_workspace_execution_simulation_capabilities() -> dict[str, Any]:
    """Return capability metadata without proposal-specific rows."""

    return {
        "version": REVIEW_WORKSPACE_EXECUTION_SIMULATION_VERSION,
        "side_effect_free": True,
        "hypothetical_replay": True,
        "sequential_proposal_validation": True,
        "first_failure_stops": True,
        "not_evaluated_tail_reporting": True,
        "state_machine_preflight": True,
        "dependency_preflight": True,
        "required_check_preflight": True,
        "reason_preflight": True,
        "stale_predecessor_detection": True,
        "automatic_event_chain_linking": True,
        "projected_execution_receipt": True,
        "projected_metrics_receipt": True,
        "projected_operations_receipt": True,
        "projected_transitions_receipt": True,
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
    "REVIEW_WORKSPACE_EXECUTION_SIMULATION_MAX_EVENT_ID",
    "REVIEW_WORKSPACE_EXECUTION_SIMULATION_MAX_MESSAGE",
    "REVIEW_WORKSPACE_EXECUTION_SIMULATION_MAX_PROPOSALS",
    "REVIEW_WORKSPACE_EXECUTION_SIMULATION_SCHEMA_VERSION",
    "REVIEW_WORKSPACE_EXECUTION_SIMULATION_VERSION",
    "ReviewWorkspaceExecutionSimulation",
    "ReviewWorkspaceExecutionSimulationProposal",
    "ReviewWorkspaceExecutionSimulationResult",
    "review_workspace_execution_simulation_capabilities",
    "review_workspace_execution_simulation_csv",
    "review_workspace_execution_simulation_export_payloads",
    "review_workspace_execution_simulation_from_mapping",
    "review_workspace_execution_simulation_json",
    "review_workspace_execution_simulation_schema",
    "render_review_workspace_execution_simulation_markdown",
    "simulate_review_workspace_plan_execution",
]
