"""Focused contract, propagation, packet, CLI, and boundary tests for module impact."""

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread
from urllib.parse import urlencode

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.module_impact import (
    build_module_impact_diff,
    build_module_impact_report,
    module_impact_json,
    verify_module_impact_diff,
)
from glio_noncode.module_impact_audit import audit_module_impact
from glio_noncode.module_impact_contracts import (
    ImpactChangeKind,
    ImpactPropagation,
)
from glio_noncode.module_impact_observability import (
    build_module_impact_observability,
    module_impact_events_csv,
    module_impact_metrics_csv,
)
from glio_noncode.module_impact_packet import (
    build_module_impact_packet,
    load_module_impact_packet,
    verify_module_impact_packet,
    write_module_impact_packet,
)
from glio_noncode.module_impact_packet_query import (
    diff_module_impact_packets,
    query_module_impact_packet,
    replay_module_impact_packet,
)
from glio_noncode.module_impact_policy import (
    build_module_impact_policy,
    default_module_impact_policy,
    evaluate_module_impact_gate,
)
from glio_noncode.module_impact_query import (
    diff_module_impact_reports,
    impact_diff_from_mapping,
    impact_gate_from_mapping,
    impact_plan_from_mapping,
    impact_report_from_mapping,
    query_module_impact,
)
from glio_noncode.module_impact_runtime import (
    module_impact_runtime_capabilities,
    module_impact_runtime_schema,
    run_module_impact,
)
from glio_noncode.module_impact_schema import (
    default_module_impact_schema,
    module_impact_schema_capabilities,
    validate_module_impact_schema,
)
from glio_noncode.module_impact_verification import (
    build_module_impact_verification_plan,
    module_impact_verification_schema,
    query_module_impact_tasks,
)
from glio_noncode.module_inventory import build_module_inventory
from glio_noncode.run_workspace import _has_forbidden_key


class ModuleImpactFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.left_root = root / "left"
        self.right_root = root / "right"
        self.left_tests = root / "left-tests"
        self.right_tests = root / "right-tests"
        for directory in (self.left_root, self.right_root, self.left_tests, self.right_tests):
            directory.mkdir()
        self.left_files = {
            "a.py": "def alpha():\n    return 1\n",
            "b.py": "from glio_noncode.a import alpha\n\ndef beta():\n    return alpha()\n",
            "c.py": "from glio_noncode.b import beta\n\ndef gamma():\n    return beta()\n",
        }
        self.right_files = self.left_files | {
            "a.py": "def alpha():\n    return 2\n",
            "d.py": "from glio_noncode.a import alpha\n\ndef delta():\n    return alpha()\n",
        }
        self._write(self.left_root, self.left_files)
        self._write(self.right_root, self.right_files)
        self._write(self.left_tests, {"test_a.py": "import glio_noncode.a\n"})
        self._write(
            self.right_tests,
            {"test_a.py": "import glio_noncode.a\nimport glio_noncode.d\n"},
        )
        self.left = build_module_inventory(self.left_root, test_root=self.left_tests)
        self.right = build_module_inventory(self.right_root, test_root=self.right_tests)
        self.diff = build_module_impact_diff(self.left, self.right)
        self.report = build_module_impact_report(self.left, self.right, self.diff)
        self.plan = build_module_impact_verification_plan(self.diff, self.report)
        self.gate = evaluate_module_impact_gate(self.diff, self.report, self.plan)

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def _write(root: Path, files: dict[str, str]) -> None:
        for relative, text in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")


