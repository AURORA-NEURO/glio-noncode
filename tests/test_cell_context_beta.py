from __future__ import annotations

import unittest

from glio_noncode.cell_context_beta import (
    CellContextBetaState,
    ContextPriorObservation,
    ContextPriorObservationParser,
    DevelopmentalLineagePrior,
    GlioblastomaMalignantStatePrior,
    H3K27AlteredDevelopmentalStatePrior,
    IdhMutantLineageStatePrior,
    PriorObservationState,
)
from glio_noncode.models import ReferenceContext

CONTEXT = ReferenceContext("GRCh38", "glioma", "adult", "stem_like", territory="core")
GBM_CONTEXT = ReferenceContext("GRCh38", "glioblastoma", "adult", "stem_like", territory="core")
IDH_CONTEXT = ReferenceContext("GRCh38", "glioma", "adult", "proneural", territory="core")


class CellContextBetaTests(unittest.TestCase):
    def _observation(
        self,
        observation_id: str,
        candidate_id: str,
        support: float,
        *,
        context_key: str = CONTEXT.key,
        subject_id: str = "case-1",
        uncertainty: float = 0.1,
        state: PriorObservationState = PriorObservationState.SUPPORTED,
    ) -> ContextPriorObservation:
        return ContextPriorObservation(
            observation_id=observation_id,
            subject_id=subject_id,
            candidate_id=candidate_id,
            candidate_label=candidate_id.replace("_", " "),
            context_key=context_key,
            support=support,
            uncertainty=uncertainty,
            source_id="lineage-atlas",
            source_version="v1",
            raw_hash=f"raw-{observation_id}",
            state=state,
            evidence_tier="reference-atlas",
        )

    def test_parser_retains_versioned_prior_observations_and_quarantine(self) -> None:
        text = (
            "observation_id\tcandidate_id\tcandidate_label\tcontext_key\tsupport\tuncertainty\n"
            f"obs-1\tradial_glia_like\tradial glia-like\t{CONTEXT.key}\t0.9\t0.1\n"
            f"obs-2\tbad\tbad\t{CONTEXT.key}\ttoo-high\t0.1\n"
        )
        batch = ContextPriorObservationParser().parse_text(
            text,
            source_id="lineage-atlas",
            source_version="v1",
        )
        self.assertEqual(len(batch.observations), 1)
        self.assertEqual(batch.observations[0].candidate_id, "radial_glia_like")
        self.assertEqual(batch.observations[0].source_version, "v1")
        self.assertEqual(batch.issues[0].code, "invalid_context_prior_row")

    def test_developmental_lineage_prior_selects_one_candidate_with_bounded_support(self) -> None:
        result = DevelopmentalLineagePrior().estimate(
            CONTEXT,
            (
                self._observation("obs-1", "radial_glia_like", 0.9),
                self._observation("obs-2", "radial_glia_like", 0.8),
                self._observation("obs-3", "oligodendrocyte_lineage", 0.3),
            ),
            subject_id="case-1",
            model_version="v1",
        )
        self.assertEqual(result.state, CellContextBetaState.SUPPORTED)
        self.assertEqual(result.selected_candidate_id, "radial_glia_like")
        self.assertLessEqual(result.candidates[0].support_score, 1.0)
        self.assertIn("not calibrated probabilities", " ".join(result.warnings))

    def test_lineage_prior_preserves_ambiguity_and_context_mismatch(self) -> None:
        ambiguous = DevelopmentalLineagePrior().estimate(
            CONTEXT,
            (
                self._observation("obs-1", "radial_glia_like", 0.8),
                self._observation("obs-2", "oligodendrocyte_lineage", 0.78),
            ),
            subject_id="case-1",
            model_version="v1",
            ambiguity_margin=0.15,
        )
        self.assertEqual(ambiguous.state, CellContextBetaState.AMBIGUOUS)
        self.assertIsNone(ambiguous.selected_candidate_id)

        out_of_domain = DevelopmentalLineagePrior().estimate(
            CONTEXT,
            (self._observation("obs-other", "radial_glia_like", 0.9, context_key=GBM_CONTEXT.key),),
            subject_id="case-1",
            model_version="v1",
        )
        self.assertEqual(out_of_domain.state, CellContextBetaState.OUT_OF_DOMAIN)

    def test_glioblastoma_prior_has_explicit_disease_gate(self) -> None:
        supported = GlioblastomaMalignantStatePrior().estimate(
            GBM_CONTEXT,
            (self._observation("obs-gbm", "stem_like", 0.9, context_key=GBM_CONTEXT.key),),
            subject_id="case-1",
            model_version="v1",
        )
        self.assertEqual(supported.state, CellContextBetaState.SUPPORTED)
        generic = GlioblastomaMalignantStatePrior().estimate(
            CONTEXT,
            (self._observation("obs-generic", "stem_like", 0.9),),
            subject_id="case-1",
            model_version="v1",
        )
        self.assertEqual(generic.state, CellContextBetaState.OUT_OF_DOMAIN)
        self.assertFalse(generic.applicable)

    def test_idh_and_h3k27_models_require_declared_molecular_state(self) -> None:
        idh = IdhMutantLineageStatePrior().estimate(
            IDH_CONTEXT,
            (self._observation("obs-idh", "proneural", 0.85, context_key=IDH_CONTEXT.key),),
            declared_molecular_state="IDH-mutant",
            subject_id="case-1",
            model_version="v1",
        )
        self.assertEqual(idh.state, CellContextBetaState.SUPPORTED)
        self.assertEqual(idh.selected_candidate_id, "proneural")
        wildtype = IdhMutantLineageStatePrior().estimate(
            IDH_CONTEXT,
            (self._observation("obs-wt", "proneural", 0.85, context_key=IDH_CONTEXT.key),),
            declared_molecular_state="IDH-wildtype",
            subject_id="case-1",
            model_version="v1",
        )
        self.assertEqual(wildtype.state, CellContextBetaState.OUT_OF_DOMAIN)

        h3_context = ReferenceContext(
            "GRCh38", "glioma", "pediatric", "stem_like", territory="midline"
        )
        h3 = H3K27AlteredDevelopmentalStatePrior().estimate(
            h3_context,
            (
                self._observation(
                    "obs-h3", "midline_glial_progenitor", 0.9, context_key=h3_context.key
                ),
            ),
            declared_molecular_state="H3K27-altered",
            subject_id="case-1",
            model_version="v1",
        )
        self.assertEqual(h3.state, CellContextBetaState.SUPPORTED)

    def test_contradictory_evidence_is_not_collapsed_into_a_selected_prior(self) -> None:
        result = DevelopmentalLineagePrior().estimate(
            CONTEXT,
            (
                self._observation("obs-support", "radial_glia_like", 0.9),
                self._observation(
                    "obs-conflict",
                    "radial_glia_like",
                    0.9,
                    state=PriorObservationState.CONTRADICTORY,
                ),
            ),
            subject_id="case-1",
            model_version="v1",
        )
        self.assertEqual(result.state, CellContextBetaState.CONTRADICTORY)
        self.assertIsNone(result.selected_candidate_id)


if __name__ == "__main__":
    unittest.main()
