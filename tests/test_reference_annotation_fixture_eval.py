from __future__ import annotations

import unittest

from glio_noncode.reference_annotation_fixture_eval import evaluate_reference_annotation_fixture
from glio_noncode.reference_annotation_public_data import (
    ReferenceAnnotationRole,
    default_reference_annotation_fixture,
)


class ReferenceAnnotationFixtureEvaluationTests(unittest.TestCase):
    def test_fixture_evaluation_is_accepted_with_deep_check_floor(self) -> None:
        report = evaluate_reference_annotation_fixture()
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.receipts), 16)
        self.assertEqual(len(report.checks), 120)
        self.assertEqual(report.failed_check_ids, ())

    def test_every_operation_has_one_positive_and_three_controls(self) -> None:
        report = evaluate_reference_annotation_fixture()
        for operation in {receipt.operation for receipt in report.receipts}:
            rows = [receipt for receipt in report.receipts if receipt.operation is operation]
            self.assertEqual(sum(row.role is ReferenceAnnotationRole.POSITIVE for row in rows), 1)
            self.assertEqual(sum(row.role is ReferenceAnnotationRole.CONTROL for row in rows), 3)

    def test_sanitized_receipts_exclude_input_text(self) -> None:
        report = evaluate_reference_annotation_fixture()
        self.assertTrue(all("input_text" not in receipt.summary for receipt in report.receipts))

    def test_gencode_ambiguity_retains_issue_and_two_matches(self) -> None:
        receipt = next(
            receipt
            for receipt in evaluate_reference_annotation_fixture().receipts
            if receipt.record_id == "C05-CTRL-002"
        )
        self.assertEqual(receipt.resolution_state, "ambiguous")
        self.assertEqual(receipt.match_count, 2)
        self.assertIn("ambiguous_transcript_match", receipt.observed_issue_codes)

    def test_mane_positive_resolves_refseq_identifier(self) -> None:
        receipt = next(
            receipt
            for receipt in evaluate_reference_annotation_fixture().receipts
            if receipt.record_id == "C06-POS-001"
        )
        self.assertEqual(receipt.resolution_state, "supported")
        self.assertEqual(receipt.match_count, 1)

    def test_regulatory_alias_collision_is_not_selected(self) -> None:
        receipt = next(
            receipt
            for receipt in evaluate_reference_annotation_fixture().receipts
            if receipt.record_id == "C07-CTRL-001"
        )
        self.assertEqual(receipt.resolution_state, "ambiguous")
        self.assertIn("term_match_ambiguous", receipt.observed_issue_codes)

    def test_disease_mapping_keeps_two_targets(self) -> None:
        receipt = next(
            receipt
            for receipt in evaluate_reference_annotation_fixture().receipts
            if receipt.record_id == "C08-CTRL-001"
        )
        self.assertEqual(receipt.resolution_state, "ambiguous")
        self.assertEqual(receipt.match_count, 2)

    def test_mutated_expected_state_is_visible_as_review(self) -> None:
        fixture = default_reference_annotation_fixture()
        record = fixture.records[0]
        mutated = record.__class__(
            record.record_id,
            record.operation,
            record.role,
            record.context_key,
            record.source_ids,
            record.payload,
            "ambiguous",
            record.expected_issue_codes,
            record.description,
            record.content_address,
        )
        records = (mutated,) + fixture.records[1:]
        mutated_fixture = fixture.__class__(
            fixture.fixture_id,
            fixture.fixture_version,
            fixture.context_key,
            fixture.evidence_boundary,
            fixture.sources,
            records,
            fixture.content_address,
        )
        report = evaluate_reference_annotation_fixture(mutated_fixture)
        self.assertFalse(report.accepted)
        self.assertIn("C05-POS-001:state", report.failed_check_ids)

    def test_evaluation_is_deterministic(self) -> None:
        first = evaluate_reference_annotation_fixture()
        second = evaluate_reference_annotation_fixture()
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(
            [item.content_address for item in first.receipts],
            [item.content_address for item in second.receipts],
        )

    def test_record_receipts_have_stable_capability_ids(self) -> None:
        report = evaluate_reference_annotation_fixture()
        self.assertEqual(
            {receipt.capability_id for receipt in report.receipts},
            {"GNC-D04-C05", "GNC-D04-C06", "GNC-D04-C07", "GNC-D04-C08"},
        )
