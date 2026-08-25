"""Regression tests for the deep D13 validation-design closure handoff."""

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.validation_design_frontier_bundle_closure_boundary import (
    closure_public_boundary_inventory,
    validate_validation_design_closure_boundary,
)
from glio_noncode.validation_design_frontier_bundle_closure_certification import (
    certify_validation_design_closure,
    export_validation_design_closure_certification_csv,
    export_validation_design_closure_certification_domains_csv,
)
from glio_noncode.validation_design_frontier_bundle_closure_export import (
    build_validation_design_closure_export,
    verify_validation_design_closure_export,
    write_validation_design_closure_export,
)
from glio_noncode.validation_design_frontier_bundle_closure_failure_injection import (
    export_validation_design_closure_failures_csv,
    rehearse_validation_design_closure_failures,
)
from glio_noncode.validation_design_frontier_bundle_closure_graph import (
    audit_validation_design_closure_graph,
    build_validation_design_closure_graph,
    export_validation_design_closure_graph_csv,
)
from glio_noncode.validation_design_frontier_bundle_closure_indexes import (
    audit_validation_design_closure_indexes,
    build_validation_design_closure_indexes,
    index_lookup,
)
from glio_noncode.validation_design_frontier_bundle_closure_observability import (
    audit_validation_design_closure_observability,
    build_validation_design_closure_observability,
    export_validation_design_closure_events_csv,
    export_validation_design_closure_metrics_csv,
)
from glio_noncode.validation_design_frontier_bundle_closure_query import (
    closure_query_resource_names,
    export_validation_design_closure_csv,
    export_validation_design_closure_markdown,
    query_validation_design_closure,
)
from glio_noncode.validation_design_frontier_bundle_closure_reconciliation import (
    diff_validation_design_closure_bundles,
    reconcile_validation_design_closure,
)
from glio_noncode.validation_design_frontier_bundle_closure_runtime import (
    run_validation_design_closure_runtime,
)
from glio_noncode.validation_design_frontier_bundle_closure_schema import (
    validate_validation_design_closure_projection,
    validation_design_closure_schema,
)
from glio_noncode.validation_design_frontier_bundle_closure_summary import (
    audit_validation_design_closure_summary,
    build_validation_design_closure_summary,
    export_validation_design_closure_summary_csv,
    export_validation_design_closure_summary_markdown,
)
from glio_noncode.validation_design_frontier_offline_bundle import (
    build_validation_design_offline_bundle,
)


class ValidationDesignFrontierBundleClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = build_validation_design_offline_bundle()

    def test_public_boundary_is_independently_closed(self) -> None:
        report = validate_validation_design_closure_boundary(self.bundle)
        self.assertTrue(report.accepted)
        self.assertEqual(report.forbidden_keys, ())
        self.assertEqual(len(report.artifact_checks), 27)
        self.assertTrue(all(item["accepted"] for item in report.artifact_checks))
        self.assertEqual(closure_public_boundary_inventory(self.bundle)["artifact_count"], 27)

    def test_indexes_conserve_every_resource(self) -> None:
        indexes = build_validation_design_closure_indexes(self.bundle)
        audit = audit_validation_design_closure_indexes(self.bundle, indexes)
        self.assertTrue(indexes.accepted)
        self.assertTrue(audit.accepted, audit.failed_check_ids)
        self.assertEqual(indexes.resource_counts["artifacts"], 27)
        self.assertEqual(indexes.resource_counts["records"], 16)
        self.assertEqual(indexes.resource_counts["checks"], 80)
        self.assertEqual(indexes.resource_counts["stages"], 79)
        self.assertEqual(indexes.resource_counts["planes"], 57)
        self.assertEqual(len(index_lookup(indexes, "operation", "gap_analysis")), 4)
        self.assertEqual(len(index_lookup(indexes, "stage_id", "data-audit")), 1)

    def test_reconciliation_and_summary_close_cross_artifact_joins(self) -> None:
        reconciliation = reconcile_validation_design_closure(self.bundle)
        self.assertTrue(reconciliation.accepted, reconciliation.failed_check_ids)
        self.assertEqual(reconciliation.passed_count, 33)
        summary = build_validation_design_closure_summary(self.bundle)
        audit = audit_validation_design_closure_summary(self.bundle, summary)
        self.assertTrue(summary.accepted)
        self.assertTrue(audit.accepted, audit.failed_check_ids)
        self.assertEqual(summary.counter_map["records"], 16)
        self.assertEqual(summary.counter_map["passed_evaluation_checks"], 80)
        self.assertEqual(sum(item.record_count for item in summary.operations), 16)
        self.assertEqual(sum(item.passed_check_count for item in summary.operations), 80)
        self.assertIn(
            "operation", export_validation_design_closure_summary_csv(summary).splitlines()[0]
        )
        self.assertIn(
            "D13 validation-design closure summary",
            export_validation_design_closure_summary_markdown(summary),
        )

    def test_certification_has_eight_domains_and_forty_eight_checks(self) -> None:
        indexes = build_validation_design_closure_indexes(self.bundle)
        index_audit = audit_validation_design_closure_indexes(self.bundle, indexes)
        reconciliation = reconcile_validation_design_closure(self.bundle)
        summary = build_validation_design_closure_summary(self.bundle)
        summary_audit = audit_validation_design_closure_summary(self.bundle, summary)
        report = certify_validation_design_closure(
            self.bundle,
            indexes=indexes,
            index_audit=index_audit,
            reconciliation=reconciliation,
            summary=summary,
            summary_audit=summary_audit,
        )
        self.assertTrue(report.accepted, report.failed_check_ids)
        self.assertEqual(report.check_count, 48)
        self.assertEqual(report.passed_check_count, 48)
        self.assertEqual(report.coverage_percent, 100.0)
        self.assertEqual(len(report.domains), 8)
        self.assertTrue(all(item.accepted for item in report.domains))
        self.assertIn(
            "check_id", export_validation_design_closure_certification_csv(report).splitlines()[0]
        )
        self.assertIn(
            "domain_id",
            export_validation_design_closure_certification_domains_csv(report).splitlines()[0],
        )

    def test_observability_is_stage_complete_and_addressed(self) -> None:
        observability = build_validation_design_closure_observability(self.bundle)
        checks = audit_validation_design_closure_observability(self.bundle, observability)
        self.assertTrue(observability.accepted)
        self.assertEqual(observability.event_count, 158)
        self.assertEqual(observability.metric_count, 18)
        self.assertTrue(all(item.passed for item in checks))
        self.assertEqual(
            len(export_validation_design_closure_events_csv(observability).splitlines()), 159
        )
        self.assertEqual(
            len(export_validation_design_closure_metrics_csv(observability).splitlines()), 19
        )

    def test_all_closure_resources_are_queryable_and_bounded(self) -> None:
        self.assertEqual(
            closure_query_resource_names(),
            (
                "artifacts",
                "checks",
                "executions",
                "issues",
                "operations",
                "planes",
                "records",
                "reviews",
                "sources",
                "stages",
                "states",
            ),
        )
        for resource, expected in (
            ("artifacts", 27),
            ("records", 16),
            ("executions", 16),
            ("checks", 80),
            ("sources", 5),
            ("stages", 79),
            ("planes", 57),
            ("operations", 4),
            ("reviews", 16),
        ):
            result = query_validation_design_closure(self.bundle, resource=resource, limit=500)
            self.assertTrue(result.accepted)
            self.assertEqual(result.total, expected, resource)
            self.assertLessEqual(len(result.items), 500)
        records = query_validation_design_closure(
            self.bundle, resource="records", operation="gap_analysis", limit=2
        )
        self.assertEqual(records.total, 4)
        self.assertEqual(len(records.items), 2)
        self.assertTrue(all(item["operation"] == "gap_analysis" for item in records.items))
        self.assertIn("record_id", export_validation_design_closure_csv(records).splitlines()[0])
        self.assertIn("D13 closure query", export_validation_design_closure_markdown(records))

    def test_schema_and_runtime_report_are_closed(self) -> None:
        schema = validation_design_closure_schema()
        self.assertEqual(schema["$id"], "glio-noncode/validation-design-closure-schema-v1")
        runtime = run_validation_design_closure_runtime()
        self.assertTrue(runtime.accepted)
        self.assertEqual(runtime.state.value, "ready")
        self.assertEqual(len(runtime.stages), 12)
        self.assertEqual(runtime.certification.check_count, 48)
        self.assertTrue(runtime.replay.deterministic)
        projection = runtime.to_dict()
        validation = validate_validation_design_closure_projection(projection)
        self.assertTrue(validation["accepted"], validation)
        self.assertTrue(all(item["state"] == "ready" for item in projection["stages"]))

    def test_closure_diff_is_stable_for_identical_bundles(self) -> None:
        diff = diff_validation_design_closure_bundles(
            self.bundle, build_validation_design_offline_bundle()
        )
        self.assertTrue(diff.accepted)
        self.assertEqual(diff.changed_artifacts, ())
        self.assertEqual(diff.changed_counts, {})

    def test_failure_matrix_catches_ten_negative_controls(self) -> None:
        report = rehearse_validation_design_closure_failures(self.bundle)
        self.assertTrue(report.accepted, report.failed_scenario_ids)
        self.assertEqual(report.probe_count, 10)
        self.assertEqual(report.passed_probe_count, 10)
        self.assertEqual(report.failed_scenario_ids, ())
        self.assertEqual(
            len(export_validation_design_closure_failures_csv(report).splitlines()), 11
        )

    def test_export_packet_is_exact_byte_verifiable(self) -> None:
        runtime = run_validation_design_closure_runtime()
        failures = rehearse_validation_design_closure_failures(runtime.bundle)
        manifest = build_validation_design_closure_export(runtime, failure_report=failures)
        self.assertTrue(manifest.accepted)
        self.assertEqual(manifest.artifact_count, 11)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "closure-export"
            write_validation_design_closure_export(manifest, destination)
            verification = verify_validation_design_closure_export(destination)
            self.assertTrue(verification.accepted, verification.failed_check_ids)
            self.assertEqual(verification.artifact_count, 11)
            (destination / "summary.json").write_text("tampered\n", encoding="utf-8")
            tampered = verify_validation_design_closure_export(destination)
            self.assertFalse(tampered.accepted)
            self.assertIn("bytes:summary", tampered.failed_check_ids)

    def test_relationship_graph_connects_the_complete_closure(self) -> None:
        graph = build_validation_design_closure_graph(self.bundle)
        checks = audit_validation_design_closure_graph(graph)
        self.assertTrue(graph.accepted)
        self.assertEqual(graph.connected_component_count, 1)
        self.assertGreater(graph.node_count, 100)
        self.assertGreater(graph.edge_count, 200)
        self.assertTrue(all(item["passed"] for item in checks), checks)
        self.assertEqual(
            len(export_validation_design_closure_graph_csv(graph).splitlines()),
            graph.edge_count + 1,
        )

    def test_cli_closure_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "bundle"
            self.assertEqual(
                main(["validation-design-frontier-bundle", "--destination", str(destination)]), 0
            )
            for command, filename in (
                ("validation-design-frontier-bundle-closure-boundary", "boundary.json"),
                ("validation-design-frontier-bundle-closure-indexes", "indexes.json"),
                ("validation-design-frontier-bundle-closure-reconciliation", "reconciliation.json"),
                ("validation-design-frontier-bundle-closure-summary", "summary.json"),
                ("validation-design-frontier-bundle-closure-certification", "certification.json"),
                ("validation-design-frontier-bundle-closure-observability", "observability.json"),
            ):
                output = root / filename
                self.assertEqual(
                    main([command, str(destination), "--output", str(output)]), 0, command
                )
                self.assertTrue(json.loads(output.read_text(encoding="utf-8")))
            query_output = root / "query.csv"
            self.assertEqual(
                main(
                    [
                        "validation-design-frontier-bundle-closure-query",
                        str(destination),
                        "--resource",
                        "stages",
                        "--format",
                        "csv",
                        "--output",
                        str(query_output),
                    ]
                ),
                0,
            )
            self.assertIn("stage_id", query_output.read_text(encoding="utf-8").splitlines()[0])
            schema_output = root / "schema.json"
            self.assertEqual(
                main(
                    [
                        "validation-design-frontier-bundle-closure-schema",
                        "--output",
                        str(schema_output),
                    ]
                ),
                0,
            )
            self.assertEqual(
                json.loads(schema_output.read_text(encoding="utf-8"))["$id"],
                "glio-noncode/validation-design-closure-schema-v1",
            )

    def test_http_closure_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = None
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=120)
                for endpoint in (
                    "/closure-schema",
                    "/boundary",
                    "/indexes",
                    "/reconciliation",
                    "/summary",
                    "/certification",
                    "/closure-observability",
                    "/closure-query?resource=records&operation=gap_analysis",
                ):
                    connection.request("GET", f"/v1/validation-design/bundle{endpoint}")
                    response = connection.getresponse()
                    payload = json.loads(response.read())
                    self.assertEqual(response.status, 200, endpoint)
                    if endpoint != "/closure-schema":
                        accepted = payload.get("accepted")
                        if accepted is None:
                            accepted = payload.get("audit", {}).get("accepted")
                        if accepted is None:
                            accepted = payload.get("summary", {}).get("accepted")
                        self.assertTrue(accepted, endpoint)
                connection.close()
                connection = None
            finally:
                if connection is not None:
                    connection.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
