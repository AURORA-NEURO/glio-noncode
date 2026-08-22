"""Typed bindings from the C05-C08 fixture to beta link primitives."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .link_graph import LinkEvidence, LinkState, LinkType
from .link_graph_beta import ActivityByContactLinkAdapter, AlleleSpecificLinkEvidenceIntegrator, CoaccessibilityLinker, MolecularQtlLinker
from .link_graph_beta_frontier_public_data import LINK_GRAPH_BETA_FRONTIER_CONTEXT_KEY, LinkGraphBetaFrontierOperation, LinkGraphBetaFrontierRecord
from .models import ReferenceContext
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierAdapterSpec:
    operation: LinkGraphBetaFrontierOperation
    adapter_id: str
    primitive: str
    input_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    states: tuple[str, ...]
    limitation: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierAdapterResult:
    record_id: str
    operation: LinkGraphBetaFrontierOperation
    state: str
    issue_codes: tuple[str, ...]
    measurements: dict[str, Any]
    source_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierAdapterRegistry:
    specs: tuple[LinkGraphBetaFrontierAdapterSpec, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: LinkGraphBetaFrontierOperation | str) -> LinkGraphBetaFrontierAdapterSpec:
        value = LinkGraphBetaFrontierOperation(str(operation))
        return next(item for item in self.specs if item.operation is value)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"specs": [item.to_dict() for item in self.specs], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _context(value: str) -> ReferenceContext:
    genome, disease, age, cell, territory, treatment = value.split("|")
    return ReferenceContext(genome, disease, age, cell, territory=territory, treatment_phase=treatment)


def _result(record: LinkGraphBetaFrontierRecord, state: str, *, issues: tuple[str, ...] = (), measurements: dict[str, Any] | None = None, sources: tuple[str, ...] = (), evidence: tuple[str, ...] = ()) -> LinkGraphBetaFrontierAdapterResult:
    body = {"record_id": record.record_id, "operation": record.operation, "state": state, "issues": issues, "measurements": measurements or {}, "sources": sources, "evidence": evidence}
    return LinkGraphBetaFrontierAdapterResult(record.record_id, record.operation, state, issues, measurements or {}, sources, evidence, content_hash(body))


def _graph_result(record: LinkGraphBetaFrontierRecord, graph: Any, *, issues: tuple[str, ...] = (), measurements: dict[str, Any] | None = None) -> LinkGraphBetaFrontierAdapterResult:
    evidence = tuple(sorted({evidence_id for link in graph.links for evidence_id in link.evidence_ids}))
    sources = tuple(sorted({source_id for link in graph.links for source_id in link.source_ids}))
    return _result(record, graph.state.value, issues=issues, measurements=measurements or {"link_count": len(graph.links), "element_count": len(graph.element_ids), "gene_count": len(graph.gene_ids)}, sources=sources or record.source_ids, evidence=evidence)


def _activity(record: LinkGraphBetaFrontierRecord) -> LinkGraphBetaFrontierAdapterResult:
    observations = record.payload.get("observations", [])
    batch = ActivityByContactLinkAdapter().parse_text(json.dumps({"observations": observations}), source_id=record.source_ids[0], input_format="json")
    values = batch.observations
    if not values:
        return _result(record, LinkState.OUT_OF_DOMAIN.value if observations else LinkState.ABSTAINED.value, issues=("context_mismatch",) if observations else ("missing_evidence",), measurements={"observation_count": 0}, sources=record.source_ids)
    context = _context(LINK_GRAPH_BETA_FRONTIER_CONTEXT_KEY)
    evidence = tuple(LinkEvidence(item.evidence_id, item.variant_id, item.element_id, item.gene_id, LinkType.CONTACT, item.context_key, item.source_id, item.source_version, item.raw_hash, item.support, item.confidence) for item in values)
    from .link_graph import EnhancerGeneConsensusLinker
    graph = EnhancerGeneConsensusLinker().link(evidence, context, variant_id="v-1")
    issue = ("context_mismatch",) if graph.state is LinkState.OUT_OF_DOMAIN else (("replicate_pair",) if len(values) > 1 else ("single_method",))
    return _graph_result(record, graph, issues=issue, measurements={"observation_count": len(values), "support": round(values[0].support, 9) if values else 0.0})


def _coaccessibility(record: LinkGraphBetaFrontierRecord) -> LinkGraphBetaFrontierAdapterResult:
    observations = record.payload.get("observations", [])
    if not observations:
        return _result(record, LinkState.ABSTAINED.value, issues=("missing_evidence",), measurements={"observation_count": 0}, sources=record.source_ids)
    context = _context(LINK_GRAPH_BETA_FRONTIER_CONTEXT_KEY)
    graph = CoaccessibilityLinker().link(observations, context, variant_id="v-1")
    issue = ("context_mismatch",) if graph.state is LinkState.OUT_OF_DOMAIN else (("alternative_gene",) if len(graph.gene_ids) > 1 else ("single_method",))
    return _graph_result(record, graph, issues=issue, measurements={"observation_count": len(observations), "gene_count": len(graph.gene_ids)})


def _qtl(record: LinkGraphBetaFrontierRecord) -> LinkGraphBetaFrontierAdapterResult:
    observations = record.payload.get("observations", [])
    if not observations:
        return _result(record, LinkState.ABSTAINED.value, issues=("missing_evidence",), measurements={"observation_count": 0}, sources=record.source_ids)
    context = _context(LINK_GRAPH_BETA_FRONTIER_CONTEXT_KEY)
    graph = MolecularQtlLinker().link(observations, context, variant_id="v-1")
    issue = ("context_mismatch",) if graph.state is LinkState.OUT_OF_DOMAIN else (("weak_q_value",) if float(observations[0].get("q_value", 0.0)) >= 0.1 else ("single_method",))
    return _graph_result(record, graph, issues=issue, measurements={"observation_count": len(observations), "bounded_support": round(graph.links[0].support or 0.0, 9) if graph.links else 0.0})


def _allele(record: LinkGraphBetaFrontierRecord) -> LinkGraphBetaFrontierAdapterResult:
    observations = record.payload.get("observations", [])
    if not observations:
        return _result(record, LinkState.ABSTAINED.value, issues=("missing_evidence",), measurements={"observation_count": 0}, sources=record.source_ids)
    context = _context(LINK_GRAPH_BETA_FRONTIER_CONTEXT_KEY)
    graph = AlleleSpecificLinkEvidenceIntegrator().integrate(observations, context, variant_id="v-1")
    directions = {str(item.get("direction")) for item in observations}
    issue = ("context_mismatch",) if graph.state is LinkState.OUT_OF_DOMAIN else (("direction_conflict",) if {"gain", "loss"} <= directions else ("single_direction",))
    return _graph_result(record, graph, issues=issue, measurements={"observation_count": len(observations), "direction_count": len(directions)})


def execute_link_graph_beta_frontier_record(record: LinkGraphBetaFrontierRecord) -> LinkGraphBetaFrontierAdapterResult:
    return {LinkGraphBetaFrontierOperation.ACTIVITY_CONTACT: _activity, LinkGraphBetaFrontierOperation.COACCESSIBILITY: _coaccessibility, LinkGraphBetaFrontierOperation.MOLECULAR_QTL: _qtl, LinkGraphBetaFrontierOperation.ALLELE_SPECIFIC: _allele}[record.operation](record)


def build_link_graph_beta_frontier_adapters() -> LinkGraphBetaFrontierAdapterRegistry:
    states = tuple(item.value for item in LinkState)
    specs = (LinkGraphBetaFrontierAdapterSpec(LinkGraphBetaFrontierOperation.ACTIVITY_CONTACT, "activity-contact-frontier", "ActivityByContactLinkAdapter", ("observations", "activity_signal", "contact_signal", "context_key"), ("support", "link_count", "evidence_ids"), states, "activity and contact remain separate aggregate components"), LinkGraphBetaFrontierAdapterSpec(LinkGraphBetaFrontierOperation.COACCESSIBILITY, "coaccessibility-frontier", "CoaccessibilityLinker", ("observations", "score", "context_key"), ("gene_ids", "link_count", "evidence_ids"), states, "coaccessibility is one candidate evidence method"), LinkGraphBetaFrontierAdapterSpec(LinkGraphBetaFrontierOperation.MOLECULAR_QTL, "molecular-qtl-frontier", "MolecularQtlLinker", ("observations", "effect_size", "p_value", "q_value"), ("bounded_support", "effect_size", "evidence_ids"), states, "bounded support does not establish causality"), LinkGraphBetaFrontierAdapterSpec(LinkGraphBetaFrontierOperation.ALLELE_SPECIFIC, "allele-specific-frontier", "AlleleSpecificLinkEvidenceIntegrator", ("observations", "direction", "support", "context_key"), ("directions", "link_count", "evidence_ids"), states, "gain and loss directions remain visible when contradictory"))
    return LinkGraphBetaFrontierAdapterRegistry(specs, len(specs) == 4 and all(spec.input_fields and spec.output_fields and spec.limitation for spec in specs))


__all__ = ["LinkGraphBetaFrontierAdapterRegistry", "LinkGraphBetaFrontierAdapterResult", "LinkGraphBetaFrontierAdapterSpec", "build_link_graph_beta_frontier_adapters", "execute_link_graph_beta_frontier_record"]
