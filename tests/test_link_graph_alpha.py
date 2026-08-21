from __future__ import annotations

import unittest

from glio_noncode.link_graph import LinkEvidence, LinkState, LinkType
from glio_noncode.link_graph_alpha import (
    ContactAssayKind,
    CRISPRPerturbationLinkAdapter,
    CRISPRPerturbationLinker,
    LinkGraphAlphaState,
    MultiGeneElementGraphBuilder,
    PerturbationDirection,
    PromoterTetheringModel,
    TetheringTier,
    ThreeDContactLinkAdapter,
    ThreeDContactLinker,
)
from glio_noncode.models import ReferenceContext

CONTEXT = ReferenceContext("GRCh38", "glioma", "adult", "stem_like", territory="core")
OTHER_CONTEXT = ReferenceContext("GRCh38", "glioma", "adult", "differentiated", territory="core")


class LinkGraphAlphaTests(unittest.TestCase):
    def test_crispr_adapter_preserves_effect_direction_and_quarantines_bad_rows(self) -> None:
        text = (
            "evidence_id\tvariant_id\telement_id\tgene_id\tperturbation_mode\t"
            "direction\teffect_size\tcontext\tguide_id\n"
            f"cr-1\tv1\tenh-1\tGENE1\tCRISPRi\trepressing\t-0.5\t{CONTEXT.key}\tg-1\n"
            "cr-bad\tv1\tenh-1\tGENE1\tCRISPRi\trepressing\tbad\tunknown\tg-bad\n"
        )
        batch = CRISPRPerturbationLinkAdapter().parse_text(
            text,
            source_id="crispr-atlas",
            effect_scale=1.0,
        )
        self.assertEqual(len(batch.observations), 1)
        self.assertEqual(batch.observations[0].direction, PerturbationDirection.REPRESSING)
        self.assertAlmostEqual(batch.observations[0].bounded_support, 0.5)
        self.assertEqual(batch.observations[0].guide_id, "g-1")
        self.assertEqual(batch.issues[0].code, "invalid_crispr_perturbation_row")

    def test_crispr_linker_surfaces_opposing_direction_as_contradictory(self) -> None:
        common = {
            "variant_id": "v1",
            "element_id": "enh-1",
            "gene_id": "GENE1",
            "perturbation_mode": "CRISPRi",
            "effect_scale": 1.0,
            "context_key": CONTEXT.key,
            "source_id": "crispr",
            "source_version": "v1",
        }
        graph = CRISPRPerturbationLinker().link(
            [
                {**common, "evidence_id": "gain", "direction": "activating", "effect_size": 0.8},
                {**common, "evidence_id": "loss", "direction": "repressing", "effect_size": -0.7},
            ],
            CONTEXT,
            variant_id="v1",
        )
        self.assertEqual(graph.state, LinkState.CONTRADICTORY)
        self.assertIsNone(graph.links[0].support)
        self.assertEqual(set(graph.links[0].evidence_ids), {"gain", "loss"})

    def test_contact_adapter_and_linker_preserve_signal_scale_and_resolution(self) -> None:
        batch = ThreeDContactLinkAdapter().parse_text(
            "evidence_id\tvariant_id\telement_id\tgene_id\tcontact\tcontext\n"
            f"c-1\tv1\tenh-1\tGENE1\t4\t{CONTEXT.key}\n",
            source_id="hic",
            contact_scale=10.0,
            resolution_bp=5000,
            assay_kind=ContactAssayKind.HIC,
        )
        observation = batch.observations[0]
        self.assertAlmostEqual(observation.normalized_contact, 0.4)
        self.assertEqual(observation.resolution_bp, 5000)
        self.assertEqual(observation.assay_kind, ContactAssayKind.HIC)
        graph = ThreeDContactLinker().link((observation,), CONTEXT, variant_id="v1")
        self.assertEqual(graph.state, LinkState.PARTIAL)
        self.assertAlmostEqual(graph.links[0].support, 0.4)
        self.assertEqual(graph.links[0].evidence_ids, ("c-1",))

    def test_contact_linker_does_not_transport_other_context(self) -> None:
        graph = ThreeDContactLinker().link(
            [
                {
                    "evidence_id": "other",
                    "variant_id": "v1",
                    "element_id": "enh-1",
                    "gene_id": "GENE1",
                    "contact": 1.0,
                    "contact_scale": 1.0,
                    "context_key": OTHER_CONTEXT.key,
                }
            ],
            CONTEXT,
            variant_id="v1",
        )
        self.assertEqual(graph.state, LinkState.OUT_OF_DOMAIN)
        self.assertEqual(graph.links, ())

    def test_promoter_tethering_model_exposes_components_and_overlap_tier(self) -> None:
        report = PromoterTetheringModel().assess(
            [
                {
                    "observation_id": "t-1",
                    "variant_id": "v1",
                    "element_id": "enh-1",
                    "gene_id": "GENE1",
                    "distance_bp": 1000,
                    "contact_support": 0.8,
                    "promoter_activity": 0.9,
                    "element_activity": 0.7,
                    "promoter_overlap": True,
                    "context_key": CONTEXT.key,
                }
            ],
            context_key=CONTEXT.key,
            minimum_score=0.5,
        )
        result = report.results[0]
        self.assertEqual(report.state, LinkGraphAlphaState.SUPPORTED)
        self.assertEqual(result.tier, TetheringTier.PROMOTER_OVERLAP)
        self.assertEqual(
            result.available_components,
            ("distance_prior", "contact", "promoter", "element", "overlap"),
        )
        self.assertAlmostEqual(result.overlap_component, 1.0)
        self.assertGreater(result.tethering_score or 0.0, 0.5)

    def test_promoter_tethering_retains_tied_alternative_genes(self) -> None:
        rows = [
            {
                "observation_id": "t-1",
                "variant_id": "v1",
                "element_id": "enh-1",
                "gene_id": gene,
                "distance_bp": 1000,
                "contact_support": 0.8,
                "promoter_activity": 0.8,
                "context_key": CONTEXT.key,
            }
            for gene in ("GENE1", "GENE2")
        ]
        report = PromoterTetheringModel().assess(rows, context_key=CONTEXT.key)
        self.assertEqual(report.state, LinkGraphAlphaState.AMBIGUOUS)
        self.assertEqual(report.results[0].alternatives, ("GENE2",))
        self.assertEqual(report.results[1].alternatives, ("GENE1",))

    def test_promoter_tethering_abstains_when_components_are_missing(self) -> None:
        report = PromoterTetheringModel().assess(
            [
                {
                    "observation_id": "t-1",
                    "variant_id": "v1",
                    "element_id": "enh-1",
                    "gene_id": "GENE1",
                    "distance_bp": 1000,
                    "context_key": CONTEXT.key,
                }
            ],
            context_key=CONTEXT.key,
        )
        self.assertEqual(report.state, LinkGraphAlphaState.ABSTAINED)
        self.assertIsNone(report.results[0].tethering_score)

    def test_multi_gene_graph_builder_retains_alternatives_components_and_degrees(self) -> None:
        evidence: list[LinkEvidence] = []
        for gene in ("GENE1", "GENE2"):
            evidence.extend(
                [
                    LinkEvidence(
                        f"contact-{gene}",
                        "v1",
                        "enh-1",
                        gene,
                        LinkType.CONTACT,
                        CONTEXT.key,
                        "hic",
                        "v1",
                        f"raw-contact-{gene}",
                        0.8,
                        0.9,
                    ),
                    LinkEvidence(
                        f"coaccess-{gene}",
                        "v1",
                        "enh-1",
                        gene,
                        LinkType.COACCESSIBILITY,
                        CONTEXT.key,
                        "coaccess",
                        "v1",
                        f"raw-coaccess-{gene}",
                        0.7,
                        0.8,
                    ),
                ]
            )
        graph = MultiGeneElementGraphBuilder().build(
            evidence,
            CONTEXT,
            graph_id="g1",
            variant_id="v1",
        )
        self.assertEqual(graph.state, LinkState.SUPPORTED)
        self.assertEqual(graph.variant_ids, ("v1",))
        self.assertEqual(graph.element_ids, ("enh-1",))
        self.assertEqual(graph.gene_ids, ("GENE1", "GENE2"))
        self.assertEqual(len(graph.edges), 2)
        self.assertEqual(graph.edges[0].alternatives, ("GENE2",))
        self.assertEqual(len(graph.connected_components), 1)
        self.assertEqual(graph.degree_by_node["variant:v1"], 2)

    def test_multi_gene_graph_builder_context_mismatch_is_explicit(self) -> None:
        graph = MultiGeneElementGraphBuilder().build(
            [
                {
                    "evidence_id": "other",
                    "variant_id": "v1",
                    "element_id": "enh-1",
                    "gene_id": "GENE1",
                    "link_type": "contact",
                    "context_key": OTHER_CONTEXT.key,
                    "source_id": "hic",
                    "support": 0.8,
                    "confidence": 1.0,
                }
            ],
            CONTEXT,
        )
        self.assertEqual(graph.state, LinkState.OUT_OF_DOMAIN)
        self.assertEqual(graph.edges, ())


if __name__ == "__main__":
    unittest.main()
