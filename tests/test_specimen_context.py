from __future__ import annotations

import json
import unittest
from dataclasses import replace
from unittest.mock import patch

from glio_noncode.errors import ValidationError
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

    def test_ontology_mapper_exposes_all_conflicting_specimen_context_dimensions(self) -> None:
        base = _observation("o1", "sample-1", "tumor", "subject-1")
        conflicts = (
            (
                "specimen identifier",
                replace(base, observation_id="o2", specimen_id="specimen-other"),
            ),
            ("specimen type", replace(base, observation_id="o2", specimen_type="organoid")),
            ("timepoint", replace(base, observation_id="o2", timepoint="recurrence")),
            ("relationship", replace(base, observation_id="o2", relationship="normal")),
        )
        for label, conflicting_observation in conflicts:
            with self.subTest(label=label):
                result = SpecimenOntologyMapper().map((base, conflicting_observation))
                mapping = result.mappings[0]
                self.assertEqual(mapping.state, SpecimenEvidenceState.AMBIGUOUS)
                self.assertTrue(any(label in reason for reason in mapping.reasons))
                self.assertEqual(mapping.candidate_observation_ids, ("o1", "o2"))

    def test_missing_specimen_identifier_is_not_inferred_from_sample_identifier(self) -> None:
        result = SpecimenOntologyMapper().parse_rows(
            (
                {
                    "sample_id": "sample-1",
                    "subject_id": "subject-1",
                    "relationship": "tumor",
                },
            ),
            source_id="specimen-source",
        )

        mapping = result.mappings[0]
        self.assertEqual(result.observations[0].specimen_id, "unspecified")
        self.assertEqual(mapping.specimen_ids, ())
        self.assertEqual(mapping.state, SpecimenEvidenceState.PARTIAL)
        self.assertIn("specimen identifier", mapping.reasons[0])

    def test_partially_missing_subject_declaration_does_not_become_supported(self) -> None:
        observed = _observation("o1", "sample-1", "tumor", "subject-1")
        missing = replace(observed, observation_id="o2", subject_id=None)

        mapping = SpecimenOntologyMapper().map((observed, missing)).mappings[0]

        self.assertEqual(mapping.state, SpecimenEvidenceState.PARTIAL)
        self.assertIn("subject identifier", mapping.reasons[0])
        self.assertEqual(mapping.subject_ids, ("subject-1",))

    def test_duplicate_observation_ids_are_rejected_before_mapping(self) -> None:
        first = _observation("duplicate", "sample-1", "tumor", "subject-1")
        second = _observation("duplicate", "sample-2", "normal", "subject-1")

        with self.assertRaisesRegex(ValidationError, "observation IDs must be unique"):
            SpecimenOntologyMapper().map((first, second))

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

    def test_matched_normal_deduplicates_repeated_rows_for_one_sample(self) -> None:
        tumor = _observation("t1", "tumor-1", "tumor", "subject-1")
        normal = _observation("n1", "normal-1", "normal", "subject-1")
        repeated_normal = replace(normal, observation_id="n2")

        pair = MatchedNormalResolver().resolve((tumor, normal, repeated_normal)).pairs[0]

        self.assertEqual(pair.state, SpecimenEvidenceState.SUPPORTED)
        self.assertEqual(pair.normal_sample_ids, ("normal-1",))
        self.assertEqual(pair.source_observation_ids, ("n1", "n2", "t1"))

    def test_matched_normal_never_pairs_a_sample_with_itself(self) -> None:
        tumor = _observation("o1", "shared-sample", "tumor", "subject-1")
        conflicting_normal = replace(tumor, observation_id="o2", relationship="normal")

        pair = MatchedNormalResolver().resolve((tumor, conflicting_normal)).pairs[0]

        self.assertEqual(pair.state, SpecimenEvidenceState.AMBIGUOUS)
        self.assertEqual(pair.normal_sample_ids, ())
        self.assertIn("conflicting specimen context", pair.reasons[0])

    def test_matched_normal_propagates_partial_specimen_context(self) -> None:
        tumor = _observation("t1", "tumor-1", "tumor", "subject-1")
        normal = replace(
            _observation("n1", "normal-1", "normal", "subject-1"),
            specimen_id="unspecified",
        )

        pair = MatchedNormalResolver().resolve((tumor, normal)).pairs[0]

        self.assertEqual(pair.state, SpecimenEvidenceState.PARTIAL)
        self.assertEqual(pair.normal_sample_ids, ("normal-1",))

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

    def test_purity_ploidy_quarantines_invalid_values_without_echoing_source_text(self) -> None:
        private_text = "PRIVATE_VALUE_DO_NOT_ECHO"
        result = PurityPloidyImporter().parse_text(
            json.dumps(
                {
                    "records": [
                        {
                            "sample_id": "tumor-1",
                            "purity": private_text,
                            "ploidy": 2.0,
                        }
                    ]
                }
            ),
            source_id="purity-private-value-fixture",
            input_format="json",
        )

        serialized = json.dumps(result.to_dict(), sort_keys=True)
        self.assertEqual(result.records, ())
        self.assertEqual(len(result.issues), 1)
        self.assertEqual(result.issues[0].code, "invalid_purity_ploidy_row")
        self.assertNotIn(private_text, serialized)

    def test_purity_ploidy_rejects_nonfinite_boolean_and_missing_sample_values(self) -> None:
        result = PurityPloidyImporter().parse_text(
            json.dumps(
                {
                    "records": [
                        {"sample_id": "nan", "purity": 0.7, "ploidy": "nan"},
                        {"sample_id": "inf", "purity": 0.7, "ploidy": "inf"},
                        {"sample_id": "bool", "purity": True, "ploidy": 2.0},
                        {"purity": 0.7, "ploidy": 2.0},
                    ]
                }
            ),
            source_id="purity-invalid-numbers-fixture",
            input_format="json",
        )

        self.assertEqual(result.records, ())
        self.assertEqual(len(result.issues), 4)
        self.assertTrue(all(issue.raw_hash for issue in result.issues))

    def test_purity_ploidy_rejects_ambiguous_headers_and_bounds_inputs(self) -> None:
        importer = PurityPloidyImporter()
        with self.assertRaisesRegex(ValidationError, "headers must be nonempty and unique"):
            importer.parse_text(
                "sample_id\tpurity\tPurity\tploidy\n"
                "tumor-1\t0.7\t0.8\t2.0\n",
                source_id="purity-duplicate-header-fixture",
            )
        ragged = importer.parse_text(
            "sample_id\tpurity\tploidy\n"
            "tumor-1\t0.7\t2.0\textra\n",
            source_id="purity-ragged-row-fixture",
        )
        self.assertEqual(ragged.records, ())
        self.assertEqual(len(ragged.issues), 1)
        self.assertEqual(
            ragged.issues[0].message,
            "row field count does not match the TSV header",
        )
        with patch("glio_noncode.specimen_context.MAX_PURITY_PLOIDY_INPUT_BYTES", 8):
            with self.assertRaisesRegex(ValidationError, "size limit"):
                importer.parse_text("123456789", source_id="purity-size-fixture")
        with patch("glio_noncode.specimen_context.MAX_PURITY_PLOIDY_ROWS", 1):
            with self.assertRaisesRegex(ValidationError, "row limit"):
                importer.parse_text(
                    "sample_id\tpurity\tploidy\n"
                    "tumor-1\t0.7\t2.0\n"
                    "tumor-2\t0.8\t2.1\n",
                    source_id="purity-row-limit-fixture",
                )

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
