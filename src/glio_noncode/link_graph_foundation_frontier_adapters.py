"""Adapters binding C01-C04 fixture rows to the existing link primitives."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph import CcreElementAssigner, GeneFeature, LinkEvidence, LinkState, LinkType, NearestGeneBaseline, CoordinateOverlapLinker, EnhancerGeneConsensusLinker
from .models import CandidateElement, ReferenceContext, VariantIdentity
from .serialization import content_hash, jsonable
from .link_graph_foundation_frontier_public_data import LINK_GRAPH_FOUNDATION_FRONTIER_CONTEXT_KEY, LinkGraphFoundationFrontierOperation, LinkGraphFoundationFrontierRecord


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierAdapterSpec:
    operation: LinkGraphFoundationFrontierOperation
    adapter_id: str
    primitive: str
    input_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    states: tuple[str, ...]
    limitation: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierAdapterResult:
    record_id: str
    operation: LinkGraphFoundationFrontierOperation
    state: str
    issue_codes: tuple[str, ...]
    measurements: dict[str, Any]
    source_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierAdapterRegistry:
    specs: tuple[LinkGraphFoundationFrontierAdapterSpec, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: LinkGraphFoundationFrontierOperation | str) -> LinkGraphFoundationFrontierAdapterSpec:
        value = LinkGraphFoundationFrontierOperation(str(operation))
        for spec in self.specs:
            if spec.operation is value:
                return spec
        raise KeyError(value)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"specs": [item.to_dict() for item in self.specs], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def _context(value: str) -> ReferenceContext:
    genome, disease, age, cell, territory, treatment = value.split("|")
    return ReferenceContext(genome, disease, age, cell, territory=territory, treatment_phase=treatment)


def _variant(value: dict[str, Any]) -> VariantIdentity:
    return VariantIdentity.from_dict(value)


def _element(value: dict[str, Any], context: ReferenceContext) -> CandidateElement:
    selected = _context(str(value.get("context_key", context.key)))
    return CandidateElement.from_dict(value, selected)


def _gene(value: dict[str, Any]) -> GeneFeature:
    return GeneFeature(gene_id=str(value["gene_id"]), symbol=str(value.get("symbol", value["gene_id"])), chromosome=str(value["chromosome"]), start=int(value["start"]), end=int(value["end"]), genome_build=str(value["genome_build"]), context_key=str(value["context_key"]), source_id="gene-aggregate", source_version=str(value.get("source_version", "unspecified")), raw_hash=str(value.get("raw_hash", content_hash(value))))


def _evidence(value: dict[str, Any]) -> LinkEvidence:
    return LinkEvidence(evidence_id=str(value["evidence_id"]), variant_id=str(value["variant_id"]), element_id=str(value["element_id"]), gene_id=str(value["gene_id"]), link_type=LinkType(str(value.get("link_type", LinkType.CONTACT.value))), context_key=str(value["context_key"]), source_id=str(value["source_id"]), source_version=str(value.get("source_version", "unspecified")), raw_hash=content_hash(value), support=float(value.get("support", 0.0)), confidence=float(value.get("confidence", 1.0)), state=LinkState(str(value.get("state", LinkState.SUPPORTED.value))))


def _result(record: LinkGraphFoundationFrontierRecord, state: str, *, issues: tuple[str, ...] = (), measurements: dict[str, Any] | None = None, sources: tuple[str, ...] = (), evidence: tuple[str, ...] = ()) -> LinkGraphFoundationFrontierAdapterResult:
    values = measurements or {}
    return LinkGraphFoundationFrontierAdapterResult(record.record_id, record.operation, state, tuple(dict.fromkeys(issues)), values, sources or record.source_ids, evidence, content_hash({"record_id": record.record_id, "operation": record.operation, "state": state, "issues": issues, "measurements": values, "sources": sources or record.source_ids, "evidence": evidence}))


def _coordinate(record: LinkGraphFoundationFrontierRecord) -> LinkGraphFoundationFrontierAdapterResult:
    payload = record.payload
    context = _context(LINK_GRAPH_FOUNDATION_FRONTIER_CONTEXT_KEY)
    report = CoordinateOverlapLinker().link(_variant(payload["variant"]), tuple(_element(item, context) for item in payload.get("elements", ())), context)
    state = LinkState.AMBIGUOUS if len(report.links) > 1 else report.state
    issues = ("context_mismatch",) if state is LinkState.OUT_OF_DOMAIN else ("multiple_overlaps",) if state is LinkState.AMBIGUOUS else ("no_overlap",) if state is LinkState.ABSENT else ()
    return _result(record, state.value, issues=issues, measurements={"link_count": len(report.links), "element_ids": sorted({item.element_id for item in report.links}), "alternative_genes": sorted({gene for item in report.links for gene in item.alternatives})}, sources=tuple(sorted({source for item in report.links for source in item.source_ids})), evidence=tuple(sorted({evidence for item in report.links for evidence in item.evidence_ids})))


def _nearest(record: LinkGraphFoundationFrontierRecord) -> LinkGraphFoundationFrontierAdapterResult:
    payload = record.payload
    context = _context(LINK_GRAPH_FOUNDATION_FRONTIER_CONTEXT_KEY)
    report = NearestGeneBaseline(max_distance_bp=payload.get("max_distance_bp")).link(_variant(payload["variant"]), tuple(_gene(item) for item in payload.get("genes", ())), context)
    issues = ["context_mismatch"] if record.context_key != context.key else []
    if report.state is LinkState.AMBIGUOUS:
        issues.append("distance_tie")
    if report.state is LinkState.ABSTAINED and not issues:
        issues.append("distance_window")
    return _result(record, report.state.value, issues=tuple(dict.fromkeys(issues)), measurements={"link_count": len(report.links), "distances_bp": [item.distance_bp for item in report.links], "gene_ids": sorted({item.gene_id for item in report.links if item.gene_id})}, sources=tuple(sorted({source for item in report.links for source in item.source_ids})), evidence=tuple(sorted({evidence for item in report.links for evidence in item.evidence_ids})))


def _ccre(record: LinkGraphFoundationFrontierRecord) -> LinkGraphFoundationFrontierAdapterResult:
    payload = record.payload
    context = _context(LINK_GRAPH_FOUNDATION_FRONTIER_CONTEXT_KEY)
    variant = _variant(payload["variant"])
    elements = tuple(_element(item, context) for item in payload.get("elements", ()))
    report = CcreElementAssigner().assign(variant, elements, context)
    issues = ("context_mismatch",) if report.state is LinkState.OUT_OF_DOMAIN else ("multiple_ccres",) if report.state is LinkState.AMBIGUOUS else ("no_ccre",) if report.state is LinkState.ABSENT else ()
    return _result(record, report.state.value, issues=issues, measurements={"element_count": len(report.element_ids), "element_ids": report.element_ids, "reason": report.reason}, sources=report.source_ids)


def _consensus(record: LinkGraphFoundationFrontierRecord) -> LinkGraphFoundationFrontierAdapterResult:
    payload = record.payload
    context = _context(LINK_GRAPH_FOUNDATION_FRONTIER_CONTEXT_KEY)
    evidence = tuple(_evidence(item) for item in payload.get("evidence", ()))
    report = EnhancerGeneConsensusLinker().link(evidence, context, variant_id=str(payload.get("variant_id", "v-1")))
    issues = ["context_mismatch"] if record.context_key != context.key and not report.links else []
    if report.state is LinkState.PARTIAL:
        issues.append("single_method")
    if report.state is LinkState.CONTRADICTORY:
        issues.append("contradictory_evidence")
    return _result(record, report.state.value, issues=tuple(dict.fromkeys(issues)), measurements={"link_count": len(report.links), "methods": sorted({item.link_type.value for item in report.links}), "gene_ids": sorted({item.gene_id for item in report.links if item.gene_id}), "alternative_genes": sorted({gene for item in report.links for gene in item.alternatives})}, sources=tuple(sorted({source for item in report.links for source in item.source_ids})), evidence=tuple(sorted({evidence_id for item in report.links for evidence_id in item.evidence_ids})))


def execute_link_graph_foundation_frontier_record(record: LinkGraphFoundationFrontierRecord) -> LinkGraphFoundationFrontierAdapterResult:
    if record.operation is LinkGraphFoundationFrontierOperation.COORDINATE_OVERLAP:
        return _coordinate(record)
    if record.operation is LinkGraphFoundationFrontierOperation.NEAREST_GENE:
        return _nearest(record)
    if record.operation is LinkGraphFoundationFrontierOperation.CCRE_ASSIGNMENT:
        return _ccre(record)
    if record.operation is LinkGraphFoundationFrontierOperation.CONSENSUS:
        return _consensus(record)
    raise ValueError(record.operation)


def build_link_graph_foundation_frontier_adapters() -> LinkGraphFoundationFrontierAdapterRegistry:
    states = tuple(item.value for item in LinkState)
    specs = (LinkGraphFoundationFrontierAdapterSpec(LinkGraphFoundationFrontierOperation.COORDINATE_OVERLAP, "d10-c01-coordinate", "CoordinateOverlapLinker", ("variant", "elements", "context_key"), ("link_count", "element_ids", "alternative_genes"), states, "Overlap is a candidate edge, not regulatory proof."), LinkGraphFoundationFrontierAdapterSpec(LinkGraphFoundationFrontierOperation.NEAREST_GENE, "d10-c02-nearest", "NearestGeneBaseline", ("variant", "genes", "max_distance_bp", "context_key"), ("link_count", "distances_bp", "gene_ids"), states, "Distance is a baseline and not a target claim."), LinkGraphFoundationFrontierAdapterSpec(LinkGraphFoundationFrontierOperation.CCRE_ASSIGNMENT, "d10-c03-ccre", "CcreElementAssigner", ("variant", "elements", "context_key"), ("element_count", "element_ids", "reason"), states, "cCRE assignment retains one-to-many ambiguity."), LinkGraphFoundationFrontierAdapterSpec(LinkGraphFoundationFrontierOperation.CONSENSUS, "d10-c04-consensus", "EnhancerGeneConsensusLinker", ("evidence", "variant_id", "context_key"), ("link_count", "methods", "gene_ids", "alternative_genes"), states, "Consensus is method aggregation, not mechanism proof."))
    return LinkGraphFoundationFrontierAdapterRegistry(specs, len(specs) == 4)


__all__ = ["LinkGraphFoundationFrontierAdapterRegistry", "LinkGraphFoundationFrontierAdapterResult", "LinkGraphFoundationFrontierAdapterSpec", "build_link_graph_foundation_frontier_adapters", "execute_link_graph_foundation_frontier_record"]
