"""Typed adapter registry for the four C09-C12 alpha operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .causal_alpha import (
    ConfoundingChecklistAdjudicator,
    DependenceMethod,
    EvidenceDependenceCorrector,
    MediationSensitivityAnalyzer,
    NegativeEvidenceIntegrator,
)
from .causal_beta import MediatorKind
from .causal_reasoning import CausalState
from .causal_alpha_frontier_public_data import CausalAlphaFrontierOperation, CausalAlphaFrontierRecord
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierAdapter:
    """One operation adapter with explicit input/output ownership."""

    operation: CausalAlphaFrontierOperation
    adapter_id: str
    implementation: str
    required_payload_keys: tuple[str, ...]
    limitation: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"operation": self.operation, "adapter_id": self.adapter_id, "implementation": self.implementation, "required_payload_keys": self.required_payload_keys, "limitation": self.limitation}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierAdapterRegistry:
    """Closed registry proving every fixture operation has an adapter."""

    adapters: tuple[CausalAlphaFrontierAdapter, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: CausalAlphaFrontierOperation | str) -> CausalAlphaFrontierAdapter:
        value = CausalAlphaFrontierOperation(str(operation))
        return next(item for item in self.adapters if item.operation is value)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"adapters": [item.to_dict() for item in self.adapters], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierEvaluationResult:
    """Normalized adapter result paired with expected fixture evidence."""

    record_id: str
    operation: CausalAlphaFrontierOperation
    expected_state: CausalState
    observed_state: CausalState
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    output: Mapping[str, Any]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def state_match(self) -> bool:
        return self.expected_state is self.observed_state

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"record_id": self.record_id, "operation": self.operation, "expected_state": self.expected_state, "observed_state": self.observed_state, "expected_issue_codes": self.expected_issue_codes, "observed_issue_codes": self.observed_issue_codes, "output": jsonable(self.output), "accepted": self.accepted, "state_match": self.state_match}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierEvaluation:
    """Full fixture replay with per-operation and per-row closure."""

    fixture_id: str
    results: tuple[CausalAlphaFrontierEvaluationResult, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def mismatches(self) -> tuple[CausalAlphaFrontierEvaluationResult, ...]:
        return tuple(item for item in self.results if not item.accepted)

    def for_operation(self, operation: CausalAlphaFrontierOperation | str) -> tuple[CausalAlphaFrontierEvaluationResult, ...]:
        value = CausalAlphaFrontierOperation(str(operation))
        return tuple(item for item in self.results if item.operation is value)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "results": [item.to_dict() for item in self.results], "mismatches": [item.record_id for item in self.mismatches], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_causal_alpha_frontier_adapters() -> CausalAlphaFrontierAdapterRegistry:
    adapters = (
        CausalAlphaFrontierAdapter(CausalAlphaFrontierOperation.MEDIATION_SENSITIVITY, "alpha-c09-mediation", "MediationSensitivityAnalyzer.analyze", ("mediator_kind", "source_node", "target_node", "evidence"), "source omission is sensitivity analysis, not causal identification"),
        CausalAlphaFrontierAdapter(CausalAlphaFrontierOperation.CONFOUNDING_CHECKLIST, "alpha-c10-confounding", "ConfoundingChecklistAdjudicator.assess", ("required_confounder_ids", "observations"), "checklist completion does not prove absence of unmeasured confounding"),
        CausalAlphaFrontierAdapter(CausalAlphaFrontierOperation.DEPENDENCE_CORRECTION, "alpha-c11-dependence", "EvidenceDependenceCorrector.correct", ("observations",), "declared grouping yields a bounded support proxy"),
        CausalAlphaFrontierAdapter(CausalAlphaFrontierOperation.NEGATIVE_EVIDENCE, "alpha-c12-negative", "NegativeEvidenceIntegrator.integrate", ("observations",), "negative evidence is not proof of absence"),
    )
    return CausalAlphaFrontierAdapterRegistry(adapters, len(adapters) == 4 and {item.operation for item in adapters} == set(CausalAlphaFrontierOperation))


def _run_adapter(record: CausalAlphaFrontierRecord, requested_context: str | None = None) -> Any:
    payload = record.payload
    context_key = requested_context or record.context_key
    if record.operation is CausalAlphaFrontierOperation.MEDIATION_SENSITIVITY:
        return MediationSensitivityAnalyzer().analyze(payload["evidence"], mediator_kind=MediatorKind(str(payload["mediator_kind"])), source_node=str(payload["source_node"]), target_node=str(payload["target_node"]), context_key=context_key, model_id="causal-alpha-frontier", model_version="2026.08", robustness_tolerance=0.2)
    if record.operation is CausalAlphaFrontierOperation.CONFOUNDING_CHECKLIST:
        return ConfoundingChecklistAdjudicator().assess(payload["observations"], context_key=context_key, required_confounder_ids=payload["required_confounder_ids"])
    if record.operation is CausalAlphaFrontierOperation.DEPENDENCE_CORRECTION:
        return EvidenceDependenceCorrector().correct(payload["observations"], context_key=context_key, minimum_independent_groups=2)
    if record.operation is CausalAlphaFrontierOperation.NEGATIVE_EVIDENCE:
        return NegativeEvidenceIntegrator().integrate(payload["observations"], context_key=context_key, minimum_negative_controls=1)
    raise ValidationError(f"unsupported causal alpha operation: {record.operation}")


def _state_and_issues(output: Any) -> tuple[CausalState, tuple[str, ...]]:
    state = getattr(output, "state", None)
    if state is None and hasattr(output, "result"):
        state = output.result.sensitivity_state
    if not isinstance(state, CausalState) and hasattr(state, "value"):
        state = CausalState(str(state.value))
    if not isinstance(state, CausalState):
        raise ValidationError("causal alpha adapter did not return a typed state")
    issues = tuple(sorted({str(item.code) for item in getattr(output, "issues", ())}))
    if state is CausalState.OUT_OF_DOMAIN and "context_mismatch" not in issues:
        issues = tuple(sorted((*issues, "context_mismatch")))
    return state, issues


def evaluate_causal_alpha_frontier_fixture(fixture: Any) -> CausalAlphaFrontierEvaluation:
    results: list[CausalAlphaFrontierEvaluationResult] = []
    for record in fixture.records:
        output = _run_adapter(record, fixture.context_key)
        observed_state, observed_issues = _state_and_issues(output)
        if record.context_key != fixture.context_key:
            observed_state = CausalState.OUT_OF_DOMAIN
            observed_issues = tuple(sorted({*observed_issues, "context_mismatch"}))
        accepted = observed_state is record.expected_state
        results.append(CausalAlphaFrontierEvaluationResult(record.record_id, record.operation, record.expected_state, observed_state, record.expected_issue_codes, observed_issues, output.to_dict(), accepted))
    return CausalAlphaFrontierEvaluation(fixture.fixture_id, tuple(results), all(item.accepted for item in results))


__all__ = [
    "CausalAlphaFrontierAdapter",
    "CausalAlphaFrontierAdapterRegistry",
    "CausalAlphaFrontierEvaluation",
    "CausalAlphaFrontierEvaluationResult",
    "build_causal_alpha_frontier_adapters",
    "evaluate_causal_alpha_frontier_fixture",
]
