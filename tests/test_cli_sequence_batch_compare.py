from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from glio_noncode._cli_sequence_batch import build_batch_report
from glio_noncode._cli_sequence_batch_compare import build_batch_comparison, main
from glio_noncode.cli import main as cli_main
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import content_hash
from tests.test_cli_sequence import _input
from tests.test_cli_sequence_batch import _batch_input


class SequenceBatchCompareTests(unittest.TestCase):
    def test_exact_aggregate_comparison_reports_prevalence_direction(self) -> None:
        left = build_batch_report(_batch_input())
        right_input = _batch_input()
        right_input["analyses"] = [_input(), _input(), _input()]  # type: ignore[index]
        right = build_batch_report(right_input)
        report = build_batch_comparison(left, right)
        self.assertEqual(report["schema"], "glio-noncode.sequence-haplotype-batch-comparison.v1")
        self.assertEqual(report["changes"][0]["left_analysis_count"], 2)
        self.assertEqual(report["changes"][0]["right_analysis_count"], 3)
        self.assertEqual(report["changes"][0]["direction"], "increased")
        serialized = json.dumps(report)
        self.assertNotIn("AACCGGTTAACC", serialized)
        self.assertNotIn("PRIVATE_SAMPLE_1", serialized)
        self.assertEqual(
            report["content_address"],
            content_hash(
                {key: value for key, value in report.items() if key != "content_address"},
                prefix="sequence-batch-comparison",
            ),
        )

    def test_mixed_reference_contexts_are_rejected(self) -> None:
        left = build_batch_report(_batch_input())
        other_input = _batch_input()
        other_input["analyses"] = [dict(_input(), genome_build="hg19")]  # type: ignore[index]
        right = build_batch_report(other_input)
        with self.assertRaisesRegex(ValidationError, "shared reference context"):
            build_batch_comparison(left, right)

    def test_missing_change_is_not_reported_and_identical_batches_are_unchanged(self) -> None:
        left = build_batch_report(_batch_input())
        abstained_only = _input()
        abstained_only["variants"] = [
            dict(abstained_only["variants"][0], notation="7:103:BND:chr8:200")  # type: ignore[index]
        ]
        right = build_batch_report(
            {
                "schema": "glio-noncode.sequence-haplotype-batch-input.v1",
                "analyses": [abstained_only],
            }
        )
        missing = build_batch_comparison(left, right)
        self.assertEqual(missing["changes"][0]["direction"], "not_reported_in_one_batch")
        self.assertIsNone(missing["changes"][0]["delta_fraction"])
        unchanged = build_batch_comparison(left, left)
        self.assertTrue(all(item["direction"] == "unchanged" for item in unchanged["changes"]))

    def test_comparison_is_reproducible_for_reordered_change_rows(self) -> None:
        left = build_batch_report(_batch_input())
        reordered = json.loads(json.dumps(left))
        reordered["motif_changes"] = list(reversed(reordered["motif_changes"]))
        reordered["content_address"] = content_hash(
            {key: value for key, value in reordered.items() if key != "content_address"},
            prefix="sequence-haplotype-batch-analysis",
        )
        report = build_batch_comparison(left, reordered)
        self.assertEqual(report["changes"][0]["direction"], "unchanged")
        self.assertEqual(report["changes"][0]["delta_fraction"], 0.0)

    def test_cli_invalid_input_is_a_bounded_nonzero_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left = root / "left.json"
            right = root / "right.json"
            output = root / "invalid.json"
            left.write_text(json.dumps({"status": "invalid"}), encoding="utf-8")
            right.write_text(json.dumps({"status": "invalid"}), encoding="utf-8")
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                exit_code = main([str(left), str(right), "--output", str(output)])
            self.assertEqual(exit_code, 2)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(
                payload["schema"],
                "glio-noncode.sequence-haplotype-batch-comparison.v1",
            )
            self.assertEqual(payload["status"], "invalid")
            self.assertNotIn("AACCGGTTAACC", json.dumps(payload))

    def test_cli_writes_comparison_and_static_index_exposes_command(self) -> None:
        left = build_batch_report(_batch_input())
        right = build_batch_report(
            {"schema": "glio-noncode.sequence-haplotype-batch-input.v1", "analyses": [_input()]}
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left_path, right_path, output_path = (
                root / "left.json",
                root / "right.json",
                root / "comparison.json",
            )
            left_path.write_text(json.dumps(left), encoding="utf-8")
            right_path.write_text(json.dumps(right), encoding="utf-8")
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                exit_code = main([str(left_path), str(right_path), "--output", str(output_path)])
            self.assertEqual(exit_code, 0)
            self.assertEqual(
                json.loads(output_path.read_text(encoding="utf-8"))["status"], "completed"
            )
        stdout = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(io.StringIO()):
            exit_code = cli_main(["commands", "show", "sequence-batch-compare"])
        self.assertEqual(exit_code, 0)
        self.assertIn("sequence-batch-compare", stdout.getvalue())
