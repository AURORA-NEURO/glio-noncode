from __future__ import annotations

import unittest

from glio_noncode.cohort_alpha import (
    ClonalityLabel,
    ClonalityTimingIntegrator,
    CohortAlphaState,
    CrossCohortReplicationEngine,
    PrimaryRecurrenceComparator,
    SelectionLabel,
    TimingLabel,
    TreatmentSelectionSignalDetector,
)

CONTEXT = "GRCh38|glioma|adult|stem_like|core|unknown"
OTHER_CONTEXT = "GRCh38|glioma|adult|differentiated|core|unknown"


class CohortAlphaTests(unittest.TestCase):
    def test_clonality_integrator_retains_ccf_and_sample_timing(self) -> None:
        report = ClonalityTimingIntegrator().integrate(
            [
                {
                    "observation_id": "c-1",
                    "variant_id": "v1",
                    "sample_id": "sample-primary",
                    "cancer_cell_fraction": 0.9,
                    "timepoint": 1,
                    "phase": "primary",
                    "context_key": CONTEXT,
                    "source_id": "ccf",
                },
                {
                    "observation_id": "c-2",
                    "variant_id": "v1",
                    "sample_id": "sample-recurrence",
                    "cancer_cell_fraction": 0.88,
                    "timepoint": 2,
                    "phase": "recurrence",
                    "context_key": CONTEXT,
                    "source_id": "ccf",
                },
            ],
            context_key=CONTEXT,
        )
        result = report.results[0]
        self.assertEqual(report.state, CohortAlphaState.SUPPORTED)
        self.assertEqual(result.clonality_label, ClonalityLabel.CLONAL)
        self.assertEqual(result.timing_label, TimingLabel.EARLY)
        self.assertEqual(result.ordered_sample_ids, ("sample-primary", "sample-recurrence"))
        self.assertAlmostEqual(result.median_cancer_cell_fraction or 0.0, 0.89)

    def test_clonality_integrator_marks_missing_ccf_partial(self) -> None:
        report = ClonalityTimingIntegrator().integrate(
            [
                {
                    "observation_id": "c-1",
                    "variant_id": "v1",
                    "sample_id": "sample-1",
                    "phase": "primary",
                    "context_key": CONTEXT,
                    "source_id": "ccf",
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(report.state, CohortAlphaState.PARTIAL)
        self.assertEqual(report.results[0].clonality_label, ClonalityLabel.UNKNOWN)

    def test_primary_recurrence_comparator_reports_frequency_delta(self) -> None:
        report = PrimaryRecurrenceComparator().compare(
            [
                {
                    "observation_id": "p-1",
                    "variant_id": "v1",
                    "locus_id": "locus-1",
                    "sample_id": "primary-1",
                    "phase": "primary",
                    "frequency": 0.2,
                    "context_key": CONTEXT,
                    "source_id": "cohort-a",
                },
                {
                    "observation_id": "r-1",
                    "variant_id": "v1",
                    "locus_id": "locus-1",
                    "sample_id": "recurrence-1",
                    "phase": "recurrence",
                    "frequency": 0.6,
                    "context_key": CONTEXT,
                    "source_id": "cohort-a",
                },
            ],
            context_key=CONTEXT,
            change_threshold=0.2,
        )
        result = report.results[0]
        self.assertEqual(report.state, CohortAlphaState.SUPPORTED)
        self.assertEqual(result.label, SelectionLabel.ENRICHED)
        self.assertAlmostEqual(result.recurrence_minus_primary or 0.0, 0.4)

    def test_primary_recurrence_comparator_requires_both_phases(self) -> None:
        report = PrimaryRecurrenceComparator().compare(
            [
                {
                    "observation_id": "p-1",
                    "variant_id": "v1",
                    "locus_id": "locus-1",
                    "sample_id": "primary-1",
                    "phase": "primary",
                    "frequency": 0.2,
                    "context_key": CONTEXT,
                    "source_id": "cohort-a",
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(report.state, CohortAlphaState.PARTIAL)
        self.assertEqual(report.results[0].label, SelectionLabel.UNKNOWN)

    def test_treatment_selection_detector_reports_pre_post_signal(self) -> None:
        report = TreatmentSelectionSignalDetector().detect(
            [
                {
                    "observation_id": "pre-1",
                    "variant_id": "v1",
                    "sample_id": "pre",
                    "treatment_id": "drug-a",
                    "selection_phase": "pre_treatment",
                    "frequency": 0.2,
                    "context_key": CONTEXT,
                    "source_id": "longitudinal",
                },
                {
                    "observation_id": "post-1",
                    "variant_id": "v1",
                    "sample_id": "post",
                    "treatment_id": "drug-a",
                    "selection_phase": "post_treatment",
                    "frequency": 0.6,
                    "response_label": "progression",
                    "context_key": CONTEXT,
                    "source_id": "longitudinal",
                },
            ],
            context_key=CONTEXT,
            change_threshold=0.2,
        )
        result = report.results[0]
        self.assertEqual(report.state, CohortAlphaState.SUPPORTED)
        self.assertEqual(result.selection_label, SelectionLabel.ENRICHED)
        self.assertEqual(result.response_labels, ("progression",))

    def test_treatment_selection_detector_does_not_transport_context(self) -> None:
        report = TreatmentSelectionSignalDetector().detect(
            [
                {
                    "observation_id": "post-1",
                    "variant_id": "v1",
                    "sample_id": "post",
                    "treatment_id": "drug-a",
                    "selection_phase": "post_treatment",
                    "frequency": 0.6,
                    "context_key": OTHER_CONTEXT,
                    "source_id": "longitudinal",
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(report.state, CohortAlphaState.OUT_OF_DOMAIN)
        self.assertEqual(report.results, ())

    def test_cross_cohort_replication_requires_concordant_cohorts(self) -> None:
        report = CrossCohortReplicationEngine().replicate(
            [
                {
                    "observation_id": "a-1",
                    "feature_id": "v1",
                    "cohort_id": "cohort-a",
                    "effect": 0.4,
                    "support": 0.8,
                    "sample_count": 10,
                    "context_key": CONTEXT,
                    "source_id": "study-a",
                },
                {
                    "observation_id": "b-1",
                    "feature_id": "v1",
                    "cohort_id": "cohort-b",
                    "effect": 0.3,
                    "support": 0.7,
                    "sample_count": 12,
                    "context_key": CONTEXT,
                    "source_id": "study-b",
                },
            ],
            context_key=CONTEXT,
            minimum_cohorts=2,
        )
        result = report.results[0]
        self.assertEqual(report.state, CohortAlphaState.SUPPORTED)
        self.assertTrue(result.replicated)
        self.assertEqual(result.direction_concordance, 1.0)
        self.assertEqual(result.sample_counts["cohort-b"], 12)

    def test_cross_cohort_replication_surfaces_direction_disagreement(self) -> None:
        report = CrossCohortReplicationEngine().replicate(
            [
                {
                    "observation_id": "a-1",
                    "feature_id": "v1",
                    "cohort_id": "cohort-a",
                    "effect": 0.4,
                    "support": 0.8,
                    "sample_count": 10,
                    "context_key": CONTEXT,
                    "source_id": "study-a",
                },
                {
                    "observation_id": "b-1",
                    "feature_id": "v1",
                    "cohort_id": "cohort-b",
                    "effect": -0.3,
                    "support": 0.7,
                    "sample_count": 12,
                    "context_key": CONTEXT,
                    "source_id": "study-b",
                },
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(report.state, CohortAlphaState.AMBIGUOUS)
        self.assertFalse(report.results[0].replicated)
        self.assertEqual(report.results[0].positive_cohort_ids, ("cohort-a",))
        self.assertEqual(report.results[0].negative_cohort_ids, ("cohort-b",))


if __name__ == "__main__":
    unittest.main()
