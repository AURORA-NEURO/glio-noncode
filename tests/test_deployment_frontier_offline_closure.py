"""Deep contract tests for the D16 deployment-frontier closure layer."""

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.deployment_frontier_offline_bundle import (
    build_deployment_frontier_offline_bundle,
    write_deployment_frontier_offline_bundle,
)
from glio_noncode.deployment_frontier_offline_closure_boundary import (
    audit_deployment_frontier_closure_boundary,
)
from glio_noncode.deployment_frontier_offline_closure_certification import (
    certify_deployment_frontier_closure,
)
from glio_noncode.deployment_frontier_offline_closure_export import (
    build_deployment_frontier_closure_export,
    verify_deployment_frontier_closure_export,
    write_deployment_frontier_closure_export,
)
from glio_noncode.deployment_frontier_offline_closure_failure_injection import (
    audit_deployment_frontier_closure_failure_report,
    build_deployment_frontier_closure_failure_report,
)
from glio_noncode.deployment_frontier_offline_closure_graph import (
    audit_deployment_frontier_closure_graph,
    build_deployment_frontier_closure_graph,
)
from glio_noncode.deployment_frontier_offline_closure_indexes import (
    audit_deployment_frontier_closure_indexes,
    build_deployment_frontier_closure_indexes,
    lookup_deployment_frontier_closure_index,
)
from glio_noncode.deployment_frontier_offline_closure_observability import (
    audit_deployment_frontier_closure_observability,
    build_deployment_frontier_closure_observability,
)
from glio_noncode.deployment_frontier_offline_closure_query import (
    query_deployment_frontier_closure,
)
from glio_noncode.deployment_frontier_offline_closure_reconciliation import (
    diff_deployment_frontier_closure_bundles,
    reconcile_deployment_frontier_closure,
)
from glio_noncode.deployment_frontier_offline_closure_runtime import (
    run_deployment_frontier_closure_runtime,
)
from glio_noncode.deployment_frontier_offline_closure_schema import (
    audit_deployment_frontier_closure_schema,
    build_deployment_frontier_closure_schema,
)
from glio_noncode.deployment_frontier_offline_closure_summary import (
    audit_deployment_frontier_closure_summary,
    build_deployment_frontier_closure_summary,
)


class DeploymentFrontierClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = build_deployment_frontier_offline_bundle()

    def test_boundary_indexes_and_queries_conserve_the_full_projection(self) -> None:
        self.assertTrue(audit_deployment_frontier_closure_boundary(self.bundle).accepted)
        indexes = build_deployment_frontier_closure_indexes(self.bundle)
        self.assertTrue(indexes.accepted)
        self.assertTrue(audit_deployment_frontier_closure_indexes(self.bundle, indexes).accepted)
        self.assertEqual(len(indexes.by_artifact_id), 51)
        self.assertEqual(len({item.key for item in indexes.by_record_id}), 16)
        self.assertEqual(len(indexes.by_check_id), 80)
        self.assertEqual(len(indexes.by_edge_id), 52)
        self.assertEqual(
            len(lookup_deployment_frontier_closure_index(indexes, "record_id", "C13-POS-001")),
            4,
        )
        records = query_deployment_frontier_closure(
            self.bundle,
            resource="records",
            filters={"operation": "privacy_security_policy"},
        )
        self.assertTrue(records.accepted)
        self.assertEqual(records.total, 4)
        checks = query_deployment_frontier_closure(
            self.bundle, resource="checks", state="passed", limit=200
        )
        self.assertEqual(checks.total, 80)
        queue = query_deployment_frontier_closure(
            self.bundle, resource="queue", filters={"priority": "80"}
        )
        self.assertEqual(queue.total, 11)

    def test_reconciliation_summary_certification_and_schema_are_closed(self) -> None:
        reconciliation = reconcile_deployment_frontier_closure(self.bundle)
        self.assertTrue(reconciliation.accepted)
        self.assertEqual(reconciliation.passed_count, len(reconciliation.checks))
        summary = build_deployment_frontier_closure_summary(self.bundle)
        self.assertTrue(summary.accepted)
        self.assertTrue(audit_deployment_frontier_closure_summary(summary).accepted)
        self.assertEqual(summary.counter_map["record_count"], 16)
        self.assertEqual(summary.counter_map["evaluation_check_count"], 80)
        self.assertEqual(summary.counter_map["queue_count"], 12)
        certification = certify_deployment_frontier_closure(self.bundle)
        self.assertTrue(certification.accepted)
        self.assertEqual(certification.check_count, 60)
        self.assertEqual(certification.passed_check_count, 60)
        self.assertEqual(certification.coverage_percent, 100.0)
        schema = build_deployment_frontier_closure_schema()
        self.assertEqual(schema["version"], "deployment-frontier-closure-schema-v1")
        self.assertTrue(
            all(
                item.passed
                for item in audit_deployment_frontier_closure_schema(self.bundle, schema)
            )
        )

    def test_observability_graph_and_negative_controls_are_deep(self) -> None:
        observability = build_deployment_frontier_closure_observability(self.bundle)
        self.assertTrue(observability.accepted)
        self.assertEqual(len(observability.events), 151)
        self.assertEqual(len(observability.metrics), 24)
        self.assertTrue(
            all(
                item.passed
                for item in audit_deployment_frontier_closure_observability(observability)
            )
        )
        graph = build_deployment_frontier_closure_graph(self.bundle)
        self.assertTrue(graph.accepted)
        self.assertEqual(graph.connected_component_count, 1)
        self.assertEqual(len(graph.nodes), 599)
        self.assertEqual(len(graph.edges), 866)
        self.assertTrue(all(item.passed for item in audit_deployment_frontier_closure_graph(graph)))
        failure = build_deployment_frontier_closure_failure_report(self.bundle)
        self.assertTrue(failure.accepted)
        self.assertEqual(len(failure.cases), 12)
        self.assertTrue(
            all(item.passed for item in audit_deployment_frontier_closure_failure_report(failure))
        )

    def test_runtime_has_fourteen_stages_and_deterministic_replay(self) -> None:
        runtime = run_deployment_frontier_closure_runtime(run_id="test-d16-closure-runtime")
        self.assertTrue(runtime.accepted)
        self.assertEqual(len(runtime.stages), 14)
        self.assertTrue(runtime.replay.deterministic)
        self.assertEqual(runtime.certification.coverage_percent, 100.0)
        repeated = run_deployment_frontier_closure_runtime(run_id="test-d16-closure-runtime")
        self.assertEqual(runtime.content_address, repeated.content_address)
        self.assertEqual(
            [stage.output_address for stage in runtime.stages],
            [stage.output_address for stage in repeated.stages],
        )

    def test_exact_byte_export_packet_round_trip(self) -> None:
        packet = build_deployment_frontier_closure_export(self.bundle)
        self.assertTrue(packet.accepted)
        self.assertEqual(packet.manifest.artifact_count, 14)
        self.assertTrue(
            all(
                item.content_address.startswith("deployment-frontier-closure-export:")
                for item in packet.artifacts
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "closure-export"
            write_deployment_frontier_closure_export(packet, destination)
            verification = verify_deployment_frontier_closure_export(packet, destination)
            self.assertTrue(verification.accepted)
            self.assertEqual(verification.checked_artifact_count, 14)

    def test_cli_and_api_closure_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle_path = root / "bundle"
            write_deployment_frontier_offline_bundle(self.bundle, bundle_path)
            output = root / "closure.json"
            self.assertEqual(
                main(
                    [
                        "deployment-frontier-offline-bundle-closure-certification",
                        str(bundle_path),
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8"))["coverage_percent"], 100.0
            )
            self.assertEqual(
                main(
                    [
                        "deployment-frontier-offline-bundle-closure-query",
                        str(bundle_path),
                        "--resource",
                        "records",
                        "--output",
                        str(root / "query.json"),
                    ]
                ),
                0,
            )
            export_path = root / "export"
            self.assertEqual(
                main(
                    [
                        "deployment-frontier-offline-bundle-closure-export",
                        "--destination",
                        str(export_path),
                        "--output",
                        str(root / "export.json"),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "deployment-frontier-offline-bundle-closure-export-verify",
                        str(export_path),
                        "--output",
                        str(root / "verify.json"),
                    ]
                ),
                0,
            )
            server = create_server("127.0.0.1", 0, root)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=120)
                for path in (
                    "/v1/deployment-frontier/bundle/closure-schema",
                    "/v1/deployment-frontier/bundle/closure-query?resource=records",
                    "/v1/deployment-frontier/bundle/closure-certification",
                    "/v1/deployment-frontier/bundle/closure-runtime?run_id=api-d16-closure",
                ):
                    connection.request("GET", path)
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200, path)
                    body = json.loads(response.read())
                    self.assertTrue(body.get("accepted", True))
            finally:
                connection.close()
                server.shutdown()
                thread.join(timeout=10)
                server.server_close()

    def test_identical_bundles_have_no_closure_delta(self) -> None:
        repeated = build_deployment_frontier_offline_bundle()
        delta = diff_deployment_frontier_closure_bundles(self.bundle, repeated)
        self.assertTrue(delta.accepted)
        self.assertEqual(delta.changed_artifacts, ())
        self.assertEqual(delta.changed_counts, {})


if __name__ == "__main__":
    unittest.main()
