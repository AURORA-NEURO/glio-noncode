from __future__ import annotations

import json
import struct
import tempfile
import unittest
import zlib
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.variant_normalization import NormalizationState
from glio_noncode.variant_stream import (
    StreamingVariantImporter,
    breakend_normalization_schema,
    iter_text_lines_from_chunks,
    normalize_breakend,
    streaming_intake_capabilities,
    streaming_intake_schema,
)


def _typed_string(value: str) -> bytes:
    raw = value.encode() + b"\x00"
    return bytes([(len(raw) << 4) | 7]) + raw


def _typed_int(value: int) -> bytes:
    return bytes([0x13]) + struct.pack("<i", value)


def _typed_int_vector(values: list[int]) -> bytes:
    return bytes([(len(values) << 4) | 3]) + b"".join(struct.pack("<i", value) for value in values)


def _raw_bcf(
    *,
    alternates: tuple[str, ...] = ("T",),
    genotype_alleles: tuple[int, ...] = (0, 1),
    sample_names: tuple[str, ...] = ("SAMPLE",),
    sample_genotype_alleles: tuple[tuple[int, ...], ...] | None = None,
    format_ids: tuple[int, ...] = (0,),
    format_names: tuple[str, ...] = ("GT",),
    format_header_overrides: dict[str, bytes] | None = None,
    phased_genotypes: bool = False,
    sample_phase_sets: tuple[int, ...] | None = None,
) -> bytes:
    sample_genotypes = sample_genotype_alleles or tuple(
        genotype_alleles for _ in sample_names
    )
    if len(sample_genotypes) != len(sample_names):
        raise ValueError("sample genotype count must match sample name count")
    format_definitions = {
        "GT": b'##FORMAT=<ID=GT,Number=1,Type=String,Description="genotype">\n',
        "DP": b'##FORMAT=<ID=DP,Number=1,Type=Integer,Description="depth">\n',
        "PS": b'##FORMAT=<ID=PS,Number=1,Type=Integer,Description="phase set">\n',
    }
    if format_header_overrides:
        format_definitions.update(format_header_overrides)
    header = (
        b"##fileformat=VCFv4.3\n"
        b"##contig=<ID=7,length=1000000>\n"
        b'##INFO=<ID=DP,Number=1,Type=Integer,Description="depth">\n'
        + b"".join(format_definitions[name] for name in format_names)
        + b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t"
        + "\t".join(sample_names).encode("utf-8")
        + b"\n"
    )
    shared = b"".join(
        (
            struct.pack("<i", 0),
            struct.pack("<i", 99),
            struct.pack("<i", 1),
            struct.pack("<f", 42.0),
            struct.pack("<I", (len(alternates) + 1) | (1 << 16)),
            struct.pack("<I", (len(format_ids) << 24) | len(sample_names)),
            _typed_string("rs1"),
            _typed_string("A"),
            *(_typed_string(alternate) for alternate in alternates),
            _typed_int_vector([0]),
            _typed_int(0),
            _typed_int(12),
        )
    )
    encoded_genotypes = [
        ((allele_index + 1) << 1) | int(phased_genotypes and allele_offset > 0)
        for genotype in sample_genotypes
        for allele_offset, allele_index in enumerate(genotype)
    ]
    if sample_phase_sets is not None and len(sample_phase_sets) != len(sample_names):
        raise ValueError("phase-set count must match sample name count")
    phase_sets = sample_phase_sets or tuple(17 for _ in sample_names)
    individual_parts: list[bytes] = []
    for format_index, format_id in enumerate(format_ids):
        format_name = format_names[format_index] if format_index < len(format_names) else ""
        if format_name == "PS":
            format_values = list(phase_sets)
        else:
            format_values = encoded_genotypes
        individual_parts.extend((_typed_int(format_id), _typed_int_vector(format_values)))
    individual = b"".join(individual_parts)
    return (
        b"BCF\x02\x02"
        + struct.pack("<I", len(header) + 1)
        + header
        + b"\x00"
        + struct.pack("<II", len(shared), len(individual))
        + shared
        + individual
    )


def _bgzf(payload: bytes) -> bytes:
    compressor = zlib.compressobj(level=6, wbits=-15)
    compressed = compressor.compress(payload) + compressor.flush()
    header = b"\x1f\x8b\x08\x04\x00\x00\x00\x00\x00\xff"
    extra_length = struct.pack("<H", 6)
    block_size = len(header) + 2 + 6 + len(compressed) + 8
    extra = b"BC" + struct.pack("<H", 2) + struct.pack("<H", block_size - 1)
    trailer = struct.pack("<II", zlib.crc32(payload) & 0xFFFFFFFF, len(payload) & 0xFFFFFFFF)
    return header + extra_length + extra + compressed + trailer


