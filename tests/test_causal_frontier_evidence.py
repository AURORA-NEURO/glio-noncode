"""Deep tests for the Domain 11 causal frontier evidence boundary."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.causal_frontier_contracts import default_causal_frontier_contracts
from glio_noncode.causal_frontier_exports import (
    export_causal_frontier_canonical,
    export_causal_frontier_json,
    export_causal_frontier_manifest,
    export_causal_frontier_review_csv,
)
from glio_noncode.causal_frontier_fixture_eval import (
    evaluate_causal_frontier_fixture,
    execute_causal_frontier_record,
)
from glio_noncode.causal_frontier_lineage import build_causal_frontier_lineage
from glio_noncode.causal_frontier_metrics import measure_causal_frontier
from glio_noncode.causal_frontier_observability import observe_causal_frontier
from glio_noncode.causal_frontier_policy import (
    CausalFrontierDecision,
    default_causal_frontier_policy,
)
from glio_noncode.causal_frontier_public_data import (
    CAUSAL_FRONTIER_CONTEXT_KEY,
    CAUSAL_FRONTIER_EVIDENCE_BOUNDARY,
    CausalFrontierOperation,
    CausalFrontierRole,
    audit_causal_frontier_data,
    build_causal_frontier_catalog,
    default_causal_frontier_fixture,
    load_causal_frontier_fixture,
)
from glio_noncode.causal_frontier_quality_gate import evaluate_causal_frontier_quality
from glio_noncode.causal_frontier_reconciliation import reconcile_causal_frontier
from glio_noncode.causal_frontier_release import (
    CausalFrontierReleaseState,
    build_causal_frontier_release_manifest,
)
from glio_noncode.causal_frontier_replay import (
    compare_causal_frontier_replays,
    replay_causal_frontier,
    replay_is_deterministic,
)
from glio_noncode.causal_frontier_runtime import run_causal_frontier_runtime
from glio_noncode.causal_frontier_scenario_matrix import build_causal_frontier_scenario_matrix
from glio_noncode.causal_frontier_schema import default_causal_frontier_schema
from glio_noncode.causal_frontier_views import build_causal_frontier_review_view


class CausalFrontierEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_causal_frontier_fixture()
        self.contracts = default_causal_frontier_contracts()
        self.schema = default_causal_frontier_schema()
        self.evaluation = evaluate_causal_frontier_fixture(self.fixture)
        self.policy = default_causal_frontier_policy(self.contracts)
        self.lineage = build_causal_frontier_lineage(self.fixture, self.evaluation)
        self.reconciliation = reconcile_causal_frontier(self.fixture, self.evaluation, self.policy)
        self.metrics = measure_causal_frontier(self.evaluation)
        self.gate = evaluate_causal_frontier_quality(
            self.fixture,
            self.evaluation,
            self.contracts,
            self.schema,
            self.lineage,
            self.reconciliation,
        )
        self.runtime = run_causal_frontier_runtime(self.fixture, run_id="test-runtime")
        self.replay = replay_causal_frontier(self.fixture, replay_id="test-replay")
        self.release = build_causal_frontier_release_manifest(
            self.runtime.bundle,
            self.gate,
            self.replay,
        )

    def test_fixture_declares_public_boundary_and_exact_context(self) -> None:
        self.assertEqual(self.fixture.context_key, CAUSAL_FRONTIER_CONTEXT_KEY)
        self.assertEqual(self.fixture.evidence_boundary, CAUSAL_FRONTIER_EVIDENCE_BOUNDARY)
        self.assertEqual(len(self.fixture.sources), 5)
        self.assertEqual(len(self.fixture.records), 16)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)
        self.assertTrue(all(source.uri.startswith("https://") for source in self.fixture.sources))
        self.assertTrue(all(source.content_address for source in self.fixture.sources))

    def test_data_audit_and_catalog_are_accepted(self) -> None:
        audit = audit_causal_frontier_data(self.fixture)
        catalog = build_causal_frontier_catalog(self.fixture)
        self.assertTrue(audit.accepted)
        self.assertEqual(audit.failed_check_ids, ())
        self.assertEqual(len(audit.checks), 12)
        self.assertEqual(set(catalog.operations), set(CausalFrontierOperation))
        self.assertEqual(len(catalog.record_ids), 16)
        self.assertEqual(len(catalog.source_ids), 5)

    def test_operation_distribution_has_one_positive_and_three_controls(self) -> None:
        for operation in CausalFrontierOperation:
            records = tuple(item for item in self.fixture.records if item.operation is operation)
            self.assertEqual(len(records), 4, operation)
            self.assertEqual(sum(item.role is CausalFrontierRole.POSITIVE for item in records), 1)
            self.assertEqual(sum(item.role is CausalFrontierRole.CONTROL for item in records), 3)

    def test_evaluation_has_120_checks_and_no_failures(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.checks), 120)
        self.assertEqual(self.evaluation.passed_checks, 120)
        self.assertEqual(self.evaluation.failed_check_ids, ())
        self.assertEqual(len(self.evaluation.executions), 16)

    def test_positive_records_are_accepted(self) -> None:
        positives = tuple(item for item in self.evaluation.executions if item.role is CausalFrontierRole.POSITIVE)
        self.assertEqual(len(positives), 4)
        self.assertTrue(all(item.accepted for item in positives))
        self.assertEqual({item.state for item in positives}, {"supported", "published"})
        self.assertTrue(all(item.error is None for item in positives))

    def test_controls_remain_non_accepted(self) -> None:
        controls = tuple(item for item in self.evaluation.executions if item.role is CausalFrontierRole.CONTROL)
        self.assertEqual(len(controls), 12)
        self.assertTrue(all(not item.accepted for item in controls))
        self.assertTrue(all(item.issue_codes for item in controls))
        self.assertTrue(all(item.error is None or item.state == "invalid" for item in controls))

    def test_posterior_operation_retains_named_components(self) -> None:
        execution = self.evaluation.execution_map()["C13-POS-001"]
        self.assertEqual(execution.state, "supported")
        self.assertIn("components", execution.output)
        self.assertEqual(len(execution.output["components"]), 2)
        self.assertEqual(execution.output["top_hypothesis_id"], "h1")
        self.assertTrue(all("raw_posterior" in row for row in execution.output["components"]))
        self.assertTrue(all("normalized_posterior" in row for row in execution.output["components"]))

    def test_posterior_controls_cover_zero_empty_and_invalid(self) -> None:
        expected = {
            "C13-CTRL-001": ("partial", ("zero_posterior_mass",)),
            "C13-CTRL-002": ("invalid", ("empty_posterior_input",)),
            "C13-CTRL-003": ("invalid", ("invalid_posterior_input",)),
        }
        for record_id, (state, issues) in expected.items():
            execution = self.evaluation.execution_map()[record_id]
            self.assertEqual(execution.state, state)
            self.assertEqual(execution.issue_codes, issues)

    def test_driver_operation_retains_evidence_rank_and_support(self) -> None:
        execution = self.evaluation.execution_map()["C14-POS-001"]
        self.assertEqual(execution.state, "supported")
        self.assertEqual(execution.output["top_driver_id"], "driver-1")
        self.assertEqual(len(execution.output["posteriors"]), 2)
        self.assertEqual(execution.output["posteriors"][0]["rank"], 1)
        self.assertIn("evidence_ids", execution.output["posteriors"][0])
        self.assertIn("posterior", execution.output["posteriors"][0])

    def test_driver_controls_cover_low_empty_and_invalid(self) -> None:
        self.assertEqual(self.evaluation.execution_map()["C14-CTRL-001"].issue_codes, ("low_driver_support",))
        self.assertEqual(self.evaluation.execution_map()["C14-CTRL-002"].issue_codes, ("empty_driver_input",))
        self.assertEqual(self.evaluation.execution_map()["C14-CTRL-003"].issue_codes, ("invalid_driver_input",))

    def test_selective_prediction_retains_threshold_and_abstention(self) -> None:
        positive = self.evaluation.execution_map()["C15-POS-001"]
        low = self.evaluation.execution_map()["C15-CTRL-001"]
        uncertain = self.evaluation.execution_map()["C15-CTRL-002"]
        self.assertEqual(positive.output["accepted_ids"], ["pred-1"])
        self.assertEqual(positive.output["abstained_ids"], [])
        self.assertEqual(low.issue_codes, ("selective_prediction_abstention",))
        self.assertEqual(uncertain.issue_codes, ("prediction_uncertainty_high", "selective_prediction_abstention"))
        self.assertEqual(low.output["abstained_ids"], ["pred-low"])
        self.assertEqual(uncertain.output["abstained_ids"], ["pred-uncertain"])

    def test_dossier_operation_is_a_manifest(self) -> None:
        positive = self.evaluation.execution_map()["C16-POS-001"]
        self.assertEqual(positive.state, "published")
        self.assertEqual(positive.output["dossier_id"], "dossier-1")
        self.assertEqual(positive.output["top_hypothesis_id"], "h1")
        self.assertEqual(len(positive.output["evidence_addresses"]), 2)
        self.assertTrue(positive.output["dossier_address"].startswith("sha256:"))

    def test_dossier_controls_reject_bad_top_empty_and_missing_address(self) -> None:
        self.assertEqual(self.evaluation.execution_map()["C16-CTRL-001"].issue_codes, ("invalid_dossier_input",))
        self.assertEqual(self.evaluation.execution_map()["C16-CTRL-002"].issue_codes, ("empty_dossier_input",))
        self.assertEqual(self.evaluation.execution_map()["C16-CTRL-003"].issue_codes, ("invalid_dossier_input",))

    def test_contracts_cover_all_operations_and_issue_codes(self) -> None:
        self.assertEqual({item.operation for item in self.contracts.contracts}, set(CausalFrontierOperation))
        self.assertEqual(len(self.contracts.issue_codes()), 11)
        for operation in CausalFrontierOperation:
            contract = self.contracts.by_operation(operation)
            self.assertTrue(contract.required_payload_fields)
            self.assertTrue(contract.prohibited_claims)
            self.assertTrue(contract.content_address)

    def test_schema_covers_fields_and_invariants(self) -> None:
        self.assertEqual(len(self.schema.operations), 4)
        self.assertEqual(len(self.schema.invariant_ids), 5)
        for operation in CausalFrontierOperation:
            schema = self.schema.by_operation(operation)
            self.assertIn("input_records", schema.field_names())
            self.assertIn("content_address", schema.field_names())
            self.assertTrue(schema.issue_codes)

    def test_policy_uses_positive_operation_paths_for_release(self) -> None:
        decisions = self.policy.decide(self.evaluation)
        self.assertEqual(len(decisions), 4)
        self.assertTrue(all(item.decision in {CausalFrontierDecision.ALLOW_REVIEW, CausalFrontierDecision.ALLOW_PUBLICATION} for item in decisions))
        self.assertEqual(
            next(item for item in decisions if item.operation is CausalFrontierOperation.DOSSIER_PUBLICATION).decision,
            CausalFrontierDecision.ALLOW_PUBLICATION,
        )

    def test_lineage_is_acyclic_and_has_terminal_receipts(self) -> None:
        self.assertTrue(self.lineage.acyclic)
        self.assertEqual(len(self.lineage.terminal_addresses), 16)
        self.assertEqual(len(self.lineage.edges), 36)
        self.assertGreaterEqual(len(self.lineage.node_addresses), 21)
        self.assertTrue(all(item.content_address for item in self.lineage.edges))

    def test_reconciliation_matches_every_expected_control(self) -> None:
        self.assertTrue(self.reconciliation.reconciled)
        self.assertEqual(self.reconciliation.mismatched_record_ids, ())
        self.assertEqual(len(self.reconciliation.items), 16)
        self.assertTrue(all(item.reconciled for item in self.reconciliation.items))

    def test_metrics_include_overall_and_operation_rates(self) -> None:
        self.assertEqual(len(self.metrics.metrics), 13)
        self.assertEqual(self.metrics.by_id("overall_check_pass_rate").value, 1.0)
        for operation in CausalFrontierOperation:
            self.assertEqual(self.metrics.by_id(f"{operation.value}_execution_acceptance").denominator, 4)
            self.assertTrue(self.metrics.by_id(f"{operation.value}_issue_free_rate").value >= 0)

    def test_quality_gate_has_layered_checks(self) -> None:
        self.assertTrue(self.gate.accepted)
        self.assertEqual(len(self.gate.checks), 12)
        self.assertEqual(self.gate.passed_count, 12)
        self.assertEqual(self.gate.blocking_check_ids, ())

    def test_runtime_has_ten_ordered_stages(self) -> None:
        self.assertTrue(self.runtime.accepted)
        self.assertEqual(len(self.runtime.stages), 10)
        self.assertEqual(tuple(item.sequence for item in self.runtime.stages), tuple(range(1, 11)))
        self.assertEqual(self.runtime.stage_ids[0], "data-audit")
        self.assertEqual(self.runtime.stage_ids[-1], "release-bundle")

    def test_replay_is_deterministic(self) -> None:
        second = replay_causal_frontier(self.fixture, replay_id="test-replay-2")
        comparison = compare_causal_frontier_replays(self.replay, second)
        self.assertTrue(comparison.accepted)
        self.assertEqual(comparison.drift_fields, ())
        self.assertTrue(replay_is_deterministic(self.fixture))

    def test_release_manifest_is_ready(self) -> None:
        self.assertEqual(self.release.state, CausalFrontierReleaseState.READY)
        self.assertTrue(self.release.accepted)
        self.assertTrue(self.release.allowed_uses)
        self.assertTrue(self.release.excluded_uses)
        self.assertTrue(all(item.evidence_address.startswith("sha256:") for item in self.release.checks))

    def test_scenario_matrix_has_threshold_crossings(self) -> None:
        matrix = build_causal_frontier_scenario_matrix()
        self.assertEqual(len(matrix.scenarios), 33)
        self.assertEqual(len(matrix.dimensions), 5)
        self.assertTrue(matrix.review_scenarios)
        self.assertTrue(matrix.publishable_scenarios)
        self.assertEqual({item.operation for item in matrix.scenarios}, set(CausalFrontierOperation))

    def test_observability_has_stage_and_execution_events(self) -> None:
        report = observe_causal_frontier(self.runtime, self.evaluation)
        self.assertEqual(len(report.events), 26)
        self.assertEqual(report.counter_map()["runtime_stage_count"], 10)
        self.assertEqual(report.counter_map()["execution_count"], 16)
        self.assertEqual(report.counter_map()["accepted_execution_count"], 4)
        self.assertTrue(all(event.receipt_address for event in report.events))

    def test_review_view_rows_preserve_controls(self) -> None:
        view = build_causal_frontier_review_view(
            self.fixture,
            self.evaluation,
            self.metrics,
            self.policy.decide(self.evaluation),
            self.release,
        )
        self.assertEqual(len(view.rows), 16)
        self.assertEqual(len(view.accepted_rows()), 4)
        self.assertEqual(len(view.issue_rows()), 12)
        csv_text = export_causal_frontier_review_csv(view)
        self.assertEqual(len(csv_text.splitlines()), 17)
        self.assertIn("C13-POS-001", csv_text)

    def test_json_exports_are_stable_and_canonical(self) -> None:
        text = export_causal_frontier_json(self.release)
        canonical = export_causal_frontier_canonical(self.release)
        manifest = export_causal_frontier_manifest(self.runtime.bundle, self.release)
        self.assertTrue(text.endswith("\n"))
        self.assertEqual(json.loads(text)["release_id"], "causal-frontier-release")
        self.assertTrue(canonical.startswith("{"))
        self.assertEqual(manifest["public_boundary"], CAUSAL_FRONTIER_EVIDENCE_BOUNDARY)

    def test_fixture_round_trip_through_json_file(self) -> None:
        payload = self.fixture.to_dict()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            loaded = load_causal_frontier_fixture(path)
        self.assertEqual(loaded.fixture_id, self.fixture.fixture_id)
        self.assertEqual(len(loaded.records), 16)
        self.assertEqual(loaded.records[0].operation, CausalFrontierOperation.POSTERIOR_DECOMPOSITION)

    def test_record_execution_is_repeatable(self) -> None:
        record = self.fixture.record_map()["C13-POS-001"]
        first = execute_causal_frontier_record(record)
        second = execute_causal_frontier_record(record)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.output, second.output)
        self.assertTrue(first.accepted)


if __name__ == "__main__":
    unittest.main()
