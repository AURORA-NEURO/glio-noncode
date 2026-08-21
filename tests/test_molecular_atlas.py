from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.molecular_atlas_bundle import (
    MolecularAtlasBundleBuilder,
    MolecularAtlasBundleFormat,
)
from glio_noncode.molecular_atlas_contracts import default_molecular_atlas_contracts
from glio_noncode.molecular_atlas_fixture_eval import evaluate_molecular_atlas_fixture
from glio_noncode.molecular_atlas_lineage import (
    MolecularAtlasNodeKind,
    build_molecular_atlas_lineage,
)
from glio_noncode.molecular_atlas_metrics import (
    build_molecular_atlas_metrics,
    render_molecular_atlas_metrics,
    verify_molecular_atlas_metrics,
)
from glio_noncode.molecular_atlas_policy import (
    MolecularAtlasPolicyDisposition,
    default_molecular_atlas_policy_rules,
    evaluate_molecular_atlas_policy,
    verify_molecular_atlas_policy,
)
from glio_noncode.molecular_atlas_public_data import (
    MOLECULAR_ATLAS_CONTEXT_KEY,
    MOLECULAR_ATLAS_FIXTURE_VERSION,
    audit_molecular_atlas_data,
    build_molecular_atlas_catalog,
    default_molecular_atlas_fixture,
    load_molecular_atlas_fixture,
)
from glio_noncode.molecular_atlas_quality_gate import evaluate_molecular_atlas_quality_gate
from glio_noncode.molecular_atlas_reconciliation import reconcile_molecular_atlas_views
from glio_noncode.molecular_atlas_release import (
    MolecularAtlasReleaseState,
    build_molecular_atlas_release_manifest,
    verify_molecular_atlas_release_manifest,
)
from glio_noncode.molecular_atlas_replay import replay_molecular_atlas_evaluation
from glio_noncode.molecular_atlas_runtime import (
    MolecularAtlasPipelineRequest,
    run_molecular_atlas_pipeline,
    run_molecular_atlas_pipeline_file,
)
from glio_noncode.molecular_atlas_scenario_matrix import evaluate_molecular_atlas_scenarios


class MolecularAtlasFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_molecular_atlas_fixture()

    def test_fixture_has_public_boundary_and_balanced_records(self) -> None:
        self.assertEqual(self.fixture.fixture_version, MOLECULAR_ATLAS_FIXTURE_VERSION)
        self.assertEqual(self.fixture.context_key, MOLECULAR_ATLAS_CONTEXT_KEY)
        self.assertEqual(len(self.fixture.sources), 5)
        self.assertEqual(len(self.fixture.records), 16)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)
        self.assertTrue(all(source.uri.startswith("https://") for source in self.fixture.sources))
        self.assertTrue(
            all(
                not {"subject_id", "patient_id", "donor_id", "sample_id"} & set(record.payload)
                for record in self.fixture.records
            )
        )

    def test_catalog_covers_four_operations(self) -> None:
        catalog = build_molecular_atlas_catalog(self.fixture)
        self.assertEqual(len(catalog.source_ids), 5)
        self.assertEqual(len(catalog.record_ids), 16)
        self.assertEqual(len(catalog.operations), 4)
        self.assertEqual(len(set(catalog.record_ids)), 16)

    def test_data_audit_passes(self) -> None:
        report = audit_molecular_atlas_data(self.fixture)
        self.assertTrue(report.accepted)
        self.assertEqual(report.failed_check_ids, ())
        self.assertGreaterEqual(len(report.checks), 20)

    def test_descriptor_load_is_explicit(self) -> None:
        self.assertEqual(
            load_molecular_atlas_fixture({"fixture": "default_molecular_atlas_fixture"}),
            self.fixture,
        )
        self.assertEqual(
            load_molecular_atlas_fixture({"fixture_id": "molecular-atlas-public-aggregate"}),
            self.fixture,
        )
        with self.assertRaises(ValidationError):
            load_molecular_atlas_fixture({"fixture": "unknown"})


class MolecularAtlasExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_molecular_atlas_fixture()
        self.report = evaluate_molecular_atlas_fixture(self.fixture)

    def test_evaluation_is_deep_and_accepted(self) -> None:
        self.assertTrue(self.report.accepted)
        self.assertEqual(len(self.report.receipts), 16)
        self.assertEqual(len(self.report.checks), 120)
        self.assertEqual(self.report.positive_count, 4)
        self.assertEqual(self.report.control_count, 12)
        self.assertEqual(self.report.failed_check_ids, ())

    def test_state_families_remain_separate(self) -> None:
        by_id = {receipt.record_id: receipt for receipt in self.report.receipts}
        self.assertEqual(by_id["C05-POS-001"].adapter_state, "supported")
        self.assertEqual(by_id["C06-POS-001"].adapter_state, "supported")
        self.assertEqual(by_id["C07-POS-001"].adapter_state, "supported")
        self.assertEqual(by_id["C05-CTRL-001"].adapter_state, "out_of_domain")
        self.assertEqual(by_id["C06-CTRL-002"].adapter_state, "abstained")
        self.assertEqual(by_id["C07-CTRL-003"].adapter_state, "ambiguous")

    def test_histone_states_and_issue_codes_are_visible(self) -> None:
        by_id = {receipt.record_id: receipt for receipt in self.report.receipts}
        self.assertEqual(by_id["C08-POS-001"].adapter_state, "supported")
        self.assertIn("invalid_histone_row", by_id["C08-CTRL-001"].observed_issue_codes)
        self.assertIn("histone_signal_disagreement", by_id["C08-CTRL-002"].observed_issue_codes)
        self.assertIn("histone_single_replicate", by_id["C08-CTRL-003"].observed_issue_codes)

    def test_receipts_are_sanitized(self) -> None:
        forbidden = {"payload", "input_text", "records", "restrictions", "subject_id"}
        for receipt in self.report.receipts:
            self.assertFalse(forbidden & set(receipt.summary))
            self.assertTrue(receipt.content_address.startswith("sha256:"))

    def test_contract_registry_is_complete(self) -> None:
        registry = default_molecular_atlas_contracts()
        self.assertEqual(len(registry.contracts), 4)
        self.assertEqual(len(registry.manifest()["contracts"]), 4)
        for record in self.fixture.records:
            self.assertEqual(
                registry.by_operation(record.operation).validate_payload(record.payload), ()
            )


class MolecularAtlasReplayScenarioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_molecular_atlas_fixture()
        self.evaluation = evaluate_molecular_atlas_fixture(self.fixture)

    def test_replay_is_deterministic(self) -> None:
        report = replay_molecular_atlas_evaluation(self.evaluation, fixture=self.fixture)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 13)
        self.assertEqual(report.current_evaluation_address, self.evaluation.content_address)

    def test_scenario_matrix_covers_all_families(self) -> None:
        report = evaluate_molecular_atlas_scenarios(self.fixture, report=self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.results), 15)
        scenario_ids = {result.scenario_id for result in report.results}
        for expected in (
            "idh-mutant-supported",
            "idh-wildtype-ambiguous",
            "h3k27-context-mismatch",
            "histone-disagreement",
            "histone-single-replicate",
        ):
            self.assertIn(expected, scenario_ids)


class MolecularAtlasPolicyLineageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_molecular_atlas_fixture()
        self.evaluation = evaluate_molecular_atlas_fixture(self.fixture)

    def test_policy_rules_are_explicit_and_pass(self) -> None:
        rules = default_molecular_atlas_policy_rules()
        report = evaluate_molecular_atlas_policy(self.fixture, self.evaluation, rules=rules)
        self.assertTrue(report.accepted)
        self.assertEqual(len(rules), 12)
        self.assertEqual(verify_molecular_atlas_policy(report), ())
        self.assertTrue(
            all(
                check.disposition is MolecularAtlasPolicyDisposition.PASS for check in report.checks
            )
        )

    def test_lineage_graph_is_closed_and_sanitized(self) -> None:
        graph = build_molecular_atlas_lineage(self.evaluation, fixture=self.fixture)
        audit = graph.audit(self.evaluation)
        self.assertTrue(audit.passed)
        self.assertEqual(audit.node_count, 157)
        self.assertEqual(audit.edge_count, 158)
        self.assertEqual(sum(node.kind is MolecularAtlasNodeKind.SOURCE for node in graph.nodes), 5)
        self.assertEqual(
            sum(node.kind is MolecularAtlasNodeKind.RECORD for node in graph.nodes), 16
        )
        self.assertEqual(
            sum(node.kind is MolecularAtlasNodeKind.RECEIPT for node in graph.nodes), 16
        )
        self.assertEqual(
            sum(node.kind is MolecularAtlasNodeKind.CHECK for node in graph.nodes), 120
        )
        self.assertTrue(all("payload" not in node.attributes for node in graph.nodes))

    def test_lineage_detects_fixture_drift(self) -> None:
        graph = build_molecular_atlas_lineage(self.evaluation, fixture=self.fixture)
        drifted = replace(graph, fixture_id="different-fixture")
        self.assertIn("fixture-id", drifted.audit(self.evaluation).failed_check_ids)


class MolecularAtlasMetricsBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_molecular_atlas_fixture()
        self.evaluation = evaluate_molecular_atlas_fixture(self.fixture)
        self.builder = MolecularAtlasBundleBuilder()

    def test_metrics_are_balanced_and_sanitized(self) -> None:
        report = build_molecular_atlas_metrics(self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(report.receipt_count, 16)
        self.assertEqual(report.check_count, 120)
        self.assertEqual(len(report.operation_metrics), 4)
        self.assertEqual(verify_molecular_atlas_metrics(report), ())
        self.assertEqual(render_molecular_atlas_metrics(report)["totals"]["positive"], 4)

    def test_bundle_formats_and_accepted_only(self) -> None:
        for output_format in MolecularAtlasBundleFormat:
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
            if output_format is MolecularAtlasBundleFormat.JSON:
                self.assertEqual(len(json.loads(rendered)["entries"]), 4)
            if output_format is MolecularAtlasBundleFormat.CSV:
                self.assertIn("record_id,operation,role,state", rendered)
            if output_format is MolecularAtlasBundleFormat.MARKDOWN:
                self.assertIn("# Molecular atlas bundle", rendered)

    def test_full_bundle_keeps_controls_visible(self) -> None:
        bundle = self.builder.build(self.evaluation, fixture=self.fixture)
        self.assertEqual(self.builder.verify(bundle), ())
        self.assertEqual(len(bundle.entries), 16)
        self.assertTrue(any(entry.role == "control" for entry in bundle.entries))

    def test_bundle_write_rejects_mutated_address(self) -> None:
        bundle = self.builder.build(self.evaluation, fixture=self.fixture, accepted_only=True)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValidationError):
                self.builder.write(
                    replace(bundle, fixture_id="mutated"), Path(directory) / "bundle.json"
                )


class MolecularAtlasQualityRuntimeReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_molecular_atlas_fixture()
        self.evaluation = evaluate_molecular_atlas_fixture(self.fixture)

    def test_quality_gate_has_all_expected_floors(self) -> None:
        report = evaluate_molecular_atlas_quality_gate(self.fixture)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 25)
        self.assertEqual(report.failed_check_ids, ())

    def test_reconciliation_closes_all_views(self) -> None:
        data = audit_molecular_atlas_data(self.fixture)
        replay = replay_molecular_atlas_evaluation(self.evaluation, fixture=self.fixture)
        scenarios = evaluate_molecular_atlas_scenarios(self.fixture, report=self.evaluation)
        lineage = build_molecular_atlas_lineage(self.evaluation, fixture=self.fixture)
        report = reconcile_molecular_atlas_views(
            self.fixture, data, self.evaluation, replay, scenarios, lineage
        )
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 17)

    def test_runtime_publishes_nine_stages(self) -> None:
        report = run_molecular_atlas_pipeline(
            MolecularAtlasPipelineRequest({"fixture": "default_molecular_atlas_fixture"})
        )
        self.assertTrue(report.published)
        self.assertEqual(len(report.stages), 9)
        self.assertEqual(report.failed_stages, ())

    def test_runtime_file_supports_descriptor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "request.json"
            path.write_text(
                json.dumps({"fixture": "default_molecular_atlas_fixture", "accepted_only": True}),
                encoding="utf-8",
            )
            report = run_molecular_atlas_pipeline_file(path)
        self.assertTrue(report.published)

    def test_release_manifest_is_publishable(self) -> None:
        quality = evaluate_molecular_atlas_quality_gate(self.fixture)
        replay = replay_molecular_atlas_evaluation(self.evaluation, fixture=self.fixture)
        bundle = MolecularAtlasBundleBuilder().build(
            self.evaluation, fixture=self.fixture, accepted_only=True
        )
        manifest = build_molecular_atlas_release_manifest(
            self.evaluation, quality, bundle, replay, fixture=self.fixture
        )
        self.assertEqual(manifest.state, MolecularAtlasReleaseState.PUBLISHED)
        self.assertTrue(manifest.publishable)
        self.assertEqual(verify_molecular_atlas_release_manifest(manifest), ())

    def test_release_address_detects_mutation(self) -> None:
        quality = evaluate_molecular_atlas_quality_gate(self.fixture)
        replay = replay_molecular_atlas_evaluation(self.evaluation, fixture=self.fixture)
        bundle = MolecularAtlasBundleBuilder().build(
            self.evaluation, fixture=self.fixture, accepted_only=True
        )
        manifest = build_molecular_atlas_release_manifest(
            self.evaluation, quality, bundle, replay, fixture=self.fixture
        )
        self.assertIn(
            "manifest-address",
            verify_molecular_atlas_release_manifest(replace(manifest, context_key="drifted")),
        )


if __name__ == "__main__":
    unittest.main()
