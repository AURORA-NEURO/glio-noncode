from __future__ import annotations

import unittest

from glio_noncode.structural_beta import (
    ChromothripsisPatternDetector,
    EnhancerHijackingCandidateDetector,
    ExtrachromosomalDnaCandidateDetector,
    FocalAmplificationBoundaryMapper,
    StructuralBetaState,
)

CONTEXT = "GRCh38|glioma|adult|stem_like|unknown|unknown"


class StructuralBetaTests(unittest.TestCase):
    def test_focal_amplification_mapper_preserves_edges_and_callers(self) -> None:
        result = FocalAmplificationBoundaryMapper().map(
            [
                {
                    "segment_id": "a-1",
                    "caller_id": "caller-a",
                    "source_id": "cn-a",
                    "source_version": "v1",
                    "chrom": "7",
                    "start": 100,
                    "end": 200,
                    "copy_number": 8,
                    "context_key": CONTEXT,
                },
                {
                    "segment_id": "b-1",
                    "caller_id": "caller-b",
                    "source_id": "cn-b",
                    "source_version": "v2",
                    "chrom": "7",
                    "start": 100,
                    "end": 200,
                    "copy_number": 7,
                    "context_key": CONTEXT,
                },
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(result.state, StructuralBetaState.SUPPORTED)
        self.assertEqual(len(result.candidates), 1)
        candidate = result.candidates[0]
        self.assertEqual((candidate.start, candidate.end), (100, 200))
        self.assertEqual(candidate.caller_ids, ("caller-a", "caller-b"))
        self.assertEqual(candidate.left_boundary_support, (100,))
        self.assertEqual(candidate.right_boundary_support, (200,))
        self.assertEqual(len(candidate.raw_hashes), 2)

    def test_focal_amplification_mapper_abstains_without_amplified_segments(self) -> None:
        result = FocalAmplificationBoundaryMapper().map(
            [{"chrom": "7", "start": 1, "end": 20, "copy_number": 3}],
            amplification_threshold=6,
            minimum_gain=4,
        )
        self.assertEqual(result.state, StructuralBetaState.ABSTAINED)
        self.assertEqual(result.candidates, ())

    def test_chromothripsis_detector_reports_cluster_pattern_without_probability(self) -> None:
        records = [
            {
                "event_id": f"sv-{index}",
                "chrom": "7",
                "pos": 1000 + index * 100,
                "orientation": "forward" if index % 2 == 0 else "reverse",
                "copy_number_state": "high" if index % 2 == 0 else "low",
                "context_key": CONTEXT,
                "source_id": "sv-calls",
            }
            for index in range(6)
        ]
        result = ChromothripsisPatternDetector().detect(
            records,
            context_key=CONTEXT,
            require_copy_number_oscillation=True,
        )
        self.assertEqual(result.state, StructuralBetaState.SUPPORTED)
        self.assertEqual(len(result.candidates), 1)
        candidate = result.candidates[0]
        self.assertEqual(candidate.breakpoint_count, 6)
        self.assertEqual(candidate.orientation_switches, 5)
        self.assertEqual(candidate.copy_number_switches, 5)
        self.assertLessEqual(candidate.evidence_index, 1.0)
        self.assertTrue(
            any("not a calibrated probability" in warning for warning in result.warnings)
        )

    def test_chromothripsis_detector_is_partial_when_copy_state_is_missing(self) -> None:
        result = ChromothripsisPatternDetector().detect(
            [
                {
                    "event_id": f"sv-{index}",
                    "chrom": "7",
                    "pos": 1000 + index * 100,
                    "orientation": "forward" if index % 2 == 0 else "reverse",
                }
                for index in range(6)
            ],
            min_orientation_switches=3,
        )
        self.assertEqual(result.state, StructuralBetaState.PARTIAL)
        self.assertEqual(result.candidates[0].copy_number_states, ())

    def test_ecdna_detector_requires_explicit_circular_evidence(self) -> None:
        high_copy_only = ExtrachromosomalDnaCandidateDetector().detect(
            [{"component_id": "amp-1", "copy_number": 12, "junction_count": 4}]
        )
        self.assertEqual(high_copy_only.state, StructuralBetaState.ABSTAINED)
        self.assertEqual(high_copy_only.candidates, ())

        result = ExtrachromosomalDnaCandidateDetector().detect(
            [
                {
                    "component_id": "cycle-1",
                    "caller_id": "caller-a",
                    "source_id": "sv-a",
                    "is_circular": True,
                    "junction_count": 3,
                    "copy_number": 12,
                    "chrom": "7",
                    "start": 100,
                    "end": 500,
                },
                {
                    "component_id": "cycle-1",
                    "caller_id": "caller-b",
                    "source_id": "sv-b",
                    "is_circular": True,
                    "junction_count": 3,
                    "copy_number": 11,
                    "chrom": "7",
                    "start": 100,
                    "end": 500,
                },
            ]
        )
        self.assertEqual(result.state, StructuralBetaState.SUPPORTED)
        self.assertEqual(result.candidates[0].junction_count, 3)
        self.assertEqual(result.candidates[0].caller_ids, ("caller-a", "caller-b"))

    def test_ecdna_detector_keeps_conflicting_linear_evidence_ambiguous(self) -> None:
        result = ExtrachromosomalDnaCandidateDetector().detect(
            [
                {
                    "component_id": "cycle-1",
                    "caller_id": "caller-a",
                    "source_id": "sv-a",
                    "is_circular": True,
                    "junction_count": 3,
                    "copy_number": 12,
                },
                {
                    "component_id": "cycle-1",
                    "caller_id": "caller-b",
                    "source_id": "sv-b",
                    "is_circular": True,
                    "linear_evidence": True,
                    "junction_count": 3,
                    "copy_number": 12,
                },
            ]
        )
        self.assertEqual(result.state, StructuralBetaState.AMBIGUOUS)
        self.assertEqual(result.candidates[0].conflicting_linear_evidence, ("sv-b",))

    def test_enhancer_hijacking_detector_requires_bridge_and_keeps_alternatives(self) -> None:
        records = [
            {
                "event_id": "sv-1",
                "enhancer_id": "enh-1",
                "target_gene_id": "gene-a",
                "context_key": CONTEXT,
                "breakpoint_supported": True,
                "activity_supported": True,
                "contact_supported": True,
                "enhancer_chrom": "7",
                "enhancer_start": 100,
                "enhancer_end": 200,
                "promoter_chrom": "7",
                "promoter_start": 900,
                "promoter_end": 1000,
                "source_id": "links-1",
                "source_version": "v1",
            },
            {
                "event_id": "sv-1",
                "enhancer_id": "enh-1",
                "target_gene_id": "gene-b",
                "context_key": CONTEXT,
                "breakpoint_supported": True,
                "contact_supported": True,
                "source_id": "links-2",
                "source_version": "v2",
            },
        ]
        result = EnhancerHijackingCandidateDetector().detect(records, context_key=CONTEXT)
        self.assertEqual(result.state, StructuralBetaState.AMBIGUOUS)
        self.assertEqual(len(result.candidates), 2)
        self.assertTrue(all(candidate.alternatives_for_event for candidate in result.candidates))
        self.assertEqual(result.candidates[0].enhancer_interval, ("chr7", 100, 200))
        self.assertTrue(all(candidate.breakpoint_bridge for candidate in result.candidates))

    def test_enhancer_hijacking_detector_abstains_without_bridge_and_gates_context(self) -> None:
        no_bridge = EnhancerHijackingCandidateDetector().detect(
            [
                {
                    "event_id": "sv-1",
                    "enhancer_id": "enh-1",
                    "target_gene_id": "gene-a",
                    "context_key": CONTEXT,
                    "contact_supported": True,
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(no_bridge.state, StructuralBetaState.ABSTAINED)
        self.assertEqual(no_bridge.candidates, ())

        out_of_domain = EnhancerHijackingCandidateDetector().detect(
            [
                {
                    "event_id": "sv-1",
                    "enhancer_id": "enh-1",
                    "target_gene_id": "gene-a",
                    "context_key": "GRCh38|glioma|pediatric|unknown|unknown|unknown",
                    "breakpoint_supported": True,
                    "contact_supported": True,
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(out_of_domain.state, StructuralBetaState.OUT_OF_DOMAIN)
