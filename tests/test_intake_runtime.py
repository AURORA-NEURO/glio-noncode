"""End-to-end orchestration tests for the Domain 01 intake runtime."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.intake_runtime import (
    IntakePipeline,
    IntakePipelineRequest,
    IntakePipelineState,
    IntakeStageReceipt,
    run_intake_pipeline,
)

ROOT = Path(__file__).resolve().parents[1]
REQUEST_PATH = ROOT / "examples" / "intake-pipeline-batch.json"
REQUEST = json.loads(REQUEST_PATH.read_text(encoding="utf-8"))
CONTEXT = REQUEST["context_key"]


def valid_request() -> dict[str, object]:
    raw = copy.deepcopy(REQUEST)
    raw["records"] = [raw["records"][0]]
    return raw


class IntakeRuntimeTests(unittest.TestCase):
    def test_public_pipeline_fixture_returns_review_with_partial_manifest(self) -> None:
        report = run_intake_pipeline(REQUEST)
        self.assertEqual(report.state, IntakePipelineState.REVIEW)
        self.assertFalse(report.accepted)
        self.assertTrue(report.published)
        self.assertEqual(report.accepted_record_ids, ("pipeline-accepted-clinvar",))
        self.assertEqual(report.blocked_record_ids, ("pipeline-review-sequence",))
        self.assertEqual(report.review_record_ids, ())
        self.assertEqual(len(report.stage_receipts), 4)
        self.assertEqual(report.stage_receipts[-1].state, "published")
        self.assertRegex(report.content_address, r"^sha256:[0-9a-f]{64}$")

    def test_all_valid_records_are_accepted_and_published(self) -> None:
        report = run_intake_pipeline(valid_request())
        self.assertEqual(report.state, IntakePipelineState.ACCEPTED)
        self.assertTrue(report.accepted)
        self.assertTrue(report.published)
        self.assertEqual(report.review_record_ids, ())
        self.assertEqual(report.blocked_record_ids, ())
        self.assertEqual(report.bundle["record_count"], 1)
        self.assertNotIn("records", report.bundle)

    def test_invalid_sequence_blocks_only_the_bad_row(self) -> None:
        raw = copy.deepcopy(REQUEST)
        report = IntakePipeline().run(IntakePipelineRequest.from_mapping(raw))
        self.assertIn("pipeline-review-sequence", report.blocked_record_ids)
        self.assertNotIn("pipeline-review-sequence", report.accepted_record_ids)
        anomaly = next(receipt for receipt in report.stage_receipts if receipt.stage_id == "anomaly")
        self.assertEqual(anomaly.accepted_count, 1)
        self.assertEqual(anomaly.review_count, 1)
        self.assertIn("invalid_sequence", anomaly.issue_codes)

    def test_missing_completeness_fields_remain_review_not_blocked(self) -> None:
        raw = valid_request()
        raw["records"][0].pop("end")
        report = run_intake_pipeline(raw)
        self.assertEqual(report.state, IntakePipelineState.BLOCKED)
        self.assertEqual(report.accepted_record_ids, ())
        self.assertEqual(report.blocked_record_ids, ())
        self.assertEqual(report.review_record_ids, ("pipeline-accepted-clinvar",))
        completeness = next(
            receipt for receipt in report.stage_receipts if receipt.stage_id == "completeness"
        )
        self.assertEqual(completeness.state, "review")
        self.assertIn("pipeline-accepted-clinvar", report.review_record_ids)

    def test_withdrawn_policy_blocks_export(self) -> None:
        raw = valid_request()
        raw["records"][0]["consent_status"] = "withdrawn"
        report = run_intake_pipeline(raw)
        self.assertEqual(report.state, IntakePipelineState.BLOCKED)
        self.assertFalse(report.published)
        self.assertIsNone(report.bundle)
        self.assertEqual(report.blocked_record_ids, ("pipeline-accepted-clinvar",))
        consent = next(receipt for receipt in report.stage_receipts if receipt.stage_id == "consent")
        self.assertEqual(consent.state, "review")
        self.assertIn("consent_not_active", consent.issue_codes)

    def test_context_mismatch_blocks_policy_and_anomaly(self) -> None:
        raw = valid_request()
        raw["records"][0]["context_key"] = "GRCh37|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"
        report = run_intake_pipeline(raw)
        self.assertEqual(report.state, IntakePipelineState.BLOCKED)
        self.assertIn("context_mismatch", report.issues)
        self.assertIn("pipeline-accepted-clinvar", report.blocked_record_ids)

    def test_request_parser_derives_source_ids_when_omitted(self) -> None:
        raw = valid_request()
        raw.pop("source_ids")
        request = IntakePipelineRequest.from_mapping(raw)
        self.assertEqual(request.source_ids, ("ncbi-clinvar-rs121913502",))
        self.assertEqual(request.record_ids, ("pipeline-accepted-clinvar",))

    def test_request_rejects_duplicate_record_ids_and_fields(self) -> None:
        raw = valid_request()
        raw["records"] = [raw["records"][0], copy.deepcopy(raw["records"][0])]
        with self.assertRaises(ValidationError):
            IntakePipelineRequest.from_mapping(raw)
        raw = valid_request()
        raw["required_fields"] = list(raw["required_fields"]) + ["start"]
        with self.assertRaises(ValidationError):
            IntakePipelineRequest.from_mapping(raw)

    def test_request_rejects_weight_key_drift_and_empty_records(self) -> None:
        raw = valid_request()
        raw["weights"].pop("start")
        with self.assertRaises(ValidationError):
            IntakePipelineRequest.from_mapping(raw)
        raw = valid_request()
        raw["records"] = []
        with self.assertRaises(ValidationError):
            IntakePipelineRequest.from_mapping(raw)

    def test_request_rejects_non_mapping_rows_and_invalid_threshold(self) -> None:
        raw = valid_request()
        raw["records"] = ["not-a-row"]
        with self.assertRaises(ValidationError):
            IntakePipelineRequest.from_mapping(raw)
        raw = valid_request()
        raw["minimum_score"] = 1.5
        with self.assertRaises(ValidationError):
            IntakePipelineRequest.from_mapping(raw)

    def test_stage_receipt_enforces_count_and_address_invariants(self) -> None:
        with self.assertRaises(ValidationError):
            IntakeStageReceipt(
                "stage",
                "GNC-D01-C13",
                "operation",
                "accepted",
                2,
                1,
                0,
                (),
                "sha256:address",
                "detail",
            )
        with self.assertRaises(ValidationError):
            IntakeStageReceipt(
                "stage",
                "GNC-D01-C13",
                "operation",
                "accepted",
                1,
                1,
                0,
                (),
                "not-addressed",
                "detail",
            )

    def test_pipeline_is_deterministic_for_same_request(self) -> None:
        first = run_intake_pipeline(valid_request())
        second = run_intake_pipeline(valid_request())
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_report_does_not_copy_an_extra_raw_field_into_bundle_receipt(self) -> None:
        raw = valid_request()
        raw["records"][0]["raw_private_payload_marker"] = "must-not-be-copied"
        report = run_intake_pipeline(raw)
        self.assertNotIn("raw_private_payload_marker", json.dumps(report.to_dict()))


if __name__ == "__main__":
    unittest.main()
