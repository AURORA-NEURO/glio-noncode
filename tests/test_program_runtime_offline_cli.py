"""CLI contract tests for the architecture-program offline handoff."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


class ProgramRuntimeOfflineCliTests(unittest.TestCase):
    def _run(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "glio_noncode", *arguments],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_materialize_verify_query_and_certify(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glio-program-offline-cli-") as directory:
            destination = str(Path(directory) / "handoff")
            built = self._run(
                "architecture-program-offline-bundle",
                "--destination",
                destination,
                "--bundle-id",
                "cli-bundle",
                "--run-id",
                "cli-run",
            )
            self.assertEqual(built.returncode, 0, built.stderr)
            self.assertTrue(json.loads(built.stdout)["accepted"])
            verified = self._run("architecture-program-offline-verify", destination)
            self.assertEqual(verified.returncode, 0, verified.stderr)
            self.assertTrue(json.loads(verified.stdout)["accepted"])
            queried = self._run(
                "architecture-program-offline-query",
                destination,
                "--resource",
                "domains",
                "--domain-id",
                "D08",
            )
            self.assertEqual(queried.returncode, 0, queried.stderr)
            self.assertEqual(json.loads(queried.stdout)["total"], 1)
            certified = self._run(
                "architecture-program-offline-certification",
                destination,
            )
            self.assertEqual(certified.returncode, 0, certified.stderr)
            self.assertTrue(json.loads(certified.stdout)["accepted"])
            observed = self._run(
                "architecture-program-offline-observability",
                destination,
                "--format",
                "metrics-csv",
            )
            self.assertEqual(observed.returncode, 0, observed.stderr)
            self.assertIn("metric_id,plane,name,value,unit,content_address", observed.stdout)

    def test_schema_validation_and_runtime_commands(self) -> None:
        schema = self._run("architecture-program-offline-schema")
        self.assertEqual(schema.returncode, 0, schema.stderr)
        self.assertEqual(
            json.loads(schema.stdout)["schema_version"], "program-runtime-offline-schema-v1"
        )
        with tempfile.TemporaryDirectory(prefix="glio-program-offline-cli-runtime-") as directory:
            destination = str(Path(directory) / "handoff")
            built = self._run("architecture-program-offline-bundle", "--destination", destination)
            self.assertEqual(built.returncode, 0, built.stderr)
            manifest_path = str(Path(destination) / "bundle.json")
            validated = self._run("architecture-program-offline-validate", manifest_path)
            self.assertEqual(validated.returncode, 0, validated.stderr)
            self.assertTrue(json.loads(validated.stdout)["accepted"])


if __name__ == "__main__":
    unittest.main()
