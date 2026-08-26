"""Contract and query tests for module-by-module workbench planning."""

from __future__ import annotations

import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.errors import ValidationError
from glio_noncode.module_certification import build_module_certification
from glio_noncode.module_certification_lineage import build_module_certification_lineage
from glio_noncode.module_certification_quality import build_module_certification_quality
from glio_noncode.module_inventory import build_module_inventory
from glio_noncode.module_workbench import (
    build_module_workbench,
    module_workbench_csv,
    module_workbench_json,
    module_workbench_schema,
    query_module_workbench,
    render_module_workbench_markdown,
    verify_module_workbench,
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
            self.assertEqual(main(["module-workbench-schema", "--output", str(schema_path)]), 0)
            self.assertEqual(
                main(["module-workbench-policy-capabilities", "--output", str(caps_path)]),
                0,
            )
            self.assertIn(
                "public_aggregate_module_workbench", schema_path.read_text(encoding="utf-8")
            )
            self.assertIn("operations", caps_path.read_text(encoding="utf-8"))
        server = create_server(host="127.0.0.1", port=0)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = HTTPConnection("127.0.0.1", server.server_port, timeout=10)
            for route, key in (
                ("/v1/module-workbench/schema", "boundary"),
                ("/v1/module-workbench/policy/schema", "boundary"),
                ("/v1/module-workbench/audit/capabilities", "operations"),
                ("/v1/module-workbench/diff/capabilities", "operations"),
                ("/v1/module-workbench/runtime/schema", "stage_order"),
                ("/v1/module-workbench/portfolio/schema", "selection"),
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
        self.assertEqual(module_workbench_portfolio_schema()["selection"][0], "capacity")
        self.assertEqual(
            module_workbench_portfolio_capabilities()["operation_count"],
            len(module_workbench_portfolio_capabilities()["operations"]),
        )

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
