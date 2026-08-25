"""Contract tests for the portable D13 validation-design bundle."""

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.validation_design_frontier_bundle_audit import (
    audit_validation_design_offline_bundle,
)
from glio_noncode.validation_design_frontier_bundle_contracts import (
    VALIDATION_DESIGN_BUNDLE_VERSION,
)
from glio_noncode.validation_design_frontier_bundle_query import (
    diff_validation_design_offline_bundles,
    export_validation_design_bundle_query_csv,
    load_validation_design_offline_bundle,
    query_validation_design_offline_bundle,
)
from glio_noncode.validation_design_frontier_bundle_runtime import (
    build_validation_design_bundle_observability,
    run_validation_design_bundle_runtime,
)
from glio_noncode.validation_design_frontier_bundle_schema import (
    validate_validation_design_bundle_manifest,
    validation_design_bundle_schema,
)
from glio_noncode.validation_design_frontier_offline_bundle import (
    VALIDATION_DESIGN_BUNDLE_ARTIFACT_COUNT,
    build_validation_design_offline_bundle,
    verify_validation_design_offline_bundle,
    write_validation_design_offline_bundle,
)


class ValidationDesignFrontierBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = build_validation_design_offline_bundle()

    def test_bundle_closes_artifacts_and_denominators(self) -> None:
        self.assertTrue(self.bundle.accepted)
        self.assertEqual(self.bundle.version, VALIDATION_DESIGN_BUNDLE_VERSION)
        self.assertEqual(self.bundle.artifact_count, VALIDATION_DESIGN_BUNDLE_ARTIFACT_COUNT)
        self.assertEqual(self.bundle.failed_check_count, 0)
        self.assertTrue(self.bundle.content_address.startswith("validation-design-bundle:"))
        self.assertTrue(all(item.payload for item in self.bundle.artifacts))

    def test_bundle_is_deterministic_despite_runtime_wall_clock(self) -> None:
        repeated = build_validation_design_offline_bundle()
        self.assertEqual(self.bundle.content_address, repeated.content_address)
        self.assertEqual(self.bundle.runtime_address, repeated.runtime_address)
        self.assertEqual(
            [item.content_address for item in self.bundle.artifacts],
            [item.content_address for item in repeated.artifacts],
        )

    def test_filesystem_verification_and_independent_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "bundle"
            write_validation_design_offline_bundle(self.bundle, destination)
            verification = verify_validation_design_offline_bundle(destination)
            self.assertTrue(verification.accepted)
            loaded = load_validation_design_offline_bundle(destination, include_payloads=True)
            audit = audit_validation_design_offline_bundle(loaded)
            self.assertTrue(audit.accepted)
            self.assertEqual(audit.failed_check_ids, ())
            diff = diff_validation_design_offline_bundles(destination, destination)
            self.assertTrue(diff.accepted)
            self.assertEqual(len(diff.unchanged_artifact_ids), VALIDATION_DESIGN_BUNDLE_ARTIFACT_COUNT)

    def test_tampering_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "bundle"
            write_validation_design_offline_bundle(self.bundle, destination)
            (destination / "review.csv").write_text(
                (destination / "review.csv").read_text(encoding="utf-8") + "tampered\n",
                encoding="utf-8",
            )
            verification = verify_validation_design_offline_bundle(destination)
            self.assertFalse(verification.accepted)
            self.assertTrue(any(item.check_id == "bytes:review-csv" and not item.passed for item in verification.checks))

    def test_queries_cover_records_checks_sources_and_artifacts(self) -> None:
        records = query_validation_design_offline_bundle(self.bundle, resource="records", operation="gap_analysis")
        self.assertTrue(records.accepted)
        self.assertEqual(records.total, 4)
        self.assertTrue(all(item["operation"] == "gap_analysis" for item in records.items))

        checks = query_validation_design_offline_bundle(self.bundle, resource="checks", state="passed", limit=100)
        self.assertTrue(checks.accepted)
        self.assertEqual(checks.total, 80)
        self.assertTrue(all(item["passed"] for item in checks.items))

        sources = query_validation_design_offline_bundle(self.bundle, resource="sources")
        self.assertEqual(sources.total, 5)
        self.assertTrue(all(str(item["uri"]).startswith("https://") for item in sources.items))

        artifacts = query_validation_design_offline_bundle(self.bundle, resource="artifacts", artifact_kind="runtime")
        self.assertEqual(artifacts.total, 1)
        self.assertEqual(artifacts.items[0]["artifact_id"], "runtime")
        self.assertIn("record_id", export_validation_design_bundle_query_csv(records).splitlines()[0])

    def test_schema_and_manifest_validation_are_closed(self) -> None:
        schema = validation_design_bundle_schema()
        self.assertEqual(schema["$id"], "glio-noncode/validation-design-bundle-schema-v1")
        manifest_report = validate_validation_design_bundle_manifest(self.bundle.to_dict(include_payloads=False))
        self.assertTrue(manifest_report.accepted)
        malformed = dict(self.bundle.to_dict(include_payloads=False))
        malformed["version"] = "wrong"
        self.assertFalse(validate_validation_design_bundle_manifest(malformed).accepted)

    def test_observability_and_staged_runtime_replay(self) -> None:
        observability = build_validation_design_bundle_observability(self.bundle)
        self.assertTrue(observability.accepted)
        self.assertEqual(observability.stage_count, 79)
        runtime = run_validation_design_bundle_runtime()
        self.assertTrue(runtime.accepted)
        self.assertEqual(len(runtime.stages), 6)
        self.assertTrue(runtime.replay.deterministic)

    def test_cli_bundle_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "bundle"
            output = Path(directory) / "result.json"
            self.assertEqual(
                main(
                    [
                        "validation-design-frontier-bundle",
                        "--destination",
                        str(destination),
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(output.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(
                main(
                    [
                        "validation-design-frontier-bundle-verify",
                        str(destination),
                        "--output",
                        str(Path(directory) / "verification.json"),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "validation-design-frontier-bundle-query",
                        str(destination),
                        "--resource",
                        "records",
                        "--operation",
                        "gap_analysis",
                        "--output",
                        str(Path(directory) / "query.json"),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "validation-design-frontier-bundle-audit",
                        str(destination),
                        "--output",
                        str(Path(directory) / "audit.json"),
                    ]
                ),
                0,
            )

    def test_http_bundle_schema_and_audit_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=60)
                connection.request("GET", "/v1/validation-design/bundle/schema")
                schema_response = connection.getresponse()
                self.assertEqual(schema_response.status, 200)
                self.assertEqual(json.loads(schema_response.read())["$id"], "glio-noncode/validation-design-bundle-schema-v1")

                connection.request("GET", "/v1/validation-design/bundle/audit")
                audit_response = connection.getresponse()
                self.assertEqual(audit_response.status, 200)
                self.assertTrue(json.loads(audit_response.read())["accepted"])

                connection.request("GET", "/v1/validation-design/bundle/observability")
                observability_response = connection.getresponse()
                self.assertEqual(observability_response.status, 200)
                self.assertTrue(json.loads(observability_response.read())["accepted"])

                connection.request("GET", "/v1/validation-design/bundle/runtime")
                runtime_response = connection.getresponse()
                self.assertEqual(runtime_response.status, 200)
                self.assertTrue(json.loads(runtime_response.read())["accepted"])
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
