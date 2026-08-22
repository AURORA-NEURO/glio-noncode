from __future__ import annotations

import unittest

from glio_noncode.link_frontier_bundle import build_link_frontier_bundle
from glio_noncode.link_frontier_contracts import default_link_frontier_contracts
from glio_noncode.link_frontier_exports import (
    export_link_frontier_json,
    export_link_frontier_metrics_csv,
    export_link_frontier_receipts_csv,
    export_link_frontier_review_csv,
    link_frontier_export_receipt,
    render_link_frontier_release_markdown,
    render_link_frontier_review_markdown,
)
from glio_noncode.link_frontier_fixture_eval import evaluate_link_frontier_fixture
from glio_noncode.link_frontier_lineage import (
    build_link_frontier_lineage,
    verify_link_frontier_lineage,
)
from glio_noncode.link_frontier_metrics import (
    compute_link_frontier_metrics,
    link_frontier_metric_checks,
)
from glio_noncode.link_frontier_observability import (
    build_link_frontier_trace,
    compare_link_frontier_runs,
)
from glio_noncode.link_frontier_policy import (
    default_link_frontier_policy_rules,
    evaluate_link_frontier_policy,
)
from glio_noncode.link_frontier_public_data import (
    LINK_FRONTIER_CONTEXT_KEY,
    LINK_FRONTIER_EVIDENCE_BOUNDARY,
    LinkFrontierOperation,
    audit_link_frontier_data,
    build_link_frontier_catalog,
    default_link_frontier_fixture,
)
from glio_noncode.link_frontier_quality_gate import run_link_frontier_quality_gate
from glio_noncode.link_frontier_reconciliation import reconcile_link_frontier
from glio_noncode.link_frontier_release import build_link_frontier_release
from glio_noncode.link_frontier_replay import replay_link_frontier_evaluation
from glio_noncode.link_frontier_runtime import run_link_frontier_pipeline
from glio_noncode.link_frontier_scenario_matrix import evaluate_link_frontier_scenarios
from glio_noncode.link_frontier_schema import validate_link_frontier_schema
from glio_noncode.link_frontier_views import (
    build_link_frontier_view,
    filter_link_frontier_review_queue,
    link_frontier_review_summary,
)


class LinkFrontierEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_link_frontier_fixture()
        self.evaluation = evaluate_link_frontier_fixture(self.fixture)

    def test_public_boundary_and_catalog_are_closed(self) -> None:
        self.assertEqual(self.fixture.context_key, LINK_FRONTIER_CONTEXT_KEY)
        self.assertEqual(self.fixture.evidence_boundary, LINK_FRONTIER_EVIDENCE_BOUNDARY)
        self.assertEqual(len(self.fixture.sources), 5)
        self.assertEqual(len(self.fixture.records), 16)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)
        catalog = build_link_frontier_catalog(self.fixture)
        self.assertEqual(set(catalog.operations), set(LinkFrontierOperation))
        self.assertEqual(len(catalog.record_ids), 16)
        self.assertEqual(len(catalog.source_ids), 5)
        self.assertTrue(catalog.content_address)
        audit = audit_link_frontier_data(self.fixture)
        self.assertTrue(audit.accepted)
        self.assertEqual(len(audit.checks), 12)
        self.assertEqual(audit.failed_check_ids, ())

    def test_evaluation_has_fixed_positive_control_and_check_counts(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.executions), 16)
        self.assertEqual(len(self.evaluation.checks), 120)
        self.assertEqual(self.evaluation.passed_checks, 120)
        self.assertEqual(self.evaluation.failed_check_ids, ())
        self.assertEqual(len(self.evaluation.positive_record_ids), 4)
        self.assertEqual(len(self.evaluation.control_record_ids), 12)

    def test_each_operation_has_one_positive_and_three_controls(self) -> None:
        for operation in LinkFrontierOperation:
            records = tuple(item for item in self.fixture.records if item.operation is operation)
            self.assertEqual(len(records), 4, operation)
            self.assertEqual(sum(item.role.value == "positive" for item in records), 1)
            self.assertEqual(sum(item.role.value == "control" for item in records), 3)
            positive = next(item for item in records if item.role.value == "positive")
            execution = self.evaluation.execution_map()[positive.record_id]
            self.assertTrue(execution.accepted, operation)

    def test_controls_retain_explicit_failure_vocabulary(self) -> None:
        executions = self.evaluation.execution_map()
        self.assertEqual(executions["C13-CTRL-001"].issue_codes, ("zero_corrected_support",))
        self.assertEqual(executions["C13-CTRL-002"].issue_codes, ("empty_dependence_input",))
        self.assertEqual(executions["C14-CTRL-001"].issue_codes, ("zero_rank_support",))
        self.assertEqual(executions["C14-CTRL-002"].issue_codes, ("invalid_rank_input",))
        self.assertEqual(executions["C15-CTRL-001"].issue_codes, ("link_uncertainty_high",))
        self.assertEqual(executions["C15-CTRL-002"].issue_codes, ("link_calibration_error_high",))
        self.assertEqual(executions["C16-CTRL-001"].issue_codes, ("publication_context_mismatch",))
        self.assertEqual(executions["C16-CTRL-002"].issue_codes, ("invalid_publication_input",))
        self.assertGreaterEqual(sum(execution.state == "invalid" for execution in executions.values()), 6)
        self.assertTrue(all(execution.issue_codes for execution in executions.values() if execution.state == "invalid"))

    def test_replay_is_deterministic_at_record_and_report_levels(self) -> None:
        replay = replay_link_frontier_evaluation(self.fixture, first=self.evaluation)
        self.assertTrue(replay.deterministic)
        self.assertEqual(len(replay.records), 16)
        self.assertTrue(all(item.deterministic for item in replay.records))
        self.assertEqual(replay.first_evaluation_address, self.evaluation.content_address)

    def test_scenarios_cover_baseline_and_three_adversarial_changes(self) -> None:
        matrix = evaluate_link_frontier_scenarios(self.fixture)
        self.assertTrue(matrix.all_expectations_met)
        self.assertEqual(len(matrix.scenarios), 4)
        self.assertTrue(matrix.scenarios[0].accepted)
        self.assertFalse(matrix.scenarios[1].accepted)
        self.assertFalse(matrix.scenarios[2].accepted)
        self.assertFalse(matrix.scenarios[3].accepted)

    def test_policy_contract_and_schema_reports_are_complete(self) -> None:
        contracts = default_link_frontier_contracts()
        self.assertEqual(len(contracts.contracts), 4)
        self.assertEqual(set(item.operation for item in contracts.contracts), set(LinkFrontierOperation))
        self.assertTrue(all(item.prohibited_claims for item in contracts.contracts))
        rules = default_link_frontier_policy_rules()
        self.assertEqual(len(rules), 12)
        policy = evaluate_link_frontier_policy(self.fixture, evaluation=self.evaluation, contracts=contracts)
        self.assertTrue(policy.accepted)
        self.assertEqual(len(policy.results), 12)
        schema = validate_link_frontier_schema(self.fixture, contracts=contracts)
        self.assertTrue(schema.accepted)
        self.assertEqual(len(schema.schemas), 4)
        self.assertEqual(len(schema.checks), 20)

    def test_lineage_reconciliation_metrics_and_quality_gate(self) -> None:
        lineage = build_link_frontier_lineage(self.fixture, self.evaluation)
        self.assertTrue(lineage.valid)
        self.assertEqual(verify_link_frontier_lineage(lineage), ())
        self.assertEqual(len(lineage.nodes), 1 + 5 + 16 + 16)
        self.assertEqual(len(lineage.roots), 1)
        reconciliation = reconcile_link_frontier(self.fixture, self.evaluation)
        self.assertTrue(reconciliation.accepted)
        self.assertEqual(reconciliation.state_match_count, 16)
        self.assertEqual(reconciliation.issue_match_count, 16)
        metrics = compute_link_frontier_metrics(self.fixture, self.evaluation)
        self.assertEqual(metrics.record_count, 16)
        self.assertEqual(metrics.positive_count, 4)
        self.assertEqual(metrics.control_count, 12)
        self.assertEqual(metrics.operation_counts, {operation.value: 4 for operation in LinkFrontierOperation})
        self.assertEqual(metrics.positive_acceptance_rate, 1.0)
        self.assertEqual(metrics.control_rejection_rate, 1.0)
        self.assertTrue(all(passed for _key, passed, _observed in link_frontier_metric_checks(metrics)))
        quality = run_link_frontier_quality_gate(self.fixture, evaluation=self.evaluation)
        self.assertTrue(quality.accepted)
        self.assertEqual(len(quality.checks), 12)
        self.assertEqual(quality.failed_check_ids, ())

    def test_runtime_release_bundle_and_observability(self) -> None:
        pipeline = run_link_frontier_pipeline(self.fixture)
        self.assertTrue(pipeline.accepted)
        self.assertEqual(len(pipeline.stages), 9)
        self.assertEqual(pipeline.stages[0].stage_id, "load")
        self.assertEqual(pipeline.stages[-1].stage_id, "complete")
        release = build_link_frontier_release(self.fixture, pipeline=pipeline, release_id="d10-test")
        self.assertEqual(release.state, "released")
        self.assertEqual(release.record_count, 16)
        self.assertEqual(release.source_count, 5)
        self.assertEqual(len(release.limitations), 4)
        bundle = build_link_frontier_bundle(
            self.fixture,
            self.evaluation,
            reconcile_link_frontier(self.fixture, self.evaluation),
            build_link_frontier_lineage(self.fixture, self.evaluation),
            compute_link_frontier_metrics(self.fixture, self.evaluation),
            evaluate_link_frontier_policy(self.fixture, evaluation=self.evaluation),
            bundle_id="d10-bundle",
        )
        self.assertTrue(bundle.accepted)
        self.assertEqual(len(bundle.record_ids), 16)
        trace_a = build_link_frontier_trace(pipeline, run_id="a")
        trace_b = build_link_frontier_trace(pipeline, run_id="b")
        self.assertEqual(len(trace_a.events), 9)
        comparison = compare_link_frontier_runs(trace_a, trace_b)
        self.assertTrue(comparison.equivalent)

    def test_views_keep_controls_and_source_rows_separate(self) -> None:
        view = build_link_frontier_view(self.fixture, self.evaluation)
        self.assertEqual(view.review_count, 12)
        self.assertEqual(view.source_count, 5)
        self.assertEqual(len(view.sources), 5)
        self.assertEqual(len(filter_link_frontier_review_queue(view, minimum_priority=3)), 8)
        summary = link_frontier_review_summary(view)
        self.assertEqual(summary["review_count"], 12)
        self.assertEqual(set(summary["operation_counts"]), {operation.value for operation in LinkFrontierOperation})

    def test_exports_are_sanitized_and_addressed(self) -> None:
        view = build_link_frontier_view(self.fixture, self.evaluation)
        metrics = compute_link_frontier_metrics(self.fixture, self.evaluation)
        release = build_link_frontier_release(self.fixture)
        json_text = export_link_frontier_json(self.evaluation)
        receipts = export_link_frontier_receipts_csv(self.evaluation)
        review = export_link_frontier_review_csv(view)
        metric_csv = export_link_frontier_metrics_csv(metrics)
        review_md = render_link_frontier_review_markdown(view)
        release_md = render_link_frontier_release_markdown(release)
        self.assertIn('"accepted": true', json_text)
        self.assertIn("record_id,operation", receipts)
        self.assertIn("record_id,operation", review)
        self.assertIn("fixture_id,record_count", metric_csv)
        self.assertIn("# Link frontier review", review_md)
        self.assertIn("# Link frontier release", release_md)
        receipt = link_frontier_export_receipt("evaluation.json", json_text)
        self.assertEqual(receipt["byte_count"], len(json_text.encode("utf-8")))
        self.assertTrue(receipt["content_address"])


if __name__ == "__main__":
    unittest.main()
