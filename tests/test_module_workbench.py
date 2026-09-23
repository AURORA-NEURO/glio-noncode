"""Contract and query tests for module-by-module workbench planning."""

from __future__ import annotations

import json
import io
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread
from unittest.mock import patch
import zipfile

import glio_noncode.api as api_module
from glio_noncode.api import ApiHandler, create_server
from glio_noncode.errors import ValidationError
from glio_noncode.module_certification import build_module_certification
from glio_noncode.module_certification_lineage import build_module_certification_lineage
from glio_noncode.module_certification_quality import build_module_certification_quality
from glio_noncode.module_inventory import build_module_inventory
from glio_noncode.module_workbench import (
    build_module_workbench,
    build_module_workbench_detail,
    module_workbench_csv,
    module_workbench_detail_capabilities,
    module_workbench_detail_schema,
    module_workbench_json,
    module_workbench_schema,
    query_module_workbench,
    render_module_workbench_markdown,
    verify_module_workbench,
)
from glio_noncode.module_workbench_cache import snapshot_from_mapping, snapshot_payload
from glio_noncode.module_workbench_observability import (
    build_module_workbench_observability,
    module_workbench_observability_capabilities,
    module_workbench_observability_schema,
)
from glio_noncode.module_workbench_audit import (
    audit_module_workbench,
    module_workbench_audit_csv,
    query_module_workbench_audit,
    verify_module_workbench_audit,
)
from glio_noncode.module_workbench_contracts import (
    ModuleWorkbenchDepthBand,
    ModuleWorkbenchRisk,
)
from glio_noncode.module_workbench_diff import (
    build_module_workbench_diff,
    module_workbench_diff_csv,
    query_module_workbench_diff,
    verify_module_workbench_diff,
)
from glio_noncode.module_workbench_execution import build_module_workbench_execution
from glio_noncode.module_workbench_execution_plan import (
    build_module_workbench_execution_plan,
    compare_module_workbench_execution_plans,
    module_workbench_execution_plan_capabilities,
    module_workbench_execution_plan_schema,
    query_module_workbench_execution_plan,
    verify_module_workbench_execution_plan,
)
from glio_noncode.module_workbench_policy import (
    build_module_workbench_policy,
    default_module_workbench_policy,
    evaluate_module_workbench_policy,
    module_workbench_policy_csv,
    query_module_workbench_policy,
    verify_module_workbench_gate,
    verify_module_workbench_policy,
)
from glio_noncode.module_workbench_portfolio import (
    build_module_workbench_portfolio,
    module_workbench_portfolio_capabilities,
    module_workbench_portfolio_schema,
    query_module_workbench_portfolio,
    verify_module_workbench_portfolio,
)
from glio_noncode.module_workbench_runtime import (
    module_workbench_runtime_csv,
    module_workbench_runtime_schema,
    query_module_workbench_runtime,
    run_module_workbench,
    verify_module_workbench_runtime,
)
from glio_noncode.module_workbench_triage import (
    build_module_workbench_triage,
    module_workbench_triage_capabilities,
    module_workbench_triage_csv,
    module_workbench_triage_schema,
    query_module_workbench_triage,
    render_module_workbench_triage_markdown,
    verify_module_workbench_triage,
)
from glio_noncode.module_workbench_triage_contracts import ModuleWorkbenchTriageItem


class ModuleWorkbenchFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.package = root / "src" / "glio_noncode"
        self.tests = root / "tests"
        self.docs = root / "docs"
        self.package.mkdir(parents=True)
        self.tests.mkdir()
        self.docs.mkdir()
        (self.package / "__init__.py").write_text(
            "from .core import public_core\nfrom .thin import public_thin\n",
            encoding="utf-8",
        )
        (self.package / "core.py").write_text(
            "\n".join(
                (
                    "from .thin import public_thin",
                    "class Core:",
                    "    def run(self):",
                    "        return public_thin()",
                    "",
                    "def public_core():",
                    "    return Core()",
                )
            ),
            encoding="utf-8",
        )
        (self.package / "thin.py").write_text(
            "def public_thin():\n    return 1\n",
            encoding="utf-8",
        )
        (self.tests / "test_core.py").write_text(
            "from glio_noncode.core import public_core\n",
            encoding="utf-8",
        )
        (self.docs / "MODULES.md").write_text(
            "# Modules\n\nThe core contract covers glio_noncode.core.\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def report(self):
        inventory = build_module_inventory(self.package, test_root=self.tests)
        matrix = build_module_certification(
            inventory,
            source_root=self.package,
            test_root=self.tests,
            docs_root=self.docs,
        )
        lineage = build_module_certification_lineage(
            inventory,
            matrix=matrix,
            source_root=self.package,
            test_root=self.tests,
            docs_root=self.docs,
        )
        quality = build_module_certification_quality(matrix, lineage)
        return build_module_workbench(inventory, matrix, lineage, quality)

    def test_api_workbench_context_reuses_and_invalidates_derived_chain(self) -> None:
        handler = object.__new__(ApiHandler)
        handler.server = type("Server", (), {})()
        inventory = object()
        matrix = object()
        lineage = object()
        quality = object()
        workbench = object()
        with (
            patch(
                "glio_noncode.api._module_inventory_source_signature",
                side_effect=[("stable",), ("stable",), ("changed",)],
            ),
            patch.object(
                handler,
                "_module_certification_context",
                return_value=(inventory, matrix, None, None, None),
            ) as certification_context,
            patch(
                "glio_noncode.api.build_module_certification_lineage",
                return_value=lineage,
            ) as lineage_builder,
            patch(
                "glio_noncode.api.build_module_certification_quality",
                return_value=quality,
            ) as quality_builder,
            patch(
                "glio_noncode.api.build_module_workbench",
                return_value=workbench,
            ) as workbench_builder,
        ):
            first = handler._module_workbench_context()
            second = handler._module_workbench_context()
            third = handler._module_workbench_context()

        self.assertIs(first, second)
        self.assertIsNot(second, third)
        self.assertEqual(certification_context.call_count, 2)
        self.assertEqual(lineage_builder.call_count, 2)
        self.assertEqual(quality_builder.call_count, 2)
        self.assertEqual(workbench_builder.call_count, 2)

    def test_api_workbench_context_invalidates_when_documentation_changes(self) -> None:
        handler = object.__new__(ApiHandler)
        handler.server = type("Server", (), {})()
        inventory = object()
        matrix = object()
        lineage = object()
        quality = object()
        workbench = object()
        source_signature = (
            ("0:alpha.py", 10, 100),
            ("1:test_core.py", 20, 200),
            ("2:MODULES.md", 30, 300),
        )
        changed_docs_signature = source_signature[:-1] + (("2:MODULES.md", 31, 301),)
        with (
            patch(
                "glio_noncode.api._module_inventory_source_signature",
                side_effect=[source_signature, source_signature, changed_docs_signature],
            ),
            patch.object(
                handler,
                "_module_certification_context",
                return_value=(inventory, matrix, None, None, None),
            ) as certification_context,
            patch(
                "glio_noncode.api.build_module_certification_lineage",
                return_value=lineage,
            ) as lineage_builder,
            patch(
                "glio_noncode.api.build_module_certification_quality",
                return_value=quality,
            ) as quality_builder,
            patch(
                "glio_noncode.api.build_module_workbench",
                return_value=workbench,
            ) as workbench_builder,
        ):
            first = handler._module_workbench_context()
            second = handler._module_workbench_context()
            third = handler._module_workbench_context()

        self.assertIs(first, second)
        self.assertIsNot(second, third)
        self.assertEqual(certification_context.call_count, 2)
        self.assertEqual(lineage_builder.call_count, 2)
        self.assertEqual(quality_builder.call_count, 2)
        self.assertEqual(workbench_builder.call_count, 2)

    def test_api_inventory_passes_previous_rows_for_incremental_rebuilds(self) -> None:
        handler = object.__new__(ApiHandler)
        handler.server = type("Server", (), {})()
        previous = object()
        current = object()
        first_signature = (
            ("0:alpha.py", 10, 100),
            ("1:test_core.py", 20, 200),
        )
        second_signature = (
            ("0:alpha.py", 10, 100),
            ("1:test_core.py", 21, 201),
        )
        with (
            patch(
                "glio_noncode.api._module_inventory_source_signature",
                side_effect=[first_signature, second_signature],
            ),
            patch(
                "glio_noncode.api.build_module_inventory",
                side_effect=[previous, current],
            ) as builder,
        ):
            handler._module_inventory(evidence={})
            handler._module_inventory(evidence={})

        self.assertIsNone(builder.call_args_list[0].kwargs["previous"])
        self.assertIs(builder.call_args_list[1].kwargs["previous"], previous)
        self.assertEqual(
            builder.call_args_list[1].kwargs["previous_source_signature"],
            {"alpha.py": (10, 100)},
        )
        self.assertEqual(
            builder.call_args_list[1].kwargs["source_signature"],
            {"alpha.py": (10, 100)},
        )

    def test_api_triage_context_reuses_and_invalidates_ranked_projection(self) -> None:
        handler = object.__new__(ApiHandler)
        handler.server = type("Server", (), {})()
        inventory = object()
        matrix = object()
        lineage = object()
        quality = object()
        workbench = object()
        triage = object()
        rebuilt_triage = object()
        with (
            patch(
                "glio_noncode.api._module_inventory_source_signature",
                side_effect=[("stable",), ("stable",), ("changed",)],
            ),
            patch.object(
                handler,
                "_module_workbench_context",
                return_value=(lineage, quality, workbench),
            ) as workbench_context,
            patch.object(
                handler,
                "_module_certification_context",
                return_value=(inventory, matrix, None, None, None),
            ) as certification_context,
            patch(
                "glio_noncode.api.build_module_workbench_triage",
                side_effect=[triage, rebuilt_triage],
            ) as triage_builder,
        ):
            first = handler._module_workbench_triage_context()
            second = handler._module_workbench_triage_context()
            third = handler._module_workbench_triage_context()

        self.assertIs(first, second)
        self.assertIsNot(second, third)
        self.assertEqual(workbench_context.call_count, 2)
        self.assertEqual(certification_context.call_count, 2)
        self.assertEqual(triage_builder.call_count, 2)

    def test_http_workbench_routes_skip_generic_certification_preamble(self) -> None:
        report = self.report()
        with (
            patch.object(
                ApiHandler,
                "_module_certification_context",
                side_effect=AssertionError("workbench route invoked certification preamble"),
            ),
            patch.object(
                ApiHandler,
                "_module_workbench_context",
                return_value=(None, None, report),
            ),
            tempfile.TemporaryDirectory() as data_root,
        ):
            server = create_server("127.0.0.1", 0, data_root)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=10)
                connection.request(
                    "GET",
                    "/v1/module-workbench/query?resource=modules&limit=1",
                )
                response = connection.getresponse()
                body = response.read().decode("utf-8")
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
        self.assertEqual(response.status, 200)
        self.assertIn('"total":3', body)

    def test_http_workbench_observability_route_is_bounded_and_path_free(self) -> None:
        observation = build_module_workbench_observability(
            rebuild_mode="incremental",
            cache_hit=False,
            source_file_count=3,
            test_file_count=1,
            module_count=3,
            task_count=7,
            reused_module_count=2,
            reparsed_module_count=1,
            inventory_address="module-inventory:inventory",
            certification_address="module-certification:matrix",
            lineage_address="module-certification-lineage:lineage",
            quality_address="module-certification-quality:quality",
            workbench_address="module-workbench:workbench",
            accepted=True,
        )
        with (
            patch.object(ApiHandler, "_module_workbench_observation", return_value=observation),
            tempfile.TemporaryDirectory() as data_root,
        ):
            server = create_server("127.0.0.1", 0, data_root)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=10)
                connection.request("GET", "/v1/module-workbench/observability")
                response = connection.getresponse()
                body = response.read().decode("utf-8")
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
        self.assertEqual(response.status, 200)
        self.assertIn('"rebuild_mode":"incremental"', body)
        self.assertIn('"reused_module_count":2', body)
        self.assertNotIn("source_root", body)
        self.assertNotIn(str(self.package), body)

    def test_module_workbench_observability_contract_is_addressed(self) -> None:
        value = build_module_workbench_observability(
            rebuild_mode="snapshot",
            cache_hit=True,
            source_file_count=2,
            test_file_count=1,
            module_count=2,
            task_count=4,
            reused_module_count=2,
            reparsed_module_count=0,
            inventory_address="inventory",
            certification_address="certification",
            lineage_address="lineage",
            quality_address="quality",
            workbench_address="workbench",
            accepted=True,
        )
        self.assertTrue(value.content_address.startswith("module-workbench-observability:"))
        self.assertEqual(module_workbench_observability_schema()["version"], "module-workbench-observability-v1")
        self.assertEqual(module_workbench_observability_capabilities()["operation_count"], 3)
        with self.assertRaises(ValidationError):
            build_module_workbench_observability(
                rebuild_mode="full",
                cache_hit=False,
                source_file_count=0,
                test_file_count=0,
                module_count=2,
                task_count=0,
                reused_module_count=2,
                reparsed_module_count=1,
                inventory_address="inventory",
                certification_address="certification",
                lineage_address="lineage",
                quality_address="quality",
                workbench_address="workbench",
                accepted=True,
            )

    def test_durable_snapshot_round_trip_verifies_every_upstream_plane(self) -> None:
        inventory = build_module_inventory(self.package, test_root=self.tests)
        matrix = build_module_certification(
            inventory,
            source_root=self.package,
            test_root=self.tests,
            docs_root=self.docs,
        )
        lineage = build_module_certification_lineage(
            inventory,
            matrix=matrix,
            source_root=self.package,
            test_root=self.tests,
            docs_root=self.docs,
        )
        quality = build_module_certification_quality(matrix, lineage)
        workbench = build_module_workbench(inventory, matrix, lineage, quality)
        signature = (("0:core.py", 10, 20), ("1:test_core.py", 11, 21))
        payload = snapshot_payload(signature, inventory, matrix, lineage, quality, workbench)
        restored = snapshot_from_mapping(payload, signature)
        fast_restored = snapshot_from_mapping(payload, signature, verify_nested=False)
        legacy_payload = dict(payload)
        legacy_payload.pop("payload_digest")
        legacy_restored = snapshot_from_mapping(legacy_payload, signature)
        self.assertEqual(restored[0].content_address, inventory.content_address)
        self.assertEqual(restored[1].content_address, matrix.content_address)
        self.assertEqual(restored[2].content_address, lineage.content_address)
        self.assertEqual(restored[3].content_address, quality.content_address)
        self.assertEqual(restored[4].content_address, workbench.content_address)
        self.assertEqual(fast_restored[4].content_address, workbench.content_address)
        self.assertEqual(legacy_restored[4].content_address, workbench.content_address)
        fast_legacy = snapshot_from_mapping(legacy_payload, signature, verify_nested=False)
        self.assertEqual(fast_legacy[4].content_address, workbench.content_address)
        with self.assertRaises(ValidationError):
            snapshot_from_mapping(payload, (("changed.py", 1, 1),))
        payload["workbench"]["overall_score"] = 0.0
        with self.assertRaises(ValidationError):
            snapshot_from_mapping(payload, signature)
        cache_directory = Path(self.directory.name) / "cache"
        cache_directory.mkdir()
        handler = object.__new__(ApiHandler)
        handler.server = type("Server", (), {
            "glio_module_workbench_cache_path": cache_directory / "snapshot.json.gz",
        })()
        handler._persist_module_workbench_snapshot(
            signature, inventory, matrix, lineage, quality, workbench
        )
        loaded = handler._load_module_workbench_snapshot(signature)
        assert loaded is not None
        self.assertEqual(loaded[4].content_address, workbench.content_address)
        previous = handler._load_module_workbench_previous_inventory()
        assert previous is not None
        self.assertEqual(previous[0].content_address, inventory.content_address)
        self.assertEqual(previous[1], signature)
        self.assertIsNone(handler._load_module_workbench_snapshot((('0:core.py', 10, 19),)))

    def test_stale_durable_snapshot_seeds_incremental_inventory_context(self) -> None:
        inventory = build_module_inventory(self.package, test_root=self.tests)
        matrix = build_module_certification(
            inventory,
            source_root=self.package,
            test_root=self.tests,
            docs_root=self.docs,
        )
        lineage = build_module_certification_lineage(
            inventory,
            matrix=matrix,
            source_root=self.package,
            test_root=self.tests,
            docs_root=self.docs,
        )
        quality = build_module_certification_quality(matrix, lineage)
        workbench = build_module_workbench(inventory, matrix, lineage, quality)
        signature = (("0:core.py", 10, 20), ("1:test_core.py", 11, 21))
        changed_signature = (("0:core.py", 10, 22), ("1:test_core.py", 11, 21))
        cache_directory = Path(self.directory.name) / "stale-cache"
        cache_directory.mkdir()
        handler = object.__new__(ApiHandler)
        handler.server = type(
            "Server",
            (),
            {"glio_module_workbench_cache_path": cache_directory / "snapshot.json.gz"},
        )()
        handler._persist_module_workbench_snapshot(
            signature, inventory, matrix, lineage, quality, workbench
        )
        rebuilt_lineage = object()
        rebuilt_quality = object()
        rebuilt_workbench = object()

        def certification_context(*, include_certification: bool, evidence: dict[str, object]):
            self.assertFalse(include_certification)
            inventory_state = handler.server.glio_module_inventory_snapshot
            self.assertEqual(inventory_state["inventory"].content_address, inventory.content_address)
            return inventory, matrix, None, None, None

        with (
            patch(
                "glio_noncode.api._module_inventory_source_signature",
                return_value=changed_signature,
            ),
            patch.object(
                handler,
                "_module_certification_context",
                side_effect=certification_context,
            ),
            patch(
                "glio_noncode.api.build_module_certification_lineage",
                return_value=rebuilt_lineage,
            ),
            patch(
                "glio_noncode.api.build_module_certification_quality",
                return_value=rebuilt_quality,
            ),
            patch(
                "glio_noncode.api.build_module_workbench",
                return_value=rebuilt_workbench,
            ),
            patch.object(handler, "_persist_module_workbench_snapshot"),
        ):
            result = handler._module_workbench_context()
        self.assertIs(result[0], rebuilt_lineage)
        self.assertIs(result[1], rebuilt_quality)
        self.assertIs(result[2], rebuilt_workbench)

    def test_module_workbench_detail_joins_all_review_planes(self) -> None:
        inventory = build_module_inventory(self.package, test_root=self.tests)
        matrix = build_module_certification(
            inventory,
            source_root=self.package,
            test_root=self.tests,
            docs_root=self.docs,
        )
        lineage = build_module_certification_lineage(
            inventory,
            matrix=matrix,
            source_root=self.package,
            test_root=self.tests,
            docs_root=self.docs,
        )
        quality = build_module_certification_quality(matrix, lineage)
        workbench = build_module_workbench(inventory, matrix, lineage, quality)
        detail = build_module_workbench_detail(
            inventory,
            matrix,
            lineage,
            quality,
            workbench,
            module_id="glio_noncode.core",
        )
        self.assertEqual(detail["schema"], "module-workbench-detail-v1")
        self.assertEqual(detail["summary"]["certification_state"], "certified")
        self.assertTrue(detail["assessment"]["module_id"].endswith(".core"))
        self.assertTrue(detail["tasks"])
        self.assertTrue(detail["evidence"])
        self.assertIn("upstream_addresses", detail)
        self.assertNotIn("source_text", str(detail))
        self.assertNotIn(str(self.package), str(detail))
        self.assertEqual(module_workbench_detail_schema()["schema"], "module-workbench-detail-v1")
        self.assertEqual(
            module_workbench_detail_capabilities()["operation_count"],
            len(module_workbench_detail_capabilities()["operations"]),
        )
        with self.assertRaises(ValidationError):
            build_module_workbench_detail(
                inventory,
                matrix,
                lineage,
                quality,
                workbench,
                module_id="glio_noncode.missing",
            )
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "detail.json"
            self.assertEqual(
                main(
                    [
                        "module-workbench-detail",
                        "--source-root",
                        str(self.package),
                        "--test-root",
                        str(self.tests),
                        "--docs-root",
                        str(self.docs),
                        "--module-id",
                        "glio_noncode.core",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            self.assertIn(
                "module-workbench-detail-v1",
                output.read_text(encoding="utf-8"),
            )

    def test_report_conserves_depth_risk_and_task_surfaces(self) -> None:
        report = self.report()
        verify_module_workbench(report)
        self.assertEqual(len(report.assessments), 3)
        self.assertEqual(report.blocked_count, 0)
        self.assertEqual(sum(report.risk_counts.values()), 3)
        self.assertTrue(report.tasks)
        self.assertTrue(report.families)
        self.assertIn(
            report.assessments[0].depth_band,
            tuple(ModuleWorkbenchDepthBand),
        )
        self.assertIn(report.assessments[0].risk, tuple(ModuleWorkbenchRisk))

    def test_queries_filter_modules_tasks_families_and_risks(self) -> None:
        report = self.report()
        modules = query_module_workbench(report, resource="modules", module_id="glio_noncode.core")
        self.assertEqual(modules["total"], 1)
        tasks = query_module_workbench(report, resource="tasks", text="coverage", limit=10)
        self.assertGreaterEqual(tasks["total"], 1)
        families = query_module_workbench(report, resource="families", limit=10)
        self.assertEqual(families["total"], len(report.families))
        risks = query_module_workbench(report, resource="risks", limit=10)
        self.assertEqual(sum(item["count"] for item in risks["items"]), 3)

    def test_triage_ranks_and_explains_module_review_pressure(self) -> None:
        inventory = build_module_inventory(self.package, test_root=self.tests)
        matrix = build_module_certification(
            inventory,
            source_root=self.package,
            test_root=self.tests,
            docs_root=self.docs,
        )
        lineage = build_module_certification_lineage(
            inventory,
            matrix=matrix,
            source_root=self.package,
            test_root=self.tests,
            docs_root=self.docs,
        )
        quality = build_module_certification_quality(matrix, lineage)
        report = build_module_workbench_triage(self.report(), matrix, lineage, quality)
        verify_module_workbench_triage(report)
        self.assertEqual(tuple(item.rank for item in report.items), (1, 2, 3))
        self.assertEqual(len(report.reason_counts), len(set(report.reason_counts)))
        self.assertTrue(report.items[0].reasons)
        self.assertLessEqual(report.items[0].priority_score, 1.0)
        filtered = query_module_workbench_triage(report, reason=report.items[0].reasons[0])
        self.assertGreaterEqual(filtered["total"], 1)
        self.assertIn("priority_score", module_workbench_triage_csv(report))
        self.assertIn("Module workbench triage", render_module_workbench_triage_markdown(report))
        self.assertEqual(
            module_workbench_triage_capabilities()["operation_count"],
            len(module_workbench_triage_capabilities()["operations"]),
        )
        self.assertEqual(module_workbench_triage_schema()["version"], "module-workbench-triage-v1")
        long_task_id = "module." + ("nested." * 60) + "add_test"
        long_item = ModuleWorkbenchTriageItem(
            rank=1,
            module_id="glio_noncode.core",
            family="core",
            role="implementation",
            risk="low",
            depth_band="deep",
            score=0.8,
            priority_score=0.2,
            fan_in=0,
            fan_out=0,
            gap_count=0,
            evidence_count=1,
            unresolved_edge_count=0,
            task_count=1,
            reasons=("low_score",),
            recommended_task_ids=(long_task_id,),
            content_address="triage-item-test",
        )
        self.assertEqual(long_item.recommended_task_ids[0], long_task_id)
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "triage.json"
            self.assertEqual(
                main(
                    [
                        "module-workbench-triage",
                        "--source-root",
                        str(self.package),
                        "--test-root",
                        str(self.tests),
                        "--docs-root",
                        str(self.docs),
                        "--format",
                        "summary",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            self.assertIn("module-workbench-triage-v1", output.read_text(encoding="utf-8"))

    def test_exports_are_stable_and_explainable(self) -> None:
        report = self.report()
        self.assertIn('"module_count":3', module_workbench_json(report))
        self.assertIn("module_id", module_workbench_csv(report))
        self.assertIn("Priority task queue", render_module_workbench_markdown(report))
        schema = module_workbench_schema()
        self.assertEqual(schema["boundary"], "public_aggregate_module_workbench")
        self.assertEqual(len(schema["task_kinds"]), 8)

    def test_policy_gate_and_audit_are_independently_verifiable(self) -> None:
        report = self.report()
        policy = default_module_workbench_policy()
        verify_module_workbench_policy(policy)
        gate = evaluate_module_workbench_policy(report, policy)
        verify_module_workbench_gate(gate)
        self.assertTrue(gate.checks)
        self.assertEqual(
            query_module_workbench_policy(gate, passed=False)["total"], gate.failed_count
        )
        self.assertIn("check_id", module_workbench_policy_csv(gate))

        audit = audit_module_workbench(report)
        verify_module_workbench_audit(audit)
        self.assertTrue(audit.checks)
        self.assertEqual(
            query_module_workbench_audit(audit, passed=False)["total"], audit.failed_count
        )
        self.assertIn("boundary-keys", module_workbench_audit_csv(audit))

    def test_diff_is_stable_for_the_same_snapshot(self) -> None:
        report = self.report()
        diff = build_module_workbench_diff(report, report)
        verify_module_workbench_diff(diff)
        self.assertEqual(diff.unchanged_count, len(report.assessments))
        self.assertEqual(diff.changed_count, 0)
        self.assertEqual(diff.task_delta, 0)
        self.assertEqual(
            query_module_workbench_diff(diff, kind="unchanged")["total"], len(report.assessments)
        )
        self.assertIn("previous_score", module_workbench_diff_csv(diff))

    def test_cli_and_api_contract_surfaces_are_registered(self) -> None:
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as directory:
            schema_path = Path(directory) / "schema.json"
            caps_path = Path(directory) / "caps.json"
            detail_schema_path = Path(directory) / "detail-schema.json"
            detail_caps_path = Path(directory) / "detail-caps.json"
            triage_schema_path = Path(directory) / "triage-schema.json"
            triage_caps_path = Path(directory) / "triage-caps.json"
            self.assertEqual(main(["module-workbench-schema", "--output", str(schema_path)]), 0)
            self.assertEqual(
                main(["module-workbench-policy-capabilities", "--output", str(caps_path)]),
                0,
            )
            observability_schema_path = Path(directory) / "observability-schema.json"
            observability_caps_path = Path(directory) / "observability-caps.json"
            observability_path = Path(directory) / "observability.json"
            cache_root = Path(directory) / "workbench-cache"
            cached_first_path = Path(directory) / "observability-first.json"
            cached_second_path = Path(directory) / "observability-second.json"
            cached_incremental_path = Path(directory) / "observability-incremental.json"
            self.assertEqual(
                main(
                    [
                        "module-workbench-observability-schema",
                        "--output",
                        str(observability_schema_path),
                    ]
                ),
                0,
            )
            for output in (cached_first_path, cached_second_path):
                self.assertEqual(
                    main(
                        [
                            "module-workbench-observability",
                            "--source-root",
                            str(self.package),
                            "--test-root",
                            str(self.tests),
                            "--docs-root",
                            str(self.docs),
                            "--cache-root",
                            str(cache_root),
                            "--output",
                            str(output),
                        ]
                    ),
                    0,
                )
            self.assertEqual(
                main(
                    [
                        "module-workbench-observability-capabilities",
                        "--output",
                        str(observability_caps_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-observability",
                        "--source-root",
                        str(self.package),
                        "--test-root",
                        str(self.tests),
                        "--docs-root",
                        str(self.docs),
                        "--output",
                        str(observability_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-detail-schema",
                        "--output",
                        str(detail_schema_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-triage-schema",
                        "--output",
                        str(triage_schema_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-triage-capabilities",
                        "--output",
                        str(triage_caps_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-detail-capabilities",
                        "--output",
                        str(detail_caps_path),
                    ]
                ),
                0,
            )
            self.assertIn(
                "public_aggregate_module_workbench", schema_path.read_text(encoding="utf-8")
            )
            self.assertIn("operations", caps_path.read_text(encoding="utf-8"))
            self.assertIn(
                "module-workbench-observability-v1",
                observability_schema_path.read_text(encoding="utf-8"),
            )
            self.assertIn("operations", observability_caps_path.read_text(encoding="utf-8"))
            observation = json.loads(observability_path.read_text(encoding="utf-8"))
            self.assertEqual(observation["rebuild_mode"], "full")
            self.assertFalse(observation["cache_hit"])
            self.assertEqual(observation["reused_module_count"], 0)
            self.assertEqual(observation["reparsed_module_count"], 3)
            self.assertEqual(observation["source_file_count"], 3)
            self.assertEqual(observation["test_file_count"], 1)
            first_cached = json.loads(cached_first_path.read_text(encoding="utf-8"))
            second_cached = json.loads(cached_second_path.read_text(encoding="utf-8"))
            self.assertEqual(first_cached["rebuild_mode"], "full")
            self.assertFalse(first_cached["cache_hit"])
            self.assertEqual(first_cached["reparsed_module_count"], 3)
            self.assertEqual(second_cached["rebuild_mode"], "snapshot")
            self.assertTrue(second_cached["cache_hit"])
            self.assertEqual(second_cached["reused_module_count"], 3)
            self.assertEqual(second_cached["reparsed_module_count"], 0)
            (self.package / "thin.py").write_text(
                "def public_thin():\n    return 2\n",
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-observability",
                        "--source-root",
                        str(self.package),
                        "--test-root",
                        str(self.tests),
                        "--docs-root",
                        str(self.docs),
                        "--cache-root",
                        str(cache_root),
                        "--output",
                        str(cached_incremental_path),
                    ]
                ),
                0,
            )
            incremental = json.loads(cached_incremental_path.read_text(encoding="utf-8"))
            self.assertEqual(incremental["rebuild_mode"], "incremental")
            self.assertFalse(incremental["cache_hit"])
            self.assertEqual(incremental["reused_module_count"], 2)
            self.assertEqual(incremental["reparsed_module_count"], 1)
            self.assertIn(
                "module-workbench-detail-v1",
                detail_schema_path.read_text(encoding="utf-8"),
            )
            self.assertIn("operations", detail_caps_path.read_text(encoding="utf-8"))
            self.assertIn("module-workbench-triage-v1", triage_schema_path.read_text(encoding="utf-8"))
            self.assertIn("operations", triage_caps_path.read_text(encoding="utf-8"))
        server = create_server(host="127.0.0.1", port=0)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = HTTPConnection("127.0.0.1", server.server_port, timeout=10)
            for route, key in (
                ("/v1/module-workbench/schema", "boundary"),
                ("/v1/module-workbench/detail/schema", "required"),
                ("/v1/module-workbench/policy/schema", "boundary"),
                ("/v1/module-workbench/audit/capabilities", "operations"),
                ("/v1/module-workbench/detail/capabilities", "operations"),
                ("/v1/module-workbench/diff/capabilities", "operations"),
                ("/v1/module-workbench/runtime/schema", "stage_order"),
                ("/v1/module-workbench/portfolio/schema", "selection"),
                ("/v1/module-workbench/triage/schema", "reason_codes"),
                ("/v1/module-workbench/triage/capabilities", "operations"),
            ):
                connection.request("GET", route)
                response = connection.getresponse()
                payload = response.read().decode("utf-8")
                self.assertEqual(response.status, 200)
                self.assertIn(key, payload)
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=10)

    def test_http_module_workbench_detail_route(self) -> None:
        inventory = build_module_inventory(self.package, test_root=self.tests)
        matrix = build_module_certification(
            inventory,
            source_root=self.package,
            test_root=self.tests,
            docs_root=self.docs,
        )
        lineage = build_module_certification_lineage(
            inventory,
            matrix=matrix,
            source_root=self.package,
            test_root=self.tests,
            docs_root=self.docs,
        )
        quality = build_module_certification_quality(matrix, lineage)
        workbench = build_module_workbench(inventory, matrix, lineage, quality)
        server = create_server(host="127.0.0.1", port=0)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with (
                patch.object(
                    ApiHandler,
                    "_module_certification_context",
                    return_value=(inventory, matrix, None, None, None),
                ),
                patch.object(
                    ApiHandler,
                    "_module_workbench_context",
                    return_value=(lineage, quality, workbench),
                ),
            ):
                connection = HTTPConnection("127.0.0.1", server.server_port, timeout=10)
                connection.request(
                    "GET",
                    "/v1/module-workbench/detail?module_id=glio_noncode.core",
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                payload = response.read().decode("utf-8")
                self.assertIn('"schema":"module-workbench-detail-v1"', payload)
                self.assertIn('"module_id":"glio_noncode.core"', payload)
                connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=10)

    def test_http_module_workbench_triage_route(self) -> None:
        inventory = build_module_inventory(self.package, test_root=self.tests)
        matrix = build_module_certification(
            inventory,
            source_root=self.package,
            test_root=self.tests,
            docs_root=self.docs,
        )
        lineage = build_module_certification_lineage(
            inventory,
            matrix=matrix,
            source_root=self.package,
            test_root=self.tests,
            docs_root=self.docs,
        )
        quality = build_module_certification_quality(matrix, lineage)
        workbench = build_module_workbench(inventory, matrix, lineage, quality)
        server = create_server(host="127.0.0.1", port=0)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            triage = build_module_workbench_triage(workbench, matrix, lineage, quality)
            with (
                patch.object(
                    ApiHandler,
                    "_module_workbench_triage_context",
                    return_value=triage,
                ),
            ):
                connection = HTTPConnection("127.0.0.1", server.server_port, timeout=10)
                connection.request("GET", "/v1/module-workbench/triage?format=summary")
                response = connection.getresponse()
                payload = response.read().decode("utf-8")
                connection.close()
            self.assertEqual(response.status, 200)
            self.assertIn('"version":"module-workbench-triage-v1"', payload)
            self.assertIn('"item_count":3', payload)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=10)

    def test_http_execution_command_is_evidence_gated_and_replayed(self) -> None:
        report = self.report()
        with tempfile.TemporaryDirectory() as data_root:
            with patch.object(ApiHandler, "_module_workbench_context", return_value=(None, None, report)):
                server = create_server(host="127.0.0.1", port=0, data_root=data_root)
                thread = Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    host, port = server.server_address
                    connection = HTTPConnection(host, port, timeout=30)
                    connection.request("GET", "/v1/module-workbench/execution/query?resource=items&state=ready&limit=1")
                    response = connection.getresponse()
                    ready_payload = json.loads(response.read().decode("utf-8"))
                    self.assertEqual(response.status, 200)
                    self.assertGreaterEqual(ready_payload["total"], 1)
                    task_id = ready_payload["items"][0]["task_id"]
                    ledger_address = ready_payload["ledger_address"]
                    connection.request(
                        "POST",
                        "/v1/module-workbench/execution/command",
                        body=json.dumps(
                            {
                                "task_id": task_id,
                                "action": "start",
                                "detail": "begin bounded implementation task",
                                "expected_ledger_address": ledger_address,
                            }
                        ),
                        headers={"Content-Type": "application/json"},
                    )
                    response = connection.getresponse()
                    started_payload = json.loads(response.read().decode("utf-8"))
                    self.assertEqual(response.status, 201)
                    self.assertEqual(started_payload["event"]["to_state"], "in_progress")
                    self.assertEqual(started_payload["event_count"], 1)
                    self.assertEqual(started_payload["derived_events"], [])
                    self.assertEqual(started_payload["journal"]["command_count"], 1)
                    current_ledger_address = started_payload["ledger"]["content_address"]
                    connection.request(
                        "GET",
                        "/v1/module-workbench/execution/packet?include_payloads=true",
                    )
                    packet_response = connection.getresponse()
                    packet_payload = json.loads(packet_response.read().decode("utf-8"))
                    self.assertEqual(packet_response.status, 200)
                    self.assertEqual(packet_payload["ledger_address"], current_ledger_address)
                    command_artifact = next(
                        item
                        for item in packet_payload["artifacts"]
                        if item["artifact_id"] == "commands"
                    )
                    command_trace = json.loads(command_artifact["payload"])
                    self.assertEqual(command_trace["command_count"], 1)
                    self.assertEqual(command_trace["event_count"], 1)
                    self.assertEqual(command_trace["ledger_address"], current_ledger_address)
                    packet_address = packet_payload["content_address"]
                    for packet_projection_path, address_field in (
                        ("/v1/module-workbench/execution/packet/release?format=summary", "packet_address"),
                        ("/v1/module-workbench/execution/packet/runtime?include_stages=false", "packet_address"),
                        ("/v1/module-workbench/execution/packet/inspection?format=summary", "packet_address"),
                        ("/v1/module-workbench/execution/packet/archive?format=summary", "packet_address"),
                    ):
                        connection.request("GET", packet_projection_path)
                        projection_response = connection.getresponse()
                        projection_payload = json.loads(
                            projection_response.read().decode("utf-8")
                        )
                        self.assertEqual(projection_response.status, 200)
                        self.assertEqual(projection_payload[address_field], packet_address)
                    connection.request(
                        "GET",
                        "/v1/module-workbench/execution/packet/archive.zip",
                    )
                    archive_response = connection.getresponse()
                    archive_payload = archive_response.read()
                    self.assertEqual(archive_response.status, 200)
                    self.assertEqual(archive_response.getheader("Content-Type"), "application/zip")
                    self.assertIn(
                        'attachment; filename="glio-noncode-execution-packet.zip"',
                        archive_response.getheader("Content-Disposition", ""),
                    )
                    self.assertEqual(
                        archive_response.getheader("X-GLIO-Packet-Address"),
                        packet_address,
                    )
                    self.assertTrue(archive_payload.startswith(b"PK"))
                    with zipfile.ZipFile(io.BytesIO(archive_payload)) as archive_reader:
                        self.assertIn("manifest.json", archive_reader.namelist())
                        self.assertIn("commands.json", archive_reader.namelist())
                    for downstream_path in (
                        "/v1/module-workbench/execution/audit",
                        "/v1/module-workbench/execution/policy",
                        "/v1/module-workbench/execution/review",
                    ):
                        connection.request("GET", downstream_path)
                        downstream_response = connection.getresponse()
                        downstream_payload = json.loads(
                            downstream_response.read().decode("utf-8")
                        )
                        self.assertEqual(downstream_response.status, 200)
                        self.assertEqual(
                            downstream_payload["ledger_address"],
                            current_ledger_address,
                        )
                    connection.request(
                        "GET",
                        "/v1/module-workbench/execution/plan/query?resource=summary&limit=1",
                    )
                    plan_response = connection.getresponse()
                    plan_payload = json.loads(plan_response.read().decode("utf-8"))
                    self.assertEqual(plan_response.status, 200)
                    self.assertEqual(plan_payload["total"], 1)
                    self.assertEqual(plan_payload["items"][0]["ledger_address"], current_ledger_address)
                    self.assertEqual(
                        plan_payload["items"][0]["content_address"],
                        plan_payload["plan_address"],
                    )
                    connection.request(
                        "GET",
                        "/v1/module-workbench/execution/plan/query?resource=dependencies&limit=10",
                    )
                    dependencies_response = connection.getresponse()
                    dependencies_payload = json.loads(
                        dependencies_response.read().decode("utf-8")
                    )
                    self.assertEqual(dependencies_response.status, 200)
                    self.assertEqual(
                        dependencies_payload["plan_address"],
                        plan_payload["plan_address"],
                    )
                    connection.request(
                        "GET",
                        "/v1/module-workbench/execution/plan/preview/query?resource=summary&capacity=9&max_tasks_per_module=3&limit=1",
                    )
                    preview_response = connection.getresponse()
                    preview_payload = json.loads(preview_response.read().decode("utf-8"))
                    self.assertEqual(preview_response.status, 200)
                    self.assertEqual(preview_payload["mode"], "preview")
                    self.assertEqual(preview_payload["selection"]["capacity"], 9)
                    self.assertEqual(preview_payload["selection"]["max_tasks_per_module"], 3)
                    self.assertTrue(preview_payload["preview_address"])
                    self.assertEqual(
                        preview_payload["comparison"]["candidate_plan_address"],
                        preview_payload["plan_address"],
                    )
                    self.assertIn("added_task_count", preview_payload["comparison"])
                    self.assertGreater(
                        preview_payload["items"][0]["dependency_edge_count"],
                        0,
                    )
                    connection.close()
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=10)

            with patch.object(ApiHandler, "_module_workbench_context", return_value=(None, None, report)):
                server = create_server(host="127.0.0.1", port=0, data_root=data_root)
                thread = Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    host, port = server.server_address
                    connection = HTTPConnection(host, port, timeout=30)
                    connection.request(
                        "GET",
                        f"/v1/module-workbench/execution/query?resource=items&task_id={task_id}&limit=1",
                    )
                    response = connection.getresponse()
                    replayed = json.loads(response.read().decode("utf-8"))
                    connection.close()
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=10)
            self.assertEqual(response.status, 200)
            self.assertEqual(replayed["items"][0]["state"], "in_progress")
            self.assertEqual(replayed["items"][0]["event_count"], 1)

    def test_execution_packet_and_archive_projections_reuse_immutable_cache(self) -> None:
        report = self.report()
        with tempfile.TemporaryDirectory() as data_root:
            server = create_server(host="127.0.0.1", port=0, data_root=data_root)
            try:
                handler = object.__new__(ApiHandler)
                handler.server = server
                with (
                    patch.object(
                        ApiHandler,
                        "_module_workbench_context",
                        return_value=(None, None, report),
                    ),
                    patch.object(
                        api_module,
                        "build_module_workbench_execution_packet",
                        wraps=api_module.build_module_workbench_execution_packet,
                    ) as packet_builder,
                    patch.object(
                        api_module,
                        "build_module_workbench_execution_packet_archive",
                        wraps=api_module.build_module_workbench_execution_packet_archive,
                    ) as archive_builder,
                ):
                    first_packet = handler._module_workbench_durable_packet(report)
                    second_packet = handler._module_workbench_durable_packet(report)
                    first_archive = handler._module_workbench_durable_archive(report)
                    second_archive = handler._module_workbench_durable_archive(report)
                self.assertIs(first_packet, second_packet)
                self.assertIs(first_archive, second_archive)
                self.assertEqual(packet_builder.call_count, 1)
                self.assertEqual(archive_builder.call_count, 1)
                self.assertEqual(first_archive.packet_address, first_packet.content_address)
            finally:
                server.server_close()

    def test_http_execution_command_batch_is_atomic_and_durable(self) -> None:
        report = self.report()
        with tempfile.TemporaryDirectory() as data_root:
            with patch.object(ApiHandler, "_module_workbench_context", return_value=(None, None, report)):
                server = create_server(host="127.0.0.1", port=0, data_root=data_root)
                thread = Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    host, port = server.server_address
                    connection = HTTPConnection(host, port, timeout=30)
                    connection.request(
                        "GET",
                        "/v1/module-workbench/execution/query?resource=items&state=ready&limit=2",
                    )
                    response = connection.getresponse()
                    ready_payload = json.loads(response.read().decode("utf-8"))
                    self.assertEqual(response.status, 200)
                    self.assertGreaterEqual(ready_payload["total"], 2)
                    ready_items = ready_payload["items"][:2]
                    ledger_address = ready_payload["ledger_address"]

                    for metadata_path in (
                        "/v1/module-workbench/execution/commands/schema",
                        "/v1/module-workbench/execution/commands/capabilities",
                    ):
                        connection.request("GET", metadata_path)
                        metadata_response = connection.getresponse()
                        metadata_payload = json.loads(metadata_response.read().decode("utf-8"))
                        self.assertEqual(metadata_response.status, 200)
                        if metadata_path.endswith("/schema"):
                            self.assertTrue(metadata_payload["batch"]["atomic"])
                            self.assertEqual(metadata_payload["batch"]["maximum_commands"], 128)
                        else:
                            self.assertTrue(metadata_payload["atomic_batch"])
                            self.assertEqual(metadata_payload["maximum_batch_commands"], 128)

                    commands = [
                        {
                            "task_id": item["task_id"],
                            "action": "start",
                            "detail": f"start bounded batch task {index}",
                        }
                        for index, item in enumerate(ready_items)
                    ]
                    connection.request(
                        "POST",
                        "/v1/module-workbench/execution/commands",
                        body=json.dumps(
                            {
                                "expected_ledger_address": ledger_address,
                                "commands": commands + [
                                    {
                                        "task_id": "missing-task",
                                        "action": "start",
                                        "detail": "this command must roll back the batch",
                                    }
                                ],
                            }
                        ),
                        headers={"Content-Type": "application/json"},
                    )
                    response = connection.getresponse()
                    rejected_payload = json.loads(response.read().decode("utf-8"))
                    self.assertEqual(response.status, 422)
                    self.assertEqual(rejected_payload["error"], "validation_error")

                    connection.request(
                        "GET",
                        f"/v1/module-workbench/execution/query?resource=items&task_id={ready_items[0]['task_id']}&limit=1",
                    )
                    rollback_response = connection.getresponse()
                    rollback_payload = json.loads(rollback_response.read().decode("utf-8"))
                    self.assertEqual(rollback_response.status, 200)
                    self.assertEqual(rollback_payload["items"][0]["state"], "ready")
                    self.assertEqual(rollback_payload["items"][0]["event_count"], 0)
                    self.assertEqual(rollback_payload["ledger_address"], ledger_address)

                    connection.request(
                        "POST",
                        "/v1/module-workbench/execution/commands",
                        body=json.dumps(
                            {
                                "expected_ledger_address": ledger_address,
                                "commands": commands,
                            }
                        ),
                        headers={"Content-Type": "application/json"},
                    )
                    response = connection.getresponse()
                    accepted_payload = json.loads(response.read().decode("utf-8"))
                    self.assertEqual(response.status, 201)
                    self.assertTrue(accepted_payload["atomic"])
                    self.assertEqual(accepted_payload["batch_count"], 2)
                    self.assertEqual(accepted_payload["event_count"], 2)
                    self.assertEqual(accepted_payload["derived_event_count"], 0)
                    self.assertEqual(len(accepted_payload["events"]), 2)
                    self.assertEqual(
                        [event["to_state"] for event in accepted_payload["events"]],
                        ["in_progress", "in_progress"],
                    )
                    self.assertEqual(accepted_payload["journal"]["command_count"], 2)
                    current_ledger_address = accepted_payload["ledger"]["content_address"]
                    self.assertNotEqual(current_ledger_address, ledger_address)
                    connection.close()
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=10)

            with patch.object(ApiHandler, "_module_workbench_context", return_value=(None, None, report)):
                server = create_server(host="127.0.0.1", port=0, data_root=data_root)
                thread = Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    host, port = server.server_address
                    connection = HTTPConnection(host, port, timeout=30)
                    connection.request(
                        "GET",
                        f"/v1/module-workbench/execution/query?resource=items&task_id={ready_items[0]['task_id']}&limit=1",
                    )
                    replay_response = connection.getresponse()
                    replayed = json.loads(replay_response.read().decode("utf-8"))
                    connection.close()
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=10)
            self.assertEqual(replay_response.status, 200)
            self.assertEqual(replayed["items"][0]["state"], "in_progress")
            self.assertEqual(replayed["items"][0]["event_count"], 1)
            self.assertEqual(replayed["ledger_address"], current_ledger_address)

    def test_runtime_runs_the_complete_static_chain_once(self) -> None:
        runtime = run_module_workbench(
            self.package,
            test_root=self.tests,
            docs_root=self.docs,
        )
        verify_module_workbench_runtime(runtime)
        self.assertEqual(runtime.completed_count + runtime.blocked_count, len(runtime.stages))
        self.assertEqual(query_module_workbench_runtime(runtime)["total"], len(runtime.stages))
        self.assertIn("kind", module_workbench_runtime_csv(runtime))
        self.assertEqual(
            module_workbench_runtime_schema()["stage_order"],
            ["inventory", "certification", "lineage", "quality", "workbench", "policy", "audit"],
        )

    def test_portfolio_selection_respects_capacity_and_risk_filters(self) -> None:
        report = self.report()
        portfolio = build_module_workbench_portfolio(
            report,
            capacity=2,
            max_tasks_per_module=1,
            maximum_priority=55,
        )
        verify_module_workbench_portfolio(portfolio)
        self.assertLessEqual(len(portfolio.selected_tasks), 2)
        self.assertLessEqual(
            len({item.module_id for item in portfolio.selected_tasks}),
            len(portfolio.selected_tasks),
        )
        self.assertEqual(
            query_module_workbench_portfolio(portfolio, limit=10)["total"],
            len(portfolio.selected_tasks),
        )
        portfolio_page = query_module_workbench_portfolio(portfolio, limit=10)
        self.assertEqual(
            portfolio_page["portfolio_summary"]["content_address"],
            portfolio.content_address,
        )
        self.assertEqual(
            portfolio_page["portfolio_summary"]["deferred_task_count"],
            portfolio.deferred_task_count,
        )
        self.assertTrue(portfolio.dependency_safe)
        self.assertEqual(module_workbench_portfolio_schema()["selection"][0], "capacity")
        self.assertEqual(
            module_workbench_portfolio_capabilities()["operation_count"],
            len(module_workbench_portfolio_capabilities()["operations"]),
        )

    def test_execution_plan_exposes_dependency_and_state_context(self) -> None:
        report = self.report()
        portfolio = build_module_workbench_portfolio(
            report,
            capacity=len(report.tasks),
            max_tasks_per_module=len(report.tasks),
        )
        ledger = build_module_workbench_execution(report, portfolio)
        plan = build_module_workbench_execution_plan(report, portfolio, ledger)
        verify_module_workbench_execution_plan(plan)
        summary = query_module_workbench_execution_plan(plan, resource="summary", limit=1)
        dependencies = query_module_workbench_execution_plan(
            plan,
            resource="dependencies",
            limit=100,
        )
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["items"][0]["content_address"], plan.content_address)
        self.assertEqual(
            plan.dependency_edge_count,
            plan.selected_prerequisite_count
            + plan.deferred_prerequisite_count
            + plan.unknown_prerequisite_count,
        )
        self.assertEqual(
            len(dependencies["items"]),
            plan.dependency_edge_count,
        )
        self.assertGreater(plan.dependency_edge_count, 0)
        self.assertGreater(plan.max_depth, 0)
        self.assertTrue(portfolio.dependency_safe)
        self.assertEqual(
            module_workbench_execution_plan_capabilities()["operation_count"],
            len(module_workbench_execution_plan_capabilities()["operations"]),
        )
        self.assertEqual(
            module_workbench_execution_plan_schema()["resources"],
            ["nodes", "dependencies", "critical_path", "summary"],
        )
        self.assertFalse(
            module_workbench_execution_plan_schema()["preview"]["durable_ledger_mutation"]
        )
        self.assertIn(
            "preview_alternate_capacity",
            module_workbench_execution_plan_capabilities()["operations"],
        )
        baseline_portfolio = build_module_workbench_portfolio(
            report,
            capacity=2,
            max_tasks_per_module=1,
        )
        baseline_ledger = build_module_workbench_execution(report, baseline_portfolio)
        baseline_plan = build_module_workbench_execution_plan(
            report,
            baseline_portfolio,
            baseline_ledger,
        )
        comparison = compare_module_workbench_execution_plans(baseline_plan, plan)
        self.assertEqual(comparison["baseline_plan_address"], baseline_plan.content_address)
        self.assertEqual(comparison["candidate_plan_address"], plan.content_address)
        self.assertTrue(comparison["selection_changed"])
        self.assertTrue(comparison["content_address"])

    def test_strict_policy_exposes_failed_thresholds_without_hiding_rows(self) -> None:
        report = self.report()
        strict = build_module_workbench_policy(
            minimum_overall_score=0.99,
            minimum_depth_percent=99.0,
            maximum_high_risk_count=0,
            minimum_test_references=2,
            minimum_evidence_count=4,
        )
        gate = evaluate_module_workbench_policy(report, strict)
        self.assertFalse(gate.accepted)
        self.assertGreater(gate.failed_count, 1)
        self.assertEqual(
            query_module_workbench_policy(gate, passed=False, limit=100)["total"],
            gate.failed_count,
        )

    def test_audit_detects_a_tampered_report_address(self) -> None:
        from dataclasses import replace

        report = self.report()
        audit = audit_module_workbench(report)
        tampered = replace(audit, report_address="tampered-report-address")
        self.assertFalse(
            query_module_workbench_audit(
                audit_module_workbench(report),
                text="does-not-match",
            )["items"]
        )
        with self.assertRaises(ValidationError):
            verify_module_workbench_audit(tampered)

    def test_portfolio_rejects_invalid_bounds_and_filters_risk(self) -> None:
        report = self.report()
        with self.assertRaises(ValidationError):
            build_module_workbench_portfolio(report, capacity=0)
        with self.assertRaises(ValidationError):
            build_module_workbench_portfolio(report, risks=("unknown",))
        risk = report.assessments[0].risk.value
        portfolio = build_module_workbench_portfolio(
            report,
            capacity=10,
            risks=(risk,),
        )
        module_risks = {item.module_id: item.risk.value for item in report.assessments}
        self.assertTrue(
            all(module_risks[task.module_id] == risk for task in portfolio.selected_tasks)
        )

    def test_diff_classifies_an_added_module(self) -> None:
        left = self.report()
        (self.package / "added.py").write_text(
            "def public_added():\n    return 3\n",
            encoding="utf-8",
        )
        right = self.report()
        diff = build_module_workbench_diff(left, right)
        verify_module_workbench_diff(diff)
        added = [item for item in diff.changes if item.module_id.endswith(".added")]
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0].kind.value, "added")
        self.assertGreaterEqual(diff.task_delta, 0)


if __name__ == "__main__":
    unittest.main()
