from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.frontier_data_alpha import FrontierState
from glio_noncode.frontier_inference_alpha import (
    CompartmentSwitchEstimator,
    EcDNARegulatoryContactModel,
    ThreeDEvidencePublisher,
    TopologyUncertaintyTransportModel,
)
from glio_noncode.topology_frontier_fixture_eval import evaluate_topology_frontier_fixture
from glio_noncode.topology_frontier_lineage import build_topology_frontier_lineage
from glio_noncode.topology_frontier_metrics import compute_topology_frontier_metrics
from glio_noncode.topology_frontier_policy import evaluate_topology_frontier_policy
from glio_noncode.topology_frontier_public_data import (
    TOPOLOGY_FRONTIER_CONTEXT_KEY,
    TopologyFrontierOperation,
    TopologyFrontierRole,
    build_topology_frontier_catalog,
    default_topology_frontier_fixture,
    load_topology_frontier_fixture,
)
from glio_noncode.topology_frontier_quality_gate import run_topology_frontier_quality_gate
from glio_noncode.topology_frontier_reconciliation import reconcile_topology_frontier
from glio_noncode.topology_frontier_schema import (
    default_topology_frontier_schemas,
    validate_topology_frontier_schema,
)
from glio_noncode.topology_frontier_views import (
    build_topology_frontier_view,
    filter_topology_frontier_review_queue,
)


class TopologyFrontierDepthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_topology_frontier_fixture()
        self.evaluation = evaluate_topology_frontier_fixture(self.fixture)

    def test_ecdna_model_accepts_two_sources(self) -> None:
        report = EcDNARegulatoryContactModel().evaluate(
            [{"amplicon_id": "a", "element_id": "e", "gene_id": "g", "contact_score": 0.8, "source_ids": ["s1", "s2"], "context_key": TOPOLOGY_FRONTIER_CONTEXT_KEY}],
            context_key=TOPOLOGY_FRONTIER_CONTEXT_KEY,
            minimum_contact_score=0.5,
            minimum_sources=2,
        )
        self.assertEqual(report.contacts[0].state, FrontierState.ACCEPTED)
        self.assertEqual(report.supported_ids, ("a",))

    def test_ecdna_model_marks_weak_score_for_review(self) -> None:
        report = EcDNARegulatoryContactModel().evaluate(
            [{"amplicon_id": "a", "element_id": "e", "gene_id": "g", "contact_score": 0.2, "source_ids": ["s1"], "context_key": TOPOLOGY_FRONTIER_CONTEXT_KEY}],
            context_key=TOPOLOGY_FRONTIER_CONTEXT_KEY,
            minimum_contact_score=0.5,
            minimum_sources=1,
        )
        self.assertEqual(report.contacts[0].state, FrontierState.REVIEW)
        self.assertIn("weak_ecDNA_contact", {issue.code for issue in report.contacts[0].issues})

    def test_ecdna_model_marks_context_issue(self) -> None:
        report = EcDNARegulatoryContactModel().evaluate(
            [{"amplicon_id": "a", "element_id": "e", "gene_id": "g", "contact_score": 0.8, "source_ids": ["s1"], "context_key": "other"}],
            context_key=TOPOLOGY_FRONTIER_CONTEXT_KEY,
        )
        self.assertEqual(report.contacts[0].state, FrontierState.REVIEW)
        self.assertIn("ecDNA_context_mismatch", {issue.code for issue in report.contacts[0].issues})

    def test_ecdna_model_rejects_non_object(self) -> None:
        with self.assertRaises(ValidationError):
            EcDNARegulatoryContactModel().evaluate(["bad"], context_key=TOPOLOGY_FRONTIER_CONTEXT_KEY)

    def test_ecdna_model_requires_positive_source_count(self) -> None:
        with self.assertRaises(ValidationError):
            EcDNARegulatoryContactModel().evaluate([], context_key=TOPOLOGY_FRONTIER_CONTEXT_KEY, minimum_sources=0)

    def test_compartment_model_reports_b_to_a_switch(self) -> None:
        report = CompartmentSwitchEstimator().estimate(
            [{"region_id": "r", "previous_score": -0.4, "current_score": 0.5}],
            context_key=TOPOLOGY_FRONTIER_CONTEXT_KEY,
            switch_threshold=0.15,
        )
        result = report.switches[0]
        self.assertEqual(result.switch_kind, "B_to_A")
        self.assertEqual(result.state, FrontierState.ACCEPTED)
        self.assertEqual(report.switched_ids, ("r",))

    def test_compartment_model_reports_stable_state(self) -> None:
        report = CompartmentSwitchEstimator().estimate(
            [{"region_id": "r", "previous_score": 0.4, "current_score": 0.45}],
            context_key=TOPOLOGY_FRONTIER_CONTEXT_KEY,
            switch_threshold=0.15,
        )
        self.assertEqual(report.switches[0].switch_kind, "stable")
        self.assertEqual(report.switches[0].state, FrontierState.REVIEW)
        self.assertEqual(report.stable_ids, ("r",))

    def test_compartment_model_handles_negative_to_negative(self) -> None:
        report = CompartmentSwitchEstimator().estimate(
            [{"region_id": "r", "previous_score": -0.8, "current_score": -0.2}],
            context_key=TOPOLOGY_FRONTIER_CONTEXT_KEY,
            switch_threshold=0.15,
        )
        self.assertEqual(report.switches[0].previous_compartment, "B")
        self.assertEqual(report.switches[0].current_compartment, "B")
        self.assertEqual(report.switches[0].switch_kind, "stable")

    def test_compartment_model_rejects_missing_current_score(self) -> None:
        with self.assertRaises(ValidationError):
            CompartmentSwitchEstimator().estimate(
                [{"region_id": "r", "previous_score": 0.2}],
                context_key=TOPOLOGY_FRONTIER_CONTEXT_KEY,
            )

    def test_compartment_model_rejects_empty_context(self) -> None:
        with self.assertRaises(ValidationError):
            CompartmentSwitchEstimator().estimate([], context_key="")

    def test_transport_model_accepts_contiguous_path(self) -> None:
        report = TopologyUncertaintyTransportModel().transport(
            [{"path_id": "p", "node_ids": ["a", "b", "c"], "edges": [{"uncertainty": 0.1}, {"uncertainty": 0.1}], "signal": 0.9}],
            context_key=TOPOLOGY_FRONTIER_CONTEXT_KEY,
            minimum_effective_signal=0.3,
        )
        result = report.transports[0]
        self.assertEqual(result.state, FrontierState.ACCEPTED)
        self.assertAlmostEqual(result.effective_signal, 0.72)
        self.assertEqual(report.supported_ids, ("p",))

    def test_transport_model_marks_weak_effective_signal(self) -> None:
        report = TopologyUncertaintyTransportModel().transport(
            [{"path_id": "p", "node_ids": ["a", "b"], "edges": [{"uncertainty": 0.9}], "signal": 0.4}],
            context_key=TOPOLOGY_FRONTIER_CONTEXT_KEY,
            minimum_effective_signal=0.3,
        )
        self.assertEqual(report.transports[0].state, FrontierState.REVIEW)
        self.assertIn("weak_transported_signal", {issue.code for issue in report.transports[0].issues})

    def test_transport_model_marks_disconnected_path(self) -> None:
        report = TopologyUncertaintyTransportModel().transport(
            [{"path_id": "p", "node_ids": ["a", "b", "c"], "edges": [{"uncertainty": 0.1}], "signal": 0.9}],
            context_key=TOPOLOGY_FRONTIER_CONTEXT_KEY,
        )
        self.assertEqual(report.transports[0].state, FrontierState.REVIEW)
        self.assertIn("topology_path_disconnected", {issue.code for issue in report.transports[0].issues})

    def test_transport_model_bounds_accumulated_uncertainty(self) -> None:
        report = TopologyUncertaintyTransportModel().transport(
            [{"path_id": "p", "node_ids": ["a", "b", "c", "d"], "edges": [{"uncertainty": 0.8}, {"uncertainty": 0.8}, {"uncertainty": 0.8}], "signal": 1.0}],
            context_key=TOPOLOGY_FRONTIER_CONTEXT_KEY,
        )
        self.assertEqual(report.transports[0].uncertainty, 2.4)
        self.assertEqual(report.transports[0].effective_signal, 0.0)

    def test_transport_model_rejects_invalid_edge_value(self) -> None:
        with self.assertRaises(ValidationError):
            TopologyUncertaintyTransportModel().transport(
                [{"path_id": "p", "node_ids": ["a", "b"], "edges": [{"uncertainty": "bad"}], "signal": 0.9}],
                context_key=TOPOLOGY_FRONTIER_CONTEXT_KEY,
            )

    def test_publisher_accepts_paths_and_assays(self) -> None:
        bundle = ThreeDEvidencePublisher().publish(
            [{"path_id": "p", "context_key": TOPOLOGY_FRONTIER_CONTEXT_KEY}],
            bundle_id="b",
            context_key=TOPOLOGY_FRONTIER_CONTEXT_KEY,
            assay_ids=("hi-c", "micro-c"),
        )
        self.assertEqual(bundle.state, FrontierState.PUBLISHED)
        self.assertEqual(bundle.path_ids, ("p",))
        self.assertTrue(bundle.records_address.startswith("sha256:"))
        self.assertTrue(bundle.bundle_address.startswith("sha256:"))

    def test_publisher_sorts_path_and_assay_ids(self) -> None:
        bundle = ThreeDEvidencePublisher().publish(
            [{"path_id": "z", "context_key": TOPOLOGY_FRONTIER_CONTEXT_KEY}, {"path_id": "a", "context_key": TOPOLOGY_FRONTIER_CONTEXT_KEY}],
            bundle_id="b",
            context_key=TOPOLOGY_FRONTIER_CONTEXT_KEY,
            assay_ids=("micro-c", "hi-c", "hi-c"),
        )
        self.assertEqual(bundle.path_ids, ("a", "z"))

    def test_publisher_rejects_empty_rows(self) -> None:
        with self.assertRaises(ValidationError):
            ThreeDEvidencePublisher().publish([], bundle_id="b", context_key=TOPOLOGY_FRONTIER_CONTEXT_KEY, assay_ids=("hi-c",))

    def test_publisher_rejects_empty_assays(self) -> None:
        with self.assertRaises(ValidationError):
            ThreeDEvidencePublisher().publish([{"path_id": "p", "context_key": TOPOLOGY_FRONTIER_CONTEXT_KEY}], bundle_id="b", context_key=TOPOLOGY_FRONTIER_CONTEXT_KEY, assay_ids=())

    def test_publisher_rejects_other_context(self) -> None:
        with self.assertRaises(ValidationError):
            ThreeDEvidencePublisher().publish([{"path_id": "p", "context_key": "other"}], bundle_id="b", context_key=TOPOLOGY_FRONTIER_CONTEXT_KEY, assay_ids=("hi-c",))

    def test_catalog_covers_all_records_and_operations(self) -> None:
        catalog = build_topology_frontier_catalog(self.fixture)
        self.assertEqual(len(catalog.record_ids), 16)
        self.assertEqual(len(catalog.source_ids), 5)
        self.assertEqual(set(catalog.operations), set(TopologyFrontierOperation))

    def test_fixture_round_trip_preserves_address(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.json"
            path.write_text(json.dumps(self.fixture.to_dict()), encoding="utf-8")
            loaded = load_topology_frontier_fixture(path)
            self.assertEqual(loaded.fixture_id, self.fixture.fixture_id)
            self.assertEqual(loaded.content_address, self.fixture.content_address)
            self.assertEqual(tuple(item.record_id for item in loaded.records), tuple(item.record_id for item in self.fixture.records))

    def test_source_receipts_are_https(self) -> None:
        self.assertTrue(all(item.uri.startswith("https://") for item in self.fixture.sources))

    def test_record_addresses_are_stable(self) -> None:
        second = default_topology_frontier_fixture()
        self.assertEqual(tuple(item.content_address for item in self.fixture.records), tuple(item.content_address for item in second.records))

    def test_evaluation_address_is_stable(self) -> None:
        second = evaluate_topology_frontier_fixture(default_topology_frontier_fixture())
        self.assertEqual(self.evaluation.content_address, second.content_address)

    def test_policy_accepts_default_evaluation(self) -> None:
        report = evaluate_topology_frontier_policy(self.fixture, self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.rules), 8)

    def test_schema_accepts_default_evaluation(self) -> None:
        report = validate_topology_frontier_schema(self.evaluation, schemas=default_topology_frontier_schemas())
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 20)

    def test_lineage_edge_count_matches_evaluation(self) -> None:
        report = build_topology_frontier_lineage(self.fixture, self.evaluation)
        self.assertEqual(len(report.edges), len(self.evaluation.receipts))
        self.assertTrue(report.accepted)

    def test_reconciliation_item_count_matches_fixture(self) -> None:
        report = reconcile_topology_frontier(self.fixture, self.evaluation)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.items), len(self.fixture.records))

    def test_metrics_total_issue_count_is_nonzero(self) -> None:
        metrics = compute_topology_frontier_metrics(self.evaluation)
        self.assertGreater(metrics.total_issues, 0)
        self.assertEqual(len(metrics.operation_metrics), 4)

    def test_quality_gate_data_audit_is_first(self) -> None:
        report = run_topology_frontier_quality_gate(self.fixture)
        self.assertEqual(report.checks[0].check_id, "data-audit")
        self.assertTrue(report.accepted)

    def test_view_operation_rows_have_four_records(self) -> None:
        view = build_topology_frontier_view(self.fixture, self.evaluation)
        self.assertTrue(all(len(item.record_ids) == 4 for item in view.operation_views))
        self.assertEqual(len(view.review_queue), 12)

    def test_view_priority_separates_boundary_and_partial(self) -> None:
        view = build_topology_frontier_view(self.fixture, self.evaluation)
        high = filter_topology_frontier_review_queue(view, maximum_priority=2)
        self.assertEqual(len(high), 6)
        self.assertTrue(all(item.priority <= 2 for item in high))

    def test_each_operation_has_one_supported_record(self) -> None:
        for operation in TopologyFrontierOperation:
            rows = tuple(item for item in self.evaluation.receipts if item.operation is operation)
            self.assertEqual(sum(item.adapter_state == "supported" for item in rows), 1)

    def test_each_operation_has_three_control_records(self) -> None:
        for operation in TopologyFrontierOperation:
            rows = tuple(item for item in self.evaluation.receipts if item.operation is operation)
            self.assertEqual(sum(item.role is TopologyFrontierRole.CONTROL for item in rows), 3)

    def test_all_positive_records_have_no_issue_codes(self) -> None:
        positives = tuple(item for item in self.evaluation.receipts if item.role is TopologyFrontierRole.POSITIVE)
        self.assertTrue(all(item.observed_issue_codes == () for item in positives))

    def test_all_control_records_have_review_or_boundary_state(self) -> None:
        controls = tuple(item for item in self.evaluation.receipts if item.role is TopologyFrontierRole.CONTROL)
        self.assertTrue(all(item.adapter_state in {"partial", "out_of_domain", "invalid"} for item in controls))


if __name__ == "__main__":
    unittest.main()
