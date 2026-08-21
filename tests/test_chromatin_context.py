from __future__ import annotations

import unittest

from glio_noncode.chromatin_context import (
    AccessibilityDeltaEstimator,
    AccessibilityMeasurement,
    ChromatinContextRetriever,
    ChromatinQueryResult,
    ChromatinState,
    ChromatinTrackKind,
    ChromatinTrackParser,
    H3K27acActivityEstimator,
)
from glio_noncode.errors import ValidationError
from glio_noncode.models import ReferenceContext


class ChromatinContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = ReferenceContext(
            "GRCh38", "glioma", "adult", "stem_like", territory="tumor"
        )
        self.other_context = ReferenceContext(
            "GRCh38", "glioma", "adult", "differentiated", territory="tumor"
        )

    def test_parser_converts_bed_coordinates_and_quarantines_bad_rows(self) -> None:
        text = (
            "chrom\tstart\tend\ttrack_id\tsignal\tcontext\tversion\treplicate\n"
            f"7\t99\t120\tatac-1\t4.5\t{self.context.key}\taccess-v1\tr1\n"
            "7\tbad\t150\tatac-bad\t4\tunknown\taccess-v1\tr1\n"
        )
        batch = ChromatinTrackParser().parse_text(
            text, source_id="atlas-atac", track_kind=ChromatinTrackKind.ATAC
        )
        self.assertEqual(len(batch.observations), 1)
        self.assertEqual(batch.observations[0].start, 100)
        self.assertEqual(batch.observations[0].end, 120)
        self.assertEqual(batch.observations[0].chromosome, "chr7")
        self.assertEqual(batch.observations[0].signal, 4.5)
        self.assertEqual(len(batch.issues), 1)
        self.assertEqual(batch.issues[0].code, "invalid_chromatin_row")
        self.assertTrue(batch.content_address)

    def test_json_parser_preserves_replicates_and_kind(self) -> None:
        payload = (
            '{"observations": [{"chromosome": "chr7", "start": 100, '
            f'"end": 120, "signal": 2.0, "context_key": "{self.context.key}", '
            '"replicate": "r1", "kind": "h3k27ac"}]}'
        )
        batch = ChromatinTrackParser().parse_text(
            payload,
            source_id="atlas-histone",
            track_kind=ChromatinTrackKind.HISTONE,
            input_format="json",
        )
        self.assertEqual(len(batch.observations), 1)
        self.assertEqual(batch.observations[0].track_kind, ChromatinTrackKind.H3K27AC)
        self.assertEqual(batch.observations[0].replicate_id, "r1")

    def test_retriever_is_context_gated_and_reports_out_of_domain(self) -> None:
        text = (
            "chrom\tstart\tend\ttrack_id\tsignal\tcontext\n"
            f"7\t99\t120\tatac-1\t4.5\t{self.context.key}\n"
            f"7\t99\t120\tatac-2\t2.0\t{self.other_context.key}\n"
        )
        batch = ChromatinTrackParser().parse_text(
            text, source_id="atlas-atac", track_kind=ChromatinTrackKind.ATAC
        )
        retriever = ChromatinContextRetriever(batch.observations)
        supported = retriever.query(ChromatinTrackKind.ATAC, "chr7", 100, 110, self.context)
        out_of_domain = retriever.query(
            ChromatinTrackKind.ATAC,
            "chr7",
            100,
            110,
            ReferenceContext("GRCh38", "glioma", "adult", "cycling", territory="tumor"),
        )
        self.assertEqual(supported.state, ChromatinState.SUPPORTED)
        self.assertEqual(supported.median_signal, 4.5)
        self.assertEqual(out_of_domain.state, ChromatinState.OUT_OF_DOMAIN)
        self.assertIsNone(out_of_domain.median_signal)

    def test_retriever_rejects_invalid_query_interval(self) -> None:
        with self.assertRaises(ValidationError):
            ChromatinContextRetriever(()).query(
                ChromatinTrackKind.ATAC, "7", 0, 10, self.context
            )

    def test_accessibility_delta_is_explicit_about_missingness_and_zero_baseline(self) -> None:
        estimator = AccessibilityDeltaEstimator()
        measured = estimator.estimate(
            AccessibilityMeasurement(
                "m1", "v1", self.context.key, ChromatinTrackKind.ATAC, 2.0, 3.0, "atlas", "h1"
            )
        )
        missing = estimator.estimate(
            AccessibilityMeasurement(
                "m2", "v2", self.context.key, ChromatinTrackKind.DNASE, None, 3.0, "atlas", "h2"
            )
        )
        zero = estimator.estimate(
            AccessibilityMeasurement(
                "m3", "v3", self.context.key, ChromatinTrackKind.ATAC, 0.0, 1.0, "atlas", "h3"
            )
        )
        self.assertEqual(measured.state, ChromatinState.SUPPORTED)
        self.assertEqual(measured.delta, 1.0)
        self.assertEqual(measured.relative_delta, 0.5)
        self.assertEqual(missing.state, ChromatinState.ABSTAINED)
        self.assertIsNone(missing.delta)
        self.assertIsNone(zero.relative_delta)

    def test_h3k27ac_estimator_reports_observation_and_preserves_ambiguity(self) -> None:
        text = (
            "chrom\tstart\tend\ttrack_id\tsignal\tcontext\treplicate\n"
            f"7\t99\t120\th3-1\t2.0\t{self.context.key}\tr1\n"
            f"7\t99\t120\th3-2\t3.0\t{self.context.key}\tr2\n"
        )
        batch = ChromatinTrackParser().parse_text(
            text, source_id="atlas-h3", track_kind=ChromatinTrackKind.H3K27AC
        )
        query = ChromatinContextRetriever(batch.observations).query(
            ChromatinTrackKind.H3K27AC, "7", 100, 120, self.context
        )
        activity = H3K27acActivityEstimator().estimate("enh-1", query)
        self.assertEqual(query.state, ChromatinState.AMBIGUOUS)
        self.assertEqual(activity.state, ChromatinState.AMBIGUOUS)
        self.assertEqual(activity.signal, 2.5)
        self.assertEqual(activity.replicate_count, 2)
        with self.assertRaises(ValidationError):
            H3K27acActivityEstimator().estimate(
                "enh-1",
                ChromatinQueryResult(
                    track_kind=ChromatinTrackKind.ATAC,
                    chromosome=query.chromosome,
                    start=query.start,
                    end=query.end,
                    context_key=query.context_key,
                    state=query.state,
                    observations=query.observations,
                    median_signal=query.median_signal,
                    replicate_spread=query.replicate_spread,
                    reason=query.reason,
                    content_address=query.content_address,
                ),
            )


if __name__ == "__main__":
    unittest.main()
