"""Deep contract tests for the aggregate D13-D16 frontier release closure."""

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.frontier_release_closure_boundary import audit_frontier_release_boundary
from glio_noncode.frontier_release_closure_bundle import (
    build_frontier_release_snapshot,
    frontier_release_snapshot_counts,
)
from glio_noncode.frontier_release_closure_certification import certify_frontier_release
from glio_noncode.frontier_release_closure_export import (
    build_frontier_release_export,
    verify_frontier_release_export,
    write_frontier_release_export,
)
from glio_noncode.frontier_release_closure_failure_injection import (
    audit_frontier_release_failure_report,
    build_frontier_release_failure_report,
)
from glio_noncode.frontier_release_closure_graph import (
    audit_frontier_release_graph,
    build_frontier_release_graph,
)
from glio_noncode.frontier_release_closure_indexes import (
    audit_frontier_release_indexes,
    build_frontier_release_indexes,
    lookup_frontier_release_index,
)
from glio_noncode.frontier_release_closure_observability import (
    audit_frontier_release_observability,
    build_frontier_release_observability,
)
from glio_noncode.frontier_release_closure_plan import (
    audit_frontier_release_plan,
    build_frontier_release_plan,
)
from glio_noncode.frontier_release_closure_query import query_frontier_release
from glio_noncode.frontier_release_closure_reconciliation import (
    diff_frontier_release_snapshots,
    reconcile_frontier_release,
)
from glio_noncode.frontier_release_closure_runtime import (
    run_frontier_release_closure_runtime,
)
from glio_noncode.frontier_release_closure_schema import (
    audit_frontier_release_schema,
    build_frontier_release_schema,
)
from glio_noncode.frontier_release_closure_summary import (
    audit_frontier_release_summary,
    build_frontier_release_summary,
)
from glio_noncode.frontier_release_closure_support import forbidden_keys


class FrontierReleaseClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = build_frontier_release_snapshot(run_id="test-frontier-release-closure")

    def test_snapshot_conserves_all_four_source_domains(self) -> None:
        self.assertTrue(self.snapshot.accepted)
        self.assertEqual(
            frontier_release_snapshot_counts(self.snapshot),
            {
                "domain_count": 4,
                "artifact_count": 155,
                "dependency_count": 6,
                "gate_count": 24,
                "accepted_domain_count": 4,
                "passed_gate_count": 24,
                "source_count": 20,
                "record_count": 64,
                "evaluation_check_count": 360,
                "closure_stage_count": 52,
                "certification_check_count": 216,
                "reconciliation_check_count": 158,
                "graph_node_count": 1359,
                "graph_edge_count": 2239,
            },
        )
        self.assertEqual(
            tuple(item.domain_id for item in self.snapshot.domains), ("D13", "D14", "D15", "D16")
        )
        self.assertEqual(len({item.artifact_ref for item in self.snapshot.artifacts}), 155)
        self.assertEqual(len({item.gate_id for item in self.snapshot.gates}), 24)
        self.assertEqual(len({item.dependency_id for item in self.snapshot.dependencies}), 6)
        self.assertEqual(forbidden_keys(self.snapshot.to_dict()), ())

    def test_boundary_and_index_planes_preserve_address_identity(self) -> None:
        boundary = audit_frontier_release_boundary(self.snapshot)
        self.assertTrue(boundary.accepted)
        self.assertEqual(len(boundary.checks), 13)
        self.assertEqual(boundary.forbidden_keys, ())
        indexes = build_frontier_release_indexes(self.snapshot)
        self.assertTrue(indexes.accepted)
        audit = audit_frontier_release_indexes(self.snapshot, indexes)
        self.assertTrue(audit.accepted)
        self.assertEqual(len(audit.checks), 22)
        self.assertEqual(len(indexes.by_artifact_ref), 155)
        self.assertEqual(len(indexes.by_content_address), 193)
        self.assertEqual(len(lookup_frontier_release_index(indexes, "by_domain_id", "D13")), 1)
        artifact_key = self.snapshot.artifacts[0].artifact_ref
        self.assertEqual(
            len(lookup_frontier_release_index(indexes, "by_artifact_ref", artifact_key)), 1
        )

    def test_query_plane_supports_domains_artifacts_gates_and_runtime(self) -> None:
        domains = query_frontier_release(self.snapshot, resource="domains")
        self.assertTrue(domains.accepted)
        self.assertEqual(domains.total, 4)
        artifacts = query_frontier_release(
            self.snapshot,
            resource="artifacts",
            domain_id="D14",
            limit=200,
        )
        self.assertEqual(artifacts.total, 21)
        gates = query_frontier_release(
            self.snapshot,
            resource="gates",
            gate_type="certification_coverage",
            state="passed",
        )
        self.assertEqual(gates.total, 4)
        runtime = query_frontier_release(self.snapshot, resource="runtime", domain_id="D16")
        self.assertEqual(runtime.total, 1)
        dependencies = query_frontier_release(
            self.snapshot,
            resource="dependencies",
            relation="release_precedes",
        )
        self.assertEqual(dependencies.total, 6)

    def test_reconciliation_summary_certification_and_schema_close(self) -> None:
        reconciliation = reconcile_frontier_release(self.snapshot)
        self.assertTrue(reconciliation.accepted)
        self.assertEqual(reconciliation.passed_count, len(reconciliation.checks))
        self.assertEqual(len(reconciliation.checks), 35)
        summary = build_frontier_release_summary(self.snapshot)
        self.assertTrue(summary.accepted)
        summary_audit = audit_frontier_release_summary(summary)
        self.assertTrue(summary_audit.accepted)
        self.assertEqual(len(summary_audit.checks), 20)
        self.assertEqual(summary.counter_map["artifact_count"], 155)
        self.assertEqual(summary.counter_map["source_count"], 20)
        certification = certify_frontier_release(self.snapshot)
        self.assertTrue(certification.accepted)
        self.assertEqual(certification.check_count, 48)
        self.assertEqual(certification.passed_check_count, 48)
        self.assertEqual(certification.coverage_percent, 100.0)
        schema = build_frontier_release_schema()
        self.assertEqual(schema["version"], "frontier-release-schema-v1")
        schema_checks = audit_frontier_release_schema(self.snapshot, schema)
        self.assertEqual(len(schema_checks), 11)
        self.assertTrue(all(item.passed for item in schema_checks))

    def test_observability_graph_and_negative_controls_are_deep(self) -> None:
        observability = build_frontier_release_observability(self.snapshot)
        self.assertTrue(observability.accepted)
        self.assertEqual(len(observability.events), 193)
        self.assertEqual(len(observability.metrics), 24)
        self.assertTrue(
            all(item.passed for item in audit_frontier_release_observability(observability))
        )
        graph = build_frontier_release_graph(self.snapshot)
        self.assertTrue(graph.accepted)
        self.assertEqual(graph.connected_component_count, 1)
        self.assertEqual(len(graph.nodes), 189)
        self.assertEqual(len(graph.edges), 191)
        self.assertTrue(all(item.passed for item in audit_frontier_release_graph(graph)))
        failures = build_frontier_release_failure_report(self.snapshot)
        self.assertTrue(failures.accepted)
        self.assertEqual(len(failures.cases), 12)
        self.assertTrue(
            all(item.passed for item in audit_frontier_release_failure_report(failures))
        )

    def test_ordered_plan_is_addressed_and_replayable(self) -> None:
        plan = build_frontier_release_plan(self.snapshot)
        self.assertTrue(plan.accepted)
        self.assertEqual(len(plan.steps), 13)
        self.assertEqual(tuple(item.ordinal for item in plan.steps), tuple(range(1, 14)))
        self.assertEqual(plan.steps[0].domain_id, "D13")
        self.assertEqual(plan.steps[-1].step_id, "publish-release")
        plan_audit = audit_frontier_release_plan(plan)
        self.assertEqual(len(plan_audit), 6)
        self.assertTrue(all(item["passed"] for item in plan_audit))
        self.assertEqual(
            plan.content_address, build_frontier_release_plan(self.snapshot).content_address
        )

    def test_runtime_has_twelve_stages_and_deterministic_replay(self) -> None:
        runtime = run_frontier_release_closure_runtime(run_id="test-frontier-release-runtime")
        self.assertTrue(runtime.accepted)
        self.assertEqual(len(runtime.stages), 12)
        self.assertTrue(runtime.replay.deterministic)
        self.assertTrue(runtime.plan.accepted)
        self.assertEqual(len(runtime.plan_audit), 6)
        self.assertEqual(runtime.certification.coverage_percent, 100.0)
        repeated = run_frontier_release_closure_runtime(run_id="test-frontier-release-runtime")
        self.assertEqual(runtime.content_address, repeated.content_address)
        self.assertEqual(
            [stage.output_address for stage in runtime.stages],
            [stage.output_address for stage in repeated.stages],
        )

    def test_exact_byte_export_packet_round_trip(self) -> None:
        runtime = run_frontier_release_closure_runtime(run_id="test-frontier-release-export")
        packet = build_frontier_release_export(runtime)
        self.assertTrue(packet.accepted)
        self.assertEqual(packet.manifest.artifact_count, 13)
        self.assertIn("plan.json", {item.relative_path for item in packet.artifacts})
        self.assertTrue(
            all(
                item.content_address.startswith("frontier-release-export:")
                for item in packet.artifacts
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "frontier-release-export"
            write_frontier_release_export(packet, destination)
            verification = verify_frontier_release_export(packet, destination)
            self.assertTrue(verification.accepted)
            self.assertEqual(verification.checked_artifact_count, 13)

    def test_cli_surfaces_emit_json_and_exact_byte_export(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime_output = root / "runtime.json"
            self.assertEqual(
                main(
                    [
                        "frontier-release-closure-runtime",
                        "--run-id",
                        "cli-frontier-release",
                        "--output",
                        str(runtime_output),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(runtime_output.read_text(encoding="utf-8"))["accepted"])
            query_output = root / "query.json"
            self.assertEqual(
                main(
                    [
                        "frontier-release-closure-query",
                        "--resource",
                        "artifacts",
                        "--domain-id",
                        "D15",
                        "--output",
                        str(query_output),
                    ]
                ),
                0,
            )
            self.assertEqual(json.loads(query_output.read_text(encoding="utf-8"))["total"], 56)
            export_root = root / "export"
            self.assertEqual(
                main(
                    [
                        "frontier-release-closure-export",
                        "--destination",
                        str(export_root),
                        "--output",
                        str(root / "export.json"),
                    ]
                ),
                0,
            )
            verify_output = root / "verify.json"
            self.assertEqual(
                main(
                    [
                        "frontier-release-closure-export-verify",
                        str(export_root),
                        "--output",
                        str(verify_output),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(verify_output.read_text(encoding="utf-8"))["accepted"])

    def test_api_surfaces_expose_schema_query_certification_plan_and_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server("127.0.0.1", 0, Path(directory))
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = None
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=120)
                paths = (
                    "/v1/frontier-release/closure/schema",
                    "/v1/frontier-release/closure/query?resource=artifacts&domain_id=D13",
                    "/v1/frontier-release/closure/certification",
                    "/v1/frontier-release/closure/plan",
                    "/v1/frontier-release/closure/runtime?run_id=api-frontier-release",
                )
                for path in paths:
                    connection.request("GET", path)
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200, path)
                    body = json.loads(response.read())
                    if path.endswith("/schema"):
                        self.assertTrue(all(item["passed"] for item in body["schema_audit"]))
                    elif "/query?" in path:
                        self.assertEqual(body["total"], 27)
                    elif path.endswith("/certification"):
                        self.assertEqual(body["coverage_percent"], 100.0)
                    elif path.endswith("/plan"):
                        self.assertTrue(body["plan"]["accepted"])
                    else:
                        self.assertTrue(body["accepted"])
            finally:
                if connection is not None:
                    connection.close()
                server.shutdown()
                thread.join(timeout=10)
                server.server_close()

    def test_identical_snapshots_have_no_release_delta(self) -> None:
        repeated = build_frontier_release_snapshot(run_id="test-frontier-release-closure")
        delta = diff_frontier_release_snapshots(self.snapshot, repeated)
        self.assertTrue(delta.accepted)
        self.assertEqual(delta.changed_domains, ())
        self.assertEqual(delta.changed_artifacts, ())
        self.assertEqual(delta.changed_gates, ())


if __name__ == "__main__":
    unittest.main()
