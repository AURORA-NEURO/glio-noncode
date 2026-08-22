"""Deep evidence tests for Domain 12 cohort convergence."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cohort_frontier_artifacts import (
    CohortFrontierArtifactKind,
    build_cohort_frontier_artifact_inventory,
)
from glio_noncode.cohort_frontier_checks import (
    cohort_frontier_observation_map,
    default_cohort_frontier_invariants,
    run_cohort_frontier_invariants,
)
from glio_noncode.cohort_frontier_contracts import default_cohort_frontier_contracts
from glio_noncode.cohort_frontier_exports import (
    export_cohort_frontier_canonical,
    export_cohort_frontier_json,
    export_cohort_frontier_manifest,
    export_cohort_frontier_review_csv,
)
from glio_noncode.cohort_frontier_fixture_eval import (
    evaluate_cohort_frontier_fixture,
    execute_cohort_frontier_record,
)
from glio_noncode.cohort_frontier_lineage import build_cohort_frontier_lineage
from glio_noncode.cohort_frontier_metrics import measure_cohort_frontier
from glio_noncode.cohort_frontier_observability import observe_cohort_frontier
from glio_noncode.cohort_frontier_policy import (
    CohortFrontierDecision,
    default_cohort_frontier_policy,
)
from glio_noncode.cohort_frontier_public_data import (
    CohortFrontierOperation,
    CohortFrontierRole,
    audit_cohort_frontier_data,
    build_cohort_frontier_catalog,
    default_cohort_frontier_fixture,
    load_cohort_frontier_fixture,
)
from glio_noncode.cohort_frontier_quality_gate import evaluate_cohort_frontier_quality
from glio_noncode.cohort_frontier_reconciliation import reconcile_cohort_frontier
from glio_noncode.cohort_frontier_release import (
    CohortFrontierReleaseState,
    build_cohort_frontier_release_manifest,
)
from glio_noncode.cohort_frontier_replay import (
    compare_cohort_frontier_replays,
    replay_cohort_frontier,
    replay_cohort_frontier_is_deterministic,
)
from glio_noncode.cohort_frontier_runtime import run_cohort_frontier_runtime
from glio_noncode.cohort_frontier_scenario_matrix import build_cohort_frontier_scenario_matrix
from glio_noncode.cohort_frontier_schema import default_cohort_frontier_schema
from glio_noncode.cohort_frontier_thresholds import (
    build_cohort_frontier_threshold_report,
    default_cohort_frontier_threshold_profiles,
)
from glio_noncode.cohort_frontier_views import build_cohort_frontier_review_view


class CohortFrontierEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_cohort_frontier_fixture()
        self.contracts = default_cohort_frontier_contracts()
        self.schema = default_cohort_frontier_schema()
        self.evaluation = evaluate_cohort_frontier_fixture(self.fixture)
        self.policy = default_cohort_frontier_policy(self.contracts)
        self.lineage = build_cohort_frontier_lineage(self.fixture, self.evaluation)
        self.reconciliation = reconcile_cohort_frontier(self.fixture, self.evaluation, self.policy)
        self.metrics = measure_cohort_frontier(self.evaluation)
        self.quality = evaluate_cohort_frontier_quality(self.fixture, self.evaluation, self.contracts, self.schema, self.lineage, self.reconciliation)
        self.runtime = run_cohort_frontier_runtime(self.fixture, run_id="cohort-test-runtime")
        self.replay = replay_cohort_frontier(self.fixture, replay_id="cohort-test-replay")
        self.release = build_cohort_frontier_release_manifest(self.runtime.bundle, self.quality, self.replay)

    def test_public_fixture_manifest(self) -> None:
        self.assertEqual(self.fixture.fixture_id, "cohort-frontier-public-aggregate")
        self.assertEqual(self.fixture.evidence_boundary, "public_aggregate_non_patient")
        self.assertEqual(len(self.fixture.sources), 5)
        self.assertEqual(len(self.fixture.records), 16)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)
        self.assertTrue(all(item.uri.startswith("https://") for item in self.fixture.sources))

    def test_data_audit_catalog_and_operation_coverage(self) -> None:
        audit = audit_cohort_frontier_data(self.fixture)
        catalog = build_cohort_frontier_catalog(self.fixture)
        self.assertTrue(audit.accepted)
        self.assertEqual(len(audit.checks), 12)
        self.assertEqual(len(catalog.record_ids), 16)
        self.assertEqual(set(catalog.operations), set(CohortFrontierOperation))
        for operation in CohortFrontierOperation:
            rows = tuple(item for item in self.fixture.records if item.operation is operation)
            self.assertEqual(len(rows), 4)
            self.assertEqual(sum(item.role is CohortFrontierRole.POSITIVE for item in rows), 1)

    def test_evaluation_has_120_passed_checks(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.checks), 120)
        self.assertEqual(self.evaluation.passed_checks, 120)
        self.assertEqual(self.evaluation.failed_check_ids, ())

    def test_positive_paths_are_supported_or_published(self) -> None:
        positives = tuple(item for item in self.evaluation.executions if item.role is CohortFrontierRole.POSITIVE)
        self.assertEqual(len(positives), 4)
        self.assertTrue(all(item.accepted for item in positives))
        self.assertEqual({item.state for item in positives}, {"supported", "published"})

    def test_controls_are_non_accepted_with_expected_issues(self) -> None:
        controls = tuple(item for item in self.evaluation.executions if item.role is CohortFrontierRole.CONTROL)
        self.assertEqual(len(controls), 12)
        self.assertTrue(all(not item.accepted for item in controls))
        self.assertEqual(self.evaluation.execution_map()["C13-CTRL-001"].issue_codes, ("parity_gap_high",))
        self.assertEqual(self.evaluation.execution_map()["C14-CTRL-001"].issue_codes, ("target_feature_gap",))
        self.assertEqual(self.evaluation.execution_map()["C14-CTRL-002"].issue_codes, ("distribution_shift_high",))
        self.assertEqual(self.evaluation.execution_map()["C15-CTRL-001"].issue_codes, ("privacy_floor_violation",))
        self.assertEqual(self.evaluation.execution_map()["C16-CTRL-002"].issue_codes, ("empty_cohort_discovery_input",))

    def test_subgroup_fairness_retains_strata_and_gap(self) -> None:
        output = self.evaluation.execution_map()["C13-POS-001"].output
        self.assertEqual(len(output["strata"]), 2)
        self.assertEqual(output["maximum_parity_gap"], 0.0)
        self.assertEqual(output["review_ids"], [])
        control = self.evaluation.execution_map()["C13-CTRL-001"].output
        self.assertEqual(control["review_ids"], ["group:B"])
        self.assertEqual(control["strata"][0]["total"], 2)

    def test_transportability_retains_overlap_shift_and_review_ids(self) -> None:
        positive = self.evaluation.execution_map()["C14-POS-001"].output
        self.assertEqual(positive["transportable_ids"], ["analysis-1"])
        self.assertEqual(positive["estimates"][0]["overlap"], 1.0)
        gap = self.evaluation.execution_map()["C14-CTRL-001"].output
        shift = self.evaluation.execution_map()["C14-CTRL-002"].output
        self.assertEqual(gap["review_ids"], ["analysis-gap"])
        self.assertEqual(shift["review_ids"], ["analysis-shift"])

    def test_federated_summary_retains_privacy_and_spread(self) -> None:
        positive = self.evaluation.execution_map()["C15-POS-001"].output
        summary = positive["summaries"][0]
        self.assertEqual(summary["site_count"], 2)
        self.assertEqual(summary["total_count"], 22)
        self.assertEqual(summary["privacy_floor"], 5)
        self.assertEqual(positive["supported_ids"], ["f-1"])
        control = self.evaluation.execution_map()["C15-CTRL-001"].output
        self.assertEqual(control["review_ids"], ["f-low"])

    def test_discovery_manifest_is_aggregate_only(self) -> None:
        positive = self.evaluation.execution_map()["C16-POS-001"]
        self.assertEqual(positive.state, "published")
        self.assertEqual(positive.output["bundle_id"], "cohort-frontier-1")
        self.assertEqual(positive.output["feature_ids"], ["f-1"])
        self.assertTrue(positive.output["bundle_address"].startswith("sha256:"))

    def test_contracts_and_schema_cover_four_operations(self) -> None:
        self.assertEqual(len(self.contracts.contracts), 4)
        self.assertEqual({item.operation for item in self.contracts.contracts}, set(CohortFrontierOperation))
        self.assertEqual(len(self.schema.operations), 4)
        self.assertEqual(len(self.contracts.issue_codes()), 12)
        for operation in CohortFrontierOperation:
            self.assertIn("input_records", self.schema.by_operation(operation).field_names())

    def test_policy_allows_positive_paths_but_keeps_controls(self) -> None:
        decisions = self.policy.decide(self.evaluation)
        self.assertEqual(len(decisions), 4)
        self.assertTrue(all(item.publishable for item in decisions))
        self.assertEqual(next(item for item in decisions if item.operation is CohortFrontierOperation.COHORT_DISCOVERY).decision, CohortFrontierDecision.ALLOW_PUBLICATION)
        self.assertTrue(all(item.issue_codes == () for item in decisions))

    def test_lineage_is_acyclic_with_36_edges(self) -> None:
        self.assertTrue(self.lineage.acyclic)
        self.assertEqual(len(self.lineage.edges), 36)
        self.assertEqual(len(self.lineage.terminal_addresses), 16)
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in self.lineage.edges))

    def test_reconciliation_is_exact(self) -> None:
        self.assertTrue(self.reconciliation.reconciled)
        self.assertEqual(self.reconciliation.mismatched_record_ids, ())
        self.assertEqual(len(self.reconciliation.items), 16)

    def test_metrics_have_eleven_rows(self) -> None:
        self.assertEqual(len(self.metrics.metrics), 11)
        self.assertEqual(self.metrics.by_id("overall_check_pass_rate").value, 1.0)
        self.assertEqual(self.metrics.by_id("control_rejection_rate").value, 1.0)
        for operation in CohortFrontierOperation:
            self.assertEqual(self.metrics.by_id(f"{operation.value}_acceptance_rate").denominator, 4)

    def test_quality_gate_has_twelve_checks(self) -> None:
        self.assertTrue(self.quality.accepted)
        self.assertEqual(len(self.quality.checks), 12)
        self.assertEqual(self.quality.passed_count, 12)
        self.assertEqual(self.quality.blocking_check_ids, ())

    def test_runtime_and_release_are_ready(self) -> None:
        self.assertTrue(self.runtime.accepted)
        self.assertEqual(len(self.runtime.stages), 10)
        self.assertEqual(tuple(item.sequence for item in self.runtime.stages), tuple(range(1, 11)))
        self.assertEqual(self.release.state, CohortFrontierReleaseState.READY)
        self.assertTrue(self.release.accepted)
        self.assertTrue(self.release.allowed_uses)
        self.assertTrue(self.release.excluded_uses)

    def test_replay_is_stable(self) -> None:
        second = replay_cohort_frontier(self.fixture, replay_id="cohort-test-replay-2")
        comparison = compare_cohort_frontier_replays(self.replay, second)
        self.assertTrue(comparison.accepted)
        self.assertEqual(comparison.drift_fields, ())
        self.assertTrue(replay_cohort_frontier_is_deterministic(self.fixture))

    def test_scenario_matrix_has_33_rows(self) -> None:
        matrix = build_cohort_frontier_scenario_matrix()
        self.assertEqual(len(matrix.scenarios), 33)
        self.assertEqual(len(matrix.dimensions), 6)
        self.assertTrue(matrix.review_scenarios)
        self.assertTrue(matrix.supported_scenarios)
        self.assertEqual({item.operation for item in matrix.scenarios}, set(CohortFrontierOperation))

    def test_threshold_report_has_972_probes(self) -> None:
        self.assertEqual(len(default_cohort_frontier_threshold_profiles()), 4)
        report = build_cohort_frontier_threshold_report()
        self.assertEqual(len(report.profiles), 4)
        self.assertEqual(len(report.probes), 972)
        self.assertTrue(report.accepted_probe_ids)
        self.assertTrue(report.review_probe_ids)
        self.assertEqual(len(report.accepted_probe_ids) + len(report.review_probe_ids), 972)

    def test_artifact_inventory_has_seven_nodes(self) -> None:
        inventory = build_cohort_frontier_artifact_inventory(self.fixture, self.evaluation, self.metrics, self.lineage, self.quality, self.runtime.bundle, self.release)
        self.assertEqual(len(inventory.artifacts), 7)
        self.assertEqual(inventory.root_artifact_id, "cohort-artifact-release")
        self.assertEqual(len(inventory.by_kind(CohortFrontierArtifactKind.RELEASE)), 1)
        self.assertGreater(inventory.total_bytes, 0)

    def test_invariant_report_accepts_complete_observation(self) -> None:
        observations = cohort_frontier_observation_map(context_preserved=True, content_addressed=True, positive_control_separated=True, parity_visible=True, transport_visible=True, privacy_visible=True, discovery_addressed=True, source_receipts=True, issue_vocabulary=True, replay_stable=True)
        report = run_cohort_frontier_invariants(observations)
        self.assertTrue(report.accepted)
        self.assertEqual(len(default_cohort_frontier_invariants()), 10)
        self.assertEqual(report.failed_ids, ())

    def test_observability_has_26_events(self) -> None:
        report = observe_cohort_frontier(self.runtime, self.evaluation)
        self.assertEqual(len(report.events), 26)
        self.assertEqual(report.counter_map()["runtime_stage_count"], 10)
        self.assertEqual(report.counter_map()["execution_count"], 16)
        self.assertEqual(report.counter_map()["accepted_execution_count"], 4)

    def test_review_view_and_exports_keep_all_controls(self) -> None:
        view = build_cohort_frontier_review_view(self.fixture, self.evaluation, self.metrics, self.policy.decide(self.evaluation), self.release)
        self.assertEqual(len(view.rows), 16)
        self.assertEqual(len(view.accepted_rows()), 4)
        self.assertEqual(len(view.issue_rows()), 12)
        csv_text = export_cohort_frontier_review_csv(view)
        self.assertEqual(len(csv_text.splitlines()), 17)
        self.assertIn("C13-CTRL-001", csv_text)
        self.assertTrue(export_cohort_frontier_json(self.release).endswith("\n"))
        self.assertTrue(export_cohort_frontier_canonical(self.release).startswith("{"))
        self.assertEqual(export_cohort_frontier_manifest(self.runtime.bundle, self.release)["public_boundary"], "public_aggregate_non_patient")

    def test_fixture_json_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cohort.json"
            path.write_text(json.dumps(self.fixture.to_dict()), encoding="utf-8")
            loaded = load_cohort_frontier_fixture(path)
        self.assertEqual(loaded.fixture_id, self.fixture.fixture_id)
        self.assertEqual(len(loaded.records), 16)

    def test_single_record_execution_address_is_stable(self) -> None:
        record = self.fixture.record_map()["C14-POS-001"]
        first = execute_cohort_frontier_record(record)
        second = execute_cohort_frontier_record(record)
        self.assertEqual(first.content_address, second.content_address)
        self.assertTrue(first.accepted)


if __name__ == "__main__":
    unittest.main()
