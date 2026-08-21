"""Runtime pipeline tests for Domain 03 C01-C04."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.specimen_frontier_runtime import (
    SpecimenFrontierPipelineRequest,
    SpecimenFrontierPipelineState,
    run_specimen_frontier_pipeline,
)

ROOT = Path(__file__).resolve().parents[1]
ACCEPTED = ROOT / "examples" / "specimen-frontier-pipeline-accepted.json"
REVIEW = ROOT / "examples" / "specimen-frontier-pipeline-review.json"


class SpecimenFrontierRuntimeTests(unittest.TestCase):
    def test_accepted_pipeline_publishes_four_stage_manifest(self) -> None:
        report = run_specimen_frontier_pipeline(json.loads(ACCEPTED.read_text(encoding="utf-8")))
        self.assertTrue(report.accepted)
        self.assertTrue(report.published)
        self.assertEqual(report.state, SpecimenFrontierPipelineState.ACCEPTED)
        self.assertEqual(len(report.stage_receipts), 4)
        self.assertEqual(
            [receipt.accepted_count for receipt in report.stage_receipts], [1, 2, 1, 1]
        )
        self.assertEqual([receipt.review_count for receipt in report.stage_receipts], [0, 0, 0, 0])
        self.assertTrue(report.manifest["content_address"].startswith("sha256:"))

    def test_review_pipeline_keeps_issue_codes_and_manifest_state(self) -> None:
        report = run_specimen_frontier_pipeline(json.loads(REVIEW.read_text(encoding="utf-8")))
        self.assertFalse(report.accepted)
        self.assertTrue(report.published)
        self.assertEqual(report.state, SpecimenFrontierPipelineState.REVIEW)
        self.assertIn("ambiguous_subject", report.issues)
        self.assertIn("missing_matched_normal", report.issues)
        self.assertIn("invalid_purity_ploidy_row", report.issues)
        self.assertIn("subject_fingerprint_mismatch", report.issues)
        self.assertGreater(report.to_dict()["review_stage_count"], 0)

    def test_pipeline_request_parser_accepts_nested_operations(self) -> None:
        payload = json.loads(ACCEPTED.read_text(encoding="utf-8"))
        request = SpecimenFrontierPipelineRequest.from_mapping(payload)
        self.assertEqual(request.request_id, "specimen-frontier-pipeline-accepted-001")
        self.assertEqual(len(request.source_ids), 4)
        self.assertEqual(
            set(request.operation_payloads),
            {
                "ontology_mapping",
                "matched_normal",
                "purity_ploidy",
                "sample_integrity",
            },
        )

    def test_duplicate_source_ids_are_rejected(self) -> None:
        payload = json.loads(ACCEPTED.read_text(encoding="utf-8"))
        payload["source_ids"].append(payload["source_ids"][0])
        with self.assertRaises(ValidationError):
            SpecimenFrontierPipelineRequest.from_mapping(payload)

    def test_missing_stage_payload_is_rejected(self) -> None:
        payload = json.loads(ACCEPTED.read_text(encoding="utf-8"))
        del payload["operations"]["sample_integrity"]
        with self.assertRaises(ValidationError):
            SpecimenFrontierPipelineRequest.from_mapping(payload)

    def test_invalid_context_is_rejected(self) -> None:
        payload = json.loads(ACCEPTED.read_text(encoding="utf-8"))
        payload["context_key"] = "GRCh38|only-two"
        with self.assertRaises(ValidationError):
            SpecimenFrontierPipelineRequest.from_mapping(payload)

    def test_empty_stage_batch_is_blocked(self) -> None:
        payload = json.loads(ACCEPTED.read_text(encoding="utf-8"))
        for name, stage in payload["operations"].items():
            if name in {"ontology_mapping", "matched_normal"}:
                stage["records"] = []
            elif name == "purity_ploidy":
                stage["text"] = ""
            else:
                stage["fingerprints"] = []
        report = run_specimen_frontier_pipeline(payload)
        self.assertEqual(report.state, SpecimenFrontierPipelineState.BLOCKED)
        self.assertFalse(report.published)

    def test_runtime_report_is_deterministic(self) -> None:
        payload = json.loads(ACCEPTED.read_text(encoding="utf-8"))
        first = run_specimen_frontier_pipeline(payload)
        second = run_specimen_frontier_pipeline(payload)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_runtime_output_excludes_raw_payload(self) -> None:
        payload = json.loads(ACCEPTED.read_text(encoding="utf-8"))
        payload["operations"]["ontology_mapping"]["records"][0]["private_note"] = "hidden"
        report = run_specimen_frontier_pipeline(payload)
        serialized = json.dumps(report.to_dict(), sort_keys=True)
        self.assertNotIn("private_note", serialized)
        self.assertNotIn("hidden", serialized)


if __name__ == "__main__":
    unittest.main()
