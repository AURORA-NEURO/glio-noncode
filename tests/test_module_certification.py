"""Contract, evidence, packet, API, and CLI tests for module certification."""

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.module_certification import (
    build_module_certification,
    module_certification_capabilities,
    module_certification_schema,
    verify_module_certification,
)
from glio_noncode.module_certification_audit import audit_module_certification
from glio_noncode.module_certification_contracts import (
    CertificationCheckKind,
    CertificationCheckState,
    CertificationState,
)
from glio_noncode.module_certification_diff import (
    build_module_certification_diff,
    query_module_certification_diff,
)
from glio_noncode.module_certification_exports import (
    module_certification_checks_csv,
    module_certification_rows_csv,
    module_certification_summary,
    render_module_certification_markdown,
)
from glio_noncode.module_certification_observability import (
    build_module_certification_observability,
    query_module_certification_observability,
)
from glio_noncode.module_certification_packet import (
    build_module_certification_packet,
    load_module_certification_packet,
    verify_module_certification_packet,
    write_module_certification_packet,
)
from glio_noncode.module_certification_packet_query import (
    diff_module_certification_packets,
    query_module_certification_packet,
    replay_module_certification_packet,
)
from glio_noncode.module_certification_policy import (
    build_module_certification_policy,
    evaluate_module_certification_gate,
)
from glio_noncode.module_certification_review import (
    CertificationReviewSeverity,
    build_module_certification_review_queue,
    query_module_certification_review,
)
from glio_noncode.module_certification_runtime import run_module_certification
from glio_noncode.module_certification_schema import (
    default_module_certification_fields,
    validate_module_certification_schema,
)
from glio_noncode.module_certification_tasks import (
    build_module_certification_task_plan,
    module_certification_tasks_csv,
    query_module_certification,
    verify_module_certification_tasks,
)
from glio_noncode.module_inventory import build_module_inventory


