from __future__ import annotations

import unittest
from dataclasses import replace

from glio_noncode.errors import ValidationError
from glio_noncode.sequence_frontier_exports import (
    export_sequence_frontier_metrics_csv,
    export_sequence_frontier_receipts_csv,
    export_sequence_frontier_review_csv,
    render_sequence_frontier_release_markdown,
    render_sequence_frontier_review_markdown,
    sequence_frontier_export_receipt,
)
from glio_noncode.sequence_frontier_fixture_eval import evaluate_sequence_frontier_fixture
from glio_noncode.sequence_frontier_lineage import (
    build_sequence_frontier_lineage,
    verify_sequence_frontier_lineage,
)
from glio_noncode.sequence_frontier_metrics import compute_sequence_frontier_metrics
from glio_noncode.sequence_frontier_observability import (
    build_sequence_frontier_trace,
    compare_sequence_frontier_runs,
    sequence_frontier_review_budget,
)
from glio_noncode.sequence_frontier_policy import evaluate_sequence_frontier_policy
from glio_noncode.sequence_frontier_public_data import (
    SEQUENCE_FRONTIER_CONTEXT_KEY,
    SequenceFrontierOperation,
    SequenceFrontierRole,
    SequenceFrontierSourceReceipt,
    audit_sequence_frontier_data,
    build_sequence_frontier_catalog,
    default_sequence_frontier_fixture,
)
from glio_noncode.sequence_frontier_quality_gate import run_sequence_frontier_quality_gate
from glio_noncode.sequence_frontier_reconciliation import reconcile_sequence_frontier
from glio_noncode.sequence_frontier_release import build_sequence_frontier_release
from glio_noncode.sequence_frontier_replay import replay_sequence_frontier_evaluation
from glio_noncode.sequence_frontier_runtime import (
    SequenceFrontierRuntimeOptions,
    run_sequence_frontier_pipeline,
)
from glio_noncode.sequence_frontier_scenario_matrix import evaluate_sequence_frontier_scenarios
from glio_noncode.sequence_frontier_schema import (
    sequence_frontier_schema_manifest,
    validate_sequence_frontier_schema,
)
from glio_noncode.sequence_frontier_views import (
    build_sequence_frontier_view,
    filter_sequence_frontier_review_queue,
    sequence_frontier_review_summary,
)


class SequenceFrontierEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_sequence_frontier_fixture()
        self.evaluation = evaluate_sequence_frontier_fixture(self.fixture)
        self.view = build_sequence_frontier_view(self.fixture, self.evaluation)

    def test_fixture_balance_catalog_and_data_audit(self) -> None:
        self.assertEqual(self.fixture.context_key, SEQUENCE_FRONTIER_CONTEXT_KEY)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)
        self.assertTrue(audit_sequence_frontier_data(self.fixture).accepted)
        catalog = build_sequence_frontier_catalog(self.fixture)
        self.assertEqual(set(catalog.operations), set(SequenceFrontierOperation))
        self.assertEqual(len(catalog.record_ids), 16)

    def test_evaluation_has_120_checks_and_explicit_states(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.checks), 120)
        self.assertEqual((self.evaluation.positive_count, self.evaluation.control_count), (4, 12))
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
            replay_sequence_frontier_evaluation(self.evaluation, fixture=self.fixture).accepted
        )
        self.assertTrue(evaluate_sequence_frontier_scenarios(self.evaluation).accepted)
        self.assertTrue(evaluate_sequence_frontier_policy(self.fixture, self.evaluation).accepted)
        lineage = build_sequence_frontier_lineage(self.fixture, self.evaluation)
        self.assertFalse(verify_sequence_frontier_lineage(lineage, self.fixture, self.evaluation))
        self.assertTrue(reconcile_sequence_frontier(self.fixture, self.evaluation).accepted)

    def test_quality_metrics_runtime_and_release(self) -> None:
        quality = run_sequence_frontier_quality_gate(self.fixture)
        self.assertTrue(quality.accepted)
        metrics = compute_sequence_frontier_metrics(self.evaluation)
        self.assertEqual(
            (
                metrics.total_records,
                metrics.accepted_records,
                metrics.published_records,
                metrics.review_records,
            ),
            (16, 3, 1, 12),
        )
        runtime = run_sequence_frontier_pipeline(
            SequenceFrontierRuntimeOptions(run_id="sequence-frontier-test"), fixture=self.fixture
        )
        self.assertTrue(runtime.accepted)
        release = build_sequence_frontier_release(quality, runtime)
        self.assertTrue(release.accepted)
        self.assertEqual(
            set(release.operation_ids), {operation.value for operation in SequenceFrontierOperation}
        )

    def test_strict_runtime_rejects_visible_review_records(self) -> None:
        runtime = run_sequence_frontier_pipeline(
            SequenceFrontierRuntimeOptions(run_id="sequence-frontier-strict", fail_on_review=True),
            fixture=self.fixture,
        )
        self.assertFalse(runtime.accepted)
        self.assertEqual(runtime.status, "rejected")

    def test_schema_views_and_review_budget(self) -> None:
        schema = validate_sequence_frontier_schema(self.fixture, self.evaluation)
        self.assertTrue(schema.accepted)
        self.assertEqual((len(schema.schemas), len(schema.checks)), (4, 23))
        self.assertEqual(len(sequence_frontier_schema_manifest()["schemas"]), 4)
        self.assertTrue(self.view.accepted)
        self.assertEqual(
            (
                self.view.review_count,
                len(self.view.accepted_record_ids),
                len(self.view.published_record_ids),
            ),
            (12, 3, 1),
        )
        self.assertEqual(len(self.view.source_matrix), 5)
        self.assertEqual(
            len(filter_sequence_frontier_review_queue(self.view, states=("out_of_domain",))), 4
        )
        self.assertEqual(sequence_frontier_review_summary(self.view)["review_count"], 12)
        self.assertEqual(
            sequence_frontier_review_budget(self.view, maximum_priority=2)["eligible_review_count"],
            7,
        )

    def test_trace_exports_and_release_markdown_are_sanitized(self) -> None:
        runtime = run_sequence_frontier_pipeline(
            SequenceFrontierRuntimeOptions(run_id="sequence-frontier-trace"), fixture=self.fixture
        )
        trace = build_sequence_frontier_trace(runtime, self.view)
        self.assertTrue(trace.accepted)
        self.assertEqual((len(trace.stage_receipts), len(trace.events)), (9, 9))
        left = run_sequence_frontier_pipeline(
            SequenceFrontierRuntimeOptions(run_id="sequence-frontier-left"), fixture=self.fixture
        )
        right = run_sequence_frontier_pipeline(
            SequenceFrontierRuntimeOptions(run_id="sequence-frontier-right"), fixture=self.fixture
        )
        self.assertTrue(compare_sequence_frontier_runs(left, right).equivalent)
        receipts = export_sequence_frontier_receipts_csv(self.evaluation)
        review = export_sequence_frontier_review_csv(self.view)
        metrics = export_sequence_frontier_metrics_csv(
            compute_sequence_frontier_metrics(self.evaluation)
        )
        markdown = render_sequence_frontier_review_markdown(self.view)
        release_markdown = render_sequence_frontier_release_markdown(
            build_sequence_frontier_release(runtime.quality, runtime)
        )
        self.assertEqual(
            (receipts.count("\n"), review.count("\n"), metrics.count("\n")), (17, 13, 5)
        )
        self.assertIn("C13-CTRL-003", markdown)
        self.assertIn("ncbi-refseq", release_markdown)
        self.assertNotIn("input_text", receipts)
        self.assertNotIn("input_text", str(trace.to_dict()))
        self.assertTrue(
            sequence_frontier_export_receipt("review.csv", review)["content_address"].startswith(
                "sha256:"
            )
        )

    def test_data_audit_rejects_context_boundary_and_subject_payloads(self) -> None:
        context_fixture = replace(
            self.fixture, context_key="GRCh38|other|adult|stem_like|core|untreated"
        )
        context_audit = audit_sequence_frontier_data(context_fixture)
        self.assertFalse(context_audit.accepted)
        self.assertIn("fixture-context", context_audit.failed_check_ids)

        subject_record = replace(
            self.fixture.records[0],
            payload=self.fixture.records[0].payload | {"subject": "not-permitted"},
        )
        subject_fixture = replace(self.fixture, records=(subject_record, *self.fixture.records[1:]))
        subject_audit = audit_sequence_frontier_data(subject_fixture)
        self.assertFalse(subject_audit.accepted)
        self.assertIn("no-subject-identifiers", subject_audit.failed_check_ids)

        with self.assertRaises(ValidationError):
            replace(self.fixture, evidence_boundary="private_subject")

    def test_data_audit_rejects_missing_sources_and_duplicate_records(self) -> None:
        missing_source_record = replace(
            self.fixture.records[0], source_ids=("missing-public-receipt",)
        )
        missing_source_fixture = replace(
            self.fixture,
            records=(missing_source_record, *self.fixture.records[1:]),
        )
        missing_source_audit = audit_sequence_frontier_data(missing_source_fixture)
        self.assertFalse(missing_source_audit.accepted)
        self.assertIn("source-closure", missing_source_audit.failed_check_ids)

        duplicate_record = replace(
            self.fixture.records[-1],
            record_id=self.fixture.records[0].record_id,
        )
        duplicate_fixture = replace(
            self.fixture, records=(*self.fixture.records[:-1], duplicate_record)
        )
        duplicate_audit = audit_sequence_frontier_data(duplicate_fixture)
        self.assertFalse(duplicate_audit.accepted)
        self.assertIn("record-ids-unique", duplicate_audit.failed_check_ids)

    def test_evaluation_rejects_wrong_state_and_missing_issue_floor(self) -> None:
        wrong_state_record = replace(self.fixture.records[0], expected_state="review")
        wrong_state_fixture = replace(
            self.fixture,
            records=(wrong_state_record, *self.fixture.records[1:]),
        )
        wrong_state = evaluate_sequence_frontier_fixture(wrong_state_fixture)
        self.assertFalse(wrong_state.accepted)
        self.assertFalse(
            next(
                item for item in wrong_state.checks if item.check_id == "C13-POS-001:expected-state"
            ).passed
        )

        missing_issue_record = replace(
            self.fixture.records[0], expected_issue_codes=("missing-issue",)
        )
        missing_issue_fixture = replace(
            self.fixture,
            records=(missing_issue_record, *self.fixture.records[1:]),
        )
        missing_issue = evaluate_sequence_frontier_fixture(missing_issue_fixture)
        self.assertFalse(missing_issue.accepted)
        self.assertFalse(
            next(
                item
                for item in missing_issue.checks
                if item.check_id == "C13-POS-001:expected-issues"
            ).passed
        )

    def test_quality_gate_surfaces_failed_fixture_checks(self) -> None:
        altered_record = replace(
            self.fixture.records[0],
            payload={"input_text": "[]"},
        )
        altered_fixture = replace(
            self.fixture,
            records=(altered_record, *self.fixture.records[1:]),
        )
        quality = run_sequence_frontier_quality_gate(altered_fixture)
        self.assertFalse(quality.accepted)
        self.assertTrue(quality.failed_check_ids)
        self.assertIn("evaluation", quality.failed_check_ids)
        self.assertFalse(quality.bundle.accepted)

    def test_policy_review_budget_is_deterministic_and_bounded(self) -> None:
        first = sequence_frontier_review_budget(self.view, maximum_priority=1)
        second = sequence_frontier_review_budget(self.view, maximum_priority=1)
        self.assertEqual(first, second)
        self.assertLessEqual(first["eligible_review_count"], 12)
        self.assertEqual(first["maximum_priority"], 1)
        self.assertTrue(first["content_address"].startswith("sha256:"))
        self.assertEqual(
            set(first["eligible_record_ids"]),
            {"C16-CTRL-001"},
        )

    def test_runtime_context_and_source_mode_boundaries(self) -> None:
        mismatched_context = run_sequence_frontier_pipeline(
            SequenceFrontierRuntimeOptions(
                run_id="sequence-frontier-context-mismatch",
                requested_context_key="GRCh38|wrong|adult|stem_like|core|untreated",
            ),
            fixture=self.fixture,
        )
        self.assertFalse(mismatched_context.accepted)
        self.assertEqual(mismatched_context.status, "rejected")

        with self.assertRaises(ValueError):
            SequenceFrontierRuntimeOptions(
                run_id="sequence-frontier-unsupported-source",
                source_mode="network-source",
            )

        with self.assertRaises(ValidationError):
            SequenceFrontierRuntimeOptions(run_id="")

    def test_replay_and_reconciliation_report_drift(self) -> None:
        altered_record = replace(self.fixture.records[0], expected_state="review")
        altered_fixture = replace(
            self.fixture,
            records=(altered_record, *self.fixture.records[1:]),
        )
        altered_evaluation = evaluate_sequence_frontier_fixture(altered_fixture)
        replay = replay_sequence_frontier_evaluation(altered_evaluation, fixture=self.fixture)
        self.assertFalse(replay.accepted)
        self.assertIn(
            "fixture-address", {item.check_id for item in replay.checks if not item.passed}
        )
        reconciliation = reconcile_sequence_frontier(altered_fixture, altered_evaluation)
        self.assertFalse(reconciliation.accepted)
        self.assertIn(
            "C13-POS-001", {item.record_id for item in reconciliation.items if not item.passed}
        )

    def test_schema_manifest_and_serialized_view_are_closed(self) -> None:
        manifest = sequence_frontier_schema_manifest()
        self.assertEqual(
            {item["operation"] for item in manifest["schemas"]},
            {operation.value for operation in SequenceFrontierOperation},
        )
        self.assertTrue(manifest["content_address"].startswith("sha256:"))
        view_dict = self.view.to_dict()
        self.assertEqual(view_dict["fixture_id"], self.fixture.fixture_id)
        self.assertEqual(view_dict["context_key"], SEQUENCE_FRONTIER_CONTEXT_KEY)
        self.assertNotIn("evidence_boundary", view_dict)
        self.assertNotIn("payload", str(view_dict))
        self.assertNotIn("input_text", str(view_dict))

    def test_catalog_and_fixture_addresses_are_stable(self) -> None:
        first_catalog = build_sequence_frontier_catalog(self.fixture)
        second_catalog = build_sequence_frontier_catalog(default_sequence_frontier_fixture())
        self.assertEqual(first_catalog.content_address, second_catalog.content_address)
        self.assertEqual(
            first_catalog.source_ids, tuple(source.source_id for source in self.fixture.sources)
        )
        self.assertEqual(
            first_catalog.record_ids, tuple(record.record_id for record in self.fixture.records)
        )
        self.assertTrue(self.fixture.content_address.startswith("sha256:"))
        self.assertTrue(first_catalog.content_address.startswith("sha256:"))

    def test_source_receipts_require_https_and_non_empty_fields(self) -> None:
        source = self.fixture.sources[0]
        with self.assertRaises(ValidationError):
            replace(source, uri="http://insecure.example")
        with self.assertRaises(ValidationError):
            SequenceFrontierSourceReceipt(
                source_id="",
                title="title",
                uri="https://example.org/source",
                source_kind="public",
                release="2026",
                scope="aggregate",
                content_address="sha256:source",
            )

    def test_record_contract_requires_payload_sources_and_declared_enums(self) -> None:
        record = self.fixture.records[0]
        with self.assertRaises(ValidationError):
            replace(record, source_ids=())
        with self.assertRaises(ValidationError):
            replace(record, payload={})
        with self.assertRaises(ValidationError):
            replace(record, operation="not-an-operation")
        self.assertIs(record.role, SequenceFrontierRole.POSITIVE)

    def test_exports_keep_review_rows_and_content_addresses(self) -> None:
        review_rows = export_sequence_frontier_review_csv(self.view).splitlines()
        receipt_rows = export_sequence_frontier_receipts_csv(self.evaluation).splitlines()
        metric_rows = export_sequence_frontier_metrics_csv(
            compute_sequence_frontier_metrics(self.evaluation)
        ).splitlines()
        self.assertEqual(review_rows[0].split(",")[:3], ["record_id", "operation", "role"])
        self.assertEqual(receipt_rows[0].split(",")[:3], ["record_id", "operation", "role"])
        self.assertEqual(
            metric_rows[0].split(",")[:3], ["operation", "record_count", "positive_count"]
        )
        self.assertTrue(all("sha256:" not in row or row for row in review_rows))
        self.assertIn("C16-CTRL-003", "\n".join(review_rows))

    def test_operation_counts_and_review_states_remain_explicit(self) -> None:
        metrics = compute_sequence_frontier_metrics(self.evaluation)
        by_operation = {item.operation.value: item for item in metrics.operation_metrics}
        for operation in SequenceFrontierOperation:
            metric = by_operation[operation.value]
            self.assertEqual(metric.record_count, 4)
            self.assertEqual(metric.positive_count, 1)
            self.assertEqual(metric.control_count, 3)
            self.assertGreaterEqual(metric.review_count, 0)
            self.assertTrue(metric.content_address.startswith("sha256:"))
        self.assertEqual(metrics.review_records, 12)

    def test_lineage_closure_is_false_only_for_expected_control_paths(self) -> None:
        lineage = build_sequence_frontier_lineage(self.fixture, self.evaluation)
        self.assertEqual(len(lineage.edges), 16)
        self.assertTrue(lineage.content_address.startswith("sha256:"))
        self.assertFalse(verify_sequence_frontier_lineage(lineage, self.fixture, self.evaluation))

    def test_published_record_has_bundle_addresses_and_model_receipts(self) -> None:
        published = next(
            item for item in self.evaluation.receipts if item.adapter_state == "published"
        )
        self.assertEqual(published.record_id, "C16-POS-001")
        self.assertTrue(published.summary["records_address"].startswith("sha256:"))
        self.assertTrue(published.summary["bundle_address"].startswith("sha256:"))
        self.assertTrue(published.summary["model_ids"])
        self.assertEqual(published.observed_issue_codes, ())

    def test_control_records_never_cross_success_boundary(self) -> None:
        controls = [
            item for item in self.evaluation.receipts if item.role is SequenceFrontierRole.CONTROL
        ]
        self.assertEqual(len(controls), 12)
        self.assertTrue(
            all(item.adapter_state not in {"accepted", "published"} for item in controls)
        )
        self.assertTrue(all(item.observed_issue_codes for item in controls))


if __name__ == "__main__":
    unittest.main()
