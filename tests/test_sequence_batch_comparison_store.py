from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode._cli_sequence_batch import build_batch_report
from glio_noncode._cli_sequence_batch_compare import build_batch_comparison, main
from glio_noncode.errors import StoreError, ValidationError
from glio_noncode.sequence_batch_comparison_store import (
    COMPARISON_CATALOG_SCHEMA,
    COMPARISON_CHANGES_SCHEMA,
    SequenceBatchComparisonStore,
    validate_sequence_batch_comparison,
)
from tests.test_cli_sequence import _input
from tests.test_cli_sequence_batch import _batch_input


class SequenceBatchComparisonStoreTests(unittest.TestCase):
    def test_save_catalog_reopen_change_page_and_csv(self) -> None:
        left = build_batch_report(
            {"schema": "glio-noncode.sequence-haplotype-batch-input.v1", "analyses": [_input()]}
        )
        right = build_batch_report(_batch_input())
        report = build_batch_comparison(left, right)
        with tempfile.TemporaryDirectory() as directory:
            store = SequenceBatchComparisonStore(directory)
            record = store.save(report)
            self.assertRegex(record["comparison_id"], r"^comparison-[0-9a-f]{64}$")
            self.assertEqual(record, store.save(report))
            catalog = store.list_reports(limit=5)
            self.assertEqual(catalog["schema"], COMPARISON_CATALOG_SCHEMA)
            self.assertEqual(catalog["total_count"], 1)
            reopened = store.get_report(record["comparison_id"])
            self.assertEqual(reopened["report"]["content_address"], report["content_address"])
            changes = store.page_changes(record["comparison_id"], direction="decreased")
            self.assertEqual(changes["schema"], COMPARISON_CHANGES_SCHEMA)
            self.assertEqual(changes["total_changes"], 1)
            self.assertEqual(changes["filtered_change_summary"]["change_count"], 1)
            self.assertEqual(changes["filtered_change_summary"]["decreased_count"], 1)
            self.assertEqual(changes["filtered_change_summary"]["delta_count"], 1)
            self.assertAlmostEqual(
                changes["filtered_change_summary"]["mean_absolute_delta_fraction"],
                1 / 3,
            )
            csv_body = store.changes_csv(record["comparison_id"], motif_contains="joint")
            self.assertIn("delta_fraction", csv_body.splitlines()[0])
            self.assertIn("jointly-created motif", csv_body)

    def test_validator_rejects_inconsistent_direction_and_private_keys(self) -> None:
        left = build_batch_report(
            {"schema": "glio-noncode.sequence-haplotype-batch-input.v1", "analyses": [_input()]}
        )
        right = build_batch_report(_batch_input())
        report = build_batch_comparison(left, right)
        invalid = json.loads(json.dumps(report))
        invalid["changes"][0]["direction"] = "unchanged"
        with self.assertRaisesRegex(ValidationError, "direction"):
            validate_sequence_batch_comparison(invalid)
        private = json.loads(json.dumps(report))
        private["changes"][0]["sample_id"] = "PRIVATE_SAMPLE_1"
        with self.assertRaisesRegex(ValidationError, "invalid shape"):
            validate_sequence_batch_comparison(private)

    def test_object_tampering_is_detected(self) -> None:
        left = build_batch_report(
            {"schema": "glio-noncode.sequence-haplotype-batch-input.v1", "analyses": [_input()]}
        )
        right = build_batch_report(_batch_input())
        report = build_batch_comparison(left, right)
        with tempfile.TemporaryDirectory() as directory:
            store = SequenceBatchComparisonStore(directory)
            record = store.save(report)
            object_path = (
                Path(directory) / "objects" / f"{record['report_address'].split(':', 1)[1]}.json"
            )
            raw = json.loads(object_path.read_text(encoding="utf-8"))
            raw["status"] = "invalid"
            object_path.write_text(json.dumps(raw, sort_keys=True), encoding="utf-8")
            with self.assertRaises((StoreError, ValidationError)):
                store.get_report(record["comparison_id"])

    def test_cli_can_persist_comparison(self) -> None:
        left = build_batch_report(
            {"schema": "glio-noncode.sequence-haplotype-batch-input.v1", "analyses": [_input()]}
        )
        right = build_batch_report(_batch_input())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left_path = root / "left.json"
            right_path = root / "right.json"
            output_path = root / "comparison.json"
            left_path.write_text(json.dumps(left), encoding="utf-8")
            right_path.write_text(json.dumps(right), encoding="utf-8")
            self.assertEqual(
                main(
                    [
                        str(left_path),
                        str(right_path),
                        "--output",
                        str(output_path),
                        "--save-to-workspace",
                        "--data-root",
                        str(root / "workspace"),
                    ]
                ),
                0,
            )
            self.assertEqual(
                len(list((root / "workspace" / "sequence-comparisons").glob("comparison-*.json"))),
                1,
            )


if __name__ == "__main__":
    unittest.main()
