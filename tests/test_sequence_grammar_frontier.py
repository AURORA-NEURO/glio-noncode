from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from glio_noncode.sequence_grammar_frontier_accessibility import (
    audit_sequence_grammar_accessibility,
)
from glio_noncode.sequence_grammar_frontier_adapters import (
    build_sequence_grammar_adapters,
    execute_sequence_grammar_record,
)
from glio_noncode.sequence_grammar_frontier_artifacts import build_sequence_grammar_artifacts
from glio_noncode.sequence_grammar_frontier_bundle import build_sequence_grammar_bundle
from glio_noncode.sequence_grammar_frontier_checks import (
    default_sequence_grammar_invariants,
    run_sequence_grammar_invariants,
)
from glio_noncode.sequence_grammar_frontier_compliance import audit_sequence_grammar_boundary
from glio_noncode.sequence_grammar_frontier_contracts import default_sequence_grammar_contracts
from glio_noncode.sequence_grammar_frontier_exports import (
    export_sequence_grammar_metrics_csv,
    export_sequence_grammar_receipts_csv,
    export_sequence_grammar_review_csv,
    render_sequence_grammar_release_markdown,
    render_sequence_grammar_review_markdown,
    sequence_grammar_export_receipt,
)
from glio_noncode.sequence_grammar_frontier_fixture_eval import evaluate_sequence_grammar_fixture
from glio_noncode.sequence_grammar_frontier_lineage import (
    build_sequence_grammar_lineage,
    verify_sequence_grammar_lineage,
)
from glio_noncode.sequence_grammar_frontier_metrics import compute_sequence_grammar_metrics
from glio_noncode.sequence_grammar_frontier_observability import (
    build_sequence_grammar_trace,
    compare_sequence_grammar_runs,
    sequence_grammar_review_budget,
)
from glio_noncode.sequence_grammar_frontier_pipeline import run_sequence_grammar_frontier_pipeline
from glio_noncode.sequence_grammar_frontier_policy import (
    SequenceGrammarDecision,
    evaluate_sequence_grammar_policy,
)
from glio_noncode.sequence_grammar_frontier_public_data import (
    SEQUENCE_GRAMMAR_CONTEXT_KEY,
    SequenceGrammarOperation,
    SequenceGrammarRole,
    SequenceGrammarState,
    audit_sequence_grammar_data,
    build_sequence_grammar_catalog,
    default_sequence_grammar_fixture,
    load_sequence_grammar_fixture,
)
from glio_noncode.sequence_grammar_frontier_quality_gate import run_sequence_grammar_quality_gate
from glio_noncode.sequence_grammar_frontier_reconciliation import reconcile_sequence_grammar
from glio_noncode.sequence_grammar_frontier_release import build_sequence_grammar_release
from glio_noncode.sequence_grammar_frontier_replay import replay_sequence_grammar_evaluation
from glio_noncode.sequence_grammar_frontier_review_queue import build_sequence_grammar_review_queue
from glio_noncode.sequence_grammar_frontier_runbook import default_sequence_grammar_runbook
from glio_noncode.sequence_grammar_frontier_runtime import (
    SequenceGrammarRuntimeOptions,
    run_sequence_grammar_pipeline,
)
from glio_noncode.sequence_grammar_frontier_scenario_matrix import (
    default_sequence_grammar_scenarios,
    evaluate_sequence_grammar_scenarios,
)
from glio_noncode.sequence_grammar_frontier_schema import (
    default_sequence_grammar_schemas,
    sequence_grammar_schema_manifest,
    validate_sequence_grammar_schema,
)
from glio_noncode.sequence_grammar_frontier_thresholds import (
    build_sequence_grammar_threshold_report,
    default_sequence_grammar_threshold_profiles,
)
from glio_noncode.sequence_grammar_frontier_validation_matrix import (
    build_sequence_grammar_validation_matrix,
)
from glio_noncode.sequence_grammar_frontier_views import (
    build_sequence_grammar_view,
    filter_sequence_grammar_review_queue,
    sequence_grammar_review_summary,
)


class SequenceGrammarFrontierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_sequence_grammar_fixture()
        self.evaluation = evaluate_sequence_grammar_fixture(self.fixture)

    def test_public_fixture_is_balanced_and_closed(self) -> None:
        self.assertEqual(self.fixture.context_key, SEQUENCE_GRAMMAR_CONTEXT_KEY)
        self.assertEqual(
            (len(self.fixture.positive_records), len(self.fixture.control_records)), (4, 12)
        )
        self.assertEqual(len(self.fixture.sources), 4)
        self.assertTrue(audit_sequence_grammar_data(self.fixture).accepted)
        catalog = build_sequence_grammar_catalog(self.fixture)
        self.assertEqual(
            set(catalog.operations), {operation.value for operation in SequenceGrammarOperation}
        )
        self.assertEqual(len(catalog.record_ids), 16)
        self.assertIn("motif_loss", catalog.issue_codes)

    def test_fixture_round_trip_retains_addresses(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.json"
            path.write_text(
                json.dumps(self.fixture.to_dict(include_payload=True)), encoding="utf-8"
            )
            loaded = load_sequence_grammar_fixture(path)
        self.assertEqual(loaded.content_address, self.fixture.content_address)
        self.assertEqual(
            evaluate_sequence_grammar_fixture(loaded).content_address,
            self.evaluation.content_address,
        )

    def test_evaluation_has_six_checks_per_execution(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual((len(self.evaluation.executions), len(self.evaluation.checks)), (16, 96))
        self.assertEqual((self.evaluation.positive_count, self.evaluation.control_count), (4, 12))
        states = {item.record_id: item.adapter_state for item in self.evaluation.executions}
        self.assertEqual(states["C05-POS-001"], SequenceGrammarState.SUPPORTED)
        self.assertEqual(states["C05-CTRL-001"], SequenceGrammarState.INVALID)
        self.assertEqual(states["C06-POS-001"], SequenceGrammarState.SUPPORTED)
        self.assertEqual(states["C07-CTRL-002"], SequenceGrammarState.ABSTAINED)
        self.assertEqual(states["C08-CTRL-003"], SequenceGrammarState.INVALID)

    def test_controls_retain_distinct_issue_paths(self) -> None:
        by_id = self.evaluation.execution_map()
        self.assertIn("motif_loss", by_id["C05-POS-001"].issue_codes)
        self.assertIn("invalid_sequence_alphabet", by_id["C05-CTRL-001"].issue_codes)
        self.assertIn("empty_motif_catalog", by_id["C06-CTRL-003"].issue_codes)
        self.assertIn("compatible_spacing", by_id["C07-POS-001"].issue_codes)
        self.assertIn("unmatched_rule", by_id["C07-CTRL-002"].issue_codes)
        self.assertIn("interaction_supported", by_id["C08-POS-001"].issue_codes)
        self.assertIn("missing_required_interaction", by_id["C08-CTRL-001"].issue_codes)

    def test_low_level_dispatch_matches_each_operation(self) -> None:
        results = tuple(execute_sequence_grammar_record(record) for record in self.fixture.records)
        self.assertEqual({result.operation for result in results}, set(SequenceGrammarOperation))
        self.assertTrue(all(result.content_address.startswith("sha256:") for result in results))
        self.assertTrue(build_sequence_grammar_adapters().accepted)

    def test_mutated_expected_state_fails_evaluation(self) -> None:
        altered = replace(self.fixture.records[0], expected_state=SequenceGrammarState.ABSTAINED)
        result = evaluate_sequence_grammar_fixture(
            replace(self.fixture, records=(altered, *self.fixture.records[1:]))
        )
        self.assertFalse(result.accepted)
        self.assertIn("C05-POS-001:state", result.failed_check_ids)

    def test_contracts_and_schema_cover_operations(self) -> None:
        contracts = default_sequence_grammar_contracts()
        schemas = default_sequence_grammar_schemas()
        report = validate_sequence_grammar_schema(self.fixture, self.evaluation, contracts)
        self.assertTrue(contracts.accepted)
        self.assertEqual(len(contracts.contracts), 4)
        self.assertEqual(len(schemas), 4)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 37)
        self.assertEqual(
            {item["operation"] for item in sequence_grammar_schema_manifest()["schemas"]},
            {operation.value for operation in SequenceGrammarOperation},
        )

    def test_metrics_conserve_roles_and_states(self) -> None:
        metrics = compute_sequence_grammar_metrics(self.evaluation)
        self.assertEqual(
            (metrics.total_records, metrics.positive_records, metrics.control_records), (16, 4, 12)
        )
        self.assertEqual((metrics.invalid_records, metrics.abstained_records), (4, 8))
        self.assertEqual(len(metrics.operation_metrics), 4)
        self.assertTrue(
            all(item.content_address.startswith("sha256:") for item in metrics.operation_metrics)
        )

    def test_lineage_has_source_record_execution_and_issue_layers(self) -> None:
        lineage = build_sequence_grammar_lineage(self.fixture, self.evaluation)
        self.assertTrue(lineage.accepted)
        self.assertTrue(verify_sequence_grammar_lineage(lineage, self.fixture, self.evaluation))
        self.assertEqual(sum(node.node_kind == "source" for node in lineage.nodes), 4)
        self.assertEqual(sum(node.node_kind == "record" for node in lineage.nodes), 16)
        self.assertEqual(sum(node.node_kind == "execution" for node in lineage.nodes), 16)
        self.assertGreater(len(lineage.edges), 40)

    def test_policy_withholds_controls_and_allows_positive_research_rows(self) -> None:
        policy = evaluate_sequence_grammar_policy(self.fixture, self.evaluation)
        self.assertTrue(policy.accepted)
        self.assertEqual(len(policy.decisions), 16)
        self.assertEqual(
            sum(
                item.decision is SequenceGrammarDecision.ALLOW_RESEARCH for item in policy.decisions
            ),
            4,
        )
        self.assertTrue(
            all(not item.publishable for item in policy.decisions if "CTRL" in item.record_id)
        )

    def test_reconciliation_is_exact(self) -> None:
        policy = evaluate_sequence_grammar_policy(self.fixture, self.evaluation)
        reconciliation = reconcile_sequence_grammar(self.fixture, self.evaluation, policy)
        self.assertTrue(reconciliation.accepted)
        self.assertEqual(reconciliation.failed_record_ids, ())
        self.assertEqual(len(reconciliation.items), 16)

    def test_quality_gate_has_twenty_five_checks(self) -> None:
        quality = run_sequence_grammar_quality_gate(self.fixture)
        self.assertTrue(quality.accepted)
        self.assertEqual(len(quality.checks), 25)
        self.assertEqual(quality.failed_check_ids, ())

    def test_replay_is_deterministic(self) -> None:
        replay = replay_sequence_grammar_evaluation(self.evaluation, self.fixture)
        self.assertTrue(replay.accepted)
        self.assertEqual(len(replay.checks), 8)
        first = run_sequence_grammar_pipeline(
            SequenceGrammarRuntimeOptions(run_id="grammar-first"), fixture=self.fixture
        )
        second = run_sequence_grammar_pipeline(
            SequenceGrammarRuntimeOptions(run_id="grammar-second"), fixture=self.fixture
        )
        self.assertFalse(compare_sequence_grammar_runs(first, second).equivalent)

    def test_runtime_orders_ten_stages_and_strict_mode_holds_review(self) -> None:
        runtime = run_sequence_grammar_pipeline(
            SequenceGrammarRuntimeOptions(run_id="grammar-runtime"), fixture=self.fixture
        )
        self.assertTrue(runtime.accepted)
        self.assertEqual(tuple(stage.ordinal for stage in runtime.stages), tuple(range(1, 11)))
        strict = run_sequence_grammar_pipeline(
            SequenceGrammarRuntimeOptions(run_id="grammar-strict", fail_on_review=True),
            fixture=self.fixture,
        )
        self.assertFalse(strict.accepted)
        self.assertEqual(strict.status, "rejected")

    def test_release_bundle_and_artifacts_are_closed(self) -> None:
        runtime = run_sequence_grammar_pipeline(
            SequenceGrammarRuntimeOptions(run_id="grammar-release"), fixture=self.fixture
        )
        release = build_sequence_grammar_release(runtime.quality, runtime)
        bundle = build_sequence_grammar_bundle(self.fixture, self.evaluation, release)
        artifacts = build_sequence_grammar_artifacts(runtime.quality, release, bundle)
        self.assertTrue(release.accepted)
        self.assertTrue(bundle.accepted)
        self.assertTrue(artifacts.accepted)
        self.assertEqual(len(bundle.entries), 16)
        self.assertEqual(len(artifacts.artifacts), 9)

    def test_view_queue_and_budget_keep_controls(self) -> None:
        policy = evaluate_sequence_grammar_policy(self.fixture, self.evaluation)
        view = build_sequence_grammar_view(self.fixture, self.evaluation, policy)
        queue = build_sequence_grammar_review_queue(view)
        self.assertTrue(view.accepted)
        self.assertTrue(queue.accepted)
        self.assertEqual((view.review_count, len(queue.items)), (12, 12))
        self.assertEqual(len(filter_sequence_grammar_review_queue(view, maximum_priority=3)), 12)
        self.assertEqual(sequence_grammar_review_summary(view)["accepted_count"], 4)
        self.assertEqual(sequence_grammar_review_budget(view)["eligible_review_count"], 12)
        self.assertEqual(queue.next_item().entry.role, SequenceGrammarRole.CONTROL)

    def test_trace_accessibility_boundary_and_invariants_accept(self) -> None:
        runtime = run_sequence_grammar_pipeline(
            SequenceGrammarRuntimeOptions(run_id="grammar-trace"), fixture=self.fixture
        )
        policy = evaluate_sequence_grammar_policy(self.fixture, self.evaluation)
        view = build_sequence_grammar_view(self.fixture, self.evaluation, policy)
        self.assertTrue(build_sequence_grammar_trace(runtime, view).accepted)
        self.assertTrue(audit_sequence_grammar_accessibility(self.fixture, view).accepted)
        self.assertTrue(audit_sequence_grammar_boundary(self.fixture, runtime).accepted)
        self.assertEqual(len(default_sequence_grammar_invariants()), 10)
        self.assertTrue(run_sequence_grammar_invariants(self.fixture, self.evaluation).accepted)

    def test_scenarios_thresholds_validation_and_runbook(self) -> None:
        scenarios = evaluate_sequence_grammar_scenarios(self.fixture, self.evaluation)
        self.assertTrue(scenarios.accepted)
        self.assertEqual(len(default_sequence_grammar_scenarios()), 12)
        self.assertTrue(build_sequence_grammar_threshold_report().accepted)
        self.assertEqual(len(default_sequence_grammar_threshold_profiles()), 6)
        self.assertTrue(
            build_sequence_grammar_validation_matrix(self.fixture, self.evaluation).accepted
        )
        self.assertEqual(len(default_sequence_grammar_runbook().steps), 8)

    def test_exports_are_stable_and_sanitized(self) -> None:
        policy = evaluate_sequence_grammar_policy(self.fixture, self.evaluation)
        view = build_sequence_grammar_view(self.fixture, self.evaluation, policy)
        metrics = compute_sequence_grammar_metrics(self.evaluation)
        receipts = export_sequence_grammar_receipts_csv(self.evaluation)
        review = export_sequence_grammar_review_csv(view)
        metric_csv = export_sequence_grammar_metrics_csv(metrics)
        markdown = render_sequence_grammar_review_markdown(view)
        release_markdown = render_sequence_grammar_release_markdown(
            self.fixture, run_sequence_grammar_quality_gate(self.fixture)
        )
        self.assertEqual(len(receipts.splitlines()), 17)
        self.assertEqual(len(review.splitlines()), 17)
        self.assertEqual(len(metric_csv.splitlines()), 5)
        self.assertIn("C08-CTRL-001", markdown)
        self.assertIn("public_aggregate_non_patient", release_markdown)
        self.assertNotIn("TTTGATATTT", receipts)
        self.assertTrue(
            sequence_grammar_export_receipt("review.csv", review)["content_address"].startswith(
                "sha256:"
            )
        )

    def test_root_pipeline_accepts_all_surfaces(self) -> None:
        pipeline = run_sequence_grammar_frontier_pipeline(self.fixture, run_id="grammar-root")
        self.assertTrue(pipeline.accepted)
        self.assertEqual(len(pipeline.addresses()), 19)
        self.assertTrue(all(address.startswith("sha256:") for address in pipeline.addresses()))
        self.assertEqual(pipeline.queue.next_item().entry.role, SequenceGrammarRole.CONTROL)


if __name__ == "__main__":
    unittest.main()
