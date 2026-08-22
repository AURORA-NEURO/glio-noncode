"""Deep evidence tests for Domain 15 C01–C04 research workspaces."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.workspace_frontier_adapters import (
    adapt_workspace_frontier_input,
    default_workspace_frontier_adapters,
)
from glio_noncode.workspace_frontier_artifacts import (
    WorkspaceFrontierArtifactKind,
    build_workspace_frontier_artifact_inventory,
)
from glio_noncode.workspace_frontier_checks import (
    default_workspace_frontier_invariants,
    run_workspace_frontier_invariants,
    workspace_frontier_invariants_from_execution,
    workspace_frontier_observation_map,
)
from glio_noncode.workspace_frontier_contracts import default_workspace_frontier_contracts
from glio_noncode.workspace_frontier_depth import audit_workspace_frontier_depth
from glio_noncode.workspace_frontier_exports import (
    export_workspace_frontier_canonical,
    export_workspace_frontier_json,
    export_workspace_frontier_manifest,
    export_workspace_frontier_review_csv,
)
from glio_noncode.workspace_frontier_fixture_eval import evaluate_workspace_frontier_fixture
from glio_noncode.workspace_frontier_lineage import build_workspace_frontier_lineage
from glio_noncode.workspace_frontier_metrics import measure_workspace_frontier
from glio_noncode.workspace_frontier_observability import observe_workspace_frontier
from glio_noncode.workspace_frontier_policy import (
    WorkspaceFrontierDecision,
    default_workspace_frontier_policy,
)
from glio_noncode.workspace_frontier_public_data import (
    WorkspaceFrontierOperation,
    WorkspaceFrontierRole,
    audit_workspace_frontier_data,
    build_workspace_frontier_catalog,
    default_workspace_frontier_fixture,
    load_workspace_frontier_fixture,
)
from glio_noncode.workspace_frontier_quality_gate import evaluate_workspace_frontier_quality
from glio_noncode.workspace_frontier_reconciliation import reconcile_workspace_frontier
from glio_noncode.workspace_frontier_release import (
    WorkspaceFrontierReleaseState,
    build_workspace_frontier_release_manifest,
)
from glio_noncode.workspace_frontier_replay import (
    compare_workspace_frontier_replays,
    replay_workspace_frontier,
    workspace_frontier_replay_is_deterministic,
)
from glio_noncode.workspace_frontier_review_queue import (
    WorkspaceFrontierReviewDisposition,
    build_workspace_frontier_review_queue,
)
from glio_noncode.workspace_frontier_runtime import run_workspace_frontier_runtime
from glio_noncode.workspace_frontier_scenario_matrix import build_workspace_frontier_scenario_matrix
from glio_noncode.workspace_frontier_schema import default_workspace_frontier_schema
from glio_noncode.workspace_frontier_thresholds import (
    build_workspace_frontier_threshold_report,
    default_workspace_frontier_threshold_profiles,
)
from glio_noncode.workspace_frontier_views import build_workspace_frontier_review_view


class WorkspaceFrontierEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_workspace_frontier_fixture()
        self.contracts = default_workspace_frontier_contracts()
        self.schema = default_workspace_frontier_schema()
        self.evaluation = evaluate_workspace_frontier_fixture(self.fixture)
        self.policy = default_workspace_frontier_policy()
        self.decisions = self.policy.decide(self.evaluation)
        self.lineage = build_workspace_frontier_lineage(self.fixture, self.evaluation)
        self.reconciliation = reconcile_workspace_frontier(self.fixture, self.evaluation, self.policy)
        self.metrics = measure_workspace_frontier(self.evaluation)
        self.quality = evaluate_workspace_frontier_quality(self.fixture, self.evaluation, self.contracts, self.schema, self.lineage, self.reconciliation)
        self.runtime = run_workspace_frontier_runtime(self.fixture, run_id="workspace-frontier-test-runtime")
        self.replay = replay_workspace_frontier(self.fixture, replay_id="workspace-frontier-test-replay")
        self.release = build_workspace_frontier_release_manifest(self.runtime.bundle, self.quality, self.replay, self.runtime)
        self.view = build_workspace_frontier_review_view(self.fixture, self.evaluation, self.decisions, self.release)
        self.queue = build_workspace_frontier_review_queue(self.fixture, self.evaluation, self.decisions, self.view, self.release)

    def test_boundary_catalog_and_data_audit(self) -> None:
        audit = audit_workspace_frontier_data(self.fixture)
        catalog = build_workspace_frontier_catalog(self.fixture)
        self.assertTrue(audit.accepted)
        self.assertEqual(len(audit.checks), 12)
        self.assertEqual(audit.passed_count, 12)
        self.assertEqual(len(self.fixture.sources), 5)
        self.assertEqual(len(self.fixture.records), 16)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)
        self.assertEqual(len(catalog.record_ids), 16)
        self.assertEqual(set(catalog.operations), set(WorkspaceFrontierOperation))
        self.assertEqual(self.fixture.evidence_boundary, "public_aggregate_non_patient")

    def test_fixture_source_receipts_are_public_and_addressed(self) -> None:
        self.assertTrue(all(item.uri.startswith("https://") for item in self.fixture.sources))
        self.assertEqual(len(self.fixture.source_map()), 5)
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in self.fixture.sources))
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in self.fixture.records))

    def test_evaluation_has_120_passing_checks(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.checks), 120)
        self.assertEqual(self.evaluation.passed_checks, 120)
        self.assertEqual(self.evaluation.failed_check_ids, ())

    def test_positive_paths_cover_four_surface_states(self) -> None:
        positives = tuple(item for item in self.evaluation.executions if item.role is WorkspaceFrontierRole.POSITIVE)
        self.assertEqual(len(positives), 4)
        self.assertTrue(all(item.accepted for item in positives))
        self.assertEqual({item.operation for item in positives}, set(WorkspaceFrontierOperation))
        self.assertEqual({item.state for item in positives}, {"partial", "supported"})
        self.assertEqual(self.evaluation.execution_map()["C01-POS-001"].issue_codes, ("missing_dossier",))
        self.assertEqual(self.evaluation.execution_map()["C02-POS-001"].issue_codes, ())

    def test_control_paths_keep_specific_failure_modes(self) -> None:
        controls = tuple(item for item in self.evaluation.executions if item.role is WorkspaceFrontierRole.CONTROL)
        self.assertEqual(len(controls), 12)
        self.assertTrue(all(not item.accepted for item in controls))
        expected = {
            "C01-CTRL-001": ("context_mismatch",),
            "C01-CTRL-002": ("invalid_workspace_input",),
            "C01-CTRL-003": ("duplicate_variant_id",),
            "C02-CTRL-001": ("context_mismatch",),
            "C02-CTRL-002": ("no_matching_records",),
            "C03-CTRL-001": ("variant_absent",),
            "C03-CTRL-002": ("context_mismatch",),
            "C04-CTRL-001": ("track_parse_issue",),
            "C04-CTRL-003": ("invalid_track_input",),
        }
        for record_id, issue_codes in expected.items():
            self.assertEqual(self.evaluation.execution_map()[record_id].issue_codes, issue_codes)

    def test_case_workspace_retains_sections_facets_and_accessibility(self) -> None:
        output = self.evaluation.execution_map()["C01-POS-001"].output
        self.assertEqual(output["section_ids"], ["variants", "regulatory-elements", "hypotheses", "evidence", "validation"])
        self.assertEqual(output["record_count"], 3)
        self.assertEqual(output["page_total"], 3)
        self.assertIn("variants", output["accessibility"]["keyboard_order"])
        self.assertTrue(output["accessibility"]["labels_present"])
        self.assertTrue(output["input_address"].startswith("sha256:"))

    def test_case_controls_never_transport_wrong_context_or_duplicate_identity(self) -> None:
        mismatch = self.evaluation.execution_map()["C01-CTRL-001"].output
        duplicate = self.evaluation.execution_map()["C01-CTRL-003"].output
        self.assertEqual(mismatch["state"], "out_of_domain")
        self.assertEqual(mismatch["record_count"], 0)
        self.assertIn("duplicate variant_id", duplicate["error"])

    def test_cohort_workspace_retains_query_and_selection_accounting(self) -> None:
        output = self.evaluation.execution_map()["C02-POS-001"].output
        self.assertEqual(output["state"], "supported")
        self.assertEqual(output["query_record_count"], 2)
        self.assertEqual(output["excluded_count"], 0)
        self.assertEqual(output["section_ids"], ["cohort-records", "background", "controls"])
        self.assertEqual(output["facets"]["record_type"]["cohort_record"], 2)
        self.assertTrue(output["accessibility"]["row_label"])

    def test_cohort_controls_preserve_absence_and_out_of_domain(self) -> None:
        ood = self.evaluation.execution_map()["C02-CTRL-001"].output
        absent = self.evaluation.execution_map()["C02-CTRL-002"].output
        empty = self.evaluation.execution_map()["C02-CTRL-003"].output
        self.assertEqual(ood["state"], "out_of_domain")
        self.assertEqual(absent["state"], "absent")
        self.assertEqual(empty["query_record_count"], 0)
        self.assertEqual(absent["excluded_reasons"], {"not_callable": 1})

    def test_variant_explorer_resolves_present_and_declared_absence(self) -> None:
        present = self.evaluation.execution_map()["C03-POS-001"].output
        missing = self.evaluation.execution_map()["C03-CTRL-001"].output
        mismatch = self.evaluation.execution_map()["C03-CTRL-002"].output
        self.assertEqual(present["state"], "supported")
        self.assertEqual(present["variant_record_id"], "v-frontier-1")
        self.assertEqual(present["related_record_ids"], [])
        self.assertEqual(missing["state"], "abstained")
        self.assertIsNone(missing["variant_record_id"])
        self.assertEqual(mismatch["state"], "out_of_domain")

    def test_regulatory_browser_retains_coordinates_and_parse_issues(self) -> None:
        positive = self.evaluation.execution_map()["C04-POS-001"].output
        malformed = self.evaluation.execution_map()["C04-CTRL-001"].output
        self.assertEqual(positive["feature_count"], 2)
        self.assertEqual(positive["issue_count"], 0)
        self.assertEqual(positive["coordinate_labels"], ["chr7:100-120", "chr7:181-230"])
        self.assertEqual(malformed["state"], "partial")
        self.assertEqual(malformed["issue_count"], 1)
        self.assertTrue(malformed["warnings"])

    def test_contracts_and_schema_cover_four_surfaces(self) -> None:
        self.assertEqual(len(self.contracts.contracts), 4)
        self.assertEqual(len(self.schema.operations), 4)
        self.assertEqual({item.operation for item in self.contracts.contracts}, set(WorkspaceFrontierOperation))
        self.assertEqual({item.operation for item in self.schema.operations}, set(WorkspaceFrontierOperation))
        self.assertGreaterEqual(len(self.contracts.issue_codes()), 8)
        self.assertGreaterEqual(len(self.schema.fields()), 28)
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in self.schema.fields()))

    def test_policy_allows_only_supported_positive_research_views(self) -> None:
        self.assertEqual(len(self.decisions), 16)
        ready = tuple(item for item in self.decisions if item.decision is WorkspaceFrontierDecision.ALLOW_RESEARCH_VIEW)
        self.assertEqual(len(ready), 3)
        self.assertTrue(all(item.publishable for item in ready))
        self.assertTrue(all(not item.publishable for item in self.decisions if item not in ready))
        self.assertTrue(self.policy.allowed_uses)
        self.assertTrue(self.policy.excluded_uses)
        self.assertIn("diagnosis", self.policy.excluded_uses)

    def test_lineage_and_reconciliation_are_complete(self) -> None:
        self.assertTrue(self.lineage.acyclic)
        self.assertEqual(len(self.lineage.edges), 36)
        self.assertEqual(len(self.lineage.terminal_addresses), 16)
        self.assertEqual(len(self.lineage.root_ids), 5)
        self.assertTrue(self.reconciliation.reconciled)
        self.assertEqual(self.reconciliation.mismatched_record_ids, ())
        self.assertEqual(len(self.reconciliation.items), 16)
        self.assertEqual(self.reconciliation.policy_decision_count, 16)

    def test_metrics_quality_runtime_and_release(self) -> None:
        self.assertEqual(len(self.metrics.metrics), 13)
        self.assertEqual(self.metrics.by_id("positive_acceptance_rate").value, 1.0)
        self.assertEqual(self.metrics.by_id("control_rejection_rate").value, 1.0)
        self.assertEqual(self.metrics.by_id("execution_check_pass_rate").value, 1.0)
        self.assertTrue(self.quality.accepted)
        self.assertEqual(len(self.quality.checks), 14)
        self.assertEqual(self.quality.passed_count, 14)
        self.assertTrue(self.runtime.accepted)
        self.assertEqual(len(self.runtime.stages), 8)
        self.assertEqual(tuple(item.sequence for item in self.runtime.stages), tuple(range(1, 9)))
        self.assertEqual(self.release.state, WorkspaceFrontierReleaseState.READY)
        self.assertTrue(self.release.accepted)

    def test_replay_scenarios_thresholds_and_depth(self) -> None:
        second = replay_workspace_frontier(self.fixture, replay_id="workspace-frontier-test-replay-2")
        comparison = compare_workspace_frontier_replays(self.replay, second)
        self.assertTrue(comparison.accepted)
        self.assertEqual(comparison.drift_fields, ())
        self.assertTrue(workspace_frontier_replay_is_deterministic(self.fixture))
        matrix = build_workspace_frontier_scenario_matrix()
        self.assertEqual(len(matrix.scenarios), 33)
        self.assertEqual(len(matrix.dimensions), 6)
        self.assertTrue(matrix.review_scenarios)
        self.assertEqual(set(matrix.by_operation), {item.value for item in WorkspaceFrontierOperation})
        threshold = build_workspace_frontier_threshold_report()
        self.assertEqual(len(default_workspace_frontier_threshold_profiles()), 4)
        self.assertEqual(len(threshold.probes), 972)
        self.assertEqual(len(threshold.accepted_probe_ids) + len(threshold.review_probe_ids), 972)
        self.assertTrue(audit_workspace_frontier_depth().accepted)

    def test_artifacts_invariants_and_observability(self) -> None:
        inventory = build_workspace_frontier_artifact_inventory(self.fixture.fixture_id, self.fixture.content_address, self.evaluation, self.metrics, self.quality, self.runtime, self.runtime.bundle, self.release)
        self.assertEqual(len(inventory.artifacts), 7)
        self.assertEqual(inventory.root_artifact_id, "workspace-artifact-release")
        self.assertEqual(len(inventory.by_kind(WorkspaceFrontierArtifactKind.RELEASE)), 1)
        observations = workspace_frontier_observation_map(context_preserved=True, positive_control_separated=True, workspace_addressed=True, sections_retained=True, facets_retained=True, pagination_bounded=True, interval_bounded=True, absence_explicit=True, parse_issues_visible=True, accessibility_retained=True)
        invariant = run_workspace_frontier_invariants(observations)
        self.assertTrue(invariant.accepted)
        self.assertEqual(len(default_workspace_frontier_invariants()), 10)
        self.assertTrue(workspace_frontier_invariants_from_execution(self.fixture, self.evaluation).accepted)
        events = observe_workspace_frontier(self.runtime, self.evaluation)
        self.assertTrue(events.accepted)
        self.assertEqual(len(events.events), 24)
        self.assertEqual(len(events.by_type("runtime_stage")), 8)

    def test_review_view_and_queue_keep_issue_rows(self) -> None:
        self.assertEqual(len(self.view.rows), 16)
        self.assertEqual(len(self.view.accepted_rows()), 3)
        self.assertEqual(len(self.view.issue_rows()), 13)
        self.assertEqual(len(self.queue.items), 16)
        self.assertEqual(len(self.queue.ready_items), 3)
        self.assertEqual(len(self.queue.held_items), 13)
        self.assertTrue(self.queue.accepted)
        self.assertEqual(len(self.queue.issue_codes), 8)
        self.assertTrue(all(item.disposition is WorkspaceFrontierReviewDisposition.WITHHOLD for item in self.queue.items if "context_mismatch" in item.issue_codes))

    def test_exports_are_stable_and_include_public_boundary(self) -> None:
        csv_text = export_workspace_frontier_review_csv(self.view)
        self.assertEqual(len(csv_text.splitlines()), 17)
        self.assertIn("C04-POS-001", csv_text)
        self.assertTrue(export_workspace_frontier_json(self.release).endswith("\n"))
        self.assertTrue(export_workspace_frontier_canonical(self.release).startswith("{"))
        manifest = export_workspace_frontier_manifest(self.runtime, self.release)
        self.assertEqual(manifest["public_boundary"], "public_aggregate_non_patient")
        self.assertTrue(manifest["accepted"])

    def test_fixture_json_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workspace-frontier.json"
            path.write_text(json.dumps(self.fixture.to_dict()), encoding="utf-8")
            loaded = load_workspace_frontier_fixture(path)
        self.assertEqual(loaded.fixture_id, self.fixture.fixture_id)
        self.assertEqual(loaded.content_address, self.fixture.content_address)
        self.assertEqual(evaluate_workspace_frontier_fixture(loaded).content_address, self.evaluation.content_address)

    def test_adapters_report_required_fields_and_input_addresses(self) -> None:
        registry = default_workspace_frontier_adapters()
        self.assertEqual(len(registry.adapters), 4)
        case_adapter = registry.by_operation(WorkspaceFrontierOperation.CASE_WORKSPACE)
        receipt = adapt_workspace_frontier_input(case_adapter, {"case_id": "case", "subject_id": "aggregate", "context_key": self.fixture.context_key, "variants": []})
        self.assertTrue(receipt.accepted)
        self.assertEqual(receipt.missing_fields, ())
        incomplete = adapt_workspace_frontier_input(case_adapter, {"case_id": "case"})
        self.assertFalse(incomplete.accepted)
        self.assertIn("variants", incomplete.missing_fields)
        self.assertTrue(incomplete.input_address.startswith("sha256:"))

    def test_every_execution_is_addressed_and_role_bound(self) -> None:
        for record, execution in zip(self.fixture.records, self.evaluation.executions, strict=True):
            self.assertEqual(record.record_id, execution.record_id)
            self.assertEqual(record.operation, execution.operation)
            self.assertTrue(execution.content_address.startswith("sha256:"))
            self.assertEqual(execution.accepted, record.role is WorkspaceFrontierRole.POSITIVE)

    def test_control_records_are_not_promoted_by_expected_states(self) -> None:
        for record in self.fixture.control_records:
            execution = self.evaluation.execution_map()[record.record_id]
            self.assertFalse(execution.accepted)
            self.assertEqual(execution.state, record.expected_state)

    def test_public_data_payloads_have_explicit_accessibility_shape(self) -> None:
        for record in self.fixture.records:
            if record.operation is WorkspaceFrontierOperation.VARIANT_EXPLORER:
                self.assertIn("case", record.payload)
            else:
                self.assertIn("accessibility", record.payload)

    def test_release_addresses_are_unique(self) -> None:
        addresses = self.release.artifact_addresses
        self.assertEqual(len(addresses), len(set(addresses)))
        self.assertTrue(all(address.startswith("sha256:") for address in addresses))


if __name__ == "__main__":
    unittest.main()
