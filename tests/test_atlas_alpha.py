from __future__ import annotations

import unittest

from glio_noncode.atlas_alpha import (
    AtlasAlphaState,
    EnhancerPromoterSilencerClassifier,
    MethylationTrackHarmonizer,
    OpenChromatinTrackHarmonizer,
    SuperEnhancerCandidateAtlas,
)

CONTEXT = "GRCh38|glioma|adult|stem_like|unknown|unknown"


class AtlasAlphaTests(unittest.TestCase):
    def test_open_chromatin_splits_observed_boundaries_and_harmonizes_replicates(self) -> None:
        result = OpenChromatinTrackHarmonizer().harmonize(
            [
                {
                    "observation_id": "atac-1",
                    "chrom": "7",
                    "start": 100,
                    "end": 120,
                    "track_kind": "ATAC",
                    "signal": 4.0,
                    "replicate_id": "rep-1",
                    "caller_id": "caller-a",
                    "context_key": CONTEXT,
                    "source_id": "atac-v1",
                },
                {
                    "observation_id": "atac-2",
                    "chrom": "7",
                    "start": 100,
                    "end": 120,
                    "track_kind": "ATAC",
                    "signal": 4.1,
                    "replicate_id": "rep-2",
                    "caller_id": "caller-a",
                    "context_key": CONTEXT,
                    "source_id": "atac-v1",
                },
                {
                    "observation_id": "atac-3",
                    "chrom": "7",
                    "start": 110,
                    "end": 125,
                    "track_kind": "ATAC",
                    "signal": 3.8,
                    "replicate_id": "rep-3",
                    "caller_id": "caller-a",
                    "context_key": CONTEXT,
                    "source_id": "atac-v1",
                },
            ],
            context_key=CONTEXT,
            spread_tolerance=0.5,
        )
        self.assertEqual(result.state, AtlasAlphaState.PARTIAL)
        self.assertEqual(len(result.intervals), 3)
        self.assertEqual((result.intervals[0].start, result.intervals[0].end), (100, 109))
        self.assertEqual(result.intervals[0].replicate_ids, ("rep-1", "rep-2"))
        self.assertAlmostEqual(result.intervals[0].median_signal, 4.05)
        self.assertEqual(result.intervals[1].caller_ids, ("caller-a",))
        self.assertTrue(result.observations[0].raw_hash.startswith("sha256:"))

    def test_open_chromatin_signal_disagreement_is_ambiguous(self) -> None:
        result = OpenChromatinTrackHarmonizer().harmonize(
            [
                {
                    "id": "a1",
                    "chrom": "7",
                    "start": 100,
                    "end": 120,
                    "signal": 1,
                    "replicate": "r1",
                    "caller": "caller-a",
                    "context": CONTEXT,
                },
                {
                    "id": "a2",
                    "chrom": "7",
                    "start": 100,
                    "end": 120,
                    "signal": 5,
                    "replicate": "r2",
                    "caller": "caller-a",
                    "context": CONTEXT,
                },
            ],
            context_key=CONTEXT,
            spread_tolerance=1,
        )
        self.assertEqual(result.state, AtlasAlphaState.AMBIGUOUS)
        self.assertEqual(result.intervals[0].state, AtlasAlphaState.AMBIGUOUS)
        self.assertEqual(result.intervals[0].signal_spread, 4.0)

    def test_methylation_derives_fraction_and_harmonizes_coverage_across_replicates(self) -> None:
        result = MethylationTrackHarmonizer().harmonize(
            [
                {
                    "id": "m1",
                    "chrom": "1",
                    "start": 200,
                    "end": 200,
                    "methylated_count": 8,
                    "total_count": 10,
                    "replicate": "r1",
                    "context_key": CONTEXT,
                },
                {
                    "id": "m2",
                    "chrom": "1",
                    "start": 200,
                    "end": 200,
                    "methylated_count": 6,
                    "total_count": 10,
                    "replicate": "r2",
                    "context_key": CONTEXT,
                },
            ],
            context_key=CONTEXT,
            spread_tolerance=0.3,
        )
        interval = result.intervals[0]
        self.assertEqual(result.state, AtlasAlphaState.SUPPORTED)
        self.assertAlmostEqual(interval.median_fraction, 0.7)
        self.assertEqual(interval.total_methylated_count, 14)
        self.assertEqual(interval.total_count, 20)
        self.assertEqual(interval.replicate_ids, ("r1", "r2"))

    def test_methylation_zero_coverage_is_partial(self) -> None:
        result = MethylationTrackHarmonizer().harmonize(
            [
                {
                    "id": "m-zero",
                    "chrom": "1",
                    "start": 200,
                    "end": 200,
                    "replicate": "r1",
                    "context_key": CONTEXT,
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(result.state, AtlasAlphaState.PARTIAL)
        self.assertIsNone(result.intervals[0].median_fraction)
        self.assertEqual(result.intervals[0].state, AtlasAlphaState.PARTIAL)

    def test_role_classifier_preserves_multi_role_and_missing_channels(self) -> None:
        result = EnhancerPromoterSilencerClassifier().classify(
            [
                {
                    "element_id": "el-multi",
                    "chrom": "7",
                    "start": 100,
                    "end": 110,
                    "promoter_score": 0.9,
                    "enhancer_score": 0.8,
                    "open_chromatin_signal": 3,
                    "contact_support": 0.7,
                    "target_gene_ids": ["EGFR"],
                    "context_key": CONTEXT,
                },
                {
                    "element_id": "el-methylated",
                    "chrom": "7",
                    "start": 200,
                    "end": 210,
                    "methylation_fraction": 0.9,
                    "context_key": CONTEXT,
                },
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(result.state, AtlasAlphaState.AMBIGUOUS)
        self.assertEqual(result.classifications[0].roles, ("promoter", "enhancer"))
        self.assertEqual(result.classifications[0].state, AtlasAlphaState.AMBIGUOUS)
        methylated = result.classifications[1]
        self.assertEqual(methylated.roles, ("silencer_candidate",))
        self.assertEqual(methylated.state, AtlasAlphaState.PARTIAL)
        self.assertIn("open_chromatin", methylated.missing_channels)
        self.assertIn("contact_support", methylated.missing_channels)

    def test_role_classifier_rejects_context_transport(self) -> None:
        result = EnhancerPromoterSilencerClassifier().classify(
            [
                {
                    "element_id": "wrong-context",
                    "chrom": "7",
                    "start": 100,
                    "end": 110,
                    "enhancer_score": 0.9,
                    "context_key": "GRCh38|glioma|pediatric|stem_like|unknown|unknown",
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(result.state, AtlasAlphaState.OUT_OF_DOMAIN)
        self.assertEqual(result.classifications, ())
        self.assertEqual(result.issues[0].code, "context_mismatch")

    def test_super_enhancer_atlas_ranks_merges_and_retains_target_genes(self) -> None:
        result = SuperEnhancerCandidateAtlas().build(
            [
                {
                    "enhancer_id": "enh-low",
                    "chrom": "7",
                    "start": 100,
                    "end": 110,
                    "signal": 1,
                    "target_gene_ids": ["A"],
                    "context_key": CONTEXT,
                },
                {
                    "enhancer_id": "enh-high-1",
                    "chrom": "7",
                    "start": 120,
                    "end": 130,
                    "signal": 5,
                    "target_gene_ids": ["EGFR"],
                    "context_key": CONTEXT,
                },
                {
                    "enhancer_id": "enh-high-2",
                    "chrom": "7",
                    "start": 135,
                    "end": 145,
                    "signal": 4,
                    "target_gene_ids": ["PDGFRA"],
                    "context_key": CONTEXT,
                },
            ],
            context_key=CONTEXT,
            minimum_constituents=2,
            merge_gap_bp=5,
            rank_quantile=0.5,
        )
        self.assertEqual(result.state, AtlasAlphaState.PARTIAL)
        candidate = result.candidates[0]
        self.assertEqual(candidate.constituent_ids, ("enh-high-1", "enh-high-2"))
        self.assertEqual(candidate.target_gene_ids, ("EGFR", "PDGFRA"))
        self.assertEqual((candidate.start, candidate.end), (120, 145))
        self.assertEqual(candidate.state, AtlasAlphaState.PARTIAL)
        self.assertNotIn("declared_activity", candidate.evidence_channels)

    def test_super_enhancer_atlas_requires_multiple_ranked_constituents(self) -> None:
        result = SuperEnhancerCandidateAtlas().build(
            [
                {
                    "enhancer_id": "enh-one",
                    "chrom": "7",
                    "start": 100,
                    "end": 110,
                    "signal": 10,
                    "context_key": CONTEXT,
                }
            ],
            context_key=CONTEXT,
            minimum_constituents=2,
        )
        self.assertEqual(result.state, AtlasAlphaState.ABSTAINED)
        self.assertEqual(result.candidates, ())


if __name__ == "__main__":
    unittest.main()
