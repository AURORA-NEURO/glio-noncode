from __future__ import annotations

import unittest

from glio_noncode.workspace_gamma_frontier_accessibility import (
    evaluate_gamma_frontier_accessibility,
)
from glio_noncode.workspace_gamma_frontier_adapters import (
    GammaFrontierAdapterKind,
    adapt_gamma_frontier_input,
    default_gamma_frontier_adapters,
)
from glio_noncode.workspace_gamma_frontier_artifacts import (
    GammaFrontierArtifactKind,
    build_gamma_frontier_artifact_inventory,
)
from glio_noncode.workspace_gamma_frontier_bundle import assemble_gamma_frontier_bundle
from glio_noncode.workspace_gamma_frontier_checks import (
    gamma_frontier_observation_map,
    run_gamma_frontier_invariants,
)
from glio_noncode.workspace_gamma_frontier_compliance import evaluate_gamma_frontier_boundary
from glio_noncode.workspace_gamma_frontier_contracts import default_gamma_frontier_contracts
from glio_noncode.workspace_gamma_frontier_exports import (
    export_gamma_frontier_canonical,
    export_gamma_frontier_json,
    export_gamma_frontier_manifest,
    export_gamma_frontier_review_csv,
)
from glio_noncode.workspace_gamma_frontier_fixture_eval import (
    evaluate_gamma_frontier_fixture,
)
from glio_noncode.workspace_gamma_frontier_lineage import build_gamma_frontier_lineage
from glio_noncode.workspace_gamma_frontier_metrics import measure_gamma_frontier
from glio_noncode.workspace_gamma_frontier_observability import observe_gamma_frontier
from glio_noncode.workspace_gamma_frontier_pipeline import run_gamma_frontier_pipeline
from glio_noncode.workspace_gamma_frontier_policy import (
    GammaFrontierDecision,
    default_gamma_frontier_policy,
)
from glio_noncode.workspace_gamma_frontier_projection_assertions import (
    audit_gamma_frontier_projections,
)
from glio_noncode.workspace_gamma_frontier_public_data import (
    GAMMA_FRONTIER_CONTEXT_KEY,
    GammaFrontierOperation,
    audit_gamma_frontier_data,
    build_gamma_frontier_catalog,
    default_gamma_frontier_fixture,
)
from glio_noncode.workspace_gamma_frontier_quality_gate import evaluate_gamma_frontier_quality
from glio_noncode.workspace_gamma_frontier_reconciliation import reconcile_gamma_frontier
from glio_noncode.workspace_gamma_frontier_release import (
    GammaFrontierReleaseState,
    build_gamma_frontier_release_manifest,
)
from glio_noncode.workspace_gamma_frontier_replay import (
    compare_gamma_frontier_replays,
    gamma_frontier_replay_is_deterministic,
    replay_gamma_frontier,
)
from glio_noncode.workspace_gamma_frontier_review_queue import build_gamma_frontier_review_queue
from glio_noncode.workspace_gamma_frontier_runbook import default_gamma_frontier_runbook
from glio_noncode.workspace_gamma_frontier_runtime import run_gamma_frontier_runtime
from glio_noncode.workspace_gamma_frontier_scenario_matrix import (
    build_gamma_frontier_scenario_matrix,
)
from glio_noncode.workspace_gamma_frontier_schema import default_gamma_frontier_schema
from glio_noncode.workspace_gamma_frontier_thresholds import build_gamma_frontier_threshold_report
from glio_noncode.workspace_gamma_frontier_validation_matrix import (
    build_gamma_frontier_validation_matrix,
    validate_gamma_frontier_matrix,
)
from glio_noncode.workspace_gamma_frontier_views import build_gamma_frontier_review_view


class WorkspaceGammaFrontierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_gamma_frontier_fixture()
        cls.evaluation = evaluate_gamma_frontier_fixture(cls.fixture)
        cls.runtime = run_gamma_frontier_runtime(cls.fixture, run_id="test-gamma-runtime")
        cls.replay = replay_gamma_frontier(cls.fixture, replay_id="test-gamma-replay")
        cls.release = build_gamma_frontier_release_manifest(
            cls.runtime, cls.replay, release_id="test-gamma-release"
        )
        cls.view = build_gamma_frontier_review_view(
            cls.fixture, cls.evaluation, cls.runtime.policy_decisions, cls.release
        )

    def test_public_fixture_has_four_positive_paths_and_twelve_controls(self) -> None:
        self.assertEqual(len(self.fixture.sources), 5)
        self.assertEqual(len(self.fixture.records), 16)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)
        self.assertEqual(self.fixture.context_key, GAMMA_FRONTIER_CONTEXT_KEY)
        self.assertTrue(audit_gamma_frontier_data(self.fixture).accepted)

    def test_all_surface_records_execute_against_expected_states(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(self.evaluation.passed_checks, 48)
        self.assertEqual(self.evaluation.failed_check_ids, ())
        self.assertEqual(
            {item.operation for item in self.evaluation.executions}, set(GammaFrontierOperation)
        )
        self.assertEqual(
            self.evaluation.execution_map()["gamma-snapshot-tampered"].state, "blocked"
        )
        self.assertEqual(
            self.evaluation.execution_map()["gamma-collab-unknown"].issue_codes, ("unknown_member",)
        )

    def test_board_launch_snapshot_and_access_controls_preserve_declared_boundaries(self) -> None:
        board = self.evaluation.execution_map()["gamma-board-positive"].output
        self.assertEqual(len(board["columns"]), 6)
        self.assertEqual(board["dependency_edges"], (("exp-board-01", "exp-board-02"),))
        launch = self.evaluation.execution_map()["gamma-launch-positive"].output
        self.assertEqual(launch["network_policies"], ("network_disabled",))
        snapshot = self.evaluation.execution_map()["gamma-snapshot-positive"].output
        self.assertTrue(snapshot["signature_valid"])
        access = self.evaluation.execution_map()["gamma-collab-positive"].output
        self.assertTrue(access["decisions"][0]["allowed"])

    def test_contract_schema_catalog_and_adapters_cover_every_surface(self) -> None:
        contracts = default_gamma_frontier_contracts()
        schema = default_gamma_frontier_schema()
        catalog = build_gamma_frontier_catalog(self.fixture)
        adapters = default_gamma_frontier_adapters()
        self.assertEqual(len(contracts.contracts), 4)
        self.assertEqual(len(schema.operations), 4)
        self.assertEqual(len(catalog.operations), 4)
        self.assertEqual(len(adapters.adapters), 12)
        receipt = adapt_gamma_frontier_input(
            GammaFrontierOperation.EXPERIMENT_BOARD, {"cards": []}, GammaFrontierAdapterKind.MAPPING
        )
        self.assertTrue(receipt.accepted)
        self.assertEqual(len(adapters.by_operation(GammaFrontierOperation.LAUNCH_PLAN)), 3)

    def test_lineage_metrics_policy_and_reconciliation_are_complete(self) -> None:
        lineage = build_gamma_frontier_lineage(self.fixture, self.evaluation)
        metrics = measure_gamma_frontier(self.evaluation)
        policy = default_gamma_frontier_policy()
        decisions = policy.decide(self.evaluation)
        reconciliation = reconcile_gamma_frontier(self.fixture, self.evaluation, decisions)
        self.assertGreaterEqual(len(lineage.edges), 32)
        self.assertEqual(len(metrics.metrics), 17)
        self.assertTrue(reconciliation.accepted)
        self.assertEqual(
            sum(item.decision is GammaFrontierDecision.RELEASE for item in decisions), 2
        )
        self.assertTrue(lineage.parents_of(self.evaluation.executions[0].content_address))

    def test_runtime_quality_and_projection_audits_accept(self) -> None:
        projection = audit_gamma_frontier_projections(self.evaluation)
        quality = evaluate_gamma_frontier_quality(
            self.fixture,
            self.evaluation,
            self.runtime.data_audit,
            default_gamma_frontier_contracts(),
            default_gamma_frontier_schema(),
            self.runtime.lineage,
            self.runtime.reconciliation,
            projection,
        )
        self.assertTrue(projection.accepted)
        self.assertTrue(quality.accepted)
        self.assertTrue(self.runtime.accepted)
        self.assertEqual(len(self.runtime.stages), 8)
        self.assertEqual(self.runtime.quality.passed_count, 10)

    def test_replay_is_deterministic_even_for_signed_snapshot_records(self) -> None:
        second = replay_gamma_frontier(self.fixture, replay_id="test-gamma-replay-second")
        comparison = compare_gamma_frontier_replays(self.replay, second)
        self.assertTrue(comparison.accepted)
        self.assertTrue(gamma_frontier_replay_is_deterministic(self.fixture))

    def test_release_bundle_artifacts_view_and_queue_are_addressed(self) -> None:
        bundle = assemble_gamma_frontier_bundle(
            self.fixture, self.runtime, self.release, bundle_id="test-gamma-bundle"
        )
        inventory = build_gamma_frontier_artifact_inventory(self.runtime, bundle, self.release)
        queue = build_gamma_frontier_review_queue(
            self.view, self.release, queue_id="test-gamma-queue"
        )
        self.assertTrue(bundle.accepted)
        self.assertTrue(inventory.accepted)
        self.assertIsNotNone(inventory.by_kind(GammaFrontierArtifactKind.RUNTIME))
        self.assertTrue(queue.accepted)
        self.assertEqual(len(self.view.rows), 16)
        self.assertEqual(self.view.summary["control_count"], 12)

    def test_boundary_accessibility_invariants_and_observation_map_accept(self) -> None:
        self.assertTrue(
            evaluate_gamma_frontier_accessibility(self.fixture, self.evaluation).accepted
        )
        self.assertTrue(evaluate_gamma_frontier_boundary(self.fixture, self.evaluation).accepted)
        self.assertTrue(run_gamma_frontier_invariants(self.fixture, self.evaluation).accepted)
        observations = gamma_frontier_observation_map(self.evaluation)
        self.assertEqual(len(observations), 16)
        self.assertEqual(observations["gamma-launch-resource"]["state"], "abstained")

    def test_scenarios_thresholds_validation_runbook_and_observability_are_populated(self) -> None:
        scenarios = build_gamma_frontier_scenario_matrix()
        thresholds = build_gamma_frontier_threshold_report()
        validation = build_gamma_frontier_validation_matrix()
        runbook = default_gamma_frontier_runbook()
        trace = observe_gamma_frontier(self.runtime)
        self.assertEqual(len(scenarios.scenarios), 20)
        self.assertTrue(thresholds.accepted)
        self.assertTrue(validate_gamma_frontier_matrix(validation))
        self.assertEqual(len(runbook.steps), 14)
        self.assertEqual(len(trace.events), 24)

    def test_end_to_end_pipeline_exercises_all_report_families(self) -> None:
        report = run_gamma_frontier_pipeline(self.fixture, pipeline_id="test-gamma-pipeline")
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.addresses()), 16)
        self.assertEqual(report.release.state, GammaFrontierReleaseState.READY)
        self.assertEqual(report.manifest["research_boundary"], "public_aggregate_non_patient")

    def test_exports_are_canonical_and_do_not_expose_secret_fields(self) -> None:
        bundle = assemble_gamma_frontier_bundle(
            self.fixture, self.runtime, self.release, bundle_id="test-export-bundle"
        )
        manifest = export_gamma_frontier_manifest(self.runtime.metrics, bundle, self.release)
        canonical = export_gamma_frontier_canonical(self.view)
        rendered = export_gamma_frontier_json(self.view)
        csv_text = export_gamma_frontier_review_csv(self.view)
        self.assertEqual(manifest["entry_count"], 10)
        self.assertIn("rows", canonical)
        self.assertIn("review-row-001", rendered)
        self.assertIn("row_id,record_id", csv_text)
        self.assertNotIn("signing_secret", rendered)

    def test_public_pipeline_is_safe_to_call_from_root_package(self) -> None:
        import glio_noncode

        self.assertTrue(
            glio_noncode.run_gamma_frontier_pipeline(
                self.fixture, pipeline_id="root-gamma"
            ).accepted
        )
        self.assertEqual(
            glio_noncode.GammaFrontierOperation.EXPERIMENT_BOARD,
            GammaFrontierOperation.EXPERIMENT_BOARD,
        )


if __name__ == "__main__":
    unittest.main()
