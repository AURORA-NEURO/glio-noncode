"""Typed execution adapters for Domain 10 C09-C12 link paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph import LinkState
from .link_graph_alpha import CRISPRPerturbationLinker, LinkGraphAlphaState, MultiGeneElementGraphBuilder, PromoterTetheringModel, ThreeDContactLinker
from .models import ReferenceContext
from .serialization import content_hash, jsonable
from .link_graph_alpha_frontier_public_data import LINK_GRAPH_ALPHA_FRONTIER_CONTEXT_KEY, LinkGraphAlphaFrontierOperation, LinkGraphAlphaFrontierRecord


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierAdapterSpec:
    operation: LinkGraphAlphaFrontierOperation
    adapter_id: str
    primitive: str
    input_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    state_rules: tuple[str, ...]
    limitation: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierAdapterResult:
    record_id: str
    operation: LinkGraphAlphaFrontierOperation
    state: str
    primitive_state: str
    issue_codes: tuple[str, ...]
    measurements: dict[str, Any]
    source_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierAdapterRegistry:
    specs: tuple[LinkGraphAlphaFrontierAdapterSpec, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: LinkGraphAlphaFrontierOperation | str) -> LinkGraphAlphaFrontierAdapterSpec:
        value = LinkGraphAlphaFrontierOperation(str(operation))
        for spec in self.specs:
            if spec.operation is value:
                return spec
        raise KeyError(value)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"specs": [item.to_dict() for item in self.specs], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _result(record: LinkGraphAlphaFrontierRecord, primitive_state: str, *, issue_codes: tuple[str, ...] = (), measurements: dict[str, Any] | None = None, evidence_ids: tuple[str, ...] = ()) -> LinkGraphAlphaFrontierAdapterResult:
    return LinkGraphAlphaFrontierAdapterResult(record.record_id, record.operation, primitive_state, primitive_state, issue_codes, measurements or {}, record.source_ids, evidence_ids, content_hash({"record_id": record.record_id, "operation": record.operation, "state": primitive_state, "issues": issue_codes, "measurements": measurements or {}, "evidence_ids": evidence_ids}))


def _context(value: str) -> ReferenceContext:
    genome, disease, age, cell_state, territory, treatment = value.split("|")
    return ReferenceContext(genome, disease, age, cell_state, territory=territory, treatment_phase=treatment)


def _crispr(record: LinkGraphAlphaFrontierRecord) -> LinkGraphAlphaFrontierAdapterResult:
    report = CRISPRPerturbationLinker().link(record.payload.get("observations", ()), _context(LINK_GRAPH_ALPHA_FRONTIER_CONTEXT_KEY), variant_id="v-1")
    issues: list[str] = []
    if report.state is LinkState.OUT_OF_DOMAIN:
        issues.append("context_mismatch")
    if report.state is LinkState.CONTRADICTORY:
        issues.append("direction_disagreement")
    if report.state is LinkState.PARTIAL:
        issues.append("single_method")
        if max((item.support or 0.0 for item in report.links), default=0.0) < 0.2:
            issues.append("low_support")
    return _result(record, report.state.value, issue_codes=tuple(dict.fromkeys(issues)), measurements={"link_count": len(report.links), "states": sorted({item.state.value for item in report.links}), "supports": [item.support for item in report.links], "alternative_genes": sorted({gene for item in report.links for gene in item.alternatives}), "source_ids": sorted({source for item in report.links for source in item.source_ids})}, evidence_ids=tuple(sorted({evidence for item in report.links for evidence in item.evidence_ids})))


def _contact(record: LinkGraphAlphaFrontierRecord) -> LinkGraphAlphaFrontierAdapterResult:
    report = ThreeDContactLinker().link(record.payload.get("observations", ()), _context(LINK_GRAPH_ALPHA_FRONTIER_CONTEXT_KEY), variant_id="v-1")
    observations = tuple(record.payload.get("observations", ()))
    issues: list[str] = []
    if report.state is LinkState.OUT_OF_DOMAIN:
        issues.append("context_mismatch")
    if report.state is LinkState.PARTIAL:
        issues.append("single_assay")
        if any((item.support or 0.0) < 0.3 for item in report.links):
            issues.append("weak_contact")
        if any(item.alternatives for item in report.links):
            issues.append("alternative_gene")
    return _result(record, report.state.value, issue_codes=tuple(dict.fromkeys(issues)), measurements={"link_count": len(report.links), "normalized_contacts": [item.support for item in report.links], "resolution_bp": sorted({item.get("resolution_bp") for item in observations if isinstance(item, dict)}), "assay_kinds": sorted({item.get("assay_kind") for item in observations if isinstance(item, dict)}), "alternative_genes": sorted({gene for item in report.links for gene in item.alternatives})}, evidence_ids=tuple(sorted({evidence for item in report.links for evidence in item.evidence_ids})))


def _tether(record: LinkGraphAlphaFrontierRecord) -> LinkGraphAlphaFrontierAdapterResult:
    report = PromoterTetheringModel().assess(record.payload.get("observations", ()), context_key=LINK_GRAPH_ALPHA_FRONTIER_CONTEXT_KEY)
    issues = [item.code for item in report.issues]
    if report.state is LinkGraphAlphaState.AMBIGUOUS:
        issues.append("tethering_ambiguity")
    if report.state is LinkGraphAlphaState.ABSTAINED:
        issues.append("missing_components")
    measurements = {"result_count": len(report.results), "scores": [item.tethering_score for item in report.results], "tiers": sorted({item.tier.value for item in report.results}), "available_components": [item.available_components for item in report.results], "alternative_genes": sorted({gene for item in report.results for gene in item.alternatives})}
    return _result(record, report.state.value, issue_codes=tuple(dict.fromkeys(issues)), measurements=measurements, evidence_ids=tuple(sorted({evidence for item in report.results for evidence in item.observation_ids})))


def _graph(record: LinkGraphAlphaFrontierRecord) -> LinkGraphAlphaFrontierAdapterResult:
    report = MultiGeneElementGraphBuilder().build(record.payload.get("evidence", ()), _context(LINK_GRAPH_ALPHA_FRONTIER_CONTEXT_KEY), graph_id=record.record_id, variant_id="v-1")
    issues = [item.code for item in report.issues]
    if report.state is LinkState.OUT_OF_DOMAIN:
        issues.append("context_mismatch")
    if report.state is LinkState.PARTIAL:
        issues.append("single_evidence")
    if report.state is LinkState.CONTRADICTORY:
        issues.append("contradictory_evidence")
    measurements = {"edge_count": len(report.edges), "gene_count": len(report.gene_ids), "element_count": len(report.element_ids), "variant_count": len(report.variant_ids), "component_count": len(report.connected_components), "degree_by_node": dict(report.degree_by_node), "edge_states": sorted({item.state.value for item in report.edges})}
    return _result(record, report.state.value, issue_codes=tuple(dict.fromkeys(issues)), measurements=measurements, evidence_ids=tuple(sorted({evidence for item in report.edges for evidence in item.evidence_ids})))


def execute_link_graph_alpha_frontier_record(record: LinkGraphAlphaFrontierRecord) -> LinkGraphAlphaFrontierAdapterResult:
    if record.operation is LinkGraphAlphaFrontierOperation.CRISPR_PERTURBATION:
        return _crispr(record)
    if record.operation is LinkGraphAlphaFrontierOperation.CONTACT_3D:
        return _contact(record)
    if record.operation is LinkGraphAlphaFrontierOperation.PROMOTER_TETHERING:
        return _tether(record)
    if record.operation is LinkGraphAlphaFrontierOperation.MULTI_GENE_GRAPH:
        return _graph(record)
    raise ValueError(f"unsupported link graph alpha frontier operation: {record.operation}")


def build_link_graph_alpha_frontier_adapters() -> LinkGraphAlphaFrontierAdapterRegistry:
    specs = (LinkGraphAlphaFrontierAdapterSpec(LinkGraphAlphaFrontierOperation.CRISPR_PERTURBATION, "d10-c09-crispr", "CRISPRPerturbationLinker", ("observations", "variant_id", "element_id", "gene_id", "direction", "context_key"), ("link_count", "supports", "states", "evidence_ids"), ("supported", "partial", "ambiguous", "contradictory", "out_of_domain"), "Perturbation paths remain candidate evidence, not mechanism proof."), LinkGraphAlphaFrontierAdapterSpec(LinkGraphAlphaFrontierOperation.CONTACT_3D, "d10-c10-contact", "ThreeDContactLinker", ("observations", "contact_signal", "contact_scale", "resolution_bp", "assay_kind", "context_key"), ("link_count", "normalized_contacts", "resolution_bp", "assay_kinds"), ("supported", "partial", "ambiguous", "out_of_domain"), "Contact is retained as an assay path and is not regulation proof."), LinkGraphAlphaFrontierAdapterSpec(LinkGraphAlphaFrontierOperation.PROMOTER_TETHERING, "d10-c11-tethering", "PromoterTetheringModel", ("observations", "distance_bp", "contact_support", "promoter_activity", "element_activity", "context_key"), ("scores", "tiers", "available_components", "alternative_genes"), ("supported", "partial", "ambiguous", "abstained", "out_of_domain"), "Tethering is a bounded baseline requiring external calibration."), LinkGraphAlphaFrontierAdapterSpec(LinkGraphAlphaFrontierOperation.MULTI_GENE_GRAPH, "d10-c12-graph", "MultiGeneElementGraphBuilder", ("evidence", "variant_id", "element_id", "gene_id", "link_type", "context_key"), ("edge_count", "gene_count", "component_count", "degree_by_node"), ("supported", "partial", "ambiguous", "contradictory", "out_of_domain"), "Graph edges retain alternatives and do not select a preferred target."))
    return LinkGraphAlphaFrontierAdapterRegistry(specs, len(specs) == 4)


__all__ = ["LinkGraphAlphaFrontierAdapterRegistry", "LinkGraphAlphaFrontierAdapterResult", "LinkGraphAlphaFrontierAdapterSpec", "build_link_graph_alpha_frontier_adapters", "execute_link_graph_alpha_frontier_record"]
