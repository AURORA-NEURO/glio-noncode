"""Deep contracts for independent ordered registry-history audits."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history as history
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_audit as audit
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff import DiffFixture


class RegistryHistoryAuditFixture(DiffFixture):
    """Build ordered history values through the verified registry boundary."""

    HISTORY_COMMAND = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-observatory-archive-registry-history"
    AUDIT_COMMAND = HISTORY_COMMAND + "-audit"

    def build_history(self, root: Path, *names: str) -> history.RegistryHistory:
        return history.build_history(tuple(self.one_registry(root, name) for name in names), history_id="audit-history")


class RegistryHistoryAuditModelTests(RegistryHistoryAuditFixture):
    def test_complete_audit_has_fixed_checks_and_replayable_address(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.build_history(Path(temporary), "audit-one", "audit-two", "audit-three")
            result = audit.audit_history(value)
            self.assertTrue(result.accepted)
            self.assertTrue(result.complete)
            self.assertEqual(result.state, "complete")
            self.assertEqual(result.check_count, len(audit.CHECK_IDS))
            self.assertEqual(tuple(item.check_id for item in result.checks), audit.CHECK_IDS)
            self.assertEqual(result.passed_count, result.check_count)
            self.assertEqual(result.failed_count, 0)
            self.assertEqual(audit.address_audit(result), result.content_address)
            self.assertEqual(audit.audit_from_mapping(result.to_dict()).to_dict(), result.to_dict())

    def test_malformed_public_history_returns_incomplete_diagnostics(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.build_history(Path(temporary), "malformed-one", "malformed-two")
            document = value.to_dict() | {"agent": "not-public", "source_path": "C:\\hidden"}
            result = audit.audit_from_mapping(document)
            self.assertFalse(result.accepted)
            self.assertFalse(result.complete)
            failed = {item.check_id for item in result.checks if not item.passed}
            self.assertIn("exact-fields", failed)
            self.assertIn("public-boundary", failed)
            self.assertEqual(result.check_count, len(audit.CHECK_IDS))
            self.assertNotIn("agent", canonical_json(result.to_dict()))
            self.assertNotIn("source_path", canonical_json(result.to_dict()))

    def test_tampered_nested_address_is_reported_without_losing_the_audit(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.build_history(Path(temporary), "nested-one", "nested-two")
            snapshots = [dict(item) for item in value.to_dict()["snapshots"]]
            snapshots[0]["snapshot_address"] = "glio-noncode-assurance-history-observatory-archive-registry-history-snapshot:forged"
            result = audit.audit_from_mapping(value.to_dict() | {"snapshots": snapshots})
            self.assertFalse(result.accepted)
            failed = {item.check_id for item in result.checks if not item.passed}
            self.assertIn("nested-addresses", failed)
            self.assertIn("content-address", failed)

    def test_schema_capabilities_and_public_exports_are_bounded(self):
        check_schema = audit.check_schema()
        report_schema = audit.audit_schema()
        capabilities = audit.capabilities()
        self.assertFalse(check_schema["additionalProperties"])
        self.assertFalse(report_schema["additionalProperties"])
        self.assertEqual(tuple(capabilities["checks"]), audit.CHECK_IDS)
        self.assertEqual(capabilities["limits"]["max_checks"], len(audit.CHECK_IDS))
        for payload in (check_schema, report_schema, capabilities):
            rendered = canonical_json(payload)
            self.assertNotIn("C:\\", rendered)
            self.assertNotIn("agent", rendered.lower())

    def test_report_rejects_forged_derived_counts(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.build_history(Path(temporary), "counts-one", "counts-two")
            result = audit.audit_history(value)
            with self.assertRaises(ValidationError):
                audit.audit_from_mapping(result.to_dict() | {"passed_count": 0})


class RegistryHistoryAuditCliApiTests(RegistryHistoryAuditFixture):
    def directories(self, root: Path) -> tuple[Path, Path]:
        value = self.build_history(root, "route-one", "route-two")
        first = root / "first"
        second = root / "second"
        first_registry = history.registry_model.load_registry(root / "route-one")
        second_registry = history.registry_model.load_registry(root / "route-two")
        history.registry_model.write_registry(first_registry, first)
        history.registry_model.write_registry(second_registry, second)
        destination = root / "history"
        history.write_history(value, destination)
        return destination, root / "unused"

    def server(self):
        from glio_noncode.api import create_server

        server = create_server("127.0.0.1", 0)
        import threading

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def test_cli_audit_and_contract_commands(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            value = self.build_history(Path(temporary), "cli-one", "cli-two")
            destination = Path(temporary) / "history"
            history.write_history(value, destination)
            output = Path(temporary) / "audit.json"
            self.assertEqual(main([self.AUDIT_COMMAND, "--input", str(destination), "--format", "json", "--output", str(output)]), 0)
            self.assertTrue(json.loads(output.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(main([self.AUDIT_COMMAND + "-schema"]), 0)
            self.assertEqual(main([self.AUDIT_COMMAND + "-check-schema"]), 0)
            self.assertEqual(main([self.AUDIT_COMMAND + "-capabilities"]), 0)

    def test_http_audit_schema_capabilities_and_report_routes(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.build_history(Path(temporary), "http-one", "http-two")
            destination = Path(temporary) / "history"
            history.write_history(value, destination)
            server, thread = self.server()
            try:
                prefix = f"http://127.0.0.1:{server.server_port}/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/audit"
                with urlopen(prefix + "?" + urlencode({"input": str(destination), "format": "json"})) as response:
                    payload = json.loads(response.read())
                self.assertTrue(payload["accepted"])
                with urlopen(prefix + "/schema") as response:
                    self.assertFalse(json.loads(response.read())["additionalProperties"])
                with urlopen(prefix + "/check-schema") as response:
                    self.assertFalse(json.loads(response.read())["additionalProperties"])
                with urlopen(prefix + "/capabilities") as response:
                    self.assertEqual(tuple(json.loads(response.read())["checks"]), audit.CHECK_IDS)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
