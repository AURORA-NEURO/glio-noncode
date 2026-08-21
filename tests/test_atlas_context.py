from __future__ import annotations

import unittest

from glio_noncode.atlas_context import ContextEvidenceBuilder, ContextObservation
from glio_noncode.models import EvidenceState, EvidenceTier, ReferenceContext


class AtlasContextTests(unittest.TestCase):
    def test_context_builder_transports_matching_observation(self) -> None:
        context = ReferenceContext("GRCh38", "glioma", "adult", "stem_like")
        observation = ContextObservation(
            "obs-1",
            "SRC-ENCODE-REST",
            "encode-2026",
            context,
            "chromatin",
            EvidenceState.SUPPORTED,
            EvidenceTier.REFERENCE,
            0.8,
            0.9,
            "Public assay metadata supports a chromatin observation.",
            {"accession": "ENCSR000AAA"},
        )
        bundle = ContextEvidenceBuilder().build("v1", "edge-1", context, (observation,))
        self.assertEqual(bundle.matched_count, 1)
        self.assertEqual(bundle.claims[0].state, EvidenceState.SUPPORTED)
        self.assertEqual(bundle.claims[0].payload["context_match"]["score"], 1.0)

    def test_context_builder_marks_transport_out_of_domain(self) -> None:
        case = ReferenceContext("GRCh38", "glioma", "adult", "stem_like")
        other = ReferenceContext("GRCh37", "healthy", "adult", "bulk", "blood", "treated")
        observation = ContextObservation(
            "obs-2",
            "fixture-source",
            "v1",
            other,
            "literature",
            EvidenceState.SUPPORTED,
            EvidenceTier.REFERENCE,
            0.7,
            0.8,
            "Observation from a different context.",
            {},
        )
        bundle = ContextEvidenceBuilder().build("v1", "edge-1", case, (observation,))
        self.assertEqual(bundle.out_of_context_count, 1)
        self.assertEqual(bundle.claims[0].state, EvidenceState.OUT_OF_DOMAIN)
        self.assertIsNone(bundle.claims[0].score)


if __name__ == "__main__":
    unittest.main()
