from __future__ import annotations

import unittest
from pathlib import Path

from glio_noncode.reference_annotation_runtime import (
    ReferenceAnnotationRuntimeRequest,
    run_reference_annotation_pipeline,
    run_reference_annotation_pipeline_file,
)

ROOT = Path(__file__).resolve().parents[1]


class ReferenceAnnotationRuntimeTests(unittest.TestCase):
    def test_accepted_pipeline_publishes_four_entries(self) -> None:
        request = ReferenceAnnotationRuntimeRequest(
            str(ROOT / "examples/reference-annotation-public-aggregate.json")
        )
        report = run_reference_annotation_pipeline(request)
        self.assertTrue(report.published)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.stage_receipts), 6)
        self.assertEqual(report.bundle["entry_count"], 4)

    def test_context_drift_blocks_publication(self) -> None:
        request = ReferenceAnnotationRuntimeRequest(
            str(ROOT / "examples/reference-annotation-public-aggregate.json"),
            context_key="GRCh37|diffuse_glioma|adult|bulk_tumor|reference_plane|baseline",
        )
        report = run_reference_annotation_pipeline(request)
        self.assertFalse(report.published)
        self.assertIn("public_data", report.failed_stages)
        self.assertIn("bundle", report.failed_stages)

    def test_file_request_is_supported(self) -> None:
        report = run_reference_annotation_pipeline_file(
            ROOT / "examples/reference-annotation-pipeline-accepted.json"
        )
        self.assertTrue(report.published)
        self.assertEqual(report.fixture_id, "reference-annotation-public-aggregate")

    def test_review_request_file_does_not_publish(self) -> None:
        report = run_reference_annotation_pipeline_file(
            ROOT / "examples/reference-annotation-pipeline-review.json"
        )
        self.assertFalse(report.published)
        self.assertTrue(report.failed_stages)

    def test_stage_order_is_stable(self) -> None:
        request = ReferenceAnnotationRuntimeRequest(
            str(ROOT / "examples/reference-annotation-public-aggregate.json")
        )
        report = run_reference_annotation_pipeline(request)
        self.assertEqual(
            [receipt.stage.value for receipt in report.stage_receipts],
            [
                "public_data",
                "fixture_evaluation",
                "replay",
                "reconciliation",
                "quality_gate",
                "bundle",
            ],
        )

    def test_runtime_report_is_deterministic(self) -> None:
        request = ReferenceAnnotationRuntimeRequest(
            str(ROOT / "examples/reference-annotation-public-aggregate.json")
        )
        self.assertEqual(
            run_reference_annotation_pipeline(request).content_address,
            run_reference_annotation_pipeline(request).content_address,
        )
