from __future__ import annotations

import unittest

from glio_noncode.models import (
    AssayType,
    CandidateElement,
    EvidenceState,
    ExperimentOption,
    ReferenceContext,
)
from glio_noncode.uncertainty import UncertaintyPropagator
from glio_noncode.validation_controls import NegativeControlBuilder, ValidationValuePlanner


class ValidationControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = ReferenceContext("GRCh38", "glioma", "adult", "stem_like")
        self.target = CandidateElement(
            "element-target",
            "chr7",
            100,
            120,
            "enhancer",
            self.context,
            "fixture-elements",
            target_genes=("GENE_TARGET",),
            features={"accessibility": 0.80, "conservation": 0.60},
        )

    def test_negative_controls_are_matched_but_remain_unsupported(self) -> None:
        pool = (
            CandidateElement(
                "element-control-a",
                "chr7",
                200,
                220,
                "enhancer",
                self.context,
                "fixture-elements",
                target_genes=("GENE_A",),
                features={"accessibility": 0.78, "conservation": 0.59},
            ),
            CandidateElement(
                "element-control-b",
                "chr7",
                300,
                320,
                "enhancer",
                self.context,
                "fixture-elements",
                target_genes=("GENE_B",),
                features={"accessibility": 0.30, "conservation": 0.20},
            ),
        )
        result = NegativeControlBuilder().build(self.target, pool, limit=2)
        self.assertEqual(len(result.controls), 2)
        self.assertEqual(result.controls[0].element_id, "element-control-a")
        self.assertTrue(
            all(item.expected_state == EvidenceState.UNSUPPORTED for item in result.controls)
        )
        self.assertIn("not a measured negative", result.controls[0].rationale)

    def test_validation_value_planner_ranks_options_and_preserves_band(self) -> None:
        uncertainty = UncertaintyPropagator().summarize(())
        options = (
            ExperimentOption(
                "option-low",
                AssayType.MPRA,
                ("edge-1",),
                0.90,
                0.80,
                "low",
                ("stem_like",),
                ("negative_control",),
                ("reporter_activity",),
                ("requires assay validation",),
            ),
            ExperimentOption(
                "option-high",
                AssayType.CONTACT_ASSAY,
                ("edge-1",),
                0.95,
                0.70,
                "high",
                ("stem_like",),
                ("technical_replicates",),
                ("contact_frequency",),
                ("requires assay validation",),
            ),
        )
        result = ValidationValuePlanner().rank(options, uncertainty, budget_class="medium")
        self.assertEqual(result.priorities[0].option_id, "option-low")
        self.assertEqual(result.uncertainty_band.value, "low")
        self.assertTrue(result.content_address.startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()
