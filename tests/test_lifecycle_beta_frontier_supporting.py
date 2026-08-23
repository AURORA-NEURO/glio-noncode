from __future__ import annotations

import unittest

from glio_noncode.lifecycle_beta_frontier_api_view import build_lifecycle_beta_frontier_api_view
from glio_noncode.lifecycle_beta_frontier_fixture_eval import evaluate_lifecycle_beta_frontier_fixture
from glio_noncode.lifecycle_beta_frontier_invariants import run_lifecycle_beta_frontier_invariants
from glio_noncode.lifecycle_beta_frontier_metrics import measure_lifecycle_beta_frontier
from glio_noncode.lifecycle_beta_frontier_public_data import default_lifecycle_beta_frontier_fixture
from glio_noncode.lifecycle_beta_frontier_quality_gate import run_lifecycle_beta_frontier_quality_gate
from glio_noncode.lifecycle_beta_frontier_runtime import run_lifecycle_beta_frontier_runtime
from glio_noncode.lifecycle_beta_frontier_schema import default_lifecycle_beta_frontier_schema
from glio_noncode.lifecycle_beta_frontier_source_registry import build_lifecycle_beta_frontier_source_registry
from glio_noncode.lifecycle_beta_frontier_summary import build_lifecycle_beta_frontier_summary
from glio_noncode.lifecycle_beta_frontier_transcript import build_lifecycle_beta_frontier_transcript
from glio_noncode.lifecycle_beta_frontier_views import build_lifecycle_beta_frontier_view
from glio_noncode.lifecycle_beta_frontier_retention import build_lifecycle_beta_frontier_retention_report


class LifecycleBetaFrontierSupportingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_lifecycle_beta_frontier_fixture()
        self.evaluation = evaluate_lifecycle_beta_frontier_fixture(self.fixture)
        self.runtime = run_lifecycle_beta_frontier_runtime(self.fixture, run_id="support-test")

    def test_source_registry_resolves_all_receipts(self) -> None:
        registry = build_lifecycle_beta_frontier_source_registry(self.fixture)
        self.assertTrue(registry.accepted)
        self.assertEqual(registry.source_ids, tuple(sorted(registry.source_ids)))
        self.assertEqual(registry.source("src-tier").title, "Evidence-tier aggregate receipt")

    def test_invariants_are_green(self) -> None:
        registry = build_lifecycle_beta_frontier_source_registry(self.fixture)
        report = run_lifecycle_beta_frontier_invariants(self.fixture, self.evaluation, registry)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.invariants), 8)
        self.assertEqual(report.failed_ids, ())

    def test_summary_conserves_runtime_counts(self) -> None:
        metrics = measure_lifecycle_beta_frontier(self.evaluation)
        summary = build_lifecycle_beta_frontier_summary(
            self.fixture, self.evaluation, metrics, self.runtime.quality
        )
        self.assertEqual(summary.operation_count, 8)
        self.assertEqual(summary.record_count, 32)
        self.assertEqual(summary.positive_count, 8)
        self.assertEqual(summary.control_count, 24)
        self.assertEqual(summary.accepted_count, 8)
        self.assertEqual(summary.failed_check_count, 0)
        self.assertTrue(summary.quality_accepted)

    def test_retention_report_has_all_required_classes(self) -> None:
        report = build_lifecycle_beta_frontier_retention_report(self.fixture, self.runtime)
        self.assertTrue(report.accepted)
        self.assertEqual(report.observed_counts["sources"], 9)
        self.assertEqual(report.observed_counts["executions"], 32)
        self.assertEqual(report.observed_counts["stages"], 25)
        self.assertEqual(len(report.rules), 5)

    def test_transcript_is_ordered_and_addressed(self) -> None:
        transcript = build_lifecycle_beta_frontier_transcript(self.runtime)
        self.assertEqual(len(transcript.lines), 29)
        self.assertEqual(transcript.lines[0], "run_id=support-test")
        self.assertIn("01 data-audit", transcript.lines[4])
        self.assertTrue(transcript.content_address.startswith("sha256:"))
        self.assertTrue(transcript.to_text().endswith("\n"))

    def test_api_view_uses_stable_public_fields(self) -> None:
        view = build_lifecycle_beta_frontier_view(self.evaluation)
        api = build_lifecycle_beta_frontier_api_view(self.evaluation, view)
        self.assertTrue(api.accepted)
        self.assertEqual(api.record_count, 32)
        self.assertEqual(len(api.entries), 32)
        self.assertEqual(set(api.entries[0]), {"record_id", "operation", "role", "state", "accepted", "issues"})
        self.assertEqual(api.links["evaluation"], self.evaluation.content_address)

    def test_report_contains_release_boundary(self) -> None:
        from glio_noncode.lifecycle_beta_frontier_report import render_lifecycle_beta_frontier_report

        report = render_lifecycle_beta_frontier_report(self.runtime)
        self.assertIn("# Lifecycle Beta Frontier Report", report)
        self.assertIn("Accepted: True", report)
        self.assertIn("research-use-only", report.lower())

    def test_schema_registry_and_runtime_addresses_are_closed(self) -> None:
        self.assertTrue(default_lifecycle_beta_frontier_schema().content_address.startswith("sha256:"))
        self.assertTrue(self.runtime.content_address.startswith("sha256:"))
        self.assertTrue(all(item.output_address.startswith("sha256:") for item in self.runtime.stages))


if __name__ == "__main__":
    unittest.main()
