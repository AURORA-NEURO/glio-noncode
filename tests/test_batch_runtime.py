"""Deep tests for content-addressed batch evaluation and reopening."""

from __future__ import annotations

import json
import multiprocessing
import tempfile
import unittest
from dataclasses import replace
from http.client import HTTPConnection
from pathlib import Path
from queue import Empty
from threading import Thread
from typing import Any

from glio_noncode.api import create_server
from glio_noncode.batch_runtime import (
    BATCH_CATALOG_MAX_LIMIT,
    BATCH_HARD_MAX_ITEMS,
    BATCH_RUNTIME_VERSION,
    BatchResult,
    BatchRuntime,
)
from glio_noncode.cli import main
from glio_noncode.errors import StoreError, ValidationError
from glio_noncode.runtime import CaseRuntime
from glio_noncode.serialization import canonical_json, content_hash
from glio_noncode.storage import _filesystem_lock

from .helpers import fixture_manifest


def _process_batch_evaluate(
    root: str,
    document: dict[str, object],
    index: int,
    start: Any,
    ready: Any,
    results: Any,
) -> None:
    try:
        ready.put(index)
        if not start.wait(timeout=20):
            raise TimeoutError("batch race start was not released")
        result = BatchRuntime(root).evaluate(document)
        results.put(
            (
                "ok",
                index,
                result.batch_id,
                result.result_address,
                result.created_at,
            )
        )
    except BaseException as exc:  # pragma: no cover - parent asserts serialized failure
        results.put(("error", index, type(exc).__name__, str(exc)))


