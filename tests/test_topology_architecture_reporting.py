"""Reporting and release projection tests for D09."""

from __future__ import annotations

import unittest

from glio_noncode.topology_architecture_artifacts import topology_architecture_artifacts_are_safe
from glio_noncode.topology_architecture_reporting import (
    build_topology_architecture_report,
    topology_architecture_report_json,
    topology_architecture_report_lines,
)
from glio_noncode.topology_architecture_runtime import run_topology_architecture


class TopologyArchitectureReportingTests(unittest.TestCase):
    def test_report_is_published_and_complete(self) -> None:
        runtime = run_topology_architecture()
        report = build_topology_architecture_report(runtime)
        self.assertTrue(report["accepted"])
        self.assertEqual(report["metrics"]["case_count"], 64)
        self.assertEqual(report["metrics"]["operation_count"], 16)
        self.assertEqual(report["stage_count"], 24)
        self.assertEqual(report["depth"]["check_count"], 458)
        self.assertEqual(len(report["release"]["artifact_ids"]), 6)
        self.assertTrue(topology_architecture_artifacts_are_safe(runtime.artifacts))

    def test_json_and_line_projection_are_stable(self) -> None:
        runtime = run_topology_architecture()
        text = topology_architecture_report_json(runtime)
        self.assertIn('"accepted": true', text)
        lines = topology_architecture_report_lines(runtime)
        self.assertEqual(len(lines), 5)
        self.assertIn("cases=64", lines[3])


if __name__ == "__main__":
    unittest.main()
