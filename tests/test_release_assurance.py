"""Contract tests for the whole-product release-assurance gate."""

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.public_surface_audit import build_default_public_surface_audit
from glio_noncode.release_assurance_bundle import (
    build_release_assurance_snapshot,
    release_assurance_snapshot_counts,
)
from glio_noncode.release_assurance_catalog import build_release_assurance_catalog, query_release_assurance_catalog
from glio_noncode.release_assurance_checkpoint import audit_release_assurance_checkpoint, build_release_assurance_checkpoint
from glio_noncode.release_assurance_compliance import audit_release_assurance_compliance
from glio_noncode.release_assurance_contracts import (
    RELEASE_ASSURANCE_CHECK_COUNT,
    RELEASE_ASSURANCE_DOMAIN_COUNT,
    RELEASE_ASSURANCE_EVIDENCE_LINK_COUNT,
    RELEASE_ASSURANCE_EVENT_COUNT,
    RELEASE_ASSURANCE_EXPORT_ARTIFACT_COUNT,
    RELEASE_ASSURANCE_FAILURE_CASE_COUNT,
    RELEASE_ASSURANCE_METRIC_COUNT,
    RELEASE_ASSURANCE_PLAN_STEP_COUNT,
    RELEASE_ASSURANCE_RUNTIME_STAGE_TOTAL,
    RELEASE_ASSURANCE_VIEW_COUNT,
)
from glio_noncode.release_assurance_diff import audit_release_assurance_diff, build_release_assurance_diff
from glio_noncode.release_assurance_export import (
    build_release_assurance_export,
    verify_release_assurance_export,
    write_release_assurance_export,
)
from glio_noncode.release_assurance_failure_injection import (
    audit_release_assurance_failure_injections,
    run_release_assurance_failure_injections,
)
from glio_noncode.release_assurance_graph import audit_release_assurance_graph, build_release_assurance_graph
from glio_noncode.release_assurance_history import (
    audit_release_assurance_history,
    build_release_assurance_history,
    export_release_assurance_history_csv,
    export_release_assurance_history_markdown,
    query_release_assurance_history,
)
from glio_noncode.release_assurance_indexes import audit_release_assurance_indexes, build_release_assurance_indexes
from glio_noncode.release_assurance_observability import (
    audit_release_assurance_observability,
    build_release_assurance_observability,
)
from glio_noncode.release_assurance_operations import audit_release_assurance_operations, build_release_assurance_operations
from glio_noncode.release_assurance_plan import audit_release_assurance_plan, build_release_assurance_plan
from glio_noncode.release_assurance_performance import audit_release_assurance_performance
from glio_noncode.release_assurance_query import (
    export_release_assurance_query_csv,
    export_release_assurance_query_markdown,
    query_release_assurance,
)
from glio_noncode.release_assurance_reconciliation import audit_release_assurance_reconciliation, reconcile_release_assurance
from glio_noncode.release_assurance_reports import export_release_assurance_report_csv, render_release_assurance_report_markdown
from glio_noncode.release_assurance_review import audit_release_assurance_review_queue, build_release_assurance_review_queue
from glio_noncode.release_assurance_runtime import run_release_assurance
from glio_noncode.release_assurance_schema import release_assurance_schema, validate_release_assurance_schema
from glio_noncode.release_assurance_summary import (
    audit_release_assurance_summary,
    build_release_assurance_summary,
    release_assurance_status,
)
from glio_noncode.release_assurance_thresholds import (
    audit_release_assurance_thresholds,
    evaluate_release_assurance_thresholds,
)
from glio_noncode.release_assurance_views import audit_release_assurance_views, build_release_assurance_views
from glio_noncode.release_assurance_support import forbidden_keys
from glio_noncode.service_surface import build_service_surface_snapshot