class TestModuleImpactDiff(ModuleImpactFixture):
    def test_classifies_added_changed_and_unchanged_modules(self) -> None:
        rows = {item.module_id: item for item in self.diff.changes}
        self.assertEqual(self.diff.added_count, 1)
        self.assertEqual(self.diff.changed_count, 1)
        self.assertEqual(self.diff.removed_count, 0)
        self.assertEqual(rows["glio_noncode.d"].kind, ImpactChangeKind.ADDED)
        self.assertEqual(rows["glio_noncode.a"].kind, ImpactChangeKind.CHANGED)
        self.assertEqual(rows["glio_noncode.b"].kind, ImpactChangeKind.UNCHANGED)
        self.assertIn("module_count", self.diff.changed_summary_fields)
        self.assertEqual(self.diff.summary_delta["module_count"], 1)

    def test_dependency_diff_is_addressed_and_ordered(self) -> None:
        self.assertTrue(self.diff.dependencies)
        self.assertEqual(
            tuple(item.key for item in self.diff.dependencies),
            tuple(sorted(item.key for item in self.diff.dependencies)),
        )
        verify_module_impact_diff(self.diff)
        self.assertEqual(module_impact_json(self.diff), module_impact_json(self.diff))

    def test_mapping_hydration_preserves_diff_address(self) -> None:
        hydrated = impact_diff_from_mapping(self.diff.to_dict())
        self.assertEqual(hydrated.content_address, self.diff.content_address)
        self.assertEqual(hydrated.to_dict(), self.diff.to_dict())


class TestModuleImpactPropagation(ModuleImpactFixture):
    def test_reverse_dependency_propagation_retains_shortest_paths(self) -> None:
        rows = {item.module_id: item for item in self.report.assessments}
        self.assertEqual(rows["glio_noncode.a"].propagation, ImpactPropagation.DIRECT)
        self.assertEqual(rows["glio_noncode.b"].propagation, ImpactPropagation.DEPENDENT)
        self.assertEqual(rows["glio_noncode.c"].propagation, ImpactPropagation.TRANSITIVE)
        self.assertEqual(rows["glio_noncode.c"].distance, 2)
        self.assertIn(
            "glio_noncode.a->glio_noncode.b->glio_noncode.c", rows["glio_noncode.c"].paths
        )
        self.assertEqual(rows["glio_noncode.d"].direct_change_kind, ImpactChangeKind.ADDED)

    def test_impact_counts_conserve_rows(self) -> None:
        self.assertEqual(
            self.report.direct_count + self.report.dependent_count + self.report.transitive_count,
            self.report.impact_count,
        )
        self.assertEqual(self.report.critical_count, 0)
        self.assertGreaterEqual(self.report.high_count, 0)
        self.assertTrue(self.gate.accepted)

    def test_cycle_termination_does_not_duplicate_assessments(self) -> None:
        cycle_root = Path(self.temp.name) / "cycle"
        cycle_tests = Path(self.temp.name) / "cycle-tests"
        cycle_root.mkdir()
        cycle_tests.mkdir()
        self._write(
            cycle_root,
            {
                "a.py": "from glio_noncode.b import beta\ndef alpha():\n    return beta()\n",
                "b.py": "from glio_noncode.a import alpha\ndef beta():\n    return alpha()\n",
            },
        )
        self._write(cycle_tests, {"test_a.py": "import glio_noncode.a\n"})
        old = build_module_inventory(cycle_root, test_root=cycle_tests)
        self._write(
            cycle_root, {"a.py": "from glio_noncode.b import beta\ndef alpha():\n    return 4\n"}
        )
        new = build_module_inventory(cycle_root, test_root=cycle_tests)
        report = build_module_impact_report(old, new)
        self.assertEqual(len({item.module_id for item in report.assessments}), report.impact_count)
        self.assertEqual(report.impact_count, 2)


class TestModuleImpactPolicy(ModuleImpactFixture):
    def test_removed_symbol_is_critical_and_blocks_default_gate(self) -> None:
        broken_root = Path(self.temp.name) / "broken"
        broken_tests = Path(self.temp.name) / "broken-tests"
        broken_root.mkdir()
        broken_tests.mkdir()
        self._write(broken_root, self.left_files | {"a.py": "def alternate():\n    return 5\n"})
        self._write(broken_tests, {"test_a.py": "import glio_noncode.a\n"})
        new = build_module_inventory(broken_root, test_root=broken_tests)
        diff = build_module_impact_diff(self.left, new)
        report = build_module_impact_report(self.left, new, diff)
        plan = build_module_impact_verification_plan(diff, report)
        gate = evaluate_module_impact_gate(diff, report, plan)
        self.assertEqual(report.critical_count, 1)
        self.assertEqual(gate.accepted, False)
        self.assertFalse(
            any(item.passed for item in gate.checks if item.check_id == "critical-limit")
        )

    def test_custom_policy_can_allow_reviewable_critical_change(self) -> None:
        policy = build_module_impact_policy(
            max_critical=10, max_high=10, allow_removed_modules=True
        )
        permitted = evaluate_module_impact_gate(self.diff, self.report, self.plan, policy)
        self.assertTrue(permitted.accepted)
        self.assertEqual(policy.policy_id, default_module_impact_policy().policy_id)

    def test_runtime_is_deterministic_and_staged(self) -> None:
        first = run_module_impact(self.left, self.right)
        second = run_module_impact(self.left, self.right)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual([item.order for item in first.stages], list(range(1, 8)))
        self.assertEqual(first.diff_address, self.diff.content_address)
        self.assertTrue(first.accepted)


