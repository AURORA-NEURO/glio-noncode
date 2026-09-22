from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode._cli_sequence_batch import build_batch_report
from glio_noncode.errors import StoreError, ValidationError
from glio_noncode.sequence_batch_store import (
    BATCH_CATALOG_SCHEMA,
    SequenceBatchStore,
    validate_sequence_batch_report,
)
from glio_noncode.serialization import canonical_json
from tests.test_cli_sequence_batch import _batch_input


class SequenceBatchStoreTests(unittest.TestCase):
    def test_save_reopen_catalog_and_summary_are_immutable(self) -> None:
        report = build_batch_report(_batch_input())
        with tempfile.TemporaryDirectory() as directory:
            store = SequenceBatchStore(directory)
            record = store.save(report)
            self.assertRegex(record["batch_id"], r"^batch-[0-9a-f]{64}$")
            self.assertEqual(record, store.save(report))
            catalog = store.list_reports(limit=5)
            self.assertEqual(catalog["schema"], BATCH_CATALOG_SCHEMA)
            self.assertEqual(catalog["total_count"], 1)
            self.assertEqual(catalog["rows"][0]["supported_count"], 2)
            reopened = store.get_report(record["batch_id"])
            self.assertEqual(reopened["report"], json.loads(canonical_json(report)))
            self.assertNotIn("PRIVATE_SAMPLE_1", json.dumps(catalog))

    def test_validator_rejects_private_keys_and_bad_state_counts(self) -> None:
        report = build_batch_report(_batch_input())
        private = json.loads(canonical_json(report))
        private["records"][0]["sample_id"] = "PRIVATE_SAMPLE_1"
        with self.assertRaisesRegex(ValidationError, "private individual key"):
            validate_sequence_batch_report(private)
        invalid = json.loads(canonical_json(report))
        invalid["design"]["supported_count"] = 1
        with self.assertRaisesRegex(ValidationError, "state counts"):
            validate_sequence_batch_report(invalid)

    def test_catalog_object_tampering_is_detected(self) -> None:
        report = build_batch_report(_batch_input())
        with tempfile.TemporaryDirectory() as directory:
            store = SequenceBatchStore(directory)
            record = store.save(report)
            object_path = (
                Path(directory) / "objects" / f"{record['report_address'].split(':', 1)[1]}.json"
            )
            raw = json.loads(object_path.read_text(encoding="utf-8"))
            raw["status"] = "invalid"
            object_path.write_text(
                json.dumps(raw, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            with self.assertRaises((StoreError, ValidationError)):
                store.get_report(record["batch_id"])

    def test_catalog_pagination_and_unknown_batch_are_bounded(self) -> None:
        report = build_batch_report(_batch_input())
        with tempfile.TemporaryDirectory() as directory:
            store = SequenceBatchStore(directory)
            record = store.save(report)
            self.assertFalse(store.list_reports(offset=1, limit=1)["rows"])
            with self.assertRaisesRegex(ValidationError, "limit"):
                store.list_reports(limit=0)
            with self.assertRaises(KeyError):
                store.get_report("batch-" + "0" * 64)
            self.assertEqual(store.get_report(record["batch_id"])["batch_id"], record["batch_id"])

    def test_catalog_record_tampering_is_detected_before_report_read(self) -> None:
        report = build_batch_report(_batch_input())
        with tempfile.TemporaryDirectory() as directory:
            store = SequenceBatchStore(directory)
            record = store.save(report)
            record_path = Path(directory) / "sequence-batches" / f"{record['batch_id']}.json"
            raw = json.loads(record_path.read_text(encoding="utf-8"))
            raw["summary"]["supported_count"] = 0
            record_path.write_text(
                json.dumps(raw, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            with self.assertRaises(StoreError):
                store.get_report(record["batch_id"])

    def test_batch_change_pages_and_csv_keep_aggregate_boundary(self) -> None:
        report = build_batch_report(_batch_input())
        with tempfile.TemporaryDirectory() as directory:
            store = SequenceBatchStore(directory)
            record = store.save(report)
            page = store.page_changes(record["batch_id"], motif_contains="joint")
            self.assertEqual(page["schema"], "glio-noncode.sequence-haplotype-batch-changes.v1")
            self.assertEqual(page["total_changes"], 1)
            self.assertEqual(page["filtered_change_summary"]["change_count"], 1)
            self.assertEqual(page["filtered_change_summary"]["created_count"], 1)
            self.assertEqual(page["filtered_change_summary"]["analysis_count_total"], 2)
            self.assertAlmostEqual(page["filtered_change_summary"]["mean_analysis_fraction"], 2 / 3)
            self.assertAlmostEqual(page["filtered_change_summary"]["max_analysis_fraction"], 2 / 3)
            self.assertEqual(page["changes"][0]["analysis_count"], 2)
            csv_body = store.changes_csv(record["batch_id"], change="created")
            self.assertIn("analysis_fraction", csv_body.splitlines()[0])
            self.assertIn("jointly-created motif", csv_body)
            self.assertNotIn("PRIVATE_SAMPLE_1", csv_body)
            with self.assertRaisesRegex(ValidationError, "change must"):
                store.page_changes(record["batch_id"], change="unknown")
