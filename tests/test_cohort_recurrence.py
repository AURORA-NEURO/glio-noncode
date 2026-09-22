from __future__ import annotations

import unittest
from dataclasses import replace

from glio_noncode.cohort import (
    MAX_COHORT_OBSERVATIONS,
    CohortObservation,
    RecurrenceModel,
)
from glio_noncode.models import ReferenceContext


class CohortRecurrenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = ReferenceContext(
            "GRCh38",
            "diffuse_glioma",
            "adult",
            "stem_like",
            territory="enhancer",
            treatment_phase="pretreatment",
            assay_support=("whole_genome",),
            source_version="cohort-fixture-v1",
        )
        self.rows = self._dataset()

    def _observation(
        self,
        *,
        observation_id: str,
        subject_id: str,
        locus_id: str,
        mutated: bool,
        callable: bool = True,
        score: float = 0.5,
        batch_id: str | None = None,
        context: ReferenceContext | None = None,
        variant_class: str | None = "SNV",
    ) -> CohortObservation:
        subject_index = int(subject_id.rsplit("-", 1)[-1])
        return CohortObservation(
            observation_id=observation_id,
            subject_id=subject_id,
            locus_id=locus_id,
            mutated=mutated,
            callable=callable,
            mutability_score=score + subject_index / 10_000,
            chromatin_score=0.6 + subject_index / 10_000,
            ancestry_group="ancestry-1",
            disease_class="diffuse_glioma",
            context=context or self.context,
            variant_class=variant_class,
            sequence_context="ACA>T",
            molecular_context="IDH-mutant",
            recurrence_phase="primary",
            locus_length=1,
            batch_id=batch_id or f"batch-{subject_index % 2}",
            ascertainment_group=f"ascertainment-{subject_index % 2}",
        )

    def _dataset(self) -> tuple[CohortObservation, ...]:
        rows: list[CohortObservation] = []
        for subject_index in range(9):
            subject_id = f"subject-{subject_index}"
            callable_target = subject_index < 8
            rows.append(
                self._observation(
                    observation_id=f"target-{subject_index}",
                    subject_id=subject_id,
                    locus_id="target-locus",
                    mutated=callable_target and subject_index < 6,
                    callable=callable_target,
                    score=0.5,
                )
            )
        for control_index in range(6):
            for subject_index in range(8):
                rows.append(
                    self._observation(
                        observation_id=f"control-{control_index}-{subject_index}",
                        subject_id=f"subject-{subject_index}",
                        locus_id=f"control-locus-{control_index}",
                        mutated=subject_index < control_index,
                        score=0.48 + control_index / 1_000,
                    )
                )
        return tuple(rows)

    def test_estimate_uses_callable_target_subjects_and_unique_loci(self) -> None:
        result = RecurrenceModel().evaluate(self.rows, "target-locus")

        self.assertEqual(result.status, "estimated")
        self.assertEqual((result.observed_count, result.callable_count), (6, 8))
        self.assertEqual(result.observed_rate, 0.75)
        self.assertEqual(result.expected_rate, 0.3125)
        self.assertEqual(result.matched_control.candidate_count, 6)
        self.assertEqual(result.matched_control.eligible_count, 6)
        self.assertEqual(result.matched_control.effective_sample_size, 6.0)
        self.assertEqual(len(result.matched_control.control_rates), 6)
        self.assertEqual(
            result.to_dict(), RecurrenceModel().evaluate(self.rows, "target-locus").to_dict()
        )
        self.assertNotIn("subject-0", str(result.to_dict()))
        self.assertIsNone(result.to_dict().get("p_value"))
        self.assertIn("not a probability", result.to_dict()["support_interpretation"])

    def test_target_noncallable_mutations_are_rejected_at_ingestion(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-callable"):
            replace(self.rows[0], callable=False, mutated=True)

    def test_only_controls_covering_all_callable_target_subjects_are_eligible(self) -> None:
        rows = tuple(
            row
            for row in self.rows
            if not (row.locus_id == "control-locus-0" and row.subject_id == "subject-7")
        )
        result = RecurrenceModel().evaluate(rows, "target-locus")

        self.assertEqual(result.matched_control.candidate_count, 6)
        self.assertEqual(result.matched_control.eligible_count, 5)
        self.assertEqual(
            dict(result.matched_control.excluded_locus_counts),
            {"incomplete_callable_subject_set": 1},
        )
        self.assertEqual(result.status, "estimated")

    def test_batch_or_ascertainment_mismatch_excludes_control(self) -> None:
        rows = tuple(
            replace(row, batch_id="unmatched-batch")
            if row.locus_id == "control-locus-0" and row.subject_id == "subject-0"
            else row
            for row in self.rows
        )
        result = RecurrenceModel().evaluate(rows, "target-locus")

        self.assertEqual(result.matched_control.eligible_count, 5)
        self.assertEqual(
            dict(result.matched_control.excluded_locus_counts),
            {"batch_or_ascertainment_mismatch": 1},
        )
        self.assertNotIn("control-locus-0", result.matched_control.control_locus_ids)

    def test_missing_required_matching_covariates_abstains(self) -> None:
        rows = tuple(
            replace(row, sequence_context=None) if row.locus_id == "target-locus" else row
            for row in self.rows
        )
        result = RecurrenceModel().evaluate(rows, "target-locus")

        self.assertEqual(result.status, "not_estimable")
        self.assertEqual(result.support, 0.0)
        self.assertEqual(result.uncertainty, 1.0)
        self.assertIn("sequence_context", result.matched_control.unmatched_covariates)
        self.assertIsNone(result.z_like_score)

    def test_fewer_than_minimum_controls_is_not_estimable(self) -> None:
        rows = tuple(
            row
            for row in self.rows
            if not row.locus_id.startswith("control-locus-")
            or int(row.locus_id.rsplit("-", 1)[-1]) < 4
        )
        result = RecurrenceModel().evaluate(rows, "target-locus")

        self.assertEqual(result.matched_control.eligible_count, 4)
        self.assertEqual(result.status, "not_estimable")
        self.assertIsNone(result.enrichment)
        self.assertEqual(result.support, 0.0)

    def test_zero_control_rate_variance_has_no_standardized_score(self) -> None:
        rows = tuple(
            replace(row, mutated=False) if row.locus_id.startswith("control-locus-") else row
            for row in self.rows
        )
        result = RecurrenceModel().evaluate(rows, "target-locus")

        self.assertEqual(result.matched_control.eligible_count, 6)
        self.assertEqual(result.control_rate_sd, 0.0)
        self.assertEqual(result.status, "not_estimable")
        self.assertIsNone(result.z_like_score)
        self.assertIsNone(result.enrichment)

    def test_target_context_cannot_mix_reference_strata(self) -> None:
        other_context = replace(self.context, territory="promoter")
        rows = tuple(
            replace(row, context=other_context)
            if row.locus_id == "target-locus" and row.subject_id == "subject-1"
            else row
            for row in self.rows
        )
        with self.assertRaisesRegex(ValueError, "multiple contexts"):
            RecurrenceModel().evaluate(rows, "target-locus")

    def test_duplicate_subject_locus_and_observation_ids_are_rejected(self) -> None:
        duplicate_pair = replace(self.rows[0], observation_id="target-0-copy")
        with self.assertRaisesRegex(ValueError, "duplicate subject-by-locus"):
            RecurrenceModel().evaluate(self.rows + (duplicate_pair,), "target-locus")
        duplicated_id = replace(self.rows[-1], observation_id=self.rows[0].observation_id)
        with self.assertRaisesRegex(ValueError, "duplicate cohort observation_id"):
            RecurrenceModel().evaluate(self.rows[:-1] + (duplicated_id,), "target-locus")

    def test_observation_limit_is_enforced_before_analysis(self) -> None:
        row = self.rows[0]
        with self.assertRaisesRegex(ValueError, "exceeds"):
            RecurrenceModel().evaluate(
                (row for _ in range(MAX_COHORT_OBSERVATIONS + 1)),
                "target-locus",
            )


if __name__ == "__main__":
    unittest.main()
