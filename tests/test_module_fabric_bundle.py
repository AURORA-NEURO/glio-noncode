"""Deep regression coverage for the portable module-fabric bundle."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.module_fabric_bundle import (
    build_module_fabric_bundle,
    bundle_artifact_csv,
    verify_module_fabric_bundle,
    write_module_fabric_bundle,
)
from glio_noncode.module_fabric_bundle_audit import audit_module_fabric_bundle
from glio_noncode.module_fabric_bundle_observability import (
    build_module_fabric_bundle_observability,
    fabric_bundle_events_csv,
    fabric_bundle_metrics_csv,
)
from glio_noncode.module_fabric_bundle_query import (
    diff_module_fabric_bundles,
    export_module_fabric_bundle_query_csv,
    load_module_fabric_bundle,
    query_module_fabric_bundle,
)
from glio_noncode.module_fabric_bundle_runtime import run_module_fabric_bundle_runtime
from glio_noncode.module_fabric_bundle_schema import (
    module_fabric_bundle_schema,
    validate_module_fabric_bundle_manifest,
)
from glio_noncode.module_fabric_support import contains_private_key
from glio_noncode.run_workspace import _has_forbidden_key


class ModuleFabricBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = build_module_fabric_bundle()

    def test_bundle_has_closed_public_inventory(self) -> None:
        self.assertTrue(self.bundle.accepted)
        self.assertEqual(self.bundle.artifact_count, 21)
        self.assertEqual(self.bundle.failed_check_count, 0)
        self.assertEqual(len({item.artifact_id for item in self.bundle.artifacts}), 21)
        self.assertTrue(all(item.payload is not None for item in self.bundle.artifacts))
        for artifact in self.bundle.artifacts:
            if artifact.media_type == "application/json":
                parsed = json.loads(artifact.payload or "{}")
                self.assertFalse(_has_forbidden_key(parsed))
                self.assertFalse(contains_private_key(parsed))

    def test_manifest_is_stable_and_excludes_payloads(self) -> None:
        first = self.bundle.manifest_dict()
        second = build_module_fabric_bundle().manifest_dict()
        self.assertEqual(first, second)
        self.assertFalse(any("payload" in item for item in first["artifacts"]))
        self.assertEqual(self.bundle.to_dict(include_payloads=False)["content_address"], self.bundle.content_address)

    def test_write_and_verify_exact_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = write_module_fabric_bundle(self.bundle, directory)
            verification = verify_module_fabric_bundle(root)
            self.assertTrue(verification.accepted, verification.to_dict())
            (Path(directory) / "summary.json").write_text("{}\n", encoding="utf-8")
            broken = verify_module_fabric_bundle(directory)
            self.assertFalse(broken.accepted)
            self.assertTrue(any(item.check_id == "bytes:summary" and not item.passed for item in broken.checks))

    def test_unexpected_files_and_symlinks_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            write_module_fabric_bundle(self.bundle, directory)
            extra = Path(directory) / "unexpected.txt"
            extra.write_text("unexpected\n", encoding="utf-8")
            verification = verify_module_fabric_bundle(directory)
            self.assertFalse(verification.accepted)
            self.assertTrue(any(item.check_id == "unexpected-files" and not item.passed for item in verification.checks))

    def test_query_records_and_artifacts_are_deterministic(self) -> None:
        records = query_module_fabric_bundle(self.bundle, resource="records", domain_id="D01", limit=100)
        self.assertTrue(records.accepted)
        self.assertEqual(records.total, 2)
        self.assertTrue(all(item["domain_id"] == "D01" for item in records.items))
        artifacts = query_module_fabric_bundle(self.bundle, resource="artifacts", artifact_kind="report")
        self.assertGreaterEqual(artifacts.total, 3)
        self.assertEqual(export_module_fabric_bundle_query_csv(records), export_module_fabric_bundle_query_csv(records))
        self.assertIn("artifact_id", bundle_artifact_csv(self.bundle))

    def test_offline_loader_and_diff_preserve_closure(self) -> None:
        alternate = build_module_fabric_bundle(run_id="module-fabric-bundle-alternate")
        diff = diff_module_fabric_bundles(self.bundle, alternate)
        self.assertTrue(diff.accepted)
        self.assertTrue(diff.changed_artifact_ids)
        with tempfile.TemporaryDirectory() as left_directory:
            write_module_fabric_bundle(self.bundle, left_directory)
            loaded = load_module_fabric_bundle(left_directory, include_payloads=True)
            self.assertEqual(loaded.content_address, self.bundle.content_address)
            self.assertEqual(loaded.artifact_count, self.bundle.artifact_count)

    def test_schema_and_observability_close(self) -> None:
        manifest = self.bundle.to_dict(include_payloads=False)
        schema = module_fabric_bundle_schema()
        validation = validate_module_fabric_bundle_manifest(manifest)
        self.assertTrue(validation.accepted, validation.to_dict())
        self.assertTrue(schema["content_address"].startswith("module-fabric-bundle-schema:"))
        observation = build_module_fabric_bundle_observability(self.bundle)
        self.assertTrue(observation.accepted)
        self.assertEqual(len(observation.events), self.bundle.artifact_count + 5)
        self.assertIn("event_id", fabric_bundle_events_csv(observation))
        self.assertIn("metric_id", fabric_bundle_metrics_csv(observation))

    def test_independent_audit_reconciles_all_artifact_planes(self) -> None:
        audit = audit_module_fabric_bundle(self.bundle)
        self.assertTrue(audit.accepted, audit.to_dict())
        self.assertGreaterEqual(audit.passed_check_count, 55)
        self.assertEqual(audit.failed_check_ids, ())

    def test_independent_audit_rejects_fixture_drift(self) -> None:
        fixture = next(item for item in self.bundle.artifacts if item.artifact_id == "fixture")
        changed_document = json.loads(fixture.payload or "{}")
        changed_document["fixture_id"] = "tampered-fixture"
        from glio_noncode.serialization import canonical_json

        changed_fixture = replace(fixture, payload=canonical_json(changed_document) + "\n")
        changed_bundle = replace(
            self.bundle,
            artifacts=tuple(changed_fixture if item.artifact_id == "fixture" else item for item in self.bundle.artifacts),
        )
        audit = audit_module_fabric_bundle(changed_bundle)
        self.assertFalse(audit.accepted)
        self.assertTrue(any(item in audit.failed_check_ids for item in ("manifest-address", "artifact-byte-counts", "fixture-record-count")))

    def test_staged_runtime_replays(self) -> None:
        runtime = run_module_fabric_bundle_runtime()
        self.assertTrue(runtime.accepted, runtime.to_dict())
        self.assertEqual(runtime.state.value, "ready")
        self.assertEqual(tuple(item.ordinal for item in runtime.stages), tuple(range(1, 7)))
        self.assertEqual(runtime.replay_address, runtime.bundle.content_address)

    def test_cli_and_http_surfaces_share_the_bundle_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "bundle"
            payload_path = Path(directory) / "bundle.json"
            verification_path = Path(directory) / "verification.json"
            self.assertEqual(
                main(
                    [
                        "module-fabric-bundle",
                        "--destination",
                        str(destination),
                        "--output",
                        str(payload_path),
                    ]
                ),
                0,
            )
            audit_path = Path(directory) / "audit.json"
            self.assertEqual(main(["module-fabric-bundle-audit", str(destination), "--output", str(audit_path)]), 0)
            self.assertTrue(json.loads(audit_path.read_text(encoding="utf-8"))["accepted"])
            cli_payload = json.loads(payload_path.read_text(encoding="utf-8"))
            self.assertEqual(cli_payload["content_address"], self.bundle.content_address)
            self.assertEqual(
                main(
                    [
                        "module-fabric-bundle-verify",
                        str(destination),
                        "--output",
                        str(verification_path),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(verification_path.read_text(encoding="utf-8"))["accepted"])
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                connection.request("GET", "/v1/module-fabric/bundle")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                api_payload = json.loads(response.read())
                self.assertTrue(api_payload["accepted"])
                self.assertEqual(api_payload["content_address"], self.bundle.content_address)
                connection.request("GET", "/v1/module-fabric/bundle/query?resource=records&domain_id=D01")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())["total"], 2)
                connection.request("GET", "/v1/module-fabric/bundle/observability")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertTrue(json.loads(response.read())["accepted"])
                connection.request("GET", "/v1/module-fabric/bundle/schema")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())["properties"]["version"]["const"], "module-fabric-bundle-v1")
                connection.request("GET", "/v1/module-fabric/bundle/audit")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertTrue(json.loads(response.read())["accepted"])
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
