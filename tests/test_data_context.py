from __future__ import annotations

import unittest

from glio_noncode.assay_qc import AssayQCEvaluator, AssayQCObservation, QCStatus
from glio_noncode.lineage import LineageResolver, SampleLineageRecord
from glio_noncode.models import VariantOrigin
from glio_noncode.origin import OriginClonalityAssessor, OriginObservation


class DataContextTests(unittest.TestCase):
    def test_lineage_resolver_keeps_missing_parent_warning_and_detects_cycles(self) -> None:
        result = LineageResolver().resolve(
            (SampleLineageRecord("tumor-1", ("normal-1",), "tumor", "baseline", "fixture"),)
        )
        self.assertTrue(result.supported)
        self.assertIn("normal-1", result.warnings[0])
        cycle = LineageResolver().resolve(
            (
                SampleLineageRecord("a", ("b",), "tumor", "t1", "fixture"),
                SampleLineageRecord("b", ("a",), "tumor", "t1", "fixture"),
            )
        )
        self.assertFalse(cycle.supported)
        self.assertIn("cycle", cycle.errors[0])

    def test_origin_assessment_preserves_uncertainty_without_normal_sample(self) -> None:
        result = OriginClonalityAssessor().assess(
            (
                OriginObservation(
                    "obs-1",
                    "v1",
                    "tumor-1",
                    "tumor",
                    0.42,
                    None,
                    "baseline",
                    "fixture",
                ),
            )
        )
        self.assertEqual(result.origin, VariantOrigin.UNCERTAIN)
        self.assertIn("normal presence", " ".join(result.warnings))

    def test_assay_qc_distinguishes_pass_watch_fail_and_missing(self) -> None:
        evaluator = AssayQCEvaluator()
        passed = evaluator.evaluate(
            AssayQCObservation("a1", "s1", "atac", 200_000, 0.95, 0.90, 0.01, True, "fixture")
        )
        failed = evaluator.evaluate(
            AssayQCObservation("a2", "s2", "atac", 200_000, 0.50, 0.90, 0.01, True, "fixture")
        )
        missing = evaluator.evaluate(
            AssayQCObservation("a3", "s3", "atac", None, 0.95, 0.90, 0.01, True, "fixture")
        )
        self.assertEqual(passed.status, QCStatus.PASS)
        self.assertEqual(failed.status, QCStatus.FAIL)
        self.assertEqual(missing.status, QCStatus.ABSTAINED)


if __name__ == "__main__":
    unittest.main()
