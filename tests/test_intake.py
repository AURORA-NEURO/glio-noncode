from __future__ import annotations

import json
import unittest

from glio_noncode.intake import IntakeFormat, IntakeSeverity, VariantIndex, VariantIntake
from glio_noncode.models import ReferenceContext


class IntakeTests(unittest.TestCase):
    def test_vcf_multiallelic_and_sample_metadata_are_canonicalized(self) -> None:
        text = "\n".join(
            (
                "##fileformat=VCFv4.3",
                "##source=test-fixture",
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE_A",
                "7\t55249071\trs-test\tA\tT,C\t99\tPASS\tDP=42;FLAG\tGT:PS\t1/2:10",
            )
        )
        batch = VariantIntake().parse_text(
            text, source_id="fixture-vcf", input_format=IntakeFormat.VCF
        )
        self.assertEqual(batch.receipt.record_count, 1)
        self.assertEqual(len(batch.variants), 2)
        self.assertEqual({variant.alternate for variant in batch.variants}, {"T", "C"})
        self.assertEqual(batch.variants[0].sample_id, "SAMPLE_A")
        self.assertEqual(batch.variants[0].annotations["info"]["DP"], "42")
        self.assertEqual(batch.variants[0].annotations["info"]["selected_sample"], "SAMPLE_A")
        self.assertFalse(batch.has_errors)

    def test_vcf_no_call_symbolic_and_duplicate_are_explicit(self) -> None:
        text = "\n".join(
            (
                "##fileformat=VCFv4.3",
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE_A",
                "7\t10\tno-call\tA\tT\t.\tPASS\t.\tGT\t./.",
                "7\t11\tsv\tA\t<DEL>\t.\tPASS\t.\tGT\t0/1",
                "7\t12\tdup\tA\tT\t.\tPASS\t.\tGT\t0/1",
                "7\t12\tdup2\tA\tT\t.\tPASS\t.\tGT\t0/1",
            )
        )
        batch = VariantIntake().parse_text(text, source_id="fixture-vcf", input_format="vcf")
        codes = {issue.code for issue in batch.issues}
        self.assertEqual(len(batch.variants), 1)
        self.assertIn("no_call_genotype", codes)
        self.assertIn("unsupported_symbolic_allele", codes)
        self.assertIn("duplicate_variant", codes)
        self.assertEqual(batch.receipt.warning_count, 3)

    def test_tsv_and_json_inputs_share_canonical_identity(self) -> None:
        tsv = "chrom\tpos\tref\talt\tvariant_id\tbuild\nchr7\t20\tG\tA\trow-1\tGRCh38\n"
        json_text = json.dumps(
            {
                "variants": [
                    {
                        "variant_id": "row-1",
                        "chromosome": "7",
                        "position": 20,
                        "reference": "G",
                        "alternate": "A",
                        "genome_build": "GRCh38",
                    }
                ]
            }
        )
        tsv_batch = VariantIntake().parse_text(tsv, source_id="fixture-tsv", input_format="tsv")
        json_batch = VariantIntake().parse_text(
            json_text, source_id="fixture-json", input_format="json"
        )
        self.assertEqual(tsv_batch.variants[0].canonical_key, json_batch.variants[0].canonical_key)
        self.assertEqual(tsv_batch.variants[0].variant_id, "row-1")
        self.assertEqual(json_batch.receipt.record_count, 1)

    def test_batch_manifest_and_interval_index_preserve_receipts(self) -> None:
        batch = VariantIntake().parse_text(
            '[{"notation":"7:30:C>T","variant_id":"v1","genome_build":"GRCh38"}]',
            source_id="fixture-json",
        )
        context = ReferenceContext("GRCh38", "glioma", "adult", "stem_like")
        manifest = batch.to_manifest(
            case_id="case-intake", subject_id="subject-local", context=context
        )
        index = VariantIndex(manifest.variants)
        self.assertEqual(index.overlap("chr7", 30, 30)[0].variant_id, "v1")
        self.assertEqual(manifest.input_versions["fixture-json"], batch.receipt.input_hash)
        self.assertEqual(manifest.metadata["intake_receipt"]["accepted_count"], 1)

    def test_invalid_input_is_an_error_not_an_empty_success(self) -> None:
        batch = VariantIntake().parse_text(
            "chrom\tpos\tref\n7\tbad\tA\n", source_id="bad", input_format="tsv"
        )
        self.assertTrue(batch.has_errors)
        self.assertEqual(batch.variants, ())
        self.assertEqual(batch.issues[0].severity, IntakeSeverity.ERROR)


if __name__ == "__main__":
    unittest.main()
