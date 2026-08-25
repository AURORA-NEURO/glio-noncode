"""Deep regression coverage for the portable capability certification bundle."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.capability_certification_bundle import (
    build_capability_certification_bundle,
    verify_capability_certification_bundle,
    write_capability_certification_bundle,
)
from glio_noncode.capability_certification_bundle_audit import audit_capability_certification_bundle
from glio_noncode.capability_certification_bundle_observability import (
    certification_bundle_events_csv,
    certification_bundle_metrics_csv,
    certification_bundle_observability_from_dict,
)
from glio_noncode.capability_certification_bundle_query import (
    diff_capability_certification_bundles,
    export_capability_certification_bundle_query_csv,
    load_capability_certification_bundle,
    query_capability_certification_bundle,
)
from glio_noncode.capability_certification_bundle_runtime import (
    run_capability_certification_bundle_runtime,
)
from glio_noncode.capability_certification_bundle_schema import (
    capability_certification_bundle_schema,
    validate_capability_certification_bundle_manifest,
)
from glio_noncode.cli import main
from glio_noncode.module_fabric_support import contains_private_key
from glio_noncode.run_workspace import _has_forbidden_key
from glio_noncode.serialization import canonical_json


class CapabilityCertificationBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = build_capability_certification_bundle()

    def test_bundle_closes_complete_public_inventory(self) -> None:
        self.assertTrue(self.bundle.accepted)
        self.assertEqual(self.bundle.artifact_count, 12)
        self.assertEqual(self.bundle.certificate_count, 256)
        self.assertEqual(self.bundle.domain_count, 16)
        self.assertEqual(self.bundle.total_checks, 2572)
        self.assertEqual(self.bundle.failed_check_count, 0)
        self.assertTrue(all(item.payload is not None for item in self.bundle.artifacts))
        for artifact in self.bundle.artifacts:
            if artifact.media_type == "application/json":
                value = json.loads(artifact.payload or "{}")
                self.assertFalse(_has_forbidden_key(value))
                self.assertFalse(contains_private_key(value))

    def test_manifest_is_stable_and_payload_free(self) -> None:
        self.assertEqual(self.bundle.manifest_dict(), build_capability_certification_bundle().manifest_dict())
        self.assertFalse(any("payload" in item for item in self.bundle.manifest_dict()["artifacts"]))
        self.assertEqual(self.bundle.to_dict(include_payloads=False)["content_address"], self.bundle.content_address)

    def test_schema_and_manifest_validation_close(self) -> None:
        validation = validate_capability_certification_bundle_manifest(self.bundle.to_dict(include_payloads=False))
        self.assertTrue(validation.accepted, validation.to_dict())
        self.assertTrue(capability_certification_bundle_schema()["content_address"].startswith("capability-certification-bundle-schema:"))

    def test_independent_audit_reconciles_all_artifact_planes(self) -> None:
        audit = audit_capability_certification_bundle(self.bundle)
        self.assertTrue(audit.accepted, audit.to_dict())
        self.assertGreaterEqual(audit.passed_check_count, 50)
        self.assertEqual(audit.failed_check_ids, ())

    def test_independent_audit_rejects_semantic_report_drift(self) -> None:
        report = next(item for item in self.bundle.artifacts if item.artifact_id == "report")
        changed_document = json.loads(report.payload or "{}")
        changed_document["capability_count"] = 255
        changed_payload = canonical_json(changed_document) + "\n"
        changed_report = replace(report, payload=changed_payload)
        changed_bundle = replace(
            self.bundle,
            artifacts=tuple(changed_report if item.artifact_id == "report" else item for item in self.bundle.artifacts),
        )
        audit = audit_capability_certification_bundle(changed_bundle)
        self.assertFalse(audit.accepted)
        self.assertTrue(any(item in audit.failed_check_ids for item in ("manifest-address", "artifact-byte-counts", "report-capability-denominator")))

    def test_write_verify_and_tamper_detection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = write_capability_certification_bundle(self.bundle, directory)
            verification = verify_capability_certification_bundle(root)
            self.assertTrue(verification.accepted, verification.to_dict())
            (Path(directory) / "certificates.csv").write_text("tampered\n", encoding="utf-8")
            broken = verify_capability_certification_bundle(directory)
            self.assertFalse(broken.accepted)
            self.assertTrue(any(item.check_id == "bytes:certificates" and not item.passed for item in broken.checks))

    def test_unexpected_files_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            write_capability_certification_bundle(self.bundle, directory)
            (Path(directory) / "unlisted.txt").write_text("unlisted\n", encoding="utf-8")
            verification = verify_capability_certification_bundle(directory)
            self.assertFalse(verification.accepted)
            self.assertTrue(any(item.check_id == "unexpected-files" and not item.passed for item in verification.checks))

    def test_offline_loader_query_and_csv_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            write_capability_certification_bundle(self.bundle, directory)
            loaded = load_capability_certification_bundle(directory, include_payloads=True)
            self.assertEqual(loaded.content_address, self.bundle.content_address)
            certificates = query_capability_certification_bundle(directory, resource="certificates", domain_id="D01", limit=100)
            self.assertEqual(certificates.total, 16)
            mvp = query_capability_certification_bundle(directory, resource="certificates", mvp_only=True, limit=100)
            self.assertEqual(mvp.total, 64)
            domains = query_capability_certification_bundle(directory, resource="domains", limit=100)
            self.assertEqual(domains.total, 16)
            checks = query_capability_certification_bundle(directory, resource="checks", limit=500)
            self.assertEqual(checks.total, 2572)
            artifacts = query_capability_certification_bundle(directory, resource="artifacts", artifact_kind="report")
            self.assertEqual(artifacts.total, 1)
            self.assertEqual(export_capability_certification_bundle_query_csv(certificates), export_capability_certification_bundle_query_csv(certificates))

    def test_diff_reports_address_changes(self) -> None:
        alternate = build_capability_certification_bundle(run_id="capability-certification-bundle-alternate")
        diff = diff_capability_certification_bundles(self.bundle, alternate)
        self.assertTrue(diff.accepted)
        self.assertTrue(diff.changed_artifact_ids)
        self.assertEqual(diff.added_capability_ids, ())
        self.assertEqual(diff.removed_capability_ids, ())

    def test_observability_artifact_rehydrates(self) -> None:
        artifact = next(item for item in self.bundle.artifacts if item.artifact_id == "observability")
        report = certification_bundle_observability_from_dict(json.loads(artifact.payload or "{}"))
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.events), 16)
        self.assertIn("event_id", certification_bundle_events_csv(report))
        self.assertIn("metric_id", certification_bundle_metrics_csv(report))

    def test_staged_runtime_replays(self) -> None:
        runtime = run_capability_certification_bundle_runtime()
        self.assertTrue(runtime.accepted, runtime.to_dict())
        self.assertEqual(runtime.state.value, "ready")
        self.assertEqual(tuple(item.ordinal for item in runtime.stages), tuple(range(1, 7)))
        self.assertEqual(runtime.replay_address, runtime.bundle.content_address)

    def test_cli_and_http_surfaces_share_the_bundle_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "bundle"
            payload_path = Path(directory) / "bundle.json"
            verification_path = Path(directory) / "verification.json"
            self.assertEqual(main(["capability-certification-bundle", "--destination", str(destination), "--output", str(payload_path)]), 0)
            cli_payload = json.loads(payload_path.read_text(encoding="utf-8"))
            self.assertEqual(cli_payload["content_address"], self.bundle.content_address)
            self.assertEqual(main(["capability-certification-bundle-verify", str(destination), "--output", str(verification_path)]), 0)
            self.assertTrue(json.loads(verification_path.read_text(encoding="utf-8"))["accepted"])
            query_path = Path(directory) / "query.json"
            self.assertEqual(main(["capability-certification-bundle-query", str(destination), "--resource", "certificates", "--domain-id", "D01", "--output", str(query_path)]), 0)
            self.assertEqual(json.loads(query_path.read_text(encoding="utf-8"))["total"], 16)
            schema_path = Path(directory) / "schema.json"
            self.assertEqual(main(["capability-certification-bundle-schema", "--output", str(schema_path)]), 0)
            self.assertEqual(json.loads(schema_path.read_text(encoding="utf-8"))["properties"]["version"]["const"], "capability-certification-bundle-v1")
            audit_path = Path(directory) / "audit.json"
            self.assertEqual(main(["capability-certification-bundle-audit", str(destination), "--output", str(audit_path)]), 0)
            self.assertTrue(json.loads(audit_path.read_text(encoding="utf-8"))["accepted"])
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=60)
                connection.request("GET", "/v1/capability-certification/bundle")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())["content_address"], self.bundle.content_address)
                connection.request("GET", "/v1/capability-certification/bundle/query?resource=certificates&domain_id=D01")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())["total"], 16)
                connection.request("GET", "/v1/capability-certification/bundle/observability")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertTrue(json.loads(response.read())["accepted"])
                connection.request("GET", "/v1/capability-certification/bundle/schema")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())["properties"]["version"]["const"], "capability-certification-bundle-v1")
                connection.request("GET", "/v1/capability-certification/bundle/audit")
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
