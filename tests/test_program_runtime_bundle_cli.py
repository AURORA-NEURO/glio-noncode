"""CLI verification for writing and reopening the program release bundle."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


class ProgramRuntimeBundleCliTests(unittest.TestCase):
    def test_bundle_and_verify_commands(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glio-program-release-cli-") as directory:
            bundle = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "glio_noncode",
                    "architecture-program-bundle",
                    "--output",
                    directory,
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(bundle.returncode, 0, bundle.stderr)
            self.assertEqual(json.loads(bundle.stdout)["state"], "published")
            self.assertTrue((Path(directory) / "program-release-manifest.json").exists())

            verification = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "glio_noncode",
                    "architecture-program-verify-bundle",
                    directory,
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(verification.returncode, 0, verification.stderr)
            self.assertTrue(json.loads(verification.stdout)["accepted"])


if __name__ == "__main__":
    unittest.main()
