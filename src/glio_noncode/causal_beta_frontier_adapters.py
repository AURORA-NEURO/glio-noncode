"""Typed adapters from C05-C08 fixture envelopes to beta primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .causal_beta import (
    CausalBetaState,
    CausalMediatorEvidence,
    CounterfactualAlleleStateObservation,
    CounterfactualAlleleStateSimulator,
    ElementToGeneCausalMediator,
    GeneToStateCausalMediator,
    MediatorKind,
    SequenceToElementCausalMediator,
)
from .causal_beta_frontier_public_data import (
    CAUSAL_BETA_FRONTIER_CONTEXT_KEY,
    CausalBetaFrontierOperation,
    CausalBetaFrontierRecord,
)
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierAdapterSpec:
    operation: CausalBetaFrontierOperation
    adapter_id: str
    primitive: str
    input_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    states: tuple[str, ...]
    limitation: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierAdapterResult:
    record_id: str
    operation: CausalBetaFrontierOperation
    state: CausalBetaState
    issue_codes: tuple[str, ...]
    support: float | None
    uncertainty: float
    sensitivity: float | None
    delta: float | None
    evidence_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    source_versions: tuple[str, ...]
    primitive_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierAdapterRegistry:
    specs: tuple[CausalBetaFrontierAdapterSpec, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: CausalBetaFrontierOperation | str) -> CausalBetaFrontierAdapterSpec:
        value = CausalBetaFrontierOperation(str(operation))
        return next(item for item in self.specs if item.operation is value)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"specs": [item.to_dict() for item in self.specs], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _evidence(record: CausalBetaFrontierRecord) -> tuple[CausalMediatorEvidence, ...]:
    return tuple(CausalMediatorEvidence(**dict(item)) for item in record.payload.get("evidence", ()))


def _observations(record: CausalBetaFrontierRecord) -> tuple[CounterfactualAlleleStateObservation, ...]:
    return tuple(CounterfactualAlleleStateObservation(**dict(item)) for item in record.payload.get("observations", ()))


def _result(record: CausalBetaFrontierRecord, state: CausalBetaState, issues: tuple[str, ...], *, support: float | None = None, uncertainty: float = 1.0, sensitivity: float | None = None, delta: float | None = None, evidence_ids: tuple[str, ...] = (), source_ids: tuple[str, ...] = (), source_versions: tuple[str, ...] = (), primitive_address: str = "") -> CausalBetaFrontierAdapterResult:
    body = {"record_id": record.record_id, "operation": record.operation, "state": state, "issues": issues, "support": support, "uncertainty": uncertainty, "sensitivity": sensitivity, "delta": delta, "evidence_ids": evidence_ids, "source_ids": source_ids, "source_versions": source_versions, "primitive_address": primitive_address}
    return CausalBetaFrontierAdapterResult(record.record_id, record.operation, state, issues, support, uncertainty, sensitivity, delta, evidence_ids, source_ids, source_versions, primitive_address, content_hash(body))


def _foreign(record: CausalBetaFrontierRecord) -> CausalBetaFrontierAdapterResult:
    return _result(record, CausalBetaState.OUT_OF_DOMAIN, ("context_mismatch",))


def _mediator(record: CausalBetaFrontierRecord, mediator: Any, kind: MediatorKind) -> CausalBetaFrontierAdapterResult:
    if record.context_key != CAUSAL_BETA_FRONTIER_CONTEXT_KEY:
        return _foreign(record)
    result = mediator.evaluate(_evidence(record), source_node=str(record.payload["source_node"]), target_node=str(record.payload["target_node"]), context_key=record.context_key, model_id=f"{record.operation.value}-frontier", model_version="2026.08", minimum_sources=2)
    issues: list[str] = []
    if result.state is CausalBetaState.PARTIAL:
        issues.append("minimum_independent_sources")
    if result.state is CausalBetaState.CONTRADICTORY:
        issues.append("negative_control_conflict" if any(item.negative_control for item in _evidence(record)) else "contradictory_direction")
    if result.state is CausalBetaState.ABSTAINED:
        issues.append("missing_evidence")
    if result.state is CausalBetaState.OUT_OF_DOMAIN:
        issues.append("context_mismatch")
    return _result(record, result.state, tuple(issues), support=result.support, uncertainty=result.uncertainty, sensitivity=result.sensitivity, evidence_ids=result.evidence_ids, source_ids=result.source_ids, source_versions=result.source_versions, primitive_address=result.content_address)


def _counterfactual(record: CausalBetaFrontierRecord) -> CausalBetaFrontierAdapterResult:
    if record.context_key != CAUSAL_BETA_FRONTIER_CONTEXT_KEY:
        return _foreign(record)
    result = CounterfactualAlleleStateSimulator().simulate(_observations(record), state_id=str(record.payload["state_id"]), context_key=record.context_key, model_id="counterfactual-allele-frontier", model_version="2026.08", ambiguity_tolerance=0.2)
    issues: list[str] = []
    if result.state is CausalBetaState.PARTIAL:
        issues.append("missing_alternate_allele")
    if result.state is CausalBetaState.AMBIGUOUS:
        issues.append("replicate_ambiguity")
    if result.state is CausalBetaState.OUT_OF_DOMAIN:
        issues.append("context_mismatch")
    evidence_ids = result.reference_observation_ids + result.alternate_observation_ids
    return _result(record, result.state, tuple(issues), support=None, uncertainty=1.0 if result.state is not CausalBetaState.SUPPORTED else 0.2, sensitivity=result.sensitivity, delta=result.delta_alternate_minus_reference, evidence_ids=evidence_ids, source_ids=result.source_ids, primitive_address=result.content_address)


def execute_causal_beta_frontier_record(record: CausalBetaFrontierRecord) -> CausalBetaFrontierAdapterResult:
    if record.operation is CausalBetaFrontierOperation.SEQUENCE_TO_ELEMENT:
        return _mediator(record, SequenceToElementCausalMediator(), MediatorKind.SEQUENCE_TO_ELEMENT)
    if record.operation is CausalBetaFrontierOperation.ELEMENT_TO_GENE:
        return _mediator(record, ElementToGeneCausalMediator(), MediatorKind.ELEMENT_TO_GENE)
    if record.operation is CausalBetaFrontierOperation.GENE_TO_STATE:
        return _mediator(record, GeneToStateCausalMediator(), MediatorKind.GENE_TO_STATE)
    if record.operation is CausalBetaFrontierOperation.COUNTERFACTUAL_ALLELE_STATE:
        return _counterfactual(record)
    raise ValidationError(f"unsupported causal beta operation: {record.operation}")


def build_causal_beta_frontier_adapters() -> CausalBetaFrontierAdapterRegistry:
    states = tuple(item.value for item in CausalBetaState)
    specs = (
        CausalBetaFrontierAdapterSpec(CausalBetaFrontierOperation.SEQUENCE_TO_ELEMENT, "causal-beta-sequence-element", "SequenceToElementCausalMediator", ("source_node", "target_node", "context_key", "evidence"), ("state", "support", "uncertainty", "sensitivity", "evidence_ids"), states, "independent paths are not causal identification"),
        CausalBetaFrontierAdapterSpec(CausalBetaFrontierOperation.ELEMENT_TO_GENE, "causal-beta-element-gene", "ElementToGeneCausalMediator", ("source_node", "target_node", "context_key", "evidence"), ("state", "support", "uncertainty", "evidence_ids"), states, "edge support is not a calibrated gene effect"),
        CausalBetaFrontierAdapterSpec(CausalBetaFrontierOperation.GENE_TO_STATE, "causal-beta-gene-state", "GeneToStateCausalMediator", ("source_node", "target_node", "context_key", "evidence"), ("state", "support", "uncertainty", "negative_evidence_ids"), states, "state association is not a perturbation result"),
        CausalBetaFrontierAdapterSpec(CausalBetaFrontierOperation.COUNTERFACTUAL_ALLELE_STATE, "causal-beta-allele-state", "CounterfactualAlleleStateSimulator", ("state_id", "context_key", "observations"), ("state", "reference_value", "alternate_value", "delta_alternate_minus_reference", "sensitivity"), states, "allele delta is descriptive and not proof of causality"),
    )
    return CausalBetaFrontierAdapterRegistry(specs, len(specs) == 4 and {item.operation for item in specs} == set(CausalBetaFrontierOperation))


__all__ = ["CausalBetaFrontierAdapterRegistry", "CausalBetaFrontierAdapterResult", "CausalBetaFrontierAdapterSpec", "build_causal_beta_frontier_adapters", "execute_causal_beta_frontier_record"]
