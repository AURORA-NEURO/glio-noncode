from __future__ import annotations

import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from glio_noncode.bcf import BcfReader
from glio_noncode.cli import main
from glio_noncode.intake import IntakeFormat, VariantIntake
from glio_noncode.serialization import content_hash


def _typed_string(value: str) -> bytes:
    raw = value.encode() + b"\x00"
    return bytes([(len(raw) << 4) | 7]) + raw


def _typed_int(value: int) -> bytes:
    return bytes([0x13]) + struct.pack("<i", value)


def _typed_int_vector(values: list[int]) -> bytes:
    return bytes([(len(values) << 4) | 3]) + b"".join(struct.pack("<i", value) for value in values)


def _raw_bcf(
    record_count: int = 1,
    *,
    alternates: tuple[str, ...] = ("T",),
    genotype_alleles: tuple[int, ...] = (0, 1),
    format_ids: tuple[int, ...] = (0,),
    format_names: tuple[str, ...] = ("GT",),
    format_values: dict[str, tuple[int, ...]] | None = None,
    format_header_overrides: dict[str, bytes] | None = None,
) -> bytes:
    format_definitions = {
        "GT": b'##FORMAT=<ID=GT,Number=1,Type=String,Description="genotype">\n',
        "DP": b'##FORMAT=<ID=DP,Number=1,Type=Integer,Description="depth">\n',
        "LEN": b'##FORMAT=<ID=LEN,Number=1,Type=Integer,Description="reference block length">\n',
    }
    if format_header_overrides:
        format_definitions.update(format_header_overrides)
    header = (
        b"##fileformat=VCFv4.3\n"
        b"##contig=<ID=7,length=1000000>\n"
        b'##INFO=<ID=DP,Number=1,Type=Integer,Description="depth">\n'
        + b"".join(format_definitions[name] for name in format_names)
        + b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE\n"
    )
    shared = b"".join(
        (
            struct.pack("<i", 0),
            struct.pack("<i", 99),
            struct.pack("<i", 1),
            struct.pack("<f", 42.0),
            struct.pack("<I", (len(alternates) + 1) | (1 << 16)),
            struct.pack("<I", (len(format_ids) << 24) | 1),
            _typed_string("rs1"),
            _typed_string("A"),
            *(_typed_string(alternate) for alternate in alternates),
            _typed_int_vector([0]),
            _typed_int(0),
            _typed_int(12),
        )
    )
    encoded_genotype = [(allele_index + 1) << 1 for allele_index in genotype_alleles]
    selected_format_values = format_values or {}
    individual = b"".join(
        _typed_int(format_id)
        + _typed_int_vector(
            list(selected_format_values.get(format_names[format_id], tuple(encoded_genotype)))
        )
        for format_id in format_ids
    )
    record = struct.pack("<II", len(shared), len(individual)) + shared + individual
    return (
        b"BCF\x02\x02"
        + struct.pack("<I", len(header) + 1)
        + header
        + b"\x00"
        + (record * record_count)
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


class BcfReaderTests(unittest.TestCase):
    def test_raw_and_bgzf_bcf_decode_typed_record(self) -> None:
        raw = _raw_bcf()
        for payload in (raw, _bgzf(raw)):
            document = BcfReader().read(payload)
            self.assertEqual(document.version, "2.2")
            self.assertEqual(document.contigs, ("7",))
            self.assertEqual(document.records[0].position, 100)
            self.assertEqual(document.records[0].reference, "A")
            self.assertEqual(document.records[0].alternates, ("T",))
            self.assertEqual(document.records[0].info["DP"], 12)
            self.assertEqual(document.records[0].samples["SAMPLE"]["GT"], "0/1")

    def test_bcf_converts_into_the_same_intake_batch_contract(self) -> None:
        batch = VariantIntake().parse_bytes(_raw_bcf(), source_id="bcf-fixture")
        self.assertEqual(batch.input_format, IntakeFormat.BCF)
        self.assertEqual(len(batch.variants), 1)
        self.assertEqual(batch.variants[0].canonical_key, "GRCh38:chr7:100:100:A:T")
        self.assertEqual(batch.receipt.input_hash, BcfReader().read(_raw_bcf()).input_hash)

    def test_bcf_selected_format_values_match_declared_type_and_cardinality(self) -> None:
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
                    format_values={"DP": (12, 13)},
                    format_header_overrides={"DP": declaration},
                )

                batch = VariantIntake().parse_bytes(raw, source_id="bcf-format-schema")

                self.assertEqual(batch.variants, ())
                self.assertIn(expected_code, {issue.code for issue in batch.issues})

    def test_bcf_gvcf_reference_block_uses_sample_format_len(self) -> None:
        raw = _raw_bcf(
            alternates=("<*>",),
            genotype_alleles=(0, 0),
            format_ids=(0, 1),
            format_names=("GT", "LEN"),
            format_values={"LEN": (14,)},
        )

        batch = VariantIntake().parse_bytes(raw, source_id="bcf-reference-confidence")

        self.assertEqual(batch.variants, ())
        self.assertEqual(len(batch.reference_blocks), 1)
        block = batch.reference_blocks[0]
        self.assertEqual((block.start, block.end, block.length), (99, 113, 14))
        self.assertEqual(block.sample_values["LEN"], 14)
        self.assertEqual(block.genotype, "0/0")

    def test_reference_block_query_cli_reads_bcf_blocks(self) -> None:
        raw = _raw_bcf(
            alternates=("<*>",),
            genotype_alleles=(0, 0),
            format_ids=(0, 1),
            format_names=("GT", "LEN"),
            format_values={"LEN": (14,)},
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "sample.bcf"
            output = Path(directory) / "coverage.json"
            variant_output = Path(directory) / "variant-coverage.json"
            source.write_bytes(raw)

            self.assertEqual(
                main(
                    [
                        "reference-block-query",
                        str(source),
                        "--sample-id",
                        "SAMPLE",
                        "--chromosome",
                        "7",
                        "--start",
                        "99",
                        "--end",
                        "113",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["source"]["input_format"], "bcf")
            self.assertEqual(report["coverage"]["status"], "complete_reference")
            self.assertEqual(report["coverage"]["base_counts"]["reference"], 14)

            self.assertEqual(
                main(
                    [
                        "reference-block-query",
                        str(source),
                        "--sample-id",
                        "SAMPLE",
                        "--variant",
                        "7:100:A>T",
                        "--output",
                        str(variant_output),
                    ]
                ),
                0,
            )
            variant_report = json.loads(variant_output.read_text(encoding="utf-8"))
            self.assertEqual(variant_report["source"]["input_format"], "bcf")
            self.assertEqual(
                variant_report["query"]["mode"],
                "variant_reference_span",
            )
            self.assertEqual(
                (variant_report["coverage"]["start"], variant_report["coverage"]["end"]),
                (99, 100),
            )
            self.assertEqual(
                variant_report["coverage"]["base_counts"]["reference"],
                1,
            )

    def test_bcf_duplicate_format_keys_are_preserved_and_rejected(self) -> None:
        raw = _raw_bcf(format_ids=(0, 0))
        record = BcfReader().read(raw).records[0]
        self.assertEqual(record.format_keys, ("GT", "GT"))

        batch = VariantIntake().parse_bytes(raw, source_id="duplicate-format-key")
        self.assertEqual(batch.variants, ())
        self.assertEqual(batch.issues[0].code, "duplicate_format_key")
        self.assertEqual(batch.issues[0].severity.value, "error")

    def test_bcf_requires_gt_before_other_format_keys(self) -> None:
        raw = _raw_bcf(format_ids=(1, 0), format_names=("GT", "DP"))
        record = BcfReader().read(raw).records[0]
        self.assertEqual(record.format_keys, ("DP", "GT"))

        batch = VariantIntake().parse_bytes(raw, source_id="nonleading-bcf-gt")
        self.assertEqual(batch.variants, ())
        self.assertEqual(batch.issues[0].code, "genotype_format_key_not_first")

    def test_bcf_reference_only_record_is_not_emitted_as_a_variant(self) -> None:
        raw = _raw_bcf(alternates=(), genotype_alleles=(0, 0))
        batch = VariantIntake().parse_bytes(raw, source_id="bcf-no-alternate")
        self.assertEqual(batch.variants, ())
        self.assertEqual(batch.issues[0].code, "no_alternate_allele")

    def test_bcf_spanning_deletion_star_is_deferred_not_normalized_as_cnv(self) -> None:
        raw = _raw_bcf(alternates=("*",))
        batch = VariantIntake().parse_bytes(raw, source_id="bcf-spanning-deletion")
        self.assertEqual(batch.variants, ())
        self.assertEqual(len(batch.deferred_records), 1)
        self.assertEqual(batch.issues[0].code, "unsupported_symbolic_allele")

    def test_bcf_record_bound_stops_normalization_and_preserves_full_input_hash(self) -> None:
        raw = _raw_bcf(record_count=3)
        document = BcfReader().read(raw)
        parser = VariantIntake(max_records=2)
        with patch.object(
            parser,
            "_add_record",
            wraps=parser._add_record,
        ) as add_record:
            batch = parser.parse_bytes(raw, source_id="bounded-bcf")

        self.assertEqual(add_record.call_count, 2)
        self.assertEqual(batch.receipt.record_count, 3)
        self.assertEqual(batch.receipt.input_hash, document.input_hash)
        self.assertTrue(batch.has_errors)
        overflow = [issue for issue in batch.issues if issue.code == "max_records_exceeded"]
        self.assertEqual(len(overflow), 1)
        self.assertEqual(overflow[0].severity.value, "error")
        self.assertEqual(overflow[0].raw_hash, document.records[2].raw_hash)

    def test_bcf_exact_record_bound_preserves_legacy_receipt(self) -> None:
        raw = _raw_bcf(record_count=2)
        legacy = VariantIntake().parse_bytes(raw, source_id="bounded-bcf")
        bounded = VariantIntake(
            max_records=2,
            max_auxiliary_lines=5,
        ).parse_bytes(raw, source_id="bounded-bcf")

        self.assertEqual(bounded.variants, legacy.variants)
        self.assertEqual(bounded.issues, legacy.issues)
        self.assertEqual(
            bounded.receipt.provenance_dict(),
            legacy.receipt.provenance_dict(),
        )
        self.assertFalse(bounded.has_errors)

    def test_bcf_auxiliary_header_limit_blocks_before_record_normalization(self) -> None:
        raw = _raw_bcf(record_count=1)
        document = BcfReader().read(raw)
        parser = VariantIntake(max_auxiliary_lines=4)
        with patch.object(
            parser,
            "_add_record",
            wraps=parser._add_record,
        ) as add_record:
            batch = parser.parse_bytes(raw, source_id="bounded-bcf-header")

        add_record.assert_not_called()
        self.assertEqual(batch.receipt.input_hash, document.input_hash)
        self.assertEqual(batch.receipt.record_count, 0)
        self.assertTrue(batch.has_errors)
        self.assertEqual(len(batch.issues), 1)
        issue = batch.issues[0]
        self.assertEqual(issue.code, "max_auxiliary_lines_exceeded")
        self.assertEqual(issue.line_number, 5)
        self.assertEqual(
            issue.raw_hash,
            content_hash("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE"),
        )


if __name__ == "__main__":
    unittest.main()
