from __future__ import annotations

import unittest

from glio_noncode.models import ReferenceContext
from glio_noncode.structural_extensions import (
    ComplexRearrangementResolver,
    CopyNumberSegment,
    CopyNumberSegmentHarmonizer,
    StructuralEvidenceState,
    SVConsensusImporter,
)
from glio_noncode.variation import Breakend, StructuralEvent, StructuralEventKind


class StructuralExtensionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = ReferenceContext("GRCh38", "glioma", "adult", "stem_like")

    def test_caller_consensus_preserves_rows_and_quarantines_malformed_input(self) -> None:
        text = (
            "caller_id\tcaller_version\tevent_id\tchrom\tstart\tend\tsvtype\tsupport\n"
            "caller-a\t1.0\ta1\t7\t100\t200\tDEL\t0.9\n"
            "caller-b\t2.1\tb1\tchr7\t102\t201\tDEL\t80\n"
            "caller-b\t2.1\tbad\tchr7\tnope\t201\tDEL\t0.8\n"
        )
        batch = SVConsensusImporter(breakpoint_tolerance=5).parse_text(
            text,
            source_id="sv-fixture",
        )
        self.assertEqual(len(batch.observations), 2)
        self.assertEqual(len(batch.issues), 1)
        self.assertEqual(len(batch.consensus), 1)
        self.assertEqual(batch.consensus[0].state, StructuralEvidenceState.SUPPORTED)
        self.assertEqual(batch.consensus[0].caller_ids, ("caller-a", "caller-b"))
        self.assertEqual(batch.consensus[0].breakpoint_disagreement_bp, 2)
        self.assertTrue(batch.content_address.startswith("sha256:"))

    def test_consensus_does_not_hide_breakpoint_disagreement(self) -> None:
        text = (
            "caller_id\tevent_id\tevent_key\tchrom\tstart\tend\tsvtype\tsupport\n"
            "caller-a\ta1\tcluster-1\t7\t100\t200\tDEL\t1\n"
            "caller-b\tb1\tcluster-1\t7\t140\t240\tDEL\t1\n"
        )
        batch = SVConsensusImporter(breakpoint_tolerance=5).parse_text(
            text,
            source_id="ambiguous-sv",
        )
        self.assertEqual(batch.consensus[0].state, StructuralEvidenceState.AMBIGUOUS)
        self.assertEqual(batch.consensus[0].breakpoint_disagreement_bp, 40)

    def test_complex_resolution_retains_shared_locus_as_ambiguity(self) -> None:
        first = StructuralEvent(
            event_id="event-1",
            kind=StructuralEventKind.BREAKEND_PAIR,
            breakends=(
                Breakend("b1", "7", 100, "forward", "b2"),
                Breakend("b2", "7", 200, "reverse", "b1"),
            ),
            haplotype_segments=(),
            context=self.context,
            source_id="sv-fixture",
            reconstruction_support=1.0,
            uncertainty=0.0,
        )
        second = StructuralEvent(
            event_id="event-2",
            kind=StructuralEventKind.BREAKEND_PAIR,
            breakends=(
                Breakend("c1", "7", 100, "forward", "c2"),
                Breakend("c2", "8", 300, "reverse", "c1"),
            ),
            haplotype_segments=(),
            context=self.context,
            source_id="sv-fixture",
            reconstruction_support=1.0,
            uncertainty=0.0,
        )
        result = ComplexRearrangementResolver().resolve((first, second))
        self.assertEqual(len(result.resolutions), 1)
        self.assertEqual(result.resolutions[0].state, StructuralEvidenceState.AMBIGUOUS)
        self.assertTrue(result.resolutions[0].ambiguities)
        self.assertEqual(result.resolutions[0].event_ids, ("event-1", "event-2"))

    def test_copy_number_harmonizer_splits_edges_and_retains_disagreement(self) -> None:
        segments = (
            CopyNumberSegment("a-1", "caller-a", "7", 1, 100, 2.0, "sha256:a", "cn-fixture"),
            CopyNumberSegment("b-1", "caller-b", "7", 1, 50, 2.0, "sha256:b", "cn-fixture"),
            CopyNumberSegment("b-2", "caller-b", "7", 51, 100, 3.0, "sha256:c", "cn-fixture"),
        )
        result = CopyNumberSegmentHarmonizer().harmonize(segments)
        self.assertEqual([(item.start, item.end) for item in result.segments], [(1, 50), (51, 100)])
        self.assertEqual(result.segments[0].state, StructuralEvidenceState.SUPPORTED)
        self.assertEqual(result.segments[1].state, StructuralEvidenceState.AMBIGUOUS)
        self.assertEqual(result.segments[1].source_segment_ids, ("a-1", "b-2"))

    def test_copy_number_parser_quarantines_invalid_rows(self) -> None:
        text = (
            "caller_id\tsegment_id\tchrom\tstart\tend\tcopy_number\n"
            "caller-a\ta-1\t7\t1\t10\t2\n"
            "caller-b\tb-1\t7\tbad\t10\t2\n"
        )
        result = CopyNumberSegmentHarmonizer().parse_text(text, source_id="cn-fixture")
        self.assertEqual(len(result.segments), 1)
        self.assertEqual(len(result.issues), 1)


if __name__ == "__main__":
    unittest.main()