class TestModuleImpactVerification(ModuleImpactFixture):
    def test_plan_contains_direct_and_dependent_tasks(self) -> None:
        kinds = {item.kind.value for item in self.plan.tasks}
        self.assertIn("review_direct_change", kinds)
        self.assertIn("replay_dependent", kinds)
        self.assertEqual(
            tuple((item.priority, item.kind.value, item.module_id) for item in self.plan.tasks),
            tuple(
                sorted((item.priority, item.kind.value, item.module_id) for item in self.plan.tasks)
            ),
        )

    def test_task_query_is_bounded_and_addressed(self) -> None:
        result = query_module_impact_tasks(self.plan, kind="replay_dependent", limit=1)
        self.assertEqual(result["total"], 2)
        self.assertEqual(len(result["items"]), 1)
        self.assertTrue(result["has_more"])
        self.assertTrue(result["content_address"])
        with self.assertRaises(ValidationError):
            query_module_impact_tasks(self.plan, limit=0)

    def test_general_query_supports_each_primary_resource(self) -> None:
        for resource in ("changes", "dependencies", "impacts", "tasks"):
            result = query_module_impact(
                diff=self.diff,
                report=self.report,
                plan=self.plan,
                resource=resource,
                limit=2,
            )
            self.assertEqual(result["resource"].value, resource)
            self.assertLessEqual(len(result["items"]), 2)


class TestModuleImpactClosure(ModuleImpactFixture):
    def test_schema_and_audit_close_references(self) -> None:
        schema_report = validate_module_impact_schema(self.diff, self.report, self.plan, self.gate)
        self.assertTrue(schema_report.accepted)
        audit = audit_module_impact(self.diff, self.report, self.plan, self.gate)
        self.assertTrue(audit.accepted)
        self.assertEqual(audit.passed_count, len(audit.checks))

    def test_mapping_hydration_closes_report_plan_and_gate(self) -> None:
        report = impact_report_from_mapping(self.report.to_dict())
        plan = impact_plan_from_mapping(self.plan.to_dict())
        gate = impact_gate_from_mapping(self.gate.to_dict())
        self.assertEqual(report.content_address, self.report.content_address)
        self.assertEqual(plan.content_address, self.plan.content_address)
        self.assertEqual(gate.content_address, self.gate.content_address)

    def test_report_diff_exposes_risk_shift(self) -> None:
        diff = diff_module_impact_reports(self.report, self.report)
        self.assertEqual(diff["changed_modules"], ())
        self.assertEqual(
            diff["content_address"],
            diff_module_impact_reports(self.report, self.report)["content_address"],
        )

    def test_schema_capabilities_are_public_and_deterministic(self) -> None:
        values = {
            "schema": default_module_impact_schema(),
            "schema_caps": module_impact_schema_capabilities(),
            "runtime_schema": module_impact_runtime_schema(),
            "runtime_caps": module_impact_runtime_capabilities(),
            "verification_schema": module_impact_verification_schema(),
        }
        self.assertFalse(_has_forbidden_key(values))
        self.assertEqual(
            values,
            {
                "schema": default_module_impact_schema(),
                "schema_caps": module_impact_schema_capabilities(),
                "runtime_schema": module_impact_runtime_schema(),
                "runtime_caps": module_impact_runtime_capabilities(),
                "verification_schema": module_impact_verification_schema(),
            },
        )


