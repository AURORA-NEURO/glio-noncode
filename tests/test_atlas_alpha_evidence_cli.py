from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.atlas_alpha_evidence_public_data import default_atlas_alpha_evidence_fixture
from glio_noncode.cli import main


class AtlasAlphaEvidenceCliTests(unittest.TestCase):
    def test_evaluation_audit_and_contract_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evaluation = root / "evaluation.json"
            audit = root / "audit.json"
            contracts = root / "contracts.json"
            self.assertEqual(
                main(["evaluate-atlas-alpha-evidence", "--output", str(evaluation)]), 0
            )
            self.assertEqual(main(["audit-atlas-alpha-evidence-data", "--output", str(audit)]), 0)
            self.assertEqual(
                main(["atlas-alpha-evidence-contracts", "--output", str(contracts)]), 0
            )
            self.assertTrue(json.loads(evaluation.read_text(encoding="utf-8"))["accepted"])
            self.assertTrue(json.loads(audit.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(len(json.loads(contracts.read_text(encoding="utf-8"))["contracts"]), 4)

    def test_view_trace_and_text_export_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            view = root / "view.json"
            trace = root / "trace.json"
            receipts = root / "receipts.csv"
            review = root / "review.csv"
            markdown = root / "review.md"
            metrics = root / "metrics.csv"
            commands = (
                (["atlas-alpha-evidence-review-view", "--output", str(view)], view),
                (
                    ["atlas-alpha-evidence-trace", "--run-id", "trace-cli", "--output", str(trace)],
                    trace,
                ),
                (["export-atlas-alpha-evidence-receipts-csv", "--output", str(receipts)], receipts),
                (["export-atlas-alpha-evidence-review-csv", "--output", str(review)], review),
                (
                    ["export-atlas-alpha-evidence-review-markdown", "--output", str(markdown)],
                    markdown,
                ),
                (["export-atlas-alpha-evidence-metrics-csv", "--output", str(metrics)], metrics),
            )
            for argv, path in commands:
                self.assertEqual(main(argv), 0)
                self.assertTrue(path.exists())
                self.assertTrue(path.read_text(encoding="utf-8"))
            self.assertEqual(json.loads(view.read_text(encoding="utf-8"))["review_count"], 12)
            self.assertEqual(len(json.loads(trace.read_text(encoding="utf-8"))["events"]), 9)
            self.assertEqual(receipts.read_text(encoding="utf-8").count("\n"), 17)
            self.assertIn("Atlas-alpha evidence review", markdown.read_text(encoding="utf-8"))

    def test_quality_runtime_bundle_and_release_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            quality = root / "quality.json"
            metrics = root / "metrics.json"
            bundle = root / "bundle.json"
            lineage = root / "lineage.json"
            reconciliation = root / "reconciliation.json"
            runtime = root / "runtime.json"
            release = root / "release.json"
            commands = (
                (["atlas-alpha-evidence-quality-gate", "--output", str(quality)], quality),
                (["atlas-alpha-evidence-metrics", "--output", str(metrics)], metrics),
                (["build-atlas-alpha-evidence-bundle", "--output", str(bundle)], bundle),
                (["atlas-alpha-evidence-lineage", "--output", str(lineage)], lineage),
                (
                    ["atlas-alpha-evidence-reconciliation", "--output", str(reconciliation)],
                    reconciliation,
                ),
                (
                    [
                        "run-atlas-alpha-evidence-pipeline",
                        "--run-id",
                        "cli-test",
                        "--output",
                        str(runtime),
                    ],
                    runtime,
                ),
                (
                    [
                        "build-atlas-alpha-evidence-release",
                        "--run-id",
                        "cli-release",
                        "--output",
                        str(release),
                    ],
                    release,
                ),
            )
            for argv, path in commands:
                self.assertEqual(main(argv), 0)
                self.assertTrue(path.exists())
                self.assertTrue(json.loads(path.read_text(encoding="utf-8")))
            self.assertTrue(json.loads(quality.read_text(encoding="utf-8"))["accepted"])
            self.assertTrue(json.loads(runtime.read_text(encoding="utf-8"))["accepted"])
            self.assertTrue(json.loads(release.read_text(encoding="utf-8"))["accepted"])

    def test_replay_scenario_commands_accept(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            replay = root / "replay.json"
            scenarios = root / "scenarios.json"
            self.assertEqual(main(["replay-atlas-alpha-evidence", "--output", str(replay)]), 0)
            self.assertEqual(
                main(["evaluate-atlas-alpha-evidence-scenarios", "--output", str(scenarios)]), 0
            )
            self.assertTrue(json.loads(replay.read_text(encoding="utf-8"))["accepted"])
            self.assertTrue(json.loads(scenarios.read_text(encoding="utf-8"))["accepted"])

    def test_serialized_fixture_round_trip_via_cli(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture_path = root / "fixture.json"
            evaluation = root / "evaluation.json"
            fixture_path.write_text(
                json.dumps(
                    default_atlas_alpha_evidence_fixture().to_dict(), indent=2, sort_keys=True
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "evaluate-atlas-alpha-evidence",
                        str(fixture_path),
                        "--output",
                        str(evaluation),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(evaluation.read_text(encoding="utf-8"))["accepted"])


if __name__ == "__main__":
    unittest.main()
