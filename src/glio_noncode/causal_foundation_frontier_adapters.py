"""Typed execution adapters for Domain 11 C01-C04 primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .causal_reasoning import (
    CausalState,
    ContextConditionedPriorModel,
    ContextPriorProfile,
    FactorGraphConstructor,
    FactorObservation,
    MeasurementLikelihoodModel,
    MeasurementObservation,
    TypedHypothesisObjectBuilder,
)
from .causal_foundation_frontier_public_data import (
    CAUSAL_FOUNDATION_FRONTIER_CONTEXT_KEY,
    CausalFoundationFrontierOperation,
    CausalFoundationFrontierRecord,
)
from .errors import ValidationError
from .models import ReferenceContext
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierAdapterSpec:
    operation: CausalFoundationFrontierOperation
    adapter_id: str
    primitive: str
    input_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    states: tuple[str, ...]
    limitation: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierAdapterResult:
    record_id: str
    operation: CausalFoundationFrontierOperation
    state: CausalState
    issue_codes: tuple[str, ...]
    measurements: Mapping[str, Any]
    source_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    primitive_addresses: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierAdapterRegistry:
    specs: tuple[CausalFoundationFrontierAdapterSpec, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: CausalFoundationFrontierOperation | str) -> CausalFoundationFrontierAdapterSpec:
        value = CausalFoundationFrontierOperation(str(operation))
        return next(item for item in self.specs if item.operation is value)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"specs": [item.to_dict() for item in self.specs], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _context(value: str) -> ReferenceContext:
    genome, disease, age, cell, territory, treatment = value.split("|")
    return ReferenceContext(genome, disease, age, cell, territory=territory, treatment_phase=treatment)


def _factors(record: CausalFoundationFrontierRecord) -> tuple[FactorObservation, ...]:
    return tuple(
        FactorObservation.from_mapping(item, fallback_id=f"{record.record_id}-factor-{index}", context_key=record.context_key)
        for index, item in enumerate(record.payload.get("factors", ()), start=1)
    )


def _profile(record: CausalFoundationFrontierRecord) -> ContextPriorProfile | None:
    value = record.payload.get("profile")
    return None if not isinstance(value, Mapping) else ContextPriorProfile(**dict(value))


def _measurements(record: CausalFoundationFrontierRecord) -> tuple[MeasurementObservation, ...]:
    return tuple(MeasurementObservation(**dict(item)) for item in record.payload.get("measurements", ()))


def _result(
    record: CausalFoundationFrontierRecord,
    state: CausalState,
    issues: tuple[str, ...],
    *,
    measurements: Mapping[str, Any] | None = None,
    evidence_ids: tuple[str, ...] = (),
    primitive_addresses: tuple[str, ...] = (),
) -> CausalFoundationFrontierAdapterResult:
    body = {
        "record_id": record.record_id,
        "operation": record.operation,
        "state": state,
        "issues": issues,
        "measurements": dict(measurements or {}),
        "sources": record.source_ids,
        "evidence": evidence_ids,
        "primitive_addresses": primitive_addresses,
    }
    return CausalFoundationFrontierAdapterResult(record.record_id, record.operation, state, issues, dict(measurements or {}), record.source_ids, evidence_ids, primitive_addresses, content_hash(body))


def _foreign(record: CausalFoundationFrontierRecord) -> CausalFoundationFrontierAdapterResult:
    return _result(record, CausalState.OUT_OF_DOMAIN, ("context_mismatch",), measurements={"context_key": record.context_key})


def _hypothesis(record: CausalFoundationFrontierRecord) -> CausalFoundationFrontierAdapterResult:
    if record.context_key != CAUSAL_FOUNDATION_FRONTIER_CONTEXT_KEY:
        return _foreign(record)
    context = _context(record.context_key)
    factors = _factors(record)
    graph = FactorGraphConstructor().construct(factors, context_key=context.key, graph_id=f"graph-{record.record_id}")
    profile = _profile(record)
    prior = None
    if profile is not None:
        prior = ContextConditionedPriorModel().estimate(context, record.payload.get("features", {}), profile)
    measurements = _measurements(record)
    edge_id = factors[0].edge_id if factors else str(record.payload.get("edge_id", f"edge-{record.record_id}"))
    likelihood = MeasurementLikelihoodModel().estimate(context, measurements, edge_id=edge_id)
    hypothesis = TypedHypothesisObjectBuilder().build(
        hypothesis_id=str(record.payload.get("hypothesis_id", record.record_id)),
        variant_id=str(record.payload.get("variant_id", "v-1")),
        element_id=str(record.payload.get("element_id", "enh-1")),
        gene_id=str(record.payload.get("gene_id", "GENE1")),
        state_id=str(record.payload.get("state_id", "stem_like")),
        mechanism=str(record.payload.get("mechanism", "regulatory_link")),
        context=context,
        factor_graph=graph,
        prior=prior,
        likelihood=likelihood,
    )
    issues: list[str] = []
    if prior is not None and prior.missing_features:
        issues.append("missing_prior_feature")
    if prior is not None and prior.out_of_range_features:
        issues.append("prior_feature_out_of_range")
    if graph.contradictory_edge_ids:
        issues.append("contradictory_factor_edge")
    evidence = tuple(sorted(factor.factor_id for factor in factors))
    addresses = tuple(item for item in (graph.content_address, prior.content_address if prior else "", likelihood.content_address) if item)
    return _result(record, hypothesis.state, tuple(issues), measurements={"support_proxy": hypothesis.support_proxy, "uncertainty": hypothesis.uncertainty, "factor_count": len(factors), "likelihood_state": likelihood.state.value}, evidence_ids=evidence, primitive_addresses=addresses)


def _factor_graph(record: CausalFoundationFrontierRecord) -> CausalFoundationFrontierAdapterResult:
    if record.context_key != CAUSAL_FOUNDATION_FRONTIER_CONTEXT_KEY:
        return _foreign(record)
    graph = FactorGraphConstructor().construct(_factors(record), context_key=record.context_key, graph_id=f"graph-{record.record_id}")
    issues: list[str] = []
    if graph.orphan_factor_ids:
        issues.append("orphan_factor_lineage")
    if graph.contradictory_edge_ids:
        issues.append("contradictory_factor_edge")
    return _result(record, graph.state, tuple(issues), measurements={"factor_count": len(graph.factors), "active_factor_count": len(graph.active_factor_ids), "orphan_count": len(graph.orphan_factor_ids), "contradictory_edge_count": len(graph.contradictory_edge_ids)}, evidence_ids=tuple(item.factor_id for item in graph.factors), primitive_addresses=(graph.content_address,))


def _prior(record: CausalFoundationFrontierRecord) -> CausalFoundationFrontierAdapterResult:
    if record.context_key != CAUSAL_FOUNDATION_FRONTIER_CONTEXT_KEY:
        return _foreign(record)
    profile = _profile(record)
    if profile is None:
        raise ValidationError("context prior record requires profile")
    estimate = ContextConditionedPriorModel().estimate(_context(record.context_key), record.payload.get("features", {}), profile)
    issues = []
    if estimate.missing_features:
        issues.append("missing_prior_feature")
    if estimate.out_of_range_features:
        issues.append("prior_feature_out_of_range")
    return _result(record, estimate.state, tuple(issues), measurements={"prior_score": estimate.prior_score, "uncertainty": estimate.uncertainty, "feature_count": len(estimate.feature_contributions)}, evidence_ids=tuple(estimate.feature_contributions), primitive_addresses=(estimate.content_address,))


def _likelihood(record: CausalFoundationFrontierRecord) -> CausalFoundationFrontierAdapterResult:
    if record.context_key != CAUSAL_FOUNDATION_FRONTIER_CONTEXT_KEY:
        return _foreign(record)
    edge_id = str(record.payload.get("edge_id", f"edge-{record.record_id}"))
    estimate = MeasurementLikelihoodModel().estimate(_context(record.context_key), _measurements(record), edge_id=edge_id)
    issues = []
    if estimate.state is CausalState.PARTIAL:
        issues.append("single_measurement_group")
    if estimate.state is CausalState.CONTRADICTORY:
        issues.append("contradictory_measurement")
    return _result(record, estimate.state, tuple(issues), measurements={"likelihood_proxy": estimate.likelihood_proxy, "uncertainty": estimate.uncertainty, "group_count": len(estimate.channel_groups), "missing_count": len(estimate.missing_measurement_ids)}, evidence_ids=estimate.measurement_ids, primitive_addresses=(estimate.content_address,))


def execute_causal_foundation_frontier_record(record: CausalFoundationFrontierRecord) -> CausalFoundationFrontierAdapterResult:
    if record.operation is CausalFoundationFrontierOperation.HYPOTHESIS_OBJECT:
        return _hypothesis(record)
    if record.operation is CausalFoundationFrontierOperation.FACTOR_GRAPH:
        return _factor_graph(record)
    if record.operation is CausalFoundationFrontierOperation.CONTEXT_PRIOR:
        return _prior(record)
    if record.operation is CausalFoundationFrontierOperation.MEASUREMENT_LIKELIHOOD:
        return _likelihood(record)
    raise ValidationError(f"unsupported causal foundation operation: {record.operation}")


def build_causal_foundation_frontier_adapters() -> CausalFoundationFrontierAdapterRegistry:
    states = tuple(item.value for item in CausalState)
    specs = (
        CausalFoundationFrontierAdapterSpec(CausalFoundationFrontierOperation.HYPOTHESIS_OBJECT, "causal-foundation-hypothesis", "TypedHypothesisObjectBuilder", ("hypothesis_id", "factors", "profile", "features", "measurements"), ("state", "support_proxy", "uncertainty", "factor_ids"), states, "support_proxy is not a calibrated posterior"),
        CausalFoundationFrontierAdapterSpec(CausalFoundationFrontierOperation.FACTOR_GRAPH, "causal-foundation-factor-graph", "FactorGraphConstructor", ("factors", "context_key"), ("active_factor_ids", "orphan_factor_ids", "contradictory_edge_ids", "state"), states, "superseded factors remain in history"),
        CausalFoundationFrontierAdapterSpec(CausalFoundationFrontierOperation.CONTEXT_PRIOR, "causal-foundation-context-prior", "ContextConditionedPriorModel", ("profile", "features", "context_key"), ("prior_score", "feature_contributions", "missing_features", "out_of_range_features"), states, "prior_score is a bounded proxy"),
        CausalFoundationFrontierAdapterSpec(CausalFoundationFrontierOperation.MEASUREMENT_LIKELIHOOD, "causal-foundation-likelihood", "MeasurementLikelihoodModel", ("edge_id", "measurements", "context_key"), ("likelihood_proxy", "channel_groups", "measurement_ids", "missing_measurement_ids"), states, "likelihood_proxy is not calibrated probability"),
    )
    return CausalFoundationFrontierAdapterRegistry(specs, len(specs) == len(tuple(CausalFoundationFrontierOperation)) and {item.operation for item in specs} == set(CausalFoundationFrontierOperation))


__all__ = [
    "CausalFoundationFrontierAdapterRegistry",
    "CausalFoundationFrontierAdapterResult",
    "CausalFoundationFrontierAdapterSpec",
    "build_causal_foundation_frontier_adapters",
    "execute_causal_foundation_frontier_record",
]
