from __future__ import annotations

import json
import random
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import patch

from glio_noncode.bcf import BcfDocument, BcfRecord
from glio_noncode.errors import ValidationError
from glio_noncode.intake import (
    MAX_REFERENCE_COVERAGE_PROVENANCE_REFERENCES,
    MAX_VARIANT_INDEX_RECORDS,
    MAX_VARIANT_INTAKE_AUXILIARY_LINES,
    MAX_VARIANT_INTAKE_RECORDS,
    IntakeFormat,
    IntakeSeverity,
    ReferenceBlockCallState,
    ReferenceBlockIndex,
    ReferenceBlockRecord,
    ReferenceBlockSpanSource,
    ReferenceCoverageState,
    ReferenceCoverageStatus,
    VariantIndex,
    VariantIntake,
)
from glio_noncode.models import ReferenceContext, VariantIdentity, VariantKind
from glio_noncode.serialization import content_hash


class IntakeTests(unittest.TestCase):
    @staticmethod
    def _reference_block(
        block_id: str,
        start: int,
        end: int,
        *,
        call_state: ReferenceBlockCallState = ReferenceBlockCallState.REFERENCE,
        sample_id: str | None = "S1",
        genome_build: str = "GRCh38",
        chromosome: str = "7",
    ) -> ReferenceBlockRecord:
        return ReferenceBlockRecord(
            source_id="reference-block-fixture",
            record_id=block_id,
            source_line=int(block_id.removeprefix("block-")),
            raw_hash=content_hash({"block": block_id}),
            genome_build=genome_build,
            chromosome=chromosome,
            start=start,
            end=end,
            reference="A",
            alternate="<*>",
            sample_id=sample_id,
            genotype={
                ReferenceBlockCallState.REFERENCE: "0/0",
                ReferenceBlockCallState.NO_CALL: "./.",
                ReferenceBlockCallState.UNKNOWN: None,
            }[call_state],
            call_state=call_state,
            span_source=ReferenceBlockSpanSource.FORMAT_LEN,
        )

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

    def test_vcf_multiallelic_records_are_filtered_by_selected_genotype(self) -> None:
        text = "\n".join(
            (
                "##fileformat=VCFv4.3",
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE_A",
                "7\t55249071\trs-test\tA\tT,C\t99\tPASS\t.\tGT\t0/2",
            )
        )
        batch = VariantIntake().parse_text(text, source_id="selected-allele", input_format="vcf")
        self.assertEqual([variant.alternate for variant in batch.variants], ["C"])
        self.assertEqual(
            [issue.code for issue in batch.issues],
            ["alternate_not_in_selected_genotype"],
        )
        self.assertEqual(batch.receipt.accepted_count, 1)

    def test_vcf_missing_requested_sample_does_not_fall_back_to_first_sample(self) -> None:
        text = "\n".join(
            (
                "##fileformat=VCFv4.3",
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE_A\tSAMPLE_B",
                "7\t55249071\trs-test\tA\tT,C\t99\tPASS\t.\tGT\t1/1\t0/2",
            )
        )
        batch = VariantIntake().parse_text(
            text,
            source_id="missing-sample",
            input_format="vcf",
            sample_id="SAMPLE_MISSING",
        )
        self.assertEqual(batch.variants, ())
        self.assertEqual(batch.receipt.record_count, 1)
        self.assertEqual(batch.issues[0].code, "sample_not_found")
        self.assertEqual(batch.issues[0].severity, IntakeSeverity.ERROR)

    def test_vcf_requires_explicit_selection_for_multiple_samples(self) -> None:
        text = "\n".join(
            (
                "##fileformat=VCFv4.3",
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE_A\tSAMPLE_B",
                "7\t55249071\trs-test\tA\tT,C\t99\tPASS\t.\tGT\t1/1\t0/2",
            )
        )
        batch = VariantIntake().parse_text(text, source_id="ambiguous-samples", input_format="vcf")
        self.assertEqual(batch.variants, ())
        self.assertEqual(batch.issues[0].code, "sample_selection_required")
        self.assertEqual(batch.issues[0].severity, IntakeSeverity.ERROR)

    def test_vcf_duplicate_sample_id_is_rejected_even_when_selected_explicitly(self) -> None:
        text = "\n".join(
            (
                "##fileformat=VCFv4.3",
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE_A\tSAMPLE_A",
                "7\t55249071\trs-test\tA\tT,C\t99\tPASS\t.\tGT\t1/1\t0/2",
            )
        )
        batch = VariantIntake().parse_text(
            text,
            source_id="duplicate-sample-id",
            input_format="vcf",
            sample_id="SAMPLE_A",
        )
        self.assertEqual(batch.variants, ())
        self.assertEqual(batch.issues[0].code, "duplicate_sample_id")
        self.assertEqual(batch.issues[0].severity, IntakeSeverity.ERROR)

    def test_vcf_duplicate_format_keys_are_rejected(self) -> None:
        text = "\n".join(
            (
                "##fileformat=VCFv4.3",
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE_A",
                "7\t55249071\trs-test\tA\tT,C\t99\tPASS\t.\tGT:GT\t1/1:0/2",
            )
        )
        batch = VariantIntake().parse_text(
            text,
            source_id="duplicate-format-key",
            input_format="vcf",
            sample_id="SAMPLE_A",
        )
        self.assertEqual(batch.variants, ())
        self.assertEqual(batch.issues[0].code, "duplicate_format_key")
        self.assertEqual(batch.issues[0].severity, IntakeSeverity.ERROR)

    def test_vcf_rejects_invalid_format_key_and_nonleading_gt(self) -> None:
        cases = (
            ("GT:DP+", "0/1:5", "invalid_format_key"),
            ("DP:GT", "5:0/1", "genotype_format_key_not_first"),
        )
        for format_field, sample_field, expected_issue in cases:
            with self.subTest(format_field=format_field):
                text = "\n".join(
                    (
                        "##fileformat=VCFv4.3",
                        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE_A",
                        f"7\t55249071\trs-test\tA\tT,C\t99\tPASS\t.\t{format_field}\t{sample_field}",
                    )
                )
                batch = VariantIntake().parse_text(
                    text,
                    source_id="invalid-format-key",
                    input_format="vcf",
                    sample_id="SAMPLE_A",
                )
                self.assertEqual(batch.variants, ())
                self.assertEqual(batch.issues[0].code, expected_issue)
                self.assertEqual(batch.issues[0].severity, IntakeSeverity.ERROR)

    def test_vcf_missing_selected_sample_column_rejects_the_record(self) -> None:
        text = "\n".join(
            (
                "##fileformat=VCFv4.3",
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE_A",
                "7\t55249071\trs-test\tA\tT,C\t99\tPASS\t.\tGT",
            )
        )
        batch = VariantIntake().parse_text(
            text,
            source_id="missing-sample-cell",
            input_format="vcf",
            sample_id="SAMPLE_A",
        )
        self.assertEqual(batch.variants, ())
        self.assertEqual(batch.issues[0].code, "sample_data_missing")
        self.assertEqual(batch.issues[0].severity, IntakeSeverity.ERROR)

    def test_vcf_single_dot_sample_cell_is_a_missing_gt_not_a_called_alt(self) -> None:
        text = "\n".join(
            (
                "##fileformat=VCFv4.3",
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE_A",
                "7\t55249071\trs-test\tA\tT\t99\tPASS\t.\tGT:DP\t.",
            )
        )
        batch = VariantIntake().parse_text(text, source_id="dot-sample", input_format="vcf")
        self.assertEqual(batch.variants, ())
        self.assertEqual(batch.issues[0].code, "no_call_genotype")

        retained = VariantIntake().parse_text(
            text,
            source_id="dot-sample-opt-in",
            input_format="vcf",
            include_no_call=True,
        )
        self.assertEqual(len(retained.variants), 1)

    def test_vcf_empty_or_excess_sample_subfields_are_errors(self) -> None:
        cases = (
            ("GT", "", "sample_data_missing"),
            ("GT", "0/1:8", "sample_data_excess_fields"),
            ("GT:DP:PS", "0/1::5", "sample_data_empty_field"),
            ("GT:DP", "0/1:", "sample_data_empty_field"),
        )
        for format_field, sample_field, expected_issue in cases:
            with self.subTest(sample_field=sample_field):
                text = "\n".join(
                    (
                        "##fileformat=VCFv4.3",
                        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE_A",
                        f"7\t55249071\trs-test\tA\tT\t99\tPASS\t.\t{format_field}\t{sample_field}",
                    )
                )
                batch = VariantIntake().parse_text(
                    text,
                    source_id="malformed-sample-value",
                    input_format="vcf",
                )
                self.assertEqual(batch.variants, ())
                self.assertEqual(batch.issues[0].code, expected_issue)

    def test_vcf_alt_dot_is_a_no_variant_site(self) -> None:
        text = "\n".join(
            (
                "##fileformat=VCFv4.3",
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE_A",
                "7\t55249071\trs-none\tA\t.\t99\tPASS\t.\tGT\t0/0",
            )
        )
        batch = VariantIntake().parse_text(text, source_id="no-alternate", input_format="vcf")
        self.assertEqual(batch.variants, ())
        self.assertEqual(batch.issues[0].code, "no_alternate_allele")
        self.assertEqual(batch.issues[0].severity, IntakeSeverity.WARNING)

    def test_vcf_spanning_deletion_star_is_deferred_not_normalized_as_cnv(self) -> None:
        text = "\n".join(
            (
                "##fileformat=VCFv4.3",
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE_A",
                "7\t55249071\trs-star\tA\t*\t99\tPASS\t.\tGT\t0/1",
            )
        )
        batch = VariantIntake().parse_text(text, source_id="spanning-deletion", input_format="vcf")
        self.assertEqual(batch.variants, ())
        self.assertEqual(len(batch.deferred_records), 1)
        self.assertEqual(batch.issues[0].code, "unsupported_symbolic_allele")

    def test_vcf_dot_cannot_be_combined_with_other_alt_alleles(self) -> None:
        text = "\n".join(
            (
                "##fileformat=VCFv4.3",
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO",
                "7\t55249071\trs-invalid\tA\t.,T\t99\tPASS\t.",
            )
        )
        batch = VariantIntake().parse_text(text, source_id="mixed-no-alternate", input_format="vcf")
        self.assertEqual(batch.variants, ())
        self.assertEqual(batch.issues[0].code, "invalid_alternate")

    def test_vcf_info_values_are_preserved_without_implicit_type_inference(self) -> None:
        text = "\n".join(
            (
                "##fileformat=VCFv4.3",
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO",
                "7\t55249071\trs-info\tA\tT\t99\tPASS\tDP=12;AF=0.25,0.75;DB",
            )
        )
        batch = VariantIntake().parse_text(text, source_id="info-preservation", input_format="vcf")
        self.assertEqual(len(batch.variants), 1)
        self.assertEqual(
            batch.variants[0].annotations["info"],
            {"DP": "12", "AF": ["0.25", "0.75"], "DB": True},
        )

    def test_vcf_duplicate_info_key_is_rejected_instead_of_overwritten(self) -> None:
        text = "\n".join(
            (
                "##fileformat=VCFv4.3",
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO",
                "7\t55249071\trs-info\tA\tT\t99\tPASS\tDP=12;DP=18",
            )
        )
        batch = VariantIntake().parse_text(text, source_id="duplicate-info", input_format="vcf")
        self.assertEqual(batch.variants, ())
        self.assertEqual(batch.issues[0].code, "duplicate_info_key")

    def test_vcf_declared_info_schema_checks_type_and_allele_cardinality(self) -> None:
        prefix = "\n".join(
            (
                "##fileformat=VCFv4.3",
                '##INFO=<ID=DP,Number=1,Type=Integer,Description="read depth">',
                '##INFO=<ID=AF,Number=A,Type=Float,Description="allele frequency">',
                '##INFO=<ID=DB,Number=0,Type=Flag,Description="database membership">',
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO",
            )
        )
        valid = prefix + "\n7\t10\trs-info\tA\tT,G\t50\tPASS\tDP=12;AF=0.25,0.75;DB"
        batch = VariantIntake().parse_text(valid, source_id="declared-info", input_format="vcf")
        self.assertEqual(len(batch.variants), 2)
        self.assertEqual(
            batch.records[0].info,
            {"DP": "12", "AF": ["0.25", "0.75"], "DB": True},
        )

        malformed = (
            ("DP=depth;AF=0.25,0.75;DB", "info_type_mismatch"),
            ("DP=12;AF=0.25;DB", "info_number_mismatch"),
            ("DP=12;AF=0.25,0.75;DB=1", "info_type_mismatch"),
        )
        for info_text, expected_issue in malformed:
            with self.subTest(info_text=info_text):
                text = prefix + f"\n7\t10\trs-info\tA\tT,G\t50\tPASS\t{info_text}"
                parsed = VariantIntake().parse_text(
                    text,
                    source_id="invalid-declared-info",
                    input_format="vcf",
                )
                self.assertEqual(parsed.variants, ())
                self.assertEqual(parsed.issues[-1].code, expected_issue)

    def test_vcf_declared_format_schema_checks_selected_sample_values(self) -> None:
        prefix = "\n".join(
            (
                "##fileformat=VCFv4.3",
                '##FORMAT=<ID=GT,Number=1,Type=String,Description="genotype">',
                '##FORMAT=<ID=AD,Number=R,Type=Integer,Description="allele depth">',
                '##FORMAT=<ID=AF,Number=A,Type=Float,Description="allele frequency">',
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE_A",
            )
        )
        valid = prefix + "\n7\t10\trs-format\tA\tT\t50\tPASS\t.\tGT:AD:AF\t0/1:10,5:0.25"
        parsed = VariantIntake().parse_text(
            valid, source_id="declared-format", input_format="vcf"
        )
        self.assertEqual(len(parsed.variants), 1)

        malformed = (
            ("0/1:10:0.25", "format_number_mismatch"),
            ("0/1:10,5:bad", "format_type_mismatch"),
        )
        for sample_text, expected_issue in malformed:
            with self.subTest(sample_text=sample_text):
                text = prefix + f"\n7\t10\trs-format\tA\tT\t50\tPASS\t.\tGT:AD:AF\t{sample_text}"
                result = VariantIntake().parse_text(
                    text, source_id="invalid-declared-format", input_format="vcf"
                )
                self.assertEqual(result.variants, ())
                self.assertEqual(result.issues[-1].code, expected_issue)

    def test_vcf_invalid_gt_index_is_an_error_and_emits_no_alternates(self) -> None:
        text = "\n".join(
            (
                "##fileformat=VCFv4.3",
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE_A",
                "7\t55249071\trs-test\tA\tT,C\t99\tPASS\t.\tGT\t0/3",
            )
        )
        batch = VariantIntake().parse_text(text, source_id="invalid-gt", input_format="vcf")
        self.assertEqual(batch.variants, ())
        self.assertTrue(batch.has_errors)
        self.assertEqual(batch.issues[0].code, "invalid_genotype")

    def test_included_partial_no_call_retains_all_alternates_for_review(self) -> None:
        text = "\n".join(
            (
                "##fileformat=VCFv4.3",
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE_A",
                "7\t55249071\trs-test\tA\tT,C\t99\tPASS\t.\tGT\t./2",
            )
        )
        batch = VariantIntake().parse_text(
            text,
            source_id="included-partial-call",
            input_format="vcf",
            include_no_call=True,
        )
        self.assertEqual({variant.alternate for variant in batch.variants}, {"T", "C"})
        self.assertNotIn("reference_genotype", {issue.code for issue in batch.issues})

    def test_bcf_multiallelic_records_follow_the_decoded_sample_genotype(self) -> None:
        record = BcfRecord(
            record_index=0,
            chromosome="7",
            position=100,
            reference="A",
            alternates=("T", "C"),
            record_id="bcf-test",
            quality=42.0,
            filters=("PASS",),
            info={},
            samples={"SAMPLE_A": {"GT": "0/2"}, "SAMPLE_B": {"GT": "1/1"}},
            raw_hash=content_hash("bcf-record"),
        )
        document = BcfDocument(
            version="2.2",
            header_text=(
                "##fileformat=VCFv4.3\n"
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE_A\tSAMPLE_B\n"
            ),
            contigs=("7",),
            filter_names=(),
            info_names=(),
            format_names=("GT",),
            samples=("SAMPLE_A", "SAMPLE_B"),
            records=(record,),
            bgzf_blocks=0,
            input_hash=content_hash("bcf-input"),
            content_address=content_hash("bcf-document"),
        )
        parser = VariantIntake()
        with patch("glio_noncode.intake.BcfReader.read", return_value=document):
            batch = parser.parse_bytes(
                b"test-double",
                source_id="selected-bcf-allele",
                sample_id="SAMPLE_A",
            )
            missing_sample_batch = parser.parse_bytes(
                b"test-double",
                source_id="missing-bcf-sample",
                sample_id="SAMPLE_MISSING",
            )
            no_selection_batch = parser.parse_bytes(
                b"test-double",
                source_id="ambiguous-bcf-samples",
            )
        self.assertEqual([variant.alternate for variant in batch.variants], ["C"])
        self.assertEqual(batch.issues[0].code, "alternate_not_in_selected_genotype")
        self.assertEqual(missing_sample_batch.variants, ())
        self.assertEqual(missing_sample_batch.receipt.record_count, 1)
        self.assertEqual(missing_sample_batch.issues[0].code, "sample_not_found")
        self.assertEqual(missing_sample_batch.issues[0].severity, IntakeSeverity.ERROR)
        self.assertEqual(no_selection_batch.variants, ())
        self.assertEqual(no_selection_batch.issues[0].code, "sample_selection_required")
        self.assertEqual(no_selection_batch.issues[0].severity, IntakeSeverity.ERROR)

        duplicate_document = replace(
            document,
            header_text=(
                "##fileformat=VCFv4.3\n"
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE_A\tSAMPLE_A\n"
            ),
            samples=("SAMPLE_A", "SAMPLE_A"),
        )
        with patch("glio_noncode.intake.BcfReader.read", return_value=duplicate_document):
            duplicate_sample_batch = parser.parse_bytes(
                b"test-double",
                source_id="duplicate-bcf-sample-id",
                sample_id="SAMPLE_A",
            )
        self.assertEqual(duplicate_sample_batch.variants, ())
        self.assertEqual(duplicate_sample_batch.issues[0].code, "duplicate_sample_id")
        self.assertEqual(duplicate_sample_batch.issues[0].severity, IntakeSeverity.ERROR)

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

    def test_gvcf_format_len_takes_precedence_and_stays_out_of_variant_rows(self) -> None:
        text = "\n".join(
            (
                "##fileformat=VCFv4.5",
                '##INFO=<ID=END,Number=1,Type=Integer,Description="Inclusive interval end">',
                '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">',
                '##FORMAT=<ID=LEN,Number=1,Type=Integer,Description="Reference block length">',
                '##FORMAT=<ID=DP,Number=1,Type=Integer,Description="Read depth">',
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1",
                "7\t4370\t.\tG\t<*>\t.\tPASS\tEND=4390\tGT:LEN:DP\t0/0:14:25",
            )
        )
        batch = VariantIntake().parse_text(
            text,
            source_id="reference-confidence-vcf",
            genome_build="GRCh38",
            input_format=IntakeFormat.GVCF,
        )

        self.assertEqual(batch.variants, ())
        self.assertEqual(batch.records, ())
        self.assertEqual(batch.deferred_records, ())
        self.assertEqual(batch.issues, ())
        self.assertEqual(batch.receipt.record_count, 1)
        self.assertEqual(batch.receipt.accepted_count, 0)
        self.assertEqual(batch.receipt.reference_block_count, 1)
        block = batch.reference_blocks[0]
        self.assertEqual((block.start, block.end, block.length), (4369, 4383, 14))
        self.assertEqual(block.alternate, "<*>")
        self.assertEqual(block.sample_id, "S1")
        self.assertEqual(block.genotype, "0/0")
        self.assertEqual(block.call_state, ReferenceBlockCallState.REFERENCE)
        self.assertEqual(block.span_source, ReferenceBlockSpanSource.FORMAT_LEN)
        self.assertEqual(block.sample_values["DP"], "25")
        self.assertEqual(block.info["END"], "4390")
        with self.assertRaisesRegex(TypeError, "immutable"):
            block.sample_values["LEN"] = "999"
        self.assertTrue(batch.reference_block_address.startswith("intake-reference-block-set:"))

    def test_gvcf_info_end_fallback_retains_no_call_reference_block(self) -> None:
        text = "\n".join(
            (
                "##fileformat=VCFv4.5",
                '##INFO=<ID=END,Number=1,Type=Integer,Description="Inclusive interval end">',
                '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">',
                '##FORMAT=<ID=LEN,Number=1,Type=Integer,Description="Reference block length">',
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1",
                "7\t100\t.\tC\t<NON_REF>\t.\tPASS\tEND=105\tGT:LEN\t./.:.",
            )
        )
        batch = VariantIntake().parse_text(
            text,
            source_id="legacy-reference-confidence-vcf",
            input_format=IntakeFormat.GVCF,
        )

        self.assertEqual(batch.variants, ())
        self.assertEqual(batch.receipt.reference_block_count, 1)
        self.assertEqual(batch.issues, ())
        block = batch.reference_blocks[0]
        self.assertEqual((block.start, block.end, block.length), (99, 105, 6))
        self.assertEqual(block.span_source, ReferenceBlockSpanSource.INFO_END)
        self.assertEqual(block.call_state, ReferenceBlockCallState.NO_CALL)
        self.assertEqual(block.genotype, "./.")

    def test_gvcf_selects_sample_specific_format_len(self) -> None:
        text = "\n".join(
            (
                "##fileformat=VCFv4.5",
                '##INFO=<ID=END,Number=1,Type=Integer,Description="Inclusive interval end">',
                '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">',
                '##FORMAT=<ID=LEN,Number=1,Type=Integer,Description="Reference block length">',
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\tS2",
                "7\t100\t.\tC\t<*>\t.\tPASS\tEND=105\tGT:LEN\t0/0:7\t0/0:14",
            )
        )
        batch = VariantIntake().parse_text(
            text,
            source_id="multi-sample-reference-confidence-vcf",
            input_format=IntakeFormat.GVCF,
            sample_id="S2",
        )

        self.assertEqual(len(batch.reference_blocks), 1)
        self.assertEqual(batch.reference_blocks[0].sample_id, "S2")
        self.assertEqual(
            (batch.reference_blocks[0].start, batch.reference_blocks[0].end),
            (99, 113),
        )
        self.assertEqual(batch.reference_blocks[0].span_source, ReferenceBlockSpanSource.FORMAT_LEN)

    def test_gvcf_invalid_format_len_is_an_error_not_an_end_fallback(self) -> None:
        text = "\n".join(
            (
                "##fileformat=VCFv4.5",
                '##INFO=<ID=END,Number=1,Type=Integer,Description="Inclusive interval end">',
                '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">',
                '##FORMAT=<ID=LEN,Number=1,Type=Integer,Description="Reference block length">',
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1",
                "7\t100\t.\tC\t<*>\t.\tPASS\tEND=105\tGT:LEN\t0/0:0",
            )
        )
        batch = VariantIntake().parse_text(
            text,
            source_id="invalid-reference-confidence-vcf",
            input_format=IntakeFormat.GVCF,
        )

        self.assertEqual(batch.variants, ())
        self.assertEqual(batch.reference_blocks, ())
        self.assertTrue(batch.has_errors)
        self.assertEqual(batch.issues[0].code, "invalid_reference_block_span")
        self.assertEqual(batch.receipt.rejected_count, 1)

    def test_multiallelic_record_with_non_ref_is_not_a_reference_block(self) -> None:
        text = "\n".join(
            (
                "##fileformat=VCFv4.5",
                '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">',
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1",
                "7\t100\tconcrete-and-block\tC\tT,<*>\t.\tPASS\t.\tGT\t0/1",
            )
        )
        batch = VariantIntake().parse_text(
            text,
            source_id="mixed-symbolic-record",
            input_format=IntakeFormat.GVCF,
        )

        self.assertEqual([item.alternate for item in batch.variants], ["T"])
        self.assertEqual(batch.reference_blocks, ())

    def test_reference_block_index_partitions_query_and_reports_base_counts(self) -> None:
        blocks = (
            self._reference_block("block-1", 10, 15),
            self._reference_block("block-2", 15, 20),
            self._reference_block(
                "block-3", 25, 28, call_state=ReferenceBlockCallState.NO_CALL
            ),
            self._reference_block("block-4", 28, 31, call_state=ReferenceBlockCallState.UNKNOWN),
        )
        result = ReferenceBlockIndex(blocks).coverage(
            "GRCh38", "chr7", 8, 33, sample_id="S1"
        )

        self.assertEqual(result.status, ReferenceCoverageStatus.PARTIAL)
        self.assertEqual(
            [(item.start, item.end, item.state) for item in result.segments],
            [
                (8, 10, ReferenceCoverageState.UNCOVERED),
                (10, 15, ReferenceCoverageState.REFERENCE),
                (15, 20, ReferenceCoverageState.REFERENCE),
                (20, 25, ReferenceCoverageState.UNCOVERED),
                (25, 28, ReferenceCoverageState.NO_CALL),
                (28, 31, ReferenceCoverageState.UNKNOWN),
                (31, 33, ReferenceCoverageState.UNCOVERED),
            ],
        )
        self.assertEqual(
            result.base_counts,
            {"reference": 10, "no_call": 3, "unknown": 3, "uncovered": 9, "conflict": 0},
        )
        self.assertEqual(result.chromosome, "chr7")
        self.assertEqual(result.to_dict()["coordinate_system"], "zero_based_half_open")
        self.assertTrue(result.content_address.startswith("intake-reference-coverage:"))

        mixed = ReferenceBlockIndex(
            (
                self._reference_block("block-5", 0, 5),
                self._reference_block("block-6", 5, 10, call_state=ReferenceBlockCallState.UNKNOWN),
            )
        ).coverage("GRCh38", "7", 0, 10, sample_id="S1")
        self.assertEqual(mixed.status, ReferenceCoverageStatus.MIXED)
        self.assertEqual(sum(mixed.base_counts.values()), 10)

    def test_reference_block_index_queries_parsed_gvcf_blocks_end_to_end(self) -> None:
        text = "\n".join(
            (
                "##fileformat=VCFv4.5",
                '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">',
                '##FORMAT=<ID=LEN,Number=1,Type=Integer,Description="Reference block length">',
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1",
                "7\t101\t.\tA\t<*>\t.\tPASS\t.\tGT:LEN\t0/0:5",
                "7\t103\t.\tA\t<NON_REF>\t.\tPASS\t.\tGT:LEN\t./.:5",
            )
        )
        batch = VariantIntake().parse_text(
            text,
            source_id="indexed-gvcf-fixture",
            genome_build="GRCh38",
            input_format=IntakeFormat.GVCF,
            sample_id="S1",
        )

        result = ReferenceBlockIndex(batch.reference_blocks).coverage(
            "GRCh38", "7", 100, 107, sample_id="S1"
        )

        self.assertEqual(batch.receipt.reference_block_count, 2)
        self.assertEqual(result.status, ReferenceCoverageStatus.CONFLICTING)
        self.assertEqual(
            [(item.start, item.end, item.state) for item in result.segments],
            [
                (100, 102, ReferenceCoverageState.REFERENCE),
                (102, 105, ReferenceCoverageState.CONFLICT),
                (105, 107, ReferenceCoverageState.NO_CALL),
            ],
        )
        self.assertEqual(result.base_counts["reference"], 2)
        self.assertEqual(result.base_counts["conflict"], 3)
        self.assertEqual(result.base_counts["no_call"], 2)

    def test_reference_block_index_keeps_sample_and_build_partitions_separate(self) -> None:
        index = ReferenceBlockIndex(
            (
                self._reference_block("block-1", 0, 10, sample_id="S1"),
                self._reference_block(
                    "block-2", 0, 10, sample_id="S2", call_state=ReferenceBlockCallState.NO_CALL
                ),
                self._reference_block("block-3", 0, 10, genome_build="GRCh37"),
                self._reference_block(
                    "block-4", 0, 10, sample_id=None, call_state=ReferenceBlockCallState.UNKNOWN
                ),
            )
        )

        reference = index.coverage("GRCh38", "7", 0, 10, sample_id="S1")
        no_call = index.coverage("GRCh38", "7", 0, 10, sample_id="S2")
        other_build = index.coverage("GRCh37", "7", 0, 10, sample_id="S1")
        no_sample = index.coverage("GRCh38", "7", 0, 10, sample_id=None)

        self.assertEqual(reference.status, ReferenceCoverageStatus.COMPLETE_REFERENCE)
        self.assertEqual(no_call.status, ReferenceCoverageStatus.COMPLETE_NO_CALL)
        self.assertEqual(other_build.status, ReferenceCoverageStatus.COMPLETE_REFERENCE)
        self.assertEqual(no_sample.status, ReferenceCoverageStatus.COMPLETE_UNKNOWN)
        self.assertEqual(reference.sample_id, "S1")
        self.assertEqual(other_build.genome_build, "GRCh37")
        self.assertEqual(
            index.overlap("GRCh38", "7", 0, 10, sample_id="S1")[0].record_id,
            "block-1",
        )

    def test_reference_block_index_queries_single_base_variant_coordinates(self) -> None:
        index = ReferenceBlockIndex(
            (
                self._reference_block("block-1", 100, 101),
                self._reference_block(
                    "block-2", 101, 102, call_state=ReferenceBlockCallState.NO_CALL
                ),
            )
        )
        variant = VariantIdentity(
            variant_id="variant-position-101",
            kind=VariantKind.SNV,
            chromosome="chr7",
            start=101,
            end=101,
            reference="A",
            alternate="T",
            genome_build="GRCh38",
        )

        result = index.coverage_for_variant(variant, sample_id="S1")

        self.assertEqual((result.start, result.end), (100, 101))
        self.assertEqual(result.chromosome, "chr7")
        self.assertEqual(result.status, ReferenceCoverageStatus.COMPLETE_REFERENCE)
        self.assertEqual(result.base_counts["reference"], 1)
        self.assertEqual(result.base_counts["no_call"], 0)
        self.assertEqual(result.block_addresses, (index.all()[0].content_address,))

    def test_reference_block_index_queries_multibase_variant_and_keeps_build_exact(self) -> None:
        index = ReferenceBlockIndex((self._reference_block("block-1", 10, 13),))
        variant = VariantIdentity(
            variant_id="variant-span-11-13",
            kind=VariantKind.INDEL,
            chromosome="7",
            start=11,
            end=13,
            reference="ATC",
            alternate="A",
            genome_build="GRCh38",
        )

        result = index.coverage_for_variant(variant, sample_id="S1")
        other_build = index.coverage_for_variant(
            replace(variant, genome_build="GRCh37"), sample_id="S1"
        )

        self.assertEqual((result.start, result.end), (10, 13))
        self.assertEqual(result.base_counts["reference"], 3)
        self.assertEqual(result.status, ReferenceCoverageStatus.COMPLETE_REFERENCE)
        self.assertEqual(other_build.status, ReferenceCoverageStatus.UNCOVERED)
        self.assertEqual(other_build.genome_build, "GRCh37")

    def test_reference_block_index_variant_query_rejects_untyped_input(self) -> None:
        index = ReferenceBlockIndex((self._reference_block("block-1", 0, 1),))

        with self.assertRaisesRegex(ValidationError, "VariantIdentity"):
            index.coverage_for_variant(object(), sample_id="S1")  # type: ignore[arg-type]

    def test_reference_block_index_marks_overlapping_call_states_conflicting(self) -> None:
        index = ReferenceBlockIndex(
            (
                self._reference_block("block-1", 100, 110),
                self._reference_block(
                    "block-2", 105, 115, call_state=ReferenceBlockCallState.NO_CALL
                ),
            )
        )

        result = index.coverage("GRCh38", "7", 100, 115, sample_id="S1")

        self.assertEqual(result.status, ReferenceCoverageStatus.CONFLICTING)
        self.assertEqual(
            [(item.start, item.end, item.state) for item in result.segments],
            [
                (100, 105, ReferenceCoverageState.REFERENCE),
                (105, 110, ReferenceCoverageState.CONFLICT),
                (110, 115, ReferenceCoverageState.NO_CALL),
            ],
        )
        self.assertEqual(result.base_counts["conflict"], 5)
        self.assertEqual(len(result.segments[1].block_addresses), 2)

    def test_reference_block_index_does_not_call_same_state_overlap_a_conflict(self) -> None:
        index = ReferenceBlockIndex(
            (
                self._reference_block("block-1", 100, 110),
                self._reference_block("block-2", 105, 115),
            )
        )

        result = index.coverage("GRCh38", "7", 100, 115, sample_id="S1")

        self.assertEqual(result.status, ReferenceCoverageStatus.COMPLETE_REFERENCE)
        self.assertEqual(result.base_counts["reference"], 15)
        self.assertEqual(result.base_counts["conflict"], 0)
        self.assertEqual(len(result.segments[1].block_addresses), 2)

    def test_reference_block_index_is_deterministic_and_respects_half_open_edges(self) -> None:
        first = self._reference_block("block-1", 10, 20)
        second = self._reference_block("block-2", 20, 30)
        forward = ReferenceBlockIndex((first, second))
        reverse = ReferenceBlockIndex((second, first))

        self.assertEqual(forward.content_address, reverse.content_address)
        self.assertEqual(forward.all(), reverse.all())
        self.assertEqual(forward.overlap("GRCh38", "7", 20, 25, sample_id="S1"), (second,))
        self.assertEqual(forward.overlap("GRCh38", "7", 9, 10, sample_id="S1"), ())
        uncovered = forward.coverage("GRCh38", "7", 40, 50, sample_id="S1")
        self.assertEqual(uncovered.status, ReferenceCoverageStatus.UNCOVERED)
        self.assertEqual(uncovered.base_counts["uncovered"], 10)

    def test_reference_block_index_matches_brute_force_interval_oracle(self) -> None:
        generator = random.Random(20260922)
        call_states = tuple(ReferenceBlockCallState)
        blocks = tuple(
            self._reference_block(
                f"block-{index + 1}",
                start := generator.randrange(0, 180),
                start + generator.randrange(1, 35),
                call_state=generator.choice(call_states),
                sample_id=generator.choice(("S1", "S2")),
                genome_build=generator.choice(("GRCh37", "GRCh38")),
            )
            for index in range(80)
        )
        index = ReferenceBlockIndex(blocks)

        for _ in range(40):
            build = generator.choice(("GRCh37", "GRCh38"))
            sample_id = generator.choice(("S1", "S2"))
            start = generator.randrange(0, 160)
            end = start + generator.randrange(1, 30)
            expected_blocks = tuple(
                sorted(
                    (
                        block
                        for block in blocks
                        if block.genome_build == build
                        and block.sample_id == sample_id
                        and block.chromosome == "7"
                        and block.start < end
                        and block.end > start
                    ),
                    key=lambda item: (item.start, item.end, item.content_address),
                )
            )
            actual_blocks = index.overlap(build, "7", start, end, sample_id=sample_id)
            self.assertEqual(actual_blocks, expected_blocks)

            result = index.coverage(build, "7", start, end, sample_id=sample_id)
            actual_states = [
                segment.state
                for segment in result.segments
                for _ in range(segment.length)
            ]
            expected_states: list[ReferenceCoverageState] = []
            for position in range(start, end):
                active_states = {
                    block.call_state
                    for block in expected_blocks
                    if block.start <= position < block.end
                }
                if len(active_states) > 1:
                    expected_state = ReferenceCoverageState.CONFLICT
                elif not active_states:
                    expected_state = ReferenceCoverageState.UNCOVERED
                else:
                    expected_state = ReferenceCoverageState(next(iter(active_states)).value)
                expected_states.append(expected_state)
            self.assertEqual(actual_states, expected_states)

    def test_reference_block_index_bounds_overlapping_provenance_work(self) -> None:
        block_count = 800
        blocks = tuple(
            self._reference_block(
                f"block-{index + 1}",
                index,
                block_count * 2 - index,
            )
            for index in range(block_count)
        )
        index = ReferenceBlockIndex(blocks)

        with self.assertRaisesRegex(ValidationError, "provenance budget"):
            index.coverage("GRCh38", "7", 0, block_count * 2, sample_id="S1")
        self.assertEqual(MAX_REFERENCE_COVERAGE_PROVENANCE_REFERENCES, 250_000)

    def test_reference_block_index_bounds_input_and_validates_queries(self) -> None:
        first = self._reference_block("block-1", 0, 1)
        second = self._reference_block("block-2", 1, 2)
        with self.assertRaisesRegex(ValidationError, "ceiling of 1"):
            ReferenceBlockIndex((first, second), max_records=1)
        with self.assertRaisesRegex(ValidationError, "max_records"):
            ReferenceBlockIndex((first,), max_records=True)
        with self.assertRaisesRegex(ValidationError, "only ReferenceBlockRecord"):
            ReferenceBlockIndex(("not a reference block",))  # type: ignore[arg-type]

        consumed: list[ReferenceBlockRecord] = []

        def over_limit():
            for block in (first, second, first, second):
                consumed.append(block)
                yield block

        with self.assertRaisesRegex(ValidationError, "ceiling of 2"):
            ReferenceBlockIndex(over_limit(), max_records=2)
        self.assertEqual(consumed, [first, second, first])

        index = ReferenceBlockIndex((first,))
        for start, end in ((-1, 1), (2, 1), (1, 1), (False, 2), (1, 2.0)):
            with self.subTest(start=start, end=end), self.assertRaises(ValidationError):
                index.coverage("GRCh38", "7", start, end, sample_id="S1")
        with self.assertRaisesRegex(ValidationError, "genome_build"):
            index.coverage("", "7", 0, 1, sample_id="S1")
        with self.assertRaisesRegex(ValidationError, "sample_id"):
            index.coverage("GRCh38", "7", 0, 1, sample_id=" ")

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