class ModuleCertificationFixture(unittest.TestCase):
    """Small source tree with explicit positive, negative, and boundary evidence."""

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.source = root / "source"
        self.tests = root / "tests"
        self.docs = root / "docs"
        self.source.mkdir()
        self.tests.mkdir()
        self.docs.mkdir()
        (self.source / "__init__.py").write_text(
            "from .alpha import Alpha, public_alpha\nfrom .beta import Beta\n",
            encoding="utf-8",
        )
        (self.source / "alpha.py").write_text(
            "from .beta import Beta\n\n"
            "class Alpha:\n"
            "    def run(self) -> Beta:\n"
            "        return Beta()\n\n"
            "def public_alpha() -> Alpha:\n"
            "    return Alpha()\n",
            encoding="utf-8",
        )
        (self.source / "beta.py").write_text(
            "class Beta:\n    def value(self) -> int:\n        return 1\n",
            encoding="utf-8",
        )
        (self.source / "internal.py").write_text(
            "_VALUE = 1\n",
            encoding="utf-8",
        )
        (self.source / "broken.py").write_text("def broken(:\n", encoding="utf-8")
        (self.tests / "test_alpha.py").write_text(
            "from glio_noncode.alpha import public_alpha\nfrom glio_noncode.beta import Beta\n",
            encoding="utf-8",
        )
        (self.docs / "module-contracts.md").write_text(
            "# Module contracts\n\n"
            "`glio_noncode.alpha` is the public entry point.\n"
            "`glio_noncode.beta` supports the alpha contract.\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def inventory(self):
        return build_module_inventory(self.source, test_root=self.tests)

    def matrix(self):
        inventory = self.inventory()
        return build_module_certification(
            inventory,
            source_root=self.source,
            test_root=self.tests,
            docs_root=self.docs,
        )

    def closure(self):
        inventory = self.inventory()
        matrix = build_module_certification(
            inventory,
            source_root=self.source,
            test_root=self.tests,
            docs_root=self.docs,
        )
        plan = build_module_certification_task_plan(matrix)
        policy = build_module_certification_policy(
            minimum_score=0.0,
            minimum_certified_percent=0.0,
            maximum_blocked_count=100,
            maximum_review_count=100,
            require_tests_for_domain=False,
            require_documentation_for_integration=False,
            require_export_for_public_symbols=False,
        )
        gate = evaluate_module_certification_gate(matrix, plan, policy)
        runtime = run_module_certification(
            self.source,
            test_root=self.tests,
            docs_root=self.docs,
            inventory=inventory,
            policy=policy,
        )
        audit = audit_module_certification(matrix, plan, gate, runtime)
        observation = build_module_certification_observability(matrix, plan, gate, runtime)
        return inventory, matrix, plan, gate, runtime, audit, observation


class ModuleCertificationConstructionTests(ModuleCertificationFixture):
    def test_matrix_has_one_row_per_inventory_module(self) -> None:
        inventory = self.inventory()
        matrix = self.matrix()
        self.assertEqual(matrix.module_count, inventory.module_count)
        self.assertEqual(len(matrix.rows), inventory.module_count)
        self.assertEqual(
            tuple(row.module_id for row in matrix.rows),
            tuple(sorted(row.module_id for row in matrix.rows)),
        )
        self.assertEqual(matrix.check_kind_count, 8)
        self.assertTrue(matrix.content_address.startswith("module-certification-matrix:"))

    def test_every_row_has_all_check_kinds_in_stable_order(self) -> None:
        matrix = self.matrix()
        expected = tuple(CertificationCheckKind)
        for row in matrix.rows:
            self.assertEqual(tuple(check.kind for check in row.checks), expected)
            self.assertEqual(
                row.passed_count + row.failed_count + row.not_applicable_count,
                len(row.checks),
            )
            self.assertEqual(row.gap_count, row.failed_count)
            self.assertGreaterEqual(row.score, 0.0)
            self.assertLessEqual(row.score, 1.0)

    def test_parse_error_is_blocking_and_creates_gap(self) -> None:
        matrix = self.matrix()
        broken = next(row for row in matrix.rows if row.module_id.endswith(".broken"))
        self.assertEqual(broken.state, CertificationState.BLOCKED)
        parse = next(check for check in broken.checks if check.kind is CertificationCheckKind.PARSE)
        self.assertEqual(parse.state, CertificationCheckState.FAILED)
        self.assertIn("parse:glio_noncode.broken", {gap.gap_id for gap in matrix.gaps})

    def test_public_module_gets_static_test_and_documentation_evidence(self) -> None:
        matrix = self.matrix()
        alpha = next(row for row in matrix.rows if row.module_id.endswith(".alpha"))
        check_map = {check.kind: check for check in alpha.checks}
        self.assertEqual(
            check_map[CertificationCheckKind.TEST].state, CertificationCheckState.PASSED
        )
        self.assertEqual(
            check_map[CertificationCheckKind.DOCUMENTATION].state, CertificationCheckState.PASSED
        )
        self.assertEqual(
            check_map[CertificationCheckKind.EXPORT].state, CertificationCheckState.PASSED
        )

    def test_internal_module_allows_non_applicable_coverage(self) -> None:
        matrix = self.matrix()
        internal = next(row for row in matrix.rows if row.module_id.endswith(".internal"))
        self.assertGreaterEqual(internal.not_applicable_count, 1)
        self.assertEqual(internal.state, CertificationState.CERTIFIED)

    def test_matrix_verification_preserves_addresses(self) -> None:
        matrix = self.matrix()
        self.assertIs(verify_module_certification(matrix), matrix)

    def test_matrix_json_and_schema_are_deterministic(self) -> None:
        matrix = self.matrix()
        self.assertEqual(
            module_certification_schema()["boundary"], "public_aggregate_module_certification"
        )
        self.assertEqual(
            module_certification_capabilities()["operation_count"],
            len(module_certification_capabilities()["operations"]),
        )
        self.assertEqual(len(default_module_certification_fields()), 21)
        report = validate_module_certification_schema(matrix)
        self.assertTrue(report.accepted, report.to_dict())


class ModuleCertificationTaskTests(ModuleCertificationFixture):
    def test_task_plan_has_one_task_for_each_gap(self) -> None:
        matrix = self.matrix()
        plan = build_module_certification_task_plan(matrix)
        self.assertEqual(plan.task_count, matrix.gap_count)
        self.assertEqual(
            tuple((task.priority, task.kind.value, task.module_id) for task in plan.tasks),
            tuple(sorted((task.priority, task.kind.value, task.module_id) for task in plan.tasks)),
        )
        self.assertIs(verify_module_certification_tasks(matrix, plan), plan)

    def test_task_query_can_filter_by_module_and_resource(self) -> None:
        matrix = self.matrix()
        plan = build_module_certification_task_plan(matrix)
        result = query_module_certification(
            matrix,
            plan,
            resource="tasks",
            module_id="glio_noncode.broken",
            limit=10,
        )
        self.assertTrue(result["items"])
        self.assertTrue(all(item.module_id == "glio_noncode.broken" for item in result["items"]))

    def test_task_query_rejects_unknown_resource_and_page(self) -> None:
        matrix = self.matrix()
        plan = build_module_certification_task_plan(matrix)
        with self.assertRaises(ValidationError):
            query_module_certification(matrix, plan, resource="unknown")
        with self.assertRaises(ValidationError):
            query_module_certification(matrix, plan, limit=513)

    def test_task_csv_has_stable_headers(self) -> None:
        plan = build_module_certification_task_plan(self.matrix())
        self.assertTrue(
            module_certification_tasks_csv(plan).startswith("task_id,module_id,kind,priority")
        )


class ModuleCertificationPolicyTests(ModuleCertificationFixture):
    def test_strict_policy_blocks_fixture_gaps(self) -> None:
        _, matrix, plan, gate, *_ = self.closure()
        strict = build_module_certification_policy(
            minimum_score=0.99,
            minimum_certified_percent=99.0,
            maximum_blocked_count=0,
            maximum_review_count=0,
        )
        strict_gate = evaluate_module_certification_gate(matrix, plan, strict)
        self.assertFalse(strict_gate.accepted)
        self.assertTrue(any(not check.passed for check in strict_gate.checks))
        self.assertTrue(gate.accepted, gate.to_dict())

    def test_permissive_policy_can_accept_structurally_valid_closure(self) -> None:
        _, _, _, gate, *_ = self.closure()
        self.assertEqual(gate.state.value, "accepted")
        self.assertEqual(gate.accepted, all(check.passed for check in gate.checks))
        self.assertGreaterEqual(gate.passed_count, 1)


class ModuleCertificationAuditTests(ModuleCertificationFixture):
    def test_audit_closes_matrix_plan_gate_runtime_links(self) -> None:
        _, matrix, plan, gate, runtime, audit, _ = self.closure()
        self.assertTrue(audit.accepted, audit.to_dict())
        self.assertEqual(audit.matrix_address, matrix.content_address)
        self.assertEqual(gate.matrix_address, matrix.content_address)
        self.assertEqual(runtime.plan_address, plan.content_address)

    def test_audit_has_independent_planes(self) -> None:
        *_, audit, _ = self.closure()
        planes = {check.plane.value for check in audit.checks}
        self.assertEqual(planes, {"inventory", "coverage", "policy", "public"})


class ModuleCertificationRuntimeObservabilityTests(ModuleCertificationFixture):
    def test_runtime_has_contiguous_timestamp_free_stages(self) -> None:
        _, matrix, plan, gate, runtime, _, _ = self.closure()
        self.assertEqual(tuple(stage.order for stage in runtime.stages), tuple(range(1, 8)))
        self.assertEqual(runtime.matrix_address, matrix.content_address)
        self.assertEqual(runtime.plan_address, plan.content_address)
        self.assertEqual(runtime.gate_address, gate.content_address)

    def test_observability_has_bounded_events_and_metrics(self) -> None:
        _, matrix, _, _, _, _, observation = self.closure()
        self.assertEqual(len(observation.events), 6)
        self.assertEqual(tuple(item.sequence for item in observation.events), tuple(range(1, 7)))
        metrics = query_module_certification_observability(
            observation, resource="metrics", category="matrix"
        )
        self.assertTrue(metrics["items"])
        events = query_module_certification_observability(
            observation, resource="events", state="accepted"
        )
        self.assertTrue(events["items"])
        self.assertEqual(observation.matrix_address, matrix.content_address)

    def test_observability_rejects_invalid_page(self) -> None:
        observation = self.closure()[-1]
        with self.assertRaises(ValidationError):
            query_module_certification_observability(observation, limit=513)


class ModuleCertificationExportTests(ModuleCertificationFixture):
    def test_summary_conserves_family_rows(self) -> None:
        matrix = self.matrix()
        summary = module_certification_summary(matrix)
        self.assertEqual(summary["module_count"], matrix.module_count)
        self.assertEqual(
            sum(row["module_count"] for row in summary["families"]), matrix.module_count
        )

    def test_csv_exports_have_expected_headers(self) -> None:
        matrix = self.matrix()
        self.assertTrue(module_certification_rows_csv(matrix).startswith("module_id,family,role"))
        self.assertTrue(module_certification_checks_csv(matrix).startswith("module_id,kind,state"))

    def test_markdown_report_contains_aggregate_and_gap_sections(self) -> None:
        report = render_module_certification_markdown(self.matrix())
        self.assertIn("# Module certification matrix", report)
        self.assertIn("## Family summary", report)
        self.assertIn("## Gap queue", report)


class ModuleCertificationReviewTests(ModuleCertificationFixture):
    def test_review_queue_groups_gaps_by_module(self) -> None:
        matrix = self.matrix()
        queue = build_module_certification_review_queue(matrix)
        self.assertEqual(queue.item_count, len({gap.module_id for gap in matrix.gaps}))
        self.assertEqual(
            sum(item.gap_count for item in queue.items),
            matrix.gap_count,
        )
        self.assertTrue(
            any(item.severity == CertificationReviewSeverity.BLOCKING for item in queue.items)
        )

    def test_review_query_supports_severity_and_role(self) -> None:
        queue = build_module_certification_review_queue(self.matrix())
        result = query_module_certification_review(queue, severity="blocking", role="core")
        self.assertTrue(all(item.severity == "blocking" for item in result["items"]))
        self.assertTrue(all(item.role == "core" for item in result["items"]))


class ModuleCertificationDiffTests(ModuleCertificationFixture):
    def test_diff_detects_score_and_check_changes(self) -> None:
        left = self.matrix()
        (self.source / "beta.py").write_text(
            "class Beta:\n"
            "    def value(self) -> int:\n"
            "        return 2\n\n"
            "def public_beta() -> Beta:\n"
            "    return Beta()\n",
            encoding="utf-8",
        )
        right = self.matrix()
        diff = build_module_certification_diff(left, right)
        self.assertTrue(
            any(item.module_id.endswith(".beta") for item in diff.rows if item.change == "changed")
        )
        self.assertEqual(diff.left_matrix_address, left.content_address)
        self.assertEqual(diff.right_matrix_address, right.content_address)

    def test_diff_query_is_bounded(self) -> None:
        left = self.matrix()
        right = self.matrix()
        diff = build_module_certification_diff(left, right)
        result = query_module_certification_diff(diff, change="unchanged", limit=2)
        self.assertLessEqual(len(result["items"]), 2)
        with self.assertRaises(ValidationError):
            query_module_certification_diff(diff, limit=513)


class ModuleCertificationPacketTests(ModuleCertificationFixture):
    def test_packet_has_ten_exact_byte_artifacts(self) -> None:
        _, matrix, plan, gate, runtime, audit, observation = self.closure()
        packet = build_module_certification_packet(matrix, plan, gate, runtime, audit, observation)
        self.assertEqual(packet.artifact_count, 10)
        self.assertEqual(len({item.artifact_id for item in packet.artifacts}), 10)
        self.assertTrue(all(item.payload is not None for item in packet.artifacts))
        self.assertTrue(packet.accepted, packet.to_dict())

    def test_packet_write_verify_load_and_query_round_trip(self) -> None:
        _, matrix, plan, gate, runtime, audit, observation = self.closure()
        packet = build_module_certification_packet(matrix, plan, gate, runtime, audit, observation)
        destination = Path(self.directory.name) / "packet"
        write_module_certification_packet(packet, destination)
        verification = verify_module_certification_packet(destination)
        self.assertTrue(verification.accepted, verification.to_dict())
        loaded = load_module_certification_packet(destination)
        self.assertEqual(loaded.content_address, packet.content_address)
        result = query_module_certification_packet(destination, resource="modules", limit=2)
        self.assertLessEqual(len(result["items"]), 2)
        replay = replay_module_certification_packet(destination)
        self.assertTrue(replay["accepted"], replay)

    def test_packet_query_and_diff_are_offline(self) -> None:
        closure = self.closure()
        packet = build_module_certification_packet(*closure[1:])
        left = Path(self.directory.name) / "left"
        right = Path(self.directory.name) / "right"
        write_module_certification_packet(packet, left)
        write_module_certification_packet(packet, right)
        result = query_module_certification_packet(left, resource="gaps", limit=3)
        self.assertLessEqual(len(result["items"]), 3)
        diff = diff_module_certification_packets(left, right)
        self.assertTrue(diff["accepted"], diff)
        self.assertEqual(diff["changed_artifact_ids"], ())

    def test_packet_writer_refuses_unintentional_overwrite(self) -> None:
        closure = self.closure()
        packet = build_module_certification_packet(*closure[1:])
        destination = Path(self.directory.name) / "packet"
        write_module_certification_packet(packet, destination)
        with self.assertRaises(ValidationError):
            write_module_certification_packet(packet, destination)


class ModuleCertificationBoundaryTests(ModuleCertificationFixture):
    def test_cli_schema_and_capabilities_commands(self) -> None:
        with tempfile.TemporaryDirectory() as output_dir:
            schema_path = Path(output_dir) / "schema.json"
            caps_path = Path(output_dir) / "caps.json"
            self.assertEqual(main(["module-certification-schema", "--output", str(schema_path)]), 0)
            self.assertEqual(
                main(["module-certification-capabilities", "--output", str(caps_path)]), 0
            )
            self.assertIn("packet", json.loads(schema_path.read_text(encoding="utf-8")))
            self.assertIn("certification", json.loads(caps_path.read_text(encoding="utf-8")))

    def test_api_schema_and_capabilities_are_public(self) -> None:
        server = create_server(host="127.0.0.1", port=0)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = HTTPConnection("127.0.0.1", server.server_port, timeout=10)
            connection.request("GET", "/v1/module-certification/schema")
            schema_response = connection.getresponse()
            schema = json.loads(schema_response.read().decode("utf-8"))
            self.assertEqual(schema_response.status, 200)
            self.assertIn("certification", schema)
            connection.request("GET", "/v1/module-certification/capabilities")
            capability_response = connection.getresponse()
            capabilities = json.loads(capability_response.read().decode("utf-8"))
            self.assertEqual(capability_response.status, 200)
            self.assertIn("packet_query", capabilities)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=10)


if __name__ == "__main__":
    unittest.main()