class BatchRuntimeTests(unittest.TestCase):
    def _document(self) -> dict[str, object]:
        first = fixture_manifest().to_dict()
        second = replace(
            fixture_manifest(), case_id="batch-case-002", requested_by="batch-user-2"
        ).to_dict()
        return {"batch_id": "batch-fixture", "manifests": [first, second]}

    def _process_results(self, processes: tuple[Any, ...], results: Any) -> list[Any]:
        for process in processes:
            process.join(timeout=60)
        try:
            self.assertFalse(
                [process.pid for process in processes if process.is_alive()],
                "batch evaluator process did not terminate",
            )
            self.assertTrue(all(process.exitcode == 0 for process in processes))
            output = []
            for _ in processes:
                try:
                    output.append(results.get(timeout=5))
                except Empty as exc:  # pragma: no cover - assertion exposes process state
                    self.fail(f"batch evaluator did not report a result: {exc}")
            return output
        finally:
            for process in processes:
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)

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

    def test_cross_process_identical_batch_has_one_reopenable_winner(self) -> None:
        writer_count = 4
        context = multiprocessing.get_context("spawn")
        with tempfile.TemporaryDirectory() as directory:
            runtime = BatchRuntime(directory)
            document = self._document()
            raw_document = {
                "batch_id": "batch-fixture",
                "manifests": document["manifests"],
                "live_reference": False,
                "window_bp": 2_000,
                "max_items": 100,
            }
            input_address = content_hash(raw_document)
            batch_id = f"batch-{input_address.split(':', 1)[1]}"
            start = context.Event()
            ready = context.Queue()
            results = context.Queue()
            processes = tuple(
                context.Process(
                    target=_process_batch_evaluate,
                    args=(directory, document, index, start, ready, results),
                )
                for index in range(writer_count)
            )
            with _filesystem_lock(runtime._lock_path(batch_id)):
                for process in processes:
                    process.start()
                ready_indexes = {ready.get(timeout=20) for _ in processes}
                self.assertEqual(ready_indexes, set(range(writer_count)))
                start.set()

            output = self._process_results(processes, results)
            self.assertTrue(all(item[0] == "ok" for item in output), output)
            addresses = {item[3] for item in output}
            created_values = {item[4] for item in output}
            self.assertEqual(len(addresses), 1)
            self.assertEqual(len(created_values), 1)
            reopened = runtime.get(batch_id)
            self.assertEqual(reopened.result_address, next(iter(addresses)))
            self.assertEqual(reopened.created_at, next(iter(created_values)))
            batch_payloads = []
            for path in runtime.runtime.store.store.objects.glob("*.json"):
                payload = json.loads(path.read_text(encoding="utf-8"))
                if (
                    isinstance(payload, dict)
                    and payload.get("batch_version") == BATCH_RUNTIME_VERSION
                    and payload.get("batch_id") == batch_id
                ):
                    batch_payloads.append(payload)
            self.assertEqual(len(batch_payloads), 1)
            self.assertFalse(tuple(runtime.root.glob("*.tmp")))

    def test_strict_hydration_rejects_malformed_index_and_result_payloads(self) -> None:
        def move_first_item(payload: dict[str, Any]) -> None:
            item = payload["items"][0]
            item["index"] = 9
            body = {
                field: item[field]
                for field in (
                    "index",
                    "case_id",
                    "state",
                    "input_address",
                    "run_id",
                    "dossier_address",
                    "error_code",
                    "error_message",
                )
            }
            item["content_address"] = content_hash(body, prefix="batch-item")

        mutations = {
            "version": lambda payload: payload.__setitem__("batch_version", "wrong"),
            "counts": lambda payload: payload.__setitem__("completed_count", -1),
            "unknown-result-field": lambda payload: payload.__setitem__("unexpected", True),
            "unknown-option-field": lambda payload: payload["options"].__setitem__(
                "unexpected", True
            ),
            "unknown-item-field": lambda payload: payload["items"][0].__setitem__(
                "unexpected", True
            ),
            "item-index": move_first_item,
            "item-address": lambda payload: payload["items"][0].__setitem__(
                "content_address", "batch-item:" + "0" * 64
            ),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                runtime = BatchRuntime(directory)
                result = runtime.evaluate(self._document())
                payload = runtime.runtime.store.store.get(result.result_address)
                mutate(payload)
                malformed_address = runtime.runtime.store.store.put(payload)
                index_path = runtime._index_path(result.batch_id)
                index = json.loads(index_path.read_text(encoding="utf-8"))
                index["result_address"] = malformed_address
                index_path.write_text(canonical_json(index), encoding="utf-8")
                with self.assertRaisesRegex(StoreError, "invalid batch result"):
                    runtime.get(result.batch_id)
                with self.assertRaises(ValidationError):
                    BatchResult.from_payload(payload, result_address=malformed_address)

        with tempfile.TemporaryDirectory() as directory:
            runtime = BatchRuntime(directory)
            document = self._document()
            result = runtime.evaluate(document)
            index_path = runtime._index_path(result.batch_id)
            index = json.loads(index_path.read_text(encoding="utf-8"))
            index["input_address"] = runtime.runtime.store.store.put({"foreign": True})
            index_path.write_text(canonical_json(index), encoding="utf-8")
            with self.assertRaisesRegex(StoreError, "invalid batch index"):
                runtime.get(result.batch_id)
            index["input_address"] = result.input_address
            index["accepted"] = not result.accepted
            index_path.write_text(canonical_json(index), encoding="utf-8")
            with self.assertRaisesRegex(StoreError, "accepted state"):
                runtime.get(result.batch_id)
            index["accepted"] = result.accepted
            index["unexpected"] = True
            index_path.write_text(canonical_json(index), encoding="utf-8")
            with self.assertRaisesRegex(StoreError, "invalid batch index"):
                runtime.get(result.batch_id)
            index_path.write_bytes(b"\xff")
            with self.assertRaisesRegex(StoreError, "invalid batch index"):
                runtime.get(result.batch_id)
            with self.assertRaisesRegex(StoreError, "invalid batch index"):
                runtime.evaluate(document)

    def test_reopen_closes_item_inputs_and_historical_run_dossiers(self) -> None:
        def publish_mutation(
            runtime: BatchRuntime,
            result: Any,
            mutate: Any,
        ) -> None:
            payload = runtime.runtime.store.store.get(result.result_address)
            mutate(payload)
            item = payload["items"][0]
            body = {
                field: item[field]
                for field in (
                    "index",
                    "case_id",
                    "state",
                    "input_address",
                    "run_id",
                    "dossier_address",
                    "error_code",
                    "error_message",
                )
            }
            item["content_address"] = content_hash(body, prefix="batch-item")
            result_address = runtime.runtime.store.store.put(payload)
            index_path = runtime._index_path(result.batch_id)
            index = json.loads(index_path.read_text(encoding="utf-8"))
            index["result_address"] = result_address
            index_path.write_text(canonical_json(index), encoding="utf-8")

        with tempfile.TemporaryDirectory() as directory:
            runtime = BatchRuntime(directory)
            result = runtime.evaluate(self._document())
            publish_mutation(
                runtime,
                result,
                lambda payload: payload["items"][0].__setitem__(
                    "input_address", payload["items"][1]["input_address"]
                ),
            )
            with self.assertRaisesRegex(StoreError, "item input pointer"):
                runtime.get(result.batch_id)

        with tempfile.TemporaryDirectory() as directory:
            runtime = BatchRuntime(directory)
            result = runtime.evaluate(self._document())
            publish_mutation(
                runtime,
                result,
                lambda payload: payload["items"][0].__setitem__(
                    "dossier_address", payload["items"][1]["dossier_address"]
                ),
            )
            with self.assertRaisesRegex(StoreError, "run closure"):
                runtime.get(result.batch_id)

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
            self.assertEqual(runtime.get(result.batch_id).to_dict(), result.to_dict())

    def test_catalog_and_result_verification_fail_closed_on_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = BatchRuntime(directory)
            result = runtime.evaluate(self._document())
            result_digest = result.result_address.split(":", 1)[1]
            result_path = runtime.runtime.store.store.objects / f"{result_digest}.json"
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
                runtime.evaluate(
                    {
                        "manifests": [fixture_manifest().to_dict()],
                        "max_items": BATCH_HARD_MAX_ITEMS + 1,
                    }
                )
            with self.assertRaises(ValidationError):
                runtime.catalog(limit=BATCH_CATALOG_MAX_LIMIT + 1)
            with self.assertRaises(ValidationError):
                runtime.catalog(offset=-1)
            invalid_documents = (
                {"manifests": [fixture_manifest().to_dict()], "live_reference": "false"},
                {"manifests": [fixture_manifest().to_dict()], "window_bp": "2000"},
                {"manifests": [fixture_manifest().to_dict()], "max_items": True},
                {"batch_id": 7, "manifests": [fixture_manifest().to_dict()]},
                {
                    "batch_id": "one",
                    "label": "two",
                    "manifests": [fixture_manifest().to_dict()],
                },
            )
            for document in invalid_documents:
                with self.subTest(document=document), self.assertRaises(ValidationError):
                    runtime.evaluate(document)  # type: ignore[arg-type]
            with self.assertRaises(ValidationError):
                runtime.evaluate([fixture_manifest().to_dict()], live_reference=1)  # type: ignore[arg-type]
            with self.assertRaises(ValidationError):
                runtime.evaluate([fixture_manifest().to_dict()], window_bp=True)
            with self.assertRaises(ValidationError):
                runtime.evaluate([fixture_manifest().to_dict()], max_items="100")  # type: ignore[arg-type]

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
            inspected = json.loads(inspect_path.read_text(encoding="utf-8"))
            self.assertEqual(inspected["batch_id"], result["batch_id"])
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
