"""Construction of decomposed variant-element-gene-state hypotheses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .evidence import EvidenceGraph
from .models import (
    CaseManifest,
    CandidateElement,
    EdgeType,
    EvidenceClaim,
    EvidenceState,
    EvidenceTier,
    Hypothesis,
    HypothesisEdge,
    ResearchStatus,
    SupportLevel,
)
from .scoring import (
    clamp,
    derived_path_score,
    element_relevance,
    feature_readings,
    context_for_element,
    make_claim,
    reading_from_feature,
)
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class BuiltHypotheses:
    """Builder output keeps evidence and hypotheses together for replay."""

    hypotheses: tuple[Hypothesis, ...]
    claims: tuple[EvidenceClaim, ...]
    warnings: tuple[str, ...]


class HypothesisBuilder:
    """Build a small, inspectable candidate graph from manifest data."""

    max_element_distance = 1_000_000

    def build(self, manifest: CaseManifest, run_id: str) -> BuiltHypotheses:
        graph = EvidenceGraph()
        hypotheses: list[Hypothesis] = []
        warnings: list[str] = []
        if not manifest.candidate_elements:
            warnings.append("No candidate regulatory elements were supplied; output will abstain.")
        for variant in manifest.variants:
            elements = self._eligible_elements(variant, manifest.candidate_elements)
            if not elements:
                warnings.append(f"No eligible elements for {variant.variant_id}.")
            for element in elements:
                built = self._build_one(manifest, variant, element, run_id, graph)
                hypotheses.append(built)
        if not hypotheses and manifest.variants:
            hypotheses.extend(self._abstentions(manifest, run_id, graph))
        return BuiltHypotheses(
            hypotheses=tuple(sorted(hypotheses, key=lambda item: (-item.support, item.hypothesis_id))),
            claims=graph.all_claims(),
            warnings=tuple(dict.fromkeys(warnings)),
        )

    def _eligible_elements(
        self,
        variant,
        elements: Iterable[CandidateElement],
    ) -> tuple[CandidateElement, ...]:
        eligible: list[CandidateElement] = []
        for element in elements:
            distance, _ = element_relevance(variant, element)
            same_chromosome = variant.chromosome == element.chromosome
            raw_distance = abs(variant.start - element.end) if same_chromosome else self.max_element_distance + 1
            if same_chromosome and (raw_distance <= self.max_element_distance or distance >= 0.25):
                eligible.append(element)
        return tuple(eligible)

    def _build_one(self, manifest: CaseManifest, variant, element, run_id: str, graph: EvidenceGraph) -> Hypothesis:
        variant_element_id = self._edge_id(variant.variant_id, element.element_id, EdgeType.VARIANT_TO_ELEMENT)
        element_context = context_for_element(manifest.context, element)
        relevance, relevance_note = element_relevance(variant, element)
        claims: list[EvidenceClaim] = []
        for reading in feature_readings(element):
            claims.append(
                make_claim(
                    edge_id=variant_element_id,
                    reading=reading,
                    context=manifest.context,
                    context_match=element_context,
                    summary=f"{reading.channel} for {element.element_id}; {reading.rationale}",
                    payload={"element_id": element.element_id, "relevance_prior": relevance, "note": relevance_note},
                )
            )
        graph.extend(claims)
        variant_edge_aggregate = graph.aggregate(
            HypothesisEdge(
                edge_id=variant_element_id,
                edge_type=EdgeType.VARIANT_TO_ELEMENT,
                source_id=variant.variant_id,
                target_id=element.element_id,
                support=0.0,
                uncertainty=1.0,
                context_fit=element_context.score,
                claim_ids=tuple(claim.evidence_id for claim in claims),
                support_level=SupportLevel.UNKNOWN,
            )
        )
        element_gene_edges: list[HypothesisEdge] = []
        for gene_id in element.target_genes or ("unresolved_gene",):
            edge_id = self._edge_id(element.element_id, gene_id, EdgeType.ELEMENT_TO_GENE)
            link_reading = reading_from_feature(
                "element_gene_link",
                element.features.get("contact_strength", element.features.get("coaccessibility")),
                source_id=f"{element.source_id}:link",
                confidence=float(element.annotations.get("link_confidence", 0.62)),
            )
            link_claim = make_claim(
                edge_id=edge_id,
                reading=link_reading,
                context=manifest.context,
                context_match=element_context,
                summary=f"Candidate link {element.element_id} to {gene_id}; nearest-gene is not assumed.",
                payload={"element_id": element.element_id, "gene_id": gene_id, "link_method": element.annotations.get("link_method", "adapter_input")},
            )
            graph.append(link_claim)
            aggregate = graph.aggregate(
                HypothesisEdge(
                    edge_id=edge_id,
                    edge_type=EdgeType.ELEMENT_TO_GENE,
                    source_id=element.element_id,
                    target_id=gene_id,
                    support=0.0,
                    uncertainty=1.0,
                    context_fit=element_context.score,
                    claim_ids=(link_claim.evidence_id,),
                    support_level=SupportLevel.UNKNOWN,
                )
            )
            element_gene_edges.append(
                self._edge(
                    edge_id=edge_id,
                    edge_type=EdgeType.ELEMENT_TO_GENE,
                    source_id=element.element_id,
                    target_id=gene_id,
                    aggregate=aggregate,
                )
            )
        state_edges: list[HypothesisEdge] = []
        for state_id in element.state_ids or ("unresolved_state",):
            edge_id = self._edge_id(element.target_genes[0] if element.target_genes else element.element_id, state_id, EdgeType.GENE_TO_STATE)
            state_reading = reading_from_feature(
                "state_prior",
                element.features.get("state_prior"),
                source_id=f"{element.source_id}:state",
                confidence=float(element.annotations.get("state_confidence", 0.58)),
            )
            state_claim = make_claim(
                edge_id=edge_id,
                reading=state_reading,
                context=manifest.context,
                context_match=element_context,
                summary=f"State context for {state_id} is supplied by {element.source_id}.",
                payload={"state_id": state_id, "state_definition": element.annotations.get("state_definition", "unspecified")},
            )
            graph.append(state_claim)
            aggregate = graph.aggregate(
                HypothesisEdge(
                    edge_id=edge_id,
                    edge_type=EdgeType.GENE_TO_STATE,
                    source_id=element.target_genes[0] if element.target_genes else element.element_id,
                    target_id=state_id,
                    support=0.0,
                    uncertainty=1.0,
                    context_fit=element_context.score,
                    claim_ids=(state_claim.evidence_id,),
                    support_level=SupportLevel.UNKNOWN,
                )
            )
            state_edges.append(
                self._edge(
                    edge_id=edge_id,
                    edge_type=EdgeType.GENE_TO_STATE,
                    source_id=element.target_genes[0] if element.target_genes else element.element_id,
                    target_id=state_id,
                    aggregate=aggregate,
                )
            )
        gene_edge = element_gene_edges[0]
        state_edge = state_edges[0]
        causal_edge_id = self._edge_id(variant.variant_id, f"{element.element_id}:{gene_edge.target_id}:{state_edge.target_id}", EdgeType.CAUSAL_PATH)
        path_claim = self._path_claim(
            causal_edge_id,
            manifest,
            element,
            element_context,
            variant_element_id,
            gene_edge,
            state_edge,
            variant_edge_aggregate,
            graph,
            run_id,
        )
        graph.append(path_claim)
        path_aggregate = graph.aggregate(
            HypothesisEdge(
                edge_id=causal_edge_id,
                edge_type=EdgeType.CAUSAL_PATH,
                source_id=variant.variant_id,
                target_id=state_edge.target_id,
                support=0.0,
                uncertainty=1.0,
                context_fit=element_context.score,
                claim_ids=(path_claim.evidence_id,),
                support_level=SupportLevel.UNKNOWN,
            )
        )
        edges = (
            self._edge(
                edge_id=variant_element_id,
                edge_type=EdgeType.VARIANT_TO_ELEMENT,
                source_id=variant.variant_id,
                target_id=element.element_id,
                aggregate=variant_edge_aggregate,
            ),
            *element_gene_edges,
            *state_edges,
            self._edge(
                edge_id=causal_edge_id,
                edge_type=EdgeType.CAUSAL_PATH,
                source_id=variant.variant_id,
                target_id=state_edge.target_id,
                aggregate=path_aggregate,
            ),
        )
        missing = tuple(sorted({claim.evidence_id for claim in graph.all_claims() if claim.edge_id in {edge.edge_id for edge in edges} and claim.state in (EvidenceState.UNSUPPORTED, EvidenceState.ABSTAINED, EvidenceState.OUT_OF_DOMAIN)}))
        negative = tuple(sorted({claim.evidence_id for claim in graph.all_claims() if claim.edge_id in {edge.edge_id for edge in edges} and claim.state in (EvidenceState.MEASURED_NEGATIVE, EvidenceState.CONTRADICTORY)}))
        hypothesis_id = self._hypothesis_id(variant.variant_id, element.element_id, gene_edge.target_id, state_edge.target_id)
        return Hypothesis(
            hypothesis_id=hypothesis_id,
            variant_id=variant.variant_id,
            element_id=element.element_id,
            gene_id=gene_edge.target_id,
            state_id=state_edge.target_id,
            mechanism=str(element.annotations.get("mechanism", "context-conditioned regulatory modulation")),
            context=manifest.context,
            edges=edges,
            support=path_aggregate.score,
            uncertainty=clamp(max(path_aggregate.uncertainty, 1.0 - element_context.score)),
            status=ResearchStatus.REVIEW_REQUIRED,
            missing_evidence=missing,
            negative_evidence=negative,
            alternatives=tuple(element.annotations.get("alternative_explanations", ())),
            provenance=(manifest.content_address, run_id, element.source_id),
        )

    def _path_claim(self, edge_id, manifest, element, context_match, variant_edge_id, gene_edge, state_edge, variant_aggregate, graph, run_id):
        path_score = derived_path_score((variant_aggregate.score, gene_edge.support, state_edge.support))
        state = EvidenceState.SUPPORTED if path_score >= 0.3 else EvidenceState.ABSTAINED
        reading = reading_from_feature(
            "causal_path",
            path_score,
            source_id=f"runtime:{run_id}",
            confidence=clamp(1.0 - max(variant_aggregate.uncertainty, gene_edge.uncertainty, state_edge.uncertainty)),
        )
        if state == EvidenceState.ABSTAINED:
            reading = reading_from_feature("causal_path", None, source_id=f"runtime:{run_id}", confidence=0.18)
        return make_claim(
            edge_id=edge_id,
            reading=reading,
            context=manifest.context,
            context_match=context_match,
            summary=f"Decomposed path from {element.element_id} through {gene_edge.target_id} to {state_edge.target_id}.",
            payload={"path_score": path_score, "variant_element_edge": variant_edge_id, "edge_support": [gene_edge.support, state_edge.support]},
            depends_on=tuple(claim.evidence_id for claim in graph.for_edge(variant_edge_id)) + tuple(gene_edge.claim_ids) + tuple(state_edge.claim_ids),
        )

    @staticmethod
    def _edge(edge_id, edge_type, source_id, target_id, aggregate) -> HypothesisEdge:
        if aggregate.score >= 0.72:
            level = SupportLevel.HIGH
        elif aggregate.score >= 0.45:
            level = SupportLevel.MODERATE
        elif aggregate.score > 0:
            level = SupportLevel.LOW
        else:
            level = SupportLevel.UNKNOWN
        return HypothesisEdge(
            edge_id=edge_id,
            edge_type=edge_type,
            source_id=source_id,
            target_id=target_id,
            support=aggregate.score,
            uncertainty=aggregate.uncertainty,
            context_fit=aggregate.context_support,
            claim_ids=aggregate.supported_claim_ids + aggregate.negative_claim_ids + aggregate.missing_claim_ids,
            support_level=level,
            alternatives=(),
        )

    @staticmethod
    def _edge_id(source_id: str, target_id: str, edge_type: EdgeType) -> str:
        digest = content_hash({"source": source_id, "target": target_id, "type": edge_type.value}).split(":", 1)[1]
        return f"edge-{digest[:20]}"

    @staticmethod
    def _hypothesis_id(variant_id: str, element_id: str, gene_id: str, state_id: str) -> str:
        digest = content_hash({"variant": variant_id, "element": element_id, "gene": gene_id, "state": state_id}).split(":", 1)[1]
        return f"hyp-{digest[:20]}"

    def _abstentions(self, manifest: CaseManifest, run_id: str, graph: EvidenceGraph) -> list[Hypothesis]:
        output: list[Hypothesis] = []
        for variant in manifest.variants:
            edge_id = self._edge_id(variant.variant_id, "unresolved", EdgeType.CAUSAL_PATH)
            reading = reading_from_feature("causal_path", None, source_id=f"runtime:{run_id}", confidence=0.1)
            claim = make_claim(
                edge_id=edge_id,
                reading=reading,
                context=manifest.context,
                context_match=context_for_element(manifest.context, CandidateElement(
                    element_id="unresolved",
                    chromosome=variant.chromosome,
                    start=variant.start,
                    end=variant.end,
                    element_type="unresolved",
                    context=manifest.context,
                    source_id="runtime",
                    target_genes=("unresolved_gene",),
                )),
                summary="The run abstained because no eligible regulatory element was supplied.",
            )
            graph.append(claim)
            edge = HypothesisEdge(
                edge_id=edge_id,
                edge_type=EdgeType.CAUSAL_PATH,
                source_id=variant.variant_id,
                target_id="unresolved",
                support=0.0,
                uncertainty=1.0,
                context_fit=0.0,
                claim_ids=(claim.evidence_id,),
                support_level=SupportLevel.UNKNOWN,
            )
            output.append(
                Hypothesis(
                    hypothesis_id=self._hypothesis_id(variant.variant_id, "unresolved", "unresolved_gene", "unresolved_state"),
                    variant_id=variant.variant_id,
                    element_id="unresolved",
                    gene_id="unresolved_gene",
                    state_id="unresolved_state",
                    mechanism="abstained: insufficient candidate context",
                    context=manifest.context,
                    edges=(edge,),
                    support=0.0,
                    uncertainty=1.0,
                    status=ResearchStatus.DRAFT,
                    missing_evidence=(claim.evidence_id,),
                    provenance=(manifest.content_address, run_id),
                )
            )
        return output
