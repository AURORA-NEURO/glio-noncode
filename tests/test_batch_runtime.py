"""Deep tests for content-addressed batch evaluation and reopening."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.batch_runtime import (
    BATCH_CATALOG_MAX_LIMIT,
    BATCH_HARD_MAX_ITEMS,
    BatchRuntime,
)
from glio_noncode.cli import main
from glio_noncode.errors import StoreError, ValidationError
from glio_noncode.runtime import CaseRuntime

from .helpers import fixture_manifest


class BatchRuntimeTests(unittest.TestCase):
    def _document(self) -> dict[str, object]:
        first = fixture_manifest().to_dict()
        second = replace(fixture_manifest(), case_id="batch-case-002", requested_by="batch-user-2").to_dict()
        return {"batch_id": "batch-fixture", "manifests": [first, second]}

    def test_batch_evaluates_items_and_reopens_durably(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = BatchRuntime(directory)
            result = runtime.evaluate(self._document())
            self.assertTrue(result.accepted)
            self.assertFalse(result.partial)
            self.assertEqual(result.requested_count, 2)
            self.assertEqual(result.completed_count, 2)
            self.assertEqual(result.accepted_count, 2)
            self.assertEqual(result.failed_count, 0)
            self.assertTrue(result.batch_id.startswith("batch-"))
            self.assertTrue(result.input_address.startswith("sha256:"))
            self.assertTrue(result.result_address.startswith("sha256:"))
            self.assertEqual([item.state for item in result.items], ["accepted", "accepted"])
            self.assertTrue(all(item.run_id and item.dossier_address for item in result.items))
            self.assertTrue(runtime.runtime.store.store.exists(result.input_address))
            self.assertTrue(runtime.runtime.store.store.exists(result.result_address))
            reopened = runtime.get(result.batch_id)
            self.assertEqual(reopened.to_dict(), result.to_dict())
            catalog = runtime.catalog()
            self.assertTrue(catalog.accepted)
            self.assertEqual(catalog.total_count, 1)
            self.assertEqual(catalog.rows[0].batch_id, result.batch_id)
            self.assertEqual(catalog.rows[0].accepted_count, 2)

    def test_single_case_manifest_is_a_valid_one_item_batch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = BatchRuntime(directory).evaluate(fixture_manifest().to_dict())
            self.assertTrue(result.accepted)
            self.assertEqual(result.requested_count, 1)
            self.assertEqual(result.items[0].case_id, fixture_manifest().case_id)

    def test_batch_is_idempotent_and_duplicate_case_ids_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = BatchRuntime(directory)
            document = self._document()
            first = runtime.evaluate(document)
            second = runtime.evaluate(document)
            self.assertEqual(first.batch_id, second.batch_id)
            self.assertEqual(first.result_address, second.result_address)
            self.assertEqual(first.created_at, second.created_at)

            duplicate = {
                "manifests": [
                    fixture_manifest().to_dict(),
                    fixture_manifest().to_dict(),
                ]
            }
            duplicate_result = runtime.evaluate(duplicate)
            self.assertFalse(duplicate_result.accepted)
            self.assertEqual(duplicate_result.accepted_count, 1)
            self.assertEqual(duplicate_result.failed_count, 1)
            self.assertEqual(duplicate_result.items[1].error_code, "validation_error")
            self.assertIn("duplicate case_id", duplicate_result.items[1].error_message or "")

    def test_partial_manifest_failure_preserves_successful_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = BatchRuntime(directory)
            valid = fixture_manifest().to_dict()
            invalid = dict(valid)
            invalid["case_id"] = "batch-invalid"
            invalid["variants"] = []
            result = runtime.evaluate({"manifests": [valid, invalid]})
            self.assertFalse(result.accepted)
            self.assertTrue(result.partial)
            self.assertEqual(result.accepted_count, 1)
            self.assertEqual(result.failed_count, 1)
            self.assertEqual(result.items[0].state, "accepted")
            self.assertEqual(result.items[1].state, "failed")
            self.assertEqual(result.items[1].case_id, "batch-invalid")
            self.assertEqual(result.items[1].error_code, "validation_error")
            self.assertTrue(result.items[0].run_id)
            self.assertTrue(CaseRuntime(directory).get_run(result.items[0].run_id or ""))

    def test_catalog_and_result_verification_fail_closed_on_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = BatchRuntime(directory)
            result = runtime.evaluate(self._document())
            result_path = runtime.runtime.store.store.objects / f"{result.result_address.split(':', 1)[1]}.json"
            result_path.write_text(json.dumps({"tampered": True}), encoding="utf-8")
            with self.assertRaises(StoreError):
                runtime.get(result.batch_id)
            catalog = runtime.catalog()
            self.assertFalse(catalog.accepted)
            self.assertEqual(catalog.total_count, 1)
            self.assertFalse(catalog.rows[0].accepted)
            self.assertEqual(catalog.rows[0].error, "batch could not be reopened or verified")

    def test_bounds_and_input_shapes_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = BatchRuntime(directory)
            with self.assertRaises(ValidationError):
                runtime.evaluate({"manifests": []})
            with self.assertRaises(ValidationError):
                runtime.evaluate({"manifests": [fixture_manifest().to_dict()], "max_items": 0})
            with self.assertRaises(ValidationError):
                runtime.evaluate({"manifests": [fixture_manifest().to_dict()], "max_items": BATCH_HARD_MAX_ITEMS + 1})
            with self.assertRaises(ValidationError):
                runtime.catalog(limit=BATCH_CATALOG_MAX_LIMIT + 1)
            with self.assertRaises(ValidationError):
                runtime.catalog(offset=-1)

    def test_cli_and_http_batch_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            document_path = Path(directory) / "batch.json"
            result_path = Path(directory) / "batch-result.json"
            inspect_path = Path(directory) / "batch-inspect.json"
            catalog_path = Path(directory) / "batch-catalog.json"
            document_path.write_text(json.dumps(self._document()), encoding="utf-8")
            self.assertEqual(
                main(
                    [
                        "evaluate-batch",
                        str(document_path),
                        "--data-root",
                        directory,
                        "--output",
                        str(result_path),
                    ]
                ),
                0,
            )
            result = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertTrue(result["accepted"])
            self.assertEqual(
                main(
                    [
                        "batch-inspect",
                        result["batch_id"],
                        "--data-root",
                        directory,
                        "--output",
                        str(inspect_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "batch-catalog",
                        "--data-root",
                        directory,
                        "--output",
                        str(catalog_path),
                    ]
                ),
                0,
            )
            self.assertEqual(json.loads(inspect_path.read_text(encoding="utf-8"))["batch_id"], result["batch_id"])
            self.assertTrue(json.loads(catalog_path.read_text(encoding="utf-8"))["accepted"])

            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = None
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                connection.request(
                    "POST",
                    "/v1/evaluate-batch",
                    body=document_path.read_bytes(),
                    headers={"Content-Type": "application/json"},
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                http_result = json.loads(response.read())
                self.assertTrue(http_result["accepted"])
                self.assertEqual(http_result["batch_id"], result["batch_id"])
                connection.request("GET", "/v1/batches?limit=10")
                catalog_response = connection.getresponse()
                self.assertEqual(catalog_response.status, 200)
                self.assertEqual(json.loads(catalog_response.read())["total_count"], 1)
                connection.request("GET", f"/v1/batches/{result['batch_id']}")
                inspect_response = connection.getresponse()
                self.assertEqual(inspect_response.status, 200)
                self.assertTrue(json.loads(inspect_response.read())["accepted"])
            finally:
                if connection is not None:
                    connection.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
