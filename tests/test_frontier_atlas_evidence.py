from __future__ import annotations

import unittest

from glio_noncode.frontier_atlas_exports import (
    export_frontier_atlas_metrics_csv,
    export_frontier_atlas_receipts_csv,
    export_frontier_atlas_review_csv,
    frontier_atlas_export_receipt,
    render_frontier_atlas_release_markdown,
    render_frontier_atlas_review_markdown,
)
from glio_noncode.frontier_atlas_fixture_eval import evaluate_frontier_atlas_fixture
from glio_noncode.frontier_atlas_lineage import (
    build_frontier_atlas_lineage,
    verify_frontier_atlas_lineage,
)
from glio_noncode.frontier_atlas_metrics import compute_frontier_atlas_metrics
from glio_noncode.frontier_atlas_observability import (
    build_frontier_atlas_trace,
    compare_frontier_atlas_runs,
    frontier_atlas_review_budget,
)
from glio_noncode.frontier_atlas_policy import evaluate_frontier_atlas_policy
from glio_noncode.frontier_atlas_public_data import (
    FRONTIER_ATLAS_CONTEXT_KEY,
    FrontierAtlasOperation,
    audit_frontier_atlas_data,
    build_frontier_atlas_catalog,
    default_frontier_atlas_fixture,
)
from glio_noncode.frontier_atlas_quality_gate import run_frontier_atlas_quality_gate
from glio_noncode.frontier_atlas_reconciliation import reconcile_frontier_atlas
from glio_noncode.frontier_atlas_release import build_frontier_atlas_release
from glio_noncode.frontier_atlas_replay import replay_frontier_atlas_evaluation
from glio_noncode.frontier_atlas_runtime import (
    FrontierAtlasRuntimeOptions,
    run_frontier_atlas_pipeline,
)
from glio_noncode.frontier_atlas_scenario_matrix import evaluate_frontier_atlas_scenarios
from glio_noncode.frontier_atlas_schema import (
    frontier_atlas_schema_manifest,
    validate_frontier_atlas_schema,
)
from glio_noncode.frontier_atlas_views import (
    build_frontier_atlas_view,
    filter_frontier_atlas_review_queue,
    frontier_atlas_review_summary,
)


class FrontierAtlasEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_frontier_atlas_fixture()
        self.evaluation = evaluate_frontier_atlas_fixture(self.fixture)
        self.view = build_frontier_atlas_view(self.fixture, self.evaluation)

    def test_fixture_balance_catalog_and_data_audit(self) -> None:
        self.assertEqual(self.fixture.context_key, FRONTIER_ATLAS_CONTEXT_KEY)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)
        self.assertTrue(audit_frontier_atlas_data(self.fixture).accepted)
        catalog = build_frontier_atlas_catalog(self.fixture)
        self.assertEqual(set(catalog.operations), set(FrontierAtlasOperation))
        self.assertEqual(len(catalog.record_ids), 16)

    def test_evaluation_has_120_checks_and_explicit_states(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.checks), 120)
        self.assertEqual(self.evaluation.positive_count, 4)
        self.assertEqual(self.evaluation.control_count, 12)
        self.assertEqual(
            tuple((item.record_id, item.adapter_state) for item in self.evaluation.receipts),
            (
                ("C13-POS-001", "accepted"),
                ("C13-CTRL-001", "review"),
                ("C13-CTRL-002", "review"),
                ("C13-CTRL-003", "out_of_domain"),
                ("C14-POS-001", "accepted"),
                ("C14-CTRL-001", "review"),
                ("C14-CTRL-002", "review"),
                ("C14-CTRL-003", "out_of_domain"),
                ("C15-POS-001", "accepted"),
                ("C15-CTRL-001", "review"),
                ("C15-CTRL-002", "review"),
                ("C15-CTRL-003", "out_of_domain"),
                ("C16-POS-001", "published"),
                ("C16-CTRL-001", "abstained"),
                ("C16-CTRL-002", "out_of_domain"),
                ("C16-CTRL-003", "invalid"),
            ),
        )

    def test_replay_scenarios_policy_lineage_and_reconciliation(self) -> None:
        self.assertTrue(
            replay_frontier_atlas_evaluation(self.evaluation, fixture=self.fixture).accepted
        )
        self.assertTrue(evaluate_frontier_atlas_scenarios(self.evaluation).accepted)
        self.assertTrue(evaluate_frontier_atlas_policy(self.fixture, self.evaluation).accepted)
        lineage = build_frontier_atlas_lineage(self.fixture, self.evaluation)
        self.assertFalse(verify_frontier_atlas_lineage(lineage, self.fixture, self.evaluation))
        self.assertTrue(reconcile_frontier_atlas(self.fixture, self.evaluation).accepted)

    def test_quality_metrics_runtime_and_release(self) -> None:
        quality = run_frontier_atlas_quality_gate(self.fixture)
        self.assertTrue(quality.accepted)
        self.assertTrue(any(item.check_id == "schema" and item.passed for item in quality.checks))
        metrics = compute_frontier_atlas_metrics(self.evaluation)
        self.assertEqual(metrics.total_records, 16)
        self.assertEqual(metrics.accepted_records, 3)
        self.assertEqual(metrics.published_records, 1)
        self.assertEqual(metrics.review_records, 12)
        runtime = run_frontier_atlas_pipeline(
            FrontierAtlasRuntimeOptions(run_id="frontier-test"), fixture=self.fixture
        )
        self.assertTrue(runtime.accepted)
        release = build_frontier_atlas_release(quality, runtime)
        self.assertTrue(release.accepted)
        self.assertEqual(
            set(release.operation_ids), {operation.value for operation in FrontierAtlasOperation}
        )

    def test_strict_runtime_rejects_visible_review_records(self) -> None:
        runtime = run_frontier_atlas_pipeline(
            FrontierAtlasRuntimeOptions(run_id="frontier-strict", fail_on_review=True),
            fixture=self.fixture,
        )
        self.assertFalse(runtime.accepted)
        self.assertEqual(runtime.status, "rejected")

    def test_schema_views_and_review_budget(self) -> None:
        schema = validate_frontier_atlas_schema(self.fixture, self.evaluation)
        self.assertTrue(schema.accepted)
        self.assertEqual(len(schema.schemas), 4)
        self.assertEqual(len(schema.checks), 23)
        self.assertEqual(len(frontier_atlas_schema_manifest()["schemas"]), 4)
        self.assertTrue(self.view.accepted)
        self.assertEqual(self.view.review_count, 12)
        self.assertEqual(len(self.view.accepted_record_ids), 3)
        self.assertEqual(len(self.view.published_record_ids), 1)
        self.assertEqual(len(self.view.source_matrix), 5)
        self.assertEqual(
            len(filter_frontier_atlas_review_queue(self.view, states=("out_of_domain",))), 4
        )
        self.assertEqual(frontier_atlas_review_summary(self.view)["review_count"], 12)
        self.assertEqual(
            frontier_atlas_review_budget(self.view, maximum_priority=2)["eligible_review_count"], 7
        )

    def test_trace_exports_and_release_markdown_are_sanitized(self) -> None:
        runtime = run_frontier_atlas_pipeline(
            FrontierAtlasRuntimeOptions(run_id="frontier-trace"), fixture=self.fixture
        )
        trace = build_frontier_atlas_trace(runtime, self.view)
        self.assertTrue(trace.accepted)
        self.assertEqual(len(trace.stage_receipts), 9)
        self.assertEqual(len(trace.events), 9)
        self.assertEqual(trace.stage_names[0], "data_audit")
        self.assertEqual(trace.stage_names[-1], "bundle")
        left = run_frontier_atlas_pipeline(
            FrontierAtlasRuntimeOptions(run_id="frontier-left"), fixture=self.fixture
        )
        right = run_frontier_atlas_pipeline(
            FrontierAtlasRuntimeOptions(run_id="frontier-right"), fixture=self.fixture
        )
        self.assertTrue(compare_frontier_atlas_runs(left, right).equivalent)
        receipts = export_frontier_atlas_receipts_csv(self.evaluation)
        review = export_frontier_atlas_review_csv(self.view)
        metrics = export_frontier_atlas_metrics_csv(compute_frontier_atlas_metrics(self.evaluation))
        markdown = render_frontier_atlas_review_markdown(self.view)
        release = build_frontier_atlas_release(runtime.quality, runtime)
        release_markdown = render_frontier_atlas_release_markdown(release)
        self.assertEqual(receipts.count("\n"), 17)
        self.assertEqual(review.count("\n"), 13)
        self.assertEqual(metrics.count("\n"), 5)
        self.assertIn("C13-CTRL-003", markdown)
        self.assertIn("encode-hic", release_markdown)
        self.assertNotIn("input_text", receipts)
        self.assertNotIn("input_text", str(trace.to_dict()))
        export_receipt = frontier_atlas_export_receipt("review.csv", review)
        self.assertTrue(export_receipt["content_address"].startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()
