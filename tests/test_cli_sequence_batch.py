from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from glio_noncode._cli_sequence import build_analysis_report
from glio_noncode._cli_sequence_batch import build_batch_report, main
from glio_noncode.cli import main as cli_main
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import content_hash
from tests.test_cli_sequence import _input


def _batch_input() -> dict[str, object]:
    first = _input()
    second = json.loads(json.dumps(first))
    second["variants"] = [
        dict(item, variant_id=f"{item['variant_id']}-copy") for item in second["variants"]  # type: ignore[index]
    ]
    third = json.loads(json.dumps(first))
    third["variants"] = [dict(third["variants"][0], notation="7:103:BND:chr8:200")]  # type: ignore[index]
    return {
        "schema": "glio-noncode.sequence-haplotype-batch-input.v1",
        "analyses": [first, second, third],
    }


class SequenceBatchCliTests(unittest.TestCase):
    def test_batch_keeps_shared_context_and_aggregates_motif_changes(self) -> None:
        report = build_batch_report(_batch_input())
        self.assertEqual(report["schema"], "glio-noncode.sequence-haplotype-batch-analysis.v1")
        self.assertEqual(report["design"]["analysis_count"], 3)
        self.assertEqual(report["design"]["supported_count"], 2)
        self.assertEqual(report["design"]["abstained_count"], 1)
        self.assertEqual(report["motif_changes"][0]["analysis_count"], 2)
        self.assertEqual(report["motif_changes"][0]["analysis_fraction"], 2 / 3)
        serialized = json.dumps(report, sort_keys=True)
        self.assertNotIn("AACCGGTTAACC", serialized)
        self.assertNotIn("PRIVATE_SAMPLE_1", serialized)
        self.assertEqual(
            report["content_address"],
            content_hash(
                {key: value for key, value in report.items() if key != "content_address"},
                prefix="sequence-haplotype-batch-analysis",
            ),
        )

    def test_batch_rejects_mixed_reference_contexts(self) -> None:
        raw = _batch_input()
        raw["analyses"] = [raw["analyses"][0], dict(raw["analyses"][1], genome_build="hg19")]  # type: ignore[index]
        with self.assertRaisesRegex(ValidationError, "one reference and motif context"):
            build_batch_report(raw)

    def test_batch_cli_writes_report_and_static_index_exposes_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_path = root / "batch.json"
            output_path = root / "batch-report.json"
            input_path.write_text(json.dumps(_batch_input()), encoding="utf-8")
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                exit_code = main([str(input_path), "--output", str(output_path)])
            self.assertEqual(exit_code, 0)
            self.assertEqual(
                json.loads(output_path.read_text(encoding="utf-8"))["status"],
                "completed",
            )
        stdout = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(io.StringIO()):
            exit_code = cli_main(["commands", "show", "sequence-batch"])
        self.assertEqual(exit_code, 0)
        self.assertIn("sequence-batch", stdout.getvalue())

    def test_batch_input_requires_at_least_one_analysis(self) -> None:
        with self.assertRaisesRegex(ValidationError, "between 1"):
            build_batch_report(
                {"schema": "glio-noncode.sequence-haplotype-batch-input.v1", "analyses": []}
            )

    def test_single_analysis_is_a_valid_aggregate(self) -> None:
        raw = {"schema": "glio-noncode.sequence-haplotype-batch-input.v1", "analyses": [_input()]}
        report = build_batch_report(raw)
        self.assertEqual(report["design"]["analysis_count"], 1)
        self.assertEqual(report["motif_changes"][0]["analysis_fraction"], 1.0)
        self.assertEqual(report["records"][0]["analysis_state"], "supported")
        self.assertEqual(build_analysis_report(_input())["analysis_state"], "supported")
