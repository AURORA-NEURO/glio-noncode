from __future__ import annotations

import unittest
from dataclasses import replace

from glio_noncode.chromatin_frontier_exports import (
    export_chromatin_frontier_metrics_csv,
    export_chromatin_frontier_receipts_csv,
    export_chromatin_frontier_review_csv,
    render_chromatin_frontier_release_markdown,
    render_chromatin_frontier_review_markdown,
)
from glio_noncode.chromatin_frontier_fixture_eval import evaluate_chromatin_frontier_fixture
from glio_noncode.chromatin_frontier_lineage import (
    build_chromatin_frontier_lineage,
    verify_chromatin_frontier_lineage,
)
from glio_noncode.chromatin_frontier_metrics import compute_chromatin_frontier_metrics
from glio_noncode.chromatin_frontier_observability import (
    build_chromatin_frontier_trace,
    chromatin_frontier_review_budget,
    compare_chromatin_frontier_runs,
)
from glio_noncode.chromatin_frontier_policy import evaluate_chromatin_frontier_policy
from glio_noncode.chromatin_frontier_public_data import (
    CHROMATIN_FRONTIER_CONTEXT_KEY,
    CHROMATIN_FRONTIER_EVIDENCE_BOUNDARY,
    ChromatinFrontierOperation,
    ChromatinFrontierRole,
    ChromatinFrontierSourceReceipt,
    audit_chromatin_frontier_data,
    build_chromatin_frontier_catalog,
    default_chromatin_frontier_fixture,
)
from glio_noncode.chromatin_frontier_quality_gate import run_chromatin_frontier_quality_gate
from glio_noncode.chromatin_frontier_reconciliation import reconcile_chromatin_frontier
from glio_noncode.chromatin_frontier_release import build_chromatin_frontier_release
from glio_noncode.chromatin_frontier_replay import replay_chromatin_frontier_evaluation
from glio_noncode.chromatin_frontier_runtime import (
    ChromatinFrontierRuntimeOptions,
    run_chromatin_frontier_pipeline,
)
from glio_noncode.chromatin_frontier_scenario_matrix import evaluate_chromatin_frontier_scenarios
from glio_noncode.chromatin_frontier_schema import (
    chromatin_frontier_schema_manifest,
    validate_chromatin_frontier_schema,
)
from glio_noncode.chromatin_frontier_views import (
    build_chromatin_frontier_view,
    chromatin_frontier_review_summary,
    filter_chromatin_frontier_review_queue,
)
from glio_noncode.errors import ValidationError


class ChromatinFrontierEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_chromatin_frontier_fixture()
        self.evaluation = evaluate_chromatin_frontier_fixture(self.fixture)
        self.view = build_chromatin_frontier_view(self.fixture, self.evaluation)

    def test_fixture_balance_catalog_and_data_audit(self) -> None:
        self.assertEqual(self.fixture.context_key, CHROMATIN_FRONTIER_CONTEXT_KEY)
        self.assertEqual(self.fixture.evidence_boundary, CHROMATIN_FRONTIER_EVIDENCE_BOUNDARY)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)
        self.assertTrue(audit_chromatin_frontier_data(self.fixture).accepted)
        catalog = build_chromatin_frontier_catalog(self.fixture)
        self.assertEqual(set(catalog.operations), set(ChromatinFrontierOperation))
        self.assertEqual(len(catalog.record_ids), 16)
        self.assertEqual(len(catalog.source_ids), 5)

    def test_evaluation_has_120_checks_and_explicit_states(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.checks), 120)
        self.assertEqual((self.evaluation.positive_count, self.evaluation.control_count), (4, 12))
        self.assertEqual(
            tuple((item.record_id, item.adapter_state) for item in self.evaluation.receipts),
            (
                ("C13-POS-001", "supported"),
                ("C13-CTRL-001", "ambiguous"),
                ("C13-CTRL-002", "out_of_domain"),
                ("C13-CTRL-003", "partial"),
                ("C14-POS-001", "supported"),
                ("C14-CTRL-001", "ambiguous"),
                ("C14-CTRL-002", "out_of_domain"),
                ("C14-CTRL-003", "partial"),
                ("C15-POS-001", "supported"),
                ("C15-CTRL-001", "partial"),
                ("C15-CTRL-002", "out_of_domain"),
                ("C15-CTRL-003", "partial"),
                ("C16-POS-001", "supported"),
                ("C16-CTRL-001", "partial"),
                ("C16-CTRL-002", "out_of_domain"),
                ("C16-CTRL-003", "partial"),
            ),
        )

    def test_replay_scenarios_policy_lineage_and_reconciliation(self) -> None:
        self.assertTrue(
            replay_chromatin_frontier_evaluation(self.evaluation, fixture=self.fixture).accepted
        )
        self.assertTrue(evaluate_chromatin_frontier_scenarios(self.evaluation).accepted)
        self.assertTrue(evaluate_chromatin_frontier_policy(self.fixture, self.evaluation).accepted)
        lineage = build_chromatin_frontier_lineage(self.fixture, self.evaluation)
        self.assertFalse(verify_chromatin_frontier_lineage(lineage, self.fixture, self.evaluation))
        self.assertEqual(len(lineage.edges), 16)
        self.assertTrue(reconcile_chromatin_frontier(self.fixture, self.evaluation).accepted)

    def test_quality_metrics_runtime_and_release(self) -> None:
        quality = run_chromatin_frontier_quality_gate(self.fixture)
        self.assertTrue(quality.accepted)
        self.assertEqual(len(quality.checks), 12)
        metrics = compute_chromatin_frontier_metrics(self.evaluation)
        self.assertEqual(
            (
                metrics.total_records,
                metrics.supported_records,
                metrics.review_records,
                metrics.issue_count,
            ),
            (16, 4, 12, 7),
        )
        runtime = run_chromatin_frontier_pipeline(
            ChromatinFrontierRuntimeOptions(run_id="chromatin-frontier-test"),
            fixture=self.fixture,
        )
        self.assertTrue(runtime.accepted)
        release = build_chromatin_frontier_release(quality, runtime)
        self.assertTrue(release.accepted)
        self.assertEqual(
            set(release.operation_ids),
            {operation.value for operation in ChromatinFrontierOperation},
        )
        self.assertEqual(len(release.source_ids), 5)

    def test_strict_runtime_rejects_visible_review_records(self) -> None:
        runtime = run_chromatin_frontier_pipeline(
            ChromatinFrontierRuntimeOptions(
                run_id="chromatin-frontier-strict",
                fail_on_review=True,
            ),
            fixture=self.fixture,
        )
        self.assertFalse(runtime.accepted)
        self.assertEqual(runtime.status, "rejected")

    def test_schema_views_and_review_budget(self) -> None:
        schema = validate_chromatin_frontier_schema(self.fixture, self.evaluation)
        self.assertTrue(schema.accepted)
        self.assertEqual((len(schema.schemas), len(schema.checks)), (4, 23))
        self.assertEqual(len(chromatin_frontier_schema_manifest()["schemas"]), 4)
        self.assertTrue(self.view.accepted)
        self.assertEqual(
            (self.view.review_count, len(self.view.accepted_record_ids)),
            (12, 4),
        )
        self.assertEqual(len(self.view.source_matrix), 5)
        self.assertEqual(
            len(filter_chromatin_frontier_review_queue(self.view, states=("out_of_domain",))),
            4,
        )
        self.assertEqual(chromatin_frontier_review_summary(self.view)["review_count"], 12)
        self.assertEqual(
            chromatin_frontier_review_budget(self.view, maximum_priority=2)[
                "eligible_review_count"
            ],
            6,
        )

    def test_trace_exports_and_release_markdown_are_sanitized(self) -> None:
        runtime = run_chromatin_frontier_pipeline(
            ChromatinFrontierRuntimeOptions(run_id="chromatin-frontier-trace"),
            fixture=self.fixture,
        )
        trace = build_chromatin_frontier_trace(runtime)
        self.assertTrue(trace.accepted)
        self.assertEqual((len(trace.stage_receipts), len(trace.events)), (9, 9))
        left = run_chromatin_frontier_pipeline(
            ChromatinFrontierRuntimeOptions(run_id="chromatin-frontier-left"),
            fixture=self.fixture,
        )
        right = run_chromatin_frontier_pipeline(
            ChromatinFrontierRuntimeOptions(run_id="chromatin-frontier-right"),
            fixture=self.fixture,
        )
        self.assertTrue(compare_chromatin_frontier_runs(left, right).equivalent)
        receipts = export_chromatin_frontier_receipts_csv(self.evaluation)
        review = export_chromatin_frontier_review_csv(self.view)
        metrics = export_chromatin_frontier_metrics_csv(
            compute_chromatin_frontier_metrics(self.evaluation)
        )
        markdown = render_chromatin_frontier_review_markdown(self.view)
        release_markdown = render_chromatin_frontier_release_markdown(
            build_chromatin_frontier_release(runtime.quality, runtime)
        )
        self.assertEqual(
            (receipts.count("\n"), review.count("\n"), metrics.count("\n")),
            (17, 13, 5),
        )
        self.assertIn("C13-CTRL-002", markdown)
        self.assertIn("encode-atac", release_markdown)
        self.assertNotIn("input_text", receipts)
        self.assertNotIn("input_text", str(trace.to_dict()))

    def test_data_audit_rejects_context_subject_and_missing_source(self) -> None:
        context_fixture = replace(
            self.fixture,
            context_key="GRCh38|glioma|pediatric|stem_like|tumor|unknown",
        )
        context_audit = audit_chromatin_frontier_data(context_fixture)
        self.assertFalse(context_audit.accepted)
        self.assertIn("fixture-context", context_audit.failed_check_ids)

        subject_record = replace(
            self.fixture.records[0],
            payload=self.fixture.records[0].payload | {"subject": "not-permitted"},
        )
        subject_fixture = replace(self.fixture, records=(subject_record, *self.fixture.records[1:]))
        subject_audit = audit_chromatin_frontier_data(subject_fixture)
        self.assertFalse(subject_audit.accepted)
        self.assertIn("no-subject-identifiers", subject_audit.failed_check_ids)

        missing_source_record = replace(
            self.fixture.records[0],
            source_ids=("missing-source",),
        )
        missing_source_fixture = replace(
            self.fixture,
            records=(missing_source_record, *self.fixture.records[1:]),
        )
        missing_source_audit = audit_chromatin_frontier_data(missing_source_fixture)
        self.assertFalse(missing_source_audit.accepted)
        self.assertIn("source-closure", missing_source_audit.failed_check_ids)

    def test_fixture_constructor_rejects_bad_boundary_and_source_uri(self) -> None:
        with self.assertRaises(ValidationError):
            replace(self.fixture, evidence_boundary="private_subject")
        with self.assertRaises(ValidationError):
            replace(self.fixture.sources[0], uri="http://insecure.example")
        with self.assertRaises(ValidationError):
            ChromatinFrontierSourceReceipt(
                source_id="",
                title="title",
                uri="https://example.org/source",
                source_kind="public",
                release="2026",
                scope="aggregate",
                content_address="sha256:source",
            )

    def test_evaluation_and_quality_surface_fixture_drift(self) -> None:
        wrong_state_record = replace(self.fixture.records[0], expected_state="partial")
        wrong_state_fixture = replace(
            self.fixture,
            records=(wrong_state_record, *self.fixture.records[1:]),
        )
        evaluation = evaluate_chromatin_frontier_fixture(wrong_state_fixture)
        self.assertFalse(evaluation.accepted)
        self.assertIn("C13-POS-001:expected-state", evaluation.failed_check_ids)
        quality = run_chromatin_frontier_quality_gate(wrong_state_fixture)
        self.assertFalse(quality.accepted)
        self.assertIn("evaluation", quality.failed_check_ids)

        replay = replay_chromatin_frontier_evaluation(evaluation, fixture=self.fixture)
        self.assertFalse(replay.accepted)
        self.assertIn("fixture-address", replay.failed_check_ids)

    def test_runtime_context_and_source_mode_boundaries(self) -> None:
        mismatched_context = run_chromatin_frontier_pipeline(
            ChromatinFrontierRuntimeOptions(
                run_id="chromatin-frontier-context-mismatch",
                requested_context_key="GRCh38|glioma|adult|differentiated|tumor|unknown",
            ),
            fixture=self.fixture,
        )
        self.assertFalse(mismatched_context.accepted)
        self.assertEqual(mismatched_context.status, "rejected")
        with self.assertRaises(ValueError):
            ChromatinFrontierRuntimeOptions(
                run_id="chromatin-frontier-network",
                source_mode="network-source",
            )
        with self.assertRaises(ValidationError):
            ChromatinFrontierRuntimeOptions(run_id="")

    def test_operation_metrics_are_complete_and_addressed(self) -> None:
        metrics = compute_chromatin_frontier_metrics(self.evaluation)
        by_operation = {item.operation.value: item for item in metrics.operation_metrics}
        self.assertEqual(
            set(by_operation), {operation.value for operation in ChromatinFrontierOperation}
        )
        for operation in ChromatinFrontierOperation:
            metric = by_operation[operation.value]
            self.assertEqual(metric.record_count, 4)
            self.assertEqual(metric.positive_count, 1)
            self.assertEqual(metric.control_count, 3)
            self.assertTrue(metric.content_address.startswith("sha256:"))
        self.assertEqual(metrics.check_count, 120)
        self.assertEqual(metrics.passed_check_count, 120)
        self.assertEqual(metrics.check_pass_rate, 1.0)

    def test_source_matrix_and_review_actions_are_explicit(self) -> None:
        self.assertEqual(
            {row.source_id for row in self.view.source_matrix},
            {source.source_id for source in self.fixture.sources},
        )
        self.assertTrue(all(item.action and item.priority >= 1 for item in self.view.review_queue))
        self.assertEqual(
            len(filter_chromatin_frontier_review_queue(self.view, maximum_priority=1)),
            0,
        )
        self.assertEqual(
            len(filter_chromatin_frontier_review_queue(self.view, maximum_priority=4)),
            12,
        )

    def test_summaries_have_operation_specific_outputs(self) -> None:
        summaries = {item.record_id: item.summary for item in self.evaluation.receipts}
        self.assertIn("segment_count", summaries["C13-POS-001"])
        self.assertIn("directions", summaries["C14-POS-001"])
        self.assertIn("aggregate_purity", summaries["C15-POS-001"])
        self.assertIn("corrected_signals", summaries["C16-POS-001"])
        self.assertNotIn("input_text", str(summaries))
        self.assertNotIn("payload", str(summaries))

    def test_control_states_never_cross_supported_boundary(self) -> None:
        controls = [
            item for item in self.evaluation.receipts if item.role is ChromatinFrontierRole.CONTROL
        ]
        self.assertEqual(len(controls), 12)
        self.assertTrue(all(item.adapter_state != "supported" for item in controls))
        self.assertEqual(
            {item.adapter_state for item in controls},
            {"ambiguous", "partial", "out_of_domain"},
        )


if __name__ == "__main__":
    unittest.main()