class TestModuleImpactObservability(ModuleImpactFixture):
    def test_events_and_metrics_are_timestamp_free_and_exportable(self) -> None:
        observation = build_module_impact_observability(
            self.diff, self.report, self.plan, self.gate
        )
        self.assertTrue(observation.accepted)
        self.assertEqual([item.sequence for item in observation.events], list(range(1, 6)))
        self.assertIn("event_type", module_impact_events_csv(observation).splitlines()[0])
        self.assertIn("metric_id", module_impact_metrics_csv(observation).splitlines()[0])
        self.assertFalse(_has_forbidden_key(observation.to_dict()))


class TestModuleImpactPacket(ModuleImpactFixture):
    def test_packet_round_trip_and_offline_query(self) -> None:
        packet = build_module_impact_packet(self.left, self.right)
        destination = Path(self.temp.name) / "packet"
        write_module_impact_packet(packet, destination)
        verification = verify_module_impact_packet(destination)
        loaded = load_module_impact_packet(destination)
        self.assertTrue(packet.accepted)
        self.assertTrue(verification.accepted)
        self.assertEqual(loaded.content_address, packet.content_address)
        query = query_module_impact_packet(destination, resource="impacts", limit=2)
        self.assertTrue(query["accepted"])
        self.assertEqual(len(query["items"]), 2)
        replay = replay_module_impact_packet(destination)
        self.assertTrue(replay["accepted"])

    def test_packet_tamper_is_rejected_before_load(self) -> None:
        packet = build_module_impact_packet(self.left, self.right)
        destination = Path(self.temp.name) / "tampered"
        write_module_impact_packet(packet, destination)
        diff_path = destination / "diff.json"
        diff_path.write_text(diff_path.read_text(encoding="utf-8") + "tamper\n", encoding="utf-8")
        verification = verify_module_impact_packet(destination)
        self.assertFalse(verification.accepted)
        with self.assertRaises(ValidationError):
            load_module_impact_packet(destination)

    def test_packet_diff_is_stable(self) -> None:
        first = build_module_impact_packet(self.left, self.right, packet_id="first")
        second = build_module_impact_packet(self.left, self.right, packet_id="second")
        first_dir = Path(self.temp.name) / "first"
        second_dir = Path(self.temp.name) / "second"
        write_module_impact_packet(first, first_dir)
        write_module_impact_packet(second, second_dir)
        result = diff_module_impact_packets(first_dir, second_dir)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["changed_artifacts"], ())
        self.assertTrue(result["content_address"])


class TestModuleImpactCli(ModuleImpactFixture):
    def test_cli_summary_and_schema_commands(self) -> None:
        summary_path = Path(self.temp.name) / "summary.json"
        schema_path = Path(self.temp.name) / "schema.json"
        code = main(
            [
                "module-impact",
                "--left-source-root",
                str(self.left_root),
                "--right-source-root",
                str(self.right_root),
                "--left-test-root",
                str(self.left_tests),
                "--right-test-root",
                str(self.right_tests),
                "--output",
                str(summary_path),
            ]
        )
        schema_code = main(["module-impact-schema", "--output", str(schema_path)])
        self.assertEqual(code, 0)
        self.assertEqual(schema_code, 0)
        self.assertTrue(json.loads(summary_path.read_text(encoding="utf-8"))["accepted"])
        self.assertEqual(
            json.loads(schema_path.read_text(encoding="utf-8"))["impact"]["version"],
            "module-impact-schema-v1",
        )

    def test_http_schema_and_capabilities_routes(self) -> None:
        server = create_server("127.0.0.1", 0, self.left_root)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            connection = HTTPConnection(host, port, timeout=30)
            connection.request("GET", "/v1/module-impact/schema")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            schema = json.loads(response.read())
            self.assertEqual(schema["schema"]["version"], "module-impact-schema-v1")
            connection.close()
            connection = HTTPConnection(host, port, timeout=30)
            connection.request("GET", "/v1/module-impact/capabilities")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertIn("packet_query", json.loads(response.read()))
            connection.close()
            connection = HTTPConnection(host, port, timeout=30)
            query = urlencode(
                {
                    "left_source_root": str(self.left_root),
                    "right_source_root": str(self.right_root),
                    "left_test_root": str(self.left_tests),
                    "right_test_root": str(self.right_tests),
                }
            )
            connection.request("GET", f"/v1/module-impact?{query}")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertTrue(json.loads(response.read())["accepted"])
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
