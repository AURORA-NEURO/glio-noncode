"""Pipeline runtime tests for Domain 02 C09-C12."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.structural_haplotype_public_data import StructuralHaplotypeOperation
from glio_noncode.structural_haplotype_runtime import (
    StructuralHaplotypePipeline,
    StructuralHaplotypePipelineRequest,
    StructuralHaplotypePipelineState,
    run_structural_haplotype_pipeline,
)

ROOT = Path(__file__).resolve().parents[1]
ACCEPTED = ROOT / "examples" / "structural-haplotype-pipeline-accepted.json"
REVIEW = ROOT / "examples" / "structural-haplotype-pipeline-review.json"
CONTEXT = "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"
FORBIDDEN_SERIALIZED_FIELDS = ("raw_record", "patient_id", "subject_id", "medical_record_number", "AGCT")


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


class StructuralHaplotypeRuntimeTests(unittest.TestCase):
    def test_accepted_example_runs_all_stages_in_contract_order(self) -> None:
        report = run_structural_haplotype_pipeline(_load(ACCEPTED))
        self.assertEqual(report.state, StructuralHaplotypePipelineState.ACCEPTED)
        self.assertTrue(report.accepted)
        self.assertTrue(report.published)
        self.assertEqual(
            tuple(receipt.operation for receipt in report.stage_receipts),
            tuple(StructuralHaplotypeOperation),
        )
        self.assertEqual(
            tuple(receipt.capability_id for receipt in report.stage_receipts),
            ("GNC-D02-C09", "GNC-D02-C10", "GNC-D02-C11", "GNC-D02-C12"),
        )
        self.assertEqual(tuple(receipt.input_count for receipt in report.stage_receipts), (2, 1, 1, 1))
        self.assertTrue(all(receipt.state == StructuralHaplotypePipelineState.ACCEPTED for receipt in report.stage_receipts))
        self.assertEqual(report.issues, ())

    def test_accepted_manifest_is_addressed_and_sanitized(self) -> None:
        report = run_structural_haplotype_pipeline(_load(ACCEPTED))
        assert report.manifest is not None
        self.assertEqual(report.manifest["schema_version"], "structural-haplotype-pipeline-v1")
        self.assertEqual(
            report.manifest["stage_ids"],
            ["phased_haplotype", "allele_aware_sv", "pangenome_projection", "repeat_mobile_annotation"],
        )
        self.assertEqual(len(report.manifest["stage_addresses"]), 4)
        self.assertTrue(all(str(address).startswith("sha256:") for address in report.manifest["stage_addresses"]))
        serialized = json.dumps(report.to_dict(), sort_keys=True)
        for field in FORBIDDEN_SERIALIZED_FIELDS:
            self.assertNotIn(field, serialized)
        self.assertNotIn("aggregate-pipeline-phase", serialized)

    def test_review_example_preserves_issue_codes_and_stage_accounting(self) -> None:
        report = run_structural_haplotype_pipeline(_load(REVIEW))
        self.assertEqual(report.state, StructuralHaplotypePipelineState.REVIEW)
        self.assertFalse(report.accepted)
        self.assertTrue(report.published)
        self.assertEqual(
            report.issues,
            ("annotation_context_mismatch", "conflicting_allele_observation", "context_mismatch"),
        )
        self.assertEqual(
            {receipt.stage_id: receipt.state for receipt in report.stage_receipts},
            {
                "phased_haplotype": StructuralHaplotypePipelineState.REVIEW,
                "allele_aware_sv": StructuralHaplotypePipelineState.REVIEW,
                "pangenome_projection": StructuralHaplotypePipelineState.ACCEPTED,
                "repeat_mobile_annotation": StructuralHaplotypePipelineState.REVIEW,
            },
        )
        for receipt in report.stage_receipts:
            self.assertEqual(receipt.input_count, receipt.accepted_count + receipt.review_count)
        self.assertEqual(report.stage_receipts[0].result_state, "out_of_domain")
        self.assertEqual(report.stage_receipts[1].result_state, "contradictory")

    def test_review_manifest_retains_only_stage_level_public_fields(self) -> None:
        report = run_structural_haplotype_pipeline(_load(REVIEW))
        assert report.manifest is not None
        self.assertEqual(report.manifest["state"], "review")
        self.assertEqual(report.manifest["source_ids"], [
            "ncbi-dbvar-haplotype",
            "gnomad-sv-v4",
            "ncbi-dbvar-study-browser",
            "ncbi-dbvar-ftp-manifest",
        ])
        serialized = json.dumps(report.manifest, sort_keys=True)
        self.assertNotIn("review-allele", serialized)
        self.assertNotIn("review-phase-context", serialized)

    def test_runtime_is_deterministic(self) -> None:
        first = run_structural_haplotype_pipeline(_load(ACCEPTED))
        second = run_structural_haplotype_pipeline(_load(ACCEPTED))
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_nested_and_flat_operation_envelopes_are_equivalent(self) -> None:
        nested = _load(ACCEPTED)
        flat = copy.deepcopy(nested)
        operations = flat.pop("operations")
        flat.update(operations)
        nested_report = run_structural_haplotype_pipeline(nested)
        flat_report = run_structural_haplotype_pipeline(flat)
        self.assertEqual(nested_report.content_address, flat_report.content_address)
        self.assertEqual(nested_report.to_dict(), flat_report.to_dict())

    def test_request_parser_rejects_missing_context(self) -> None:
        raw = _load(ACCEPTED)
        raw.pop("context_key")
        with self.assertRaisesRegex(ValidationError, "context_key must not be empty"):
            StructuralHaplotypePipelineRequest.from_mapping(raw)

    def test_request_parser_rejects_duplicate_sources(self) -> None:
        raw = _load(ACCEPTED)
        raw["source_ids"] = ["same-source", "same-source"]
        with self.assertRaisesRegex(ValidationError, "source IDs must be unique"):
            StructuralHaplotypePipelineRequest.from_mapping(raw)

    def test_request_parser_rejects_non_object_operations(self) -> None:
        raw = _load(ACCEPTED)
        raw["operations"]["allele_aware_sv"] = []
        with self.assertRaisesRegex(ValidationError, "operation allele_aware_sv must be an object"):
            StructuralHaplotypePipelineRequest.from_mapping(raw)

    def test_request_parser_rejects_empty_operation_payload(self) -> None:
        raw = _load(ACCEPTED)
        raw["operations"]["repeat_mobile_annotation"] = {}
        with self.assertRaisesRegex(ValidationError, "repeat_mobile_annotation payload must not be empty"):
            StructuralHaplotypePipelineRequest.from_mapping(raw)

    def test_invalid_stage_input_becomes_review_without_raw_payload(self) -> None:
        raw = _load(ACCEPTED)
        raw["operations"]["phased_haplotype"]["records"] = "not-an-array"
        report = run_structural_haplotype_pipeline(raw)
        phased = report.stage_receipts[0]
        self.assertEqual(report.state, StructuralHaplotypePipelineState.REVIEW)
        self.assertEqual(phased.state, StructuralHaplotypePipelineState.REVIEW)
        self.assertIn("validation_error", phased.issue_codes)
        self.assertEqual(phased.input_count, 0)
        self.assertEqual(phased.accepted_count, 0)
        self.assertEqual(phased.review_count, 0)
        self.assertNotIn("not-an-array", json.dumps(report.to_dict(), sort_keys=True))

    def test_all_empty_record_collections_are_blocked_without_manifest(self) -> None:
        raw = _load(ACCEPTED)
        for name, payload in raw["operations"].items():
            payload.pop("records", None)
            payload.pop("queries", None)
            payload["parameters"] = {"blocked_fixture": name}
        report = run_structural_haplotype_pipeline(raw)
        self.assertEqual(report.state, StructuralHaplotypePipelineState.BLOCKED)
        self.assertFalse(report.published)
        self.assertIsNone(report.manifest)
        self.assertTrue(all(receipt.input_count == 0 for receipt in report.stage_receipts))

    def test_direct_pipeline_and_function_wrapper_match(self) -> None:
        raw = _load(ACCEPTED)
        request = StructuralHaplotypePipelineRequest.from_mapping(raw)
        direct = StructuralHaplotypePipeline().run(request)
        wrapped = run_structural_haplotype_pipeline(raw)
        self.assertEqual(direct.content_address, wrapped.content_address)
        self.assertEqual(direct.to_dict(), wrapped.to_dict())

    def test_request_to_dict_keeps_operation_boundaries(self) -> None:
        request = StructuralHaplotypePipelineRequest.from_mapping(_load(ACCEPTED))
        payload = request.to_dict()
        self.assertEqual(payload["context_key"], CONTEXT)
        self.assertEqual(set(payload) & {
            "phased_haplotype",
            "allele_aware_sv",
            "pangenome_projection",
            "repeat_mobile_annotation",
        }, {
            "phased_haplotype",
            "allele_aware_sv",
            "pangenome_projection",
            "repeat_mobile_annotation",
        })
        self.assertNotIn("raw_record", json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
