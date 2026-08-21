from __future__ import annotations

import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.specimen_lineage_runtime import (
    SpecimenLineagePipelineRequest,
    SpecimenLineagePipelineState,
    run_specimen_lineage_pipeline,
    specimen_lineage_pipeline_request_from_file,
)

ACCEPTED = Path("examples/specimen-lineage-pipeline-accepted.json")
REVIEW = Path("examples/specimen-lineage-pipeline-review.json")


class SpecimenLineageRuntimeTests(unittest.TestCase):
    def test_accepted_pipeline_publishes_four_stages(self) -> None:
        request = specimen_lineage_pipeline_request_from_file(ACCEPTED)
        report = run_specimen_lineage_pipeline(request)
        self.assertEqual(report.state, SpecimenLineagePipelineState.ACCEPTED)
        self.assertTrue(report.published)
        self.assertEqual(len(report.stage_receipts), 4)
        self.assertEqual(
            [receipt.state.value for receipt in report.stage_receipts],
            ["accepted", "accepted", "accepted", "accepted"],
        )

    def test_review_pipeline_does_not_publish(self) -> None:
        request = specimen_lineage_pipeline_request_from_file(REVIEW)
        report = run_specimen_lineage_pipeline(request)
        self.assertEqual(report.state, SpecimenLineagePipelineState.REVIEW)
        self.assertFalse(report.published)
        self.assertTrue(any(receipt.review_count for receipt in report.stage_receipts))

    def test_stage_counts_are_conserved(self) -> None:
        report = run_specimen_lineage_pipeline(
            specimen_lineage_pipeline_request_from_file(ACCEPTED)
        )
        for receipt in report.stage_receipts:
            self.assertEqual(
                receipt.input_count,
                receipt.accepted_count + receipt.review_count + receipt.blocked_count,
            )

    def test_stage_order_is_fixed(self) -> None:
        report = run_specimen_lineage_pipeline(
            specimen_lineage_pipeline_request_from_file(ACCEPTED)
        )
        self.assertEqual(
            [receipt.stage.value for receipt in report.stage_receipts],
            ["region_lineage", "longitudinal_linking", "phase_mapping", "treatment_context"],
        )

    def test_manifest_excludes_raw_records_and_has_address(self) -> None:
        report = run_specimen_lineage_pipeline(
            specimen_lineage_pipeline_request_from_file(ACCEPTED)
        )
        self.assertNotIn("records", report.manifest)
        self.assertNotIn("specimens", report.manifest)
        self.assertTrue(report.content_address.startswith("sha256:"))
        self.assertTrue(all("result_address" in stage for stage in report.manifest["stages"]))

    def test_runtime_is_deterministic(self) -> None:
        request = specimen_lineage_pipeline_request_from_file(ACCEPTED)
        first = run_specimen_lineage_pipeline(request)
        second = run_specimen_lineage_pipeline(request)
        self.assertEqual(first.content_address, second.content_address)

    def test_request_requires_all_four_operations(self) -> None:
        with self.assertRaises(ValidationError):
            SpecimenLineagePipelineRequest(
                pipeline_id="invalid",
                context_key="context",
                source_ids=("source",),
                operation_payloads={"region_lineage": {"records": []}},
            )

    def test_request_mapping_preserves_parameters(self) -> None:
        request = specimen_lineage_pipeline_request_from_file(ACCEPTED)
        self.assertEqual(request.pipeline_id, "specimen-lineage-pipeline-accepted-v1")
        self.assertEqual(request.source_ids[0], "gdc-api-available-fields")
        self.assertEqual(
            request.operation_payloads["treatment_context"]["exposures"][0]["exposure_id"],
            "pipeline-exposure",
        )


if __name__ == "__main__":
    unittest.main()
