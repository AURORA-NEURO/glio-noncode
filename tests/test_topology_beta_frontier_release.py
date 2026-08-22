from __future__ import annotations

import unittest

from glio_noncode.topology_beta_frontier_acceptance import build_topology_beta_frontier_acceptance
from glio_noncode.topology_beta_frontier_contracts import build_topology_beta_frontier_contracts
from glio_noncode.topology_beta_frontier_fixture_eval import evaluate_topology_beta_frontier_fixture
from glio_noncode.topology_beta_frontier_governance import build_topology_beta_frontier_governance
from glio_noncode.topology_beta_frontier_history import build_topology_beta_frontier_history
from glio_noncode.topology_beta_frontier_packaging import build_topology_beta_frontier_package_manifest
from glio_noncode.topology_beta_frontier_pipeline import run_topology_beta_frontier_pipeline
from glio_noncode.topology_beta_frontier_public_data import default_topology_beta_frontier_fixture
from glio_noncode.topology_beta_frontier_regression import build_topology_beta_frontier_regression, summarize_topology_beta_frontier_regression
from glio_noncode.topology_beta_frontier_release_notes import build_topology_beta_frontier_release_notes
from glio_noncode.topology_beta_frontier_replay_ledger import build_topology_beta_frontier_replay_ledger


class TopologyBetaFrontierReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_topology_beta_frontier_fixture()
        self.evaluation = evaluate_topology_beta_frontier_fixture(self.fixture)
        self.pipeline = run_topology_beta_frontier_pipeline(self.fixture)

    def test_regression_report_has_four_cases(self) -> None:
        report = build_topology_beta_frontier_regression(self.fixture, self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.cases), 4)
        self.assertEqual(report.assertion_count, 32)
        self.assertEqual(report.passed_count, 32)
        self.assertEqual(report.failed(), ())

    def test_regression_states_are_operation_specific(self) -> None:
        report = build_topology_beta_frontier_regression(self.fixture, self.evaluation)
        self.assertEqual(report.case("loop_stripe").assertions[3].observed, ("supported", "partial", "ambiguous", "out_of_domain"))
        self.assertEqual(report.case("enhancer_promoter_contact").assertions[3].observed, ("supported", "ambiguous", "out_of_domain", "absent"))
        self.assertEqual(summarize_topology_beta_frontier_regression(report)["failed_count"], 0)

    def test_acceptance_report_has_six_gates(self) -> None:
        report = build_topology_beta_frontier_acceptance(self.pipeline.evaluation, self.pipeline.contracts, self.pipeline.schema, self.pipeline.quality, self.pipeline.integrity, self.pipeline.review_queue)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.gates), 6)
        self.assertTrue(all(item.passed for item in report.gates))
        self.assertEqual(report.gate("evaluation").observed, 16)

    def test_governance_report_keeps_four_operation_decisions(self) -> None:
        report = build_topology_beta_frontier_governance(self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.decisions), 16)
        self.assertEqual(sum(item.passed for item in report.decisions), 16)
        self.assertEqual(len(report.decisions_for("activity_by_contact")), 4)

    def test_package_manifest_has_required_sanitized_files(self) -> None:
        manifest = build_topology_beta_frontier_package_manifest(self.pipeline)
        self.assertTrue(manifest.accepted)
        self.assertEqual(len(manifest.files), 8)
        self.assertEqual(len(manifest.required_files()), 7)
        self.assertEqual(len(manifest.by_role("review")), 1)
        self.assertTrue(all(item.sanitized for item in manifest.files))

    def test_release_notes_cover_scope_controls_and_limits(self) -> None:
        notes = build_topology_beta_frontier_release_notes(self.pipeline)
        self.assertTrue(notes.accepted)
        self.assertEqual(len(notes.by_category("controls")), 1)
        self.assertEqual(len(notes.by_category("limitations")), 1)
        self.assertEqual(len(notes.by_category("scope")), 1)
        self.assertTrue(all(item.evidence_refs for item in notes.notes))

    def test_history_addresses_both_entries(self) -> None:
        history = build_topology_beta_frontier_history()
        self.assertTrue(history.accepted)
        self.assertEqual(len(history.entries), 2)
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in history.entries))
        self.assertEqual(history.latest().record_count, 16)

    def test_pipeline_release_links_to_package(self) -> None:
        manifest = build_topology_beta_frontier_package_manifest(self.pipeline)
        release_file = next(item for item in manifest.files if item.role == "release")
        artifact_file = next(item for item in manifest.files if item.role == "artifacts")
        self.assertEqual(release_file.content_address, self.pipeline.release.content_address)
        self.assertEqual(artifact_file.content_address, self.pipeline.artifacts.content_address)

    def test_pipeline_scope_and_version_are_forwarded(self) -> None:
        manifest = build_topology_beta_frontier_package_manifest(self.pipeline)
        self.assertEqual(manifest.version, self.fixture.version)
        self.assertEqual(manifest.scope, self.fixture.boundary)
        self.assertEqual(manifest.package_id, "topology-beta-frontier-package")

    def test_release_notes_use_pipeline_receipts(self) -> None:
        notes = build_topology_beta_frontier_release_notes(self.pipeline)
        reproducibility = next(item for item in notes.notes if item.category == "reproducibility")
        self.assertIn(self.pipeline.content_address, reproducibility.evidence_refs)
        controls = next(item for item in notes.notes if item.category == "controls")
        self.assertEqual(len(controls.evidence_refs), 12)

    def test_contract_and_regression_agree_on_operation_count(self) -> None:
        contracts = build_topology_beta_frontier_contracts()
        regression = build_topology_beta_frontier_regression(self.fixture, self.evaluation)
        self.assertEqual(len(contracts.contracts), len(regression.cases))
        self.assertEqual({item.operation.value for item in contracts.contracts}, {item.operation for item in regression.cases})

    def test_all_stage_receipts_are_addressed(self) -> None:
        ledger = build_topology_beta_frontier_replay_ledger(self.pipeline)
        self.assertTrue(all(item.stage_address.startswith("sha256:") for item in ledger.entries))

    def test_review_count_is_stable_across_release_surfaces(self) -> None:
        self.assertEqual(self.pipeline.review_queue.count, 12)
        self.assertEqual(self.pipeline.release.required_review_count, 12)
        self.assertEqual(sum(item.role == "control" for item in self.evaluation.rows), 12)

    def test_pipeline_has_no_failed_stage_before_packaging(self) -> None:
        manifest = build_topology_beta_frontier_package_manifest(self.pipeline)
        self.assertEqual(self.pipeline.failed_stages, ())
        self.assertTrue(manifest.accepted)
        self.assertTrue(self.pipeline.release.publishable)

    def test_release_scope_is_public_aggregate(self) -> None:
        self.assertEqual(self.pipeline.release.scope, "public_aggregate_non_patient")
        self.assertEqual(self.pipeline.fixture.boundary, self.pipeline.release.scope)
        self.assertTrue(all(item.public for item in build_topology_beta_frontier_release_notes(self.pipeline).notes))

    def test_regression_and_release_artifacts_share_record_count(self) -> None:
        regression = build_topology_beta_frontier_regression(self.fixture, self.evaluation)
        record_artifacts = tuple(item for item in self.pipeline.artifacts.artifacts if item.kind == "record_result")
        self.assertEqual(sum(len(item.assertions) for item in regression.cases), 32)
        self.assertEqual(len(record_artifacts), len(self.evaluation.rows))

    def test_fixture_and_evaluation_addresses_are_present(self) -> None:
        self.assertTrue(self.fixture.content_address.startswith("sha256:"))
        self.assertTrue(self.evaluation.content_address.startswith("sha256:"))

    def test_release_manifest_contains_all_record_artifacts(self) -> None:
        record_ids = {item.record_id for item in self.pipeline.evaluation.rows}
        release_ids = {item.removeprefix("artifact-") for item in self.pipeline.release.artifact_ids if item.startswith("artifact-D09-")}
        self.assertEqual(record_ids, release_ids)

    def test_pipeline_metrics_and_release_version_are_consistent(self) -> None:
        self.assertEqual(self.pipeline.metrics.get("record_count").value, 16.0)
        self.assertEqual(self.pipeline.release.version, self.fixture.version)
        self.assertEqual(self.pipeline.release.fixture_id, self.fixture.fixture_id)

    def test_controls_are_not_marked_as_positive(self) -> None:
        self.assertTrue(all(item.role == "control" for item in self.pipeline.evaluation.controls()))
        self.assertEqual(len(self.pipeline.evaluation.positives()), 4)

    def test_package_file_roles_are_unique(self) -> None:
        manifest = build_topology_beta_frontier_package_manifest(self.pipeline)
        self.assertEqual(len({item.path for item in manifest.files}), len(manifest.files))
        self.assertEqual(len({item.role for item in manifest.files}), 8)

    def test_release_notes_include_external_calibration_limit(self) -> None:
        notes = build_topology_beta_frontier_release_notes(self.pipeline)
        limitations = notes.by_category("limitations")
        self.assertEqual(len(limitations), 1)
        self.assertIn("calibration", limitations[0].reviewer_action)

    def test_bundle_and_artifact_addresses_are_distinct_receipts(self) -> None:
        self.assertTrue(self.pipeline.bundle.content_address.startswith("sha256:"))
        self.assertTrue(self.pipeline.artifacts.content_address.startswith("sha256:"))
        self.assertNotEqual(self.pipeline.bundle.content_address, self.pipeline.artifacts.content_address)

    def test_pipeline_content_address_is_present_after_release_assembly(self) -> None:
        self.assertTrue(self.pipeline.content_address.startswith("sha256:"))
        self.assertEqual(len(self.pipeline.failed_stages), 0)

    def test_release_fixture_contains_four_sources(self) -> None:
        self.assertEqual(len(self.pipeline.fixture.sources), 4)
        self.assertTrue(all(item.public_aggregate for item in self.pipeline.fixture.sources))

    def test_release_artifacts_retain_operation_records(self) -> None:
        ids = {item.record_id for item in self.pipeline.evaluation.rows}
        artifact_ids = {item.record_id for item in self.pipeline.artifacts.artifacts if item.record_id}
        self.assertEqual(ids, artifact_ids)

    def test_release_pipeline_is_accepted(self) -> None:
        self.assertTrue(self.pipeline.accepted)

    def test_release_review_queue_is_nonempty(self) -> None:
        self.assertGreater(self.pipeline.review_queue.count, 0)

    def test_release_bundle_has_required_members(self) -> None:
        self.assertGreaterEqual(len(self.pipeline.bundle.members), 4)
        self.assertTrue(all(item.required for item in self.pipeline.bundle.members))
        self.assertTrue(self.pipeline.bundle.accepted)
        self.assertTrue(self.pipeline.bundle.content_address.startswith("sha256:"))
        self.assertEqual(self.pipeline.bundle.fixture_id, self.fixture.fixture_id)
        self.assertEqual(self.pipeline.bundle.release_id, self.pipeline.release.release_id)
        self.assertEqual(len(self.pipeline.bundle.members), 4)
        self.assertTrue(self.pipeline.release.publishable)


if __name__ == "__main__":
    unittest.main()
