from __future__ import annotations

import copy
import tempfile
import unittest
from dataclasses import replace

from glio_noncode.assessments import (
    RUN_ASSESSMENT_VERSION,
    VerifiedRunAssessment,
    assessment_capabilities,
    build_run_assessment,
)
from glio_noncode.errors import ValidationError
from glio_noncode.runtime import CaseRuntime

from .helpers import fixture_manifest


class VerifiedRunAssessmentTests(unittest.TestCase):
    def test_build_round_trip_and_verify_close_every_derived_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            snapshot = runtime.load_run_snapshot(dossier.run_id)

            assessment = build_run_assessment(
                snapshot,
                audience="public",
                format="markdown",
            )
            reopened = VerifiedRunAssessment.from_dict(assessment.to_dict())

            self.assertEqual(reopened, assessment)
            self.assertTrue(assessment.verify_without_rebuild(snapshot))
            self.assertTrue(assessment.verify(snapshot))
            self.assertEqual(assessment.assessment_version, RUN_ASSESSMENT_VERSION)
            self.assertEqual(assessment.dossier_address, dossier.content_address)
            self.assertEqual(assessment.quality_report.dossier_address, dossier.content_address)
            self.assertEqual(assessment.dossier_report.audience, "public")
            self.assertEqual(assessment.rendered_report.format, "markdown")
            self.assertTrue(assessment.rendered_report.payload.startswith("# Public"))

    def test_tampering_and_a_different_snapshot_fail_closed(self) -> None:
        with (
            tempfile.TemporaryDirectory() as first_directory,
            tempfile.TemporaryDirectory() as second_directory,
        ):
            first_runtime = CaseRuntime(first_directory)
            first = first_runtime.evaluate(fixture_manifest())
            assessment = build_run_assessment(first_runtime.load_run_snapshot(first.run_id))
            raw = copy.deepcopy(assessment.to_dict())
            raw["event_address"] = "sha256:" + "0" * 64
            with self.assertRaisesRegex(ValidationError, "content_address"):
                VerifiedRunAssessment.from_dict(raw)

            second_manifest = replace(fixture_manifest(), case_id="case-assessment-second")
            second_runtime = CaseRuntime(second_directory)
            second = second_runtime.evaluate(second_manifest)
            self.assertFalse(
                assessment.verify_without_rebuild(
                    second_runtime.load_run_snapshot(second.run_id)
                )
            )

    def test_capabilities_are_deterministic_and_defaults_are_public_json(self) -> None:
        first = assessment_capabilities()
        second = assessment_capabilities()
        self.assertEqual(first, second)
        self.assertEqual(first["assessment_version"], RUN_ASSESSMENT_VERSION)
        self.assertEqual((first["default_audience"], first["default_format"]), ("public", "json"))

    def test_nominally_typed_mutated_snapshot_is_revalidated_before_use(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            snapshot = runtime.load_run_snapshot(dossier.run_id)
            assessment = build_run_assessment(snapshot)

            object.__setattr__(snapshot, "event_record", {})

            with self.assertRaisesRegex(ValidationError, "snapshot"):
                build_run_assessment(snapshot)
            self.assertFalse(assessment.verify(snapshot))
            self.assertFalse(assessment.verify_without_rebuild(snapshot))

    def test_verifiers_revalidate_the_assessment_envelope_itself(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            snapshot = runtime.load_run_snapshot(dossier.run_id)
            assessment = build_run_assessment(snapshot)

            object.__setattr__(assessment, "assessment_version", "forged-version")

            self.assertFalse(assessment.verify(snapshot))
            self.assertFalse(assessment.verify_without_rebuild(snapshot))


if __name__ == "__main__":
    unittest.main()
