"""Deep tests for portable batch release bundles and verification."""

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.batch_release import (
    build_persisted_batch_release,
    verify_batch_release_bundle,
    write_batch_release_bundle,
)
from glio_noncode.batch_runtime import BatchRuntime
from glio_noncode.cli import main
from glio_noncode.runtime import CaseRuntime

from .helpers import fixture_manifest


class BatchReleaseTests(unittest.TestCase):
    def _document(self) -> dict[str, object]:
        first = fixture_manifest().to_dict()
        second = dict(first)
        second["case_id"] = "batch-release-case-002"
        second["requested_by"] = "batch-release-user-2"
        return {"batch_id": "batch-release-fixture", "manifests": [first, second]}

    def _runtime_and_batch(self, directory: str, document: dict[str, object] | None = None) -> tuple[CaseRuntime, str]:
        runtime = CaseRuntime(directory)
        result = BatchRuntime(runtime=runtime).evaluate(document or self._document())
        return runtime, result.batch_id

    def test_accepted_bundle_contains_eight_artifacts_and_reopens(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, batch_id = self._runtime_and_batch(directory)
            bundle = build_persisted_batch_release(runtime, batch_id)
            self.assertTrue(bundle.accepted)
            self.assertEqual(bundle.state, "ready")
            self.assertEqual(bundle.artifact_count, 8)
            self.assertEqual(bundle.failed_check_ids, ())
            self.assertTrue(bundle.content_address.startswith("batch-release:"))

            destination = Path(directory) / "batch-release"
            write_batch_release_bundle(bundle, destination)
            self.assertEqual(len(list(destination.iterdir())), 9)
            self.assertTrue((destination / "batch.md").read_text(encoding="utf-8").startswith("# Batch release"))
            public_input = (destination / "batch-input-public.json").read_text(encoding="utf-8")
            self.assertNotIn("subject_id", public_input)
            self.assertNotIn("patient_id", public_input)
            verification = verify_batch_release_bundle(destination)
            self.assertTrue(verification.accepted)
            self.assertTrue(verification.manifest_address_valid)
            self.assertEqual(verification.artifact_count, 8)
            self.assertEqual(verification.verified_artifact_count, 8)
            self.assertEqual(verification.failed_artifact_ids, ())

    def test_partial_batch_is_blocked_but_remains_inspectable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            valid = fixture_manifest().to_dict()
            invalid = dict(valid)
            invalid["case_id"] = "batch-release-invalid"
            invalid["variants"] = []
            runtime, batch_id = self._runtime_and_batch(
                directory,
                {"manifests": [valid, invalid]},
            )
            bundle = build_persisted_batch_release(runtime, batch_id)
            self.assertFalse(bundle.accepted)
            self.assertEqual(bundle.state, "blocked")
            self.assertIn("batch-accepted", bundle.failed_check_ids)
            self.assertEqual(bundle.artifact_count, 8)
            destination = Path(directory) / "partial-release"
            write_batch_release_bundle(bundle, destination)
            verification = verify_batch_release_bundle(destination)
            self.assertFalse(verification.accepted)
            self.assertTrue(verification.manifest_address_valid)
            self.assertEqual(verification.verified_artifact_count, 8)

    def test_tampered_artifact_and_unsafe_path_fail_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, batch_id = self._runtime_and_batch(directory)
            bundle = build_persisted_batch_release(runtime, batch_id)
            destination = Path(directory) / "tampered-release"
            write_batch_release_bundle(bundle, destination)
            csv_path = destination / "batch-items.csv"
            csv_path.write_text(csv_path.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
            tampered = verify_batch_release_bundle(destination)
            self.assertFalse(tampered.accepted)
            self.assertIn("batch-items-csv", tampered.failed_artifact_ids)
            self.assertFalse(tampered.manifest_address_valid)

            manifest_path = destination / "release.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"][0]["filename"] = "../outside.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            unsafe = verify_batch_release_bundle(destination)
            self.assertFalse(unsafe.accepted)
            self.assertTrue(any("unsafe artifact path" in warning for warning in unsafe.warnings))

    def test_cli_build_and_verify_commands_write_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, batch_id = self._runtime_and_batch(directory)
            destination = Path(directory) / "cli-release"
            verification_path = Path(directory) / "verification.json"
            self.assertEqual(
                main(
                    [
                        "batch-release",
                        batch_id,
                        "--data-root",
                        directory,
                        "--output",
                        str(destination),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "batch-release-verify",
                        str(destination),
                        "--output",
                        str(verification_path),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(verification_path.read_text(encoding="utf-8"))["accepted"])

    def test_http_batch_release_route_returns_gated_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
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
                    body=json.dumps(self._document()).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                evaluated = connection.getresponse()
                self.assertEqual(evaluated.status, 200)
                batch_id = json.loads(evaluated.read())["batch_id"]
                connection.request("GET", f"/v1/batches/{batch_id}/release")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                payload = json.loads(response.read())
                self.assertTrue(payload["accepted"])
                self.assertEqual(payload["artifact_count"], 8)
            finally:
                if connection is not None:
                    connection.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
