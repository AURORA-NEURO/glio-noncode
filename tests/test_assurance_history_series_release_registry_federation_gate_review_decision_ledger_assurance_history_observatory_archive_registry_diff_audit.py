"""Deep contracts for independent observatory registry diff audits."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry as registry
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff as diff
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff_audit as audit
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff import DiffFixture


class RegistryDiffAuditFixture(DiffFixture):
    """Build an audit input through the verified registry-diff boundary."""

    AUDIT_COMMAND = DiffFixture.DIFF_COMMAND + "-audit"

    def diff_value(self, root: Path, left: str = "baseline", right: str = "candidate") -> diff.RegistryDiff:
        return diff.build_diff(self.one_registry(root, left), self.one_registry(root, right))

    def assert_public(self, value) -> None:
        payload = value.to_dict() if hasattr(value, "to_dict") else value
        rendered = canonical_json(payload)
        self.assertNotIn("C:\\", rendered)
        self.assertNotIn("/Users/", rendered)
        forbidden = {"agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"}

        def walk(node):
            if isinstance(node, dict):
                for key, item in node.items():
                    self.assertNotIn(key.lower(), forbidden)
                    walk(item)
            elif isinstance(node, (list, tuple)):
                for item in node:
                    walk(item)

        walk(payload)


class RegistryDiffAuditBuildTests(RegistryDiffAuditFixture):
    def test_valid_typed_diff_produces_complete_fixed_check_set(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = audit.audit_diff(self.diff_value(Path(temporary)))
            self.assertEqual(value.state, "complete")
            self.assertTrue(value.complete)
            self.assertTrue(value.accepted)
            self.assertEqual(value.check_count, audit.MAX_CHECKS)
            self.assertEqual(value.passed_count, audit.MAX_CHECKS)
            self.assertEqual(value.failed_count, 0)
            self.assertEqual(tuple(item.check_id for item in value.checks), audit.CHECK_IDS)
            self.assertEqual(audit.address_audit(value), value.content_address)
            self.assertEqual(audit.verify_audit(value), value)
            self.assert_public(value)

    def test_audit_json_and_markdown_are_deterministic(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = audit.audit_diff(self.diff_value(Path(temporary), "same-left", "same-right"))
            self.assertEqual(audit.audit_json(value), audit.audit_json(value))
            self.assertTrue(audit.audit_json(value).startswith("{"))
            self.assertIn("Registry Diff Audit", audit.render_audit_markdown(value))
            self.assertIn("mapping-round-trip", audit.render_audit_markdown(value))
            self.assert_public(audit.audit_schema())
            self.assert_public(audit.check_schema())
            self.assert_public(audit.capabilities())

    def test_mapping_round_trip_preserves_complete_audit(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = audit.audit_diff(self.diff_value(Path(temporary), "round-left", "round-right"))
            loaded = audit.audit_from_mapping(value.to_dict())
            self.assertEqual(loaded.to_dict(), value.to_dict())
            self.assertEqual(audit.address_audit(loaded), value.content_address)

    def test_real_downloaded_registry_self_diff_is_audited_when_present(self):
        source = Path(tempfile.gettempdir()) / "glio-noncode-history-observatory-demo-current" / "registry-v1"
        if not source.is_dir():
            self.skipTest("the optional local downloaded-data demo is not present")
        value = diff.build_diff_from_directories(source, source)
        report = audit.audit_diff(value)
        self.assertTrue(report.accepted)
        self.assertEqual(report.passed_count, audit.MAX_CHECKS)


class RegistryDiffAuditTamperTests(RegistryDiffAuditFixture):
    def test_malformed_mapping_returns_incomplete_diagnostics_instead_of_raising(self):
        with tempfile.TemporaryDirectory() as temporary:
            document = self.diff_value(Path(temporary)).to_dict()
            document["item_count"] = 99
            value = audit.audit_from_mapping(document)
            self.assertEqual(value.state, "incomplete")
            self.assertFalse(value.complete)
            self.assertFalse(value.accepted)
            self.assertGreater(value.failed_count, 0)
            self.assertEqual(tuple(item.check_id for item in value.checks), audit.CHECK_IDS)
            self.assert_public(value)

    def test_private_mapping_key_is_reported_by_public_boundary_check(self):
        with tempfile.TemporaryDirectory() as temporary:
            document = self.diff_value(Path(temporary)).to_dict() | {"private": "C:\\hidden"}
            value = audit.audit_from_mapping(document)
            checks = {item.check_id: item for item in value.checks}
            self.assertFalse(value.accepted)
            self.assertFalse(checks["exact-fields"].passed)
            self.assertFalse(checks["public-boundary"].passed)
            self.assert_public(value)

    def test_forged_content_address_is_incomplete_but_report_remains_addressable(self):
        with tempfile.TemporaryDirectory() as temporary:
            document = self.diff_value(Path(temporary)).to_dict() | {"content_address": diff.DIFF_PREFIX + ":forged"}
            value = audit.audit_from_mapping(document)
            checks = {item.check_id: item for item in value.checks}
            self.assertFalse(checks["content-address"].passed)
            self.assertEqual(audit.address_audit(value), value.content_address)
            self.assert_public(value)

    def test_audit_constructor_rejects_wrong_check_order_and_non_public_sources(self):
        with self.assertRaises(ValidationError):
            audit.RegistryDiffAudit(
                diff.DIFF_PREFIX + ":one",
                registry.REGISTRY_PREFIX + ":one",
                registry.REGISTRY_PREFIX + ":two",
                "complete",
                True,
                True,
                (),
                "pending:audit",
            )
        with tempfile.TemporaryDirectory() as temporary:
            report = audit.audit_diff(self.diff_value(Path(temporary)))
            with self.assertRaises(ValidationError):
                audit.RegistryDiffAudit(
                    report.diff_address,
                    "C:\\private",
                    report.candidate_address,
                    report.state,
                    report.complete,
                    report.accepted,
                    report.checks,
                    "pending:audit",
                )


class RegistryDiffAuditCliAndApiTests(RegistryDiffAuditFixture):
    def server(self):
        from glio_noncode.api import create_server

        server = create_server("127.0.0.1", 0)
        import threading

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def directories(self, root: Path) -> tuple[Path, Path]:
        baseline = self.one_registry(root, "audit-cli-baseline")
        candidate = self.one_registry(root, "audit-cli-candidate")
        baseline_dir = root / "baseline"
        candidate_dir = root / "candidate"
        registry.write_registry(baseline, baseline_dir)
        registry.write_registry(candidate, candidate_dir)
        return baseline_dir, candidate_dir

    def test_cli_audit_and_contract_commands(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            baseline, candidate = self.directories(Path(temporary))
            output = Path(temporary) / "audit.json"
            self.assertEqual(main([self.AUDIT_COMMAND, "--baseline", str(baseline), "--candidate", str(candidate), "--format", "json", "--output", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(payload["accepted"])
            self.assertEqual(payload["passed_count"], audit.MAX_CHECKS)
            self.assertEqual(main([self.AUDIT_COMMAND + "-schema"]), 0)
            self.assertEqual(main([self.AUDIT_COMMAND + "-check-schema"]), 0)
            self.assertEqual(main([self.AUDIT_COMMAND + "-capabilities"]), 0)

    def test_http_audit_schema_capabilities_and_report_routes(self):
        with tempfile.TemporaryDirectory() as temporary:
            baseline, candidate = self.directories(Path(temporary))
            server, thread = self.server()
            try:
                prefix = f"http://127.0.0.1:{server.server_port}/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/diff/audit"
                params = {"baseline": str(baseline), "candidate": str(candidate), "format": "json"}
                with urlopen(prefix + "?" + urlencode(params)) as response:
                    payload = json.loads(response.read())
                self.assertTrue(payload["accepted"])
                self.assertEqual(payload["check_count"], audit.MAX_CHECKS)
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
