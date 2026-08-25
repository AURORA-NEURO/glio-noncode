"""Independent contract tests for the D16 deployment offline handoff."""

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.deployment_frontier_offline_audit import (
    audit_deployment_frontier_offline_bundle,
    audit_deployment_frontier_offline_directory,
)
from glio_noncode.deployment_frontier_offline_boundary import (
    audit_deployment_frontier_offline_boundary,
    deployment_frontier_offline_key_inventory,
)
from glio_noncode.deployment_frontier_offline_bundle import (
    build_deployment_frontier_offline_bundle,
    verify_deployment_frontier_offline_bundle,
    write_deployment_frontier_offline_bundle,
)
from glio_noncode.deployment_frontier_offline_certification import (
    audit_deployment_frontier_offline_certification,
    certify_deployment_frontier_offline_bundle,
    query_deployment_frontier_offline_certification,
)
from glio_noncode.deployment_frontier_offline_contracts import (
    DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_COUNT,
    DEPLOYMENT_FRONTIER_OFFLINE_STAGE_COUNT,
)
from glio_noncode.deployment_frontier_offline_indexes import (
    audit_deployment_frontier_offline_indexes,
    build_deployment_frontier_offline_indexes,
)
from glio_noncode.deployment_frontier_offline_query import (
    diff_deployment_frontier_offline_bundles,
    export_deployment_frontier_offline_query_csv,
    load_deployment_frontier_offline_bundle,
    query_deployment_frontier_offline_bundle,
)
from glio_noncode.deployment_frontier_offline_reconciliation import (
    reconcile_deployment_frontier_offline_bundle,
)
from glio_noncode.deployment_frontier_offline_runtime import (
    build_deployment_frontier_offline_observability,
    run_deployment_frontier_offline_runtime,
)
from glio_noncode.deployment_frontier_offline_schema import (
    deployment_frontier_offline_bundle_schema,
    validate_deployment_frontier_offline_manifest,
)
from glio_noncode.deployment_frontier_offline_summary import (
    audit_deployment_frontier_offline_summary,
    build_deployment_frontier_offline_summary,
)


class DeploymentFrontierOfflineBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = build_deployment_frontier_offline_bundle()

    def test_bundle_closes_actual_d16_denominators(self) -> None:
        self.assertTrue(self.bundle.ready)
        self.assertEqual(self.bundle.artifact_count, DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_COUNT)
        self.assertEqual(self.bundle.stage_count, DEPLOYMENT_FRONTIER_OFFLINE_STAGE_COUNT)
        self.assertEqual(self.bundle.failed_check_count, 0)
        self.assertEqual(len(self.bundle.checks), 32)
        self.assertTrue(
            self.bundle.content_address.startswith("deployment-frontier-offline-bundle:")
        )

    def test_bundle_is_deterministic_despite_runtime_wall_clock(self) -> None:
        repeated = build_deployment_frontier_offline_bundle()
        self.assertEqual(self.bundle.content_address, repeated.content_address)
        self.assertEqual(self.bundle.runtime_address, repeated.runtime_address)
        self.assertEqual(
            [item.content_address for item in self.bundle.artifacts],
            [item.content_address for item in repeated.artifacts],
        )

    def test_filesystem_verification_and_independent_audits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "bundle"
            write_deployment_frontier_offline_bundle(self.bundle, destination)
            verification = verify_deployment_frontier_offline_bundle(destination)
            self.assertTrue(verification.accepted)
            loaded = load_deployment_frontier_offline_bundle(destination, include_payloads=True)
            self.assertTrue(audit_deployment_frontier_offline_bundle(loaded).accepted)
            self.assertTrue(audit_deployment_frontier_offline_boundary(loaded).accepted)
            self.assertTrue(audit_deployment_frontier_offline_directory(destination).accepted)
            self.assertTrue(deployment_frontier_offline_key_inventory(loaded)["accepted"])
            diff = diff_deployment_frontier_offline_bundles(destination, destination)
            self.assertTrue(diff.accepted)
            self.assertEqual(
                len(diff.unchanged_artifact_ids), DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_COUNT
            )

    def test_tampered_exact_bytes_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "bundle"
            write_deployment_frontier_offline_bundle(self.bundle, destination)
            payload = destination / "exports" / "review.csv"
            payload.write_text(payload.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
            verification = verify_deployment_frontier_offline_bundle(destination)
            self.assertFalse(verification.accepted)
            self.assertTrue(
                any(
                    "artifact-bytes:review-csv" == item.check_id and not item.passed
                    for item in verification.checks
                )
            )

    def test_queries_cover_records_controls_stages_and_indexes(self) -> None:
        records = query_deployment_frontier_offline_bundle(
            self.bundle,
            resource="records",
            filters={"operation": "privacy_security_policy"},
        )
        self.assertTrue(records.accepted)
        self.assertEqual(records.total, 4)
        self.assertTrue(
            all(item["operation"] == "privacy_security_policy" for item in records.items)
        )
        controls = query_deployment_frontier_offline_bundle(
            self.bundle, resource="records", filters={"role": "control"}, limit=100
        )
        self.assertEqual(controls.total, 12)
        stages = query_deployment_frontier_offline_bundle(self.bundle, resource="stages", limit=100)
        self.assertEqual(stages.total, DEPLOYMENT_FRONTIER_OFFLINE_STAGE_COUNT)
        self.assertEqual(stages.items[0]["sequence"], 1)
        issues = query_deployment_frontier_offline_bundle(self.bundle, resource="issues")
        self.assertEqual(issues.total, 13)
        self.assertIn(
            "record_id", export_deployment_frontier_offline_query_csv(records).splitlines()[0]
        )

    def test_schema_and_manifest_validation_are_closed(self) -> None:
        schema = deployment_frontier_offline_bundle_schema()
        self.assertEqual(schema["$id"], "glio-noncode/deployment-frontier-offline-schema-v1")
        report = validate_deployment_frontier_offline_manifest(
            self.bundle.to_dict(include_payloads=False)
        )
        self.assertTrue(report.accepted)
        malformed = dict(self.bundle.to_dict(include_payloads=False))
        malformed["version"] = "wrong"
        self.assertFalse(validate_deployment_frontier_offline_manifest(malformed).accepted)

    def test_indexes_reconciliation_and_summary_close_depth(self) -> None:
        indexes = build_deployment_frontier_offline_indexes(self.bundle)
        self.assertTrue(indexes.accepted)
        self.assertTrue(audit_deployment_frontier_offline_indexes(self.bundle, indexes).accepted)
        self.assertEqual(indexes.resource_counts["artifacts"], 51)
        self.assertEqual(indexes.resource_counts["records"], 16)
        self.assertEqual(indexes.resource_counts["stages"], 38)
        self.assertTrue(reconcile_deployment_frontier_offline_bundle(self.bundle).accepted)
        summary = build_deployment_frontier_offline_summary(self.bundle)
        self.assertTrue(summary.accepted)
        self.assertTrue(audit_deployment_frontier_offline_summary(summary).accepted)
        self.assertEqual(summary.queue_row_count, 12)
        self.assertEqual(summary.lineage_edge_count, 52)

    def test_certification_domains_are_independently_queryable(self) -> None:
        report = certify_deployment_frontier_offline_bundle(self.bundle)
        self.assertTrue(report.accepted)
        self.assertEqual(report.coverage_percent, 100.0)
        self.assertEqual(len(report.domains), 7)
        audited = audit_deployment_frontier_offline_certification(self.bundle, report)
        self.assertTrue(audited.accepted)
        self.assertEqual(
            query_deployment_frontier_offline_certification(report, failed_only=True), ()
        )
        self.assertTrue(query_deployment_frontier_offline_certification(report, domain="runtime"))

    def test_offline_runtime_rehearses_audits_and_replay(self) -> None:
        observability = build_deployment_frontier_offline_observability(self.bundle)
        self.assertTrue(observability.accepted)
        self.assertEqual(observability.stage_count, DEPLOYMENT_FRONTIER_OFFLINE_STAGE_COUNT)
        runtime = run_deployment_frontier_offline_runtime()
        self.assertTrue(runtime.accepted)
        self.assertEqual(len(runtime.stages), 10)
        self.assertTrue(runtime.replay.deterministic)

    def test_cli_bundle_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "bundle"
            output = Path(directory) / "result.json"
            self.assertEqual(
                main(
                    [
                        "deployment-frontier-offline-bundle",
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
                        "deployment-frontier-offline-bundle-verify",
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
                        "deployment-frontier-offline-bundle-query",
                        str(destination),
                        "--resource",
                        "records",
                        "--operation",
                        "privacy_security_policy",
                        "--output",
                        str(Path(directory) / "query.json"),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "deployment-frontier-offline-bundle-certification",
                        str(destination),
                        "--output",
                        str(Path(directory) / "certification.json"),
                    ]
                ),
                0,
            )

    def test_http_offline_bundle_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=60)
                for path in (
                    "/v1/deployment-frontier/bundle/schema",
                    "/v1/deployment-frontier/bundle/audit",
                    "/v1/deployment-frontier/bundle/query?resource=records&operation=privacy_security_policy",
                    "/v1/deployment-frontier/bundle/indexes",
                    "/v1/deployment-frontier/bundle/reconciliation",
                    "/v1/deployment-frontier/bundle/summary",
                    "/v1/deployment-frontier/bundle/certification",
                ):
                    connection.request("GET", path)
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200, path)
                    payload = json.loads(response.read())
                    if path.endswith("/schema"):
                        self.assertEqual(
                            payload["$id"],
                            "glio-noncode/deployment-frontier-offline-schema-v1",
                        )
                    elif "query?" in path:
                        self.assertEqual(payload["total"], 4)
                    elif path.endswith("/indexes"):
                        self.assertTrue(payload["audit"]["accepted"])
                    elif path.endswith("/summary") or path.endswith("/certification"):
                        self.assertTrue(payload["audit"]["accepted"])
                    else:
                        self.assertTrue(payload["accepted"])
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
