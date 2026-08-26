"""Regression coverage for evidence-gated module-workbench execution."""

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
from glio_noncode.module_workbench import build_module_workbench
from glio_noncode.module_workbench_execution import (
    apply_module_workbench_execution_command,
    apply_module_workbench_execution_commands,
    build_module_workbench_execution,
    execution_command,
    module_workbench_execution_capabilities,
    module_workbench_execution_csv,
    module_workbench_execution_json,
    module_workbench_execution_schema,
    query_module_workbench_execution,
    render_module_workbench_execution_markdown,
    verify_module_workbench_execution,
)
from glio_noncode.module_workbench_execution_audit import (
    audit_module_workbench_execution,
    module_workbench_execution_audit_capabilities,
    module_workbench_execution_audit_csv,
    module_workbench_execution_audit_json,
    module_workbench_execution_audit_schema,
    query_module_workbench_execution_audit,
    verify_module_workbench_execution_audit,
)
from glio_noncode.module_workbench_execution_contracts import (
    ModuleWorkbenchExecutionAction,
    ModuleWorkbenchExecutionState,
)
from glio_noncode.module_workbench_execution_diff import (
    build_module_workbench_execution_diff,
    module_workbench_execution_diff_capabilities,
    module_workbench_execution_diff_csv,
    module_workbench_execution_diff_json,
    module_workbench_execution_diff_schema,
    query_module_workbench_execution_diff,
    verify_module_workbench_execution_diff,
)
from glio_noncode.module_workbench_execution_policy import (
    build_module_workbench_execution_policy,
    evaluate_module_workbench_execution_policy,
    module_workbench_execution_policy_capabilities,
    module_workbench_execution_policy_csv,
    module_workbench_execution_policy_json,
    module_workbench_execution_policy_schema,
    module_workbench_execution_policy_summary,
    query_module_workbench_execution_policy,
    verify_module_workbench_execution_policy,
    verify_module_workbench_execution_policy_gate,
)
from glio_noncode.module_workbench_execution_runtime import (
    module_workbench_execution_runtime_capabilities,
    module_workbench_execution_runtime_csv,
    module_workbench_execution_runtime_json,
    module_workbench_execution_runtime_schema,
    query_module_workbench_execution_runtime,
    run_module_workbench_execution,
    verify_module_workbench_execution_runtime,
)
from glio_noncode.module_workbench_portfolio import build_module_workbench_portfolio


