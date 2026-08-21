from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from glio_noncode.reference_governance_bundle import (
    ReferenceGovernanceBundleBuilder,
    ReferenceGovernanceBundleFormat,
)
from glio_noncode.reference_governance_contracts import default_reference_governance_contracts
from glio_noncode.reference_governance_fixture_eval import evaluate_reference_governance_fixture
from glio_noncode.reference_governance_lineage import build_reference_governance_lineage
from glio_noncode.reference_governance_metrics import (
    build_reference_governance_metrics,
    render_reference_governance_metrics,
    verify_reference_governance_metrics,
)
from glio_noncode.reference_governance_policy import (
    evaluate_reference_governance_policy,
    verify_reference_governance_policy,
)
from glio_noncode.reference_governance_public_data import (
    REFERENCE_GOVERNANCE_CONTEXT_KEY,
    ReferenceGovernanceOperation,
    audit_reference_governance_data,
    build_reference_governance_catalog,
    default_reference_governance_fixture,
    load_reference_governance_fixture,
)
from glio_noncode.reference_governance_quality_gate import (
    evaluate_reference_governance_quality_gate,
)
from glio_noncode.reference_governance_reconciliation import reconcile_reference_governance_views
from glio_noncode.reference_governance_release import (
    build_reference_governance_release_manifest,
    verify_reference_governance_release_manifest,
)
from glio_noncode.reference_governance_replay import (
    build_reference_governance_expectation,
    replay_reference_governance_evaluation,
)
from glio_noncode.reference_governance_runtime import (
    ReferenceGovernancePipelineRequest,
    run_reference_governance_pipeline,
)
from glio_noncode.reference_governance_scenario_matrix import (
    evaluate_reference_governance_scenarios,
)


class ReferenceGovernanceFixtureTests(unittest.TestCase):
    def test_fixture_has_public_boundary_and_balanced_operations(self) -> None:
        fixture = default_reference_governance_fixture()
        self.assertEqual(fixture.context_key, REFERENCE_GOVERNANCE_CONTEXT_KEY)
        self.assertEqual(len(fixture.sources), 5)
        self.assertEqual(len(fixture.records), 16)
        self.assertEqual(len(fixture.positive_records), 4)
        self.assertEqual(len(fixture.control_records), 12)
        self.assertEqual(
            {record.operation for record in fixture.records}, set(ReferenceGovernanceOperation)
        )
        self.assertTrue(
            all(
                sum(record.operation is op for record in fixture.records) == 4
                for op in ReferenceGovernanceOperation
            )
        )

    def test_fixture_descriptor_loader_is_explicit(self) -> None:
        fixture = load_reference_governance_fixture(
            {"fixture": "default_reference_governance_fixture"}
        )
        self.assertEqual(fixture.fixture_id, "reference-governance-public-aggregate")
        self.assertEqual(
            load_reference_governance_fixture(fixture.to_dict()).content_address,
            fixture.content_address,
        )

    def test_catalog_and_data_audit_are_addressed(self) -> None:
        fixture = default_reference_governance_fixture()
        catalog = build_reference_governance_catalog(fixture)
        audit = audit_reference_governance_data(fixture)
        self.assertEqual(len(catalog.source_ids), 5)
        self.assertEqual(len(catalog.record_ids), 16)
        self.assertTrue(audit.accepted)
        self.assertEqual(len(audit.checks), 23)
        self.assertEqual(audit.failed_check_ids, ())

    def test_data_audit_rejects_wrong_context(self) -> None:
        fixture = default_reference_governance_fixture()
        wrong = fixture.__class__(
            fixture.fixture_id,
            fixture.fixture_version,
            "GRCh37|wrong|context",
            fixture.evidence_boundary,
            fixture.sources,
            fixture.records,
            fixture.content_address,
        )
        audit = audit_reference_governance_data(wrong)
        self.assertFalse(audit.accepted)
        self.assertIn("fixture-context", audit.failed_check_ids)


