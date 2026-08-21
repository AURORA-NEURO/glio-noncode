from __future__ import annotations

import unittest

from glio_noncode.chromatin_alpha import (
    AlleleSpecificChromatinAnalyzer,
    BatchCellCompositionCorrector,
    ChromatinAlphaState,
    ChromatinStateSegmentationAdapter,
    EpigenomicPurityDeconvolver,
)

CONTEXT = "GRCh38|glioma|adult|stem_like|tumor|unknown"


class ChromatinAlphaTests(unittest.TestCase):
    def test_segmentation_splits_boundaries_and_retains_replicates(self) -> None:
        result = ChromatinStateSegmentationAdapter().segment(
            [
                {
                    "id": "c1",
                    "chrom": "7",
                    "start": 100,
                    "end": 120,
                    "assay": "ATAC",
                    "signal": 0.9,
                    "state": "open",
                    "replicate": "r1",
                    "sample": "s1",
                    "context_key": CONTEXT,
                },
                {
                    "id": "c2",
                    "chrom": "7",
                    "start": 100,
                    "end": 120,
                    "assay": "ATAC",
                    "signal": 0.8,
                    "state": "open",
                    "replicate": "r2",
                    "sample": "s1",
                    "context_key": CONTEXT,
                },
                {
                    "id": "c3",
                    "chrom": "7",
                    "start": 110,
                    "end": 130,
                    "assay": "ATAC",
                    "signal": 0.1,
                    "state": "closed",
                    "replicate": "r3",
                    "sample": "s2",
                    "context_key": CONTEXT,
                },
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(result.state, ChromatinAlphaState.AMBIGUOUS)
        self.assertEqual(len(result.segments), 3)
        self.assertEqual((result.segments[0].start, result.segments[0].end), (100, 109))
        self.assertEqual(result.segments[0].state_label, "open")
        self.assertEqual(result.segments[0].replicate_ids, ("r1", "r2"))
        self.assertEqual(result.segments[1].state, ChromatinAlphaState.AMBIGUOUS)
        self.assertEqual(result.segments[2].state, ChromatinAlphaState.PARTIAL)

    def test_segmentation_context_mismatch_is_out_of_domain(self) -> None:
        result = ChromatinStateSegmentationAdapter().segment(
            [
                {
                    "id": "wrong",
                    "chrom": "7",
                    "start": 100,
                    "end": 110,
                    "signal": 1,
                    "context_key": "GRCh38|glioma|pediatric|stem_like|tumor|unknown",
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(result.state, ChromatinAlphaState.OUT_OF_DOMAIN)
        self.assertEqual(result.segments, ())

    def test_allele_specific_chromatin_summarizes_replicate_delta(self) -> None:
        result = AlleleSpecificChromatinAnalyzer().analyze(
            [
                {
                    "id": "a1",
                    "variant_id": "v1",
                    "assay": "ATAC",
                    "reference_signal": 2,
                    "alternate_signal": 3,
                    "replicate": "r1",
                    "context_key": CONTEXT,
                },
                {
                    "id": "a2",
                    "variant_id": "v1",
                    "assay": "ATAC",
                    "reference_signal": 2,
                    "alternate_signal": 2.8,
                    "replicate": "r2",
                    "context_key": CONTEXT,
                },
            ],
            context_key=CONTEXT,
            ambiguity_tolerance=0.3,
        )
        result_row = result.results[0]
        self.assertEqual(result.state, ChromatinAlphaState.SUPPORTED)
        self.assertAlmostEqual(result_row.median_delta, 0.9)
        self.assertEqual(result_row.direction, "increased")
        self.assertEqual(result_row.replicate_count, 2)

    def test_allele_specific_chromatin_marks_mixed_directions_ambiguous(self) -> None:
        result = AlleleSpecificChromatinAnalyzer().analyze(
            [
                {
                    "variant_id": "v2",
                    "assay": "DNase",
                    "reference_signal": 2,
                    "alternate_signal": 3,
                    "replicate": "r1",
                    "context_key": CONTEXT,
                },
                {
                    "variant_id": "v2",
                    "assay": "DNase",
                    "reference_signal": 2,
                    "alternate_signal": 1,
                    "replicate": "r2",
                    "context_key": CONTEXT,
                },
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(result.state, ChromatinAlphaState.AMBIGUOUS)
        self.assertEqual(result.results[0].direction, "mixed")

    def test_epigenomic_purity_deconvolution_aggregates_marker_proportions(self) -> None:
        result = EpigenomicPurityDeconvolver().estimate(
            [
                {
                    "marker_id": "m1",
                    "assay": "methylation",
                    "observed_signal": 0.6,
                    "tumor_signal": 1.0,
                    "normal_signal": 0.0,
                    "context_key": CONTEXT,
                },
                {
                    "marker_id": "m2",
                    "assay": "ATAC",
                    "observed_signal": 0.34,
                    "tumor_signal": 0.5,
                    "normal_signal": 0.1,
                    "context_key": CONTEXT,
                },
            ],
            context_key=CONTEXT,
            minimum_markers=2,
        )
        self.assertEqual(result.state, ChromatinAlphaState.SUPPORTED)
        self.assertAlmostEqual(result.aggregate_purity, 0.6)
        self.assertEqual(result.purity_spread, 0.0)
        self.assertTrue(all(item.bounded_purity == 0.6 for item in result.estimates))

    def test_epigenomic_purity_deconvolution_preserves_out_of_range_marker(self) -> None:
        result = EpigenomicPurityDeconvolver().estimate(
            [
                {
                    "marker_id": "m1",
                    "observed_signal": 2,
                    "tumor_signal": 1,
                    "normal_signal": 0,
                    "context_key": CONTEXT,
                }
            ],
            context_key=CONTEXT,
            minimum_markers=1,
        )
        self.assertEqual(result.state, ChromatinAlphaState.PARTIAL)
        self.assertEqual(result.estimates[0].raw_purity, 2.0)
        self.assertEqual(result.estimates[0].bounded_purity, 1.0)

    def test_batch_cell_composition_correction_retains_adjustment_terms(self) -> None:
        result = BatchCellCompositionCorrector().correct(
            [
                {
                    "feature_id": "f1",
                    "batch_id": "batch-1",
                    "assay": "ATAC",
                    "raw_signal": 1.0,
                    "batch_offset": 0.1,
                    "cell_composition": {"tumor": 0.8, "normal": 0.2},
                    "composition_coefficients": {"tumor": 0.5, "normal": -0.5},
                    "context_key": CONTEXT,
                }
            ],
            context_key=CONTEXT,
            target_composition={"tumor": 0.5, "normal": 0.5},
        )
        correction = result.corrections[0]
        self.assertEqual(result.state, ChromatinAlphaState.SUPPORTED)
        self.assertAlmostEqual(correction.batch_adjustment, 0.1)
        self.assertAlmostEqual(correction.composition_adjustment, 0.3)
        self.assertAlmostEqual(correction.corrected_signal, 0.6)

    def test_batch_cell_composition_missing_batch_offset_is_partial(self) -> None:
        result = BatchCellCompositionCorrector().correct(
            [
                {
                    "feature_id": "f2",
                    "batch_id": "batch-missing",
                    "raw_signal": 1.0,
                    "cell_composition": {"tumor": 1.0},
                    "composition_coefficients": {"tumor": 0.2},
                    "context_key": CONTEXT,
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(result.state, ChromatinAlphaState.PARTIAL)
        self.assertEqual(result.corrections[0].state, ChromatinAlphaState.PARTIAL)


if __name__ == "__main__":
    unittest.main()
