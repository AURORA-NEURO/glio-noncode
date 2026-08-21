"""End-to-end orchestration tests for the Domain 02 structural runtime."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.structural_runtime import (
    StructuralPipelineRequest,
    StructuralPipelineState,
    StructuralStageReceipt,
    run_structural_pipeline,
)

ROOT = Path(__file__).resolve().parents[1]
ACCEPTED_PATH = ROOT / "examples" / "structural-pipeline-accepted.json"
REVIEW_PATH = ROOT / "examples" / "structural-pipeline-batch.json"
ACCEPTED = json.loads(ACCEPTED_PATH.read_text(encoding="utf-8"))
REVIEW = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))


class StructuralRuntimeTests(unittest.TestCase):
    def test_accepted_pipeline_composes_all_four_stages(self) -> None:
        report = run_structural_pipeline(ACCEPTED)
        self.assertEqual(report.state, StructuralPipelineState.ACCEPTED)
        self.assertTrue(report.accepted)
        self.assertTrue(report.published)
        self.assertEqual(len(report.stage_receipts), 4)
        self.assertTrue(all(item.state == StructuralPipelineState.ACCEPTED for item in report.stage_receipts))
        self.assertEqual([item.capability_id for item in report.stage_receipts], [
            "GNC-D02-C01",
            "GNC-D02-C02",
            "GNC-D02-C03",
            "GNC-D02-C04",
        ])

    def test_review_pipeline_keeps_other_stages_and_manifest(self) -> None:
        report = run_structural_pipeline(REVIEW)
        self.assertEqual(report.state, StructuralPipelineState.REVIEW)
        self.assertFalse(report.accepted)
        self.assertTrue(report.published)
        self.assertIn("missing_mate_id", report.issues)
        self.assertEqual(report.stage_receipts[0].state, StructuralPipelineState.REVIEW)
        self.assertTrue(all(item.state == StructuralPipelineState.ACCEPTED for item in report.stage_receipts[1:]))
        self.assertNotIn("records", str(report.manifest))

    def test_stage_count_invariant_is_enforced(self) -> None:
        with self.assertRaises(ValidationError):
            StructuralStageReceipt(
                stage_id="stage",
                capability_id="GNC-D02-C01",
                operation=__import__(
                    "glio_noncode.structural_public_data", fromlist=["StructuralOperation"]
                ).StructuralOperation.RECONSTRUCTION,
                state=StructuralPipelineState.ACCEPTED,
                input_count=2,
                accepted_count=1,
                review_count=0,
                result_state="eventful",
                issue_codes=(),
                output_address="sha256:address",
                detail="detail",
            )

    def test_request_parser_requires_exact_context_and_operations(self) -> None:
        request = StructuralPipelineRequest.from_mapping(ACCEPTED)
        self.assertEqual(request.context_key, ACCEPTED["context_key"])
        self.assertEqual(set(request.operation_payloads), {
            "reconstruction",
            "consensus",
            "complex_resolution",
            "copy_number",
        })
        raw = copy.deepcopy(ACCEPTED)
        raw["context_key"] = "GRCh38|only-three-fields"
        with self.assertRaises(ValidationError):
            StructuralPipelineRequest.from_mapping(raw)

    def test_request_parser_rejects_duplicate_sources(self) -> None:
        raw = copy.deepcopy(ACCEPTED)
        raw["source_ids"] = ["same", "same"]
        with self.assertRaises(ValidationError):
            StructuralPipelineRequest.from_mapping(raw)

    def test_request_parser_rejects_non_object_operation(self) -> None:
        raw = copy.deepcopy(ACCEPTED)
        raw["operations"]["consensus"] = []
        with self.assertRaises(ValidationError):
            StructuralPipelineRequest.from_mapping(raw)

    def test_pipeline_is_deterministic(self) -> None:
        first = run_structural_pipeline(ACCEPTED)
        second = run_structural_pipeline(ACCEPTED)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_manifest_contains_only_addresses_and_declared_sources(self) -> None:
        report = run_structural_pipeline(ACCEPTED)
        manifest = report.manifest
        self.assertEqual(manifest["source_ids"], ACCEPTED["source_ids"])
        self.assertEqual(manifest["stage_ids"], [
            "reconstruction",
            "consensus",
            "complex_resolution",
            "copy_number",
        ])
        self.assertTrue(all(address.startswith("sha256:") for address in manifest["stage_addresses"]))
        self.assertNotIn("pipeline-del", json.dumps(manifest))
        self.assertNotIn("caller_version", json.dumps(manifest))

    def test_invalid_copy_number_stage_is_review_not_success(self) -> None:
        raw = copy.deepcopy(ACCEPTED)
        raw["operations"]["copy_number"]["segments"][0]["copy_number"] = -1
        report = run_structural_pipeline(raw)
        self.assertEqual(report.state, StructuralPipelineState.REVIEW)
        self.assertIn("validation_error", report.issues)
        self.assertEqual(report.stage_receipts[-1].state, StructuralPipelineState.REVIEW)

    def test_empty_operation_payload_is_rejected_at_request_boundary(self) -> None:
        raw = copy.deepcopy(ACCEPTED)
        raw["operations"]["complex_resolution"] = {}
        with self.assertRaises(ValidationError):
            StructuralPipelineRequest.from_mapping(raw)

    def test_raw_request_copy_does_not_change_report_address(self) -> None:
        raw = copy.deepcopy(ACCEPTED)
        raw["operations"]["reconstruction"]["records"][0]["raw_private_payload_marker"] = "private"
        report = run_structural_pipeline(raw)
        self.assertNotIn("private", json.dumps(report.to_dict()))

    def test_pipeline_request_round_trips_without_execution_payload_loss(self) -> None:
        request = StructuralPipelineRequest.from_mapping(ACCEPTED)
        round_trip = StructuralPipelineRequest.from_mapping(request.to_dict())
        self.assertEqual(request.request_id, round_trip.request_id)
        self.assertEqual(request.manifest_id, round_trip.manifest_id)
        self.assertEqual(request.context_key, round_trip.context_key)
        self.assertEqual(request.source_ids, round_trip.source_ids)
        self.assertEqual(request.operation_payloads, round_trip.operation_payloads)


if __name__ == "__main__":
    unittest.main()
