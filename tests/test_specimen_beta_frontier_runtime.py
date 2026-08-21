from __future__ import annotations

import unittest
from pathlib import Path

from glio_noncode.specimen_beta_frontier_runtime import (
    SpecimenBetaFrontierPipelineState,
    run_specimen_beta_frontier_pipeline,
    specimen_beta_frontier_pipeline_request_from_file,
)

ACCEPTED = Path("examples/specimen-beta-frontier-pipeline-accepted.json")
REVIEW = Path("examples/specimen-beta-frontier-pipeline-review.json")


class SpecimenBetaFrontierRuntimeTests(unittest.TestCase):
    def test_accepted_pipeline_publishes_four_stages(self) -> None:
        request = specimen_beta_frontier_pipeline_request_from_file(str(ACCEPTED))
        report = run_specimen_beta_frontier_pipeline(request)
        self.assertEqual(report.state, SpecimenBetaFrontierPipelineState.ACCEPTED)
        self.assertTrue(report.published)
        self.assertEqual(len(report.stage_receipts), 4)
        self.assertEqual(
            [receipt.state.value for receipt in report.stage_receipts],
            ["accepted", "accepted", "accepted", "accepted"],
        )

    def test_accepted_pipeline_conserves_stage_counts(self) -> None:
        request = specimen_beta_frontier_pipeline_request_from_file(str(ACCEPTED))
        report = run_specimen_beta_frontier_pipeline(request)
        for receipt in report.stage_receipts:
            self.assertEqual(
                receipt.input_count,
                receipt.accepted_count + receipt.review_count + receipt.blocked_count,
            )

    def test_review_pipeline_keeps_issue_free_review_states(self) -> None:
        request = specimen_beta_frontier_pipeline_request_from_file(str(REVIEW))
        report = run_specimen_beta_frontier_pipeline(request)
        self.assertEqual(report.state, SpecimenBetaFrontierPipelineState.REVIEW)
        self.assertFalse(report.published)
        self.assertTrue(any(receipt.review_count for receipt in report.stage_receipts))

    def test_pipeline_manifest_is_sanitized(self) -> None:
        request = specimen_beta_frontier_pipeline_request_from_file(str(ACCEPTED))
        report = run_specimen_beta_frontier_pipeline(request)
        self.assertNotIn("records", report.manifest)
        self.assertTrue(report.content_address.startswith("sha256:"))

    def test_pipeline_is_deterministic(self) -> None:
        request = specimen_beta_frontier_pipeline_request_from_file(str(ACCEPTED))
        first = run_specimen_beta_frontier_pipeline(request)
        second = run_specimen_beta_frontier_pipeline(request)
        self.assertEqual(first.content_address, second.content_address)

    def test_pipeline_request_requires_all_operations(self) -> None:
        from glio_noncode.errors import ValidationError
        from glio_noncode.specimen_beta_frontier_runtime import SpecimenBetaFrontierPipelineRequest

        with self.assertRaises(ValidationError):
            SpecimenBetaFrontierPipelineRequest(
                pipeline_id="invalid",
                context_key="context",
                source_ids=("source",),
                operation_payloads={"origin": {"records": []}},
            )

    def test_review_pipeline_keeps_all_four_stage_receipts(self) -> None:
        request = specimen_beta_frontier_pipeline_request_from_file(str(REVIEW))
        report = run_specimen_beta_frontier_pipeline(request)
        self.assertEqual(
            [receipt.stage.value for receipt in report.stage_receipts],
            ["origin", "mosaicism", "cancer_cell_fraction", "subclone"],
        )

    def test_stage_addresses_are_present(self) -> None:
        request = specimen_beta_frontier_pipeline_request_from_file(str(ACCEPTED))
        report = run_specimen_beta_frontier_pipeline(request)
        self.assertTrue(
            all(receipt.result_address.startswith("sha256:") for receipt in report.stage_receipts)
        )
        self.assertTrue(
            all(receipt.content_address.startswith("sha256:") for receipt in report.stage_receipts)
        )


if __name__ == "__main__":
    unittest.main()
