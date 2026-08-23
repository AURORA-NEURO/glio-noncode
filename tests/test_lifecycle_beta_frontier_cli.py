from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main


class LifecycleBetaFrontierCliTests(unittest.TestCase):
    def test_all_depth_commands_write_json(self) -> None:
        commands = (
            "lifecycle-beta-frontier-data-audit",
            "lifecycle-beta-frontier-evaluate",
            "lifecycle-beta-frontier-pipeline",
            "lifecycle-beta-frontier-thresholds",
            "lifecycle-beta-frontier-validation-matrix",
            "lifecycle-beta-frontier-handoff",
        )
        with tempfile.TemporaryDirectory() as directory:
            for command in commands:
                output = Path(directory) / f"{command}.json"
                self.assertEqual(main([command, "--output", str(output)]), 0)
                payload = json.loads(output.read_text(encoding="utf-8"))
                self.assertTrue(payload)
                self.assertTrue(payload.get("accepted", True), command)

    def test_pipeline_exposes_stage_and_depth_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "pipeline.json"
            self.assertEqual(main(["lifecycle-beta-frontier-pipeline", "--output", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["stages"]), 25)
            self.assertEqual(payload["thresholds"]["profile_count"], 8)
            self.assertEqual(payload["thresholds"]["probe_count"], 40)
            self.assertEqual(payload["validation_matrix"]["cell_count"], 32)
            self.assertEqual(payload["handoff"]["record_count"], 32)

    def test_evaluation_exposes_all_operations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "evaluation.json"
            self.assertEqual(main(["lifecycle-beta-frontier-evaluate", "--output", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["executions"]), 32)
            self.assertEqual(len(payload["checks"]), 166)
            self.assertEqual(payload["failed_check_ids"], [])

    def test_threshold_command_exposes_boundary_positions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "thresholds.json"
            self.assertEqual(main(["lifecycle-beta-frontier-thresholds", "--output", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["profiles"]), 8)
            self.assertEqual(len(payload["probes"]), 40)
            self.assertEqual({item["position"] for item in payload["probes"]}, {"below", "lower", "nominal", "upper", "above"})

    def test_matrix_command_exposes_six_planes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "matrix.json"
            self.assertEqual(main(["lifecycle-beta-frontier-validation-matrix", "--output", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["cell_count"], 32)
            self.assertEqual(len(payload["axes"]), 6)

    def test_handoff_command_exposes_public_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "handoff.json"
            self.assertEqual(main(["lifecycle-beta-frontier-handoff", "--output", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["record_count"], 32)
            self.assertEqual(payload["operation_count"], 8)
            self.assertEqual(len(payload["excluded_uses"]), 5)


if __name__ == "__main__":
    unittest.main()
