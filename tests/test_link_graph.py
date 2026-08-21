from __future__ import annotations

import unittest

from glio_noncode.link_graph import (
    CcreElementAssigner,
    CoordinateOverlapLinker,
    EnhancerGeneConsensusLinker,
    GeneFeatureParser,
    LinkEvidence,
    LinkState,
    LinkType,
    NearestGeneBaseline,
)
from glio_noncode.models import CandidateElement, ReferenceContext, VariantIdentity, VariantKind


class LinkGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = ReferenceContext(
            "GRCh38", "glioma", "adult", "stem_like", territory="core"
        )
        self.other_context = ReferenceContext(
            "GRCh38", "glioma", "adult", "differentiated", territory="core"
        )
        self.variant = VariantIdentity(
            "v1", VariantKind.SNV, "chr7", 100, 100, "A", "T", "GRCh38"
        )

    def _element(
        self,
        element_id: str,
        *,
        context: ReferenceContext | None = None,
        start: int = 90,
        end: int = 120,
        target_genes: tuple[str, ...] = ("GENE1",),
        element_type: str = "ccre",
    ) -> CandidateElement:
        return CandidateElement(
            element_id,
            "chr7",
            start,
            end,
            element_type,
            context or self.context,
            "ccre-atlas",
            target_genes=target_genes,
        )

    def test_coordinate_overlap_linker_is_context_gated(self) -> None:
        graph = CoordinateOverlapLinker().link(
            self.variant,
            (self._element("enh-1"), self._element("enh-other", context=self.other_context)),
            self.context,
        )
        self.assertEqual(graph.state, LinkState.SUPPORTED)
        self.assertEqual(graph.links[0].element_id, "enh-1")
        self.assertEqual(graph.links[0].distance_bp, 0)
        self.assertEqual(graph.links[0].gene_id, "GENE1")

        out_of_domain = CoordinateOverlapLinker().link(
            self.variant, (self._element("enh-other", context=self.other_context),), self.context
        )
        self.assertEqual(out_of_domain.state, LinkState.OUT_OF_DOMAIN)
        self.assertFalse(out_of_domain.links)

    def test_gene_parser_and_nearest_baseline_keep_ties_visible(self) -> None:
        text = (
            "gene_id\tsymbol\tchromosome\tstart\tend\tcontext\tbuild\n"
            f"g1\tGENE1\t7\t199\t300\t{self.context.key}\tGRCh38\n"
            f"g2\tGENE2\t7\t199\t300\t{self.context.key}\tGRCh38\n"
            "bad\tGENE3\t7\tbad\t400\tunknown\tGRCh38\n"
        )
        batch = GeneFeatureParser().parse_text(text, source_id="genes")
        self.assertEqual(len(batch.genes), 2)
        self.assertEqual(batch.genes[0].start, 200)
        self.assertEqual(len(batch.issues), 1)
        graph = NearestGeneBaseline().link(self.variant, batch.genes, self.context)
        self.assertEqual(graph.state, LinkState.AMBIGUOUS)
        self.assertEqual({link.gene_id for link in graph.links}, {"g1", "g2"})
        self.assertEqual(graph.links[0].distance_bp, 100)

    def test_nearest_gene_abstains_outside_declared_window(self) -> None:
        text = (
            "gene_id\tsymbol\tchromosome\tstart\tend\tcontext\n"
            f"g1\tGENE1\t7\t999\t1100\t{self.context.key}\n"
        )
        genes = GeneFeatureParser().parse_text(text, source_id="genes").genes
        graph = NearestGeneBaseline(max_distance_bp=50).link(
            self.variant, genes, self.context
        )
        self.assertEqual(graph.state, LinkState.ABSTAINED)
        self.assertEqual(graph.variant_ids, ("v1",))

    def test_ccre_assigner_exposes_multiple_element_candidates(self) -> None:
        assignment = CcreElementAssigner().assign(
            self.variant,
            (self._element("enh-1"), self._element("enh-2", start=95, end=130)),
            self.context,
        )
        self.assertEqual(assignment.state, LinkState.AMBIGUOUS)
        self.assertEqual(assignment.element_ids, ("enh-1", "enh-2"))
        self.assertEqual(assignment.source_ids, ("ccre-atlas",))

    def test_consensus_requires_multiple_methods_for_supported_status(self) -> None:
        evidence = (
            LinkEvidence(
                "e1", "v1", "enh-1", "GENE1", LinkType.CONTACT, self.context.key,
                "hic", "v1", "h1", 0.8, 0.9,
            ),
            LinkEvidence(
                "e2", "v1", "enh-1", "GENE1", LinkType.COACCESSIBILITY, self.context.key,
                "sc-atlas", "v2", "h2", 0.6, 0.8,
            ),
        )
        graph = EnhancerGeneConsensusLinker().link(evidence, self.context, variant_id="v1")
        self.assertEqual(graph.state, LinkState.SUPPORTED)
        self.assertEqual(graph.links[0].link_type, LinkType.CONSENSUS)
        self.assertAlmostEqual(graph.links[0].support, 0.705882353)
        self.assertIn("methods=coaccessibility,contact", graph.links[0].reason)

    def test_single_method_consensus_is_partial_and_alternatives_are_retained(self) -> None:
        evidence = (
            LinkEvidence(
                "e1", "v1", "enh-1", "GENE1", LinkType.CONTACT, self.context.key,
                "hic", "v1", "h1", 0.8, 1.0,
            ),
            LinkEvidence(
                "e2", "v1", "enh-1", "GENE2", LinkType.CONTACT, self.context.key,
                "hic", "v1", "h2", 0.5, 1.0,
            ),
        )
        graph = EnhancerGeneConsensusLinker().link(evidence, self.context, variant_id="v1")
        self.assertEqual(graph.state, LinkState.PARTIAL)
        self.assertEqual(graph.links[0].alternatives, ("GENE2",))
        self.assertEqual(graph.links[1].alternatives, ("GENE1",))

    def test_consensus_does_not_transport_other_context_evidence(self) -> None:
        evidence = (
            LinkEvidence(
                "e1", "v1", "enh-1", "GENE1", LinkType.CONTACT, self.other_context.key,
                "hic", "v1", "h1", 0.8, 1.0,
            ),
        )
        graph = EnhancerGeneConsensusLinker().link(evidence, self.context, variant_id="v1")
        self.assertEqual(graph.state, LinkState.OUT_OF_DOMAIN)
        self.assertEqual(graph.links, ())

    def test_contradictory_consensus_is_not_averaged_away(self) -> None:
        evidence = (
            LinkEvidence(
                "e1", "v1", "enh-1", "GENE1", LinkType.CONTACT, self.context.key,
                "hic", "v1", "h1", 0.8, 1.0,
            ),
            LinkEvidence(
                "e2", "v1", "enh-1", "GENE1", LinkType.PERTURBATION, self.context.key,
                "crispr", "v1", "h2", 0.0, 0.8, LinkState.CONTRADICTORY,
            ),
        )
        graph = EnhancerGeneConsensusLinker().link(evidence, self.context, variant_id="v1")
        self.assertEqual(graph.state, LinkState.CONTRADICTORY)
        self.assertIsNone(graph.links[0].support)
        self.assertEqual(graph.links[0].uncertainty, 1.0)


if __name__ == "__main__":
    unittest.main()
