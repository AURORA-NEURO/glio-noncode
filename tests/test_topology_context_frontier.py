from __future__ import annotations

import json
import unittest

from glio_noncode.topology_context_frontier_accessibility import (
    evaluate_topology_context_frontier_accessibility,
)
from glio_noncode.topology_context_frontier_adapters import (
    build_topology_context_frontier_adapters,
    execute_topology_context_frontier_record,
)
from glio_noncode.topology_context_frontier_artifacts import (
    build_topology_context_frontier_artifacts,
)
from glio_noncode.topology_context_frontier_bundle import build_topology_context_frontier_bundle
from glio_noncode.topology_context_frontier_candidate_depth import (
    audit_topology_context_frontier_candidates,
)
from glio_noncode.topology_context_frontier_catalog import build_topology_context_frontier_catalog
from glio_noncode.topology_context_frontier_cli import (
    TOPOLOGY_CONTEXT_FRONTIER_COMMANDS,
    run_topology_context_frontier_operation,
)
from glio_noncode.topology_context_frontier_compliance import (
    evaluate_topology_context_frontier_boundary,
)
from glio_noncode.topology_context_frontier_contracts import (
    build_topology_context_frontier_contracts,
)
from glio_noncode.topology_context_frontier_delta_depth import (
    audit_topology_context_frontier_deltas,
)
from glio_noncode.topology_context_frontier_depth import audit_topology_context_frontier_depth
from glio_noncode.topology_context_frontier_exports import (
    export_topology_context_frontier_manifest,
    export_topology_context_frontier_review_csv,
    render_topology_context_frontier_review_markdown,
)
from glio_noncode.topology_context_frontier_fixture_eval import (
    evaluate_topology_context_frontier_fixture,
)
from glio_noncode.topology_context_frontier_integrity import (
    evaluate_topology_context_frontier_integrity,
)
from glio_noncode.topology_context_frontier_lineage import build_topology_context_frontier_lineage
from glio_noncode.topology_context_frontier_metrics import build_topology_context_frontier_metrics
from glio_noncode.topology_context_frontier_observability import (
    build_topology_context_frontier_trace,
)
from glio_noncode.topology_context_frontier_pipeline import run_topology_context_frontier_pipeline
from glio_noncode.topology_context_frontier_policy import evaluate_topology_context_frontier_policy
from glio_noncode.topology_context_frontier_provenance import (
    build_topology_context_frontier_provenance,
)
from glio_noncode.topology_context_frontier_public_data import (
    TopologyContextFrontierOperation,
    audit_topology_context_frontier_data,
    default_topology_context_frontier_fixture,
)
from glio_noncode.topology_context_frontier_quality_gate import (
    build_topology_context_frontier_quality,
)
from glio_noncode.topology_context_frontier_reconciliation import (
    reconcile_topology_context_frontier,
)
from glio_noncode.topology_context_frontier_release import build_topology_context_frontier_release
from glio_noncode.topology_context_frontier_replay import replay_topology_context_frontier
from glio_noncode.topology_context_frontier_reports import build_topology_context_frontier_report
from glio_noncode.topology_context_frontier_review_queue import (
    build_topology_context_frontier_review_queue,
)
from glio_noncode.topology_context_frontier_runbook import default_topology_context_frontier_runbook
from glio_noncode.topology_context_frontier_runtime import (
    TopologyContextFrontierRuntimeOptions,
    run_topology_context_frontier_runtime,
)
from glio_noncode.topology_context_frontier_scenario_matrix import (
    build_topology_context_frontier_scenario_matrix,
    evaluate_topology_context_frontier_scenarios,
)
from glio_noncode.topology_context_frontier_schema import validate_topology_context_frontier_schema
from glio_noncode.topology_context_frontier_source_registry import (
    build_topology_context_frontier_source_registry,
)
from glio_noncode.topology_context_frontier_thresholds import (
    build_topology_context_frontier_threshold_report,
)
from glio_noncode.topology_context_frontier_validation_matrix import (
    build_topology_context_frontier_validation_matrix,
    validate_topology_context_frontier_matrix,
)
from glio_noncode.topology_context_frontier_views import build_topology_context_frontier_view


class TopologyContextFrontierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_topology_context_frontier_fixture()
        self.evaluation = evaluate_topology_context_frontier_fixture(self.fixture)

    def test_fixture_is_closed_and_balanced(self) -> None:
        self.assertEqual(len(self.fixture.sources), 4)
        self.assertEqual(len(self.fixture.records), 16)
        self.assertEqual(len(self.fixture.positive_records), 4)
        self.assertEqual(len(self.fixture.control_records), 12)
        self.assertTrue(
            all(item.content_address.startswith("sha256:") for item in self.fixture.records)
        )

    def test_data_boundary_and_source_audits_pass(self) -> None:
        self.assertTrue(audit_topology_context_frontier_data(self.fixture).accepted)
        self.assertTrue(
            evaluate_topology_context_frontier_boundary(self.fixture, self.evaluation).accepted
        )
        self.assertTrue(build_topology_context_frontier_source_registry(self.fixture).accepted)

    def test_each_operation_has_one_positive_and_three_controls(self) -> None:
        for operation in TopologyContextFrontierOperation:
            rows = self.fixture.operation_records(operation)
            self.assertEqual(len(rows), 4)
            self.assertEqual(sum(item.role.value == "positive" for item in rows), 1)
            self.assertEqual(sum(item.role.value == "control" for item in rows), 3)

    def test_adapter_registry_is_complete(self) -> None:
        registry = build_topology_context_frontier_adapters()
        self.assertTrue(registry.accepted)
        self.assertEqual(len(registry.specs), 4)
        self.assertEqual(
            registry.for_operation("matrix_qc").primitive,
            "ContactMatrixQcEvaluator + ContactMatrixNormalizer",
        )

    def test_evaluation_replays_all_states_and_issue_floors(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(self.evaluation.state_match_count, 16)
        self.assertEqual(self.evaluation.issue_match_count, 16)
        self.assertEqual(self.evaluation.failed_record_ids, ())

    def test_contact_import_preserves_supported_ambiguity_and_foreign_context(self) -> None:
        contact = self.evaluation.by_operation("contact_import")
        self.assertEqual(
            [item.observed_state for item in contact],
            ["supported", "partial", "ambiguous", "out_of_domain"],
        )
        self.assertIn("contact-a", contact[2].adapter.measurements["interaction_ids"])
        self.assertIn("context_mismatch", contact[3].adapter.issue_codes)

    def test_matrix_qc_preserves_duplicate_zero_and_empty_controls(self) -> None:
        matrix = self.evaluation.by_operation("matrix_qc")
        self.assertEqual(matrix[0].observed_state, "supported")
        self.assertEqual(matrix[1].adapter.measurements["duplicate_count"], 1)
        self.assertEqual(matrix[1].adapter.measurements["zero_signal_count"], 1)
        self.assertEqual(matrix[2].observed_state, "abstained")
        self.assertEqual(matrix[3].observed_state, "out_of_domain")

    def test_boundary_ensemble_retains_assay_agreement_and_alternatives(self) -> None:
        boundary = self.evaluation.by_operation("boundary_ensemble")
        self.assertEqual(boundary[0].observed_state, "supported")
        self.assertEqual(boundary[0].adapter.measurements["representative_position"], 1005)
        self.assertEqual(boundary[1].observed_state, "partial")
        self.assertEqual(boundary[2].observed_state, "ambiguous")
        self.assertEqual(boundary[2].adapter.measurements["cluster_count"], 2)

    def test_insulation_delta_retains_direction_missingness_and_invalidity(self) -> None:
        insulation = self.evaluation.by_operation("insulation_delta")
        self.assertEqual(insulation[0].observed_state, "supported")
        self.assertEqual(insulation[0].adapter.measurements["direction"], "decrease")
        self.assertEqual(insulation[1].observed_state, "abstained")
        self.assertIn("missing_insulation_score", insulation[1].adapter.issue_codes)
        self.assertEqual(insulation[2].observed_state, "invalid")
        self.assertEqual(insulation[3].observed_state, "out_of_domain")

    def test_schema_contract_metrics_policy_lineage_reconciliation_pass(self) -> None:
        self.assertTrue(build_topology_context_frontier_contracts().accepted)
        self.assertTrue(
            validate_topology_context_frontier_schema(self.fixture, self.evaluation).accepted
        )
        metrics = build_topology_context_frontier_metrics(self.evaluation)
        self.assertTrue(metrics.accepted)
        self.assertEqual(metrics.get("record_count").value, 16.0)
        self.assertEqual(
            evaluate_topology_context_frontier_policy(self.evaluation).review_count, 12
        )
        self.assertTrue(
            build_topology_context_frontier_lineage(self.fixture, self.evaluation).accepted
        )
        self.assertTrue(reconcile_topology_context_frontier(self.evaluation).accepted)

    def test_quality_depth_candidate_delta_validation_and_scenarios_pass(self) -> None:
        schema = validate_topology_context_frontier_schema(self.fixture, self.evaluation)
        reconciliation = reconcile_topology_context_frontier(self.evaluation)
        quality = build_topology_context_frontier_quality(
            self.fixture,
            audit_topology_context_frontier_data(self.fixture),
            schema,
            self.evaluation,
            reconciliation,
        )
        self.assertTrue(quality.accepted)
        depth = audit_topology_context_frontier_depth(self.fixture, self.evaluation)
        candidates = audit_topology_context_frontier_candidates(self.evaluation)
        deltas = audit_topology_context_frontier_deltas(self.evaluation)
        self.assertTrue(depth.accepted)
        self.assertGreaterEqual(depth.mean_depth, 0.9)
        self.assertTrue(candidates.accepted)
        self.assertGreaterEqual(candidates.candidate_count, 8)
        self.assertTrue(deltas.accepted)
        validation = build_topology_context_frontier_validation_matrix(self.evaluation)
        self.assertTrue(validate_topology_context_frontier_matrix(validation))
        scenarios = build_topology_context_frontier_scenario_matrix(self.evaluation)
        self.assertTrue(scenarios.accepted)
        self.assertEqual(
            evaluate_topology_context_frontier_scenarios(scenarios)["scenario_count"], 4
        )
        self.assertTrue(build_topology_context_frontier_threshold_report().accepted)

    def test_integrity_accessibility_view_queue_trace_and_runbook_pass(self) -> None:
        self.assertTrue(
            evaluate_topology_context_frontier_integrity(self.fixture, self.evaluation).accepted
        )
        self.assertTrue(evaluate_topology_context_frontier_accessibility(self.evaluation).accepted)
        self.assertTrue(build_topology_context_frontier_view(self.evaluation).accepted)
        self.assertEqual(build_topology_context_frontier_review_queue(self.evaluation).count, 12)
        self.assertEqual(
            len(build_topology_context_frontier_trace(self.evaluation, "test").events), 16
        )
        self.assertEqual(len(default_topology_context_frontier_runbook().steps), 5)

    def test_provenance_graph_closes_sources_records_and_results(self) -> None:
        graph = build_topology_context_frontier_provenance(self.fixture, self.evaluation)
        self.assertTrue(graph.accepted)
        self.assertEqual(graph.source_count, 4)
        self.assertEqual(graph.result_count, 16)
        self.assertEqual(len(graph.nodes_by_kind("result")), 16)
        self.assertEqual(len(graph.edges_for_record("D09-C01-P")), 1)
        self.assertGreaterEqual(len(graph.edges), 32)
        self.assertTrue(all(item.aggregate for item in graph.nodes))

    def test_contract_fields_and_payload_boundaries_are_explicit(self) -> None:
        contracts = build_topology_context_frontier_contracts()
        self.assertEqual(len(contracts.contracts), 4)
        for contract in contracts.contracts:
            self.assertTrue(contract.contract_id.startswith("GNC-D09-C0"))
            self.assertIn("public_aggregate", contract.required_fields)
            self.assertIn("out_of_domain", contract.state_values)
            self.assertTrue(contract.limitation)
        for record in self.fixture.records:
            self.assertTrue(record.payload["public_aggregate"])
            self.assertNotIn("subject_id", json.dumps(record.payload))
            self.assertEqual(record.context_key, self.fixture.context_key)

    def test_source_receipts_and_result_measurements_keep_operation_specific_fields(self) -> None:
        sources = build_topology_context_frontier_source_registry(self.fixture)
        self.assertEqual(
            {item.source_kind for item in sources.entries},
            {"contact_aggregate", "boundary_aggregate", "insulation_aggregate", "method_reference"},
        )
        contact = self.evaluation.by_operation("contact_import")[0].adapter.measurements
        matrix = self.evaluation.by_operation("matrix_qc")[0].adapter.measurements
        boundary = self.evaluation.by_operation("boundary_ensemble")[0].adapter.measurements
        insulation = self.evaluation.by_operation("insulation_delta")[0].adapter.measurements
        self.assertIn("median_signal", contact)
        self.assertIn("duplicate_count", matrix)
        self.assertIn("representative_position", boundary)
        self.assertIn("relative_delta", insulation)

    def test_pipeline_stage_details_remain_nonempty_and_ordered(self) -> None:
        pipeline = run_topology_context_frontier_pipeline(self.fixture)
        expected = (
            "fixture",
            "contracts",
            "sources",
            "evaluation",
            "schema",
            "quality",
            "policy",
            "boundary",
            "depth",
            "validation",
            "integrity",
            "release",
        )
        self.assertEqual(tuple(item.stage_id for item in pipeline.stages), expected)
        self.assertTrue(all(item.status == "passed" for item in pipeline.stages))
        self.assertTrue(all(item.input_count >= 0 for item in pipeline.stages))
        self.assertTrue(all(item.output_count >= 0 for item in pipeline.stages))
        self.assertTrue(all(item.detail for item in pipeline.stages))

    def test_release_bundle_artifacts_and_report_pass(self) -> None:
        pipeline = run_topology_context_frontier_pipeline(self.fixture)
        release = build_topology_context_frontier_release(
            self.fixture, self.evaluation, pipeline.quality
        )
        bundle = build_topology_context_frontier_bundle(
            self.fixture, release, pipeline.metrics, pipeline.deltas
        )
        artifacts = build_topology_context_frontier_artifacts(bundle, self.evaluation)
        report = build_topology_context_frontier_report(
            self.evaluation, pipeline.metrics, pipeline.quality
        )
        self.assertTrue(release.publishable)
        self.assertTrue(bundle.accepted)
        self.assertTrue(artifacts.accepted)
        self.assertEqual(len(artifacts.artifacts), 20)
        self.assertTrue(report.accepted)

    def test_pipeline_has_twelve_accepted_stages_and_stable_addresses(self) -> None:
        pipeline = run_topology_context_frontier_pipeline(self.fixture)
        self.assertTrue(pipeline.accepted)
        self.assertEqual(pipeline.failed_stages, ())
        self.assertEqual(len(pipeline.stages), 12)
        self.assertTrue(pipeline.invariants.accepted)
        replay = replay_topology_context_frontier(self.fixture)
        self.assertTrue(replay.accepted)
        self.assertEqual(pipeline.evaluation.content_address, replay.expected_address)

    def test_runtime_limit_is_enforced(self) -> None:
        self.assertTrue(run_topology_context_frontier_runtime(fixture=self.fixture).accepted)
        with self.assertRaises(ValueError):
            run_topology_context_frontier_runtime(
                TopologyContextFrontierRuntimeOptions(max_records=15), fixture=self.fixture
            )

    def test_exports_are_sanitized(self) -> None:
        manifest = export_topology_context_frontier_manifest(self.fixture, self.evaluation)
        self.assertEqual(json.loads(manifest)["fixture"]["fixture_id"], self.fixture.fixture_id)
        self.assertEqual(
            export_topology_context_frontier_review_csv(self.evaluation).count("\n"), 17
        )
        self.assertIn(
            "Domain 09 topology context review",
            render_topology_context_frontier_review_markdown(self.evaluation),
        )
        self.assertNotIn("subject_id", manifest)

    def test_all_cli_operations_return_nonempty_mappings(self) -> None:
        self.assertEqual(len(TOPOLOGY_CONTEXT_FRONTIER_COMMANDS), 12)
        for operation in TOPOLOGY_CONTEXT_FRONTIER_COMMANDS:
            value = run_topology_context_frontier_operation(operation)
            self.assertIsInstance(value, dict)
            self.assertTrue(value)

    def test_catalog_is_closed(self) -> None:
        catalog = build_topology_context_frontier_catalog()
        self.assertTrue(catalog.accepted)
        self.assertEqual(len(catalog.entries), 4)
        self.assertEqual(catalog.for_operation("insulation_delta").capability_id, "GNC-D09-C04")

    def test_direct_adapters_keep_result_addresses(self) -> None:
        for record in self.fixture.records:
            result = execute_topology_context_frontier_record(record)
            self.assertTrue(result.content_address.startswith("sha256:"))
            self.assertEqual(result.record_id, record.record_id)


if __name__ == "__main__":
    unittest.main()
