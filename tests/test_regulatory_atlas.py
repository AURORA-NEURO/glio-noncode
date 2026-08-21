from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.regulatory_atlas_bundle import (
    RegulatoryAtlasBundleBuilder,
    RegulatoryAtlasBundleFormat,
)
from glio_noncode.regulatory_atlas_contracts import default_regulatory_atlas_contracts
from glio_noncode.regulatory_atlas_fixture_eval import evaluate_regulatory_atlas_fixture
from glio_noncode.regulatory_atlas_lineage import (
    RegulatoryAtlasNodeKind,
    build_regulatory_atlas_lineage,
)
from glio_noncode.regulatory_atlas_metrics import (
    build_regulatory_atlas_metrics,
    render_regulatory_atlas_metrics,
    verify_regulatory_atlas_metrics,
)
from glio_noncode.regulatory_atlas_policy import (
    RegulatoryAtlasPolicyDisposition,
    default_regulatory_atlas_policy_rules,
    evaluate_regulatory_atlas_policy,
    verify_regulatory_atlas_policy,
)
from glio_noncode.regulatory_atlas_public_data import (
    REGULATORY_ATLAS_CONTEXT_KEY,
    REGULATORY_ATLAS_CONTROL_COUNT,
    REGULATORY_ATLAS_FIXTURE_VERSION,
    REGULATORY_ATLAS_POSITIVE_COUNT,
    audit_regulatory_atlas_data,
    build_regulatory_atlas_catalog,
    default_regulatory_atlas_fixture,
    load_regulatory_atlas_fixture,
)
from glio_noncode.regulatory_atlas_quality_gate import evaluate_regulatory_atlas_quality_gate
from glio_noncode.regulatory_atlas_reconciliation import reconcile_regulatory_atlas_views
from glio_noncode.regulatory_atlas_release import (
    RegulatoryAtlasReleaseState,
    build_regulatory_atlas_release_manifest,
    verify_regulatory_atlas_release_manifest,
)
from glio_noncode.regulatory_atlas_replay import replay_regulatory_atlas_evaluation
from glio_noncode.regulatory_atlas_runtime import (
    RegulatoryAtlasPipelineRequest,
    run_regulatory_atlas_pipeline,
    run_regulatory_atlas_pipeline_file,
)
from glio_noncode.regulatory_atlas_scenario_matrix import evaluate_regulatory_atlas_scenarios


class RegulatoryAtlasFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_regulatory_atlas_fixture()
        self.evaluation = evaluate_regulatory_atlas_fixture(self.fixture)

    def test_fixture_has_public_boundary_and_balanced_records(self) -> None:
        self.assertEqual(self.fixture.fixture_version, REGULATORY_ATLAS_FIXTURE_VERSION)
        self.assertEqual(self.fixture.context_key, REGULATORY_ATLAS_CONTEXT_KEY)
        self.assertEqual(len(self.fixture.sources), 5)
        self.assertEqual(len(self.fixture.records), 16)
        self.assertEqual(len(self.fixture.positive_records), REGULATORY_ATLAS_POSITIVE_COUNT)
        self.assertEqual(len(self.fixture.control_records), REGULATORY_ATLAS_CONTROL_COUNT)
        self.assertTrue(all(source.uri.startswith("https://") for source in self.fixture.sources))
        self.assertTrue(all("subject_id" not in record.payload for record in self.fixture.records))

    def test_catalog_is_unique_and_covers_all_operations(self) -> None:
        catalog = build_regulatory_atlas_catalog(self.fixture)
        self.assertEqual(len(catalog.source_ids), 5)
        self.assertEqual(len(catalog.record_ids), 16)
        self.assertEqual(len(catalog.operations), 4)
        self.assertEqual(len(set(catalog.record_ids)), 16)

    def test_public_data_audit_passes(self) -> None:
        report = audit_regulatory_atlas_data(self.fixture)
        self.assertTrue(report.accepted)
        self.assertEqual(report.failed_check_ids, ())
        self.assertGreaterEqual(len(report.checks), 20)

    def test_descriptor_load_is_explicit(self) -> None:
        self.assertEqual(
            load_regulatory_atlas_fixture({"fixture": "default_regulatory_atlas_fixture"}),
            self.fixture,
        )
        self.assertEqual(
            load_regulatory_atlas_fixture({"fixture_id": "regulatory-atlas-public-aggregate"}),
            self.fixture,
        )

    def test_descriptor_rejects_unknown_fixture(self) -> None:
        with self.assertRaises(ValidationError):
            load_regulatory_atlas_fixture({"fixture": "unknown"})


class RegulatoryAtlasExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_regulatory_atlas_fixture()
        self.report = evaluate_regulatory_atlas_fixture(self.fixture)

    def test_evaluation_is_deep_and_accepted(self) -> None:
        self.assertTrue(self.report.accepted)
        self.assertEqual(len(self.report.receipts), 16)
        self.assertEqual(len(self.report.checks), 120)
        self.assertEqual(self.report.positive_count, 4)
        self.assertEqual(self.report.control_count, 12)
        self.assertEqual(self.report.failed_check_ids, ())

    def test_expected_states_cover_positive_and_review_controls(self) -> None:
        states = {receipt.record_id: receipt.adapter_state for receipt in self.report.receipts}
        self.assertEqual(states["C01-POS-001"], "supported")
        self.assertEqual(states["C01-CTRL-003"], "abstained")
        self.assertEqual(states["C02-CTRL-001"], "out_of_domain")
        self.assertEqual(states["C02-CTRL-002"], "absent")
        self.assertEqual(states["C02-CTRL-003"], "ambiguous")
        self.assertEqual(states["C03-POS-001"], "supported")
        self.assertEqual(states["C04-POS-001"], "supported")

    def test_issue_codes_are_preserved(self) -> None:
        by_id = {receipt.record_id: receipt for receipt in self.report.receipts}
        self.assertIn("invalid_ccre_row", by_id["C01-CTRL-001"].observed_issue_codes)
        self.assertIn("invalid_ccre_row", by_id["C01-CTRL-002"].observed_issue_codes)
        self.assertIn("invalid_ccre_json", by_id["C01-CTRL-003"].observed_issue_codes)
        self.assertIn("ccre_context_mismatch", by_id["C02-CTRL-001"].observed_issue_codes)
        self.assertIn("no_compatible_ccre", by_id["C03-CTRL-002"].observed_issue_codes)
        self.assertIn("ambiguous_ccre_match", by_id["C04-CTRL-003"].observed_issue_codes)

    def test_receipts_are_sanitized(self) -> None:
        forbidden = {"payload", "input_text", "records", "restrictions", "subject_id"}
        for receipt in self.report.receipts:
            self.assertFalse(forbidden & set(receipt.summary))
            self.assertTrue(receipt.content_address.startswith("sha256:"))

    def test_contract_registry_has_four_complete_contracts(self) -> None:
        registry = default_regulatory_atlas_contracts()
        self.assertEqual(len(registry.contracts), 4)
        self.assertEqual(len(registry.manifest()["contracts"]), 4)
        for record in self.fixture.records:
            contract = registry.by_operation(record.operation)
            self.assertEqual(contract.validate_payload(record.payload), ())


class RegulatoryAtlasReplayScenarioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_regulatory_atlas_fixture()
        self.evaluation = evaluate_regulatory_atlas_fixture(self.fixture)

    def test_replay_is_deterministic(self) -> None:
        report = replay_regulatory_atlas_evaluation(self.evaluation, fixture=self.fixture)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 13)
        self.assertEqual(report.current_evaluation_address, self.evaluation.content_address)
        self.assertEqual(report.failed_check_ids, ())

    def test_scenario_matrix_covers_each_review_state(self) -> None:
        report = evaluate_regulatory_atlas_scenarios(self.fixture, report=self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.results), 13)
        scenario_ids = {result.scenario_id for result in report.results}
        self.assertIn("parse-invalid-json", scenario_ids)
        self.assertIn("brain-context-mismatch", scenario_ids)
        self.assertIn("adult-ambiguous", scenario_ids)
        self.assertIn("pediatric-absent", scenario_ids)


class RegulatoryAtlasPolicyLineageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_regulatory_atlas_fixture()
        self.evaluation = evaluate_regulatory_atlas_fixture(self.fixture)

    def test_policy_rules_are_explicit_and_pass(self) -> None:
        rules = default_regulatory_atlas_policy_rules()
        report = evaluate_regulatory_atlas_policy(self.fixture, self.evaluation, rules=rules)
        self.assertTrue(report.accepted)
        self.assertEqual(len(rules), 12)
        self.assertEqual(len(report.checks), 12)
        self.assertEqual(verify_regulatory_atlas_policy(report), ())
        self.assertTrue(
            all(
                check.disposition is RegulatoryAtlasPolicyDisposition.PASS
                for check in report.checks
            )
        )

    def test_lineage_graph_is_closed_and_sanitized(self) -> None:
        graph = build_regulatory_atlas_lineage(self.evaluation, fixture=self.fixture)
        audit = graph.audit(self.evaluation)
        self.assertTrue(audit.passed)
        self.assertEqual(audit.node_count, 157)
        self.assertEqual(audit.edge_count, 157)
        self.assertEqual(
            sum(node.kind is RegulatoryAtlasNodeKind.SOURCE for node in graph.nodes), 5
        )
        self.assertEqual(
            sum(node.kind is RegulatoryAtlasNodeKind.RECORD for node in graph.nodes), 16
        )
        self.assertEqual(
            sum(node.kind is RegulatoryAtlasNodeKind.RECEIPT for node in graph.nodes), 16
        )
        self.assertEqual(
            sum(node.kind is RegulatoryAtlasNodeKind.CHECK for node in graph.nodes), 120
        )
        self.assertTrue(all("payload" not in node.attributes for node in graph.nodes))

    def test_lineage_detects_fixture_drift(self) -> None:
        graph = build_regulatory_atlas_lineage(self.evaluation, fixture=self.fixture)
        drifted = replace(graph, fixture_id="different-fixture")
        self.assertIn("fixture-id", drifted.audit(self.evaluation).failed_check_ids)


class RegulatoryAtlasMetricsBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_regulatory_atlas_fixture()
        self.evaluation = evaluate_regulatory_atlas_fixture(self.fixture)
        self.builder = RegulatoryAtlasBundleBuilder()

    def test_metrics_are_balanced_and_sanitized(self) -> None:
        report = build_regulatory_atlas_metrics(self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(report.receipt_count, 16)
        self.assertEqual(report.check_count, 120)
        self.assertEqual(len(report.operation_metrics), 4)
        self.assertEqual(verify_regulatory_atlas_metrics(report), ())
        self.assertEqual(render_regulatory_atlas_metrics(report)["totals"]["positive"], 4)

    def test_bundle_formats_and_accepted_only(self) -> None:
        for output_format in RegulatoryAtlasBundleFormat:
            bundle = self.builder.build(
                self.evaluation,
                fixture=self.fixture,
                output_format=output_format,
                accepted_only=True,
            )
            self.assertEqual(self.builder.verify(bundle), ())
            self.assertEqual(len(bundle.entries), 4)
            rendered = self.builder.render(bundle)
            self.assertTrue(rendered)
            if output_format is RegulatoryAtlasBundleFormat.JSON:
                self.assertEqual(len(json.loads(rendered)["entries"]), 4)
            if output_format is RegulatoryAtlasBundleFormat.CSV:
                self.assertIn("record_id,operation,role,state", rendered)
            if output_format is RegulatoryAtlasBundleFormat.MARKDOWN:
                self.assertIn("# Regulatory atlas bundle", rendered)

    def test_full_bundle_keeps_review_controls_visible(self) -> None:
        bundle = self.builder.build(self.evaluation, fixture=self.fixture)
        self.assertEqual(self.builder.verify(bundle), ())
        self.assertEqual(len(bundle.entries), 16)
        self.assertTrue(any(entry.role == "control" for entry in bundle.entries))

    def test_bundle_write_rejects_mutated_address(self) -> None:
        bundle = self.builder.build(self.evaluation, fixture=self.fixture, accepted_only=True)
        mutated = replace(bundle, fixture_id="mutated")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValidationError):
                self.builder.write(mutated, Path(directory) / "bundle.json")


class RegulatoryAtlasQualityRuntimeReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_regulatory_atlas_fixture()
        self.evaluation = evaluate_regulatory_atlas_fixture(self.fixture)

    def test_quality_gate_has_all_expected_floors(self) -> None:
        report = evaluate_regulatory_atlas_quality_gate(self.fixture)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 25)
        self.assertEqual(report.failed_check_ids, ())

    def test_reconciliation_closes_all_views(self) -> None:
        data = audit_regulatory_atlas_data(self.fixture)
        replay = replay_regulatory_atlas_evaluation(self.evaluation, fixture=self.fixture)
        scenarios = evaluate_regulatory_atlas_scenarios(self.fixture, report=self.evaluation)
        lineage = build_regulatory_atlas_lineage(self.evaluation, fixture=self.fixture)
        report = reconcile_regulatory_atlas_views(
            self.fixture, data, self.evaluation, replay, scenarios, lineage
        )
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 17)

    def test_runtime_publishes_nine_stages(self) -> None:
        request = RegulatoryAtlasPipelineRequest({"fixture": "default_regulatory_atlas_fixture"})
        report = run_regulatory_atlas_pipeline(request)
        self.assertTrue(report.published)
        self.assertEqual(len(report.stages), 9)
        self.assertEqual(report.failed_stages, ())

    def test_runtime_file_supports_descriptor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "request.json"
            path.write_text(
                json.dumps({"fixture": "default_regulatory_atlas_fixture", "accepted_only": True}),
                encoding="utf-8",
            )
            report = run_regulatory_atlas_pipeline_file(path)
        self.assertTrue(report.published)

    def test_release_manifest_is_publishable(self) -> None:
        quality = evaluate_regulatory_atlas_quality_gate(self.fixture)
        replay = replay_regulatory_atlas_evaluation(self.evaluation, fixture=self.fixture)
        bundle = RegulatoryAtlasBundleBuilder().build(
            self.evaluation, fixture=self.fixture, accepted_only=True
        )
        manifest = build_regulatory_atlas_release_manifest(
            self.evaluation, quality, bundle, replay, fixture=self.fixture
        )
        self.assertEqual(manifest.state, RegulatoryAtlasReleaseState.PUBLISHED)
        self.assertTrue(manifest.publishable)
        self.assertEqual(verify_regulatory_atlas_release_manifest(manifest), ())

    def test_release_address_detects_mutation(self) -> None:
        quality = evaluate_regulatory_atlas_quality_gate(self.fixture)
        replay = replay_regulatory_atlas_evaluation(self.evaluation, fixture=self.fixture)
        bundle = RegulatoryAtlasBundleBuilder().build(
            self.evaluation, fixture=self.fixture, accepted_only=True
        )
        manifest = build_regulatory_atlas_release_manifest(
            self.evaluation, quality, bundle, replay, fixture=self.fixture
        )
        mutated = replace(manifest, context_key="drifted")
        self.assertIn("manifest-address", verify_regulatory_atlas_release_manifest(mutated))


if __name__ == "__main__":
    unittest.main()
