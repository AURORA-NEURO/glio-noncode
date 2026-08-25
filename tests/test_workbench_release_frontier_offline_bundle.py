"""Contract tests for the portable D15 workbench-release handoff."""

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.workbench_release_frontier_offline_audit import (
    audit_workbench_release_offline_bundle,
)
from glio_noncode.workbench_release_frontier_offline_boundary import (
    audit_workbench_release_offline_boundary,
    audit_workbench_release_offline_directory,
    workbench_release_offline_key_inventory,
)
from glio_noncode.workbench_release_frontier_offline_certification import (
    audit_workbench_release_offline_certification,
    certify_workbench_release_offline_bundle,
    query_workbench_release_offline_certification,
)
from glio_noncode.workbench_release_frontier_offline_bundle import (
    build_workbench_release_offline_bundle,
    verify_workbench_release_offline_bundle,
    write_workbench_release_offline_bundle,
)
from glio_noncode.workbench_release_frontier_offline_contracts import (
    WORKBENCH_RELEASE_OFFLINE_ARTIFACT_COUNT,
)
from glio_noncode.workbench_release_frontier_offline_indexes import (
    audit_workbench_release_offline_indexes,
    build_workbench_release_offline_indexes,
)
from glio_noncode.workbench_release_frontier_offline_query import (
    diff_workbench_release_offline_bundles,
    export_workbench_release_offline_query_csv,
    load_workbench_release_offline_bundle,
    query_workbench_release_offline_bundle,
)
from glio_noncode.workbench_release_frontier_offline_reconciliation import (
    reconcile_workbench_release_offline_bundle,
)
from glio_noncode.workbench_release_frontier_offline_runtime import (
    build_workbench_release_offline_observability,
    run_workbench_release_offline_bundle_runtime,
)
from glio_noncode.workbench_release_frontier_offline_schema import (
    validate_workbench_release_offline_manifest,
    workbench_release_offline_bundle_schema,
)
from glio_noncode.workbench_release_frontier_offline_summary import (
    audit_workbench_release_offline_summary,
    build_workbench_release_offline_summary,
)


class WorkbenchReleaseOfflineBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = build_workbench_release_offline_bundle()

    def test_bundle_closes_artifacts_and_d15_denominators(self) -> None:
        self.assertTrue(self.bundle.accepted)
        self.assertEqual(self.bundle.artifact_count, WORKBENCH_RELEASE_OFFLINE_ARTIFACT_COUNT)
        self.assertEqual(self.bundle.artifact_count, 56)
        self.assertEqual(self.bundle.stage_count, 49)
        self.assertEqual(self.bundle.failed_check_count, 0)
        self.assertTrue(self.bundle.content_address.startswith("workbench-release-offline-bundle:"))
        self.assertTrue(all(item.payload for item in self.bundle.artifacts))
        self.assertEqual(len(self.bundle.checks), 26)

    def test_bundle_is_deterministic_despite_runtime_wall_clock(self) -> None:
        repeated = build_workbench_release_offline_bundle()
        self.assertEqual(self.bundle.content_address, repeated.content_address)
        self.assertEqual(self.bundle.runtime_address, repeated.runtime_address)
        self.assertEqual(
            [item.content_address for item in self.bundle.artifacts],
            [item.content_address for item in repeated.artifacts],
        )

    def test_filesystem_verification_and_independent_audits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "bundle"
            write_workbench_release_offline_bundle(self.bundle, destination)
            verification = verify_workbench_release_offline_bundle(destination)
            self.assertTrue(verification.accepted)
            loaded = load_workbench_release_offline_bundle(destination, include_payloads=True)
            self.assertTrue(audit_workbench_release_offline_bundle(loaded).accepted)
            self.assertTrue(audit_workbench_release_offline_boundary(loaded).accepted)
            self.assertTrue(audit_workbench_release_offline_directory(destination).accepted)
            self.assertTrue(workbench_release_offline_key_inventory(loaded)["accepted"])
            diff = diff_workbench_release_offline_bundles(destination, destination)
            self.assertTrue(diff.accepted)
            self.assertEqual(
                len(diff.unchanged_artifact_ids), WORKBENCH_RELEASE_OFFLINE_ARTIFACT_COUNT
            )

    def test_tampering_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "bundle"
            write_workbench_release_offline_bundle(self.bundle, destination)
            payload = destination / "exports" / "review.csv"
            payload.write_text(payload.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
            verification = verify_workbench_release_offline_bundle(destination)
            self.assertFalse(verification.accepted)
            self.assertTrue(
                any(
                    "artifact-bytes" in item.check_id and not item.passed
                    for item in verification.checks
                )
            )

    def test_queries_cover_runtime_resources_and_filters(self) -> None:
        records = query_workbench_release_offline_bundle(
            self.bundle, resource="records", filters={"operation": "review_form"}
        )
        self.assertTrue(records.accepted)
        self.assertEqual(records.total, 4)
        self.assertTrue(all(item["operation"] == "review_form" for item in records.items))
        checks = query_workbench_release_offline_bundle(
            self.bundle, resource="checks", filters={"state": "passed"}, limit=200
        )
        self.assertEqual(checks.total, 80)
        self.assertTrue(all(item["passed"] for item in checks.items))
        sources = query_workbench_release_offline_bundle(self.bundle, resource="sources")
        self.assertEqual(sources.total, 5)
        self.assertTrue(all(str(item["uri"]).startswith("https://") for item in sources.items))
        stages = query_workbench_release_offline_bundle(self.bundle, resource="stages", limit=100)
        self.assertEqual(stages.total, 49)
        self.assertEqual(stages.items[0]["sequence"], 1)
        events = query_workbench_release_offline_bundle(self.bundle, resource="events")
        self.assertEqual(events.total, 1)
        artifacts = query_workbench_release_offline_bundle(
            self.bundle, resource="artifacts", filters={"kind": "runtime"}
        )
        self.assertEqual(artifacts.total, 1)
        self.assertEqual(artifacts.items[0]["artifact_id"], "runtime")
        self.assertIn(
            "record_id", export_workbench_release_offline_query_csv(records).splitlines()[0]
        )

    def test_schema_and_manifest_validation_are_closed(self) -> None:
        schema = workbench_release_offline_bundle_schema()
        self.assertEqual(schema["$id"], "glio-noncode/workbench-release-offline-schema-v1")
        report = validate_workbench_release_offline_manifest(
            self.bundle.to_dict(include_payloads=False)
        )
        self.assertTrue(report.accepted)
        malformed = dict(self.bundle.to_dict(include_payloads=False))
        malformed["version"] = "wrong"
        self.assertFalse(validate_workbench_release_offline_manifest(malformed).accepted)

    def test_observability_and_staged_runtime_replay(self) -> None:
        observability = build_workbench_release_offline_observability(self.bundle)
        self.assertTrue(observability.accepted)
        self.assertEqual(observability.artifact_count, 56)
        self.assertEqual(observability.stage_count, 49)
        self.assertEqual(observability.component_count, 53)
        runtime = run_workbench_release_offline_bundle_runtime()
        self.assertTrue(runtime.accepted)
        self.assertEqual(len(runtime.stages), 6)
        self.assertTrue(runtime.replay.deterministic)

    def test_indexes_reconciliation_and_summary_conserve_depth(self) -> None:
        indexes = build_workbench_release_offline_indexes(self.bundle)
        self.assertTrue(indexes.accepted)
        self.assertTrue(audit_workbench_release_offline_indexes(self.bundle, indexes).accepted)
        self.assertEqual(
            indexes.resource_counts,
            {
                "artifacts": 56,
                "records": 16,
                "sources": 5,
                "executions": 16,
                "checks": 80,
                "stages": 49,
                "operations": 4,
                "queue_rows": 12,
            },
        )
        self.assertTrue(reconcile_workbench_release_offline_bundle(self.bundle).accepted)
        summary = build_workbench_release_offline_summary(self.bundle)
        self.assertTrue(summary.accepted)
        self.assertTrue(audit_workbench_release_offline_summary(summary).accepted)
        self.assertEqual(summary.record_count, 16)
        self.assertEqual(summary.source_count, 5)
        self.assertEqual(summary.evaluation_check_count, 80)
        self.assertEqual(summary.runtime_stage_count, 49)
        self.assertEqual(summary.lineage_edge_count, 52)
        self.assertEqual(summary.queue_row_count, 12)

    def test_independent_certification_domains_and_queries(self) -> None:
        report = certify_workbench_release_offline_bundle(self.bundle)
        self.assertTrue(report.accepted)
        self.assertEqual(report.check_count, 41)
        self.assertEqual(report.coverage_percent, 100.0)
        self.assertEqual(len(report.domains), 7)
        self.assertTrue(audit_workbench_release_offline_certification(self.bundle, report).accepted)
        failed = query_workbench_release_offline_certification(report, failed_only=True)
        self.assertEqual(failed, ())
        runtime_checks = query_workbench_release_offline_certification(report, domain="runtime")
        self.assertTrue(runtime_checks)

    def test_cli_bundle_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "bundle"
            output = Path(directory) / "result.json"
            self.assertEqual(
                main(
                    [
                        "workbench-release-offline-bundle",
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
                        "workbench-release-offline-bundle-verify",
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
                        "workbench-release-offline-bundle-query",
                        str(destination),
                        "--resource",
                        "records",
                        "--operation",
                        "review_form",
                        "--output",
                        str(Path(directory) / "query.json"),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "workbench-release-offline-bundle-audit",
                        str(destination),
                        "--output",
                        str(Path(directory) / "audit.json"),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "workbench-release-offline-bundle-summary",
                        str(destination),
                        "--output",
                        str(Path(directory) / "summary.json"),
                    ]
                ),
                0,
            )

    def test_http_bundle_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=60)
                for path in (
                    "/v1/workbench-release/bundle/schema",
                    "/v1/workbench-release/bundle/audit",
                    "/v1/workbench-release/bundle/query?resource=records&operation=review_form",
                    "/v1/workbench-release/bundle/indexes",
                    "/v1/workbench-release/bundle/reconciliation",
                    "/v1/workbench-release/bundle/summary",
                ):
                    connection.request("GET", path)
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200, path)
                    payload = json.loads(response.read())
                    if path.endswith("/schema"):
                        self.assertEqual(
                            payload["$id"], "glio-noncode/workbench-release-offline-schema-v1"
                        )
                    elif path.endswith("/query?resource=records&operation=review_form"):
                        self.assertEqual(payload["total"], 4)
                    elif path.endswith("/indexes") or path.endswith("/summary"):
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
