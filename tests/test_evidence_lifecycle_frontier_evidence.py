"""Deep evidence tests for Domain 14 C01–C04 lifecycle coverage."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.evidence_lifecycle_frontier_artifacts import (
    EvidenceLifecycleArtifactKind,
    build_evidence_lifecycle_artifact_inventory,
)
from glio_noncode.evidence_lifecycle_frontier_checks import (
    default_evidence_lifecycle_invariants,
    run_evidence_lifecycle_invariants,
    validation_lifecycle_observation_map,
)
from glio_noncode.evidence_lifecycle_frontier_contracts import default_evidence_lifecycle_contracts
from glio_noncode.evidence_lifecycle_frontier_depth import audit_evidence_lifecycle_depth
from glio_noncode.evidence_lifecycle_frontier_exports import (
    export_evidence_lifecycle_canonical,
    export_evidence_lifecycle_json,
    export_evidence_lifecycle_manifest,
    export_evidence_lifecycle_review_csv,
)
from glio_noncode.evidence_lifecycle_frontier_fixture_eval import (
    evaluate_evidence_lifecycle_fixture,
)
from glio_noncode.evidence_lifecycle_frontier_lineage import build_evidence_lifecycle_lineage
from glio_noncode.evidence_lifecycle_frontier_metrics import measure_evidence_lifecycle
from glio_noncode.evidence_lifecycle_frontier_observability import observe_evidence_lifecycle
from glio_noncode.evidence_lifecycle_frontier_policy import (
    EvidenceLifecycleDecision,
    default_evidence_lifecycle_policy,
)
from glio_noncode.evidence_lifecycle_frontier_public_data import (
    EvidenceLifecycleOperation,
    EvidenceLifecycleRole,
    audit_evidence_lifecycle_data,
    build_evidence_lifecycle_catalog,
    default_evidence_lifecycle_fixture,
    load_evidence_lifecycle_fixture,
)
from glio_noncode.evidence_lifecycle_frontier_quality_gate import (
    evaluate_evidence_lifecycle_quality,
)
from glio_noncode.evidence_lifecycle_frontier_reconciliation import reconcile_evidence_lifecycle
from glio_noncode.evidence_lifecycle_frontier_release import (
    EvidenceLifecycleReleaseState,
    build_evidence_lifecycle_release_manifest,
)
from glio_noncode.evidence_lifecycle_frontier_replay import (
    compare_evidence_lifecycle_replays,
    evidence_lifecycle_replay_is_deterministic,
    replay_evidence_lifecycle,
)
from glio_noncode.evidence_lifecycle_frontier_runtime import run_evidence_lifecycle_runtime
from glio_noncode.evidence_lifecycle_frontier_scenario_matrix import (
    build_evidence_lifecycle_scenario_matrix,
)
from glio_noncode.evidence_lifecycle_frontier_schema import default_evidence_lifecycle_schema
from glio_noncode.evidence_lifecycle_frontier_thresholds import (
    build_evidence_lifecycle_threshold_report,
    default_evidence_lifecycle_threshold_profiles,
)
from glio_noncode.evidence_lifecycle_frontier_views import build_evidence_lifecycle_review_view


class EvidenceLifecycleFrontierEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_evidence_lifecycle_fixture()
        self.contracts = default_evidence_lifecycle_contracts()
        self.schema = default_evidence_lifecycle_schema()
        self.evaluation = evaluate_evidence_lifecycle_fixture(self.fixture)
        self.policy = default_evidence_lifecycle_policy()
        self.decisions = self.policy.decide(self.evaluation)
        self.lineage = build_evidence_lifecycle_lineage(self.fixture, self.evaluation)
        self.reconciliation = reconcile_evidence_lifecycle(self.fixture, self.evaluation, self.policy)
        self.metrics = measure_evidence_lifecycle(self.evaluation)
        self.quality = evaluate_evidence_lifecycle_quality(self.fixture, self.evaluation, self.contracts, self.schema, self.lineage, self.reconciliation)
        self.runtime = run_evidence_lifecycle_runtime(self.fixture, run_id="lifecycle-test-runtime")
        self.replay = replay_evidence_lifecycle(self.fixture, replay_id="lifecycle-test-replay")
        self.release = build_evidence_lifecycle_release_manifest(self.runtime.bundle, self.quality, self.replay)

    def test_boundary_catalog_and_data_audit(self) -> None:
        audit = audit_evidence_lifecycle_data(self.fixture)
        catalog = build_evidence_lifecycle_catalog(self.fixture)
        self.assertTrue(audit.accepted)
        self.assertEqual(len(audit.checks), 12)
        self.assertEqual(len(self.fixture.sources), 5)
        self.assertEqual(len(self.fixture.records), 16)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)
        self.assertEqual(len(catalog.record_ids), 16)
        self.assertEqual(set(catalog.operations), set(EvidenceLifecycleOperation))

    def test_evaluation_has_120_passing_checks(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.checks), 120)
        self.assertEqual(self.evaluation.passed_checks, 120)
        self.assertEqual(self.evaluation.failed_check_ids, ())

    def test_positive_paths_retain_distinct_lifecycle_states(self) -> None:
        positives = tuple(item for item in self.evaluation.executions if item.role is EvidenceLifecycleRole.POSITIVE)
        self.assertEqual(len(positives), 4)
        self.assertTrue(all(item.accepted for item in positives))
        self.assertEqual({item.state for item in positives}, {"partial", "supported", "contradictory"})
        self.assertEqual(self.evaluation.execution_map()["C01-POS-001"].issue_codes, ("missing_required_field",))
        self.assertEqual(self.evaluation.execution_map()["C04-POS-001"].issue_codes, ("contradiction_unresolved",))

    def test_controls_retain_specific_failure_modes(self) -> None:
        controls = tuple(item for item in self.evaluation.executions if item.role is EvidenceLifecycleRole.CONTROL)
        self.assertEqual(len(controls), 12)
        self.assertTrue(all(not item.accepted for item in controls))
        self.assertEqual(self.evaluation.execution_map()["C01-CTRL-001"].issue_codes, ("invalid_json",))
        self.assertEqual(self.evaluation.execution_map()["C02-CTRL-001"].issue_codes, ("orphan_claim",))
        self.assertEqual(self.evaluation.execution_map()["C03-CTRL-002"].issue_codes, ("edge_context_mismatch",))
        self.assertEqual(self.evaluation.execution_map()["C04-CTRL-003"].issue_codes, ("disagreement_out_of_domain",))

    def test_citation_resolution_retains_quarantine_accounting(self) -> None:
        output = self.evaluation.execution_map()["C01-POS-001"].output
        self.assertEqual(output["state"], "partial")
        self.assertEqual(len(output["citations"]), 1)
        self.assertEqual(output["issues"][0]["code"], "missing_required_field")
        self.assertEqual(output["quarantined_count"], 1)
        self.assertTrue(output["input_hash"].startswith("sha256:"))

    def test_graph_construction_retains_supersession_and_history(self) -> None:
        output = self.evaluation.execution_map()["C02-POS-001"].output
        self.assertEqual(output["state"], "supported")
        self.assertEqual(output["superseded_claim_ids"], ["c02-first"])
        self.assertEqual(output["active_claim_ids"], ["c02-current"])
        self.assertEqual(len(output["claims"]), 2)
        self.assertTrue(any("superseded" in warning for warning in output["warnings"]))

    def test_edge_validation_keeps_missing_source_and_context_visible(self) -> None:
        missing = self.evaluation.execution_map()["C03-CTRL-001"].output
        mismatch = self.evaluation.execution_map()["C03-CTRL-002"].output
        self.assertEqual(missing["state"], "partial")
        self.assertEqual(missing["missing_source_ids"], ["missing-source"])
        self.assertEqual(mismatch["state"], "out_of_domain")
        self.assertTrue(mismatch["warnings"])

    def test_disagreement_tracker_keeps_competing_values_separate(self) -> None:
        output = self.evaluation.execution_map()["C04-POS-001"].output
        record = output["records"][0]
        self.assertEqual(record["state"], "contradictory")
        self.assertEqual(record["positive_claim_ids"], ["c04-positive"])
        self.assertEqual(record["negative_claim_ids"], ["c04-negative"])
        self.assertEqual(set(record["value_groups"]), {"increases", "decreases"})
        self.assertEqual(output["contradictory_edge_ids"], ["edge-c04"])

    def test_contracts_and_schema_cover_four_operations(self) -> None:
        self.assertEqual(len(self.contracts.contracts), 4)
        self.assertEqual(len(self.schema.operations), 4)
        self.assertEqual({item.operation for item in self.contracts.contracts}, set(EvidenceLifecycleOperation))
        self.assertEqual({item.operation for item in self.schema.operations}, set(EvidenceLifecycleOperation))
        self.assertGreaterEqual(len(self.contracts.issue_codes()), 13)

    def test_policy_allows_positive_paths_with_research_boundary(self) -> None:
        self.assertEqual(len(self.decisions), 4)
        self.assertTrue(all(item.publishable for item in self.decisions))
        self.assertEqual(next(item for item in self.decisions if item.operation is EvidenceLifecycleOperation.GRAPH_CONSTRUCTION).decision, EvidenceLifecycleDecision.ALLOW_REPLAY)
        self.assertTrue(self.policy.allowed_uses)
        self.assertTrue(self.policy.excluded_uses)

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
        self.assertEqual(self.release.state, EvidenceLifecycleReleaseState.READY)
        self.assertTrue(self.release.accepted)

    def test_replay_scenarios_thresholds_and_depth(self) -> None:
        second = replay_evidence_lifecycle(self.fixture, replay_id="lifecycle-test-replay-2")
        comparison = compare_evidence_lifecycle_replays(self.replay, second)
        self.assertTrue(comparison.accepted)
        self.assertEqual(comparison.drift_fields, ())
        self.assertTrue(evidence_lifecycle_replay_is_deterministic(self.fixture))
        matrix = build_evidence_lifecycle_scenario_matrix()
        self.assertEqual(len(matrix.scenarios), 31)
        self.assertEqual(len(matrix.dimensions), 6)
        self.assertTrue(matrix.review_scenarios)
        threshold = build_evidence_lifecycle_threshold_report()
        self.assertEqual(len(default_evidence_lifecycle_threshold_profiles()), 4)
        self.assertEqual(len(threshold.probes), 972)
        self.assertEqual(len(threshold.accepted_probe_ids) + len(threshold.review_probe_ids), 972)
        self.assertTrue(audit_evidence_lifecycle_depth().accepted)

    def test_artifacts_invariants_and_observability(self) -> None:
        inventory = build_evidence_lifecycle_artifact_inventory(self.fixture, self.evaluation, self.metrics, self.quality, self.runtime, self.release, self.runtime.bundle)
        self.assertEqual(len(inventory.artifacts), 7)
        self.assertEqual(inventory.root_artifact_id, "evidence-artifact-release")
        self.assertEqual(len(inventory.by_kind(EvidenceLifecycleArtifactKind.RELEASE)), 1)
        observations = validation_lifecycle_observation_map(context_preserved=True, positive_control_separated=True, citation_issues_visible=True, graph_history_retained=True, edge_no_averaging=True, disagreement_visible=True, source_addressed=True, execution_addressed=True, replay_stable=True, research_boundary=True)
        invariant = run_evidence_lifecycle_invariants(observations)
        self.assertTrue(invariant.accepted)
        self.assertEqual(len(default_evidence_lifecycle_invariants()), 10)
        self.assertEqual(len(observe_evidence_lifecycle(self.runtime, self.evaluation).events), 26)

    def test_review_view_and_exports_keep_issue_rows(self) -> None:
        view = build_evidence_lifecycle_review_view(self.fixture, self.evaluation, self.decisions, self.release)
        self.assertEqual(len(view.rows), 16)
        self.assertEqual(len(view.accepted_rows()), 4)
        self.assertEqual(len(view.issue_rows()), 13)
        csv_text = export_evidence_lifecycle_review_csv(view)
        self.assertEqual(len(csv_text.splitlines()), 17)
        self.assertIn("C04-POS-001", csv_text)
        self.assertTrue(export_evidence_lifecycle_json(self.release).endswith("\n"))
        self.assertTrue(export_evidence_lifecycle_canonical(self.release).startswith("{"))
        self.assertEqual(export_evidence_lifecycle_manifest(self.runtime.bundle, self.release)["public_boundary"], "public_aggregate_non_patient")

    def test_fixture_json_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence-lifecycle.json"
            path.write_text(json.dumps(self.fixture.to_dict()), encoding="utf-8")
            loaded = load_evidence_lifecycle_fixture(path)
        self.assertEqual(loaded.fixture_id, self.fixture.fixture_id)
        self.assertEqual(loaded.content_address, self.fixture.content_address)
        self.assertEqual(evaluate_evidence_lifecycle_fixture(loaded).content_address, self.evaluation.content_address)

    def test_every_execution_is_addressed_and_role_bound(self) -> None:
        for record, execution in zip(self.fixture.records, self.evaluation.executions, strict=True):
            self.assertEqual(record.record_id, execution.record_id)
            self.assertEqual(record.operation, execution.operation)
            self.assertTrue(execution.content_address.startswith("sha256:"))
            self.assertEqual(execution.accepted, record.role is EvidenceLifecycleRole.POSITIVE)

    def test_control_records_are_not_promoted_by_expected_states(self) -> None:
        for record in self.fixture.control_records:
            execution = self.evaluation.execution_map()[record.record_id]
            self.assertFalse(execution.accepted)
            self.assertEqual(execution.state, record.expected_state)


if __name__ == "__main__":
    unittest.main()
