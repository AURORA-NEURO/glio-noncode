"""Deep contract tests for the D14 evidence-lifecycle closure layer."""

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.evidence_lifecycle_frontier_offline_bundle import (
    build_evidence_lifecycle_offline_bundle,
    write_evidence_lifecycle_offline_bundle,
)
from glio_noncode.evidence_lifecycle_frontier_offline_closure_boundary import (
    audit_evidence_lifecycle_closure_boundary,
)
from glio_noncode.evidence_lifecycle_frontier_offline_closure_certification import (
    certify_evidence_lifecycle_closure,
)
from glio_noncode.evidence_lifecycle_frontier_offline_closure_export import (
    build_evidence_lifecycle_closure_export,
    verify_evidence_lifecycle_closure_export,
    write_evidence_lifecycle_closure_export,
)
from glio_noncode.evidence_lifecycle_frontier_offline_closure_failure_injection import (
    evidence_lifecycle_closure_failure_control_ids,
    inject_evidence_lifecycle_closure_failure,
    run_evidence_lifecycle_closure_failure_injection,
)
from glio_noncode.evidence_lifecycle_frontier_offline_closure_graph import (
    audit_evidence_lifecycle_closure_graph,
    build_evidence_lifecycle_closure_graph,
)
from glio_noncode.evidence_lifecycle_frontier_offline_closure_indexes import (
    audit_evidence_lifecycle_closure_indexes,
    build_evidence_lifecycle_closure_indexes,
    lookup_evidence_lifecycle_closure_index,
)
from glio_noncode.evidence_lifecycle_frontier_offline_closure_observability import (
    audit_evidence_lifecycle_closure_observability,
    build_evidence_lifecycle_closure_observability,
)
from glio_noncode.evidence_lifecycle_frontier_offline_closure_query import (
    query_evidence_lifecycle_closure,
)
from glio_noncode.evidence_lifecycle_frontier_offline_closure_reconciliation import (
    diff_evidence_lifecycle_closure_bundles,
    reconcile_evidence_lifecycle_closure,
)
from glio_noncode.evidence_lifecycle_frontier_offline_closure_runtime import (
    run_evidence_lifecycle_closure_runtime,
)
from glio_noncode.evidence_lifecycle_frontier_offline_closure_schema import (
    evidence_lifecycle_closure_schema,
    validate_evidence_lifecycle_closure_schema,
)
from glio_noncode.evidence_lifecycle_frontier_offline_closure_summary import (
    audit_evidence_lifecycle_closure_summary,
    build_evidence_lifecycle_closure_summary,
)


class EvidenceLifecycleClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = build_evidence_lifecycle_offline_bundle()

    def test_boundary_indexes_and_query_cover_every_resource(self) -> None:
        self.assertTrue(audit_evidence_lifecycle_closure_boundary(self.bundle).accepted)
        indexes = build_evidence_lifecycle_closure_indexes(self.bundle)
        self.assertTrue(indexes.accepted)
        self.assertTrue(audit_evidence_lifecycle_closure_indexes(self.bundle, indexes).accepted)
        self.assertEqual(len(indexes.by_artifact_id), 21)
        self.assertEqual(len({item.key for item in indexes.by_record_id}), 16)
        self.assertEqual(len(indexes.by_check_id), 120)
        self.assertEqual(len(indexes.by_edge_id), 36)
        self.assertEqual(
            len(lookup_evidence_lifecycle_closure_index(indexes, "record_id", "C02-POS-001")), 2
        )
        records = query_evidence_lifecycle_closure(
            self.bundle, resource="records", operation="graph_construction"
        )
        self.assertTrue(records.accepted)
        self.assertEqual(records.total, 4)
        checks = query_evidence_lifecycle_closure(
            self.bundle, resource="checks", state="passed", limit=200
        )
        self.assertTrue(checks.accepted)
        self.assertEqual(checks.total, 120)
        events = query_evidence_lifecycle_closure(
            self.bundle, resource="events", event_type="runtime_stage"
        )
        self.assertEqual(events.total, 10)
        queue = query_evidence_lifecycle_closure(
            self.bundle, resource="queue", disposition="hold_for_repair"
        )
        self.assertEqual(queue.total, 12)

    def test_reconciliation_summary_certification_and_schema(self) -> None:
        reconciliation = reconcile_evidence_lifecycle_closure(self.bundle)
        self.assertTrue(reconciliation.accepted)
        self.assertEqual(reconciliation.passed_count, len(reconciliation.checks))
        summary = build_evidence_lifecycle_closure_summary(self.bundle)
        self.assertTrue(summary.accepted)
        self.assertTrue(audit_evidence_lifecycle_closure_summary(summary).accepted)
        self.assertEqual(summary.counter_map["record_count"], 16)
        self.assertEqual(summary.counter_map["evaluation_check_count"], 120)
        self.assertEqual(summary.counter_map["queue_held_count"], 12)
        certification = certify_evidence_lifecycle_closure(self.bundle)
        self.assertTrue(certification.accepted)
        self.assertEqual(certification.check_count, 48)
        self.assertEqual(certification.passed_check_count, 48)
        self.assertEqual(certification.coverage_percent, 100.0)
        schema = evidence_lifecycle_closure_schema()
        self.assertEqual(schema["version"], "evidence-lifecycle-closure-schema-v1")
        self.assertTrue(validate_evidence_lifecycle_closure_schema(self.bundle).accepted)

    def test_observability_graph_and_failure_controls(self) -> None:
        observability = build_evidence_lifecycle_closure_observability(self.bundle)
        self.assertTrue(observability.accepted)
        self.assertEqual(len(observability.events), 62)
        self.assertEqual(len(observability.metrics), 18)
        self.assertTrue(audit_evidence_lifecycle_closure_observability(observability).accepted)
        graph = build_evidence_lifecycle_closure_graph(self.bundle)
        self.assertTrue(graph.accepted)
        self.assertEqual(graph.connected_component_count, 1)
        self.assertGreater(len(graph.nodes), 300)
        self.assertTrue(audit_evidence_lifecycle_closure_graph(graph).accepted)
        failure = run_evidence_lifecycle_closure_failure_injection(self.bundle)
        self.assertTrue(failure.accepted)
        self.assertEqual(len(failure.probes), 10)
        self.assertEqual(len(evidence_lifecycle_closure_failure_control_ids()), 10)
        self.assertTrue(
            all(
                inject_evidence_lifecycle_closure_failure(control, self.bundle).detected
                for control in evidence_lifecycle_closure_failure_control_ids()
            )
        )

    def test_runtime_is_twelve_stage_and_replay_is_deterministic(self) -> None:
        runtime = run_evidence_lifecycle_closure_runtime(run_id="test-d14-closure-runtime")
        self.assertTrue(runtime.accepted)
        self.assertEqual(len(runtime.stages), 12)
        self.assertTrue(runtime.replay.deterministic)
        self.assertEqual(runtime.certification.coverage_percent, 100.0)
        repeated = run_evidence_lifecycle_closure_runtime(run_id="test-d14-closure-runtime")
        self.assertEqual(runtime.content_address, repeated.content_address)
        self.assertEqual(
            [stage.output_address for stage in runtime.stages],
            [stage.output_address for stage in repeated.stages],
        )

    def test_exact_byte_export_packet_round_trip(self) -> None:
        packet = build_evidence_lifecycle_closure_export(self.bundle)
        self.assertTrue(packet.accepted)
        self.assertEqual(packet.manifest.artifact_count, 12)
        self.assertTrue(
            all(
                item.content_address.startswith("evidence-lifecycle-closure-export:")
                for item in packet.artifacts
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "closure-export"
            write_evidence_lifecycle_closure_export(packet, destination)
            verification = verify_evidence_lifecycle_closure_export(packet, destination)
            self.assertTrue(verification.accepted)
            self.assertEqual(verification.checked_artifact_count, 12)

    def test_cli_and_api_closure_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle_path = root / "bundle"
            write_evidence_lifecycle_offline_bundle(self.bundle, bundle_path)
            output = root / "closure.json"
            self.assertEqual(
                main(
                    [
                        "evidence-lifecycle-offline-bundle-closure-certification",
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
                        "evidence-lifecycle-offline-bundle-closure-query",
                        str(bundle_path),
                        "--resource",
                        "records",
                        "--format",
                        "json",
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
                        "evidence-lifecycle-offline-bundle-closure-export",
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
                        "evidence-lifecycle-offline-bundle-closure-export-verify",
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
                    "/v1/evidence-lifecycle/bundle/closure-schema",
                    "/v1/evidence-lifecycle/bundle/closure-query?resource=records",
                    "/v1/evidence-lifecycle/bundle/closure-certification",
                    "/v1/evidence-lifecycle/bundle/closure-runtime?run_id=api-d14-closure",
                ):
                    connection.request("GET", path)
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200, path)
                    self.assertTrue(
                        json.loads(response.read())["accepted"]
                        if not path.endswith("closure-schema")
                        else True
                    )
            finally:
                server.shutdown()
                thread.join(timeout=10)

    def test_identical_bundles_have_no_closure_delta(self) -> None:
        repeated = build_evidence_lifecycle_offline_bundle()
        delta = diff_evidence_lifecycle_closure_bundles(self.bundle, repeated)
        self.assertTrue(delta.accepted)
        self.assertEqual(delta.changed_artifacts, ())
        self.assertEqual(delta.changed_counts, {})


if __name__ == "__main__":
    unittest.main()
