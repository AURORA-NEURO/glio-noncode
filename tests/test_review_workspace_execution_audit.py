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
from glio_noncode.review_workspace import build_persisted_review_workspace
from glio_noncode.review_workspace_execution import (
    ReviewPlanExecutionEventKind,
    ReviewPlanExecutionStore,
    build_review_plan_execution_event,
)
from glio_noncode.review_workspace_execution_audit import (
    ReviewWorkspaceExecutionAuditDomain,
    audit_persisted_review_workspace_plan_execution,
    audit_review_workspace_plan_execution,
    render_review_workspace_execution_audit_markdown,
    review_workspace_execution_audit_capabilities,
    review_workspace_execution_audit_csv,
    review_workspace_execution_audit_export_payloads,
    review_workspace_execution_audit_from_mapping,
    review_workspace_execution_audit_json,
    review_workspace_execution_audit_schema,
)
from glio_noncode.review_workspace_plan import build_review_workspace_plan
from glio_noncode.runtime import CaseRuntime
from glio_noncode.serialization import canonical_json

from .helpers import fixture_manifest


class ReviewWorkspaceExecutionAuditTests(unittest.TestCase):
    def _context(self, directory: str):
        runtime = CaseRuntime(directory)
        dossier = runtime.evaluate(fixture_manifest())
        workspace = build_persisted_review_workspace(runtime, dossier.run_id)
        return runtime, dossier, build_review_workspace_plan(workspace)

    @staticmethod
    def _start(plan, event_id: str):
        return build_review_plan_execution_event(
            plan=plan,
            action_id=plan.actions[0].action_id,
            event_id=event_id,
            kind=ReviewPlanExecutionEventKind.START,
            occurred_at="2026-08-25T12:00:00Z",
        )

    def test_empty_ledger_is_a_valid_explicit_audit_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier, plan = self._context(directory)
            audit = audit_persisted_review_workspace_plan_execution(runtime, dossier.run_id)
            self.assertTrue(audit.accepted)
            self.assertFalse(audit.directory_exists)
            self.assertFalse(audit.ledger_present)
            self.assertTrue(audit.exact_bytes)
            self.assertTrue(audit.manifest_accepted)
            self.assertTrue(audit.replay_accepted)
            self.assertEqual(audit.event_count, 0)
            self.assertIn("no persisted execution ledger", audit.warnings[0])
            self.assertEqual(
                audit_review_workspace_plan_execution(
                    plan,
                    ReviewPlanExecutionStore(directory),
                ).content_address,
                audit.content_address,
            )

    def test_valid_ledger_reconciles_files_manifest_and_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier, plan = self._context(directory)
            store = ReviewPlanExecutionStore(directory)
            event = self._start(plan, "audit-start")
            store.append(plan, event)
            audit = audit_persisted_review_workspace_plan_execution(runtime, dossier.run_id)
            self.assertTrue(audit.accepted, audit.to_dict())
            self.assertTrue(audit.directory_exists)
            self.assertTrue(audit.ledger_present)
            self.assertTrue(audit.exact_bytes)
            self.assertTrue(audit.manifest_accepted)
            self.assertTrue(audit.replay_accepted)
            self.assertTrue(audit.boundary_accepted)
            self.assertEqual(audit.event_count, 1)
            self.assertEqual(audit.line_count, 1)
            self.assertEqual(audit.first_event_address, event.content_address)
            self.assertEqual(audit.last_event_address, event.content_address)
            self.assertTrue(any(item.check_id == "manifest:events_address" for item in audit.findings))
            self.assertTrue(any(item.domain is ReviewWorkspaceExecutionAuditDomain.REPLAY for item in audit.findings))
            hydrated = review_workspace_execution_audit_from_mapping(audit.to_dict())
            self.assertEqual(hydrated.to_dict(), audit.to_dict())
            hydrated_with_report = review_workspace_execution_audit_from_mapping(
                audit.to_dict(include_report=True)
            )
            self.assertIsNotNone(hydrated_with_report.report)
            self.assertEqual(hydrated_with_report.report.event_count, 1)

    def test_manifest_byte_and_unexpected_file_failures_are_distinguished(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier, plan = self._context(directory)
            store = ReviewPlanExecutionStore(directory)
            store.append(plan, self._start(plan, "audit-tamper"))
            ledger, events_path, manifest_path = store.paths(plan)
            original = events_path.read_bytes()
            events_path.write_bytes(original.replace(b"\n", b" \n", 1))
            tampered_bytes = audit_persisted_review_workspace_plan_execution(runtime, dossier.run_id)
            self.assertFalse(tampered_bytes.accepted)
            self.assertFalse(tampered_bytes.exact_bytes)
            self.assertFalse(tampered_bytes.manifest_accepted)
            self.assertTrue(tampered_bytes.replay_accepted)
            events_path.write_bytes(original)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            tampered_manifest_bytes = audit_persisted_review_workspace_plan_execution(
                runtime,
                dossier.run_id,
            )
            self.assertFalse(tampered_manifest_bytes.exact_bytes)
            self.assertFalse(tampered_manifest_bytes.manifest_accepted)
            manifest_path.write_text(canonical_json(manifest), encoding="utf-8")
            manifest["event_count"] = 99
            manifest_path.write_text(canonical_json(manifest), encoding="utf-8")
            tampered_manifest = audit_persisted_review_workspace_plan_execution(runtime, dossier.run_id)
            self.assertFalse(tampered_manifest.accepted)
            self.assertTrue(any(item.check_id == "manifest:event_count" and not item.accepted for item in tampered_manifest.findings))
            manifest["event_count"] = 1
            manifest_path.write_text(canonical_json(manifest), encoding="utf-8")
            (ledger / "unexpected.txt").write_text("unexpected", encoding="utf-8")
            unexpected = audit_persisted_review_workspace_plan_execution(runtime, dossier.run_id)
            self.assertFalse(unexpected.accepted)
            self.assertTrue(any(item.check_id == "ledger:allowed-files" and not item.accepted for item in unexpected.findings))

    def test_public_boundary_and_exports_are_content_addressed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier, plan = self._context(directory)
            store = ReviewPlanExecutionStore(directory)
            store.append(plan, self._start(plan, "audit-public"))
            _, _, manifest_path = store.paths(plan)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["agent_id"] = "must-not-publish"
            manifest_path.write_text(canonical_json(manifest), encoding="utf-8")
            audit = audit_persisted_review_workspace_plan_execution(runtime, dossier.run_id)
            self.assertFalse(audit.accepted)
            self.assertFalse(audit.boundary_accepted)
            self.assertTrue(any(item.domain is ReviewWorkspaceExecutionAuditDomain.BOUNDARY and not item.accepted for item in audit.findings))
            payloads = review_workspace_execution_audit_export_payloads(audit)
            self.assertEqual(
                set(payloads),
                {
                    "review-workspace-execution-audit.json",
                    "review-workspace-execution-audit.md",
                    "review-workspace-execution-audit.csv",
                },
            )
            self.assertEqual(json.loads(review_workspace_execution_audit_json(audit)), audit.to_dict())
            self.assertIn("check_id", review_workspace_execution_audit_csv(audit).splitlines()[0])
            self.assertIn("read-only", render_review_workspace_execution_audit_markdown(audit))
            self.assertTrue(review_workspace_execution_audit_capabilities()["independent_filesystem_inspection"])
            self.assertEqual(review_workspace_execution_audit_schema()["version"], "review-workspace-execution-audit-schema-v1")
            with self.assertRaises(ValidationError):
                review_workspace_execution_audit_from_mapping(
                    audit.to_dict() | {"accepted": True}
                )

    def test_cli_and_http_surfaces_expose_the_same_audit_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier, plan = self._context(directory)
            store = ReviewPlanExecutionStore(directory)
            store.append(plan, self._start(plan, "audit-surface"))
            output = Path(directory) / "audit.json"
            self.assertEqual(
                main(
                    [
                        "review-workspace-plan-execution-audit",
                        dossier.run_id,
                        "--data-root",
                        directory,
                        "--include-report",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["accepted"])
            self.assertIn("report", payload)
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                connection.request(
                    "GET",
                    f"/v1/runs/{dossier.run_id}/review-workspace/plan/execution/audit?include_report=true",
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                api_payload = json.loads(response.read())
                self.assertEqual(api_payload["content_address"], payload["content_address"])
                connection.request("GET", "/v1/review-workspace/plan/execution/audit/schema")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(
                    json.loads(response.read())["audit_version"],
                    "review-workspace-execution-audit-v1",
                )
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
