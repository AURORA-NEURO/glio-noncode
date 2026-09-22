from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode._cli_sequence import build_analysis_report
from glio_noncode.errors import StoreError, ValidationError
from glio_noncode.sequence_haplotype_store import (
    SEQUENCE_ANALYSIS_CATALOG_SCHEMA,
    SequenceHaplotypeStore,
    validate_sequence_haplotype_report,
)
from glio_noncode.serialization import canonical_json
from tests.test_cli_sequence import _input


class SequenceHaplotypeStoreTests(unittest.TestCase):
    def test_save_catalog_reopen_and_bounded_change_projections(self) -> None:
        report = build_analysis_report(_input())
        with tempfile.TemporaryDirectory() as directory:
            store = SequenceHaplotypeStore(directory)
            record = store.save(report)
            self.assertRegex(record["analysis_id"], r"^seq-[0-9a-f]{64}$")
            self.assertEqual(record, store.save(report))

            catalog = store.list_reports(limit=5)
            self.assertEqual(catalog["schema"], SEQUENCE_ANALYSIS_CATALOG_SCHEMA)
            self.assertEqual(catalog["total_count"], 1)
            self.assertEqual(catalog["rows"][0]["created_motif_count"], 1)
            self.assertNotIn("AACCGGTTAACC", json.dumps(catalog))
            saved = store.get_report(record["analysis_id"])
            self.assertEqual(saved["report"], json.loads(canonical_json(report)))

            changes = store.page_changes(record["analysis_id"], motif_contains="JOINT")
            self.assertEqual(changes["total_changes"], 1)
            self.assertEqual(changes["changes"][0]["change"], "created")
            self.assertEqual(
                store.page_changes(record["analysis_id"], change="disrupted")["total_changes"],
                0,
            )
            csv_body = store.changes_csv(record["analysis_id"], change="created")
            self.assertIn("matched_sequence", csv_body.splitlines()[0])
            self.assertIn("CTAG", csv_body)
            self.assertNotIn("PRIVATE_SAMPLE_1", csv_body)

    def test_abstained_report_with_nullable_alternate_fields_is_storable(self) -> None:
        source = _input()
        source["variants"] = [dict(source["variants"][0], notation="7:103:BND:chr8:200")]  # type: ignore[index]
        report = build_analysis_report(source)
        self.assertEqual(report["analysis_state"], "abstained")
        with tempfile.TemporaryDirectory() as directory:
            saved = SequenceHaplotypeStore(directory).save(report)
            self.assertEqual(saved["summary"]["analysis_state"], "abstained")

    def test_public_validator_rejects_raw_input_and_private_output_keys(self) -> None:
        with self.assertRaisesRegex(ValidationError, "complete v1 report"):
            validate_sequence_haplotype_report(_input())
        report = build_analysis_report(_input())
        private = json.loads(json.dumps(report))
        private["analysis"]["sample_id"] = "PRIVATE_SAMPLE_1"
        with self.assertRaisesRegex(ValidationError, "private individual key"):
            validate_sequence_haplotype_report(private)

    def test_object_tampering_is_detected_on_reopen(self) -> None:
        report = build_analysis_report(_input())
        with tempfile.TemporaryDirectory() as directory:
            store = SequenceHaplotypeStore(directory)
            record = store.save(report)
            object_path = (
                Path(directory)
                / "objects"
                / f"{record['report_address'].split(':', 1)[1]}.json"
            )
            raw = json.loads(object_path.read_text(encoding="utf-8"))
            raw["analysis_state"] = "abstained"
            object_path.write_text(
                json.dumps(raw, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            with self.assertRaises((StoreError, ValidationError)):
                store.get_report(record["analysis_id"])

    def test_bounds_and_unknown_filters_are_rejected(self) -> None:
        report = build_analysis_report(_input())
        with tempfile.TemporaryDirectory() as directory:
            store = SequenceHaplotypeStore(directory)
            record = store.save(report)
            with self.assertRaisesRegex(ValidationError, "change must be"):
                store.page_changes(record["analysis_id"], change="unknown")
            with self.assertRaisesRegex(ValidationError, "limit"):
                store.list_reports(limit=0)
