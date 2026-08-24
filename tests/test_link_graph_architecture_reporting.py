"""D10 report and release projection tests."""

from __future__ import annotations

import unittest

from glio_noncode.link_graph_architecture_artifacts import (
    link_graph_architecture_artifacts_are_safe,
)
from glio_noncode.link_graph_architecture_reporting import (
    build_link_graph_architecture_report,
    link_graph_architecture_report_json,
    link_graph_architecture_report_lines,
)
from glio_noncode.link_graph_architecture_runtime import run_link_graph_architecture


class LinkGraphArchitectureReportingTests(unittest.TestCase):
    def test_report_is_published_and_complete(self) -> None:
        runtime = run_link_graph_architecture()
        report = build_link_graph_architecture_report(runtime)
        self.assertTrue(report["accepted"])
        self.assertEqual(report["metrics"]["case_count"], 64)
        self.assertEqual(report["stage_count"], 22)
        self.assertEqual(report["artifact_count"], 6)
        self.assertTrue(link_graph_architecture_artifacts_are_safe(runtime.artifacts))

    def test_json_and_line_projection_are_stable(self) -> None:
        runtime = run_link_graph_architecture()
        self.assertIn('"accepted": true', link_graph_architecture_report_json(runtime))
        lines = link_graph_architecture_report_lines(runtime)
        self.assertEqual(len(lines), 5)
        self.assertIn("cases=64", lines[3])


if __name__ == "__main__":
    unittest.main()
