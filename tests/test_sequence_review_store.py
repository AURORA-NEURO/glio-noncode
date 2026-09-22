from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode._cli_sequence import build_analysis_report
from glio_noncode._cli_sequence_batch import build_batch_report
from glio_noncode._cli_sequence_review import main as review_main
from glio_noncode.errors import ValidationError
from glio_noncode.sequence_review_store import (
    SEQUENCE_REVIEW_MOTIFS_SCHEMA,
    SEQUENCE_REVIEW_SUMMARY_SCHEMA,
    SEQUENCE_REVIEW_VERIFY_SCHEMA,
    SequenceReviewStore,
)
from tests.test_cli_sequence import _input
from tests.test_cli_sequence_batch import _batch_input


class SequenceReviewStoreTests(unittest.TestCase):
    def _save_fixture_archive(self, directory: str) -> SequenceReviewStore:
        store = SequenceReviewStore(directory)
        store.analyses.save(build_analysis_report(_input()))
        store.batches.save(build_batch_report(_batch_input()))
        return store

    def test_summary_is_public_and_content_addressed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            summary = self._save_fixture_archive(directory).summary()
            self.assertEqual(summary["schema"], SEQUENCE_REVIEW_SUMMARY_SCHEMA)
            self.assertEqual(summary["catalogs"]["sequence_analyses"]["record_count"], 1)
            self.assertEqual(summary["catalogs"]["sequence_batches"]["record_count"], 1)
            self.assertTrue(summary["content_address"].startswith("sequence-review-summary:"))
            self.assertNotIn("AACCGGTTAACC", json.dumps(summary))
            self.assertNotIn("PRIVATE_SAMPLE_1", json.dumps(summary))

    def test_motif_activity_combines_single_and_batch_reports_with_exact_filters(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = self._save_fixture_archive(directory)
            page = store.motif_activity(motif_contains="joint", limit=10)
            self.assertEqual(page["schema"], SEQUENCE_REVIEW_MOTIFS_SCHEMA)
            self.assertEqual(page["total_count"], 1)
            self.assertEqual(page["filtered_motif_summary"]["row_count"], 1)
            self.assertEqual(page["filtered_motif_summary"]["created_row_count"], 1)
            self.assertEqual(page["filtered_motif_summary"]["occurrence_count"], 2)
            self.assertEqual(page["filtered_motif_summary"]["single_analysis_occurrence_count"], 1)
            self.assertEqual(page["filtered_motif_summary"]["batch_occurrence_count"], 1)
            self.assertEqual(page["filtered_motif_summary"]["motif_source_id_counts"]["motif-fixture"], 1)
            row = page["rows"][0]
            self.assertEqual(row["motif_id"], "joint")
            self.assertEqual(row["single_analysis_count"], 1)
            self.assertEqual(row["batch_count"], 1)
            self.assertAlmostEqual(row["max_batch_fraction"], 2 / 3)
            source_filtered = store.motif_activity(source_id="SRC-UCSC-REST", limit=10)
            self.assertEqual(source_filtered["filtered_motif_summary"]["row_count"], 1)
            self.assertEqual(store.motif_activity(change="disrupted")["total_count"], 0)
            csv_body = store.motifs_csv(motif_contains="joint")
            self.assertIn("single_analysis_count", csv_body.splitlines()[0])
            self.assertIn(",joint,jointly-created motif,", csv_body)
            self.assertNotIn("PRIVATE_SAMPLE_1", csv_body)

    def test_verification_reopens_both_objects_and_catches_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = self._save_fixture_archive(directory)
            clean = store.verify()
            self.assertEqual(clean["schema"], SEQUENCE_REVIEW_VERIFY_SCHEMA)
            self.assertEqual(clean["record_count"], 2)
            self.assertEqual(clean["verified_count"], 2)
            self.assertEqual(clean["failed_count"], 0)

            records = store.analyses.list_reports(limit=5)["rows"]
            saved = store.analyses.get_report(records[0]["analysis_id"])
            address = saved["report_address"]
            object_path = Path(directory) / "objects" / f"{address.split(':', 1)[1]}.json"
            payload = json.loads(object_path.read_text(encoding="utf-8"))
            payload["analysis_state"] = "abstained"
            object_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            verification = store.verify()
            self.assertEqual(verification["record_count"], 2)
            self.assertEqual(verification["verified_count"], 1)
            self.assertEqual(verification["failed_count"], 1)
            failure = next(item for item in verification["results"] if item["status"] == "failed")
            self.assertEqual(failure["kind"], "sequence_analysis")
            self.assertIn(failure["error"]["code"], {"invalid_record", "store_integrity_failure"})

    def test_filters_and_page_bounds_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = self._save_fixture_archive(directory)
            with self.assertRaisesRegex(ValidationError, "change must"):
                store.motif_activity(change="unknown")
            with self.assertRaisesRegex(ValidationError, "limit"):
                store.motif_activity(limit=0)
            with self.assertRaisesRegex(ValidationError, "offset"):
                store.motif_activity(offset=-1)
            self.assertIn("occurrence_count", store.motifs_csv().splitlines()[0])

    def test_cli_summary_verify_and_motif_json_are_replayable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = self._save_fixture_archive(directory)
            self.assertEqual(store.summary()["catalogs"]["sequence_batches"]["record_count"], 1)
            summary_path = Path(directory) / "summary.json"
            self.assertEqual(
                review_main(["--data-root", directory, "summary", "--output", str(summary_path)]),
                0,
            )
            self.assertEqual(
                json.loads(summary_path.read_text(encoding="utf-8"))["schema"],
                SEQUENCE_REVIEW_SUMMARY_SCHEMA,
            )
            verify_path = Path(directory) / "verify.json"
            self.assertEqual(
                review_main(["--data-root", directory, "verify", "--output", str(verify_path)]),
                0,
            )
            self.assertEqual(json.loads(verify_path.read_text(encoding="utf-8"))["failed_count"], 0)
            motifs_path = Path(directory) / "motifs.json"
            self.assertEqual(
                review_main(
                    [
                        "--data-root",
                        directory,
                        "motifs",
                        "--motif-contains",
                        "joint",
                        "--output",
                        str(motifs_path),
                    ]
                ),
                0,
            )
            self.assertEqual(json.loads(motifs_path.read_text(encoding="utf-8"))["total_count"], 1)


if __name__ == "__main__":
    unittest.main()
