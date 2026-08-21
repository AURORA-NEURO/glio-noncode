"""Pipeline runtime tests for Domain 02 C13-C16."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.structural_frontier_public_data import StructuralFrontierOperation
from glio_noncode.structural_frontier_runtime import (
    StructuralFrontierPipeline,
    StructuralFrontierPipelineRequest,
    StructuralFrontierPipelineState,
    run_structural_frontier_pipeline,
)

ROOT = Path(__file__).resolve().parents[1]
ACCEPTED = ROOT / "examples" / "structural-frontier-pipeline-accepted.json"
REVIEW = ROOT / "examples" / "structural-frontier-pipeline-review.json"
CONTEXT = "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"
SOURCE_IDS = ["ncbi-dbvar-ftp-manifest", "ncbi-dbvar-study-browser", "gnomad-sv-v4", "ncbi-dbvar-human-hub"]


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


class StructuralFrontierRuntimeTests(unittest.TestCase):
    def test_accepted_example_runs_stages_in_contract_order(self) -> None:
        report = run_structural_frontier_pipeline(_load(ACCEPTED))
        self.assertEqual(report.state, StructuralFrontierPipelineState.ACCEPTED)
        self.assertTrue(report.accepted)
        self.assertTrue(report.published)
        self.assertEqual(tuple(receipt.operation for receipt in report.stage_receipts), tuple(StructuralFrontierOperation))
        self.assertEqual(tuple(receipt.capability_id for receipt in report.stage_receipts), (
            "GNC-D02-C13", "GNC-D02-C14", "GNC-D02-C15", "GNC-D02-C16"
        ))
        self.assertEqual(tuple(receipt.input_count for receipt in report.stage_receipts), (1, 1, 1, 2))
        self.assertTrue(all(receipt.state == StructuralFrontierPipelineState.ACCEPTED for receipt in report.stage_receipts))
        self.assertEqual(report.issues, ())

    def test_accepted_manifest_contains_only_stage_metadata(self) -> None:
        report = run_structural_frontier_pipeline(_load(ACCEPTED))
        assert report.manifest is not None
        self.assertEqual(report.manifest["schema_version"], "structural-frontier-pipeline-v1")
        self.assertEqual(report.manifest["stage_ids"], [item.value for item in StructuralFrontierOperation])
        self.assertEqual(report.manifest["source_ids"], SOURCE_IDS)
        self.assertTrue(all(str(address).startswith("sha256:") for address in report.manifest["stage_addresses"]))
        serialized = json.dumps(report.to_dict(), sort_keys=True)
        self.assertNotIn("raw_record", serialized)
        self.assertNotIn("pipeline-repeat-1", serialized)

    def test_review_example_preserves_all_issue_codes(self) -> None:
        report = run_structural_frontier_pipeline(_load(REVIEW))
        self.assertEqual(report.state, StructuralFrontierPipelineState.REVIEW)
        self.assertFalse(report.accepted)
        self.assertTrue(report.published)
        self.assertEqual(report.issues, ("incomplete_haplotype", "invalid_motif", "validation_error"))
        states = {receipt.stage_id: receipt.state for receipt in report.stage_receipts}
        self.assertTrue(all(state == StructuralFrontierPipelineState.REVIEW for state in states.values()))
        self.assertEqual(report.stage_receipts[3].result_state, "invalid")

    def test_stage_counts_conserve_input(self) -> None:
        for path in (ACCEPTED, REVIEW):
            report = run_structural_frontier_pipeline(_load(path))
            for receipt in report.stage_receipts:
                self.assertEqual(receipt.input_count, receipt.accepted_count + receipt.review_count)

    def test_runtime_is_deterministic(self) -> None:
        first = run_structural_frontier_pipeline(_load(ACCEPTED))
        second = run_structural_frontier_pipeline(_load(ACCEPTED))
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_nested_and_flat_operation_envelopes_are_equivalent(self) -> None:
        nested = _load(ACCEPTED)
        flat = copy.deepcopy(nested)
        operations = flat.pop("operations")
        flat.update(operations)
        self.assertEqual(run_structural_frontier_pipeline(nested).to_dict(), run_structural_frontier_pipeline(flat).to_dict())

    def test_missing_context_is_rejected(self) -> None:
        raw = _load(ACCEPTED)
        raw.pop("context_key")
        with self.assertRaisesRegex(ValidationError, "context_key must not be empty"):
            StructuralFrontierPipelineRequest.from_mapping(raw)

    def test_duplicate_source_ids_are_rejected(self) -> None:
        raw = _load(ACCEPTED)
        raw["source_ids"] = ["same-source", "same-source"]
        with self.assertRaisesRegex(ValidationError, "source IDs must be unique"):
            StructuralFrontierPipelineRequest.from_mapping(raw)

    def test_non_object_operation_is_rejected(self) -> None:
        raw = _load(ACCEPTED)
        raw["operations"]["tandem_repeat"] = []
        with self.assertRaisesRegex(ValidationError, "operation tandem_repeat must be an object"):
            StructuralFrontierPipelineRequest.from_mapping(raw)

    def test_empty_operation_payload_is_rejected(self) -> None:
        raw = _load(ACCEPTED)
        raw["operations"]["tandem_repeat"] = {}
        with self.assertRaisesRegex(ValidationError, "tandem_repeat payload must not be empty"):
            StructuralFrontierPipelineRequest.from_mapping(raw)

    def test_invalid_stage_input_becomes_review_without_echo(self) -> None:
        raw = _load(ACCEPTED)
        raw["operations"]["tandem_repeat"]["records"] = "not-an-array"
        report = run_structural_frontier_pipeline(raw)
        receipt = report.stage_receipts[0]
        self.assertEqual(report.state, StructuralFrontierPipelineState.REVIEW)
        self.assertEqual(receipt.result_state, "invalid")
        self.assertIn("validation_error", receipt.issue_codes)
        self.assertEqual(receipt.input_count, 0)
        self.assertNotIn("not-an-array", json.dumps(report.to_dict(), sort_keys=True))

    def test_all_empty_collections_are_blocked_without_manifest(self) -> None:
        raw = _load(ACCEPTED)
        for payload in raw["operations"].values():
            payload.pop("records", None)
            payload.pop("evidence", None)
            payload["parameters"] = {"blocked": True}
        report = run_structural_frontier_pipeline(raw)
        self.assertEqual(report.state, StructuralFrontierPipelineState.BLOCKED)
        self.assertFalse(report.published)
        self.assertIsNone(report.manifest)
        self.assertTrue(all(receipt.input_count == 0 for receipt in report.stage_receipts))

    def test_direct_pipeline_and_wrapper_match(self) -> None:
        raw = _load(ACCEPTED)
        request = StructuralFrontierPipelineRequest.from_mapping(raw)
        direct = StructuralFrontierPipeline().run(request)
        wrapped = run_structural_frontier_pipeline(raw)
        self.assertEqual(direct.content_address, wrapped.content_address)
        self.assertEqual(direct.to_dict(), wrapped.to_dict())

    def test_request_to_dict_preserves_four_boundaries(self) -> None:
        request = StructuralFrontierPipelineRequest.from_mapping(_load(ACCEPTED))
        payload = request.to_dict()
        self.assertEqual(payload["context_key"], CONTEXT)
        self.assertEqual(set(payload) & {
            "tandem_repeat", "compound_haplotype", "breakpoint_uncertainty", "structural_evidence_export"
        }, {
            "tandem_repeat", "compound_haplotype", "breakpoint_uncertainty", "structural_evidence_export"
        })


if __name__ == "__main__":
    unittest.main()
