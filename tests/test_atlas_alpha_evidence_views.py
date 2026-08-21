from __future__ import annotations

import unittest

from glio_noncode.atlas_alpha_evidence_exports import (
    atlas_alpha_evidence_export_receipt,
    export_atlas_alpha_evidence_metrics_csv,
    export_atlas_alpha_evidence_receipts_csv,
    export_atlas_alpha_evidence_review_csv,
    render_atlas_alpha_evidence_release_markdown,
    render_atlas_alpha_evidence_review_markdown,
)
from glio_noncode.atlas_alpha_evidence_fixture_eval import evaluate_atlas_alpha_evidence_fixture
from glio_noncode.atlas_alpha_evidence_metrics import compute_atlas_alpha_evidence_metrics
from glio_noncode.atlas_alpha_evidence_observability import (
    atlas_alpha_evidence_review_budget,
    build_atlas_alpha_evidence_trace,
    compare_atlas_alpha_evidence_runs,
)
from glio_noncode.atlas_alpha_evidence_public_data import (
    AtlasAlphaEvidenceOperation,
    default_atlas_alpha_evidence_fixture,
)
from glio_noncode.atlas_alpha_evidence_quality_gate import run_atlas_alpha_evidence_quality_gate
from glio_noncode.atlas_alpha_evidence_release import build_atlas_alpha_evidence_release
from glio_noncode.atlas_alpha_evidence_runtime import (
    AtlasAlphaEvidenceRuntimeOptions,
    run_atlas_alpha_evidence_pipeline,
)
from glio_noncode.atlas_alpha_evidence_schema import (
    atlas_alpha_evidence_schema_manifest,
    validate_atlas_alpha_evidence_schema,
)
from glio_noncode.atlas_alpha_evidence_views import (
    build_atlas_alpha_evidence_view,
    filter_atlas_alpha_evidence_review_queue,
    review_queue_summary,
)


class AtlasAlphaEvidenceViewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_atlas_alpha_evidence_fixture()
        self.evaluation = evaluate_atlas_alpha_evidence_fixture(self.fixture)
        self.view = build_atlas_alpha_evidence_view(self.fixture, self.evaluation)

    def test_operation_views_and_source_matrix_are_complete(self) -> None:
        self.assertTrue(self.view.accepted)
        self.assertEqual(len(self.view.operation_views), 4)
        self.assertEqual(
            {item.operation for item in self.view.operation_views}, set(AtlasAlphaEvidenceOperation)
        )
        self.assertEqual(len(self.view.review_queue), 12)
        self.assertEqual(len(self.view.supported_record_ids), 4)
        self.assertEqual(len(self.view.source_matrix), 5)
        self.assertTrue(
            all(item.content_address.startswith("sha256:") for item in self.view.source_matrix)
        )

    def test_review_queue_is_priority_ordered_and_filterable(self) -> None:
        priorities = tuple(item.priority for item in self.view.review_queue)
        self.assertEqual(priorities, tuple(sorted(priorities, reverse=True)))
        ambiguous = filter_atlas_alpha_evidence_review_queue(self.view, states=("ambiguous",))
        self.assertEqual(len(ambiguous), 3)
        chromatin = filter_atlas_alpha_evidence_review_queue(
            self.view, operation=AtlasAlphaEvidenceOperation.OPEN_CHROMATIN
        )
        self.assertEqual(len(chromatin), 3)
        high = filter_atlas_alpha_evidence_review_queue(self.view, minimum_priority=4)
        self.assertEqual(len(high), 4)
        self.assertTrue(all(item.priority == 4 for item in high))

    def test_view_summary_is_stable_and_does_not_include_payloads(self) -> None:
        summary = review_queue_summary(self.view)
        self.assertEqual(summary["review_count"], 12)
        self.assertEqual(summary["supported_count"], 4)
        self.assertEqual(summary["by_state"]["ambiguous"], 3)
        self.assertEqual(summary["by_operation"]["open_chromatin_harmonization"], 3)
        self.assertNotIn("input_text", str(summary))
        budget = atlas_alpha_evidence_review_budget(self.view, maximum_priority=3)
        self.assertEqual(budget["eligible_review_count"], 8)
        self.assertTrue(budget["content_address"].startswith("sha256:"))

    def test_text_exports_are_deterministic_and_sanitized(self) -> None:
        metrics = compute_atlas_alpha_evidence_metrics(self.evaluation)
        receipts_csv = export_atlas_alpha_evidence_receipts_csv(self.evaluation)
        review_csv = export_atlas_alpha_evidence_review_csv(self.view)
        metrics_csv = export_atlas_alpha_evidence_metrics_csv(metrics)
        review_markdown = render_atlas_alpha_evidence_review_markdown(self.view)
        self.assertEqual(receipts_csv.count("\n"), 17)
        self.assertEqual(review_csv.count("\n"), 13)
        self.assertEqual(metrics_csv.count("\n"), 5)
        self.assertIn("C09-CTRL-002", review_markdown)
        self.assertNotIn("input_text", receipts_csv)
        receipt = atlas_alpha_evidence_export_receipt("review.csv", review_csv)
        self.assertEqual(receipt["line_count"], 13)
        self.assertTrue(receipt["content_address"].startswith("sha256:"))

    def test_trace_has_nine_ordered_stages_and_sanitized_events(self) -> None:
        runtime = run_atlas_alpha_evidence_pipeline(
            AtlasAlphaEvidenceRuntimeOptions(run_id="trace-one"), fixture=self.fixture
        )
        trace = build_atlas_alpha_evidence_trace(runtime, self.view)
        self.assertTrue(trace.accepted)
        self.assertEqual(len(trace.stage_receipts), 9)
        self.assertEqual(len(trace.events), 9)
        self.assertEqual(trace.stage_names[0], "data_audit")
        self.assertEqual(trace.stage_names[-1], "bundle")
        self.assertEqual(tuple(event.sequence for event in trace.events), tuple(range(1, 10)))
        self.assertNotIn("input_text", str(trace.to_dict()))

    def test_equivalent_runs_have_no_state_drift(self) -> None:
        left = run_atlas_alpha_evidence_pipeline(
            AtlasAlphaEvidenceRuntimeOptions(run_id="left"), fixture=self.fixture
        )
        right = run_atlas_alpha_evidence_pipeline(
            AtlasAlphaEvidenceRuntimeOptions(run_id="right"), fixture=self.fixture
        )
        comparison = compare_atlas_alpha_evidence_runs(left, right)
        self.assertTrue(comparison.equivalent)
        self.assertEqual(comparison.review_count_delta, 0)
        self.assertEqual(comparison.state_changes, ())

    def test_release_markdown_contains_operation_and_source_closure(self) -> None:
        quality = run_atlas_alpha_evidence_quality_gate(self.fixture)
        runtime = run_atlas_alpha_evidence_pipeline(
            AtlasAlphaEvidenceRuntimeOptions(run_id="release-view"), fixture=self.fixture
        )
        release = build_atlas_alpha_evidence_release(quality, runtime)
        markdown = render_atlas_alpha_evidence_release_markdown(release)
        self.assertIn("open_chromatin_harmonization", markdown)
        self.assertIn("encode-atac", markdown)
        self.assertIn(release.content_address, markdown)

    def test_schema_manifest_and_quality_schema_gate_are_complete(self) -> None:
        report = validate_atlas_alpha_evidence_schema(self.fixture, self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.schemas), 4)
        self.assertEqual(len(report.checks), 23)
        manifest = atlas_alpha_evidence_schema_manifest()
        self.assertEqual(len(manifest["schemas"]), 4)
        self.assertTrue(manifest["content_address"].startswith("sha256:"))
        quality = run_atlas_alpha_evidence_quality_gate(self.fixture)
        self.assertTrue(quality.accepted)
        self.assertTrue(any(item.check_id == "schema" and item.passed for item in quality.checks))


if __name__ == "__main__":
    unittest.main()
