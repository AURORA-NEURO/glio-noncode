from __future__ import annotations

import unittest

from glio_noncode.sequence_adapters import (
    LongContextVariantEffectAdapter,
    RegulatoryTrackDeltaEnsemble,
    SequenceAdapterState,
    SequenceContextEncoder,
    SequenceFoundationModelAdapter,
)


class SequenceAdapterTests(unittest.TestCase):
    def test_sequence_context_encoder_is_deterministic_and_transparent(self) -> None:
        encoder = SequenceContextEncoder()
        first = encoder.encode(
            "ACGTNACG",
            sequence_id="window-1",
            source_id="sequence-fixture",
            kmer_size=2,
        )
        second = encoder.encode(
            "ACGTNACG",
            sequence_id="window-1",
            source_id="sequence-fixture",
            kmer_size=2,
        )
        self.assertEqual(first.content_address, second.content_address)
        self.assertAlmostEqual(first.gc_fraction, 0.5)
        self.assertAlmostEqual(first.ambiguous_fraction, 0.125)
        self.assertIn("AC", first.kmer_frequencies)

    def test_foundation_adapter_preserves_version_and_quarantines_invalid_delta(self) -> None:
        text = (
            "model_id\tmodel_version\tvariant_id\tref_score\talt_score\tcontext_length\n"
            "model-a\t1.0\tv1\t0.2\t0.8\t512\n"
            "model-b\t2.0\tv1\t0.2\t0.7\t512\n"
        )
        result = SequenceFoundationModelAdapter().parse_text(
            text,
            source_id="foundation-fixture",
        )
        self.assertEqual(len(result.observations), 2)
        self.assertEqual(result.observations[0].model_version, "1.0")
        self.assertEqual(result.observations[0].delta, 0.6)
        self.assertEqual(result.issues, ())

    def test_long_context_adapter_rejects_short_context_and_keeps_valid_rows(self) -> None:
        text = (
            "model_id\tmodel_version\tvariant_id\tref_score\talt_score\tcontext_length\n"
            "long-a\t1.0\tv1\t0.5\t0.7\t2048\n"
            "long-b\t1.0\tv1\t0.5\t0.6\t512\n"
        )
        result = LongContextVariantEffectAdapter().parse_text(
            text,
            source_id="long-context-fixture",
        )
        self.assertEqual(len(result.observations), 1)
        self.assertEqual(len(result.issues), 1)
        self.assertEqual(result.observations[0].context_length, 2048)

    def test_ensemble_retains_support_and_model_disagreement(self) -> None:
        batch = SequenceFoundationModelAdapter().parse_text(
            "model_id\tmodel_version\tvariant_id\tref_score\talt_score\tcontext_length\n"
            "model-a\t1\tv1\t0.2\t0.8\t512\n"
            "model-b\t1\tv1\t0.2\t0.7\t512\n"
            "model-c\t1\tv2\t0.2\t0.3\t512\n",
            source_id="ensemble-fixture",
        )
        result = RegulatoryTrackDeltaEnsemble(disagreement_tolerance=0.05).combine(
            batch.observations
        )
        by_variant = {item.variant_id: item for item in result}
        self.assertEqual(by_variant["v1"].state, SequenceAdapterState.AMBIGUOUS)
        self.assertEqual(by_variant["v1"].model_ids, ("model-a", "model-b"))
        self.assertEqual(by_variant["v2"].state, SequenceAdapterState.PARTIAL)
        self.assertTrue(by_variant["v1"].limitations)


if __name__ == "__main__":
    unittest.main()
