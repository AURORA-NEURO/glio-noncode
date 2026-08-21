from __future__ import annotations

import unittest

from glio_noncode.reference_annotation_bundle import (
    ReferenceAnnotationBundleBuilder,
    ReferenceAnnotationBundleFormat,
)
from glio_noncode.reference_annotation_fixture_eval import evaluate_reference_annotation_fixture
from glio_noncode.reference_annotation_lineage import build_reference_annotation_lineage
from glio_noncode.reference_annotation_public_data import default_reference_annotation_fixture
from glio_noncode.reference_annotation_quality_gate import (
    evaluate_reference_annotation_quality_gate,
)
from glio_noncode.reference_annotation_reconciliation import reconcile_reference_annotation_views


class ReferenceAnnotationQualityBundleTests(unittest.TestCase):
    def test_quality_gate_accepts_all_integrated_components(self) -> None:
        report = evaluate_reference_annotation_quality_gate()
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 23)
        self.assertEqual(report.failed_check_ids, ())

    def test_accepted_only_bundle_has_four_positive_entries(self) -> None:
        fixture = default_reference_annotation_fixture()
        evaluation = evaluate_reference_annotation_fixture(fixture)
        builder = ReferenceAnnotationBundleBuilder()
        bundle = builder.build(evaluation, fixture=fixture, accepted_only=True)
        self.assertTrue(bundle.published)
        self.assertEqual(len(bundle.entries), 4)
        self.assertEqual(bundle.review_count, 0)
        self.assertEqual(builder.verify(bundle), ())

    def test_review_bundle_retains_all_sixteen_entries(self) -> None:
        fixture = default_reference_annotation_fixture()
        evaluation = evaluate_reference_annotation_fixture(fixture)
        bundle = ReferenceAnnotationBundleBuilder().build(evaluation, fixture=fixture)
        self.assertFalse(bundle.published)
        self.assertEqual(len(bundle.entries), 16)
        self.assertEqual(bundle.review_count, 12)

    def test_bundle_renderings_are_terminal_and_structured(self) -> None:
        fixture = default_reference_annotation_fixture()
        evaluation = evaluate_reference_annotation_fixture(fixture)
        bundle = ReferenceAnnotationBundleBuilder().build(
            evaluation, fixture=fixture, accepted_only=True
        )
        builder = ReferenceAnnotationBundleBuilder()
        json_text = builder.render(bundle, ReferenceAnnotationBundleFormat.JSON)
        csv_text = builder.render(bundle, ReferenceAnnotationBundleFormat.CSV)
        markdown = builder.render(bundle, ReferenceAnnotationBundleFormat.MARKDOWN)
        self.assertTrue(json_text.endswith("\n"))
        self.assertEqual(len(csv_text.splitlines()), 5)
        self.assertIn("| Record | Capability |", markdown)

    def test_bundle_address_changes_when_entry_state_changes(self) -> None:
        fixture = default_reference_annotation_fixture()
        evaluation = evaluate_reference_annotation_fixture(fixture)
        builder = ReferenceAnnotationBundleBuilder()
        bundle = builder.build(evaluation, fixture=fixture, accepted_only=True)
        entry = bundle.entries[0]
        mutated_entry = entry.__class__(
            entry.entry_id,
            entry.record_id,
            entry.capability_id,
            entry.operation,
            entry.role,
            entry.context_key,
            "ambiguous",
            entry.issue_codes,
            entry.match_count,
            entry.source_ids,
            entry.evidence_boundary,
            entry.content_address,
        )
        mutated = bundle.__class__(
            bundle.bundle_id,
            bundle.fixture_id,
            bundle.fixture_version,
            bundle.context_key,
            bundle.evidence_boundary,
            bundle.published,
            (mutated_entry,) + bundle.entries[1:],
            bundle.content_address,
        )
        self.assertIn("entry-address", builder.verify(mutated))

    def test_lineage_has_expected_nodes_edges_and_audit(self) -> None:
        fixture = default_reference_annotation_fixture()
        evaluation = evaluate_reference_annotation_fixture(fixture)
        graph = build_reference_annotation_lineage(evaluation, fixture=fixture)
        self.assertTrue(graph.audit.accepted)
        self.assertEqual(len(graph.nodes), 38)
        self.assertEqual(len(graph.edges), 59)

    def test_lineage_contains_one_result_per_record(self) -> None:
        fixture = default_reference_annotation_fixture()
        evaluation = evaluate_reference_annotation_fixture(fixture)
        graph = build_reference_annotation_lineage(evaluation, fixture=fixture)
        result_nodes = [node for node in graph.nodes if node.kind.value == "result"]
        self.assertEqual(len(result_nodes), 16)

    def test_reconciliation_accepts_evaluation_bundle_and_lineage(self) -> None:
        fixture = default_reference_annotation_fixture()
        evaluation = evaluate_reference_annotation_fixture(fixture)
        builder = ReferenceAnnotationBundleBuilder()
        bundle = builder.build(evaluation, fixture=fixture, accepted_only=True)
        graph = build_reference_annotation_lineage(evaluation, fixture=fixture)
        report = reconcile_reference_annotation_views(evaluation, bundle, graph, fixture=fixture)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 17)

    def test_reconciliation_detects_wrong_fixture_id(self) -> None:
        fixture = default_reference_annotation_fixture()
        evaluation = evaluate_reference_annotation_fixture(fixture)
        builder = ReferenceAnnotationBundleBuilder()
        bundle = builder.build(evaluation, fixture=fixture, accepted_only=True)
        graph = build_reference_annotation_lineage(evaluation, fixture=fixture)
        wrong_bundle = bundle.__class__(
            bundle.bundle_id,
            "wrong-fixture",
            bundle.fixture_version,
            bundle.context_key,
            bundle.evidence_boundary,
            bundle.published,
            bundle.entries,
            bundle.content_address,
        )
        report = reconcile_reference_annotation_views(
            evaluation, wrong_bundle, graph, fixture=fixture
        )
        self.assertFalse(report.accepted)
        self.assertIn("fixture-id", report.failed_check_ids)
