from __future__ import annotations

import json
import unittest

from glio_noncode.causal_alpha_frontier_controls import build_causal_alpha_frontier_control_coverage
from glio_noncode.causal_alpha_frontier_diagnostics import (
    CausalAlphaFrontierDiagnosticSeverity,
    build_causal_alpha_frontier_diagnostics,
)
from glio_noncode.causal_alpha_frontier_fixture_eval import evaluate_causal_alpha_frontier_fixture_deep
from glio_noncode.causal_alpha_frontier_policy import default_causal_alpha_frontier_policy
from glio_noncode.causal_alpha_frontier_projections import build_causal_alpha_frontier_projections
from glio_noncode.causal_alpha_frontier_public_data import default_causal_alpha_frontier_fixture
from glio_noncode.causal_alpha_frontier_review import build_causal_alpha_frontier_review_queue
from glio_noncode.causal_alpha_frontier_traces import build_causal_alpha_frontier_trace_ledger
from glio_noncode.causal_alpha_frontier_runtime import run_causal_alpha_frontier_runtime
from glio_noncode.serialization import jsonable


class CausalAlphaFrontierDiagnosticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_causal_alpha_frontier_fixture()
        self.evaluation = evaluate_causal_alpha_frontier_fixture_deep(self.fixture)
        policy = default_causal_alpha_frontier_policy()
        decisions = policy.decide(self.evaluation)
        review = build_causal_alpha_frontier_review_queue(self.fixture, self.evaluation, decisions)
        self.controls = build_causal_alpha_frontier_control_coverage(self.fixture, self.evaluation, tuple(item.record_id for item in review.items))
        self.traces = build_causal_alpha_frontier_trace_ledger(self.fixture, self.evaluation, decisions, review)
        self.projections = build_causal_alpha_frontier_projections(self.fixture, self.evaluation, self.controls, decisions)

    def test_diagnostics_have_eight_cross_plane_findings(self) -> None:
        report = build_causal_alpha_frontier_diagnostics(self.fixture, self.evaluation, self.controls, self.traces, self.projections)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.findings), 8)
        self.assertEqual(report.error_count, 0)
        self.assertEqual(report.warning_count, 0)
        self.assertEqual(report.failed_checks, ())

    def test_diagnostic_check_ids_are_unique_and_addressed(self) -> None:
        report = build_causal_alpha_frontier_diagnostics(self.fixture, self.evaluation, self.controls, self.traces, self.projections)
        self.assertEqual(len({item.check_id for item in report.findings}), 8)
        self.assertEqual(len({item.finding_id for item in report.findings}), 8)
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in report.findings))
        self.assertTrue(report.content_address.startswith("sha256:"))

    def test_diagnostic_findings_are_all_error_severity_only_when_failing(self) -> None:
        report = build_causal_alpha_frontier_diagnostics(self.fixture, self.evaluation, self.controls, self.traces, self.projections)
        self.assertTrue(all(item.severity is CausalAlphaFrontierDiagnosticSeverity.ERROR for item in report.findings))
        self.assertEqual(report.errors, ())
        self.assertEqual(report.warnings, ())

    def test_each_diagnostic_references_an_evidence_address(self) -> None:
        report = build_causal_alpha_frontier_diagnostics(self.fixture, self.evaluation, self.controls, self.traces, self.projections)
        self.assertTrue(all(item.evidence_addresses for item in report.findings))
        self.assertTrue(all(any(str(address).startswith("sha256:") for address in item.evidence_addresses) for item in report.findings))
        self.assertEqual(report.for_check("foreign-quarantine").expected, 4)
        self.assertEqual(report.for_check("trace-cardinality").observed, 16)

    def test_diagnostic_serialization_is_json_safe(self) -> None:
        report = build_causal_alpha_frontier_diagnostics(self.fixture, self.evaluation, self.controls, self.traces, self.projections)
        payload = jsonable(report)
        encoded = json.dumps(payload, sort_keys=True)
        self.assertGreater(len(encoded), 4000)
        decoded = json.loads(encoded)
        self.assertTrue(decoded["accepted"])
        self.assertEqual(len(decoded["findings"]), 8)

    def test_runtime_exposes_accepted_diagnostics(self) -> None:
        runtime = run_causal_alpha_frontier_runtime(self.fixture, run_id="alpha-diagnostics")
        self.assertTrue(runtime.accepted)
        self.assertTrue(runtime.diagnostics.accepted)
        self.assertEqual(runtime.diagnostics.failed_checks, ())
        self.assertEqual(runtime.diagnostics.for_check("row-identity").observed, runtime.diagnostics.for_check("row-identity").expected)
        self.assertEqual(runtime.artifacts.for_kind("diagnostics")[0].relative_path, "diagnostics.json")

    def test_runtime_diagnostic_export_is_content_addressed(self) -> None:
        runtime = run_causal_alpha_frontier_runtime(self.fixture, run_id="alpha-diagnostic-export")
        envelope = runtime.exports.by_id("diagnostics")
        self.assertTrue(envelope.content_address.startswith("sha256:"))
        self.assertEqual(envelope.source_address, runtime.diagnostics.content_address)
        self.assertEqual(envelope.payload["accepted"], True)

    def test_diagnostic_output_contains_remediation_for_every_join(self) -> None:
        report = build_causal_alpha_frontier_diagnostics(self.fixture, self.evaluation, self.controls, self.traces, self.projections)
        self.assertTrue(all(item.remediation for item in report.findings))
        self.assertTrue(all(item.message for item in report.findings))
        self.assertTrue(all(item.expected is not None for item in report.findings))


if __name__ == "__main__":
    unittest.main()
