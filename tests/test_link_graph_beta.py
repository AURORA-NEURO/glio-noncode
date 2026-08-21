from __future__ import annotations

import unittest

from glio_noncode.link_graph import LinkState
from glio_noncode.link_graph_beta import (
    ActivityByContactLinkAdapter,
    AlleleSpecificLinkEvidenceIntegrator,
    AlleleSpecificLinkObservation,
    CoaccessibilityLinker,
    CoaccessibilityObservation,
    LinkGraphBetaDirection,
    MolecularQtlLinker,
    MolecularQtlObservation,
)
from glio_noncode.models import ReferenceContext

CONTEXT = ReferenceContext("GRCh38", "glioma", "adult", "stem_like", territory="core")
OTHER_CONTEXT = ReferenceContext("GRCh38", "glioma", "adult", "differentiated", territory="core")


class LinkGraphBetaTests(unittest.TestCase):
    def test_activity_by_contact_adapter_retains_components_and_support(self) -> None:
        text = (
            "evidence_id\tvariant_id\telement_id\tgene_id\tactivity_signal\tcontact_signal\t"
            "context\tversion\n"
            f"abc-1\tv1\tenh-1\tGENE1\t0.8\t5\t{CONTEXT.key}\tv1\n"
            "abc-bad\tv1\tenh-1\tGENE1\tbad\t5\tunknown\tv1\n"
        )
        batch = ActivityByContactLinkAdapter().parse_text(
            text, source_id="abc-atlas", contact_scale=10
        )
        self.assertEqual(len(batch.observations), 1)
        self.assertEqual(batch.observations[0].support, 0.4)
        self.assertEqual(batch.observations[0].source_version, "v1")
        self.assertEqual(batch.issues[0].code, "invalid_activity_contact_row")

    def test_coaccessibility_linker_preserves_single_method_partial_and_context_gate(self) -> None:
        observation = CoaccessibilityObservation(
            "co-1",
            "v1",
            "enh-1",
            "GENE1",
            0.75,
            CONTEXT.key,
            "coaccess-atlas",
            "v2",
            "raw-co-1",
            0.9,
        )
        graph = CoaccessibilityLinker().link((observation,), CONTEXT, variant_id="v1")
        self.assertEqual(graph.state, LinkState.PARTIAL)
        self.assertEqual(graph.links[0].gene_id, "GENE1")
        self.assertEqual(graph.links[0].evidence_ids, ("co-1",))
        other = CoaccessibilityLinker().link(
            (
                CoaccessibilityObservation(
                    "co-other",
                    "v1",
                    "enh-1",
                    "GENE1",
                    0.75,
                    OTHER_CONTEXT.key,
                    "coaccess-atlas",
                    "v2",
                    "raw-co-other",
                ),
            ),
            CONTEXT,
            variant_id="v1",
        )
        self.assertEqual(other.state, LinkState.OUT_OF_DOMAIN)

    def test_qtl_linker_uses_declared_pvalue_transform_and_retains_effect(self) -> None:
        observation = MolecularQtlObservation(
            "qtl-1",
            "v1",
            "enh-1",
            "GENE1",
            0.42,
            CONTEXT.key,
            "qtl-atlas",
            "v3",
            "raw-qtl-1",
            q_value=0.001,
        )
        graph = MolecularQtlLinker().link((observation,), CONTEXT, variant_id="v1")
        self.assertEqual(graph.state, LinkState.PARTIAL)
        self.assertEqual(graph.links[0].support, 0.3)
        self.assertEqual(graph.links[0].evidence_ids, ("qtl-1",))

    def test_allele_specific_integrator_surfaces_gain_loss_conflict(self) -> None:
        observations = (
            AlleleSpecificLinkObservation(
                "allele-gain",
                "v1",
                "enh-1",
                "GENE1",
                LinkGraphBetaDirection.GAIN,
                0.8,
                0.9,
                CONTEXT.key,
                "sequence-atlas",
                "v1",
                "raw-gain",
            ),
            AlleleSpecificLinkObservation(
                "allele-loss",
                "v1",
                "enh-1",
                "GENE1",
                LinkGraphBetaDirection.LOSS,
                0.7,
                0.9,
                CONTEXT.key,
                "chromatin-atlas",
                "v2",
                "raw-loss",
            ),
        )
        graph = AlleleSpecificLinkEvidenceIntegrator().integrate(
            observations, CONTEXT, variant_id="v1"
        )
        self.assertEqual(graph.state, LinkState.CONTRADICTORY)
        self.assertIsNone(graph.links[0].support)
        self.assertEqual(set(graph.links[0].evidence_ids), {"allele-gain", "allele-loss"})


if __name__ == "__main__":
    unittest.main()
