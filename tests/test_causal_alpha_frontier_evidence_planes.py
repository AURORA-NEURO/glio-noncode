from __future__ import annotations

import json
import unittest

from glio_noncode.causal_alpha_frontier_controls import (
    CausalAlphaFrontierControlClass,
    build_causal_alpha_frontier_control_coverage,
)
from glio_noncode.causal_alpha_frontier_fixture_eval import evaluate_causal_alpha_frontier_fixture_deep
from glio_noncode.causal_alpha_frontier_policy import default_causal_alpha_frontier_policy
from glio_noncode.causal_alpha_frontier_projections import build_causal_alpha_frontier_projections
from glio_noncode.causal_alpha_frontier_public_data import CausalAlphaFrontierOperation, default_causal_alpha_frontier_fixture
from glio_noncode.causal_alpha_frontier_review import build_causal_alpha_frontier_review_queue
from glio_noncode.causal_alpha_frontier_traces import build_causal_alpha_frontier_trace_ledger
from glio_noncode.causal_alpha_frontier_runtime import run_causal_alpha_frontier_runtime
from glio_noncode.serialization import jsonable


class CausalAlphaFrontierEvidencePlaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_causal_alpha_frontier_fixture()
        self.evaluation = evaluate_causal_alpha_frontier_fixture_deep(self.fixture)
        self.policy = default_causal_alpha_frontier_policy()
        self.decisions = self.policy.decide(self.evaluation)
        self.review = build_causal_alpha_frontier_review_queue(self.fixture, self.evaluation, self.decisions)

    def test_control_coverage_contains_all_required_classes(self) -> None:
        coverage = build_causal_alpha_frontier_control_coverage(self.fixture, self.evaluation, tuple(item.record_id for item in self.review.items))
        self.assertTrue(coverage.accepted)
        self.assertEqual(coverage.missing_classes, ())
        self.assertEqual(len(coverage.rows), 16)
        self.assertEqual(coverage.class_counts, {"contradictory": 2, "foreign_context": 4, "fragile": 1, "measured_negative": 1, "missing": 1, "positive": 4, "single_source": 2, "unresolved": 1})
        self.assertEqual(set(coverage.present_classes), set(CausalAlphaFrontierControlClass))

    def test_control_coverage_operation_facets_are_explicit(self) -> None:
        coverage = build_causal_alpha_frontier_control_coverage(self.fixture, self.evaluation, tuple(item.record_id for item in self.review.items))
        self.assertEqual(coverage.for_operation(CausalAlphaFrontierOperation.MEDIATION_SENSITIVITY)[0].control_class, CausalAlphaFrontierControlClass.POSITIVE)
        self.assertEqual(coverage.for_class("foreign_context")[0].record_id, "D11-C09-C3")
        self.assertEqual(coverage.for_class("contradictory"), tuple(item for item in coverage.rows if item.observed_state.value == "contradictory"))
        self.assertTrue(all(item.retained_in_review or item.control_class is CausalAlphaFrontierControlClass.POSITIVE for item in coverage.rows))

    def test_control_coverage_serializes_addresses_and_counts(self) -> None:
        coverage = build_causal_alpha_frontier_control_coverage(self.fixture, self.evaluation, tuple(item.record_id for item in self.review.items))
        payload = jsonable(coverage)
        self.assertEqual(payload["class_counts"]["foreign_context"], 4)
        self.assertEqual(len(payload["rows"]), 16)
        self.assertTrue(payload["content_address"].startswith("sha256:"))
        self.assertTrue(all(item["content_address"].startswith("sha256:") for item in payload["rows"]))

    def test_trace_ledger_has_three_ordered_steps_per_record(self) -> None:
        ledger = build_causal_alpha_frontier_trace_ledger(self.fixture, self.evaluation, self.decisions, self.review)
        self.assertTrue(ledger.accepted)
        self.assertEqual(len(ledger.traces), 16)
        for trace in ledger.traces:
            self.assertEqual(trace.step_ids, ("source-receipts", "operation-evaluation", "policy-disposition"))
            self.assertEqual(tuple(item.sequence for item in trace.steps), (1, 2, 3))
            self.assertTrue(trace.accepted)
            self.assertTrue(all(item.output_address.startswith("sha256:") for item in trace.steps))
        self.assertEqual(ledger.for_record("D11-C12-C2").final_disposition, "review")
        self.assertEqual(len(ledger.for_operation("negative_evidence")), 4)

    def test_trace_step_inputs_link_previous_outputs(self) -> None:
        ledger = build_causal_alpha_frontier_trace_ledger(self.fixture, self.evaluation, self.decisions, self.review)
        for trace in ledger.traces:
            self.assertEqual(trace.steps[1].input_addresses, (trace.steps[0].output_address,))
            self.assertEqual(trace.steps[2].input_addresses, (trace.steps[1].output_address,))
            self.assertEqual(trace.steps[0].sequence, 1)

    def test_trace_ledger_is_deterministic(self) -> None:
        first = build_causal_alpha_frontier_trace_ledger(self.fixture, self.evaluation, self.decisions, self.review)
        second = build_causal_alpha_frontier_trace_ledger(self.fixture, self.evaluation, self.decisions, self.review)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(tuple(item.content_address for item in first.traces), tuple(item.content_address for item in second.traces))
        self.assertEqual(first.to_dict(False), second.to_dict(False))

    def test_projections_cover_six_faceted_dimensions(self) -> None:
        coverage = build_causal_alpha_frontier_control_coverage(self.fixture, self.evaluation, tuple(item.record_id for item in self.review.items))
        projections = build_causal_alpha_frontier_projections(self.fixture, self.evaluation, coverage, self.decisions)
        self.assertTrue(projections.accepted)
        self.assertEqual(projections.dimensions, ("context", "control_class", "disposition", "operation", "role", "state"))
        self.assertEqual(projections.facet("operation", "mediation_sensitivity").count, 4)
        self.assertEqual(projections.facet("context", "foreign").record_ids, ("D11-C09-C3", "D11-C10-C3", "D11-C11-C3", "D11-C12-C3"))
        self.assertEqual(projections.facet("role", "positive").count, 4)
        self.assertEqual(projections.facet("disposition", "quarantine").count, 4)

    def test_projection_where_supports_dimension_and_value_filters(self) -> None:
        coverage = build_causal_alpha_frontier_control_coverage(self.fixture, self.evaluation, tuple(item.record_id for item in self.review.items))
        projections = build_causal_alpha_frontier_projections(self.fixture, self.evaluation, coverage, self.decisions)
        self.assertEqual(len(projections.where(dimension="operation")), 4)
        self.assertEqual(len(projections.where(value="foreign")), 1)
        self.assertEqual(len(projections.where(dimension="state", value="contradictory")), 1)
        self.assertTrue(all(item.accepted for item in projections.facets))

    def test_runtime_integrates_the_three_planes(self) -> None:
        runtime = run_causal_alpha_frontier_runtime(self.fixture, run_id="alpha-evidence-planes")
        self.assertTrue(runtime.accepted)
        self.assertEqual(runtime.stage_ids[14:17], ("control-coverage", "decision-traces", "projections"))
        self.assertTrue(runtime.controls.accepted)
        self.assertTrue(runtime.traces.accepted)
        self.assertTrue(runtime.projections.accepted)
        self.assertEqual(runtime.artifacts.for_kind("control_coverage")[0].relative_path, "control-coverage.json")
        self.assertEqual(runtime.artifacts.for_kind("decision_traces")[0].relative_path, "decision-traces.json")
        self.assertEqual(runtime.artifacts.for_kind("projections")[0].relative_path, "projections.json")

    def test_runtime_exports_include_the_three_planes(self) -> None:
        runtime = run_causal_alpha_frontier_runtime(self.fixture, run_id="alpha-evidence-exports")
        self.assertEqual({item.export_id for item in runtime.exports.envelopes} - {"fixture", "evaluation", "summary", "review-csv", "review-markdown", "release"}, {"controls", "traces", "projections", "diagnostics"})
        self.assertTrue(runtime.exports.by_id("controls").payload["accepted"])
        self.assertTrue(runtime.exports.by_id("traces").payload["accepted"])
        self.assertTrue(runtime.exports.by_id("projections").payload["accepted"])
        self.assertTrue(runtime.exports.by_id("diagnostics").payload["accepted"])
        self.assertGreater(len(json.dumps(jsonable(runtime.exports.to_dict()))), 20000)


if __name__ == "__main__":
    unittest.main()