class ReferenceGovernanceEvaluationTests(unittest.TestCase):
    def test_all_records_execute_with_expected_states(self) -> None:
        report = evaluate_reference_governance_fixture()
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.receipts), 16)
        self.assertEqual(len(report.checks), 120)
        self.assertEqual(report.positive_count, 4)
        self.assertEqual(report.control_count, 12)
        self.assertEqual(report.failed_check_ids, ())

    def test_operation_states_and_issue_boundaries_are_retained(self) -> None:
        report = evaluate_reference_governance_fixture()
        by_id = {receipt.record_id: receipt for receipt in report.receipts}
        self.assertEqual(by_id["C09-POS-001"].adapter_state, "supported")
        self.assertEqual(by_id["C09-CTRL-001"].adapter_state, "ambiguous")
        self.assertIn("gene_match_ambiguous", by_id["C09-CTRL-001"].observed_issue_codes)
        self.assertEqual(by_id["C10-POS-001"].summary["frequency_range"], (0.04, 0.04))
        self.assertEqual(by_id["C10-CTRL-001"].adapter_state, "contradictory")
        self.assertEqual(by_id["C11-CTRL-001"].adapter_state, "contradictory")
        self.assertIn("manifest_hash_mismatch", by_id["C11-CTRL-001"].observed_issue_codes)
        self.assertEqual(
            by_id["C12-CTRL-001"].summary["missing_resource_ids"], ("restricted-table",)
        )

    def test_receipts_are_sanitized(self) -> None:
        report = evaluate_reference_governance_fixture()
        for receipt in report.receipts:
            self.assertNotIn("records", receipt.summary)
            self.assertNotIn("resources", receipt.summary)
            self.assertNotIn("restrictions", receipt.summary)
            self.assertNotIn("queries", receipt.summary)

    def test_contract_registry_has_unique_operation_and_capability_ids(self) -> None:
        registry = default_reference_governance_contracts()
        self.assertEqual(len(registry.contracts), 4)
        self.assertEqual(len({contract.capability_id for contract in registry.contracts}), 4)
        self.assertEqual(len({contract.operation for contract in registry.contracts}), 4)
        self.assertEqual(
            registry.by_capability("GNC-D04-C09").operation, ReferenceGovernanceOperation.GENE_ALIAS
        )
        self.assertEqual(
            registry.by_operation(ReferenceGovernanceOperation.LICENSE_RESTRICTION).capability_id,
            "GNC-D04-C12",
        )


class ReferenceGovernanceEvidenceTests(unittest.TestCase):
    def test_replay_is_deterministic_and_has_floors(self) -> None:
        fixture = default_reference_governance_fixture()
        evaluation = evaluate_reference_governance_fixture(fixture)
        expectation = build_reference_governance_expectation(evaluation)
        replay = replay_reference_governance_evaluation(evaluation, fixture=fixture)
        self.assertEqual(
            expectation.record_ids, tuple(item.record_id for item in evaluation.receipts)
        )
        self.assertTrue(replay.accepted)
        self.assertEqual(len(replay.checks), 13)
        self.assertEqual(replay.failed_check_ids, ())

    def test_scenarios_cover_support_and_review_states(self) -> None:
        fixture = default_reference_governance_fixture()
        evaluation = evaluate_reference_governance_fixture(fixture)
        scenarios = evaluate_reference_governance_scenarios(fixture, report=evaluation)
        self.assertTrue(scenarios.accepted)
        self.assertGreaterEqual(len(scenarios.results), 12)
        self.assertIn("alias-ambiguity", {item.scenario_id for item in scenarios.results})
        self.assertIn("license-missing", {item.scenario_id for item in scenarios.results})

    def test_lineage_closes_and_has_expected_depth(self) -> None:
        fixture = default_reference_governance_fixture()
        evaluation = evaluate_reference_governance_fixture(fixture)
        graph = build_reference_governance_lineage(evaluation, fixture=fixture)
        audit = graph.audit(evaluation)
        self.assertTrue(audit.passed)
        self.assertEqual(audit.node_count, 157)
        self.assertEqual(audit.edge_count, 155)
        self.assertEqual(audit.failed_check_ids, ())
        self.assertTrue(all("payload" not in node.attributes for node in graph.nodes))

    def test_reconciliation_accepts_all_views(self) -> None:
        fixture = default_reference_governance_fixture()
        data = audit_reference_governance_data(fixture)
        evaluation = evaluate_reference_governance_fixture(fixture)
        replay = replay_reference_governance_evaluation(evaluation, fixture=fixture)
        scenarios = evaluate_reference_governance_scenarios(fixture, report=evaluation)
        graph = build_reference_governance_lineage(evaluation, fixture=fixture)
        report = reconcile_reference_governance_views(
            fixture, data, evaluation, replay, scenarios, graph
        )
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 16)

    def test_quality_gate_and_metrics_accept(self) -> None:
        fixture = default_reference_governance_fixture()
        quality = evaluate_reference_governance_quality_gate(fixture)
        metrics = build_reference_governance_metrics(quality.evaluation)
        self.assertTrue(quality.accepted)
        self.assertEqual(len(quality.checks), 25)
        self.assertTrue(metrics.accepted)
        self.assertEqual(verify_reference_governance_metrics(metrics), ())
        dashboard = render_reference_governance_metrics(metrics)
        self.assertEqual(dashboard["totals"]["receipts"], 16)
        self.assertEqual(len(dashboard["operations"]), 4)

    def test_policy_report_closes_explicit_boundary_rules(self) -> None:
        fixture = default_reference_governance_fixture()
        evaluation = evaluate_reference_governance_fixture(fixture)
        policy = evaluate_reference_governance_policy(fixture, evaluation)
        self.assertTrue(policy.accepted)
        self.assertEqual(len(policy.rules), 12)
        self.assertEqual(len(policy.checks), 12)
        self.assertEqual(verify_reference_governance_policy(policy), ())

    def test_bundle_formats_and_verification(self) -> None:
        fixture = default_reference_governance_fixture()
        evaluation = evaluate_reference_governance_fixture(fixture)
        builder = ReferenceGovernanceBundleBuilder()
        bundle = builder.build(evaluation, fixture=fixture, accepted_only=True)
        self.assertTrue(bundle.accepted)
        self.assertEqual(len(bundle.entries), 4)
        self.assertEqual(builder.verify(bundle), ())
        self.assertTrue(builder.render(bundle).endswith("\n"))
        self.assertGreater(len(builder.render(bundle).splitlines()), 20)
        for selected in ReferenceGovernanceBundleFormat:
            rendered = builder.render(
                bundle.__class__(
                    bundle.fixture_id,
                    bundle.fixture_version,
                    bundle.context_key,
                    selected,
                    bundle.accepted_only,
                    bundle.entries,
                    bundle.content_address,
                )
            )
            self.assertTrue(rendered)

    def test_bundle_mutation_is_detected(self) -> None:
        fixture = default_reference_governance_fixture()
        evaluation = evaluate_reference_governance_fixture(fixture)
        builder = ReferenceGovernanceBundleBuilder()
        bundle = builder.build(evaluation, fixture=fixture, accepted_only=True)
        entry = bundle.entries[0]
        mutated = entry.__class__(
            entry.record_id,
            entry.capability_id,
            entry.operation,
            entry.role,
            "ambiguous",
            entry.primary_count,
            entry.secondary_count,
            entry.issue_codes,
            entry.accepted,
            entry.content_address,
        )
        changed = bundle.__class__(
            bundle.fixture_id,
            bundle.fixture_version,
            bundle.context_key,
            bundle.output_format,
            bundle.accepted_only,
            (mutated,) + tuple(bundle.entries[1:]),
            bundle.content_address,
        )
        self.assertIn("entry-address:" + entry.record_id, builder.verify(changed))