class ReleaseAssuranceTests(unittest.TestCase):
    """Exercise every public plane without exposing source records."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.service = build_service_surface_snapshot()
        cls.public_audit = build_default_public_surface_audit(snapshot=cls.service)
        cls.snapshot = build_release_assurance_snapshot(
            cls.service,
            public_audit=cls.public_audit,
            bundle_id="test-release-assurance",
            run_id="test-release-assurance-run",
        )

    def test_four_planes_close_denominators_and_boundary(self) -> None:
        counts = release_assurance_snapshot_counts(self.snapshot)
        self.assertTrue(self.snapshot.accepted)
        self.assertEqual(counts["domain_count"], RELEASE_ASSURANCE_DOMAIN_COUNT)
        self.assertEqual(counts["evidence_count"], RELEASE_ASSURANCE_EVIDENCE_LINK_COUNT)
        self.assertEqual(counts["check_count"], RELEASE_ASSURANCE_CHECK_COUNT)
        self.assertEqual(counts["passed_check_count"], RELEASE_ASSURANCE_CHECK_COUNT)
        self.assertEqual(counts["overall_percent"], 100.0)
        self.assertEqual(tuple(item.domain_id for item in self.snapshot.domains), (
            "capability-catalog", "architecture-program", "service-release", "public-surface"
        ))
        self.assertEqual(len({item.content_address for item in self.snapshot.domains}), 4)
        self.assertEqual(forbidden_keys(self.snapshot.to_dict()), ())

    def test_schema_summary_and_status_reconcile(self) -> None:
        schema = release_assurance_schema()
        self.assertEqual(schema["denominators"]["domain_count"], RELEASE_ASSURANCE_DOMAIN_COUNT)
        self.assertTrue(all(item.passed for item in validate_release_assurance_schema(self.snapshot, schema)))
        summary = build_release_assurance_summary(self.snapshot)
        self.assertTrue(summary.accepted)
        self.assertTrue(audit_release_assurance_summary(summary, self.snapshot).accepted)
        self.assertEqual(summary.counter_map["check_count"], RELEASE_ASSURANCE_CHECK_COUNT)
        status = release_assurance_status(self.snapshot)
        self.assertTrue(status["accepted"])
        self.assertEqual(status["overall_percent"], 100.0)
        self.assertEqual(status["failed_check_count"], 0)

    def test_query_filters_pagination_and_exports(self) -> None:
        domains = query_release_assurance(self.snapshot, resource="domains", limit=2)
        self.assertEqual(domains.total, 4)
        self.assertEqual(len(domains.items), 2)
        self.assertTrue(domains.has_more)
        checks = query_release_assurance(
            self.snapshot,
            resource="checks",
            domain_id="service-release",
            passed_only=True,
        )
        self.assertEqual(checks.total, 5)
        self.assertTrue(all(item["passed"] for item in checks.items))
        self.assertIn(b"domain_id", export_release_assurance_query_csv(checks))
        self.assertIn(b"# Release assurance", export_release_assurance_query_markdown(checks))
        with self.assertRaises(Exception):
            query_release_assurance(self.snapshot, resource="unknown")

    def test_deep_reconciliation_catalog_compliance_and_operations(self) -> None:
        reconciliation = reconcile_release_assurance(
            self.snapshot,
            source_snapshot=self.service,
            public_audit=self.public_audit,
        )
        self.assertTrue(reconciliation.accepted)
        self.assertGreaterEqual(reconciliation.row_count, 30)
        self.assertEqual(reconciliation.failed_row_ids, ())
        self.assertTrue(all(item.passed for item in audit_release_assurance_reconciliation(reconciliation, self.snapshot)))
        comparison_snapshot = build_release_assurance_snapshot(
            self.service,
            public_audit=self.public_audit,
            bundle_id=self.snapshot.bundle_id,
            run_id=self.snapshot.run_id,
        )
        diff = build_release_assurance_diff(self.snapshot, comparison_snapshot)
        self.assertTrue(diff.accepted)
        self.assertTrue(diff.identical)
        self.assertTrue(all(item.passed for item in audit_release_assurance_diff(diff, self.snapshot, comparison_snapshot)))
        catalog = build_release_assurance_catalog(self.snapshot)
        self.assertTrue(catalog.accepted)
        self.assertEqual(len(catalog.entries), 10)
        self.assertEqual(len(query_release_assurance_catalog(catalog, source_plane="runtime")), 6)
        compliance = audit_release_assurance_compliance(self.snapshot)
        self.assertTrue(compliance.accepted)
        self.assertEqual(compliance.failed_item_ids, ())
        performance = audit_release_assurance_performance(self.snapshot)
        self.assertTrue(performance.accepted)
        operations = build_release_assurance_operations(self.snapshot)
        self.assertTrue(operations.accepted)
        self.assertEqual(len(operations.operations), RELEASE_ASSURANCE_CHECK_COUNT)
        self.assertTrue(all(item.passed for item in audit_release_assurance_operations(operations, self.snapshot)))

    def test_reviewer_report_exports_are_public_and_deterministic(self) -> None:
        runtime = run_release_assurance(
            self.service,
            public_audit=self.public_audit,
            run_id="test-report-run",
            bundle_id="test-report-bundle",
        )
        markdown = render_release_assurance_report_markdown(runtime)
        csv = export_release_assurance_report_csv(runtime)
        self.assertIn(b"whole-product release assurance", markdown)
        self.assertIn(b"stage_id", csv)
        self.assertNotIn(b"model_name", markdown.lower())
        self.assertNotIn(b"agent_id", csv.lower())
        checkpoint = build_release_assurance_checkpoint(runtime)
        self.assertTrue(checkpoint.accepted)
        self.assertEqual(checkpoint.component_count, 6)
        self.assertTrue(all(item.passed for item in audit_release_assurance_checkpoint(checkpoint, runtime)))
        review = build_release_assurance_review_queue(runtime)
        self.assertTrue(review.accepted)
        self.assertEqual(review.blocked_count, 0)
        self.assertTrue(all(item.passed for item in audit_release_assurance_review_queue(review, runtime)))
        history = build_release_assurance_history(runtime, review_queue=review)
        self.assertTrue(history.accepted)
        self.assertEqual(history.event_count, 19)
        self.assertTrue(all(item.passed for item in audit_release_assurance_history(history, runtime)))
        self.assertEqual(len(query_release_assurance_history(history, event_type="runtime-stage")), 12)
        self.assertIn(b"event_type", export_release_assurance_history_csv(history))
        self.assertIn(b"# Release assurance history", export_release_assurance_history_markdown(history))
        thresholds = evaluate_release_assurance_thresholds(runtime.snapshot, runtime=runtime)
        self.assertTrue(thresholds.accepted)
        self.assertEqual(thresholds.failed_threshold_ids, ())
        self.assertTrue(all(item.passed for item in audit_release_assurance_thresholds(thresholds, runtime.snapshot)))

    def test_indexes_graph_observability_failure_controls(self) -> None:
        indexes = build_release_assurance_indexes(self.snapshot)
        self.assertTrue(indexes.accepted)
        self.assertTrue(audit_release_assurance_indexes(self.snapshot, indexes).accepted)
        graph = build_release_assurance_graph(self.snapshot)
        self.assertTrue(graph.connected)
        self.assertEqual(graph.to_dict()["node_count"], 53)
        self.assertEqual(graph.to_dict()["edge_count"], 52)
        self.assertTrue(all(item.passed for item in audit_release_assurance_graph(graph, self.snapshot)))
        observability = build_release_assurance_observability(self.snapshot)
        self.assertEqual(observability.event_count, RELEASE_ASSURANCE_EVENT_COUNT)
        self.assertEqual(observability.metric_count, RELEASE_ASSURANCE_METRIC_COUNT)
        self.assertTrue(all(item.passed for item in audit_release_assurance_observability(observability)))
        failures = run_release_assurance_failure_injections(self.snapshot)
        self.assertTrue(failures.accepted)
        self.assertEqual(failures.case_count, RELEASE_ASSURANCE_FAILURE_CASE_COUNT)
        self.assertTrue(all(item.passed for item in audit_release_assurance_failure_injections(failures)))

    def test_plan_views_and_runtime_replay_close(self) -> None:
        plan = build_release_assurance_plan(self.snapshot)
        self.assertEqual(len(plan.steps), RELEASE_ASSURANCE_PLAN_STEP_COUNT)
        self.assertTrue(all(item.passed for item in audit_release_assurance_plan(plan)))
        views = build_release_assurance_views(self.snapshot)
        self.assertEqual(views.to_dict()["view_count"], RELEASE_ASSURANCE_VIEW_COUNT)
        self.assertTrue(all(item.passed for item in audit_release_assurance_views(views, self.snapshot)))
        runtime = run_release_assurance(
            self.service,
            public_audit=self.public_audit,
            run_id="test-runtime-run",
            bundle_id="test-runtime-bundle",
        )
        self.assertTrue(runtime.accepted)
        self.assertEqual(len(runtime.stages), RELEASE_ASSURANCE_RUNTIME_STAGE_TOTAL)
        self.assertEqual(runtime.replay.first_address, runtime.replay.second_address)
        self.assertEqual(runtime.replay.expected_address, runtime.snapshot.content_address)
        self.assertEqual(runtime.to_dict()["failed_stage_ids"], [])

    def test_exact_byte_export_round_trip_and_tamper_detection(self) -> None:
        runtime = run_release_assurance(
            self.service,
            public_audit=self.public_audit,
            run_id="test-export-run",
            bundle_id="test-export-bundle",
        )
        packet = build_release_assurance_export(runtime)
        self.assertTrue(packet.accepted)
        self.assertEqual(len(packet.artifacts), RELEASE_ASSURANCE_EXPORT_ARTIFACT_COUNT)
        with tempfile.TemporaryDirectory() as directory:
            write_release_assurance_export(packet, directory)
            verification = verify_release_assurance_export(directory)
            self.assertTrue(verification.accepted)
            self.assertEqual(verification.checked_artifact_count, RELEASE_ASSURANCE_EXPORT_ARTIFACT_COUNT)
            target = Path(directory) / "runtime" / "release-assurance.json"
            payload = json.loads(target.read_text(encoding="utf-8"))
            payload["accepted"] = False
            target.write_text(json.dumps(payload), encoding="utf-8")
            tampered = verify_release_assurance_export(directory)
            self.assertFalse(tampered.accepted)
            self.assertIn("runtime/release-assurance.json", tampered.tampered_paths)

    def test_http_routes_are_bounded_and_invalid_resources_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server("127.0.0.1", 0, directory)
            server.glio_service_surface = self.service
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=120)
                connection.request("GET", "/v1/release-assurance?bundle_id=http-assurance")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                snapshot = json.loads(response.read())
                self.assertTrue(snapshot["accepted"])
                self.assertEqual(snapshot["domain_count"], 4)
                connection.request("GET", "/v1/release-assurance/query?resource=checks&domain_id=service-release&limit=2")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())["total"], 5)
                connection.request("GET", "/v1/release-assurance/schema")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertTrue(all(item["passed"] for item in json.loads(response.read())["audit"]))
                for route, key in (
                    ("/v1/release-assurance/reconciliation", "report"),
                    ("/v1/release-assurance/catalog", "entry_count"),
                    ("/v1/release-assurance/compliance", "summary"),
                    ("/v1/release-assurance/performance", "status"),
                    ("/v1/release-assurance/operations", "operations"),
                    ("/v1/release-assurance/thresholds", "report"),
                    ("/v1/release-assurance/history?event_type=runtime-stage&limit=2", "history"),
                ):
                    connection.request("GET", route)
                    projection = connection.getresponse()
                    self.assertEqual(projection.status, 200)
                    payload = json.loads(projection.read())
                    self.assertIn(key, payload)
                connection.request("GET", "/v1/release-assurance/query?resource=unknown")
                response = connection.getresponse()
                self.assertEqual(response.status, 422)
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_cli_snapshot_and_schema_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            snapshot_path = str(Path(directory) / "snapshot.json")
            schema_path = str(Path(directory) / "schema.json")
            self.assertEqual(main(["release-assurance", "--plane", "snapshot", "--output", snapshot_path]), 0)
            self.assertEqual(main(["release-assurance", "--plane", "schema", "--output", schema_path]), 0)
            self.assertTrue(json.loads(Path(snapshot_path).read_text(encoding="utf-8"))["accepted"])
            schema_payload = json.loads(Path(schema_path).read_text(encoding="utf-8"))
            self.assertTrue(schema_payload["accepted"])


if __name__ == "__main__":
    unittest.main()