class ModuleWorkbenchExecutionFixture(unittest.TestCase):
    """Small source graph with enough task variety to exercise transitions."""

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
        (self.package / "isolated.py").write_text(
            "def isolated_value():\n    return 2\n",
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

    def ledger(self):
        report = self.report()
        portfolio = build_module_workbench_portfolio(
            report,
            capacity=100,
            max_tasks_per_module=8,
        )
        return report, build_module_workbench_execution(report, portfolio)

    def test_plan_has_ready_and_prerequisite_tasks(self) -> None:
        _report, ledger = self.ledger()
        verify_module_workbench_execution(ledger)
        self.assertGreaterEqual(ledger.total_task_count, 3)
        self.assertGreaterEqual(ledger.ready_count, 1)
        self.assertEqual(ledger.completed_count, 0)
        self.assertEqual(
            ledger.event_count if hasattr(ledger, "event_count") else len(ledger.events), 0
        )
        self.assertTrue(any(item.prerequisites for item in ledger.items))
        self.assertEqual(
            ledger.planned_count + ledger.ready_count,
            ledger.total_task_count,
        )

    def test_complete_requires_start_and_declared_evidence(self) -> None:
        _report, ledger = self.ledger()
        ready = next(
            item for item in ledger.items if item.state is ModuleWorkbenchExecutionState.READY
        )
        with self.assertRaises(ValidationError):
            apply_module_workbench_execution_command(
                ledger,
                execution_command(
                    ready.task_id, ModuleWorkbenchExecutionAction.COMPLETE, "too early"
                ),
            )
        started = apply_module_workbench_execution_command(
            ledger,
            execution_command(ready.task_id, "start", "begin bounded task"),
        )
        with self.assertRaises(ValidationError):
            apply_module_workbench_execution_command(
                started,
                execution_command(ready.task_id, "complete", "missing receipts"),
            )
        completed = apply_module_workbench_execution_command(
            started,
            execution_command(
                ready.task_id,
                "complete",
                "completed with source and test receipts",
                evidence_addresses=("receipt:source", "receipt:test"),
            ),
        )
        item = next(item for item in completed.items if item.task_id == ready.task_id)
        self.assertEqual(item.state, ModuleWorkbenchExecutionState.COMPLETED)
        self.assertEqual(item.completion_percent, 100.0)
        self.assertEqual(len(completed.events), 2)
        verify_module_workbench_execution(completed)

    def test_prerequisite_block_unblock_and_start_rules(self) -> None:
        _report, ledger = self.ledger()
        dependent = next(item for item in ledger.items if item.prerequisites)
        blocked = apply_module_workbench_execution_command(
            ledger,
            execution_command(dependent.task_id, "block", "waiting for prerequisite review"),
        )
        blocked_item = next(item for item in blocked.items if item.task_id == dependent.task_id)
        self.assertEqual(blocked_item.state, ModuleWorkbenchExecutionState.BLOCKED)
        with self.assertRaises(ValidationError):
            apply_module_workbench_execution_command(
                blocked,
                execution_command(dependent.task_id, "unblock", "attempted too early"),
            )
        prerequisite_id = dependent.prerequisites[0]
        prerequisite = next(item for item in blocked.items if item.task_id == prerequisite_id)
        ready = blocked
        if prerequisite.state is ModuleWorkbenchExecutionState.READY:
            ready = apply_module_workbench_execution_command(
                ready,
                execution_command(prerequisite_id, "start", "begin prerequisite"),
            )
            ready = apply_module_workbench_execution_command(
                ready,
                execution_command(
                    prerequisite_id,
                    "complete",
                    "close prerequisite",
                    evidence_addresses=("receipt:one", "receipt:two"),
                ),
            )
        unblocked = apply_module_workbench_execution_command(
            ready,
            execution_command(dependent.task_id, "unblock", "prerequisite is complete"),
        )
        self.assertEqual(
            next(item for item in unblocked.items if item.task_id == dependent.task_id).state,
            ModuleWorkbenchExecutionState.READY,
        )
        started = apply_module_workbench_execution_command(
            unblocked,
            execution_command(dependent.task_id, "start", "begin dependent task"),
        )
        self.assertEqual(
            next(item for item in started.items if item.task_id == dependent.task_id).state,
            ModuleWorkbenchExecutionState.IN_PROGRESS,
        )

    def test_skip_reopen_and_supersede_are_explicit(self) -> None:
        _report, ledger = self.ledger()
        ready = next(
            item for item in ledger.items if item.state is ModuleWorkbenchExecutionState.READY
        )
        skipped = apply_module_workbench_execution_command(
            ledger,
            execution_command(ready.task_id, "skip", "covered by a later task"),
        )
        self.assertEqual(
            next(item for item in skipped.items if item.task_id == ready.task_id).state,
            ModuleWorkbenchExecutionState.SKIPPED,
        )
        reopened = apply_module_workbench_execution_command(
            skipped,
            execution_command(ready.task_id, "reopen", "require fresh implementation evidence"),
        )
        self.assertEqual(
            next(item for item in reopened.items if item.task_id == ready.task_id).state,
            ModuleWorkbenchExecutionState.READY,
        )
        superseded = apply_module_workbench_execution_command(
            reopened,
            execution_command(ready.task_id, "supersede", "replaced by a stronger contract"),
        )
        superseded_item = next(item for item in superseded.items if item.task_id == ready.task_id)
        self.assertEqual(superseded_item.state, ModuleWorkbenchExecutionState.SUPERSEDED)
        self.assertTrue(superseded_item.blockers)

    def test_audit_policy_and_tamper_detection(self) -> None:
        _report, ledger = self.ledger()
        audit = audit_module_workbench_execution(ledger)
        verify_module_workbench_execution_audit(audit)
        self.assertTrue(audit.accepted)
        self.assertEqual(audit.failed_count, 0)
        gate = evaluate_module_workbench_execution_policy(ledger, audit=audit)
        verify_module_workbench_execution_policy_gate(gate)
        self.assertTrue(gate.accepted)
        strict = build_module_workbench_execution_policy(minimum_completion_percent=100.0)
        verify_module_workbench_execution_policy(strict)
        strict_gate = evaluate_module_workbench_execution_policy(ledger, strict, audit)
        self.assertFalse(strict_gate.accepted)
        self.assertGreater(strict_gate.failed_count, 0)
        tampered = ledger.items[0]
        object.__setattr__(tampered, "detail", "tampered")
        with self.assertRaises(ValidationError):
            verify_module_workbench_execution(ledger)

    def test_queries_and_exports_are_bounded_and_stable(self) -> None:
        _report, ledger = self.ledger()
        audit = audit_module_workbench_execution(ledger)
        gate = evaluate_module_workbench_execution_policy(ledger, audit=audit)
        self.assertEqual(
            query_module_workbench_execution(ledger, resource="items")["total"],
            ledger.total_task_count,
        )
        self.assertEqual(query_module_workbench_execution(ledger, resource="summary")["total"], 1)
        self.assertEqual(
            query_module_workbench_execution_audit(audit, passed=True)["total"], audit.passed_count
        )
        self.assertEqual(
            query_module_workbench_execution_policy(gate, passed=True)["total"], gate.passed_count
        )
        self.assertIn('"task_count"', module_workbench_execution_json(ledger))
        self.assertIn("task_id", module_workbench_execution_csv(ledger))
        self.assertIn(
            "Module Workbench Execution", render_module_workbench_execution_markdown(ledger)
        )
        self.assertIn("check_id", module_workbench_execution_audit_csv(audit))
        self.assertIn('"check_count"', module_workbench_execution_audit_json(audit))
        self.assertIn("check_id", module_workbench_execution_policy_csv(gate))
        self.assertIn('"check_count"', module_workbench_execution_policy_json(gate))
        self.assertEqual(module_workbench_execution_policy_summary(gate)["accepted"], gate.accepted)

    def test_diff_reports_state_and_evidence_changes(self) -> None:
        _report, ledger = self.ledger()
        ready = next(
            item for item in ledger.items if item.state is ModuleWorkbenchExecutionState.READY
        )
        current = apply_module_workbench_execution_commands(
            ledger,
            (
                execution_command(ready.task_id, "start", "begin diff scenario"),
                execution_command(
                    ready.task_id,
                    "complete",
                    "finish diff scenario",
                    evidence_addresses=("receipt:a", "receipt:b"),
                ),
            ),
        )
        diff = build_module_workbench_execution_diff(ledger, current)
        verify_module_workbench_execution_diff(diff)
        self.assertEqual(diff.changed_count, 1)
        self.assertEqual(diff.event_delta, 2)
        self.assertGreater(diff.evidence_delta, 0)
        self.assertEqual(query_module_workbench_execution_diff(diff, kind="changed")["total"], 1)
        self.assertIn("current_state", module_workbench_execution_diff_csv(diff))
        self.assertIn('"change_count"', module_workbench_execution_diff_json(diff))

    def test_runtime_and_schema_capability_surfaces(self) -> None:
        report, ledger = self.ledger()
        runtime = run_module_workbench_execution(report)
        verify_module_workbench_execution_runtime(runtime)
        self.assertTrue(runtime.accepted)
        self.assertEqual(runtime.completed_count, len(runtime.stages))
        self.assertEqual(
            query_module_workbench_execution_runtime(runtime)["total"], len(runtime.stages)
        )
        self.assertIn("kind", module_workbench_execution_runtime_csv(runtime))
        self.assertIn('"stage_count"', module_workbench_execution_runtime_json(runtime))
        self.assertEqual(
            module_workbench_execution_schema()["resources"],
            ["items", "events", "blockers", "summary"],
        )
        self.assertEqual(module_workbench_execution_audit_schema()["check_count"], 8)
        self.assertEqual(
            module_workbench_execution_policy_schema()["resources"], ["checks", "summary"]
        )
        self.assertEqual(
            module_workbench_execution_diff_schema()["resources"], ["changes", "summary"]
        )
        self.assertEqual(
            module_workbench_execution_runtime_schema()["stage_order"],
            ["portfolio", "plan", "replay", "policy", "audit", "handoff"],
        )
        for capabilities in (
            module_workbench_execution_capabilities(),
            module_workbench_execution_audit_capabilities(),
            module_workbench_execution_policy_capabilities(),
            module_workbench_execution_diff_capabilities(),
            module_workbench_execution_runtime_capabilities(),
        ):
            self.assertEqual(capabilities["operation_count"], len(capabilities["operations"]))
        self.assertEqual(ledger.total_task_count, len(ledger.items))

    def test_schema_routes_are_available(self) -> None:
        server = create_server(host="127.0.0.1", port=0)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = HTTPConnection("127.0.0.1", server.server_port, timeout=10)
            for route, marker in (
                ("/v1/module-workbench/execution/schema", "resources"),
                ("/v1/module-workbench/execution/capabilities", "operations"),
                ("/v1/module-workbench/execution/audit/schema", "planes"),
                ("/v1/module-workbench/execution/policy/schema", "thresholds"),
                ("/v1/module-workbench/execution/diff/schema", "change_kinds"),
                ("/v1/module-workbench/execution/runtime/schema", "stage_order"),
                ("/v1/module-workbench/execution/review/schema", "review_states"),
                ("/v1/module-workbench/execution/review/capabilities", "operations"),
            ):
                connection.request("GET", route)
                response = connection.getresponse()
                payload = response.read().decode("utf-8")
                self.assertEqual(response.status, 200)
                self.assertIn(marker, payload)
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=10)
