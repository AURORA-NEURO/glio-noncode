from __future__ import annotations

import json
import subprocess
import sys
import unittest


class PlatformFrontierCliTests(unittest.TestCase):
    def _run(self, command: str) -> object:
        result = subprocess.run([sys.executable, "-m", "glio_noncode", command], check=True, capture_output=True, text=True)
        return json.loads(result.stdout)

    def test_data_audit(self) -> None:
        value = self._run("platform-frontier-data-audit")
        self.assertTrue(value["accepted"])
        self.assertEqual(len(value["checks"]), 9)

    def test_evaluation(self) -> None:
        value = self._run("platform-frontier-evaluate")
        self.assertTrue(value["accepted"])
        self.assertEqual(len(value["executions"]), 16)
        self.assertEqual(len(value["checks"]), 80)

    def test_pipeline_and_depth(self) -> None:
        pipeline = self._run("platform-frontier-pipeline")
        depth = self._run("platform-frontier-depth")
        self.assertTrue(pipeline["accepted"])
        self.assertEqual(len(pipeline["stages"]), 24)
        self.assertTrue(depth["accepted"])

    def test_projection_commands(self) -> None:
        thresholds = self._run("platform-frontier-thresholds")
        validation = self._run("platform-frontier-validation-matrix")
        dictionary = self._run("platform-frontier-data-dictionary")
        access = self._run("platform-frontier-access")
        self.assertEqual(thresholds["probe_count"], 16)
        self.assertEqual(validation["cell_count"], 64)
        self.assertEqual(dictionary["field_count"], 14)
        self.assertTrue(access["accepted"])


if __name__ == "__main__":
    unittest.main()
