from __future__ import annotations

import json
import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from glio_noncode.errors import ValidationError
from glio_noncode.intake import (
    MAX_VARIANT_INDEX_RECORDS,
    MAX_VARIANT_INTAKE_AUXILIARY_LINES,
    MAX_VARIANT_INTAKE_RECORDS,
    IntakeFormat,
    IntakeSeverity,
    VariantIndex,
    VariantIntake,
)
from glio_noncode.models import ReferenceContext, VariantIdentity, VariantKind
from glio_noncode.serialization import content_hash


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

    @staticmethod
    def _text_source(input_format: IntakeFormat, record_count: int) -> str:
        if input_format in {IntakeFormat.VCF, IntakeFormat.GVCF}:
            return "\n".join(
                (
                    "##fileformat=VCFv4.3",
                    "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO",
                    *(
                        f"7\t{index + 1}\tvariant-{index}\tA\tT\t.\tPASS\t."
                        for index in range(record_count)
                    ),
                )
            )
        if input_format == IntakeFormat.TSV:
            return "\n".join(
                (
                    "chrom\tpos\tref\talt\tvariant_id",
                    *(
                        f"7\t{index + 1}\tA\tT\tvariant-{index}"
                        for index in range(record_count)
                    ),
                )
            )
        return json.dumps(
            {
                "variants": [
                    {
                        "variant_id": f"variant-{index}",
                        "chromosome": "7",
                        "position": index + 1,
                        "reference": "A",
                        "alternate": "T",
                    }
                    for index in range(record_count)
                ]
            }
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

    def test_variant_intake_record_limit_is_strictly_bounded(self) -> None:
        for value in (False, 0, 1.5, MAX_VARIANT_INTAKE_RECORDS + 1):
            with self.subTest(value=value), self.assertRaisesRegex(
                ValidationError,
                "MAX_VARIANT_INTAKE_RECORDS",
            ):
                VariantIntake(max_records=value)  # type: ignore[arg-type]

    def test_variant_intake_auxiliary_limit_is_strictly_bounded(self) -> None:
        for value in (False, 0, 1.5, MAX_VARIANT_INTAKE_AUXILIARY_LINES + 1):
            with self.subTest(value=value), self.assertRaisesRegex(
                ValidationError,
                "MAX_VARIANT_INTAKE_AUXILIARY_LINES",
            ):
                VariantIntake(max_auxiliary_lines=value)  # type: ignore[arg-type]

    def test_variant_intake_string_identifiers_fail_with_typed_validation(self) -> None:
        with self.assertRaisesRegex(ValidationError, "default_build"):
            VariantIntake(default_build=None)  # type: ignore[arg-type]

        parser = VariantIntake()
        with self.assertRaisesRegex(ValidationError, "source_id"):
            parser.parse_text(
                "[]",
                source_id=None,  # type: ignore[arg-type]
                input_format=IntakeFormat.JSON,
            )
        with self.assertRaisesRegex(ValidationError, "genome_build"):
            parser.parse_text(
                "[]",
                source_id="typed-validation",
                input_format=IntakeFormat.JSON,
                genome_build=1,  # type: ignore[arg-type]
            )
        with self.assertRaisesRegex(ValidationError, "genome_build"):
            parser.parse_text(
                "[]",
                source_id="typed-validation",
                input_format=IntakeFormat.JSON,
                genome_build=0,  # type: ignore[arg-type]
            )
        with self.assertRaisesRegex(ValidationError, "sample_id"):
            parser.parse_text(
                "[]",
                source_id="typed-validation",
                input_format=IntakeFormat.JSON,
                sample_id=0,  # type: ignore[arg-type]
            )
        with self.assertRaisesRegex(ValidationError, "include_no_call"):
            parser.parse_text(
                "[]",
                source_id="typed-validation",
                input_format=IntakeFormat.JSON,
                include_no_call=1,  # type: ignore[arg-type]
            )
        with self.assertRaisesRegex(ValidationError, "source_id"):
            parser.parse_bytes(b"not-bcf", source_id=1)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValidationError, "genome_build"):
            parser.parse_bytes(
                b"not-bcf",
                source_id="typed-validation",
                genome_build=1,  # type: ignore[arg-type]
            )
        with self.assertRaisesRegex(ValidationError, "sample_id"):
            parser.parse_bytes(
                b"not-bcf",
                source_id="typed-validation",
                sample_id=0,  # type: ignore[arg-type]
            )
        with self.assertRaisesRegex(ValidationError, "include_no_call"):
            parser.parse_bytes(
                b"not-bcf",
                source_id="typed-validation",
                include_no_call=1,  # type: ignore[arg-type]
            )

    def test_text_parsers_preserve_outputs_at_exact_record_bound(self) -> None:
        for input_format in (
            IntakeFormat.VCF,
            IntakeFormat.GVCF,
            IntakeFormat.TSV,
            IntakeFormat.JSON,
        ):
            with self.subTest(input_format=input_format):
                text = self._text_source(input_format, 2)
                legacy = VariantIntake().parse_text(
                    text,
                    source_id=f"legacy-{input_format}",
                    input_format=input_format,
                )
                max_auxiliary_lines = (
                    2
                    if input_format in {IntakeFormat.VCF, IntakeFormat.GVCF}
                    else MAX_VARIANT_INTAKE_AUXILIARY_LINES
                )
                bounded = VariantIntake(
                    max_records=2,
                    max_auxiliary_lines=max_auxiliary_lines,
                ).parse_text(
                    text,
                    source_id=f"legacy-{input_format}",
                    input_format=input_format,
                )

                self.assertEqual(bounded.variants, legacy.variants)
                self.assertEqual(bounded.records, legacy.records)
                self.assertEqual(bounded.issues, legacy.issues)
                self.assertEqual(
                    bounded.receipt.provenance_dict(),
                    legacy.receipt.provenance_dict(),
                )
                self.assertEqual(bounded.receipt.record_count, 2)
                self.assertFalse(bounded.has_errors)

    def test_text_parsers_stop_on_one_overflow_sentinel_and_fail_closed(self) -> None:
        expected_lines = {
            IntakeFormat.VCF: 5,
            IntakeFormat.GVCF: 5,
            IntakeFormat.TSV: 4,
            IntakeFormat.JSON: 3,
        }
        for input_format in (
            IntakeFormat.VCF,
            IntakeFormat.GVCF,
            IntakeFormat.TSV,
            IntakeFormat.JSON,
        ):
            with self.subTest(input_format=input_format):
                text = self._text_source(input_format, 4)
                parser = VariantIntake(max_records=2)
                with patch.object(
                    parser,
                    "_add_record",
                    wraps=parser._add_record,
                ) as add_record:
                    batch = parser.parse_text(
                        text,
                        source_id=f"overflow-{input_format}",
                        input_format=input_format,
                    )

                add_record.assert_called()
                self.assertEqual(add_record.call_count, 2)
                self.assertEqual(batch.receipt.record_count, 3)
                self.assertEqual(batch.receipt.accepted_count, 2)
                self.assertEqual(batch.receipt.error_count, 1)
                self.assertEqual(batch.receipt.rejected_count, 1)
                self.assertEqual(batch.receipt.input_hash, content_hash(text))
                self.assertTrue(batch.has_errors)
                overflow = [issue for issue in batch.issues if issue.code == "max_records_exceeded"]
                self.assertEqual(len(overflow), 1)
                self.assertEqual(overflow[0].severity, IntakeSeverity.ERROR)
                self.assertEqual(overflow[0].line_number, expected_lines[input_format])
                if input_format in {IntakeFormat.VCF, IntakeFormat.GVCF}:
                    sentinel_hash = content_hash("7\t3\tvariant-2\tA\tT\t.\tPASS\t.")
                elif input_format == IntakeFormat.TSV:
                    sentinel_hash = content_hash("7\t3\tA\tT\tvariant-2")
                else:
                    sentinel_hash = content_hash(
                        {
                            "variant_id": "variant-2",
                            "chromosome": "7",
                            "position": 3,
                            "reference": "A",
                            "alternate": "T",
                        }
                    )
                self.assertEqual(overflow[0].raw_hash, sentinel_hash)

                replay = VariantIntake(max_records=2).parse_text(
                    text,
                    source_id=f"overflow-{input_format}",
                    input_format=input_format,
                )
                self.assertEqual(batch.receipt.content_address, replay.receipt.content_address)
                self.assertEqual(batch.content_address, replay.content_address)

    def test_vcf_auxiliary_limit_emits_one_addressed_error_and_stops(self) -> None:
        sources = (
            (
                "\n".join(
                    (
                        "##fileformat=VCFv4.3",
                        "##source=one",
                        "##source=overflow",
                        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO",
                        "7\t1\tv1\tA\tT\t.\tPASS\t.",
                    )
                ),
                3,
                content_hash("##source=overflow"),
            ),
            (
                "\n\n\n##fileformat=VCFv4.3\n"
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
                "7\t1\tv1\tA\tT\t.\tPASS\t.",
                3,
                content_hash(""),
            ),
        )
        for input_format in (IntakeFormat.VCF, IntakeFormat.GVCF):
            for text, line_number, sentinel_hash in sources:
                with self.subTest(input_format=input_format, line_number=line_number):
                    batch = VariantIntake(max_auxiliary_lines=2).parse_text(
                        text,
                        source_id=f"aux-{input_format}",
                        input_format=input_format,
                    )

                    self.assertTrue(batch.has_errors)
                    self.assertEqual(batch.receipt.record_count, 0)
                    self.assertEqual(batch.receipt.input_hash, content_hash(text))
                    self.assertEqual(len(batch.issues), 1)
                    issue = batch.issues[0]
                    self.assertEqual(issue.code, "max_auxiliary_lines_exceeded")
                    self.assertEqual(issue.severity, IntakeSeverity.ERROR)
                    self.assertEqual(issue.line_number, line_number)
                    self.assertEqual(issue.raw_hash, sentinel_hash)

    def test_tsv_header_and_blank_lines_share_the_auxiliary_ceiling(self) -> None:
        text = (
            "chrom\tpos\tref\talt\tvariant_id\n"
            "\n"
            "\n"
            "7\t1\tA\tT\tvariant-1\n"
        )
        batch = VariantIntake(max_auxiliary_lines=2).parse_text(
            text,
            source_id="bounded-tsv-auxiliary",
            input_format=IntakeFormat.TSV,
        )

        self.assertTrue(batch.has_errors)
        self.assertEqual(batch.receipt.record_count, 0)
        self.assertEqual(batch.receipt.input_hash, content_hash(text))
        self.assertEqual(len(batch.issues), 1)
        issue = batch.issues[0]
        self.assertEqual(issue.code, "max_auxiliary_lines_exceeded")
        self.assertEqual(issue.line_number, 3)
        self.assertEqual(issue.raw_hash, content_hash(""))

    def test_format_detection_stops_after_leading_blank_line_sentinel(self) -> None:
        text = (
            "\n\n\n##fileformat=VCFv4.3\n"
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
            "7\t1\tv1\tA\tT\t.\tPASS\t."
        )
        with self.assertRaisesRegex(
            ValidationError,
            "max_auxiliary_lines_exceeded",
        ):
            VariantIntake(max_auxiliary_lines=2).parse_text(
                text,
                source_id="auto-detect-limit",
            )

    def test_json_rejects_duplicate_keys_and_non_finite_numbers(self) -> None:
        invalid = (
            (
                '{"variants":[{"chromosome":"7","chromosome":"8",'
                '"position":1,"reference":"A","alternate":"T"}]}',
                "duplicate_json_key",
            ),
            (
                '{"variants":[{"chromosome":"7","position":NaN,'
                '"reference":"A","alternate":"T"}]}',
                "non_finite_json_number",
            ),
            (
                '{"variants":[{"chromosome":"7","position":Infinity,'
                '"reference":"A","alternate":"T"}]}',
                "non_finite_json_number",
            ),
            (
                '{"variants":[{"chromosome":"7","position":-Infinity,'
                '"reference":"A","alternate":"T"}]}',
                "non_finite_json_number",
            ),
            (
                '{"variants":[{"chromosome":"7","position":1e999,'
                '"reference":"A","alternate":"T"}]}',
                "non_finite_json_number",
            ),
        )
        for text, code in invalid:
            with self.subTest(code=code, text=text):
                batch = VariantIntake(max_records=1).parse_text(
                    text,
                    source_id="strict-json",
                    input_format=IntakeFormat.JSON,
                )

                self.assertTrue(batch.has_errors)
                self.assertEqual(batch.variants, ())
                self.assertEqual(batch.receipt.record_count, 0)
                self.assertEqual(batch.receipt.input_hash, content_hash(text))
                self.assertEqual(batch.issues[0].code, code)
                self.assertEqual(batch.issues[0].severity, IntakeSeverity.ERROR)

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
