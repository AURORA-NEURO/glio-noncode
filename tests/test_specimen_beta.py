from __future__ import annotations

import unittest

from glio_noncode.models import VariantOrigin
from glio_noncode.specimen_beta import (
    CancerCellFractionEstimator,
    MosaicismPosteriorEstimator,
    SomaticGermlineOriginClassifier,
    SpecimenBetaState,
    SubcloneAssigner,
)


class SpecimenBetaTests(unittest.TestCase):
    def test_origin_classifier_separates_somatic_and_germline_evidence(self) -> None:
        result = SomaticGermlineOriginClassifier().classify(
            [
                {
                    "variant_id": "v-somatic",
                    "observation_id": "tumor-1",
                    "relationship": "tumor",
                    "tumor_vaf": 0.45,
                    "present_in_normal": False,
                    "normal_alt_reads": 0,
                    "normal_depth": 100,
                },
                {
                    "variant_id": "v-germline",
                    "observation_id": "normal-1",
                    "relationship": "normal",
                    "normal_vaf": 0.45,
                    "present_in_normal": True,
                },
            ]
        )
        by_variant = {item.variant_id: item for item in result.classifications}
        self.assertEqual(result.state, SpecimenBetaState.SUPPORTED)
        self.assertEqual(by_variant["v-somatic"].origin, VariantOrigin.SOMATIC)
        self.assertEqual(by_variant["v-germline"].origin, VariantOrigin.GERMLINE)
        self.assertIn("normal_absence:tumor-1", by_variant["v-somatic"].evidence_channels)

    def test_origin_classifier_retains_conflicting_observations(self) -> None:
        result = SomaticGermlineOriginClassifier().classify(
            [
                {
                    "variant_id": "v-conflict",
                    "observation_id": "tumor-1",
                    "relationship": "tumor",
                    "tumor_vaf": 0.4,
                    "present_in_normal": True,
                    "normal_vaf": 0.3,
                }
            ]
        )
        classification = result.classifications[0]
        self.assertEqual(result.state, SpecimenBetaState.AMBIGUOUS)
        self.assertEqual(classification.origin, VariantOrigin.UNCERTAIN)
        self.assertEqual(classification.conflicting_observation_ids, ("tumor-1",))

    def test_mosaicism_estimator_requires_repeated_low_fraction_tissues(self) -> None:
        result = MosaicismPosteriorEstimator().estimate(
            [
                {
                    "variant_id": "v-mosaic",
                    "observation_id": "skin",
                    "tissue_id": "skin",
                    "relationship": "normal",
                    "vaf": 0.10,
                },
                {
                    "variant_id": "v-mosaic",
                    "observation_id": "blood",
                    "tissue_id": "blood",
                    "relationship": "normal",
                    "vaf": 0.08,
                },
            ]
        )
        estimate = result.estimates[0]
        self.assertEqual(result.state, SpecimenBetaState.SUPPORTED)
        self.assertEqual(estimate.supporting_tissues, ("blood", "skin"))
        self.assertFalse(estimate.calibrated)
        self.assertGreater(estimate.posterior_estimate, 0.5)
        self.assertTrue(any("uncalibrated" in warning for warning in result.warnings))

    def test_mosaicism_estimator_is_partial_for_one_tissue(self) -> None:
        result = MosaicismPosteriorEstimator().estimate(
            [{"variant_id": "v-one", "tissue_id": "blood", "vaf": 0.1}]
        )
        self.assertEqual(result.state, SpecimenBetaState.PARTIAL)
        self.assertEqual(result.estimates[0].supporting_tissues, ("blood",))

    def test_ccf_estimator_uses_purity_and_copy_number_without_silent_clamp(self) -> None:
        result = CancerCellFractionEstimator().estimate(
            [
                {
                    "variant_id": "v-clonal",
                    "sample_id": "tumor-1",
                    "purity": 0.5,
                    "vaf": 0.25,
                    "total_copy_number": 2,
                    "alternate_copy_number": 1,
                    "depth": 100,
                    "alt_reads": 25,
                },
                {
                    "variant_id": "v-out",
                    "sample_id": "tumor-1",
                    "purity": 0.3,
                    "vaf": 0.4,
                    "total_copy_number": 8,
                    "alternate_copy_number": 1,
                },
            ]
        )
        by_variant = {item.variant_id: item for item in result.estimates}
        self.assertEqual(result.state, SpecimenBetaState.PARTIAL)
        self.assertEqual(by_variant["v-clonal"].estimated_ccf, 1.0)
        self.assertGreater(by_variant["v-out"].raw_ccf, 1.0)
        self.assertIsNone(by_variant["v-out"].estimated_ccf)
        self.assertTrue(
            any("not silently clamped" in warning for warning in by_variant["v-out"].warnings)
        )

    def test_ccf_estimator_abstains_when_purity_is_zero(self) -> None:
        result = CancerCellFractionEstimator().estimate(
            [
                {
                    "variant_id": "v-zero",
                    "purity": 0,
                    "vaf": 0.2,
                    "total_copy_number": 2,
                }
            ]
        )
        self.assertEqual(result.state, SpecimenBetaState.PARTIAL)
        self.assertIsNone(result.estimates[0].estimated_ccf)

    def test_subclone_assigner_clusters_relative_ccf_within_sample(self) -> None:
        result = SubcloneAssigner().assign(
            [
                {"sample_id": "tumor-1", "variant_id": "v1", "ccf": 0.80},
                {"sample_id": "tumor-1", "variant_id": "v2", "ccf": 0.74},
                {"sample_id": "tumor-1", "variant_id": "v3", "ccf": 0.35},
            ]
        )
        by_variant = {item.variant_id: item for item in result.assignments}
        self.assertEqual(result.state, SpecimenBetaState.SUPPORTED)
        self.assertEqual(by_variant["v1"].subclone_id, by_variant["v2"].subclone_id)
        self.assertNotEqual(by_variant["v1"].subclone_id, by_variant["v3"].subclone_id)
        self.assertEqual(len(result.cluster_means), 2)

    def test_subclone_assigner_quarantines_invalid_ccf(self) -> None:
        result = SubcloneAssigner().assign(
            [
                {"sample_id": "tumor-1", "variant_id": "v1", "ccf": 0.8},
                {"sample_id": "tumor-1", "variant_id": "v2", "ccf": 1.5},
            ]
        )
        self.assertEqual(result.state, SpecimenBetaState.PARTIAL)
        self.assertEqual(len(result.assignments), 1)
        self.assertEqual(result.issues[0].code, "invalid_subclone_record")
