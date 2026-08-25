"""Contract tests for the portable D14 evidence lifecycle handoff."""

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.evidence_lifecycle_frontier_offline_audit import audit_evidence_lifecycle_offline_bundle
from glio_noncode.evidence_lifecycle_frontier_offline_bundle import (
    EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_ARTIFACT_COUNT,
    build_evidence_lifecycle_offline_bundle,
    verify_evidence_lifecycle_offline_bundle,
    write_evidence_lifecycle_offline_bundle,
)
from glio_noncode.evidence_lifecycle_frontier_offline_query import (
    diff_evidence_lifecycle_offline_bundles,
    export_evidence_lifecycle_offline_query_csv,
    load_evidence_lifecycle_offline_bundle,
    query_evidence_lifecycle_offline_bundle,
)
from glio_noncode.evidence_lifecycle_frontier_offline_runtime import (
    build_evidence_lifecycle_offline_observability,
    run_evidence_lifecycle_offline_bundle_runtime,
)
from glio_noncode.evidence_lifecycle_frontier_offline_boundary import (
    audit_evidence_lifecycle_offline_boundary,
    evidence_lifecycle_offline_boundary_key_inventory,
)
from glio_noncode.evidence_lifecycle_frontier_offline_indexes import (
    EvidenceLifecycleOfflineIndexKey,
    EvidenceLifecycleOfflineIndexResource,
    audit_evidence_lifecycle_offline_indexes,
    build_evidence_lifecycle_offline_indexes,
    query_evidence_lifecycle_offline_indexes,
)
from glio_noncode.evidence_lifecycle_frontier_offline_reconciliation import (
    reconcile_evidence_lifecycle_offline_bundle,
)
from glio_noncode.evidence_lifecycle_frontier_offline_schema import (
    evidence_lifecycle_offline_bundle_schema,
    validate_evidence_lifecycle_offline_manifest,
)
from glio_noncode.evidence_lifecycle_frontier_offline_summary import (
    audit_evidence_lifecycle_offline_summary,
    build_evidence_lifecycle_offline_summary,
)


class EvidenceLifecycleOfflineBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = build_evidence_lifecycle_offline_bundle()

    def test_bundle_closes_artifacts_and_denominators(self) -> None:
        self.assertTrue(self.bundle.accepted)
        self.assertEqual(self.bundle.artifact_count, EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_ARTIFACT_COUNT)
        self.assertEqual(self.bundle.failed_check_count, 0)
        self.assertTrue(self.bundle.content_address.startswith("evidence-lifecycle-offline-bundle:"))
        self.assertTrue(all(item.payload for item in self.bundle.artifacts))
        self.assertEqual(len(self.bundle.checks), 24)

    def test_bundle_is_deterministic_despite_runtime_wall_clock(self) -> None:
        repeated = build_evidence_lifecycle_offline_bundle()
        self.assertEqual(self.bundle.content_address, repeated.content_address)
        self.assertEqual(self.bundle.runtime_address, repeated.runtime_address)
        self.assertEqual(
            [item.content_address for item in self.bundle.artifacts],
            [item.content_address for item in repeated.artifacts],
        )

    def test_filesystem_verification_and_independent_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "bundle"
            write_evidence_lifecycle_offline_bundle(self.bundle, destination)
            verification = verify_evidence_lifecycle_offline_bundle(destination)
            self.assertTrue(verification.accepted)
            loaded = load_evidence_lifecycle_offline_bundle(destination, include_payloads=True)
            audit = audit_evidence_lifecycle_offline_bundle(loaded)
            self.assertTrue(audit.accepted)
            self.assertEqual(audit.failed_check_ids, ())
            diff = diff_evidence_lifecycle_offline_bundles(destination, destination)
            self.assertTrue(diff.accepted)
            self.assertEqual(len(diff.unchanged_artifact_ids), EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_ARTIFACT_COUNT)

    def test_tampering_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "bundle"
            write_evidence_lifecycle_offline_bundle(self.bundle, destination)
            review_csv = destination / "review.csv"
            review_csv.write_text(review_csv.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
            verification = verify_evidence_lifecycle_offline_bundle(destination)
            self.assertFalse(verification.accepted)
            self.assertTrue(any("review-csv:bytes" in item.check_id and not item.passed for item in verification.checks))

    def test_queries_cover_records_checks_sources_events_and_artifacts(self) -> None:
        records = query_evidence_lifecycle_offline_bundle(self.bundle, resource="records", operation="graph_construction")
        self.assertTrue(records.accepted)
        self.assertEqual(records.total, 4)
        self.assertTrue(all(item["operation"] == "graph_construction" for item in records.items))

        checks = query_evidence_lifecycle_offline_bundle(self.bundle, resource="checks", state="passed", limit=200)
        self.assertTrue(checks.accepted)
        self.assertEqual(checks.total, 120)
        self.assertTrue(all(item["passed"] for item in checks.items))

        sources = query_evidence_lifecycle_offline_bundle(self.bundle, resource="sources")
        self.assertEqual(sources.total, 5)
        self.assertTrue(all(str(item["uri"]).startswith("https://") for item in sources.items))

        events = query_evidence_lifecycle_offline_bundle(self.bundle, resource="events", limit=100)
        self.assertEqual(events.total, 26)
        artifacts = query_evidence_lifecycle_offline_bundle(self.bundle, resource="artifacts", artifact_kind="runtime")
        self.assertEqual(artifacts.total, 1)
        self.assertEqual(artifacts.items[0]["artifact_id"], "runtime")
        self.assertIn("record_id", export_evidence_lifecycle_offline_query_csv(records).splitlines()[0])

    def test_schema_and_manifest_validation_are_closed(self) -> None:
        schema = evidence_lifecycle_offline_bundle_schema()
        self.assertEqual(schema["$id"], "glio-noncode/evidence-lifecycle-offline-schema-v1")
        manifest_report = validate_evidence_lifecycle_offline_manifest(self.bundle.to_dict(include_payloads=False))
        self.assertTrue(manifest_report.accepted)
        malformed = dict(self.bundle.to_dict(include_payloads=False))
        malformed["version"] = "wrong"
        self.assertFalse(validate_evidence_lifecycle_offline_manifest(malformed).accepted)

    def test_observability_and_staged_runtime_replay(self) -> None:
        observability = build_evidence_lifecycle_offline_observability(self.bundle)
        self.assertTrue(observability.accepted)
        self.assertEqual(observability.artifact_count, 21)
        self.assertEqual(observability.stage_count, 10)
        runtime = run_evidence_lifecycle_offline_bundle_runtime()
        self.assertTrue(runtime.accepted)
        self.assertEqual(len(runtime.stages), 6)
        self.assertTrue(runtime.replay.deterministic)

    def test_indexes_boundary_and_reconciliation_close(self) -> None:
        catalog = build_evidence_lifecycle_offline_indexes(self.bundle)
        self.assertTrue(catalog.accepted)
        self.assertTrue(audit_evidence_lifecycle_offline_indexes(self.bundle, catalog).accepted)
        records = query_evidence_lifecycle_offline_indexes(
            catalog,
            resource=EvidenceLifecycleOfflineIndexResource.RECORDS,
            key=EvidenceLifecycleOfflineIndexKey.OPERATION,
            value="graph_construction",
        )
        self.assertEqual(records.total, 4)
        self.assertTrue(audit_evidence_lifecycle_offline_boundary(self.bundle).accepted)
        self.assertTrue(evidence_lifecycle_offline_boundary_key_inventory(self.bundle)["accepted"])
        self.assertTrue(reconcile_evidence_lifecycle_offline_bundle(self.bundle).accepted)

    def test_reviewer_summary_conserves_all_major_denominators(self) -> None:
        summary = build_evidence_lifecycle_offline_summary(self.bundle)
        self.assertTrue(summary.accepted)
        self.assertTrue(audit_evidence_lifecycle_offline_summary(summary).accepted)
        self.assertEqual(summary.record_count, 16)
        self.assertEqual(summary.source_count, 5)
        self.assertEqual(summary.evaluation_check_count, 120)
        self.assertEqual(summary.runtime_stage_count, 10)
        self.assertEqual(summary.observability_event_count, 26)
        self.assertEqual(summary.lineage_edge_count, 36)
        self.assertEqual(summary.ready_queue_count, 4)
        self.assertEqual(summary.held_queue_count, 12)

    def test_cli_bundle_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "bundle"
            output = Path(directory) / "result.json"
            self.assertEqual(
                main(
                    [
                        "evidence-lifecycle-offline-bundle",
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
                        "evidence-lifecycle-offline-bundle-verify",
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
                        "evidence-lifecycle-offline-bundle-query",
                        str(destination),
                        "--resource",
                        "records",
                        "--operation",
                        "graph_construction",
                        "--output",
                        str(Path(directory) / "query.json"),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "evidence-lifecycle-offline-bundle-audit",
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
                connection.request("GET", "/v1/evidence-lifecycle/bundle/schema")
                schema_response = connection.getresponse()
                self.assertEqual(schema_response.status, 200)
                self.assertEqual(json.loads(schema_response.read())["$id"], "glio-noncode/evidence-lifecycle-offline-schema-v1")

                connection.request("GET", "/v1/evidence-lifecycle/bundle/audit")
                audit_response = connection.getresponse()
                self.assertEqual(audit_response.status, 200)
                self.assertTrue(json.loads(audit_response.read())["accepted"])

                connection.request("GET", "/v1/evidence-lifecycle/bundle/observability")
                observability_response = connection.getresponse()
                self.assertEqual(observability_response.status, 200)
                self.assertTrue(json.loads(observability_response.read())["accepted"])

                connection.request("GET", "/v1/evidence-lifecycle/bundle/runtime")
                runtime_response = connection.getresponse()
                self.assertEqual(runtime_response.status, 200)
                self.assertTrue(json.loads(runtime_response.read())["accepted"])

                connection.request("GET", "/v1/evidence-lifecycle/bundle/indexes")
                indexes_response = connection.getresponse()
                self.assertEqual(indexes_response.status, 200)
                self.assertTrue(json.loads(indexes_response.read())["audit"]["accepted"])

                connection.request("GET", "/v1/evidence-lifecycle/bundle/boundary")
                boundary_response = connection.getresponse()
                self.assertEqual(boundary_response.status, 200)
                self.assertTrue(json.loads(boundary_response.read())["accepted"])

                connection.request("GET", "/v1/evidence-lifecycle/bundle/reconciliation")
                reconciliation_response = connection.getresponse()
                self.assertEqual(reconciliation_response.status, 200)
                self.assertTrue(json.loads(reconciliation_response.read())["accepted"])

                connection.request("GET", "/v1/evidence-lifecycle/bundle/summary")
                summary_response = connection.getresponse()
                self.assertEqual(summary_response.status, 200)
                self.assertTrue(json.loads(summary_response.read())["audit"]["accepted"])
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
