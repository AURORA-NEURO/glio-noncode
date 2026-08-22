from __future__ import annotations

import unittest

from glio_noncode.reference_release_frontier_accessibility import (
    evaluate_reference_release_accessibility,
)
from glio_noncode.reference_release_frontier_adapters import (
    default_reference_release_adapters,
    verify_reference_release_adapters,
)
from glio_noncode.reference_release_frontier_artifacts import (
    build_reference_release_artifact_inventory,
    verify_reference_release_artifact_inventory,
)
from glio_noncode.reference_release_frontier_bundle import (
    ReferenceReleaseBundleBuilder,
    ReferenceReleaseBundleFormat,
    assemble_reference_release_bundle,
)
from glio_noncode.reference_release_frontier_checks import run_reference_release_invariants
from glio_noncode.reference_release_frontier_compliance import evaluate_reference_release_boundary
from glio_noncode.reference_release_frontier_contracts import default_reference_release_contracts
from glio_noncode.reference_release_frontier_exports import (
    export_reference_release_bundle_csv,
    export_reference_release_json,
)
from glio_noncode.reference_release_frontier_fixture_eval import evaluate_reference_release_fixture
from glio_noncode.reference_release_frontier_lineage import build_reference_release_lineage
from glio_noncode.reference_release_frontier_metrics import (
    build_reference_release_metrics,
    verify_reference_release_metrics,
)
from glio_noncode.reference_release_frontier_observability import (
    observe_reference_release,
    verify_reference_release_observability,
)
from glio_noncode.reference_release_frontier_pipeline import run_reference_release_pipeline
from glio_noncode.reference_release_frontier_policy import (
    evaluate_reference_release_policy,
    verify_reference_release_policy,
)
from glio_noncode.reference_release_frontier_projection_assertions import (
    audit_reference_release_projections,
)
from glio_noncode.reference_release_frontier_public_data import (
    REFERENCE_RELEASE_FRONTIER_CONTEXT_KEY,
    ReferenceReleaseOperation,
    audit_reference_release_data,
    default_reference_release_fixture,
    load_reference_release_fixture,
)
from glio_noncode.reference_release_frontier_quality_gate import evaluate_reference_release_quality
from glio_noncode.reference_release_frontier_reconciliation import reconcile_reference_release_views
from glio_noncode.reference_release_frontier_release import (
    build_reference_release_manifest,
    verify_reference_release_manifest,
)
from glio_noncode.reference_release_frontier_replay import (
    build_reference_release_expectation,
    replay_reference_release_evaluation,
)
from glio_noncode.reference_release_frontier_review_queue import (
    build_reference_release_review_queue,
    verify_reference_release_review_queue,
)
from glio_noncode.reference_release_frontier_runbook import (
    default_reference_release_runbook,
    verify_reference_release_runbook,
)
from glio_noncode.reference_release_frontier_runtime import run_reference_release_runtime
from glio_noncode.reference_release_frontier_scenario_matrix import (
    build_reference_release_scenario_matrix,
    verify_reference_release_scenarios,
)
from glio_noncode.reference_release_frontier_schema import default_reference_release_schema
from glio_noncode.reference_release_frontier_thresholds import (
    build_reference_release_threshold_report,
    verify_reference_release_thresholds,
)
from glio_noncode.reference_release_frontier_validation_matrix import (
    build_reference_release_validation_matrix,
    validate_reference_release_matrix,
)
from glio_noncode.reference_release_frontier_views import (
    build_reference_release_review_view,
    verify_reference_release_review_view,
)


