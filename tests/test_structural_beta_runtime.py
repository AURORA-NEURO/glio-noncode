"""Runtime orchestration tests for Domain 02 C05-C08."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.structural_beta_public_data import StructuralBetaOperation
from glio_noncode.structural_beta_runtime import (
    StructuralBetaPipeline,
    StructuralBetaPipelineRequest,
    StructuralBetaPipelineState,
    run_structural_beta_pipeline,
)

ROOT = Path(__file__).resolve().parents[1]
ACCEPTED = ROOT / "examples" / "structural-beta-pipeline-accepted.json"
REVIEW = ROOT / "examples" / "structural-beta-pipeline-review.json"


def load_request(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


class StructuralBetaRuntimeTests(unittest.TestCase):
    def test_accepted_request_runs_all_four_stages_in_order(self) -> None:
        report = run_structural_beta_pipeline(load_request(ACCEPTED))
        self.assertEqual(report.state, StructuralBetaPipelineState.ACCEPTED)
        self.assertTrue(report.accepted)
        self.assertTrue(report.published)
        self.assertEqual(len(report.stage_receipts), 4)
        self.assertEqual(
            tuple(receipt.operation for receipt in report.stage_receipts),
            tuple(StructuralBetaOperation),
        )
        self.assertEqual(
            tuple(receipt.capability_id for receipt in report.stage_receipts),
            ("GNC-D02-C05", "GNC-D02-C06", "GNC-D02-C07", "GNC-D02-C08"),
        )
        self.assertEqual(report.issues, ())

    def test_accepted_stage_counts_are_conserved(self) -> None:
        report = run_structural_beta_pipeline(load_request(ACCEPTED))
        for receipt in report.stage_receipts:
            self.assertGreater(receipt.input_count, 0)
            self.assertEqual(receipt.accepted_count, receipt.input_count)
            self.assertEqual(receipt.review_count, 0)
            self.assertEqual(receipt.accepted_count + receipt.review_count, receipt.input_count)
            self.assertRegex(receipt.output_address, r"^sha256:[0-9a-f]{64}$")

    def test_accepted_manifest_is_a_sanitized_stage_index(self) -> None:
        report = run_structural_beta_pipeline(load_request(ACCEPTED))
        self.assertIsNotNone(report.manifest)
        manifest = report.manifest or {}
        self.assertEqual(manifest["schema_version"], "structural-beta-pipeline-v1")
        self.assertEqual(manifest["stage_ids"], [item.value for item in StructuralBetaOperation])
        self.assertEqual(len(manifest["stage_addresses"]), 4)
        self.assertRegex(str(manifest["content_address"]), r"^sha256:[0-9a-f]{64}$")
        serialized = json.dumps(report.to_dict(), sort_keys=True)
        self.assertNotIn("raw_record", serialized)
        self.assertNotIn("subject_id", serialized)
        self.assertNotIn("patient_id", serialized)
        self.assertNotIn('"copy_number": -1', serialized)

    def test_review_request_publishes_review_manifest_but_not_acceptance(self) -> None:
        report = run_structural_beta_pipeline(load_request(REVIEW))
        self.assertEqual(report.state, StructuralBetaPipelineState.REVIEW)
        self.assertFalse(report.accepted)
        self.assertTrue(report.published)
        self.assertGreaterEqual(report.to_dict()["review_stage_count"], 1)
        self.assertIn("invalid_copy_number_record", report.issues)
        self.assertIn("context_mismatch", report.issues)
        self.assertTrue(any(receipt.state == StructuralBetaPipelineState.REVIEW for receipt in report.stage_receipts))

    def test_review_receipt_counts_remain_conserved(self) -> None:
        report = run_structural_beta_pipeline(load_request(REVIEW))
        for receipt in report.stage_receipts:
            self.assertEqual(receipt.accepted_count + receipt.review_count, receipt.input_count)
            self.assertGreater(receipt.input_count, 0)

    def test_runtime_is_deterministic_for_same_request(self) -> None:
        raw = load_request(ACCEPTED)
        first = run_structural_beta_pipeline(raw)
        second = run_structural_beta_pipeline(raw)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_request_parser_accepts_nested_operation_payloads(self) -> None:
        request = StructuralBetaPipelineRequest.from_mapping(load_request(ACCEPTED))
        self.assertEqual(request.request_id, "structural-beta-pipeline-accepted-2026-08-21")
        self.assertEqual(request.manifest_id, "structural-beta-pipeline-manifest-accepted")
        self.assertEqual(len(request.operation_payloads), 4)
        self.assertEqual(len(request.focal_amplification["records"]), 2)
        self.assertEqual(len(request.chromothripsis["records"]), 6)
        self.assertEqual(len(request.ecdna["records"]), 2)
        self.assertEqual(len(request.enhancer_hijacking["records"]), 2)

    def test_request_parser_accepts_flat_operation_fallback(self) -> None:
        raw = load_request(ACCEPTED)
        operations = raw.pop("operations")
        raw.update(operations)
        request = StructuralBetaPipelineRequest.from_mapping(raw)
        self.assertEqual(set(request.operation_payloads), {item.value for item in StructuralBetaOperation})

    def test_request_parser_rejects_empty_operation_payload(self) -> None:
        raw = load_request(ACCEPTED)
        raw["operations"]["ecdna"] = {}
        with self.assertRaisesRegex(ValidationError, "payload must not be empty"):
            StructuralBetaPipelineRequest.from_mapping(raw)

    def test_request_parser_rejects_missing_context(self) -> None:
        raw = load_request(ACCEPTED)
        raw["context_key"] = "GRCh38|diffuse_glioma"
        with self.assertRaisesRegex(ValidationError, "six fields"):
            StructuralBetaPipelineRequest.from_mapping(raw)

    def test_request_parser_rejects_duplicate_sources(self) -> None:
        raw = load_request(ACCEPTED)
        raw["source_ids"] = ["ncbi-dbvar-nstd102", "ncbi-dbvar-nstd102"]
        with self.assertRaisesRegex(ValidationError, "unique"):
            StructuralBetaPipelineRequest.from_mapping(raw)

    def test_request_parser_rejects_non_object_operation(self) -> None:
        raw = load_request(ACCEPTED)
        raw["operations"]["focal_amplification"] = []
        with self.assertRaisesRegex(ValidationError, "must be an object"):
            StructuralBetaPipelineRequest.from_mapping(raw)

    def test_invalid_copy_number_transitions_stage_to_review(self) -> None:
        raw = copy.deepcopy(load_request(ACCEPTED))
        raw["operations"]["focal_amplification"]["records"][0]["copy_number"] = -1
        report = run_structural_beta_pipeline(raw)
        focal = report.stage_receipts[0]
        self.assertEqual(report.state, StructuralBetaPipelineState.REVIEW)
        self.assertEqual(focal.state, StructuralBetaPipelineState.REVIEW)
        self.assertEqual(focal.accepted_count, 0)
        self.assertEqual(focal.review_count, focal.input_count)
        self.assertIn("invalid_copy_number_record", focal.issue_codes)

    def test_empty_records_create_blocked_pipeline(self) -> None:
        raw = load_request(ACCEPTED)
        for operation in raw["operations"].values():
            operation["records"] = []
        report = run_structural_beta_pipeline(raw)
        self.assertEqual(report.state, StructuralBetaPipelineState.BLOCKED)
        self.assertFalse(report.accepted)
        self.assertFalse(report.published)
        self.assertEqual(report.issues, ())
        self.assertTrue(all(receipt.input_count == 0 for receipt in report.stage_receipts))

    def test_direct_pipeline_run_matches_convenience_function(self) -> None:
        raw = load_request(ACCEPTED)
        request = StructuralBetaPipelineRequest.from_mapping(raw)
        direct = StructuralBetaPipeline().run(request)
        convenience = run_structural_beta_pipeline(raw)
        self.assertEqual(direct.content_address, convenience.content_address)
        self.assertEqual(direct.stage_receipts, convenience.stage_receipts)

    def test_stage_receipts_expose_operation_specific_details(self) -> None:
        report = run_structural_beta_pipeline(load_request(ACCEPTED))
        details = {receipt.operation.value: receipt.detail for receipt in report.stage_receipts}
        self.assertTrue(all(details.values()))
        self.assertIn("focal", details["focal_amplification"])
        self.assertIn("chromothripsis", details["chromothripsis"])
        self.assertIn("ecdna", details["ecdna"])
        self.assertIn("enhancer", details["enhancer_hijacking"])


if __name__ == "__main__":
    unittest.main()
