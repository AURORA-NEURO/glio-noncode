from __future__ import annotations

import json
import subprocess
import sys
import unittest


class ControlFrontierCliTests(unittest.TestCase):
    def _run(self, command: str) -> dict[str, object]:
        result = subprocess.run([sys.executable, "-m", "glio_noncode", command], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def test_pipeline_command_returns_accepted_runtime(self) -> None:
        payload = self._run("control-frontier-pipeline")
        self.assertTrue(payload["accepted"])
        self.assertEqual(len(payload["stages"]), 24)
        self.assertTrue(payload["depth"]["accepted"])

    def test_evaluation_command_keeps_controls(self) -> None:
        payload = self._run("control-frontier-evaluate")
        self.assertTrue(payload["accepted"])
        self.assertEqual(len(payload["executions"]), 32)
        self.assertEqual(sum(item["role"] == "control" for item in payload["executions"]), 24)

    def test_data_and_depth_commands_return_receipts(self) -> None:
        audit = self._run("control-frontier-data-audit")
        depth = self._run("control-frontier-depth")
        self.assertTrue(audit["accepted"])
        self.assertTrue(depth["accepted"])


if __name__ == "__main__":
    unittest.main()
