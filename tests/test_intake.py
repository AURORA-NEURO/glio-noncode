from __future__ import annotations

import json
import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from glio_noncode.errors import ValidationError
from glio_noncode.intake import (
    MAX_VARIANT_INDEX_RECORDS,
    IntakeFormat,
    IntakeSeverity,
    VariantIndex,
    VariantIntake,
)
from glio_noncode.models import ReferenceContext, VariantIdentity, VariantKind


class IntakeTests(unittest.TestCase):
    @staticmethod
    def _variant(index: int) -> VariantIdentity:
        return VariantIdentity(
            variant_id=f"variant-{index}",
            kind=VariantKind.SNV,
            chromosome="7",
            start=index + 1,
            end=index + 1,
            reference="A",
            alternate="T",
            genome_build="GRCh38",
        )

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
        self.assertNotIn("created_at", manifest.metadata["intake_receipt"])

    def test_variant_index_accepts_exact_configured_record_bound(self) -> None:
        variants = (self._variant(index) for index in range(3))

        index = VariantIndex(variants, max_records=3)

        self.assertEqual(
            tuple(variant.variant_id for variant in index.all()),
            ("variant-0", "variant-1", "variant-2"),
        )

    def test_variant_index_stops_after_max_plus_one_record(self) -> None:
        consumed: list[int] = []

        def variants():
            for index in range(4):
                consumed.append(index)
                if index == 3:
                    raise AssertionError("variant index consumed beyond max-plus-one")
                yield self._variant(index)

        with self.assertRaisesRegex(
            ValidationError,
            "variant_index_record_limit_exceeded",
        ):
            VariantIndex(variants(), max_records=2)

        self.assertEqual(consumed, [0, 1, 2])

    def test_variant_index_record_limit_is_strictly_bounded(self) -> None:
        for value in (False, 0, 1.5, MAX_VARIANT_INDEX_RECORDS + 1):
            with self.subTest(value=value), self.assertRaisesRegex(
                ValidationError,
                "MAX_VARIANT_INDEX_RECORDS",
            ):
                VariantIndex((), max_records=value)  # type: ignore[arg-type]

        for invalid in ("variant-id", {"variant_id": "not-a-container"}, (object(),)):
            with self.subTest(invalid=type(invalid).__name__), self.assertRaisesRegex(
                ValidationError,
                "VariantIdentity",
            ):
                VariantIndex(invalid)  # type: ignore[arg-type]

    def test_observation_time_does_not_change_scientific_identity(self) -> None:
        source = '[{"notation":"7:30:C>T","variant_id":"v1","genome_build":"GRCh38"}]'
        with patch(
            "glio_noncode.intake.utc_now",
            side_effect=(
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 2, 1, tzinfo=UTC),
            ),
        ):
            first = VariantIntake().parse_text(source, source_id="fixture-json")
            second = VariantIntake().parse_text(source, source_id="fixture-json")

        context = ReferenceContext("GRCh38", "glioma", "adult", "stem_like")
        first_manifest = first.to_manifest(
            case_id="case-intake", subject_id="subject-local", context=context
        )
        second_manifest = second.to_manifest(
            case_id="case-intake", subject_id="subject-local", context=context
        )

        self.assertNotEqual(first.receipt.created_at, second.receipt.created_at)
        self.assertEqual(first.receipt.content_address, second.receipt.content_address)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first_manifest.content_address, second_manifest.content_address)

    def test_invalid_input_is_an_error_not_an_empty_success(self) -> None:
        batch = VariantIntake().parse_text(
            "chrom\tpos\tref\n7\tbad\tA\n", source_id="bad", input_format="tsv"
        )
        self.assertTrue(batch.has_errors)
        self.assertEqual(batch.variants, ())
        self.assertEqual(batch.issues[0].severity, IntakeSeverity.ERROR)


if __name__ == "__main__":
    unittest.main()