class ReferenceReleaseFixtureTests(unittest.TestCase):
    def test_fixture_has_public_boundary_and_balanced_operations(self) -> None:
        fixture = default_reference_release_fixture()
        self.assertEqual(fixture.context_key, REFERENCE_RELEASE_FRONTIER_CONTEXT_KEY)
        self.assertEqual(len(fixture.sources), 5)
        self.assertEqual(len(fixture.records), 16)
        self.assertEqual(len(fixture.positive_records), 4)
        self.assertEqual(len(fixture.control_records), 12)
        self.assertEqual(
            {item.operation for item in fixture.records}, set(ReferenceReleaseOperation)
        )
        self.assertTrue(
            all(
                sum(item.operation is operation for item in fixture.records) == 4
                for operation in ReferenceReleaseOperation
            )
        )

    def test_mapping_loader_roundtrips_the_fixture(self) -> None:
        fixture = default_reference_release_fixture()
        loaded = load_reference_release_fixture(fixture.to_dict())
        self.assertEqual(loaded.fixture_id, fixture.fixture_id)
        self.assertEqual(loaded.content_address, fixture.content_address)
        self.assertEqual(
            tuple(item.operation for item in loaded.records),
            tuple(item.operation for item in fixture.records),
        )

    def test_data_audit_has_source_and_record_closure(self) -> None:
        audit = audit_reference_release_data()
        self.assertTrue(audit.accepted)
        self.assertEqual(len(audit.checks), 23)
        self.assertEqual(audit.failed_check_ids, ())

    def test_evaluation_executes_all_positive_and_control_rows(self) -> None:
        report = evaluate_reference_release_fixture()
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.executions), 16)
        self.assertEqual(len(report.checks), 48)
        self.assertEqual(report.positive_count, 4)
        self.assertEqual(report.control_count, 12)
        by_id = report.execution_map()
        self.assertEqual(by_id["C13-POS-001"].state, "accepted")
        self.assertEqual(by_id["C13-CTRL-002"].issue_codes, ("checksum_unverified",))
        self.assertEqual(by_id["C14-CTRL-001"].state, "drift")
        self.assertEqual(by_id["C15-CTRL-001"].issue_codes, ("bundle_context_mismatch",))
        self.assertEqual(by_id["C16-POS-001"].state, "published")

    def test_contracts_and_schema_cover_every_operation(self) -> None:
        contracts = default_reference_release_contracts()
        schema = default_reference_release_schema()
        self.assertEqual(len(contracts.contracts), 4)
        self.assertEqual(len(schema.schemas), 4)
        self.assertEqual(
            contracts.by_capability("GNC-D04-C16").operation, ReferenceReleaseOperation.RELEASE_GATE
        )
        fixture = default_reference_release_fixture()
        for record in fixture.records:
            payload = dict(record.payload)
            payload["context_key"] = fixture.context_key
            self.assertEqual(schema.by_operation(record.operation).validate_input(payload), ())

    def test_projection_metrics_lineage_policy_and_quality_close(self) -> None:
        fixture = default_reference_release_fixture()
        data = audit_reference_release_data(fixture)
        evaluation = evaluate_reference_release_fixture(fixture)
        projection = audit_reference_release_projections(evaluation)
        metrics = build_reference_release_metrics(evaluation)
        lineage = build_reference_release_lineage(fixture, evaluation)
        policy = evaluate_reference_release_policy(fixture, evaluation)
        reconciliation = reconcile_reference_release_views(
            fixture, data, evaluation, projection, policy, lineage
        )
        quality = evaluate_reference_release_quality(
            fixture,
            data,
            evaluation,
            default_reference_release_contracts(),
            default_reference_release_schema(),
            lineage,
            reconciliation,
            projection,
            policy,
        )
        self.assertTrue(projection.accepted)
        self.assertTrue(metrics.accepted)
        self.assertEqual(verify_reference_release_metrics(metrics), ())
        self.assertTrue(lineage.audit(evaluation).passed)
        self.assertGreaterEqual(len(lineage.nodes), 100)
        self.assertGreaterEqual(len(lineage.edges), 100)
        self.assertTrue(policy.accepted)
        self.assertEqual(verify_reference_release_policy(policy), ())
        self.assertTrue(reconciliation.accepted)
        self.assertTrue(quality.accepted)
        self.assertEqual(len(quality.checks), 25)

    def test_replay_is_deterministic(self) -> None:
        fixture = default_reference_release_fixture()
        evaluation = evaluate_reference_release_fixture(fixture)
        replay = replay_reference_release_evaluation(evaluation, fixture=fixture)
        self.assertEqual(
            build_reference_release_expectation(evaluation)["fixture_id"], fixture.fixture_id
        )
        self.assertTrue(replay.accepted)
        self.assertEqual(len(replay.checks), 12)
        self.assertEqual(replay.failed_check_ids, ())

    def test_runtime_has_nine_accepted_stages(self) -> None:
        runtime = run_reference_release_runtime()
        self.assertTrue(runtime.accepted)
        self.assertEqual(len(runtime.stages), 9)
        self.assertEqual(tuple(item.sequence for item in runtime.stages), tuple(range(1, 10)))
        self.assertEqual(runtime.stage("quality-gate").state, "accepted")


class ReferenceReleaseOperationsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_reference_release_fixture()
        self.runtime = run_reference_release_runtime(
            self.fixture, run_id="test-reference-release-runtime"
        )
        self.manifest = build_reference_release_manifest(
            self.runtime, release_id="test-reference-release-manifest"
        )
        self.bundle = assemble_reference_release_bundle(self.fixture, self.runtime, self.manifest)
        self.view = build_reference_release_review_view(
            self.fixture, self.runtime.evaluation, self.runtime.policy, self.manifest
        )

    def test_manifest_bundle_and_artifacts_are_verified(self) -> None:
        self.assertTrue(self.manifest.ready)
        self.assertEqual(verify_reference_release_manifest(self.manifest), ())
        builder = ReferenceReleaseBundleBuilder()
        self.assertTrue(self.bundle.accepted)
        self.assertEqual(builder.verify(self.bundle), ())
        self.assertGreater(len(builder.render(self.bundle)), 100)
        for output_format in ReferenceReleaseBundleFormat:
            rendered = builder.build(
                self.runtime, self.manifest, fixture=self.fixture, output_format=output_format
            )
            self.assertTrue(builder.render(rendered))
        inventory = build_reference_release_artifact_inventory(
            self.runtime, self.manifest, self.bundle
        )
        self.assertTrue(inventory.accepted)
        self.assertEqual(len(inventory.artifacts), 11)
        self.assertEqual(verify_reference_release_artifact_inventory(inventory), ())

    def test_review_view_and_queue_preserve_all_controls(self) -> None:
        self.assertTrue(self.view.accepted)
        self.assertEqual(verify_reference_release_review_view(self.view), ())
        queue = build_reference_release_review_queue(self.view, self.manifest)
        self.assertTrue(queue.accepted)
        self.assertEqual(len(queue.items), 11)
        self.assertEqual(verify_reference_release_review_queue(queue), ())

    def test_accessibility_boundary_and_invariants_accept(self) -> None:
        accessibility = evaluate_reference_release_accessibility(
            self.fixture, self.runtime.evaluation, self.view
        )
        boundary = evaluate_reference_release_boundary(
            self.fixture, self.runtime.evaluation, self.runtime, self.bundle, self.view
        )
        invariants = run_reference_release_invariants(
            self.fixture, self.runtime.evaluation, self.manifest, self.bundle, self.view
        )
        self.assertTrue(accessibility.accepted)
        self.assertTrue(boundary.accepted)
        self.assertTrue(invariants.accepted)
        self.assertEqual(len(accessibility.checks), 10)
        self.assertEqual(len(boundary.checks), 12)
        self.assertEqual(len(invariants.checks), 16)

    def test_observability_scenarios_thresholds_validation_and_runbook_accept(self) -> None:
        observations = observe_reference_release(self.runtime)
        scenarios = build_reference_release_scenario_matrix()
        thresholds = build_reference_release_threshold_report(
            self.fixture, self.runtime.evaluation, self.runtime.metrics, self.runtime.lineage
        )
        validation = build_reference_release_validation_matrix(
            self.fixture, self.runtime.evaluation
        )
        runbook = default_reference_release_runbook()
        adapters = default_reference_release_adapters()
        self.assertTrue(observations.accepted)
        self.assertEqual(verify_reference_release_observability(observations), ())
        self.assertTrue(scenarios.accepted)
        self.assertEqual(verify_reference_release_scenarios(scenarios), ())
        self.assertTrue(thresholds.accepted)
        self.assertEqual(verify_reference_release_thresholds(thresholds), ())
        self.assertTrue(validation.accepted)
        self.assertTrue(validate_reference_release_matrix(validation))
        self.assertTrue(runbook.accepted)
        self.assertEqual(verify_reference_release_runbook(runbook), ())
        self.assertEqual(verify_reference_release_adapters(adapters), ())

    def test_exports_are_stable_and_redacted(self) -> None:
        rendered = export_reference_release_json(self.bundle)
        csv_text = export_reference_release_bundle_csv(self.bundle)
        self.assertTrue(rendered.endswith("\n"))
        self.assertTrue(csv_text.startswith("record_id,operation"))
        self.assertNotIn("raw_records", rendered)
        self.assertNotIn("payload", rendered)
        self.assertIn("C13-POS-001", csv_text)

    def test_root_pipeline_is_accepted(self) -> None:
        report = run_reference_release_pipeline(self.fixture)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.addresses()), 15)
        self.assertEqual(report.release.state.value, "ready")
        self.assertEqual(len(report.artifacts.artifacts), 11)


if __name__ == "__main__":
    unittest.main()
