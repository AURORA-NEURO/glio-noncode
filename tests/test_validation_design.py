from __future__ import annotations

import unittest

from glio_noncode.data_sources import FetchReceipt, FetchStatus, SequenceSlice
from glio_noncode.identity import parse_variant
from glio_noncode.validation_design import (
    DesignStatus,
    GuideDesigner,
    PowerPlanner,
)


def _slice(sequence: str, start: int = 100) -> SequenceSlice:
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
        "GRCh38", "chr7", start, start + len(sequence) - 1, sequence, "SRC-UCSC-REST", receipt
    )


class ValidationDesignTests(unittest.TestCase):
    def test_guide_designer_returns_local_ngg_candidate_with_unassessed_off_targets(self) -> None:
        protospacer = "AAAAAAAAAACAAAAAAAAA"
        sequence = _slice(protospacer + "TGG" + "AAA")
        variant = parse_variant("7:110:C>G", genome_build="GRCh38", variant_id="v1")
        result = GuideDesigner().design(variant, sequence)
        self.assertEqual(result.status, DesignStatus.READY_FOR_REVIEW)
        self.assertGreaterEqual(len(result.candidates), 1)
        self.assertTrue(
            all(candidate.off_target_status == "unassessed" for candidate in result.candidates)
        )
        self.assertTrue(
            all(
                candidate.start <= variant.start <= candidate.end for candidate in result.candidates
            )
        )

    def test_guide_designer_blocks_reference_mismatch(self) -> None:
        sequence = _slice("A" * 30)
        variant = parse_variant("7:110:C>G", genome_build="GRCh38", variant_id="mismatch")
        result = GuideDesigner().design(variant, sequence)
        self.assertEqual(result.status, DesignStatus.BLOCKED)
        self.assertEqual(result.candidates, ())

    def test_power_planner_declares_approximation_and_controls(self) -> None:
        plan = PowerPlanner().plan(effect_size=0.25, baseline_rate=0.5, target_power=0.9)
        self.assertGreater(plan.samples_per_group, 1)
        self.assertEqual(plan.total_samples, plan.samples_per_group * 2)
        self.assertIn("negative_control", plan.controls)
        self.assertTrue(any("approximation" in limitation for limitation in plan.limitations))


if __name__ == "__main__":
    unittest.main()
