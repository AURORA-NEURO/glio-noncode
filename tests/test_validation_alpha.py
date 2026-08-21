from __future__ import annotations

import unittest

from glio_noncode.validation_alpha import (
    ControlsRandomizationPlanner,
    ControlType,
    GuideOligoDesignAdapter,
    ModelSystemEligibilityMatcher,
    OligoType,
    PowerReplicationEstimator,
    ValidationAlphaState,
)

CONTEXT = "GRCh38|glioma|adult|stem_like|core|unknown"
OTHER_CONTEXT = "GRCh38|glioma|adult|differentiated|core|unknown"


class ValidationAlphaTests(unittest.TestCase):
    def test_model_system_eligibility_requires_declared_context_and_strength(self) -> None:
        report = ModelSystemEligibilityMatcher().match(
            [
                {
                    "observation_id": "elig-1",
                    "target_id": "target-1",
                    "model_system": "organoid",
                    "context_key": CONTEXT,
                    "supported_contexts": [CONTEXT],
                    "cell_state": "stem_like",
                    "evidence_strength": 0.9,
                    "eligible": True,
                    "source_id": "model-review",
                    "source_version": "v2",
                }
            ],
            context_key=CONTEXT,
            model_system="organoid",
        )
        self.assertEqual(report.state, ValidationAlphaState.READY_FOR_REVIEW)
        self.assertEqual(report.results[0].state, ValidationAlphaState.ELIGIBLE)
        self.assertTrue(report.results[0].eligible)
        blocked = ModelSystemEligibilityMatcher().match(
            [
                {
                    "observation_id": "elig-2",
                    "target_id": "target-2",
                    "model_system": "organoid",
                    "context_key": CONTEXT,
                    "supported_contexts": [OTHER_CONTEXT],
                    "cell_state": "stem_like",
                    "evidence_strength": 0.4,
                    "eligible": True,
                    "source_id": "model-review",
                }
            ],
            context_key=CONTEXT,
            model_system="organoid",
        )
        self.assertEqual(blocked.state, ValidationAlphaState.BLOCKED)
        self.assertIn("context_not_declared_supported", blocked.results[0].blockers)

    def test_guide_oligo_adapter_preserves_valid_rows_and_quarantines_bad_sequence(self) -> None:
        source = (
            "observation_id\tdesign_id\ttarget_id\toligo_id\toligo_type\tsequence\tcontext_key\n"
            f"obs-1\tdesign-1\ttarget-1\tguide-1\tguide\tACGTN\t{CONTEXT}\n"
            f"obs-2\tdesign-1\ttarget-1\tguide-2\tguide\tXYZ\t{CONTEXT}\n"
        )
        batch = GuideOligoDesignAdapter().parse_text(
            source,
            source_id="guide-design",
            source_version="v1",
            input_format="tsv",
        )
        self.assertEqual(len(batch.observations), 1)
        self.assertEqual(batch.observations[0].oligo_type, OligoType.GUIDE)
        self.assertEqual(batch.observations[0].sequence, "ACGTN")
        self.assertEqual(batch.observations[0].source_version, "v1")
        self.assertEqual(len(batch.issues), 1)
        self.assertEqual(batch.issues[0].code, "invalid_guide_oligo_row")

    def test_controls_randomization_is_deterministic_and_context_gated(self) -> None:
        targets = [
            {
                "target_id": "target-1",
                "context_key": CONTEXT,
                "condition": "reporter",
                "source_id": "target-source",
            }
        ]
        planner = ControlsRandomizationPlanner()
        first = planner.plan(
            targets,
            context_key=CONTEXT,
            plan_id="plan-1",
            control_types=(ControlType.NEGATIVE, ControlType.NON_TARGETING),
            biological_replicates=2,
            technical_replicates=1,
            randomization_seed="fixed-seed",
        )
        second = planner.plan(
            targets,
            context_key=CONTEXT,
            plan_id="plan-1",
            control_types=(ControlType.NEGATIVE, ControlType.NON_TARGETING),
            biological_replicates=2,
            technical_replicates=1,
            randomization_seed="fixed-seed",
        )
        self.assertEqual(first.state, ValidationAlphaState.READY_FOR_REVIEW)
        self.assertEqual(len(first.assignments), 4)
        self.assertEqual(first.assignments, second.assignments)
        mismatch = planner.plan(
            [{"target_id": "target-1", "context_key": OTHER_CONTEXT}],
            context_key=CONTEXT,
        )
        self.assertEqual(mismatch.state, ValidationAlphaState.BLOCKED)
        self.assertIn("target-1:context_mismatch", mismatch.blockers)

    def test_power_estimator_reports_requirement_and_shortfall(self) -> None:
        report = PowerReplicationEstimator().estimate(
            [
                {
                    "observation_id": "power-1",
                    "design_id": "design-1",
                    "assay_id": "assay-1",
                    "effect_size": 0.5,
                    "variance": 0.25,
                    "alpha": 0.05,
                    "target_power": 0.8,
                    "planned_replicates": 50,
                    "context_key": CONTEXT,
                    "source_id": "power-source",
                }
            ],
            context_key=CONTEXT,
        )
        result = report.results[0]
        self.assertEqual(report.state, ValidationAlphaState.READY_FOR_REVIEW)
        self.assertGreater(result.required_replicates, 0)
        self.assertGreaterEqual(result.achieved_power, 0.0)
        self.assertLessEqual(result.achieved_power, 1.0)
        self.assertEqual(result.replicate_shortfall, 0)
        mismatch = PowerReplicationEstimator().estimate(
            [
                {
                    "observation_id": "power-2",
                    "design_id": "design-1",
                    "assay_id": "assay-1",
                    "effect_size": 0.5,
                    "variance": 0.25,
                    "planned_replicates": 5,
                    "context_key": OTHER_CONTEXT,
                    "source_id": "power-source",
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(mismatch.state, ValidationAlphaState.OUT_OF_DOMAIN)


if __name__ == "__main__":
    unittest.main()
