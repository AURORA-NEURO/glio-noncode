from __future__ import annotations

import unittest

from glio_noncode.cell_context_alpha import (
    CellContextAlphaState,
    CoreMarginTerritoryPrior,
    RecurrenceStatePrior,
    SpatialNichePrior,
    TreatmentInducedStatePrior,
)

CONTEXT = "GRCh38|glioma|adult|stem_like|tumor|unknown"


class CellContextAlphaTests(unittest.TestCase):
    def test_spatial_niche_prior_ranks_candidates_and_preserves_close_margin(self) -> None:
        result = SpatialNichePrior().estimate(
            [
                {
                    "subject_id": "case-1",
                    "niche_id": "perivascular",
                    "support": 0.8,
                    "sample_id": "s1",
                    "context_key": CONTEXT,
                },
                {
                    "subject_id": "case-1",
                    "niche_id": "perivascular",
                    "support": 0.7,
                    "sample_id": "s2",
                    "context_key": CONTEXT,
                },
                {
                    "subject_id": "case-1",
                    "niche_id": "hypoxic",
                    "support": 0.7,
                    "sample_id": "s1",
                    "context_key": CONTEXT,
                },
            ],
            context_key=CONTEXT,
            ambiguity_margin=0.1,
        )
        self.assertEqual(result.state, CellContextAlphaState.AMBIGUOUS)
        self.assertEqual(result.results[0].niche_id, "perivascular")
        self.assertEqual(result.results[0].rank, 1)
        self.assertAlmostEqual(result.results[0].median_support, 0.75)
        self.assertAlmostEqual(result.results[0].score_margin_to_next, 0.05)
        self.assertEqual(result.results[0].sample_ids, ("s1", "s2"))

    def test_spatial_niche_prior_rejects_context_transport(self) -> None:
        result = SpatialNichePrior().estimate(
            [
                {
                    "subject_id": "case-1",
                    "niche_id": "perivascular",
                    "support": 0.8,
                    "context_key": "GRCh38|glioma|pediatric|stem_like|tumor|unknown",
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(result.state, CellContextAlphaState.OUT_OF_DOMAIN)
        self.assertEqual(result.results, ())

    def test_core_margin_prior_resolves_supported_core_territory(self) -> None:
        result = CoreMarginTerritoryPrior().estimate(
            [
                {
                    "subject_id": "case-1",
                    "observation_id": "territory-1",
                    "core_score": 0.8,
                    "margin_score": 0.2,
                    "context_key": CONTEXT,
                }
            ],
            context_key=CONTEXT,
        )
        territory = result.results[0]
        self.assertEqual(result.state, CellContextAlphaState.SUPPORTED)
        self.assertEqual(territory.territory_label, "core")
        self.assertAlmostEqual(territory.core_margin_delta, 0.6)

    def test_core_margin_prior_marks_near_tie_ambiguous(self) -> None:
        result = CoreMarginTerritoryPrior().estimate(
            [
                {
                    "subject_id": "case-1",
                    "core_score": 0.55,
                    "margin_score": 0.5,
                    "context_key": CONTEXT,
                }
            ],
            context_key=CONTEXT,
            ambiguity_tolerance=0.1,
        )
        self.assertEqual(result.state, CellContextAlphaState.AMBIGUOUS)
        self.assertEqual(result.results[0].territory_label, "mixed")

    def test_recurrence_prior_keeps_phase_candidates_ranked(self) -> None:
        result = RecurrenceStatePrior().estimate(
            [
                {
                    "subject_id": "case-1",
                    "phase": "primary",
                    "support": 0.8,
                    "context_key": CONTEXT,
                },
                {
                    "subject_id": "case-1",
                    "phase": "primary",
                    "support": 0.82,
                    "context_key": CONTEXT,
                },
                {
                    "subject_id": "case-1",
                    "phase": "recurrence",
                    "support": 0.4,
                    "context_key": CONTEXT,
                },
                {
                    "subject_id": "case-1",
                    "phase": "recurrence",
                    "support": 0.42,
                    "context_key": CONTEXT,
                },
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(result.state, CellContextAlphaState.SUPPORTED)
        self.assertEqual(result.results[0].phase, "primary")
        self.assertEqual(result.results[0].rank, 1)
        self.assertEqual(result.results[1].phase, "recurrence")
        self.assertAlmostEqual(result.results[0].phase_margin_to_next, 0.4)

    def test_treatment_induced_prior_reports_support_delta(self) -> None:
        result = TreatmentInducedStatePrior().estimate(
            [
                {
                    "subject_id": "case-1",
                    "treatment_id": "tmz",
                    "state_id": "mesenchymal",
                    "baseline_support": 0.2,
                    "post_treatment_support": 0.75,
                    "treatment_phase": "post_treatment",
                    "context_key": CONTEXT,
                }
            ],
            context_key=CONTEXT,
            induction_threshold=0.1,
        )
        state = result.results[0]
        self.assertEqual(result.state, CellContextAlphaState.SUPPORTED)
        self.assertEqual(state.induction_label, "induced")
        self.assertAlmostEqual(state.support_delta, 0.55)
        self.assertEqual(state.treatment_phase, "post_treatment")

    def test_treatment_induced_prior_missing_baseline_is_partial(self) -> None:
        result = TreatmentInducedStatePrior().estimate(
            [
                {
                    "subject_id": "case-1",
                    "treatment_id": "tmz",
                    "state_id": "cycling",
                    "post_treatment_support": 0.6,
                    "context_key": CONTEXT,
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(result.state, CellContextAlphaState.PARTIAL)
        self.assertEqual(result.results, ())


if __name__ == "__main__":
    unittest.main()
