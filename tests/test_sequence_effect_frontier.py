from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from glio_noncode.sequence_effect_frontier_accessibility import audit_sequence_effect_accessibility
from glio_noncode.sequence_effect_frontier_adapters import build_sequence_effect_adapters
from glio_noncode.sequence_effect_frontier_artifacts import build_sequence_effect_artifacts
from glio_noncode.sequence_effect_frontier_bundle import build_sequence_effect_bundle
from glio_noncode.sequence_effect_frontier_checks import (
    default_sequence_effect_invariants,
    run_sequence_effect_invariants,
)
from glio_noncode.sequence_effect_frontier_compliance import audit_sequence_effect_boundary
from glio_noncode.sequence_effect_frontier_contracts import default_sequence_effect_contracts
from glio_noncode.sequence_effect_frontier_exports import (
    export_sequence_effect_metrics_csv,
    export_sequence_effect_receipts_csv,
    export_sequence_effect_review_csv,
    render_sequence_effect_release_markdown,
    render_sequence_effect_review_markdown,
    sequence_effect_export_receipt,
)
from glio_noncode.sequence_effect_frontier_fixture_eval import evaluate_sequence_effect_fixture
from glio_noncode.sequence_effect_frontier_lineage import (
    build_sequence_effect_lineage,
    verify_sequence_effect_lineage,
)
from glio_noncode.sequence_effect_frontier_metrics import compute_sequence_effect_metrics
from glio_noncode.sequence_effect_frontier_observability import (
    build_sequence_effect_trace,
    compare_sequence_effect_runs,
    sequence_effect_review_budget,
)
from glio_noncode.sequence_effect_frontier_pipeline import run_sequence_effect_frontier_pipeline
from glio_noncode.sequence_effect_frontier_policy import (
    SequenceEffectDecision,
    evaluate_sequence_effect_policy,
)
from glio_noncode.sequence_effect_frontier_public_data import (
    SEQUENCE_EFFECT_CONTEXT_KEY,
    SequenceEffectOperation,
    SequenceEffectRole,
    SequenceEffectState,
    audit_sequence_effect_data,
    build_sequence_effect_catalog,
    default_sequence_effect_fixture,
    load_sequence_effect_fixture,
)
from glio_noncode.sequence_effect_frontier_quality_gate import run_sequence_effect_quality_gate
from glio_noncode.sequence_effect_frontier_reconciliation import reconcile_sequence_effect
from glio_noncode.sequence_effect_frontier_release import build_sequence_effect_release
from glio_noncode.sequence_effect_frontier_replay import replay_sequence_effect_evaluation
from glio_noncode.sequence_effect_frontier_review_queue import build_sequence_effect_review_queue
from glio_noncode.sequence_effect_frontier_runbook import default_sequence_effect_runbook
from glio_noncode.sequence_effect_frontier_runtime import (
    SequenceEffectRuntimeOptions,
    run_sequence_effect_pipeline,
)
from glio_noncode.sequence_effect_frontier_scenario_matrix import (
    default_sequence_effect_scenarios,
    evaluate_sequence_effect_scenarios,
)
from glio_noncode.sequence_effect_frontier_schema import (
    default_sequence_effect_schemas,
    sequence_effect_schema_manifest,
    validate_sequence_effect_schema,
)
from glio_noncode.sequence_effect_frontier_thresholds import (
    build_sequence_effect_threshold_report,
    default_sequence_effect_threshold_profiles,
)
from glio_noncode.sequence_effect_frontier_validation_matrix import (
    build_sequence_effect_validation_matrix,
)
from glio_noncode.sequence_effect_frontier_views import (
    build_sequence_effect_view,
    filter_sequence_effect_review_queue,
    sequence_effect_review_summary,
)


class SequenceEffectFrontierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_sequence_effect_fixture()
        self.evaluation = evaluate_sequence_effect_fixture(self.fixture)

    def test_public_fixture_is_balanced_and_closed(self) -> None:
        self.assertEqual(self.fixture.context_key, SEQUENCE_EFFECT_CONTEXT_KEY)
        self.assertEqual(
            (len(self.fixture.positive_records), len(self.fixture.control_records)), (4, 12)
        )
        self.assertEqual(len(self.fixture.sources), 4)
        self.assertTrue(audit_sequence_effect_data(self.fixture).accepted)
        catalog = build_sequence_effect_catalog(self.fixture)
        self.assertEqual(set(catalog.operations), {item.value for item in SequenceEffectOperation})
        self.assertEqual(len(catalog.record_ids), 16)
        self.assertTrue(catalog.content_address.startswith("sha256:"))

    def test_fixture_round_trip_retains_address(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.json"
            path.write_text(
                json.dumps(self.fixture.to_dict(include_payload=True)), encoding="utf-8"
            )
            loaded = load_sequence_effect_fixture(path)
        self.assertEqual(loaded.content_address, self.fixture.content_address)
        self.assertEqual(
            evaluate_sequence_effect_fixture(loaded).content_address,
            self.evaluation.content_address,
        )

    def test_evaluation_has_six_checks_per_execution(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual((len(self.evaluation.executions), len(self.evaluation.checks)), (16, 96))
        self.assertEqual((self.evaluation.positive_count, self.evaluation.control_count), (4, 12))
        states = {item.record_id: item.adapter_state for item in self.evaluation.executions}
        self.assertEqual(states["C01-POS-001"], SequenceEffectState.SUPPORTED)
        self.assertEqual(states["C01-CTRL-002"], SequenceEffectState.ABSTAINED)
        self.assertEqual(states["C02-CTRL-002"], SequenceEffectState.INVALID)
        self.assertEqual(states["C03-CTRL-001"], SequenceEffectState.INVALID)
        self.assertEqual(states["C04-CTRL-002"], SequenceEffectState.AMBIGUOUS)

    def test_controls_retain_distinct_issue_paths(self) -> None:
        by_id = self.evaluation.execution_map()
        self.assertIn("invalid_alphabet", by_id["C01-CTRL-001"].issue_codes)
        self.assertIn("empty_sequence", by_id["C01-CTRL-002"].issue_codes)
        self.assertIn("missing_model_id", by_id["C02-CTRL-002"].issue_codes)
        self.assertIn("delta_mismatch", by_id["C02-CTRL-003"].issue_codes)
        self.assertIn("context_too_short", by_id["C03-CTRL-001"].issue_codes)
        self.assertIn("single_model", by_id["C04-CTRL-001"].issue_codes)
        self.assertIn("model_disagreement", by_id["C04-CTRL-002"].issue_codes)

    def test_mutated_expected_state_fails_evaluation(self) -> None:
        altered = replace(self.fixture.records[0], expected_state=SequenceEffectState.PARTIAL)
        altered_fixture = replace(self.fixture, records=(altered, *self.fixture.records[1:]))
        result = evaluate_sequence_effect_fixture(altered_fixture)
        self.assertFalse(result.accepted)
        self.assertIn("C01-POS-001:state", result.failed_check_ids)

    def test_contracts_and_schema_cover_operations(self) -> None:
        contracts = default_sequence_effect_contracts()
        schemas = default_sequence_effect_schemas()
        report = validate_sequence_effect_schema(self.fixture, self.evaluation, contracts)
        self.assertEqual(len(contracts.contracts), 4)
        self.assertEqual(len(schemas), 4)
        self.assertEqual(
            set(item.operation for item in contracts.contracts), set(SequenceEffectOperation)
        )
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 8)
        self.assertEqual(
            {item["operation"] for item in sequence_effect_schema_manifest()["schemas"]},
            {item.value for item in SequenceEffectOperation},
        )

    def test_metrics_are_conserved_and_addressed(self) -> None:
        metrics = compute_sequence_effect_metrics(self.evaluation)
        self.assertEqual(
            (metrics.total_records, metrics.positive_records, metrics.control_records), (16, 4, 12)
        )
        self.assertEqual(metrics.accepted_records, 16)
        self.assertEqual(metrics.review_records, 12)
        self.assertEqual(len(metrics.operation_metrics), 4)
        self.assertTrue(
            all(item.content_address.startswith("sha256:") for item in metrics.operation_metrics)
        )

    def test_lineage_has_source_fixture_and_execution_layers(self) -> None:
        lineage = build_sequence_effect_lineage(self.fixture, self.evaluation)
        self.assertTrue(lineage.accepted)
        self.assertTrue(verify_sequence_effect_lineage(lineage, self.fixture, self.evaluation))
        self.assertEqual(sum(node.node_kind == "source" for node in lineage.nodes), 4)
        self.assertEqual(sum(node.node_kind == "execution" for node in lineage.nodes), 16)
        self.assertGreater(len(lineage.edges), len(self.evaluation.executions))

    def test_policy_withholds_controls_and_allows_positive_rows(self) -> None:
        policy = evaluate_sequence_effect_policy(self.fixture, self.evaluation)
        self.assertTrue(policy.accepted)
        self.assertEqual(len(policy.decisions), 16)
        self.assertEqual(
            sum(
                item.decision is SequenceEffectDecision.ALLOW_RESEARCH for item in policy.decisions
            ),
            4,
        )
        self.assertTrue(
            all(not item.publishable for item in policy.decisions if "CTRL" in item.record_id)
        )

    def test_reconciliation_is_exact(self) -> None:
        policy = evaluate_sequence_effect_policy(self.fixture, self.evaluation)
        reconciliation = reconcile_sequence_effect(self.fixture, self.evaluation, policy)
        self.assertTrue(reconciliation.accepted)
        self.assertEqual(reconciliation.failed_record_ids, ())
        self.assertEqual(len(reconciliation.items), 16)

    def test_quality_gate_has_twenty_five_checks(self) -> None:
        quality = run_sequence_effect_quality_gate(self.fixture)
        self.assertTrue(quality.accepted)
        self.assertEqual(len(quality.checks), 25)
        self.assertEqual(quality.failed_check_ids, ())

    def test_replay_is_deterministic(self) -> None:
        replay = replay_sequence_effect_evaluation(self.evaluation, self.fixture)
        self.assertTrue(replay.accepted)
        self.assertEqual(len(replay.checks), 8)
        second = run_sequence_effect_pipeline(
            SequenceEffectRuntimeOptions(run_id="sequence-effect-second"), fixture=self.fixture
        )
        first = run_sequence_effect_pipeline(
            SequenceEffectRuntimeOptions(run_id="sequence-effect-first"), fixture=self.fixture
        )
        self.assertFalse(compare_sequence_effect_runs(first, second).equivalent)

    def test_runtime_orders_ten_stages_and_supports_strict_mode(self) -> None:
        runtime = run_sequence_effect_pipeline(
            SequenceEffectRuntimeOptions(run_id="sequence-effect-runtime"), fixture=self.fixture
        )
        self.assertTrue(runtime.accepted)
        self.assertEqual(tuple(item.ordinal for item in runtime.stages), tuple(range(1, 11)))
        strict = run_sequence_effect_pipeline(
            SequenceEffectRuntimeOptions(run_id="sequence-effect-strict", fail_on_review=True),
            fixture=self.fixture,
        )
        self.assertFalse(strict.accepted)
        self.assertEqual(strict.status, "rejected")

    def test_release_bundle_and_artifacts_are_closed(self) -> None:
        quality = run_sequence_effect_quality_gate(self.fixture)
        runtime = run_sequence_effect_pipeline(
            SequenceEffectRuntimeOptions(run_id="sequence-effect-release"), fixture=self.fixture
        )
        release = build_sequence_effect_release(quality, runtime)
        bundle = build_sequence_effect_bundle(self.fixture, self.evaluation, release)
        artifacts = build_sequence_effect_artifacts(quality, release, bundle)
        self.assertTrue(release.accepted)
        self.assertTrue(bundle.accepted)
        self.assertTrue(artifacts.accepted)
        self.assertEqual(len(bundle.entries), 16)
        self.assertEqual(len(artifacts.artifacts), 9)
        self.assertEqual(artifacts.root_address, release.content_address)

    def test_review_view_and_queue_retain_all_controls(self) -> None:
        view = build_sequence_effect_view(self.fixture, self.evaluation)
        queue = build_sequence_effect_review_queue(view)
        self.assertTrue(view.accepted)
        self.assertTrue(queue.accepted)
        self.assertEqual((view.review_count, len(queue.items)), (12, 12))
        self.assertEqual(len(filter_sequence_effect_review_queue(view, maximum_priority=3)), 12)
        self.assertEqual(sequence_effect_review_summary(view)["accepted_count"], 4)
        self.assertEqual(sequence_effect_review_budget(view)["eligible_review_count"], 12)

    def test_observability_accessibility_and_boundary_accept(self) -> None:
        view = build_sequence_effect_view(self.fixture, self.evaluation)
        runtime = run_sequence_effect_pipeline(
            SequenceEffectRuntimeOptions(run_id="sequence-effect-trace"), fixture=self.fixture
        )
        trace = build_sequence_effect_trace(runtime, view)
        self.assertTrue(trace.accepted)
        self.assertEqual(len(trace.events), 10)
        self.assertTrue(audit_sequence_effect_accessibility(self.fixture, view).accepted)
        self.assertTrue(audit_sequence_effect_boundary(self.fixture, runtime).accepted)

    def test_invariants_adapters_scenarios_thresholds_validation_and_runbook(self) -> None:
        self.assertEqual(len(default_sequence_effect_invariants()), 10)
        self.assertTrue(run_sequence_effect_invariants(self.fixture, self.evaluation).accepted)
        self.assertTrue(build_sequence_effect_adapters().accepted)
        scenarios = evaluate_sequence_effect_scenarios(self.fixture, self.evaluation)
        self.assertTrue(scenarios.accepted)
        self.assertEqual(len(default_sequence_effect_scenarios()), 12)
        thresholds = build_sequence_effect_threshold_report()
        self.assertTrue(thresholds.accepted)
        self.assertEqual(len(default_sequence_effect_threshold_profiles()), 6)
        validation = build_sequence_effect_validation_matrix(self.fixture, self.evaluation)
        self.assertTrue(validation.accepted)
        self.assertEqual(len(validation.rows), 4)
        self.assertEqual(len(default_sequence_effect_runbook().steps), 8)

    def test_exports_are_stable_and_sanitized(self) -> None:
        view = build_sequence_effect_view(self.fixture, self.evaluation)
        quality = run_sequence_effect_quality_gate(self.fixture)
        receipts = export_sequence_effect_receipts_csv(self.evaluation)
        review = export_sequence_effect_review_csv(view)
        metrics = export_sequence_effect_metrics_csv(
            compute_sequence_effect_metrics(self.evaluation)
        )
        markdown = render_sequence_effect_review_markdown(view)
        release_markdown = render_sequence_effect_release_markdown(self.fixture, quality)
        self.assertEqual(len(receipts.splitlines()), 17)
        self.assertEqual(len(review.splitlines()), 17)
        self.assertEqual(len(metrics.splitlines()), 5)
        self.assertIn("C04-CTRL-002", markdown)
        self.assertIn("public_aggregate_non_patient", release_markdown)
        self.assertNotIn("ACGTACGT", receipts)
        self.assertTrue(
            sequence_effect_export_receipt("review.csv", review)["content_address"].startswith(
                "sha256:"
            )
        )

    def test_root_pipeline_accepts_all_surfaces(self) -> None:
        pipeline = run_sequence_effect_frontier_pipeline(
            self.fixture, run_id="sequence-effect-root"
        )
        self.assertTrue(pipeline.accepted)
        self.assertEqual(len(pipeline.addresses()), 17)
        self.assertTrue(all(address.startswith("sha256:") for address in pipeline.addresses()))
        self.assertEqual(
            pipeline.review_queue.next_item().entry.role, SequenceEffectRole.CONTROL.value
        )
        self.assertEqual(pipeline.fixture.context_key, SEQUENCE_EFFECT_CONTEXT_KEY)


if __name__ == "__main__":
    unittest.main()