VCF = (
    "##fileformat=VCFv4.3\n"
    "##contig=<ID=7,length=1000000>\n"
    "##contig=<ID=17,length=1000000>\n"
    "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\n"
    "7\t10\trs1\tA\tT,G\t50\tPASS\tDP=3\tGT:DP\t0/1:3\n"
    "7\t11\trs2\tC\tA\t.\tPASS\t.\tGT\t0/0\n"
    "7\t12\trs3\tC\tG\t.\tPASS\t.\tGT\t./1\n"
    "7\t13\tbnd1\tN\tG]17:20]\t.\tPASS\tSVTYPE=BND\tGT\t0/1\n"
    "7\t14\tdel1\tN\t<DEL>\t.\tPASS\tSVTYPE=DEL\tGT\t0/1\n"
)


class VariantStreamTests(unittest.TestCase):
    def test_vcf_stream_splits_multiallelic_and_preserves_source_accounting(self) -> None:
        line_lengths: list[int] = []
        row_indexes: list[int] = []

        def lines() -> object:
            for line in VCF.splitlines(keepends=True):
                line_lengths.append(len(line))
                yield line

        report = StreamingVariantImporter().import_vcf(
            lines(),
            source_id="vcf-fixture",
            on_row=lambda row: row_indexes.append(row.record_index),
        )
        self.assertEqual(report.record_count, 5)
        self.assertEqual(report.row_count, 3)
        self.assertEqual(report.accepted_count, 1)
        self.assertEqual(report.deferred_count, 2)
        self.assertEqual(report.issue_counts["no_call_genotype"], 1)
        self.assertEqual(report.issue_counts["reference_genotype"], 1)
        self.assertEqual(report.issue_counts["alternate_not_in_selected_genotype"], 1)
        self.assertEqual([row.record_id for row in report.rows], ["rs1:alt1", "bnd1", "del1"])
        self.assertEqual((report.rows[0].alternate_index, report.rows[0].alternate_count), (1, 2))
        self.assertEqual(len(line_lengths), 9)
        self.assertEqual(row_indexes, [1, 4, 5])
        self.assertFalse(report.truncated)

    def test_vcf_multiallelic_row_maps_source_gt_and_ps_to_haplotype(self) -> None:
        source = (
            "##fileformat=VCFv4.3\n"
            "##contig=<ID=7,length=1000000>\n"
            '##FORMAT=<ID=GT,Number=1,Type=String,Description="genotype">\n'
            '##FORMAT=<ID=PS,Number=1,Type=Integer,Description="phase set">\n'
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\n"
            "7\t10\trs-phase\tA\tT,G\t50\tPASS\t.\tGT:PS\t0|2:17\n"
        )
        report = StreamingVariantImporter().import_vcf(
            iter(source.splitlines(keepends=True)),
            source_id="phased-multiallelic",
        )

        self.assertEqual(report.row_count, 1)
        row = report.rows[0]
        self.assertEqual((row.alternate_index, row.alternate_count), (2, 2))
        self.assertEqual(row.variant.alternate, "G")  # type: ignore[union-attr]
        assignments = row.to_phased_variant_identities()
        self.assertEqual(len(assignments), 1)
        self.assertEqual(assignments[0].variant.sample_id, "S1")
        self.assertEqual(assignments[0].variant.alternate, "G")
        self.assertEqual(assignments[0].phase_set, "17")
        self.assertEqual(assignments[0].haplotype_index, 2)

    def test_vcf_stream_phased_handoff_rejects_unphased_or_missing_ps(self) -> None:
        for sample_value in ("0/2:17", "0|2:."):
            with self.subTest(sample_value=sample_value):
                source = (
                    "##fileformat=VCFv4.3\n"
                    "##contig=<ID=7,length=1000000>\n"
                    '##FORMAT=<ID=GT,Number=1,Type=String,Description="genotype">\n'
                    '##FORMAT=<ID=PS,Number=1,Type=Integer,Description="phase set">\n'
                    "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\n"
                    f"7\t10\trs-phase\tA\tT,G\t50\tPASS\t.\tGT:PS\t{sample_value}\n"
                )
                report = StreamingVariantImporter().import_vcf(
                    iter(source.splitlines(keepends=True)),
                    source_id="invalid-phased-handoff",
                )
                self.assertEqual(report.accepted_count, 1)
                with self.assertRaises(ValidationError):
                    report.rows[0].to_phased_variant_identities()

    def test_reference_genotype_never_assigns_unobserved_source_alternates(self) -> None:
        source = (
            "##fileformat=VCFv4.3\n"
            "##contig=<ID=7,length=1000000>\n"
            '##FORMAT=<ID=GT,Number=1,Type=String,Description="genotype">\n'
            '##FORMAT=<ID=PS,Number=1,Type=Integer,Description="phase set">\n'
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\n"
            "7\t10\trs-reference\tA\tT,G\t50\tPASS\t.\tGT:PS\t0|0:17\n"
        )
        report = StreamingVariantImporter().import_vcf(
            iter(source.splitlines(keepends=True)),
            source_id="reference-genotype",
            include_reference=True,
        )

        self.assertEqual(report.row_count, 2)
        self.assertEqual(
            tuple(row.to_phased_variant_identities() for row in report.rows),
            ((), ()),
        )

    def test_vcf_stream_requires_iterator_instead_of_whole_text(self) -> None:
        with self.assertRaisesRegex(ValidationError, "iterable of lines"):
            StreamingVariantImporter().import_vcf(VCF, source_id="whole-text")  # type: ignore[arg-type]

    def test_vcf_stream_rejects_genotype_indices_outside_the_alt_list(self) -> None:
        source = (
            "##fileformat=VCFv4.3\n"
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\n"
            "7\t10\trs1\tA\tT,C\t50\tPASS\t.\tGT\t0/3\n"
        )
        report = StreamingVariantImporter().import_vcf(
            iter(source.splitlines(keepends=True)),
            source_id="invalid-genotype-index",
        )
        self.assertEqual(report.row_count, 0)
        self.assertEqual(report.error_count, 1)
        self.assertEqual(report.issue_counts["invalid_genotype"], 1)

    def test_vcf_stream_missing_requested_sample_is_an_error_without_fallback(self) -> None:
        source = (
            "##fileformat=VCFv4.3\n"
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\tS2\n"
            "7\t10\trs1\tA\tT,C\t50\tPASS\t.\tGT\t1/1\t0/2\n"
        )
        report = StreamingVariantImporter().import_vcf(
            iter(source.splitlines(keepends=True)),
            source_id="missing-sample",
            sample_id="MISSING",
        )
        self.assertEqual(report.record_count, 1)
        self.assertEqual(report.row_count, 0)
        self.assertEqual(report.error_count, 1)
        self.assertEqual(report.issue_counts["sample_not_found"], 1)

    def test_vcf_stream_requires_explicit_selection_for_multiple_samples(self) -> None:
        source = (
            "##fileformat=VCFv4.3\n"
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\tS2\n"
            "7\t10\trs1\tA\tT,C\t50\tPASS\t.\tGT\t1/1\t0/2\n"
        )
        report = StreamingVariantImporter().import_vcf(
            iter(source.splitlines(keepends=True)),
            source_id="ambiguous-samples",
        )
        self.assertEqual(report.record_count, 1)
        self.assertEqual(report.row_count, 0)
        self.assertEqual(report.error_count, 1)
        self.assertEqual(report.issue_counts["sample_selection_required"], 1)

    def test_vcf_stream_rejects_duplicate_sample_id_even_when_requested(self) -> None:
        source = (
            "##fileformat=VCFv4.3\n"
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\tS1\n"
            "7\t10\trs1\tA\tT,C\t50\tPASS\t.\tGT\t1/1\t0/2\n"
        )
        report = StreamingVariantImporter().import_vcf(
            iter(source.splitlines(keepends=True)),
            source_id="duplicate-vcf-sample-id",
            sample_id="S1",
        )
        self.assertEqual(report.record_count, 1)
        self.assertEqual(report.row_count, 0)
        self.assertEqual(report.error_count, 1)
        self.assertEqual(report.issue_counts["duplicate_sample_id"], 1)

    def test_vcf_stream_rejects_duplicate_format_keys(self) -> None:
        source = (
            "##fileformat=VCFv4.3\n"
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\n"
            "7\t10\trs1\tA\tT,C\t50\tPASS\t.\tGT:GT\t1/1:0/2\n"
        )
        report = StreamingVariantImporter().import_vcf(
            iter(source.splitlines(keepends=True)),
            source_id="duplicate-vcf-format-key",
            sample_id="S1",
        )
        self.assertEqual(report.record_count, 1)
        self.assertEqual(report.row_count, 0)
        self.assertEqual(report.error_count, 1)
        self.assertEqual(report.issue_counts["duplicate_format_key"], 1)

    def test_vcf_stream_rejects_invalid_format_key_and_nonleading_gt(self) -> None:
        cases = (
            ("GT:DP+", "0/1:5", "invalid_format_key"),
            ("DP:GT", "5:0/1", "genotype_format_key_not_first"),
        )
        for format_field, sample_field, expected_issue in cases:
            with self.subTest(format_field=format_field):
                source = (
                    "##fileformat=VCFv4.3\n"
                    "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\n"
                    f"7\t10\trs1\tA\tT,C\t50\tPASS\t.\t{format_field}\t{sample_field}\n"
                )
                report = StreamingVariantImporter().import_vcf(
                    iter(source.splitlines(keepends=True)),
                    source_id="invalid-format-key",
                    sample_id="S1",
                )
                self.assertEqual(report.row_count, 0)
                self.assertEqual(report.error_count, 1)
                self.assertEqual(report.issue_counts[expected_issue], 1)

    def test_vcf_stream_missing_selected_sample_cell_rejects_the_record(self) -> None:
        source = (
            "##fileformat=VCFv4.3\n"
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\n"
            "7\t10\trs1\tA\tT,C\t50\tPASS\t.\tGT\n"
        )
        report = StreamingVariantImporter().import_vcf(
            iter(source.splitlines(keepends=True)),
            source_id="missing-sample-cell",
            sample_id="S1",
        )
        self.assertEqual(report.record_count, 1)
        self.assertEqual(report.row_count, 0)
        self.assertEqual(report.error_count, 1)
        self.assertEqual(report.issue_counts["sample_data_missing"], 1)

    def test_vcf_stream_single_dot_sample_cell_is_a_missing_gt(self) -> None:
        source = (
            "##fileformat=VCFv4.3\n"
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\n"
            "7\t10\trs1\tA\tT\t50\tPASS\t.\tGT:DP\t.\n"
        )
        lines = source.splitlines(keepends=True)
        importer = StreamingVariantImporter()
        report = importer.import_vcf(iter(lines), source_id="dot-sample")
        self.assertEqual(report.row_count, 0)
        self.assertEqual(report.issue_counts["no_call_genotype"], 1)

        retained = importer.import_vcf(
            iter(lines),
            source_id="dot-sample-opt-in",
            include_no_call=True,
        )
        self.assertEqual(retained.row_count, 1)

    def test_vcf_stream_rejects_empty_or_excess_sample_subfields(self) -> None:
        cases = (
            ("GT", "", "sample_data_missing"),
            ("GT", "0/1:8", "sample_data_excess_fields"),
            ("GT:DP:PS", "0/1::5", "sample_data_empty_field"),
            ("GT:DP", "0/1:", "sample_data_empty_field"),
        )
        for format_field, sample_field, expected_issue in cases:
            with self.subTest(sample_field=sample_field):
                source = (
                    "##fileformat=VCFv4.3\n"
                    "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\n"
                    f"7\t10\trs1\tA\tT\t50\tPASS\t.\t{format_field}\t{sample_field}\n"
                )
                report = StreamingVariantImporter().import_vcf(
                    iter(source.splitlines(keepends=True)),
                    source_id="malformed-sample-value",
                )
                self.assertEqual(report.row_count, 0)
                self.assertEqual(report.error_count, 1)
                self.assertEqual(report.issue_counts[expected_issue], 1)

    def test_vcf_stream_alt_dot_is_a_no_variant_site(self) -> None:
        source = (
            "##fileformat=VCFv4.3\n"
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\n"
            "7\t10\trs-none\tA\t.\t50\tPASS\t.\tGT\t0/0\n"
        )
        report = StreamingVariantImporter().import_vcf(
            iter(source.splitlines(keepends=True)),
            source_id="no-alternate",
        )
        self.assertEqual(report.row_count, 0)
        self.assertEqual(report.issue_counts["no_alternate_allele"], 1)

    def test_vcf_stream_spanning_deletion_star_is_deferred(self) -> None:
        source = (
            "##fileformat=VCFv4.3\n"
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\n"
            "7\t10\trs-star\tA\t*\t50\tPASS\t.\tGT\t0/1\n"
        )
        report = StreamingVariantImporter().import_vcf(
            iter(source.splitlines(keepends=True)),
            source_id="spanning-deletion",
        )
        self.assertEqual(report.row_count, 1)
        self.assertEqual(report.deferred_count, 1)
        self.assertIsNone(report.rows[0].variant)
        self.assertTrue(report.rows[0].deferred)
        self.assertEqual(report.issue_counts["unsupported_symbolic_allele"], 1)

    def test_vcf_stream_dot_cannot_be_combined_with_other_alt_alleles(self) -> None:
        source = (
            "##fileformat=VCFv4.3\n"
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
            "7\t10\trs-invalid\tA\t.,T\t50\tPASS\t.\n"
        )
        report = StreamingVariantImporter().import_vcf(
            iter(source.splitlines(keepends=True)),
            source_id="mixed-no-alternate",
        )
        self.assertEqual(report.row_count, 0)
        self.assertEqual(report.issue_counts["invalid_alternate"], 1)

    def test_vcf_stream_info_values_match_legacy_source_preservation(self) -> None:
        source = (
            "##fileformat=VCFv4.3\n"
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
            "7\t10\trs-info\tA\tT\t50\tPASS\tDP=12;AF=0.25,0.75;DB\n"
        )
        report = StreamingVariantImporter().import_vcf(
            iter(source.splitlines(keepends=True)),
            source_id="info-preservation",
        )
        self.assertEqual(report.accepted_count, 1)
        self.assertEqual(
            report.rows[0].info,
            {"DP": "12", "AF": ["0.25", "0.75"], "DB": True},
        )

    def test_vcf_stream_duplicate_info_key_is_rejected(self) -> None:
        source = (
            "##fileformat=VCFv4.3\n"
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
            "7\t10\trs-info\tA\tT\t50\tPASS\tDP=12;DP=18\n"
        )
        report = StreamingVariantImporter().import_vcf(
            iter(source.splitlines(keepends=True)),
            source_id="duplicate-info",
        )
        self.assertEqual(report.accepted_count, 0)
        self.assertEqual(report.issue_counts["duplicate_info_key"], 1)

    def test_vcf_stream_declared_info_schema_checks_type_and_allele_cardinality(self) -> None:
        prefix = (
            "##fileformat=VCFv4.3\n"
            '##INFO=<ID=DP,Number=1,Type=Integer,Description="read depth">\n'
            '##INFO=<ID=AF,Number=A,Type=Float,Description="allele frequency">\n'
            '##INFO=<ID=DB,Number=0,Type=Flag,Description="database membership">\n'
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
        )
        valid = prefix + "7\t10\trs-info\tA\tT,G\t50\tPASS\tDP=12;AF=0.25,0.75;DB\n"
        report = StreamingVariantImporter().import_vcf(
            iter(valid.splitlines(keepends=True)),
            source_id="declared-info",
        )
        self.assertEqual(report.accepted_count, 2)
        self.assertEqual(
            report.rows[0].info,
            {"DP": "12", "AF": ["0.25", "0.75"], "DB": True},
        )

        malformed = (
            ("DP=depth;AF=0.25,0.75;DB", "info_type_mismatch"),
            ("DP=12;AF=0.25;DB", "info_number_mismatch"),
            ("DP=12;AF=0.25,0.75;DB=1", "info_type_mismatch"),
        )
        for info_text, expected_issue in malformed:
            with self.subTest(info_text=info_text):
                source = prefix + f"7\t10\trs-info\tA\tT,G\t50\tPASS\t{info_text}\n"
                parsed = StreamingVariantImporter().import_vcf(
                    iter(source.splitlines(keepends=True)),
                    source_id="invalid-declared-info",
                )
                self.assertEqual(parsed.accepted_count, 0)
                self.assertEqual(parsed.issue_counts[expected_issue], 1)

    def test_vcf_stream_declared_format_schema_checks_selected_sample_values(self) -> None:
        prefix = (
            "##fileformat=VCFv4.3\n"
            '##FORMAT=<ID=GT,Number=1,Type=String,Description="genotype">\n'
            '##FORMAT=<ID=AD,Number=R,Type=Integer,Description="allele depth">\n'
            '##FORMAT=<ID=AF,Number=A,Type=Float,Description="allele frequency">\n'
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\n"
        )
        valid = prefix + "7\t10\trs-format\tA\tT\t50\tPASS\t.\tGT:AD:AF\t0/1:10,5:0.25\n"
        report = StreamingVariantImporter().import_vcf(
            iter(valid.splitlines(keepends=True)), source_id="declared-format"
        )
        self.assertEqual(report.accepted_count, 1)

        malformed = (
            ("0/1:10:0.25", "format_number_mismatch"),
            ("0/1:10,5:bad", "format_type_mismatch"),
        )
        for sample_text, expected_issue in malformed:
            with self.subTest(sample_text=sample_text):
                source = prefix + f"7\t10\trs-format\tA\tT\t50\tPASS\t.\tGT:AD:AF\t{sample_text}\n"
                parsed = StreamingVariantImporter().import_vcf(
                    iter(source.splitlines(keepends=True)),
                    source_id="invalid-declared-format",
                )
                self.assertEqual(parsed.accepted_count, 0)
                self.assertEqual(parsed.issue_counts[expected_issue], 1)

    def test_streaming_import_rejects_empty_or_non_string_sample_ids(self) -> None:
        importer = StreamingVariantImporter()
        with self.assertRaisesRegex(ValidationError, "sample_id"):
            importer.import_vcf(iter(()), source_id="bad-sample", sample_id=1)  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValidationError, "sample_id"):
            importer.import_bcf(iter(()), source_id="bad-sample", sample_id=" ")

    def test_include_reference_and_no_call_are_explicit_opt_ins(self) -> None:
        report = StreamingVariantImporter().import_vcf(
            iter(VCF.splitlines(keepends=True)),
            source_id="included",
            include_reference=True,
            include_no_call=True,
        )
        self.assertEqual(report.record_count, 5)
        self.assertEqual(report.row_count, 5)
        self.assertEqual(report.accepted_count, 3)
        self.assertEqual(report.deferred_count, 2)
        self.assertNotIn("no_call_genotype", report.issue_counts)
        self.assertNotIn("reference_genotype", report.issue_counts)

    def test_breakend_forms_keep_mate_coordinate_and_orientation(self) -> None:
        forms = (
            ("G]17:198982]", "prefix", "]"),
            ("]13:123]A", "suffix", "]"),
            ("G[17:198982[", "prefix", "["),
            ("[13:123[A", "suffix", "["),
        )
        for alternate, side, bracket in forms:
            report = normalize_breakend(
                chromosome="7",
                position=100,
                reference="N",
                alternate=alternate,
                input_id="bnd",
            )
            self.assertIs(report.state, NormalizationState.SUPPORTED)
            self.assertTrue(report.deferred)
            self.assertIsNotNone(report.mate)
            assert report.mate is not None
            self.assertEqual(report.mate.local_side, side)
            self.assertEqual(report.mate.bracket, bracket)
            self.assertEqual(report.mate.position, 198982 if "198982" in alternate else 123)
            self.assertEqual(report.variant.kind.value, "breakend")  # type: ignore[union-attr]

    def test_malformed_breakend_and_symbolic_allele_abstain_without_guessing(self) -> None:
        malformed = normalize_breakend(
            chromosome="7",
            position=100,
            reference="N",
            alternate="G]17:198982[",
        )
        self.assertIs(malformed.state, NormalizationState.INVALID)
        report = StreamingVariantImporter().import_vcf(
            iter(
                (
                    "##fileformat=VCFv4.3\n",
                    "##contig=<ID=7>\n",
                    "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n",
                    "7\t1\tx\tN\t<DEL>\t.\tPASS\t.\n",
                )
            ),
            source_id="symbolic",
        )
        self.assertEqual(report.deferred_count, 1)
        self.assertEqual(report.rows[0].normalization.state, NormalizationState.ABSTAINED)
        self.assertEqual(report.invalid_count, 0)

    def test_deterministic_receipt_excludes_wall_clock(self) -> None:
        first = StreamingVariantImporter().import_vcf(
            iter(VCF.splitlines(keepends=True)), source_id="same"
        )
        second = StreamingVariantImporter().import_vcf(
            iter(VCF.splitlines(keepends=True)), source_id="same"
        )
        self.assertEqual(first.input_hash, second.input_hash)
        self.assertEqual(first.header_hash, second.header_hash)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_row_and_issue_ceiling_is_loss_aware(self) -> None:
        report = StreamingVariantImporter().import_vcf(
            iter(VCF.splitlines(keepends=True)),
            source_id="bounded",
            max_records=2,
            max_retained_rows=1,
            max_issues=1,
        )
        self.assertTrue(report.truncated)
        self.assertEqual(report.record_count, 5)
        self.assertEqual(report.retained_row_count, 1)
        self.assertGreater(report.omitted_issue_count, 0)
        self.assertEqual(report.accepted, False)

    def test_raw_bcf_and_bgzf_bcf_are_incrementally_decoded(self) -> None:
        raw = _raw_bcf()
        raw_report = StreamingVariantImporter().import_bcf(
            (raw[index : index + 7] for index in range(0, len(raw), 7)),
            source_id="raw-bcf",
        )
        bgzf = _bgzf(raw)
        bgzf_report = StreamingVariantImporter().import_bcf(
            (bgzf[index : index + 11] for index in range(0, len(bgzf), 11)),
            source_id="bgzf-bcf",
        )
        self.assertEqual(raw_report.compression_mode, "raw")
        self.assertEqual(bgzf_report.compression_mode, "bgzf")
        self.assertEqual(bgzf_report.compressed_block_count, 1)
        self.assertEqual(raw_report.rows[0].variant.canonical_key, "GRCh38:chr7:100:100:A:T")  # type: ignore[union-attr]
        self.assertEqual(raw_report.rows[0].raw_hash, bgzf_report.rows[0].raw_hash)

    def test_multiallelic_bcf_emits_only_the_selected_sample_alt_alleles(self) -> None:
        raw = _raw_bcf(alternates=("T", "C"), genotype_alleles=(0, 2))
        report = StreamingVariantImporter().import_bcf(
            (raw[index : index + 11] for index in range(0, len(raw), 11)),
            source_id="multiallelic-bcf",
        )
        self.assertEqual(report.row_count, 1)
        self.assertEqual(report.rows[0].record_id, "rs1:alt2")
        self.assertEqual(report.rows[0].variant.alternate, "C")  # type: ignore[union-attr]
        self.assertEqual((report.rows[0].alternate_index, report.rows[0].alternate_count), (2, 2))
        self.assertEqual(report.issue_counts["alternate_not_in_selected_genotype"], 1)

    def test_multiallelic_bcf_maps_typed_gt_and_ps_to_haplotype(self) -> None:
        raw = _raw_bcf(
            alternates=("T", "C"),
            genotype_alleles=(0, 2),
            format_ids=(0, 1),
            format_names=("GT", "PS"),
            phased_genotypes=True,
            sample_phase_sets=(42,),
        )
        report = StreamingVariantImporter().import_bcf(
            (raw[index : index + 11] for index in range(0, len(raw), 11)),
            source_id="phased-multiallelic-bcf",
        )

        self.assertEqual(report.row_count, 1)
        row = report.rows[0]
        self.assertEqual((row.alternate_index, row.alternate_count), (2, 2))
        assignments = row.to_phased_variant_identities()
        self.assertEqual(len(assignments), 1)
        self.assertEqual(assignments[0].variant.sample_id, "SAMPLE")
        self.assertEqual(assignments[0].variant.alternate, "C")
        self.assertEqual(assignments[0].phase_set, "42")
        self.assertEqual(assignments[0].haplotype_index, 2)

    def test_bcf_stream_validates_typed_format_type_and_cardinality(self) -> None:
        declarations = (
            b'##FORMAT=<ID=DP,Number=2,Type=Float,Description="depth">\n',
            b'##FORMAT=<ID=DP,Number=1,Type=Integer,Description="depth">\n',
        )
        expected_codes = ("format_type_mismatch", "format_number_mismatch")
        for declaration, expected_code in zip(declarations, expected_codes, strict=True):
            with self.subTest(expected_code=expected_code):
                raw = _raw_bcf(
                    format_ids=(0, 1),
                    format_names=("GT", "DP"),
                    format_header_overrides={"DP": declaration},
                )

                report = StreamingVariantImporter().import_bcf(
                    (raw[index : index + 13] for index in range(0, len(raw), 13)),
                    source_id="bcf-format-schema",
                    sample_id="SAMPLE",
                )

                self.assertEqual(report.rows, ())
                self.assertIn(expected_code, {issue.code for issue in report.issues})

    def test_multiallelic_bcf_rejects_out_of_range_genotype_indices(self) -> None:
        raw = _raw_bcf(alternates=("T", "C"), genotype_alleles=(0, 3))
        report = StreamingVariantImporter().import_bcf(
            (raw[index : index + 13] for index in range(0, len(raw), 13)),
            source_id="invalid-bcf-genotype-index",
        )
        self.assertEqual(report.row_count, 0)
        self.assertEqual(report.error_count, 1)
        self.assertEqual(report.issue_counts["invalid_genotype"], 1)

    def test_bcf_stream_missing_requested_sample_is_an_error_without_fallback(self) -> None:
        raw = _raw_bcf()
        report = StreamingVariantImporter().import_bcf(
            (raw[index : index + 19] for index in range(0, len(raw), 19)),
            source_id="missing-bcf-sample",
            sample_id="MISSING",
        )
        self.assertEqual(report.record_count, 1)
        self.assertEqual(report.row_count, 0)
        self.assertEqual(report.error_count, 1)
        self.assertEqual(report.issue_counts["sample_not_found"], 1)

    def test_bcf_stream_requires_explicit_selection_for_multiple_samples(self) -> None:
        raw = _raw_bcf(
            sample_names=("S1", "S2"),
            sample_genotype_alleles=((1, 1), (0, 2)),
        )
        report = StreamingVariantImporter().import_bcf(
            (raw[index : index + 17] for index in range(0, len(raw), 17)),
            source_id="ambiguous-bcf-samples",
        )
        self.assertEqual(report.record_count, 1)
        self.assertEqual(report.row_count, 0)
        self.assertEqual(report.error_count, 1)
        self.assertEqual(report.issue_counts["sample_selection_required"], 1)

    def test_bcf_stream_rejects_duplicate_sample_ids(self) -> None:
        raw = _raw_bcf(
            sample_names=("S1", "S1"),
            sample_genotype_alleles=((1, 1), (0, 2)),
        )
        report = StreamingVariantImporter().import_bcf(
            (raw[index : index + 17] for index in range(0, len(raw), 17)),
            source_id="duplicate-bcf-sample-id",
            sample_id="S1",
        )
        self.assertEqual(report.record_count, 1)
        self.assertEqual(report.row_count, 0)
        self.assertEqual(report.error_count, 1)
        self.assertEqual(report.issue_counts["duplicate_sample_id"], 1)

    def test_bcf_stream_rejects_duplicate_format_keys(self) -> None:
        raw = _raw_bcf(format_ids=(0, 0))
        report = StreamingVariantImporter().import_bcf(
            (raw[index : index + 17] for index in range(0, len(raw), 17)),
            source_id="duplicate-bcf-format-key",
        )
        self.assertEqual(report.record_count, 1)
        self.assertEqual(report.row_count, 0)
        self.assertEqual(report.error_count, 1)
        self.assertEqual(report.issue_counts["duplicate_format_key"], 1)

    def test_bcf_stream_no_alt_record_is_not_emitted_as_a_variant(self) -> None:
        raw = _raw_bcf(alternates=(), genotype_alleles=(0, 0))
        report = StreamingVariantImporter().import_bcf(
            (raw[index : index + 17] for index in range(0, len(raw), 17)),
            source_id="bcf-no-alternate",
        )
        self.assertEqual(report.row_count, 0)
        self.assertEqual(report.issue_counts["no_alternate_allele"], 1)

    def test_bcf_stream_spanning_deletion_star_is_deferred(self) -> None:
        raw = _raw_bcf(alternates=("*",))
        report = StreamingVariantImporter().import_bcf(
            (raw[index : index + 17] for index in range(0, len(raw), 17)),
            source_id="bcf-spanning-deletion",
        )
        self.assertEqual(report.row_count, 1)
        self.assertEqual(report.deferred_count, 1)
        self.assertIsNone(report.rows[0].variant)
        self.assertTrue(report.rows[0].deferred)
        self.assertEqual(report.issue_counts["unsupported_symbolic_allele"], 1)

    def test_bcf_stream_requires_gt_before_other_format_keys(self) -> None:
        raw = _raw_bcf(format_ids=(1, 0), format_names=("GT", "DP"))
        report = StreamingVariantImporter().import_bcf(
            (raw[index : index + 17] for index in range(0, len(raw), 17)),
            source_id="nonleading-bcf-gt",
        )
        self.assertEqual(report.row_count, 0)
        self.assertEqual(report.error_count, 1)
        self.assertEqual(report.issue_counts["genotype_format_key_not_first"], 1)

    def test_text_chunk_decoder_keeps_lines_and_final_fragment(self) -> None:
        lines = tuple(iter_text_lines_from_chunks((b"a\n", b"b", b"\n", b"c")))
        self.assertEqual(lines, ("a\n", "b\n", "c"))

    def test_contracts_are_versioned_and_data_free(self) -> None:
        schema = streaming_intake_schema()
        self.assertEqual(schema["version"], "streaming-intake-v2")
        self.assertIn("alternate_index", schema["row_fields"])
        self.assertIn("phased_haplotype_assignment", schema["row_fields"])
        self.assertIn("bgzf", streaming_intake_capabilities()["compression"])
        self.assertIn("mate_fields", breakend_normalization_schema())
        serialized = json.dumps(schema, sort_keys=True)
        self.assertNotIn("agent", serialized.lower())
        self.assertNotIn("model", serialized.lower())
        self.assertNotIn("language", serialized.lower())

    def test_cli_stream_command_writes_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "calls.vcf"
            output = Path(directory) / "receipt.json"
            source.write_text(
                "##fileformat=VCFv4.3\n"
                "##contig=<ID=7>\n"
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
                "7\t10\trs1\tA\tT\t.\tPASS\t.\n",
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "stream-variants",
                        str(source),
                        "--source-id",
                        "cli-stream",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["source_id"], "cli-stream")
            self.assertEqual(payload["accepted_count"], 1)

    def test_raw_stream_api_returns_receipt_and_schemas(self) -> None:
        server = create_server("127.0.0.1", 0, ".glio-stream-test")
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            connection = HTTPConnection(host, port, timeout=5)
            body = (
                b"##fileformat=VCFv4.3\n"
                b"##contig=<ID=7>\n"
                b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
                b"7\t10\trs1\tA\tT\t.\tPASS\t.\n"
            )
            connection.request(
                "POST",
                "/v1/intake/stream?source_id=api-test",
                body=body,
                headers={"Content-Type": "text/vcf", "Content-Length": str(len(body))},
            )
            response = connection.getresponse()
            payload = json.loads(response.read().decode())
            self.assertEqual(response.status, 200)
            self.assertEqual(payload["accepted_count"], 1)
            connection.request("GET", "/v1/intake/streaming/schema")
            schema_response = connection.getresponse()
            schema_payload = json.loads(schema_response.read().decode())
            self.assertEqual(schema_response.status, 200)
            self.assertEqual(schema_payload["version"], "streaming-intake-v2")
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
