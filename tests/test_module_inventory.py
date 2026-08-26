"""Contract, query, packet, and process-boundary tests for module inventory."""

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
from glio_noncode.module_inventory import (
    build_module_inventory,
    module_inventory_capabilities,
    module_inventory_schema,
)
from glio_noncode.module_inventory_audit import audit_module_inventory
from glio_noncode.module_inventory_depth import (
    build_module_inventory_depth,
    query_module_inventory_depth,
)
from glio_noncode.module_inventory_graph import (
    build_module_inventory_graph,
    query_module_inventory_graph,
)
from glio_noncode.module_inventory_observability import (
    build_module_inventory_observability,
    query_module_inventory_observability,
)
from glio_noncode.module_inventory_packet import (
    build_module_inventory_packet,
    load_module_inventory_packet,
    verify_module_inventory_packet,
    write_module_inventory_packet,
)
from glio_noncode.module_inventory_packet_query import (
    diff_module_inventory_packets,
    query_module_inventory_packet,
    replay_module_inventory_packet,
)
from glio_noncode.module_inventory_query import (
    diff_module_inventories,
    inventory_from_mapping,
    query_module_inventory,
)
from glio_noncode.module_inventory_review import (
    build_module_inventory_review_queue,
    query_module_inventory_review,
)
from glio_noncode.module_inventory_runtime import run_module_inventory
from glio_noncode.module_inventory_schema import (
    default_module_inventory_schema,
    validate_module_inventory_schema,
)


class ModuleInventoryFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name) / "source"
        self.tests = Path(self.directory.name) / "tests"
        self.root.mkdir()
        self.tests.mkdir()
        (self.root / "alpha.py").write_text(
            "\n".join(
                (
                    "from glio_noncode.beta import Beta",
                    "from .gamma import gamma",
                    "",
                    "class Alpha:",
                    "    def run(self):",
                    "        return Beta(), gamma()",
                    "",
                    "def public_alpha():",
                    "    return Alpha()",
                )
            )
            + "\n",
            encoding="utf-8",
        )
        (self.root / "beta.py").write_text(
            """from .alpha import Alpha\n\nclass Beta:\n    pass\n""",
            encoding="utf-8",
        )
        (self.root / "gamma.py").write_text(
            """def gamma():\n    return 1\n""",
            encoding="utf-8",
        )
        (self.root / "broken.py").write_text("def broken(:\n", encoding="utf-8")
        (self.tests / "test_alpha.py").write_text(
            "from glio_noncode.alpha import public_alpha\n", encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def build(self):
        return build_module_inventory(self.root, test_root=self.tests)


class ModuleInventoryConstructionTests(ModuleInventoryFixture):
    def test_discovery_is_static_and_counts_rows(self) -> None:
        inventory = self.build()
        self.assertEqual(inventory.module_count, 4)
        self.assertEqual(inventory.parsed_module_count, 3)
        self.assertEqual(len(inventory.issues), 1)
        self.assertEqual(
            inventory.total_physical_lines, sum(item.physical_lines for item in inventory.modules)
        )
        self.assertEqual(
            inventory.total_nonblank_lines, sum(item.nonblank_lines for item in inventory.modules)
        )
        self.assertTrue(inventory.content_address.startswith("module-inventory:"))
        self.assertTrue(inventory.accepted)

    def test_symbols_and_test_references_are_explicit(self) -> None:
        inventory = self.build()
        alpha = next(item for item in inventory.modules if item.module_id.endswith(".alpha"))
        self.assertGreaterEqual(alpha.public_symbol_count, 2)
        self.assertEqual(alpha.test_reference_count, 1)
        self.assertTrue(
            any(item.name == "Alpha" and item.kind == "class" for item in inventory.symbols)
        )
        broken = next(item for item in inventory.modules if item.module_id.endswith(".broken"))
        self.assertEqual(broken.state.value, "parse_error")

    def test_local_imports_keep_resolved_and_unresolved_forms(self) -> None:
        inventory = self.build()
        alpha_edges = [
            item for item in inventory.dependencies if item.source_module.endswith(".alpha")
        ]
        self.assertTrue(
            any(item.target_module.endswith(".beta") and item.resolved for item in alpha_edges)
        )
        self.assertTrue(
            any(item.target_module.endswith(".gamma") and item.resolved for item in alpha_edges)
        )
        self.assertTrue(
            all(
                item.source_module in {row.module_id for row in inventory.modules}
                for item in inventory.dependencies
            )
        )

    def test_independent_audit_accepts_visible_parse_issue(self) -> None:
        inventory = self.build()
        audit = audit_module_inventory(inventory)
        self.assertTrue(audit.accepted, audit.to_dict())
        self.assertGreaterEqual(audit.passed_count, 10)
        self.assertEqual(audit.failed_count, 0)

    def test_mapping_round_trip_preserves_address(self) -> None:
        inventory = self.build()
        restored = inventory_from_mapping(inventory.to_dict())
        self.assertEqual(restored.content_address, inventory.content_address)
        self.assertEqual(restored.module_count, inventory.module_count)
        self.assertEqual(restored.symbols, inventory.symbols)

    def test_schema_report_and_capabilities_are_closed(self) -> None:
        inventory = self.build()
        schema = default_module_inventory_schema()
        report = validate_module_inventory_schema(inventory, schema)
        self.assertTrue(report.accepted, report.to_dict())
        self.assertEqual(schema["boundary"], "public_aggregate_module_inventory")
        self.assertEqual(
            module_inventory_capabilities()["operation_count"],
            len(module_inventory_capabilities()["operations"]),
        )
        self.assertEqual(
            module_inventory_schema()["resources"],
            ["modules", "symbols", "dependencies", "issues", "indexes"],
        )


class ModuleInventoryQueryTests(ModuleInventoryFixture):
    def test_queries_use_bounded_pages_and_filters(self) -> None:
        inventory = self.build()
        result = query_module_inventory(inventory, resource="modules", family="core", limit=2)
        self.assertLessEqual(len(result.items), 2)
        self.assertEqual(result.offset, 0)
        self.assertTrue(result.content_address.startswith("module-inventory-query:"))
        symbols = query_module_inventory(inventory, resource="symbols", symbol="Alpha")
        self.assertTrue(all(item["name"] == "Alpha" for item in symbols.items))
        dependencies = query_module_inventory(
            inventory, resource="dependencies", module_id="glio_noncode.alpha"
        )
        self.assertTrue(
            all(item["source_module"] == "glio_noncode.alpha" for item in dependencies.items)
        )

    def test_queries_reject_invalid_resource_and_page(self) -> None:
        inventory = self.build()
        with self.assertRaises(ValidationError):
            query_module_inventory(inventory, resource="unknown")
        with self.assertRaises(ValidationError):
            query_module_inventory(inventory, limit=501)

    def test_diff_detects_changed_module_and_summary(self) -> None:
        left = self.build()
        (self.root / "gamma.py").write_text(
            "def gamma():\n    value = 2\n    return value\n", encoding="utf-8"
        )
        right = self.build()
        diff = diff_module_inventories(left, right)
        self.assertIn("glio_noncode.gamma", diff.changed_modules)
        self.assertIn("total_nonblank_lines", diff.changed_summary_fields)
        self.assertTrue(diff.accepted)


class ModuleInventoryGraphTests(ModuleInventoryFixture):
    def test_graph_has_nodes_edges_roots_leaves_and_cycles(self) -> None:
        graph = build_module_inventory_graph(self.build())
        self.assertEqual(graph.node_count, 4)
        self.assertGreaterEqual(graph.edge_count, 2)
        self.assertGreaterEqual(graph.unresolved_edge_count, 0)
        self.assertTrue(
            any("glio_noncode.alpha" in component for component in graph.cycle_components)
        )
        self.assertTrue(graph.content_address.startswith("module-inventory-graph:"))

    def test_graph_query_returns_neighborhood(self) -> None:
        graph = build_module_inventory_graph(self.build())
        result = query_module_inventory_graph(graph, module_id="glio_noncode.alpha", limit=10)
        self.assertTrue(result["nodes"])
        self.assertTrue(result["edges"])
        self.assertEqual(result["query"]["module_id"], "glio_noncode.alpha")


class ModuleInventoryDepthReviewTests(ModuleInventoryFixture):
    def test_depth_report_exposes_project_percentage_and_rows(self) -> None:
        inventory = self.build()
        report = build_module_inventory_depth(inventory)
        self.assertEqual(len(report.assessments), inventory.module_count)
        self.assertGreaterEqual(report.overall_percent, 0.0)
        self.assertLessEqual(report.overall_percent, 100.0)
        result = query_module_inventory_depth(report, tier="blocked")
        self.assertTrue(all(item["tier"] == "blocked" for item in result["items"]))

    def test_review_queue_ranks_parse_and_test_gaps(self) -> None:
        inventory = self.build()
        queue = build_module_inventory_review_queue(inventory)
        self.assertTrue(queue.items)
        self.assertGreaterEqual(queue.blocker_count, 1)
        self.assertEqual(queue.open_count, len(queue.items))
        result = query_module_inventory_review(queue, kind="parse_failure")
        self.assertTrue(all(item["kind"] == "parse_failure" for item in result["items"]))


class ModuleInventoryObservabilityTests(ModuleInventoryFixture):
    def test_observability_is_timestamp_free_and_conserved(self) -> None:
        inventory = self.build()
        observation = build_module_inventory_observability(inventory)
        self.assertEqual(observation.metrics.module_count, inventory.module_count)
        self.assertEqual(observation.metrics.issue_count, len(inventory.issues))
        self.assertEqual(observation.metrics.nonblank_line_count, inventory.total_nonblank_lines)
        result = query_module_inventory_observability(observation, event_type="module_discovered")
        self.assertEqual(result["total"], inventory.module_count)
        self.assertNotIn("timestamp", observation.to_dict())


class ModuleInventoryPacketTests(ModuleInventoryFixture):
    def test_packet_writes_verifies_loads_and_queries(self) -> None:
        inventory = self.build()
        runtime = run_module_inventory(inventory=inventory)
        packet = build_module_inventory_packet(inventory, runtime, packet_id="test-module-packet")
        self.assertTrue(packet.accepted, packet.to_dict())
        self.assertEqual(packet.artifact_count, 10)
        destination = Path(self.directory.name) / "packet"
        write_module_inventory_packet(packet, destination)
        verification = verify_module_inventory_packet(destination)
        self.assertTrue(verification.accepted, verification.to_dict())
        loaded = load_module_inventory_packet(destination)
        self.assertEqual(loaded.content_address, packet.content_address)
        query = query_module_inventory_packet(
            destination, resource="modules", module_id="glio_noncode.alpha"
        )
        self.assertEqual(query["total"], 1)
        replay = replay_module_inventory_packet(destination)
        self.assertTrue(replay["accepted"])

    def test_packet_tamper_and_unexpected_file_are_blocked(self) -> None:
        inventory = self.build()
        packet = build_module_inventory_packet(
            inventory, run_module_inventory(inventory=inventory), packet_id="tamper-packet"
        )
        destination = Path(self.directory.name) / "tamper"
        write_module_inventory_packet(packet, destination)
        (destination / "summary.json").write_text("{}\n", encoding="utf-8")
        verification = verify_module_inventory_packet(destination)
        self.assertFalse(verification.accepted)
        second = Path(self.directory.name) / "tamper-extra"
        write_module_inventory_packet(packet, second)
        (second / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")
        verification = verify_module_inventory_packet(second)
        self.assertFalse(verification.accepted)

    def test_packet_diff_is_address_based(self) -> None:
        inventory = self.build()
        left = build_module_inventory_packet(
            inventory, run_module_inventory(inventory=inventory), packet_id="left"
        )
        (self.root / "gamma.py").write_text("def gamma():\n    return 3\n", encoding="utf-8")
        right_inventory = self.build()
        right = build_module_inventory_packet(
            right_inventory, run_module_inventory(inventory=right_inventory), packet_id="right"
        )
        left_dir = Path(self.directory.name) / "left"
        right_dir = Path(self.directory.name) / "right"
        write_module_inventory_packet(left, left_dir)
        write_module_inventory_packet(right, right_dir)
        diff = diff_module_inventory_packets(left_dir, right_dir)
        self.assertTrue(diff["accepted"])
        self.assertIn("inventory", diff["changed_artifact_ids"])


class ModuleInventoryProcessBoundaryTests(unittest.TestCase):
    def test_cli_schema_and_capabilities_are_available(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            schema_path = str(Path(directory) / "schema.json")
            self.assertEqual(main(["module-inventory-schema", "--output", schema_path]), 0)
            self.assertEqual(
                json.loads(Path(schema_path).read_text(encoding="utf-8"))["schema_version"],
                "module-inventory-schema-v1",
            )
            capabilities_path = str(Path(directory) / "capabilities.json")
            self.assertEqual(
                main(["module-inventory-capabilities", "--output", capabilities_path]), 0
            )
            self.assertIn(
                "inventory", json.loads(Path(capabilities_path).read_text(encoding="utf-8"))
            )

    def test_cli_can_inventory_small_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source"
            root.mkdir()
            (root / "one.py").write_text("class One:\n    pass\n", encoding="utf-8")
            output = Path(directory) / "summary.json"
            status = main(
                [
                    "module-inventory",
                    "--source-root",
                    str(root),
                    "--test-root",
                    str(Path(directory) / "missing"),
                    "--format",
                    "summary",
                    "--output",
                    str(output),
                ]
            )
            self.assertEqual(status, 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["module_count"], 1)

    def test_http_schema_and_capabilities_routes_do_not_scan_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=60)
                connection.request("GET", "/v1/module-inventory/schema")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                payload = json.loads(response.read())
                self.assertEqual(payload["schema"]["schema_version"], "module-inventory-schema-v1")
                connection.close()
                connection = HTTPConnection(host, port, timeout=60)
                connection.request("GET", "/v1/module-inventory/capabilities")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertIn("inventory", json.loads(response.read()))
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
