from __future__ import annotations

import unittest
from pathlib import Path

from glio_noncode.reference_coordinate_bundle import ReferenceCoordinateBundleFormat
from glio_noncode.reference_coordinate_runtime import (
    ReferenceCoordinatePipelineRequest,
    run_reference_coordinate_pipeline,
)

ACCEPTED = Path(__file__).parents[1] / "examples" / "reference-coordinate-pipeline-accepted.json"
REVIEW = Path(__file__).parents[1] / "examples" / "reference-coordinate-pipeline-review.json"


class ReferenceCoordinateRuntimeTests(unittest.TestCase):
    def test_accepted_pipeline_publishes_five_stages(self) -> None:
        request = ReferenceCoordinatePipelineRequest.from_file(ACCEPTED)
        report = run_reference_coordinate_pipeline(request)
        self.assertEqual(report.state, "published")
        self.assertTrue(report.published)
        self.assertTrue(report.passed)
        self.assertEqual(len(report.stages), 5)
        self.assertEqual(report.failed_stage_ids, ())
        self.assertEqual(report.output_summary["bundle_entry_count"], 4)

    def test_review_context_does_not_publish(self) -> None:
        request = ReferenceCoordinatePipelineRequest.from_file(REVIEW)
        report = run_reference_coordinate_pipeline(request)
        self.assertEqual(report.state, "review")
        self.assertFalse(report.published)
        self.assertFalse(report.output_summary["request_context_matches"])

    def test_request_resolves_fixture_relative_to_request_file(self) -> None:
        request = ReferenceCoordinatePipelineRequest.from_file(ACCEPTED)
        self.assertTrue(Path(request.fixture_path).is_absolute())
        self.assertTrue(Path(request.fixture_path).exists())

    def test_stage_counts_are_conserved_for_accepted_path(self) -> None:
        report = run_reference_coordinate_pipeline(
            ReferenceCoordinatePipelineRequest.from_file(ACCEPTED)
        )
        for stage in report.stages[:4]:
            self.assertEqual(stage.input_count, stage.output_count)
        self.assertEqual(report.stages[-1].input_count, 16)
        self.assertEqual(report.stages[-1].output_count, 4)

    def test_runtime_is_deterministic(self) -> None:
        request = ReferenceCoordinatePipelineRequest.from_file(ACCEPTED)
        first = run_reference_coordinate_pipeline(request)
        second = run_reference_coordinate_pipeline(request)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_csv_request_retains_requested_output_format(self) -> None:
        request = ReferenceCoordinatePipelineRequest(
            fixture_path=str(ACCEPTED.parent / "reference-coordinate-public-aggregate.json"),
            context_key="GRCh38|diffuse_glioma|adult|bulk_tumor|reference_plane|baseline",
            accepted_only=True,
            output_format=ReferenceCoordinateBundleFormat.CSV,
        )
        report = run_reference_coordinate_pipeline(request)
        self.assertEqual(report.output_summary["bundle_format"], "csv")
        self.assertTrue(report.published)


if __name__ == "__main__":
    unittest.main()
