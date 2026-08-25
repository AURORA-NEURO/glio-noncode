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


def _raw_bcf() -> bytes:
    header = (
        b"##fileformat=VCFv4.3\n"
        b"##contig=<ID=7,length=1000000>\n"
        b'##INFO=<ID=DP,Number=1,Type=Integer,Description="depth">\n'
        b'##FORMAT=<ID=GT,Number=1,Type=String,Description="genotype">\n'
        b"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE\n"
    )
    shared = b"".join(
        (
            struct.pack("<i", 0),
            struct.pack("<i", 99),
            struct.pack("<i", 1),
            struct.pack("<f", 42.0),
            struct.pack("<I", 2 | (1 << 16)),
            struct.pack("<I", (1 << 24) | 1),
            _typed_string("rs1"),
            _typed_string("A"),
            _typed_string("T"),
            _typed_int_vector([0]),
            _typed_int(0),
            _typed_int(12),
        )
    )
    individual = _typed_int(0) + _typed_int_vector([2, 4])
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
        self.assertEqual(report.row_count, 4)
        self.assertEqual(report.accepted_count, 2)
        self.assertEqual(report.deferred_count, 2)
        self.assertEqual(report.issue_counts["no_call_genotype"], 1)
        self.assertEqual(report.issue_counts["reference_genotype"], 1)
        self.assertEqual([row.record_id for row in report.rows[:2]], ["rs1:alt1", "rs1:alt2"])
        self.assertEqual(len(line_lengths), 9)
        self.assertEqual(row_indexes, [1, 1, 4, 5])
        self.assertFalse(report.truncated)

    def test_vcf_stream_requires_iterator_instead_of_whole_text(self) -> None:
        with self.assertRaises(Exception):
            StreamingVariantImporter().import_vcf(VCF, source_id="whole-text")  # type: ignore[arg-type]

    def test_include_reference_and_no_call_are_explicit_opt_ins(self) -> None:
        report = StreamingVariantImporter().import_vcf(
            iter(VCF.splitlines(keepends=True)),
            source_id="included",
            include_reference=True,
            include_no_call=True,
        )
        self.assertEqual(report.record_count, 5)
        self.assertEqual(report.row_count, 6)
        self.assertEqual(report.accepted_count, 4)
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

    def test_text_chunk_decoder_keeps_lines_and_final_fragment(self) -> None:
        lines = tuple(iter_text_lines_from_chunks((b"a\n", b"b", b"\n", b"c")))
        self.assertEqual(lines, ("a\n", "b\n", "c"))

    def test_contracts_are_versioned_and_data_free(self) -> None:
        schema = streaming_intake_schema()
        self.assertEqual(schema["version"], "streaming-intake-v1")
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
                "##fileformat=VCFv4.3\n"
                "##contig=<ID=7>\n"
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
                "7\t10\trs1\tA\tT\t.\tPASS\t.\n"
            ).encode()
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
            self.assertEqual(schema_payload["version"], "streaming-intake-v1")
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
