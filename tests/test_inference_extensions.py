from __future__ import annotations

import unittest

from glio_noncode.errors import ValidationError
from glio_noncode.inference_extensions import (
    InferenceExtensionSuite,
    InferenceState,
)


def _observation(
    observation_id: str,
    *,
    channel: str,
    score: float = 0.8,
    context_score: float = 0.9,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "observation_id": observation_id,
        "source_id": f"source-{channel}",
        "channel": channel,
        "state": "supported",
        "score": score,
        "confidence": 0.9,
        "context_score": context_score,
        "payload": payload or {},
    }


class InferenceExtensionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.suite = InferenceExtensionSuite()
        self.variant = {
            "variant_id": "v1",
            "chromosome": "7",
            "start": 100,
            "end": 100,
            "reference": "A",
            "alternate": "T",
        }
        self.element = {
            "element_id": "enhancer-1",
            "chromosome": "7",
            "start": 90,
            "end": 140,
            "target_genes": ["GENE1"],
            "annotations": {"link_confidence": 0.72},
        }

    def test_motif_grammar_retains_sequence_delta_without_claiming_activity(self) -> None:
        result = self.suite.motif_grammar(
            {
                "variant_id": "v1",
                "state": "supported",
                "confidence": 0.8,
                "created_hits": [{"motif_id": "motif-a"}],
                "disrupted_hits": [{"motif_id": "motif-b"}],
            },
            self.element,
        )
        self.assertEqual(result.state, InferenceState.SUPPORTED)
        self.assertEqual(result.created_motif_ids, ("motif-a",))
        self.assertEqual(result.disrupted_motif_ids, ("motif-b",))
        self.assertTrue(any("occupancy" in item for item in result.limitations))

    def test_accessibility_context_gate_preserves_out_of_domain(self) -> None:
        result = self.suite.accessibility_delta(
            {"variant_id": "v1"},
            {
                "element_id": "enhancer-1",
                "observations": [
                    _observation(
                        "chrom-1",
                        channel="chromatin",
                        context_score=0.2,
                        payload={"delta": 0.4},
                    )
                ],
            },
        )
        self.assertEqual(result.state, InferenceState.OUT_OF_DOMAIN)
        self.assertEqual(result.delta, 0.4)

    def test_topology_and_link_handlers_use_explicit_targets(self) -> None:
        topology = self.suite.topology_rewiring(
            {
                "target_id": "GENE1",
                "observations": [
                    _observation(
                        "contact-1",
                        channel="contact",
                        payload={"contact_delta": -0.3},
                    )
                ],
            },
            self.element,
        )
        link = self.suite.element_gene_link(
            self.element,
            {
                "observations": [
                    _observation(
                        "contact-2",
                        channel="contact",
                        score=0.7,
                        payload={"gene_id": "GENE1"},
                    )
                ]
            },
        )
        self.assertEqual(topology.target_id, "GENE1")
        self.assertEqual(topology.direction, "decreased")
        self.assertEqual(link.target_id, "GENE1")
        self.assertEqual(link.state, InferenceState.SUPPORTED)

    def test_variant_element_link_can_use_distance_prior_but_labels_it(self) -> None:
        result = self.suite.variant_element_link(self.variant, self.element)
        self.assertEqual(result.state, InferenceState.SUPPORTED)
        self.assertIn("distance_score", result.features)
        self.assertTrue(any("priors" in item for item in result.limitations))

    def test_allele_specific_requires_both_alleles(self) -> None:
        result = self.suite.allele_specific(
            self.variant,
            {
                "observations": [
                    _observation(
                        "ref-1", channel="functional", payload={"allele": "ref", "value": 0.2}
                    ),
                    _observation(
                        "alt-1", channel="functional", payload={"allele": "alt", "value": 0.7}
                    ),
                ]
            },
        )
        self.assertEqual(result.state, InferenceState.SUPPORTED)
        self.assertEqual(result.delta, 0.5)
        incomplete = self.suite.allele_specific(
            self.variant,
            {
                "observations": [
                    _observation(
                        "ref-2", channel="functional", payload={"allele": "ref", "value": 0.2}
                    )
                ]
            },
        )
        self.assertIsNone(incomplete.delta)
        self.assertEqual(incomplete.state, InferenceState.ABSTAINED)

    def test_cell_state_and_longitudinal_handlers_preserve_context(self) -> None:
        mechanism = self.suite.cell_state_mechanism(
            {
                "observations": [
                    _observation(
                        "link-1",
                        channel="link",
                        payload={"state_id": "stem_like", "gene_id": "GENE1"},
                    )
                ]
            },
            {"state_id": "stem_like", "gene_id": "GENE1", "element_id": "enhancer-1"},
        )
        longitudinal = self.suite.longitudinal(
            {"variant_id": "v1", "clonality": "clonal_candidate"},
            {
                "observations": [
                    _observation(
                        "t0", channel="function", payload={"timepoint": "T0", "value": 0.2}
                    ),
                    _observation(
                        "t1", channel="function", payload={"timepoint": "T1", "value": 0.6}
                    ),
                ]
            },
        )
        self.assertEqual(mechanism.state, InferenceState.SUPPORTED)
        self.assertEqual(mechanism.state_id, "stem_like")
        self.assertEqual(longitudinal.delta, 0.4)
        self.assertEqual(longitudinal.direction, "increased")

    def test_germline_and_driver_posterior_keep_declared_limits(self) -> None:
        germline = self.suite.germline_context(
            {"variant_id": "v1", "origin": "germline"},
            {
                "inherited_context": True,
                "observations": [_observation("cohort-1", channel="cohort")],
            },
        )
        posterior = self.suite.driver_posterior(
            {"hypothesis_id": "hyp-1", "declared_prior": 0.1, "support": 0.8, "path_id": "path-1"},
            {"evidence_id": "evidence-1"},
        )
        self.assertEqual(germline.state, InferenceState.SUPPORTED)
        self.assertTrue(germline.inherited_context)
        self.assertGreater(posterior.posterior_proxy or 0.0, 0.1)
        self.assertEqual(posterior.calibration_status, "unvalidated_research_proxy")
        with self.assertRaises(ValidationError):
            self.suite.driver_posterior({"hypothesis_id": "hyp-1"}, {"evidence_id": "evidence-1"})


if __name__ == "__main__":
    unittest.main()