class ReferenceGovernanceRuntimeTests(unittest.TestCase):
    def test_runtime_publishes_descriptor(self) -> None:
        request = ReferenceGovernancePipelineRequest(
            {"fixture": "default_reference_governance_fixture"}
        )
        report = run_reference_governance_pipeline(request)
        self.assertTrue(report.published)
        self.assertEqual(len(report.stages), 9)
        self.assertEqual(report.failed_stages, ())

    def test_runtime_rejects_context_drift(self) -> None:
        request = ReferenceGovernancePipelineRequest(
            {"fixture": "default_reference_governance_fixture"}, expected_context_key="wrong"
        )
        report = run_reference_governance_pipeline(request)
        self.assertFalse(report.published)
        self.assertIn("context", report.failed_stages)

    def test_release_manifest_is_publishable_and_addressed(self) -> None:
        fixture = default_reference_governance_fixture()
        evaluation = evaluate_reference_governance_fixture(fixture)
        quality = evaluate_reference_governance_quality_gate(fixture)
        replay = replay_reference_governance_evaluation(evaluation, fixture=fixture)
        bundle = ReferenceGovernanceBundleBuilder().build(
            evaluation, fixture=fixture, accepted_only=True
        )
        manifest = build_reference_governance_release_manifest(
            evaluation, quality, bundle, replay, fixture=fixture
        )
        self.assertTrue(manifest.publishable)
        self.assertEqual(manifest.state.value, "published")
        self.assertEqual(verify_reference_governance_release_manifest(manifest), ())
        self.assertEqual(len(manifest.checks), 12)

    def test_release_manifest_write_round_trip(self) -> None:
        fixture = default_reference_governance_fixture()
        evaluation = evaluate_reference_governance_fixture(fixture)
        quality = evaluate_reference_governance_quality_gate(fixture)
        replay = replay_reference_governance_evaluation(evaluation, fixture=fixture)
        bundle = ReferenceGovernanceBundleBuilder().build(
            evaluation, fixture=fixture, accepted_only=True
        )
        manifest = build_reference_governance_release_manifest(
            evaluation, quality, bundle, replay, fixture=fixture
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "release.json"
            path.write_text(manifest.to_dict().__repr__(), encoding="utf-8")
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
