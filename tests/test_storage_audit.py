"""Deep tests for store-wide object and index integrity auditing."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.batch_runtime import BatchRuntime
from glio_noncode.cli import main
from glio_noncode.runtime import CaseRuntime
from glio_noncode.storage_audit import build_storage_audit

from .helpers import fixture_manifest


class StorageAuditTests(unittest.TestCase):
    def _runtime(self, directory: str) -> tuple[CaseRuntime, object]:
        runtime = CaseRuntime(directory)
        return runtime, runtime.evaluate(fixture_manifest())

    def test_audit_accepts_reachable_run_and_batch_objects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _ = self._runtime(directory)
            batch = BatchRuntime(runtime=runtime).evaluate(
                [
                    fixture_manifest().to_dict(),
                    replace(
                        fixture_manifest(),
                        case_id="storage-audit-batch-case",
                        requested_by="storage-audit-requester",
                    ).to_dict(),
                ]
            )
            report = build_storage_audit(runtime)
            self.assertTrue(report.accepted)
            self.assertGreaterEqual(report.object_count, 7)
            self.assertEqual(report.object_count, report.valid_object_count)
            self.assertEqual(report.run_count, 2)
            self.assertEqual(report.batch_count, 1)
            self.assertEqual(report.orphan_object_count, 0)
            self.assertEqual(report.missing_reference_count, 0)
            self.assertEqual(report.unexpected_entries, ())
            self.assertEqual(report.orphan_addresses, ())
            self.assertEqual(report.missing_addresses, ())
            self.assertTrue(all(item.referenced for item in report.objects))
            self.assertTrue(all(item.event_history_count >= 1 for item in report.runs))
            for item in batch.items:
                self.assertIsNotNone(item.input_address)
                item_payload = runtime.store.store.get(str(item.input_address))
                self.assertEqual(item_payload["batch_id"], batch.batch_id)
                self.assertEqual(item_payload["index"], item.index)

    def test_audit_is_deterministic_and_only_emits_public_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _ = self._runtime(directory)
            first = build_storage_audit(runtime)
            second = build_storage_audit(runtime)
            self.assertEqual(first.to_dict(), second.to_dict())
            self.assertTrue(first.content_address.startswith("storage-audit:"))
            serialized = json.dumps(first.to_dict(), sort_keys=True).lower()
            for forbidden in (
                "subject_id",
                "sample_id",
                "agent_id",
                "agent_name",
                "assistant_id",
                "generated_by",
                "model_name",
                "author_name",
                "programming_language",
            ):
                self.assertNotIn(forbidden, serialized)

    def test_tampered_object_bytes_fail_canonical_and_hash_checks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier = self._runtime(directory)
            run_record = runtime.get_run(dossier.run_id)
            event_digest = str(run_record["event_address"]).split(":", 1)[1]
            event_path = runtime.store.store.objects / f"{event_digest}.json"
            event = json.loads(event_path.read_text(encoding="utf-8"))
            event["events"][0]["event_type"] = "tampered"
            event_path.write_text(json.dumps(event), encoding="utf-8")

            report = build_storage_audit(runtime)
            self.assertFalse(report.accepted)
            audited = next(item for item in report.objects if item.address == run_record["event_address"])
            self.assertFalse(audited.hash_valid)
            self.assertFalse(audited.canonical_bytes_valid)
            self.assertTrue(any("content" in warning for warning in audited.warnings))

    def test_missing_and_orphan_references_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier = self._runtime(directory)
            run_record = runtime.get_run(dossier.run_id)
            dossier_digest = str(run_record["dossier_address"]).split(":", 1)[1]
            (runtime.store.store.objects / f"{dossier_digest}.json").unlink()
            missing = build_storage_audit(runtime)
            self.assertFalse(missing.accepted)
            self.assertIn(run_record["dossier_address"], missing.missing_addresses)
            self.assertGreaterEqual(missing.missing_reference_count, 1)

            runtime, _ = self._runtime(directory)
            orphan_address = runtime.store.store.put({"orphan": True})
            orphan = build_storage_audit(runtime)
            self.assertFalse(orphan.accepted)
            self.assertIn(orphan_address, orphan.orphan_addresses)
            self.assertEqual(orphan.orphan_object_count, 1)

    def test_unexpected_files_and_malformed_indexes_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _ = self._runtime(directory)
            (Path(directory) / "objects" / "leftover.tmp").write_text("leftover", encoding="utf-8")
            (Path(directory) / "runs" / "not-a-run.txt").write_text("leftover", encoding="utf-8")
            report = build_storage_audit(runtime)
            self.assertFalse(report.accepted)
            self.assertIn("objects/leftover.tmp", report.unexpected_entries)
            self.assertIn("runs/not-a-run.txt", report.unexpected_entries)

    def test_cli_and_http_surfaces_return_the_same_audit_address(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _ = self._runtime(directory)
            output_path = Path(directory) / "storage-audit.json"
            self.assertEqual(
                main(
                    [
                        "storage-audit",
                        "--data-root",
                        directory,
                        "--output",
                        str(output_path),
                    ]
                ),
                0,
            )
            cli_payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertTrue(cli_payload["accepted"])
            self.assertEqual(cli_payload["object_count"], 3)

            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                connection.request("GET", "/v1/storage/audit")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                api_payload = json.loads(response.read())
                self.assertTrue(api_payload["accepted"])
                self.assertEqual(api_payload["content_address"], cli_payload["content_address"])
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
