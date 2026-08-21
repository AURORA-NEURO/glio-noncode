from __future__ import annotations

import unittest
from pathlib import Path

from glio_noncode.specimen_preanalytic_runtime import (
    SpecimenPreanalyticPipelineRequest,
    run_specimen_preanalytic_pipeline,
)

ACCEPTED = Path("examples/specimen-preanalytic-pipeline-accepted.json")
REVIEW = Path("examples/specimen-preanalytic-pipeline-review.json")


class SpecimenPreanalyticRuntimeTests(unittest.TestCase):
    def test_accepted_pipeline_publishes_four_stages(self) -> None:
        request, catalog = SpecimenPreanalyticPipelineRequest.from_file(ACCEPTED)
        report = run_specimen_preanalytic_pipeline(request, catalog)
        self.assertTrue(report.published)
        self.assertEqual(report.state, "published")
        self.assertEqual(len(report.stage_receipts), 4)
        self.assertEqual(
            {stage.operation for stage in report.stage_receipts},
            {"preanalytic_quality", "assay_lineage", "identity_adjudication", "context_envelope"},
        )

    def test_review_fixture_does_not_publish(self) -> None:
        request, catalog = SpecimenPreanalyticPipelineRequest.from_file(REVIEW)
        report = run_specimen_preanalytic_pipeline(request, catalog)
        self.assertFalse(report.published)
        self.assertEqual(report.state, "review")

    def test_stage_counts_are_conserved(self) -> None:
        request, catalog = SpecimenPreanalyticPipelineRequest.from_file(ACCEPTED)
        report = run_specimen_preanalytic_pipeline(request, catalog)
        self.assertTrue(
            all(stage.input_count == stage.output_count for stage in report.stage_receipts)
        )
        self.assertTrue(
            all(stage.content_address.startswith("sha256:") for stage in report.stage_receipts)
        )

    def test_request_rejects_context_drift(self) -> None:
        request, catalog = SpecimenPreanalyticPipelineRequest.from_file(ACCEPTED)
        drifted = SpecimenPreanalyticPipelineRequest(
            request.request_id,
            request.fixture_path,
            "GRCh38|drift|adult|stem_like|core|untreated",
            request.publish_mode,
        )
        with self.assertRaises(ValueError):
            run_specimen_preanalytic_pipeline(drifted, catalog)

    def test_runtime_is_deterministic(self) -> None:
        request, catalog = SpecimenPreanalyticPipelineRequest.from_file(ACCEPTED)
        first = run_specimen_preanalytic_pipeline(request, catalog)
        second = run_specimen_preanalytic_pipeline(request, catalog)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.manifest_address, second.manifest_address)


if __name__ == "__main__":
    unittest.main()
