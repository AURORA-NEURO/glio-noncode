"""Focused tests for D13 C09-C12 planning frontier behavior."""

from __future__ import annotations

import json
import unittest

from glio_noncode.planning_frontier_adapters import build_planning_adapters, execute_planning_adapter
from glio_noncode.planning_frontier_contracts import PLANNING_FRONTIER_CONTEXT_KEY, PLANNING_FRONTIER_FOREIGN_CONTEXT, PlanningOperation, PlanningState
from glio_noncode.planning_frontier_data_dictionary import build_planning_data_dictionary
from glio_noncode.planning_frontier_depth import build_planning_depth_report
from glio_noncode.planning_frontier_failure_injection import build_planning_failure_report
from glio_noncode.planning_frontier_fixture_eval import evaluate_planning_fixture
from glio_noncode.planning_frontier_integrity import evaluate_planning_integrity
from glio_noncode.planning_frontier_metrics import measure_planning
from glio_noncode.planning_frontier_operations import (
    evaluate_controls_randomization,
    evaluate_guide_oligo_adaptation,
    evaluate_model_system_eligibility,
    evaluate_power_replication,
)
from glio_noncode.planning_frontier_policy import materialize_planning_policy
from glio_noncode.planning_frontier_provenance import build_planning_provenance
from glio_noncode.planning_frontier_public_data import audit_planning_frontier_data, default_planning_frontier_fixture
from glio_noncode.planning_frontier_quality_gate import build_planning_quality_gate
from glio_noncode.planning_frontier_reconciliation import reconcile_planning
from glio_noncode.planning_frontier_release import build_planning_release
from glio_noncode.planning_frontier_replay import replay_planning
from glio_noncode.planning_frontier_reports import build_planning_report
from glio_noncode.planning_frontier_review_queue import build_planning_review_queue
from glio_noncode.planning_frontier_runtime import run_planning_runtime
from glio_noncode.planning_frontier_schema import default_planning_schema, validate_planning_payload


class PlanningFrontierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_planning_frontier_fixture()
        self.evaluation = evaluate_planning_fixture(self.fixture)

    def test_public_boundary_is_balanced(self) -> None:
        audit = audit_planning_frontier_data(self.fixture)
        self.assertTrue(audit.accepted)
        self.assertEqual(len(self.fixture.sources), 5)
        self.assertEqual(len(self.fixture.records), 16)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)

    def test_fixture_has_five_checks_per_record(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.checks), 80)
        self.assertEqual(self.evaluation.failed_checks, 0)

    def test_eligibility_positive_and_foreign_context(self) -> None:
        positive = self.fixture.records[0].payload
        self.assertEqual(evaluate_model_system_eligibility(positive).state, PlanningState.READY_FOR_REVIEW)
        payload = dict(positive, context_key=PLANNING_FRONTIER_FOREIGN_CONTEXT)
        result = evaluate_model_system_eligibility(payload)
        self.assertEqual(result.state, PlanningState.BLOCKED)
        self.assertIn("context_mismatch", result.issue_codes)

    def test_guide_json_is_lossless_and_addressed(self) -> None:
        payload = self.fixture.records[4].payload
        result = evaluate_guide_oligo_adaptation(payload)
        self.assertEqual(result.state, PlanningState.READY_FOR_REVIEW)
        self.assertEqual(result.output["accepted_observation_count"], 1)
        self.assertTrue(result.output["observations"][0]["row_address"].startswith("guide-row:"))

    def test_guide_tsv_is_supported(self) -> None:
        result = evaluate_guide_oligo_adaptation({
            "source_id": "tsv-source",
            "source_version": "v1",
            "input_format": "tsv",
            "context_key": PLANNING_FRONTIER_CONTEXT_KEY,
            "text": "design_id\ttarget_id\tsequence\tcontext_key\nD1\tT1\tACGT\t" + PLANNING_FRONTIER_CONTEXT_KEY + "\n",
        })
        self.assertEqual(result.output["accepted_observation_count"], 1)

    def test_controls_are_seed_deterministic(self) -> None:
        payload = self.fixture.records[8].payload
        first = evaluate_controls_randomization(payload)
        second = evaluate_controls_randomization(payload)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.output["assignment_count"], 16)

    def test_power_exposes_transparent_replicate_requirement(self) -> None:
        result = evaluate_power_replication(self.fixture.records[12].payload)
        self.assertEqual(result.state, PlanningState.READY_FOR_REVIEW)
        estimate = result.output["results"][0]
        self.assertLessEqual(estimate["required_replicates"], estimate["planned_replicates"])
        self.assertIn("two-sided normal approximation", estimate["assumptions"])

    def test_adapters_and_schemas_are_closed(self) -> None:
        adapters = build_planning_adapters()
        schema = default_planning_schema()
        self.assertEqual(tuple(item.operation for item in adapters.adapters), tuple(PlanningOperation))
        self.assertEqual(tuple(item.operation for item in schema.schemas), tuple(PlanningOperation))
        check = validate_planning_payload(PlanningOperation.POWER_REPLICATION, {"observations": []})
        self.assertFalse(check["valid"])
        self.assertIn("request_id", check["missing_fields"])

    def test_runtime_has_ordered_stages_and_assurance(self) -> None:
        runtime = run_planning_runtime(self.fixture)
        self.assertTrue(runtime.accepted)
        self.assertEqual(runtime.stage_ids, tuple(dict.fromkeys(runtime.stage_ids)))
        self.assertGreaterEqual(len(runtime.stages), 28)
        self.assertGreaterEqual(len(runtime.assurance.planes), 60)

    def test_release_and_review_projection(self) -> None:
        queue = build_planning_review_queue(self.evaluation)
        policy = materialize_planning_policy(self.evaluation)
        gate = build_planning_quality_gate(audit=audit_planning_frontier_data(self.fixture), fixture=self.fixture, evaluation=self.evaluation, adapters=build_planning_adapters(), schema=default_planning_schema())
        release = build_planning_release(self.fixture, self.evaluation, gate)
        self.assertTrue(queue.accepted)
        self.assertEqual(queue.held_count, 12)
        self.assertEqual(policy.held_count, 12)
        self.assertTrue(release.ready)
        self.assertEqual(len(release.held_records), 12)

    def test_integrity_provenance_replay_and_depth(self) -> None:
        provenance = build_planning_provenance(self.fixture, self.evaluation)
        integrity = evaluate_planning_integrity(self.fixture, self.evaluation)
        replay = replay_planning(self.fixture)
        depth = build_planning_depth_report(self.fixture, self.evaluation, measure_planning(self.evaluation), build_planning_quality_gate(audit=audit_planning_frontier_data(self.fixture), fixture=self.fixture, evaluation=self.evaluation, adapters=build_planning_adapters(), schema=default_planning_schema()))
        self.assertTrue(provenance.closed)
        self.assertTrue(integrity.accepted)
        self.assertTrue(replay.identical)
        self.assertTrue(depth.accepted)

    def test_failure_injection_is_accepted(self) -> None:
        report = build_planning_failure_report()
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.cases), 4)

    def test_report_dictionary_and_jsonability(self) -> None:
        report = build_planning_report(fixture=self.fixture, evaluation=self.evaluation)
        dictionary = build_planning_data_dictionary()
        self.assertTrue(report.accepted)
        self.assertGreaterEqual(len(dictionary.fields), 20)
        self.assertIn("D13 C09-C12", report.markdown())
        json.dumps(report.to_dict())


if __name__ == "__main__":
    unittest.main()
