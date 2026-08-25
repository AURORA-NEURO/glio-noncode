"""Deep contract tests for the D01-D16 public aggregate release closure."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.request import urlopen

from glio_noncode.api import create_server
from glio_noncode.program_release_closure_boundary import (
    audit_program_release_closure_boundary,
    validate_program_release_closure_boundary,
)
from glio_noncode.program_release_closure_bundle import (
    build_program_release_snapshot,
    program_release_snapshot_counts,
)
from glio_noncode.program_release_closure_certification import (
    audit_program_release_certification,
    certify_program_release_closure,
)
from glio_noncode.program_release_closure_contracts import (
    PROGRAM_RELEASE_CLOSURE_ARTIFACT_COUNT,
    PROGRAM_RELEASE_CLOSURE_CERTIFICATION_CHECK_COUNT,
    PROGRAM_RELEASE_CLOSURE_DEPENDENCY_COUNT,
    PROGRAM_RELEASE_CLOSURE_DOMAIN_COUNT,
    PROGRAM_RELEASE_CLOSURE_GATE_COUNT,
    PROGRAM_RELEASE_CLOSURE_OBSERVABILITY_EVENT_COUNT,
    PROGRAM_RELEASE_CLOSURE_OBSERVABILITY_METRIC_COUNT,
    PROGRAM_RELEASE_CLOSURE_RUNTIME_STAGE_TOTAL,
    ProgramReleaseClosureState,
)
from glio_noncode.program_release_closure_export import (
    build_program_release_export,
    verify_program_release_export,
    verify_program_release_export_directory,
    write_program_release_export,
)
from glio_noncode.program_release_closure_failure_injection import (
    audit_program_release_failure_injections,
    run_program_release_failure_injections,
)
from glio_noncode.program_release_closure_graph import (
    audit_program_release_graph,
    build_program_release_graph,
)
from glio_noncode.program_release_closure_indexes import (
    audit_program_release_closure_indexes,
    build_program_release_closure_indexes,
    lookup_program_release_index,
)
from glio_noncode.program_release_closure_observability import (
    audit_program_release_observability,
    build_program_release_observability,
)
from glio_noncode.program_release_closure_operations import (
    audit_program_release_operational_matrix,
    build_program_release_operational_matrix,
    program_release_operational_rows,
    render_program_release_operational_markdown,
)
from glio_noncode.program_release_closure_plan import (
    audit_program_release_closure_plan,
    build_program_release_closure_plan,
)
from glio_noncode.program_release_closure_query import query_program_release_closure
from glio_noncode.program_release_closure_reconciliation import (
    diff_program_release_closures,
    reconcile_program_release_closure,
)
from glio_noncode.program_release_closure_runtime import run_program_release_closure
from glio_noncode.program_release_closure_schema import (
    program_release_closure_schema,
    validate_program_release_closure_schema,
)
from glio_noncode.program_release_closure_summary import (
    audit_program_release_closure_summary,
    build_program_release_closure_summary,
)
from glio_noncode.program_release_closure_support import (
    artifact_address,
    forbidden_keys,
    safe_relative_path,
)
from glio_noncode.program_release_closure_views import (
    audit_program_release_review_views,
    build_program_release_review_views,
    render_program_release_review_views,
)
from glio_noncode.program_runtime_offline_bundle import build_program_runtime_offline_bundle


class ProgramReleaseClosureTest(unittest.TestCase):
    """Reuse one source build so the suite exercises the same optimization as the API."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = build_program_runtime_offline_bundle(
            bundle_id="test-program-release-source",
            run_id="test-program-release-source",
        )
        cls.snapshot = build_program_release_snapshot(
            cls.source,
            bundle_id="test-program-release-closure",
            run_id="test-program-release-closure",
        )

    def test_source_handoff_is_accepted_and_reused(self) -> None:
        self.assertTrue(self.source.ready)
        self.assertEqual(self.source.artifact_count, 18)
        self.assertEqual(self.source.passed_check_count, 31)
        second = build_program_release_snapshot(
            self.source,
            bundle_id=self.snapshot.bundle_id,
            run_id=self.snapshot.run_id,
        )
        self.assertEqual(second.content_address, self.snapshot.content_address)
        self.assertEqual(second.source_bundle_address, self.snapshot.source_bundle_address)

    def test_snapshot_conserves_all_aggregate_denominators(self) -> None:
        counts = program_release_snapshot_counts(self.snapshot)
        self.assertEqual(counts["domain_count"], PROGRAM_RELEASE_CLOSURE_DOMAIN_COUNT)
        self.assertEqual(counts["artifact_count"], PROGRAM_RELEASE_CLOSURE_ARTIFACT_COUNT)
        self.assertEqual(counts["dependency_count"], PROGRAM_RELEASE_CLOSURE_DEPENDENCY_COUNT)
        self.assertEqual(counts["gate_count"], PROGRAM_RELEASE_CLOSURE_GATE_COUNT)
        self.assertEqual(counts["accepted_domain_count"], PROGRAM_RELEASE_CLOSURE_DOMAIN_COUNT)
        self.assertEqual(counts["passed_gate_count"], PROGRAM_RELEASE_CLOSURE_GATE_COUNT)
        self.assertTrue(counts["accepted"])

    def test_snapshot_domain_order_and_contributions(self) -> None:
        self.assertEqual(
            tuple(item.domain_id for item in self.snapshot.domains),
            tuple(f"D{index:02d}" for index in range(1, 17)),
        )
        self.assertEqual(sum(item.source_artifact_count for item in self.snapshot.domains), 98)
        self.assertEqual(sum(item.evaluation_check_count for item in self.snapshot.domains), 7178)
        self.assertEqual(sum(item.stage_count for item in self.snapshot.domains), 380)
        self.assertTrue(all(item.source_runtime_address for item in self.snapshot.domains))
        self.assertTrue(all(item.source_receipt_address for item in self.snapshot.domains))

    def test_snapshot_dependency_matrix_is_complete_dag(self) -> None:
        self.assertEqual(len(self.snapshot.dependencies), 120)
        pairs = {
            (item.source_domain_id, item.target_domain_id) for item in self.snapshot.dependencies
        }
        self.assertEqual(len(pairs), 120)
        self.assertTrue(
            all(item.source_order < item.target_order for item in self.snapshot.dependencies)
        )
        self.assertEqual(self.snapshot.dependencies[0].source_domain_id, "D01")
        self.assertEqual(self.snapshot.dependencies[-1].target_domain_id, "D16")

    def test_snapshot_has_six_passed_gates_per_domain(self) -> None:
        self.assertEqual(len(self.snapshot.gates), 96)
        for domain_id in (f"D{index:02d}" for index in range(1, 17)):
            gates = tuple(item for item in self.snapshot.gates if item.domain_id == domain_id)
            self.assertEqual(len(gates), 6)
            self.assertEqual(
                tuple(item.gate_type for item in gates),
                (
                    "bundle_accepted",
                    "runtime_address",
                    "runtime_depth",
                    "evaluation_checks",
                    "artifact_contribution",
                    "public_projection",
                ),
            )
            self.assertTrue(all(item.passed for item in gates))

    def test_boundary_receipts(self) -> None:
        checks = audit_program_release_closure_boundary(self.snapshot)
        self.assertEqual(len(checks), 20)
        self.assertTrue(all(item.passed for item in checks))
        report = validate_program_release_closure_boundary(self.snapshot)
        self.assertTrue(report["accepted"])
        self.assertEqual(report["boundary"], self.snapshot.boundary)
        self.assertEqual(report["bundle_id"], self.snapshot.bundle_id)

    def test_schema_contract(self) -> None:
        schema = program_release_closure_schema()
        self.assertEqual(schema["resources"]["domains"], 16)
        self.assertEqual(schema["resources"]["artifacts"], 18)
        self.assertEqual(schema["resources"]["dependencies"], 120)
        self.assertEqual(schema["resources"]["gates"], 96)
        report = validate_program_release_closure_schema(self.snapshot, schema)
        self.assertTrue(report["accepted"])
        self.assertTrue(all(report["checks"].values()))

    def test_indexes_and_lookup(self) -> None:
        indexes = build_program_release_closure_indexes(self.snapshot)
        audit = audit_program_release_closure_indexes(self.snapshot, indexes)
        self.assertTrue(indexes.accepted)
        self.assertTrue(audit.accepted)
        self.assertEqual(len(indexes.by_domain_id), 16)
        self.assertEqual(len(indexes.by_artifact_ref), 18)
        self.assertEqual(len(indexes.by_dependency_id), 120)
        self.assertEqual(len(indexes.by_gate_id), 96)
        self.assertEqual(len(lookup_program_release_index(indexes, "by_domain_id", "D01")), 1)
        self.assertEqual(
            len(lookup_program_release_index(indexes, "by_gate_id", "gate:D01:runtime_depth")), 1
        )
        self.assertEqual(len(lookup_program_release_index(indexes, "by_domain_id", "missing")), 0)

    def test_bounded_queries_cover_each_resource(self) -> None:
        domains = query_program_release_closure(self.snapshot, resource="domains", limit=4)
        self.assertTrue(domains.accepted)
        self.assertEqual(domains.total, 16)
        self.assertEqual(len(domains.items), 4)
        self.assertEqual(domains.items[0]["domain_id"], "D01")
        gates = query_program_release_closure(
            self.snapshot,
            resource="gates",
            domain_id="D01",
            gate_type="runtime_depth",
            accepted_only=True,
        )
        self.assertEqual(gates.total, 1)
        self.assertEqual(gates.items[0]["observed"], 24)
        dependencies = query_program_release_closure(
            self.snapshot,
            resource="dependencies",
            relation="release_precedes",
            domain_id="D01",
            limit=50,
        )
        self.assertEqual(dependencies.total, 15)
        runtime = query_program_release_closure(self.snapshot, resource="runtime")
        self.assertEqual(runtime.total, 1)

    def test_query_text_and_pagination(self) -> None:
        result = query_program_release_closure(
            self.snapshot, resource="domains", text="Intake", offset=0, limit=50
        )
        self.assertEqual(result.total, 1)
        self.assertEqual(result.items[0]["domain_id"], "D01")
        page = query_program_release_closure(self.snapshot, resource="artifacts", offset=2, limit=3)
        self.assertEqual(page.total, 18)
        self.assertEqual(len(page.items), 3)
        with self.assertRaises(Exception):
            query_program_release_closure(self.snapshot, resource="not-a-resource")
        with self.assertRaises(Exception):
            query_program_release_closure(self.snapshot, offset=-1)

    def test_reconciliation_conserves_source_program_counts(self) -> None:
        report = reconcile_program_release_closure(self.snapshot, self.source)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 19)
        self.assertEqual(report.passed_count, 19)
        self.assertEqual(report.failed_check_ids, ())

    def test_summary_has_source_and_aggregate_counters(self) -> None:
        summary = build_program_release_closure_summary(self.snapshot, self.source)
        audit = audit_program_release_closure_summary(summary, self.source)
        self.assertTrue(summary.accepted)
        self.assertTrue(audit.accepted)
        counters = summary.counter_map
        expected = {
            "domain_count": 16,
            "artifact_count": 18,
            "dependency_count": 120,
            "gate_count": 96,
            "program_check_count": 172,
            "quality_check_count": 18,
            "source_runtime_stage_count": 12,
            "release_artifact_count": 11,
            "domain_artifact_total": 98,
            "evaluation_check_total": 7178,
            "stage_total": 380,
        }
        for key, value in expected.items():
            self.assertEqual(counters[key], value, key)

    def test_certification_matrix_is_ninety_six_checks(self) -> None:
        certification = certify_program_release_closure(self.snapshot)
        self.assertTrue(certification.accepted)
        self.assertEqual(
            certification.check_count, PROGRAM_RELEASE_CLOSURE_CERTIFICATION_CHECK_COUNT
        )
        self.assertEqual(certification.passed_check_count, 96)
        self.assertEqual(certification.coverage_percent, 100.0)
        self.assertTrue(
            all(
                len(tuple(item for item in certification.checks if item.domain_id == domain_id))
                == 6
                for domain_id in {item.domain_id for item in certification.checks}
            )
        )
        audit = audit_program_release_certification(certification, self.snapshot)
        self.assertTrue(audit["accepted"])

    def test_observability_denominators_and_audit(self) -> None:
        report = build_program_release_observability(self.snapshot)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.events), PROGRAM_RELEASE_CLOSURE_OBSERVABILITY_EVENT_COUNT)
        self.assertEqual(len(report.metrics), PROGRAM_RELEASE_CLOSURE_OBSERVABILITY_METRIC_COUNT)
        self.assertEqual(tuple(item.sequence for item in report.events), tuple(range(1, 267)))
        self.assertTrue(audit_program_release_observability(report)["accepted"])
        self.assertEqual(sum(item.name == "runtime_stage_count" for item in report.metrics), 16)

    def test_graph_is_connected_and_partitioned(self) -> None:
        graph = build_program_release_graph(self.snapshot)
        audit = audit_program_release_graph(graph, self.snapshot)
        self.assertTrue(graph.accepted)
        self.assertEqual(graph.connected_component_count, 1)
        self.assertEqual(len(graph.nodes), 251)
        self.assertTrue(audit["accepted"])
        self.assertEqual(sum(item.node_type == "domain" for item in graph.nodes), 16)
        self.assertEqual(sum(item.node_type == "artifact" for item in graph.nodes), 18)
        self.assertEqual(sum(item.node_type == "dependency" for item in graph.nodes), 120)
        self.assertEqual(sum(item.node_type == "gate" for item in graph.nodes), 96)

    def test_failure_controls_reject_twelve_mutations(self) -> None:
        report = run_program_release_failure_injections(self.snapshot)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.cases), 12)
        self.assertTrue(
            all(
                item.expected_rejection and item.observed_rejection and item.accepted
                for item in report.cases
            )
        )
        self.assertTrue(audit_program_release_failure_injections(report)["accepted"])

    def test_plan_is_contiguous_and_executable(self) -> None:
        plan = build_program_release_closure_plan(self.snapshot)
        self.assertTrue(plan.accepted)
        self.assertEqual(len(plan.steps), 23)
        self.assertEqual(tuple(item.ordinal for item in plan.steps), tuple(range(1, 24)))
        self.assertTrue(all(item.output_address for item in plan.steps))
        self.assertTrue(all(item.passed for item in audit_program_release_closure_plan(plan)))

    def test_operational_matrix_is_explicit_and_addressed(self) -> None:
        matrix = build_program_release_operational_matrix(self.snapshot)
        audit = audit_program_release_operational_matrix(matrix)
        self.assertTrue(matrix.accepted)
        self.assertTrue(audit.accepted)
        self.assertEqual(len(matrix.operations), 16)
        self.assertEqual(
            set(matrix.resources), {"source", "domains", "artifacts", "dependencies", "gates"}
        )
        self.assertEqual(len(program_release_operational_rows(matrix)), 16)
        self.assertIn(b"load-source", render_program_release_operational_markdown(matrix))
        self.assertEqual(matrix.operations[0].prerequisite_ids, ())
        self.assertEqual(
            matrix.operations[-1].prerequisite_ids, (matrix.operations[-2].operation_id,)
        )

    def test_joined_review_views_conserve_domain_relationships(self) -> None:
        views = build_program_release_review_views(self.snapshot)
        audit = audit_program_release_review_views(views, self.snapshot)
        self.assertTrue(views.accepted)
        self.assertTrue(all(item.passed for item in audit))
        self.assertEqual(len(views.views), 16)
        self.assertEqual(views.views[0].outgoing_dependency_count, 15)
        self.assertEqual(views.views[-1].incoming_dependency_count, 15)
        self.assertIn(b"D01", render_program_release_review_views(views))

    def test_runtime_has_fourteen_ready_stages_and_replay(self) -> None:
        report = run_program_release_closure(
            self.source,
            bundle_id=self.snapshot.bundle_id,
            run_id=self.snapshot.run_id,
        )
        self.assertTrue(report.accepted)
        self.assertEqual(report.state, ProgramReleaseClosureState.READY)
        self.assertEqual(len(report.stages), PROGRAM_RELEASE_CLOSURE_RUNTIME_STAGE_TOTAL)
        self.assertTrue(
            all(item.state is ProgramReleaseClosureState.READY for item in report.stages)
        )
        self.assertTrue(report.replay.deterministic)
        self.assertTrue(report.operational.accepted)
        self.assertTrue(report.operational_audit.accepted)
        self.assertTrue(report.views.accepted)
        self.assertTrue(all(item.passed for item in report.views_audit))
        self.assertEqual(report.replay.first_address, report.replay.second_address)
        self.assertEqual(report.replay.expected_address, report.snapshot.content_address)

    def test_replay_diff_is_empty(self) -> None:
        left = build_program_release_snapshot(
            self.source, bundle_id="diff-release", run_id="diff-release"
        )
        right = build_program_release_snapshot(
            self.source, bundle_id="diff-release", run_id="diff-release"
        )
        diff = diff_program_release_closures(left, right)
        self.assertTrue(diff["accepted"])
        self.assertEqual(diff["domains"]["changed"], ())
        self.assertEqual(diff["artifacts"]["removed"], ())

    def test_export_packet_is_exact_and_fifteen_artifacts(self) -> None:
        report = run_program_release_closure(
            self.source, bundle_id=self.snapshot.bundle_id, run_id=self.snapshot.run_id
        )
        packet = build_program_release_export(report)
        self.assertTrue(packet.accepted)
        self.assertEqual(len(packet.artifacts), 15)
        self.assertEqual(packet.manifest.artifact_count, 15)
        with tempfile.TemporaryDirectory() as temporary:
            root = write_program_release_export(packet, temporary)
            verification = verify_program_release_export(packet, root)
            directory_verification = verify_program_release_export_directory(root)
            self.assertTrue(verification.accepted)
            self.assertTrue(directory_verification.accepted)
            self.assertEqual(len(list(Path(root).glob("*.json"))), 16)
            manifest = json.loads((Path(root) / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["artifact_count"], 15)

    def test_export_detects_changed_bytes(self) -> None:
        report = run_program_release_closure(
            self.source, bundle_id=self.snapshot.bundle_id, run_id=self.snapshot.run_id
        )
        packet = build_program_release_export(report)
        with tempfile.TemporaryDirectory() as temporary:
            root = write_program_release_export(packet, temporary)
            target = root / packet.artifacts[0].relative_path
            target.write_text("changed\n", encoding="utf-8")
            verification = verify_program_release_export(packet, root)
            self.assertFalse(verification.accepted)
            self.assertEqual(verification.changed_paths, (packet.artifacts[0].relative_path,))

    def test_public_metadata_policy_and_path_policy(self) -> None:
        self.assertEqual(forbidden_keys(self.snapshot.to_dict()), ())
        self.assertEqual(safe_relative_path("nested/file.json"), "nested/file.json")
        with self.assertRaises(Exception):
            safe_relative_path("../outside.json")
        with self.assertRaises(Exception):
            safe_relative_path("C:/outside.json")
        self.assertTrue(artifact_address(b"{}\n").startswith("program-release-closure-artifact:"))

    def test_api_schema_and_query_routes_share_a_cached_source(self) -> None:
        server = create_server(host="127.0.0.1", port=0)
        server.glio_program_release_closure_test_ids = ("api-test-release", "api-test-release")
        thread = __import__("threading").Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_address[1]
            base = f"http://127.0.0.1:{port}"
            with urlopen(
                f"{base}/v1/program-release/closure/schema?bundle_id=api-test-release&run_id=api-test-release",
                timeout=90,
            ) as response:
                schema = json.loads(response.read().decode("utf-8"))
            self.assertTrue(schema["audit"]["accepted"])
            with urlopen(
                f"{base}/v1/program-release/closure/query?bundle_id=api-test-release&run_id=api-test-release&resource=gates&domain_id=D16&limit=10",
                timeout=30,
            ) as response:
                query = json.loads(response.read().decode("utf-8"))
            self.assertEqual(query["total"], 6)
            with urlopen(
                f"{base}/v1/program-release/closure/operations?bundle_id=api-test-release&run_id=api-test-release",
                timeout=30,
            ) as response:
                operations = json.loads(response.read().decode("utf-8"))
            self.assertTrue(operations["audit"]["accepted"])
            with urlopen(
                f"{base}/v1/program-release/closure/views?bundle_id=api-test-release&run_id=api-test-release",
                timeout=30,
            ) as response:
                views = json.loads(response.read().decode("utf-8"))
            self.assertTrue(all(item["passed"] for item in views["audit"]))
            self.assertEqual(len(server.glio_program_release_closure_sources), 1)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
