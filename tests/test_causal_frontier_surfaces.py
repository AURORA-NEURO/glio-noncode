"""Tests for reusable adapter, threshold, artifact, and invariant surfaces."""

from __future__ import annotations

import unittest

from glio_noncode.causal_frontier_adapters import default_causal_frontier_adapters
from glio_noncode.causal_frontier_artifacts import (
    CausalFrontierArtifactKind,
    build_causal_frontier_artifact_inventory,
)
from glio_noncode.causal_frontier_checks import (
    causal_frontier_observation_map,
    default_causal_frontier_invariants,
    run_causal_frontier_invariants,
)
from glio_noncode.causal_frontier_contracts import default_causal_frontier_contracts
from glio_noncode.causal_frontier_fixture_eval import evaluate_causal_frontier_fixture
from glio_noncode.causal_frontier_lineage import build_causal_frontier_lineage
from glio_noncode.causal_frontier_metrics import measure_causal_frontier
from glio_noncode.causal_frontier_policy import default_causal_frontier_policy
from glio_noncode.causal_frontier_public_data import (
    CausalFrontierOperation,
    default_causal_frontier_fixture,
)
from glio_noncode.causal_frontier_quality_gate import evaluate_causal_frontier_quality
from glio_noncode.causal_frontier_reconciliation import reconcile_causal_frontier
from glio_noncode.causal_frontier_release import build_causal_frontier_release_manifest
from glio_noncode.causal_frontier_replay import replay_causal_frontier
from glio_noncode.causal_frontier_runtime import run_causal_frontier_runtime
from glio_noncode.causal_frontier_schema import default_causal_frontier_schema
from glio_noncode.causal_frontier_thresholds import (
    build_causal_frontier_threshold_report,
    default_causal_frontier_threshold_profiles,
)
from glio_noncode.errors import ValidationError


class CausalFrontierSurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_causal_frontier_fixture()
        self.evaluation = evaluate_causal_frontier_fixture(self.fixture)
        self.contracts = default_causal_frontier_contracts()
        self.schema = default_causal_frontier_schema()
        self.policy = default_causal_frontier_policy(self.contracts)
        self.lineage = build_causal_frontier_lineage(self.fixture, self.evaluation)
        self.reconciliation = reconcile_causal_frontier(self.fixture, self.evaluation, self.policy)
        self.metrics = measure_causal_frontier(self.evaluation)
        self.quality = evaluate_causal_frontier_quality(
            self.fixture,
            self.evaluation,
            self.contracts,
            self.schema,
            self.lineage,
            self.reconciliation,
        )
        self.runtime = run_causal_frontier_runtime(self.fixture, run_id="surface-runtime")
        self.replay = replay_causal_frontier(self.fixture, replay_id="surface-replay")
        self.release = build_causal_frontier_release_manifest(self.runtime.bundle, self.quality, self.replay)

    def test_adapter_registry_covers_all_operations(self) -> None:
        registry = default_causal_frontier_adapters()
        self.assertEqual(len(registry.adapters), 4)
        self.assertEqual({item.operation for item in registry.adapters}, set(CausalFrontierOperation))
        self.assertTrue(all(item.boundary == "public_aggregate_non_patient" for item in registry.adapters))
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in registry.adapters))

    def test_adapter_normalizes_context_and_rows(self) -> None:
        adapter = default_causal_frontier_adapters().by_operation(CausalFrontierOperation.SELECTIVE_PREDICTION)
        receipt = adapter.normalize(
            [{"prediction_id": "p1", "score": 0.8, "uncertainty": 0.1}],
            context_key=self.fixture.context_key,
            source_ids=("ncbi-geo", "ncbi-geo"),
        )
        self.assertEqual(receipt.row_count, 1)
        self.assertEqual(receipt.source_ids, ("ncbi-geo",))
        self.assertEqual(receipt.normalized_rows[0]["context_key"], self.fixture.context_key)
        self.assertTrue(receipt.input_address.startswith("sha256:"))

    def test_adapter_context_mismatch_is_strict(self) -> None:
        adapter = default_causal_frontier_adapters().by_operation(CausalFrontierOperation.SELECTIVE_PREDICTION)
        with self.assertRaises(ValidationError):
            adapter.normalize(
                [{"prediction_id": "p1", "score": 0.8, "uncertainty": 0.1, "context_key": "other"}],
                context_key=self.fixture.context_key,
            )

    def test_threshold_profiles_cover_operations(self) -> None:
        profiles = default_causal_frontier_threshold_profiles()
        self.assertEqual(len(profiles), 4)
        self.assertEqual({item.operation for item in profiles}, set(CausalFrontierOperation))
        self.assertTrue(all(item.minimum_evidence_count >= 0 for item in profiles))

    def test_threshold_report_has_dense_boundary_probes(self) -> None:
        report = build_causal_frontier_threshold_report()
        self.assertEqual(len(report.profiles), 4)
        self.assertEqual(len(report.probes), 324)
        self.assertTrue(report.accepted_probes)
        self.assertTrue(report.review_probes)
        self.assertEqual(len(report.accepted_probes) + len(report.review_probes), 324)
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in report.probes))

    def test_threshold_report_serialization_contains_probe_summary(self) -> None:
        payload = build_causal_frontier_threshold_report().to_dict()
        self.assertEqual(len(payload["profiles"]), 4)
        self.assertEqual(len(payload["probes"]), 324)
        self.assertIn("accepted_probes", payload)
        self.assertIn("review_probes", payload)

    def test_invariant_catalog_has_ten_named_checks(self) -> None:
        invariants = default_causal_frontier_invariants()
        self.assertEqual(len(invariants), 10)
        self.assertEqual(len({item.invariant_id for item in invariants}), 10)
        self.assertTrue(all(item.severity in {"review", "blocking"} for item in invariants))

    def test_invariant_runner_accepts_complete_observation_map(self) -> None:
        observations = causal_frontier_observation_map(
            context_preserved=True,
            content_addressed=True,
            positive_control_separated=True,
            bounded_posterior=True,
            support_threshold_visible=True,
            abstention_visible=True,
            dossier_addressed=True,
            source_receipts=True,
            issue_vocabulary=True,
            replay_stable=True,
        )
        report = run_causal_frontier_invariants(observations)
        self.assertTrue(report.accepted)
        self.assertEqual(report.failed_ids, ())
        self.assertEqual(len(report.results), 10)

    def test_invariant_runner_retains_failed_ids(self) -> None:
        observations = causal_frontier_observation_map(
            context_preserved=True,
            content_addressed=False,
            positive_control_separated=True,
            bounded_posterior=True,
            support_threshold_visible=True,
            abstention_visible=True,
            dossier_addressed=True,
            source_receipts=True,
            issue_vocabulary=True,
            replay_stable=True,
        )
        report = run_causal_frontier_invariants(observations)
        self.assertFalse(report.accepted)
        self.assertEqual(report.failed_ids, ("content-addressed",))

    def test_artifact_inventory_has_release_root(self) -> None:
        inventory = build_causal_frontier_artifact_inventory(
            self.fixture,
            self.evaluation,
            self.metrics,
            self.lineage,
            self.quality,
            self.runtime.bundle,
            self.release,
        )
        self.assertEqual(len(inventory.artifacts), 7)
        self.assertEqual(inventory.root_artifact_id, "artifact-release")
        self.assertEqual(len(inventory.by_kind(CausalFrontierArtifactKind.RELEASE)), 1)
        self.assertGreater(inventory.total_bytes, 0)
        self.assertTrue(all(item.inventory_address.startswith("sha256:") for item in inventory.artifacts))

    def test_artifact_parents_form_forward_receipt_chain(self) -> None:
        inventory = build_causal_frontier_artifact_inventory(
            self.fixture,
            self.evaluation,
            self.metrics,
            self.lineage,
            self.quality,
            self.runtime.bundle,
            self.release,
        )
        evaluation = inventory.by_id("artifact-evaluation")
        release = inventory.by_id("artifact-release")
        self.assertIn(self.fixture.content_address, evaluation.parent_addresses)
        self.assertIn(self.runtime.bundle.content_address, release.parent_addresses)
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in inventory.artifacts))

    def test_all_surface_receipts_are_content_addressed(self) -> None:
        values = (
            self.contracts,
            self.schema,
            self.evaluation,
            self.metrics,
            self.lineage,
            self.reconciliation,
            self.quality,
            self.runtime,
            self.replay,
            self.runtime.bundle,
            self.release,
        )
        self.assertTrue(all(value.content_address.startswith("sha256:") for value in values))

    def test_surface_counts_remain_explicit(self) -> None:
        self.assertEqual(len(self.evaluation.executions), 16)
        self.assertEqual(len(self.evaluation.checks), 120)
        self.assertEqual(len(self.quality.checks), 12)
        self.assertEqual(len(self.runtime.stages), 10)
        self.assertEqual(len(self.metrics.metrics), 13)
        self.assertEqual(len(self.lineage.edges), 36)

    def test_operation_adapter_lookup_is_stable(self) -> None:
        registry = default_causal_frontier_adapters()
        for operation in CausalFrontierOperation:
            adapter = registry.by_operation(operation)
            self.assertEqual(adapter.operation, operation)
            self.assertTrue(adapter.adapter_id.startswith("causal-"))

    def test_invariant_operation_filters_are_useful(self) -> None:
        report = run_causal_frontier_invariants(
            causal_frontier_observation_map(
                context_preserved=True,
                content_addressed=True,
                positive_control_separated=True,
                bounded_posterior=True,
                support_threshold_visible=True,
                abstention_visible=True,
                dossier_addressed=True,
                source_receipts=True,
                issue_vocabulary=True,
                replay_stable=True,
            )
        )
        self.assertEqual(len(report.by_operation(CausalFrontierOperation.POSTERIOR_DECOMPOSITION)), 1)
        self.assertEqual(len(report.by_operation(CausalFrontierOperation.DRIVER_POSTERIOR)), 1)
        self.assertEqual(len(report.by_operation(CausalFrontierOperation.SELECTIVE_PREDICTION)), 1)
        self.assertEqual(len(report.by_operation(CausalFrontierOperation.DOSSIER_PUBLICATION)), 1)


if __name__ == "__main__":
    unittest.main()
