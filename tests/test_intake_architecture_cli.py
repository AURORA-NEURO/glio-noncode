"""CLI coverage for the D01 public aggregate architecture commands."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main
from glio_noncode.intake_architecture_public_data import intake_architecture_fixture_json


class IntakeArchitectureCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.fixture = self.root / "fixture.json"
        self.fixture.write_text(intake_architecture_fixture_json(), encoding="utf-8")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _run_json(self, *args: str) -> dict[str, object]:
        output = self.root / f"output-{len(tuple(self.root.iterdir()))}.json"
        code = main([*args, "--output", str(output)])
        self.assertEqual(code, 0)
        return json.loads(output.read_text(encoding="utf-8"))

    def test_fixture_command(self) -> None:
        payload = self._run_json("intake-architecture-fixture")
        self.assertEqual(len(payload["operations"]), 16)
        self.assertEqual(len(payload["cases"]), 64)

    def test_data_audit_command(self) -> None:
        payload = self._run_json("intake-architecture-data-audit", "--input", str(self.fixture))
        self.assertTrue(payload["accepted"])
        self.assertEqual(len(payload["checks"]), 12)

    def test_plan_command(self) -> None:
        payload = self._run_json("intake-architecture-plan", "--input", str(self.fixture))
        self.assertTrue(payload["accepted"])
        self.assertEqual(len(payload["nodes"]), 16)

    def test_evaluate_command(self) -> None:
        payload = self._run_json("intake-architecture-evaluate", "--input", str(self.fixture))
        self.assertTrue(payload["accepted"])
        self.assertEqual(payload["passed_cases"], 64)

    def test_runtime_command(self) -> None:
        payload = self._run_json("intake-architecture-runtime", "--input", str(self.fixture))
        self.assertEqual(payload["state"], "accepted")
        self.assertEqual(len(payload["stages"]), 20)

    def test_quality_command(self) -> None:
        payload = self._run_json("intake-architecture-quality", "--input", str(self.fixture))
        self.assertTrue(payload["accepted"])
        self.assertEqual(payload["passed_checks"], 18)

    def test_depth_command(self) -> None:
        payload = self._run_json("intake-architecture-depth", "--input", str(self.fixture))
        self.assertTrue(payload["accepted"])
        self.assertEqual(payload["case_count"], 64)

    def test_replay_command(self) -> None:
        payload = self._run_json("intake-architecture-replay", "--input", str(self.fixture))
        self.assertTrue(payload["accepted"])
        self.assertTrue(payload["deterministic"])

    def test_validation_command(self) -> None:
        payload = self._run_json("intake-architecture-validation", "--input", str(self.fixture))
        self.assertTrue(payload["accepted"])
        self.assertEqual(len(payload["cells"]), 112)

    def test_runbook_command(self) -> None:
        payload = self._run_json("intake-architecture-runbook", "--input", str(self.fixture))
        self.assertTrue(payload["accepted"])
        self.assertIn("preflight", payload)

    def test_report_command(self) -> None:
        output = self.root / "report.md"
        self.assertEqual(main(["intake-architecture-report", "--input", str(self.fixture), "--format", "markdown", "--output", str(output)]), 0)
        self.assertIn("D01 Variant Identity", output.read_text(encoding="utf-8"))

    def test_review_csv_command(self) -> None:
        output = self.root / "review.csv"
        self.assertEqual(main(["intake-architecture-review-csv", "--input", str(self.fixture), "--output", str(output)]), 0)
        self.assertEqual(len(output.read_text(encoding="utf-8").splitlines()), 49)

    def test_failures_command(self) -> None:
        payload = self._run_json("intake-architecture-failures")
        self.assertTrue(payload["accepted"])
        self.assertEqual(len(payload["probes"]), 3)

    def test_schema_command(self) -> None:
        payload = self._run_json("intake-architecture-schema")
        self.assertEqual(payload["schema_id"], "intake-architecture-d01")
        self.assertEqual(len(payload["fields"]), 11)

    def test_query_command(self) -> None:
        payload = self._run_json("intake-architecture-query", "--input", str(self.fixture), "--query", "review")
        self.assertEqual(payload["matched"], 48)

    def test_invariants_command(self) -> None:
        payload = self._run_json("intake-architecture-invariants", "--input", str(self.fixture))
        self.assertTrue(payload["accepted"])
        self.assertEqual(payload["issues"], [])


if __name__ == "__main__":
    unittest.main()
