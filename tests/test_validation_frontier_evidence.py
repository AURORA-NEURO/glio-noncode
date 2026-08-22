"""Deep evidence tests for the Domain 13 planning frontier."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.validation_frontier_artifacts import (
    ValidationFrontierArtifactKind,
    build_validation_frontier_artifact_inventory,
)
from glio_noncode.validation_frontier_checks import (
    default_validation_frontier_invariants,
    run_validation_frontier_invariants,
    validation_frontier_observation_map,
)
from glio_noncode.validation_frontier_contracts import default_validation_frontier_contracts
from glio_noncode.validation_frontier_exports import (
    export_validation_frontier_canonical,
    export_validation_frontier_json,
    export_validation_frontier_manifest,
    export_validation_frontier_review_csv,
)
from glio_noncode.validation_frontier_fixture_eval import (
    evaluate_validation_frontier_fixture,
    execute_validation_frontier_record,
)
from glio_noncode.validation_frontier_lineage import build_validation_frontier_lineage
from glio_noncode.validation_frontier_metrics import measure_validation_frontier
from glio_noncode.validation_frontier_observability import observe_validation_frontier
from glio_noncode.validation_frontier_policy import (
    ValidationFrontierDecision,
    default_validation_frontier_policy,
)
from glio_noncode.validation_frontier_public_data import (
    ValidationFrontierOperation,
    ValidationFrontierRole,
    audit_validation_frontier_data,
    build_validation_frontier_catalog,
    default_validation_frontier_fixture,
    load_validation_frontier_fixture,
)
from glio_noncode.validation_frontier_quality_gate import evaluate_validation_frontier_quality
from glio_noncode.validation_frontier_reconciliation import reconcile_validation_frontier
from glio_noncode.validation_frontier_release import (
    ValidationFrontierReleaseState,
    build_validation_frontier_release_manifest,
)
from glio_noncode.validation_frontier_replay import (
    compare_validation_frontier_replays,
    replay_validation_frontier,
    validation_frontier_replay_is_deterministic,
)
from glio_noncode.validation_frontier_runtime import run_validation_frontier_runtime
from glio_noncode.validation_frontier_scenario_matrix import (
    build_validation_frontier_scenario_matrix,
)
from glio_noncode.validation_frontier_schema import default_validation_frontier_schema
from glio_noncode.validation_frontier_thresholds import (
    build_validation_frontier_threshold_report,
    default_validation_frontier_threshold_profiles,
)
from glio_noncode.validation_frontier_views import build_validation_frontier_review_view


class ValidationFrontierEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_validation_frontier_fixture()
        self.contracts = default_validation_frontier_contracts()
        self.schema = default_validation_frontier_schema()
        self.evaluation = evaluate_validation_frontier_fixture(self.fixture)
        self.policy = default_validation_frontier_policy(self.contracts)
        self.lineage = build_validation_frontier_lineage(self.fixture, self.evaluation)
        self.reconciliation = reconcile_validation_frontier(self.fixture, self.evaluation, self.policy)
        self.metrics = measure_validation_frontier(self.evaluation)
        self.quality = evaluate_validation_frontier_quality(self.fixture, self.evaluation, self.contracts, self.schema, self.lineage, self.reconciliation)
        self.runtime = run_validation_frontier_runtime(self.fixture, run_id="validation-test-runtime")
        self.replay = replay_validation_frontier(self.fixture, replay_id="validation-test-replay")
        self.release = build_validation_frontier_release_manifest(self.runtime.bundle, self.quality, self.replay)

    def test_fixture_boundary_and_catalog(self) -> None:
        audit = audit_validation_frontier_data(self.fixture)
        catalog = build_validation_frontier_catalog(self.fixture)
        self.assertTrue(audit.accepted)
        self.assertEqual(len(audit.checks), 12)
        self.assertEqual(len(self.fixture.sources), 5)
        self.assertEqual(len(self.fixture.records), 16)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)
        self.assertEqual(len(catalog.record_ids), 16)
        self.assertEqual(set(catalog.operations), set(ValidationFrontierOperation))

    def test_evaluation_has_120_checks(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.checks), 120)
        self.assertEqual(self.evaluation.passed_checks, 120)
        self.assertEqual(self.evaluation.failed_check_ids, ())

    def test_positive_paths_are_accepted(self) -> None:
        positives = tuple(item for item in self.evaluation.executions if item.role is ValidationFrontierRole.POSITIVE)
        self.assertEqual(len(positives), 4)
        self.assertTrue(all(item.accepted for item in positives))
        self.assertEqual({item.state for item in positives}, {"partial", "ready_for_review"})

    def test_controls_retain_distinct_blockers(self) -> None:
        controls = tuple(item for item in self.evaluation.executions if item.role is ValidationFrontierRole.CONTROL)
        self.assertEqual(len(controls), 12)
        self.assertTrue(all(not item.accepted for item in controls))
        self.assertEqual(self.evaluation.execution_map()["C01-CTRL-001"].issue_codes, ("context_mismatch",))
        self.assertEqual(self.evaluation.execution_map()["C01-CTRL-002"].issue_codes, ("invalid_evidence_gap_input",))
        self.assertEqual(self.evaluation.execution_map()["C02-CTRL-002"].issue_codes, ("missing_controls", "missing_readouts"))
        self.assertEqual(self.evaluation.execution_map()["C03-CTRL-002"].issue_codes, ("max_constructs_exceeded",))
        self.assertEqual(self.evaluation.execution_map()["C04-CTRL-002"].issue_codes, ("insert_length",))

    def test_gap_analysis_retains_missing_evidence_and_uncertainty(self) -> None:
        output = self.evaluation.execution_map()["C01-POS-001"].output
        self.assertEqual(output["state"], "partial")
        self.assertEqual(len(output["gaps"]), 2)
        self.assertIn("h-gap:missing:1", output["priority_order"])
        self.assertIn("h-gap:uncertainty", output["priority_order"])

    def test_assay_route_retains_satisfied_constraints(self) -> None:
        output = self.evaluation.execution_map()["C02-POS-001"].output
        route = output["routes"][0]
        self.assertEqual(route["state"], "ready_for_review")
        self.assertEqual(route["model_system"], "neural_model")
        self.assertEqual(set(route["satisfied_constraints"]), {"model_system", "insert_length_range", "controls", "readouts"})
        self.assertTrue(route["sensitivity"])

    def test_reporter_packages_retain_allele_pairs(self) -> None:
        for record_id in ("C03-POS-001", "C04-POS-001"):
            output = self.evaluation.execution_map()[record_id].output
            self.assertEqual(output["state"], "ready_for_review")
            self.assertEqual(len(output["constructs"]), 2)
            self.assertEqual({item["allele"] for item in output["constructs"]}, {"reference", "alternate"})
            self.assertEqual(output["controls"], ["negative_control", "positive_control"])

    def test_contracts_and_schema_cover_four_operations(self) -> None:
        self.assertEqual(len(self.contracts.contracts), 4)
        self.assertEqual(len(self.schema.operations), 4)
        self.assertEqual({item.operation for item in self.contracts.contracts}, set(ValidationFrontierOperation))
        self.assertEqual({item.operation for item in self.schema.operations}, set(ValidationFrontierOperation))
        self.assertGreaterEqual(len(self.contracts.issue_codes()), 12)

    def test_policy_allows_positive_planning_paths(self) -> None:
        decisions = self.policy.decide(self.evaluation)
        self.assertEqual(len(decisions), 4)
        self.assertTrue(all(item.publishable for item in decisions))
        self.assertEqual(next(item for item in decisions if item.operation is ValidationFrontierOperation.ASSAY_ELIGIBILITY).decision, ValidationFrontierDecision.ALLOW_ROUTE_REVIEW)
        self.assertTrue(all(item.issue_codes == () for item in decisions))

    def test_lineage_and_reconciliation_are_complete(self) -> None:
        self.assertTrue(self.lineage.acyclic)
        self.assertEqual(len(self.lineage.edges), 36)
        self.assertEqual(len(self.lineage.terminal_addresses), 16)
        self.assertTrue(self.reconciliation.reconciled)
        self.assertEqual(self.reconciliation.mismatched_record_ids, ())
        self.assertEqual(len(self.reconciliation.items), 16)

    def test_metrics_quality_runtime_and_release(self) -> None:
        self.assertEqual(len(self.metrics.metrics), 13)
        self.assertEqual(self.metrics.by_id("positive_acceptance_rate").value, 1.0)
        self.assertEqual(self.metrics.by_id("control_rejection_rate").value, 1.0)
        self.assertTrue(self.quality.accepted)
        self.assertEqual(len(self.quality.checks), 12)
        self.assertEqual(self.quality.passed_count, 12)
        self.assertTrue(self.runtime.accepted)
        self.assertEqual(len(self.runtime.stages), 10)
        self.assertEqual(tuple(item.sequence for item in self.runtime.stages), tuple(range(1, 11)))
        self.assertEqual(self.release.state, ValidationFrontierReleaseState.READY)
        self.assertTrue(self.release.accepted)
        self.assertTrue(self.release.allowed_uses)
        self.assertTrue(self.release.excluded_uses)

    def test_replay_thresholds_and_scenarios(self) -> None:
        second = replay_validation_frontier(self.fixture, replay_id="validation-test-replay-2")
        comparison = compare_validation_frontier_replays(self.replay, second)
        self.assertTrue(comparison.accepted)
        self.assertEqual(comparison.drift_fields, ())
        self.assertTrue(validation_frontier_replay_is_deterministic(self.fixture))
        matrix = build_validation_frontier_scenario_matrix()
        self.assertEqual(len(matrix.scenarios), 31)
        self.assertEqual(len(matrix.dimensions), 6)
        self.assertTrue(matrix.review_scenarios)
        report = build_validation_frontier_threshold_report()
        self.assertEqual(len(default_validation_frontier_threshold_profiles()), 4)
        self.assertEqual(len(report.probes), 972)
        self.assertEqual(len(report.accepted_probe_ids) + len(report.review_probe_ids), 972)

    def test_artifacts_invariants_and_observability(self) -> None:
        inventory = build_validation_frontier_artifact_inventory(self.fixture, self.evaluation, self.metrics, self.lineage, self.quality, self.runtime, self.release)
        self.assertEqual(len(inventory.artifacts), 7)
        self.assertEqual(inventory.root_artifact_id, "validation-artifact-release")
        self.assertEqual(len(inventory.by_kind(ValidationFrontierArtifactKind.RELEASE)), 1)
        observations = validation_frontier_observation_map(context_preserved=True, positive_control_separated=True, source_receipts=True, gap_visible=True, route_blockers=True, construct_pairs=True, limitations_retained=True, content_addressed=True, replay_stable=True, use_boundary=True)
        invariant = run_validation_frontier_invariants(observations)
        self.assertTrue(invariant.accepted)
        self.assertEqual(len(default_validation_frontier_invariants()), 10)
        self.assertEqual(len(observe_validation_frontier(self.runtime, self.evaluation).events), 26)

    def test_review_view_and_exports_keep_controls(self) -> None:
        view = build_validation_frontier_review_view(self.fixture, self.evaluation, self.metrics, self.policy.decide(self.evaluation), self.release)
        self.assertEqual(len(view.rows), 16)
        self.assertEqual(len(view.accepted_rows()), 4)
        self.assertEqual(len(view.issue_rows()), 12)
        csv_text = export_validation_frontier_review_csv(view)
        self.assertEqual(len(csv_text.splitlines()), 17)
        self.assertIn("C02-CTRL-002", csv_text)
        self.assertTrue(export_validation_frontier_json(self.release).endswith("\n"))
        self.assertTrue(export_validation_frontier_canonical(self.release).startswith("{"))
        self.assertEqual(export_validation_frontier_manifest(self.runtime.bundle, self.release)["public_boundary"], "public_aggregate_non_patient")

    def test_fixture_json_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "validation.json"
            path.write_text(json.dumps(self.fixture.to_dict()), encoding="utf-8")
            loaded = load_validation_frontier_fixture(path)
        self.assertEqual(loaded.fixture_id, self.fixture.fixture_id)
        self.assertEqual(len(loaded.records), 16)

    def test_single_execution_address_is_stable(self) -> None:
        record = self.fixture.record_map()["C03-POS-001"]
        first = execute_validation_frontier_record(record)
        second = execute_validation_frontier_record(record)
        self.assertEqual(first.content_address, second.content_address)
        self.assertTrue(first.accepted)


if __name__ == "__main__":
    unittest.main()
