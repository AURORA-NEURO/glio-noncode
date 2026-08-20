from __future__ import annotations

import unittest

from glio_noncode.data_sources import FetchReceipt, FetchStatus, SequenceSlice
from glio_noncode.identity import parse_variant
from glio_noncode.models import ReferenceContext
from glio_noncode.sequence_inference import (
    MotifDefinition,
    MotifScanner,
    SequenceAnalysisState,
    SequenceInference,
)


def _sequence(sequence: str = "AACCGGTTAACC") -> SequenceSlice:
    receipt = FetchReceipt(
        source_id="SRC-UCSC-REST",
        source_version="fixture-1",
        url="https://api.example/sequence",
        request_hash="sha256:req",
        response_hash="sha256:resp",
        status=FetchStatus.FETCHED,
        http_status=200,
        attempts=1,
        retrieved_at="2026-08-20T00:00:00+00:00",
        elapsed_seconds=0.01,
        cache_expires_at=None,
    )
    return SequenceSlice(
        "GRCh38", "chr7", 100, 100 + len(sequence) - 1, sequence, "SRC-UCSC-REST", receipt
    )


class SequenceInferenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = ReferenceContext("GRCh38", "glioma", "adult", "stem_like")

    def test_scanner_matches_iupac_on_both_strands(self) -> None:
        hits = MotifScanner().scan(
            "ACGTAC",
            genomic_start=100,
            motifs=(MotifDefinition("m1", "sequence-motif", "ACG"),),
        )
        self.assertTrue(any(hit.strand == "+" for hit in hits))
        self.assertTrue(all(hit.start >= 100 for hit in hits))

    def test_snv_disrupts_motif_without_creating_a_probability(self) -> None:
        variant = parse_variant("7:104:G>A", genome_build="GRCh38", variant_id="v1")
        result = SequenceInference().analyze(
            variant,
            _sequence(),
            motifs=(MotifDefinition("m-cgg", "CGG motif", "CGG"),),
        )
        self.assertEqual(result.state, SequenceAnalysisState.SUPPORTED)
        self.assertGreaterEqual(len(result.disrupted_hits), 1)
        self.assertIsNone(result.to_claim(context=self.context, edge_id="edge-1").score)

    def test_reference_mismatch_abstains(self) -> None:
        variant = parse_variant("7:104:C>A", genome_build="GRCh38", variant_id="mismatch")
        result = SequenceInference().analyze(variant, _sequence())
        self.assertEqual(result.state, SequenceAnalysisState.REFERENCE_MISMATCH)
        self.assertEqual(result.alternate_sequence_hash, None)

    def test_out_of_window_is_not_a_negative(self) -> None:
        variant = parse_variant("7:120:G>A", genome_build="GRCh38", variant_id="outside")
        result = SequenceInference().analyze(variant, _sequence())
        self.assertEqual(result.state, SequenceAnalysisState.OUT_OF_WINDOW)
        self.assertIn("not fully contained", result.limitations[0])


if __name__ == "__main__":
    unittest.main()
