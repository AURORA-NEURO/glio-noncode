from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from glio_noncode._cli_sequence import build_analysis_report
from glio_noncode._cli_sequence import main as sequence_main
from glio_noncode.cli import main as cli_main
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import content_hash


def _input() -> dict[str, object]:
    return {
        "schema": "glio-noncode.sequence-haplotype-input.v1",
        "genome_build": "GRCh38",
        "sequence": {
            "assembly": "GRCh38",
            "chromosome": "chr7",
            "start": 100,
            "end": 111,
            "sequence": "AACCGGTTAACC",
            "source_id": "SRC-UCSC-REST",
            "source_url": "https://api.example/sequence",
            "source_version": "fixture-1",
            "retrieved_at": "2026-08-20T00:00:00+00:00",
        },
        "variants": [
            {
                "notation": "7:103:C>T",
                "variant_id": "snv-1",
                "sample_id": "PRIVATE_SAMPLE_1",
                "phase_set": "phase-1",
                "haplotype_index": 1,
            },
            {
                "notation": "7:104:G>A",
                "variant_id": "snv-2",
                "sample_id": "PRIVATE_SAMPLE_1",
                "phase_set": "phase-1",
                "haplotype_index": 1,
            },
        ],
        "motifs": [
            {
                "motif_id": "joint",
                "name": "jointly-created motif",
                "pattern": "CTAG",
                "source_id": "motif-fixture",
            }
        ],
    }


class SequenceHaplotypeCliTests(unittest.TestCase):
    def test_build_analysis_report_runs_existing_inference_without_raw_sequence_output(
        self,
    ) -> None:
        report = build_analysis_report(_input())

        self.assertEqual(report["schema"], "glio-noncode.sequence-haplotype-analysis.v1")
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["analysis_state"], "supported")
        self.assertEqual(report["analysis"]["variant_ids"], ["snv-1", "snv-2"])
        self.assertEqual(report["analysis"]["created_hits"][0]["matched_sequence"], "CTAG")
        self.assertEqual(report["inputs"]["variant_count"], 2)
        serialized = json.dumps(report, sort_keys=True)
        self.assertNotIn("AACCGGTTAACC", serialized)
        self.assertNotIn("PRIVATE_SAMPLE_1", serialized)
        self.assertEqual(
            report["content_address"],
            content_hash(
                {key: value for key, value in report.items() if key != "content_address"},
                prefix="sequence-haplotype-analysis",
            ),
        )

    def test_cli_reads_bounded_json_and_writes_deterministic_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "input.json"
            output_path = root / "result.json"
            input_path.write_text(json.dumps(_input()), encoding="utf-8")
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = sequence_main([str(input_path), "--output", str(output_path)])

            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "")
            report = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(len(report["analysis"]["created_hits"]), 1)

    def test_cli_can_save_the_public_report_to_an_immutable_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "input.json"
            output_path = root / "result.json"
            workspace = root / "workspace"
            input_path.write_text(json.dumps(_input()), encoding="utf-8")
            stderr = io.StringIO()
            with redirect_stdout(io.StringIO()), redirect_stderr(stderr):
                exit_code = sequence_main(
                    [
                        str(input_path),
                        "--output",
                        str(output_path),
                        "--save-to-workspace",
                        "--data-root",
                        str(workspace),
                    ]
                )
            self.assertEqual(exit_code, 0)
            self.assertIn("Saved sequence analysis seq-", stderr.getvalue())
            self.assertEqual(len(list((workspace / "sequence-analyses").glob("seq-*.json"))), 1)

    def test_cli_rejects_invalid_input_and_static_command_index_exposes_surface(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            invalid_path = Path(directory) / "invalid.json"
            invalid_path.write_text("{}", encoding="utf-8")
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = sequence_main([str(invalid_path)])
            self.assertEqual(exit_code, 2)
            self.assertEqual(json.loads(stdout.getvalue())["status"], "invalid")

        stdout = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(io.StringIO()):
            exit_code = cli_main(["commands", "show", "sequence-haplotype"])
        self.assertEqual(exit_code, 0)
        self.assertIn("sequence-haplotype", stdout.getvalue())

    def test_invalid_phase_and_schema_are_rejected_without_partial_analysis(self) -> None:
        invalid = _input()
        invalid["schema"] = "other.v1"
        with self.assertRaisesRegex(ValidationError, "schema is unsupported"):
            build_analysis_report(invalid)

        invalid = _input()
        invalid["variants"] = [dict(invalid["variants"][0], phase_set="unphased")]  # type: ignore[index]
        with self.assertRaisesRegex(ValidationError, "resolved phase block"):
            build_analysis_report(invalid)

    def test_abstention_is_a_completed_analysis_state(self) -> None:
        invalid = _input()
        invalid["variants"] = [
            dict(invalid["variants"][0], notation="7:103:BND:chr8:200")  # type: ignore[index]
        ]
        report = build_analysis_report(invalid)
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["analysis_state"], "abstained")
        self.assertTrue(report["analysis"]["limitations"])
