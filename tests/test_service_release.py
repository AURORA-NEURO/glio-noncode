"""Contract tests for the complete public service-release registry."""

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.service_release_bundle import (
    build_service_release_snapshot,
    service_release_snapshot_counts,
)
from glio_noncode.service_release_certification import (
    audit_service_release_certification,
    certify_service_release,
)
from glio_noncode.service_release_contracts import (
    SERVICE_RELEASE_ARTIFACT_COUNT,
    SERVICE_RELEASE_DEPENDENCY_COUNT,
    SERVICE_RELEASE_GATE_COUNT,
    SERVICE_RELEASE_SURFACE_IDS,
)
from glio_noncode.service_release_export import (
    build_service_release_export,
    verify_service_release_export,
    write_service_release_export,
)
from glio_noncode.service_release_failure_injection import (
    audit_service_release_failure_injections,
    run_service_release_failure_injections,
)
from glio_noncode.service_release_graph import audit_service_release_graph, build_service_release_graph
from glio_noncode.service_release_indexes import audit_service_release_indexes, build_service_release_indexes
from glio_noncode.service_release_observability import (
    audit_service_release_observability,
    build_service_release_observability,
)
from glio_noncode.service_release_plan import audit_service_release_plan, build_service_release_plan
from glio_noncode.service_release_query import (
    export_service_release_query_csv,
    export_service_release_query_markdown,
    query_service_release,
)
from glio_noncode.service_release_reconciliation import (
    audit_service_release_summary,
    build_service_release_summary,
    reconcile_service_release,
)
from glio_noncode.service_release_runtime import run_service_release
from glio_noncode.service_release_schema import service_release_schema, validate_service_release_schema
from glio_noncode.service_release_support import forbidden_keys
from glio_noncode.service_release_views import audit_service_release_views, build_service_release_views
from glio_noncode.service_surface import (
    build_service_surface_closure,
    build_service_surface_snapshot,
    service_program_release_projection,
    service_surface_status,
)


class ServiceReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.service = build_service_surface_snapshot()
        cls.release = build_service_release_snapshot(cls.service)

    def test_service_snapshot_contains_d01_d16_release(self) -> None:
        status = service_surface_status(self.service)
        self.assertTrue(self.service.accepted)
        self.assertTrue(self.service.program_release.accepted)
        self.assertEqual(status["program_release"]["domain_count"], 16)
        self.assertEqual(status["program_release"]["artifact_count"], 18)
        self.assertEqual(status["program_release"]["dependency_count"], 120)
        self.assertEqual(status["program_release"]["gate_count"], 96)

    def test_registry_cardinality_and_address_policy(self) -> None:
        counts = service_release_snapshot_counts(self.release)
        self.assertTrue(self.release.accepted)
        self.assertEqual(tuple(item.surface_id for item in self.release.surfaces), SERVICE_RELEASE_SURFACE_IDS)
        self.assertEqual(counts["surface_count"], 6)
        self.assertEqual(counts["artifact_count"], SERVICE_RELEASE_ARTIFACT_COUNT)
        self.assertEqual(counts["dependency_count"], SERVICE_RELEASE_DEPENDENCY_COUNT)
        self.assertEqual(counts["gate_count"], SERVICE_RELEASE_GATE_COUNT)
        self.assertEqual(len({item.content_address for item in self.release.surfaces}), 6)
        self.assertEqual(len({item.relative_path for item in self.release.artifacts}), 13)
        self.assertEqual(forbidden_keys(self.release.to_dict()), ())

    def test_service_projection_queries_program_release(self) -> None:
        projection = service_program_release_projection(self.service, resource="gates", accepted_only=True, limit=10)
        self.assertTrue(projection["release_status"]["accepted"])
        self.assertEqual(projection["total"], 96)
        self.assertEqual(len(projection["items"]), 10)
        self.assertTrue(projection["has_more"])
        self.assertTrue(all(item["passed"] for item in projection["items"]))

    def test_queries_filter_sort_and_export(self) -> None:
        result = query_service_release(self.release, resource="artifacts", surface_id="program-release")
        self.assertEqual(result.total, 4)
        self.assertFalse(result.has_more)
        self.assertEqual([item["artifact_id"] for item in result.items], [
            "program-release-dependencies-csv",
            "program-release-domains-csv",
            "program-release-gates-csv",
            "program-release-json",
        ])
        self.assertIn(b"artifact_id", export_service_release_query_csv(result))
        self.assertIn(b"# Service release registry", export_service_release_query_markdown(result))
        with self.assertRaises(Exception):
            query_service_release(self.release, resource="surfaces", limit=501)

    def test_indexes_reconcile_and_certify(self) -> None:
        indexes = build_service_release_indexes(self.release)
        self.assertTrue(indexes.accepted)
        self.assertTrue(audit_service_release_indexes(self.release, indexes).accepted)
        reconciliation = reconcile_service_release(self.release, self.service)
        self.assertTrue(reconciliation.accepted)
        self.assertEqual(reconciliation.failed_check_ids, ())
        summary = build_service_release_summary(self.release, self.service)
        self.assertTrue(summary.accepted)
        self.assertTrue(audit_service_release_summary(summary, self.service).accepted)
        certification = certify_service_release(self.release)
        self.assertTrue(certification.accepted)
        self.assertEqual(certification.coverage_percent, 100.0)
        self.assertTrue(all(item.passed for item in audit_service_release_certification(certification, self.release)))

    def test_observability_graph_failures_plan_and_views(self) -> None:
        observability = build_service_release_observability(self.release)
        self.assertTrue(observability.accepted)
        self.assertEqual(observability.event_count, 78)
        self.assertEqual(observability.metric_count, 24)
        self.assertTrue(all(item.passed for item in audit_service_release_observability(observability)))
        graph = build_service_release_graph(self.release)
        self.assertTrue(graph.connected)
        self.assertEqual(graph.to_dict()["node_count"], 44)
        self.assertEqual(graph.to_dict()["edge_count"], 58)
        self.assertTrue(all(item.passed for item in audit_service_release_graph(graph, self.release)))
        failures = run_service_release_failure_injections(self.release)
        self.assertTrue(failures.accepted)
        self.assertTrue(all(item.passed for item in audit_service_release_failure_injections(failures)))
        plan = build_service_release_plan(self.release)
        self.assertEqual(len(plan.steps), 23)
        self.assertTrue(all(item.passed for item in audit_service_release_plan(plan)))
        views = build_service_release_views(self.release)
        self.assertEqual(views.to_dict()["view_count"], 5)
        self.assertTrue(all(item.passed for item in audit_service_release_views(views, self.release)))

    def test_schema_and_runtime_close_all_planes(self) -> None:
        schema = service_release_schema()
        self.assertEqual(schema["denominators"]["surface_count"], 6)
        self.assertTrue(all(item.passed for item in validate_service_release_schema(self.release, schema)))
        runtime = run_service_release(self.service, run_id="test-service-release-run", bundle_id="test-service-release")
        self.assertTrue(runtime.accepted)
        self.assertEqual(len(runtime.stages), 14)
        self.assertEqual(runtime.replay.first_address, runtime.replay.second_address)
        self.assertEqual(runtime.replay.expected_address, runtime.snapshot.content_address)
        self.assertEqual(runtime.failed_stage_ids if hasattr(runtime, "failed_stage_ids") else (), ())

    def test_exact_byte_export_round_trip_and_tamper_detection(self) -> None:
        runtime = run_service_release(self.service, run_id="test-export-run", bundle_id="test-export-release")
        packet = build_service_release_export(runtime, self.service)
        self.assertTrue(packet.accepted)
        self.assertEqual(len(packet.artifacts), 13)
        with tempfile.TemporaryDirectory() as directory:
            write_service_release_export(packet, directory)
            verification = verify_service_release_export(directory)
            self.assertTrue(verification.accepted)
            self.assertEqual(verification.checked_artifact_count, 13)
            target = Path(directory) / "surfaces" / "status.json"
            payload = json.loads(target.read_text(encoding="utf-8"))
            payload["accepted"] = False
            target.write_text(json.dumps(payload), encoding="utf-8")
            tampered = verify_service_release_export(directory)
            self.assertFalse(tampered.accepted)
            self.assertIn("surfaces/status.json", tampered.tampered_paths)

    def test_service_surface_closure_contains_registry_snapshot(self) -> None:
        closure = build_service_surface_closure(self.service)
        self.assertTrue(closure["accepted"])
        self.assertIn("program_release_snapshot", closure)
        self.assertIn("program_release_domains", closure["queries"])
        self.assertEqual(closure["status"]["program_release"]["domain_count"], 16)
        self.assertNotIn("agent_id", json.dumps(closure, sort_keys=True).lower())
        self.assertNotIn("model_name", json.dumps(closure, sort_keys=True).lower())

    def test_http_registry_routes_and_invalid_resource(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server("127.0.0.1", 0, directory)
            server.glio_service_surface = self.service
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=60)
                connection.request("GET", "/v1/service-release?bundle_id=http-release")
                snapshot = connection.getresponse()
                self.assertEqual(snapshot.status, 200)
                snapshot_payload = json.loads(snapshot.read())
                self.assertTrue(snapshot_payload["accepted"])
                self.assertEqual(len(snapshot_payload["surfaces"]), 6)
                connection.request("GET", "/v1/service-release/query?bundle_id=http-release&resource=gates&accepted=true&limit=3")
                query = connection.getresponse()
                self.assertEqual(query.status, 200)
                self.assertEqual(json.loads(query.read())["total"], 24)
                connection.request("GET", "/v1/service-release/schema?bundle_id=http-release")
                schema = connection.getresponse()
                self.assertEqual(schema.status, 200)
                self.assertTrue(all(item["passed"] for item in json.loads(schema.read())["audit"]))
                connection.request("GET", "/v1/service-release/query?resource=unknown")
                invalid = connection.getresponse()
                self.assertEqual(invalid.status, 422)
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_cli_snapshot_and_schema_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            snapshot_path = str(Path(directory) / "snapshot.json")
            schema_path = str(Path(directory) / "schema.json")
            self.assertEqual(main(["service-release", "--plane", "snapshot", "--output", snapshot_path]), 0)
            self.assertEqual(main(["service-release", "--plane", "schema", "--output", schema_path]), 0)
            self.assertTrue(json.loads(Path(snapshot_path).read_text(encoding="utf-8"))["accepted"])
            schema_payload = json.loads(Path(schema_path).read_text(encoding="utf-8"))
            self.assertTrue(schema_payload["accepted"])


if __name__ == "__main__":
    unittest.main()
