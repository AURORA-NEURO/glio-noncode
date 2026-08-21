from __future__ import annotations

import json
import unittest
from pathlib import Path

from glio_noncode.reference_coordinate_fixture_eval import (
    ReferenceCoordinateFixtureEvaluator,
    evaluate_reference_coordinate_fixture,
)
from glio_noncode.reference_coordinate_public_data import ReferenceCoordinateFixtureCatalog

FIXTURE = Path(__file__).parents[1] / "examples" / "reference-coordinate-public-aggregate.json"


class ReferenceCoordinateFixtureEvaluationTests(unittest.TestCase):
    def load(self) -> ReferenceCoordinateFixtureCatalog:
        return ReferenceCoordinateFixtureCatalog.from_file(FIXTURE)

    def test_full_fixture_passes_with_deep_check_floor(self) -> None:
        report = evaluate_reference_coordinate_fixture(self.load())
        self.assertEqual(report.state, "accepted")
        self.assertTrue(report.passed)
        self.assertEqual(len(report.receipts), 16)
        self.assertEqual(len(report.checks), 134)
        self.assertEqual(report.failed_check_ids, ())

    def test_each_operation_has_positive_and_control_receipts(self) -> None:
        report = evaluate_reference_coordinate_fixture(self.load())
        for operation in {receipt.operation for receipt in report.receipts}:
            rows = [receipt for receipt in report.receipts if receipt.operation == operation]
            self.assertTrue(any(receipt.role.value == "positive" for receipt in rows))
            self.assertTrue(any(receipt.role.value == "control" for receipt in rows))

    def test_controls_retain_distinct_issue_codes_and_states(self) -> None:
        report = evaluate_reference_coordinate_fixture(self.load())
        controls = [receipt for receipt in report.receipts if receipt.role.value == "control"]
        self.assertTrue(all(receipt.state.value != "supported" for receipt in controls))
        issue_codes = {code for receipt in controls for code in receipt.issue_codes}
        self.assertEqual(
            issue_codes,
            {
                "reference_alias_unknown",
                "chain_parse_issue",
                "chain_breakend_abstained",
                "chain_unmapped",
                "ambiguity_competing",
                "ambiguity_absent",
                "pangenome_multiple",
                "pangenome_absent",
            },
        )

    def test_forward_projection_summary_retains_mapping_without_raw_chain(self) -> None:
        report = evaluate_reference_coordinate_fixture(self.load())
        receipt = next(
            receipt
            for receipt in report.receipts
            if receipt.record_id == "d04-c02-positive-forward-chain"
        )
        self.assertEqual(receipt.state.value, "supported")
        self.assertEqual(receipt.result_summary["mapping_id"], "chain-grch38-grch37-7")
        self.assertEqual(receipt.result_summary["projected_build"], "GRCh37")
        self.assertNotIn("chain_text", receipt.result_summary)

    def test_pangenome_summary_retains_all_competing_path_ids(self) -> None:
        report = evaluate_reference_coordinate_fixture(self.load())
        receipt = next(
            receipt
            for receipt in report.receipts
            if receipt.record_id == "d04-c04-control-multiple-hprc-paths"
        )
        self.assertEqual(receipt.state.value, "ambiguous")
        self.assertEqual(
            receipt.result_summary["candidate_path_ids"],
            ("hprc-v2-grch38-primary-7", "hprc-v2-grch38-alt-7"),
        )
        self.assertEqual(receipt.result_summary["candidate_count"], 2)

    def test_evaluation_is_deterministic(self) -> None:
        catalog = self.load()
        first = evaluate_reference_coordinate_fixture(catalog)
        second = ReferenceCoordinateFixtureEvaluator().evaluate(catalog)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_mutated_expected_state_is_visible_as_review(self) -> None:
        raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        raw["records"][0]["expected_state"] = "abstained"
        mutated = ReferenceCoordinateFixtureCatalog.from_mapping(raw)
        report = evaluate_reference_coordinate_fixture(mutated)
        self.assertEqual(report.state, "review")
        self.assertIn("d04-c01-positive-hg38-alias:state", report.failed_check_ids)

    def test_receipts_are_sanitized_and_content_addressed(self) -> None:
        report = evaluate_reference_coordinate_fixture(self.load())
        serialized = json.dumps(report.to_dict(), sort_keys=True)
        self.assertNotIn("chain_text", serialized)
        self.assertNotIn("subject_id", serialized)
        self.assertTrue(
            all(receipt.content_address.startswith("sha256:") for receipt in report.receipts)
        )

    def test_evaluator_preserves_exact_context_on_every_receipt(self) -> None:
        catalog = self.load()
        report = evaluate_reference_coordinate_fixture(catalog)
        self.assertTrue(
            all(receipt.context_key == catalog.context_key for receipt in report.receipts)
        )


if __name__ == "__main__":
    unittest.main()
