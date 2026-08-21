from __future__ import annotations

import unittest

from glio_noncode.specimen_context import (
    ContaminationSwapDetector,
    MatchedNormalResolver,
    PurityPloidyImporter,
    SampleFingerprint,
    SampleIntegrityState,
    SpecimenEvidenceState,
    SpecimenObservation,
    SpecimenOntologyMapper,
)


def _observation(
    observation_id: str,
    sample_id: str,
    relationship: str,
    subject_id: str | None,
    *,
    timepoint: str = "baseline",
) -> SpecimenObservation:
    return SpecimenObservation(
        observation_id=observation_id,
        sample_id=sample_id,
        specimen_id=f"specimen-{sample_id}",
        subject_id=subject_id,
        relationship=relationship,
        specimen_type="tissue",
        timepoint=timepoint,
        source_id="fixture-specimen",
        raw_hash=f"sha256:{observation_id}",
    )


class SpecimenContextTests(unittest.TestCase):
    def test_ontology_mapper_exposes_conflicting_subjects(self) -> None:
        result = SpecimenOntologyMapper().map(
            (
                _observation("o1", "tumor-1", "tumor", "subject-1"),
                _observation("o2", "tumor-1", "tumor", "subject-2"),
                _observation("o3", "normal-1", "normal", None),
            )
        )
        mapping = next(item for item in result.mappings if item.sample_id == "tumor-1")
        self.assertEqual(mapping.state, SpecimenEvidenceState.AMBIGUOUS)
        self.assertEqual(mapping.subject_ids, ("subject-1", "subject-2"))
        normal_mapping = next(item for item in result.mappings if item.sample_id == "normal-1")
        self.assertEqual(normal_mapping.state, SpecimenEvidenceState.PARTIAL)

    def test_matched_normal_requires_same_subject_and_keeps_ambiguity(self) -> None:
        result = MatchedNormalResolver().resolve(
            (
                _observation("t1", "tumor-1", "tumor", "subject-1"),
                _observation("n1", "normal-1", "normal", "subject-1"),
                _observation("n2", "normal-2", "normal", "subject-1"),
                _observation("t2", "tumor-2", "tumor", None),
            )
        )
        by_sample = {pair.tumor_sample_id: pair for pair in result.pairs}
        self.assertEqual(by_sample["tumor-1"].state, SpecimenEvidenceState.AMBIGUOUS)
        self.assertEqual(by_sample["tumor-2"].state, SpecimenEvidenceState.ABSTAINED)

    def test_purity_ploidy_importer_preserves_percent_and_quarantine(self) -> None:
        text = (
            "sample_id\tcaller_id\tversion\tpurity\tploidy\n"
            "tumor-1\tcaller-a\t1.0\t70\t2.4\n"
            "tumor-2\tcaller-a\t1.0\tbad\t2.0\n"
        )
        result = PurityPloidyImporter().parse_text(text, source_id="purity-fixture")
        self.assertEqual(len(result.records), 1)
        self.assertAlmostEqual(result.records[0].purity, 0.70)
        self.assertEqual(result.records[0].ploidy, 2.4)
        self.assertEqual(len(result.issues), 1)

    def test_contamination_and_swap_detector_flags_only_declared_conflicts(self) -> None:
        detector = ContaminationSwapDetector()
        assessments = detector.assess(
            (
                SampleFingerprint(
                    "clear",
                    "subject-1",
                    "subject-1",
                    0.01,
                    0.01,
                    1000,
                    "fingerprint-fixture",
                    "sha256:clear",
                ),
                SampleFingerprint(
                    "swap",
                    "subject-1",
                    "subject-2",
                    0.0,
                    0.0,
                    1000,
                    "fingerprint-fixture",
                    "sha256:swap",
                ),
                SampleFingerprint(
                    "incomplete",
                    "subject-1",
                    None,
                    None,
                    None,
                    None,
                    "fingerprint-fixture",
                    "sha256:incomplete",
                ),
            )
        )
        states = {assessment.sample_id: assessment.state for assessment in assessments}
        self.assertEqual(states["clear"], SampleIntegrityState.CLEAR)
        self.assertEqual(states["swap"], SampleIntegrityState.FLAGGED)
        self.assertEqual(states["incomplete"], SampleIntegrityState.ABSTAINED)


if __name__ == "__main__":
    unittest.main()
