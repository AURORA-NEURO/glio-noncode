from __future__ import annotations

import gzip
import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from glio_noncode._cli_sequence_files import build_parser, build_sequence_haplotype_input, main
from glio_noncode.errors import ValidationError


def _write_downloads(root: Path, *, phased: bool = True) -> tuple[Path, Path, Path]:
    fasta = root / "window.fa.gz"
    vcf = root / "calls.vcf"
    motifs = root / "motifs.json"
    with gzip.open(fasta, "wt", encoding="ascii") as handle:
        handle.write(">chr7 downloaded-reference\n")
        handle.write("A" * 99 + "AACCGGTTAACC\n")
    genotype = "1|0:phase-1" if phased else "1/0:phase-1"
    vcf.write_text(
        "##fileformat=VCFv4.3\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE_1\n"
        f"7\t103\tsnv-1\tC\tT\t.\tPASS\t.\tGT:PS\t{genotype}\n"
        f"7\t104\tsnv-2\tG\tA\t.\tPASS\t.\tGT:PS\t{genotype}\n",
        encoding="utf-8",
    )
    motifs.write_text(
        json.dumps(
            {
                "motifs": [
                    {
                        "motif_id": "joint",
                        "name": "jointly-created motif",
                        "pattern": "CTAG",
                        "source_id": "motif-fixture",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return fasta, vcf, motifs


def _args(fasta: Path, vcf: Path, motifs: Path, output: Path) -> list[str]:
    return [
        "--fasta",
        str(fasta),
        "--vcf",
        str(vcf),
        "--sample-id",
        "SAMPLE_1",
        "--genome-build",
        "GRCh38",
        "--chromosome",
        "chr7",
        "--start",
        "100",
        "--end",
        "111",
        "--source-id",
        "downloaded-reference-fixture",
        "--source-url",
        "https://example.test/downloads/fixture",
        "--source-version",
        "fixture-2026-08",
        "--retrieved-at",
        "2026-08-20T00:00:00+00:00",
        "--motifs",
        str(motifs),
        "--output",
        str(output),
    ]


class SequenceFilesCliTests(unittest.TestCase):
    def test_ensembl_coordinate_style_fasta_header_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fasta, vcf, motifs = _write_downloads(root)
            with gzip.open(fasta, "wt", encoding="ascii") as handle:
                handle.write(
                    ">chromosome:GRCh38:7:100:111:1 downloaded reference\n"
                    "AACCGGTTAACC\n"
                )
            args = build_parser().parse_args(_args(fasta, vcf, motifs, root / "report.json"))
            args.genome_build = "GRCh38"
            self.assertEqual(
                build_sequence_haplotype_input(args)["sequence"]["sequence"],
                "AACCGGTTAACC",
            )

    def test_local_downloads_build_exact_input_and_analysis_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fasta, vcf, motifs = _write_downloads(root)
            args = build_parser().parse_args(_args(fasta, vcf, motifs, root / "report.json"))
            input_value = build_sequence_haplotype_input(args)
            self.assertEqual(input_value["sequence"]["sequence"], "AACCGGTTAACC")
            self.assertEqual(len(input_value["variants"]), 2)
            self.assertEqual(input_value["variants"][0]["phase_set"], "phase-1")

            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main(_args(fasta, vcf, motifs, root / "report.json"))
            self.assertEqual(exit_code, 0)
            report = json.loads((root / "report.json").read_text(encoding="utf-8"))
            serialized = json.dumps(report, sort_keys=True)
            self.assertEqual(report["analysis"]["created_hits"][0]["matched_sequence"], "CTAG")
            self.assertNotIn("AACCGGTTAACC", serialized)
            self.assertNotIn("SAMPLE_1", serialized)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "")

    def test_download_sha256_digests_are_verified_before_decompression(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fasta, vcf, motifs = _write_downloads(root)
            args = _args(fasta, vcf, motifs, root / "report.json")
            args.extend(
                [
                    "--fasta-sha256",
                    hashlib.sha256(fasta.read_bytes()).hexdigest(),
                    "--vcf-sha256",
                    hashlib.sha256(vcf.read_bytes()).hexdigest(),
                ]
            )
            parsed = build_parser().parse_args(args)
            self.assertEqual(
                build_sequence_haplotype_input(parsed)["sequence"]["sequence"],
                "AACCGGTTAACC",
            )
            args[args.index("--vcf-sha256") + 1] = "0" * 64
            with self.assertRaisesRegex(ValidationError, "SHA-256 digest does not match"):
                build_sequence_haplotype_input(build_parser().parse_args(args))

    def test_malformed_download_sha256_is_rejected_before_file_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fasta, vcf, motifs = _write_downloads(root)
            args = _args(fasta, vcf, motifs, root / "report.json")
            args.extend(["--fasta-sha256", "not-a-digest"])
            with self.assertRaisesRegex(ValidationError, "exactly 64 hexadecimal"):
                build_sequence_haplotype_input(build_parser().parse_args(args))

    def test_unphased_download_is_rejected_before_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fasta, vcf, motifs = _write_downloads(root, phased=False)
            args = build_parser().parse_args(_args(fasta, vcf, motifs, root / "report.json"))
            with self.assertRaisesRegex(ValidationError, "not explicitly phased"):
                build_sequence_haplotype_input(args)

    def test_invalid_file_path_returns_bounded_invalid_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "report.json"
            stderr = io.StringIO()
            with redirect_stdout(io.StringIO()), redirect_stderr(stderr):
                exit_code = main(
                    [
                        "--fasta",
                        str(root / "missing.fa"),
                        "--vcf",
                        str(root / "missing.vcf"),
                        "--sample-id",
                        "SAMPLE_1",
                        "--genome-build",
                        "GRCh38",
                        "--chromosome",
                        "chr7",
                        "--start",
                        "100",
                        "--end",
                        "111",
                        "--source-id",
                        "source",
                        "--source-url",
                        "https://example.test/source",
                        "--source-version",
                        "1",
                        "--retrieved-at",
                        "2026-08-20T00:00:00+00:00",
                        "--output",
                        str(output),
                    ]
                )
            self.assertEqual(exit_code, 2)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["status"], "invalid")
