"""Independent audit contracts for persisted observatory archive registries."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry as registry
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_audit as audit
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_bytes, canonical_json
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry import RegistryFixture


class RegistryAuditFixture(RegistryFixture):
    AUDIT_COMMAND = RegistryFixture.REGISTRY_COMMAND + "-audit"

    def registry_directory(self, root: Path) -> Path:
        value = self.registry_value(root)
        destination = root / "registry"
        registry.write_registry(value, destination)
        return destination


class RegistryAuditModelTests(RegistryAuditFixture):
    def test_typed_registry_audit_passes_all_checks(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = audit.audit_registry(self.registry_value(Path(temporary)))
            self.assertEqual(report.state, "complete")
            self.assertTrue(report.complete)
            self.assertTrue(report.accepted)
            self.assertEqual(report.check_count, len(audit.CHECK_IDS))
            self.assertEqual(report.passed_count, len(audit.CHECK_IDS))
            self.assertEqual(report.failed_count, 0)
            self.assertEqual(tuple(check.check_id for check in report.checks), audit.CHECK_IDS)

    def test_directory_audit_reloads_and_replays_registry(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = self.registry_directory(root)
            report = audit.audit_registry_directory(directory)
            value = registry.load_registry(directory)
            self.assertEqual(report.state, "complete")
            self.assertEqual(report.registry_address, value.content_address)
            self.assertEqual(report.verification_address, value._verification.content_address)
            self.assertEqual(audit.address_audit(report), report.content_address)

    def test_audit_is_deterministic_for_equal_registry_state(self):
        with tempfile.TemporaryDirectory() as first_temporary, tempfile.TemporaryDirectory() as second_temporary:
            first = audit.audit_registry(self.registry_value(Path(first_temporary)))
            second = audit.audit_registry(self.registry_value(Path(second_temporary)))
            self.assertEqual(first.to_dict(), second.to_dict())
            self.assertEqual(audit.audit_json(first), audit.audit_json(second))

    def test_audit_mapping_round_trip_is_public(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = audit.audit_registry(self.registry_value(Path(temporary)))
            mapped = audit.audit_from_mapping(report.to_dict())
            self.assertEqual(mapped.to_dict(), report.to_dict())
            self.assert_public(mapped)
            self.assertNotIn("C:\\", canonical_json(mapped.to_dict()))

    def test_audit_mapping_rejects_unknown_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = audit.audit_registry(self.registry_value(Path(temporary)))
            with self.assertRaises(ValidationError):
                audit.audit_from_mapping(report.to_dict() | {"private": "secret"})

    def test_plain_registry_mapping_cannot_claim_an_attached_audit(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = registry.registry_from_mapping(self.registry_value(Path(temporary)).to_dict())
            with self.assertRaises(ValidationError):
                audit.audit_registry(value)

    def test_audit_check_addresses_are_independent_and_reproducible(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = audit.audit_registry(self.registry_value(Path(temporary)))
            self.assertTrue(all(check.content_address.startswith(audit.AUDIT_CHECK_PREFIX + ":") for check in report.checks))
            self.assertEqual(tuple(check.content_address for check in report.checks), tuple(audit.RegistryAuditCheck.from_mapping(check.to_dict()).content_address for check in report.checks))

    def test_audit_json_is_canonical(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = audit.audit_registry(self.registry_value(Path(temporary)))
            rendered = audit.audit_json(report)
            self.assertEqual(rendered, canonical_json(report.to_dict()))
            self.assertEqual(json.loads(rendered), json.loads(canonical_json(report.to_dict())))

    def test_markdown_lists_every_audit_check(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = audit.audit_registry(self.registry_value(Path(temporary)))
            rendered = audit.render_audit_markdown(report)
            self.assertIn("# Assurance history observatory archive registry audit", rendered)
            self.assertIn(report.content_address, rendered)
            for check_id in audit.CHECK_IDS:
                self.assertIn(check_id, rendered)

    def test_renderers_reject_plain_values(self):
        for renderer in (audit.audit_json, audit.render_audit_markdown):
            with self.assertRaises(ValidationError):
                renderer({})

    def test_audit_capabilities_and_schemas_are_closed(self):
        self.assertFalse(audit.audit_schema()["additionalProperties"])
        self.assertFalse(audit.check_schema()["additionalProperties"])
        self.assertEqual(tuple(audit.capabilities()["checks"]), audit.CHECK_IDS)
        self.assertEqual(tuple(audit.capabilities()["states"]), audit.STATES)
        self.assert_public(audit.capabilities())


class RegistryAuditFailureTests(RegistryAuditFixture):
    def test_invalid_metrics_are_reported_without_an_unstructured_exception(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = self.registry_directory(root)
            (directory / registry.METRICS_NAME).write_bytes(b"not-json")
            report = audit.audit_registry_directory(directory)
            self.assertEqual(report.state, "incomplete")
            self.assertFalse(report.accepted)
            self.assertGreater(report.failed_count, 0)
            self.assertIn("canonical-json", tuple(check.check_id for check in report.checks if not check.passed))
            self.assertIn("metrics-conservation", tuple(check.check_id for check in report.checks if not check.passed))
            self.assert_public(report)

    def test_valid_json_with_forged_registry_address_is_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = self.registry_directory(root)
            document = json.loads((directory / registry.REGISTRY_NAME).read_text(encoding="utf-8"))
            document["content_address"] = registry.REGISTRY_PREFIX + ":forged"
            (directory / registry.REGISTRY_NAME).write_bytes(canonical_bytes(document))
            report = audit.audit_registry_directory(directory)
            self.assertEqual(report.state, "incomplete")
            self.assertFalse(next(check for check in report.checks if check.check_id == "content-address").passed)

    def test_extra_member_is_audited_as_incomplete(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = self.registry_directory(root)
            (directory / "unexpected.json").write_bytes(b"{}")
            report = audit.audit_registry_directory(directory)
            self.assertFalse(report.complete)
            self.assertFalse(next(check for check in report.checks if check.check_id == "exact-members").passed)

    def test_missing_member_is_audited_as_incomplete(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = self.registry_directory(root)
            (directory / registry.METRICS_NAME).unlink()
            report = audit.audit_registry_directory(directory)
            self.assertFalse(report.complete)
            self.assertFalse(next(check for check in report.checks if check.check_id == "exact-members").passed)

    def test_non_directory_input_returns_a_public_incomplete_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "not-a-directory"
            source.write_text("archive", encoding="utf-8")
            report = audit.audit_registry_directory(source)
            self.assertEqual(report.state, "incomplete")
            self.assertFalse(report.accepted)
            self.assertEqual(report.check_count, len(audit.CHECK_IDS))
            self.assert_public(report)

    def test_corrupt_manifest_receipts_are_identified(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = self.registry_directory(root)
            manifest = json.loads((directory / registry.MANIFEST_NAME).read_text(encoding="utf-8"))
            manifest["artifacts"][0]["size"] += 1
            (directory / registry.MANIFEST_NAME).write_bytes(canonical_bytes(manifest))
            report = audit.audit_registry_directory(directory)
            self.assertFalse(next(check for check in report.checks if check.check_id == "artifact-receipts").passed)

    def test_directory_path_never_enters_audit_projection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = audit.audit_registry_directory(self.registry_directory(root))
            rendered = canonical_json(report.to_dict())
            self.assertNotIn(str(root), rendered)
            self.assertNotIn("C:\\", rendered)

    def test_audit_verifier_rejects_forged_content_address(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = audit.audit_registry(self.registry_value(Path(temporary))).to_dict()
            report["content_address"] = audit.AUDIT_PREFIX + ":forged"
            with self.assertRaises(ValidationError):
                audit.audit_from_mapping(report)


class RegistryAuditCliAndApiTests(RegistryAuditFixture):
    def test_cli_audit_and_schema_capability_commands(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = self.registry_directory(root)
            output = root / "audit.json"
            self.assertEqual(main([self.AUDIT_COMMAND, "--input", str(directory), "--format", "json", "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["failed_count"], 0)
            self.assertEqual(main([self.AUDIT_COMMAND + "-schema"]), 0)
            self.assertEqual(main([self.AUDIT_COMMAND + "-check-schema"]), 0)
            self.assertEqual(main([self.AUDIT_COMMAND + "-capabilities"]), 0)

    def test_http_audit_schema_capabilities_and_report_routes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = self.registry_directory(root)
            server, thread = self.server()
            try:
                prefix = f"http://127.0.0.1:{server.server_port}/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/audit"
                with urlopen(prefix + "/capabilities") as response:
                    self.assertEqual(tuple(json.loads(response.read())["checks"]), audit.CHECK_IDS)
                with urlopen(prefix + "/schema") as response:
                    self.assertFalse(json.loads(response.read())["additionalProperties"])
                with urlopen(prefix + "?" + urlencode({"input": str(directory), "format": "json"})) as response:
                    payload = json.loads(response.read())
                self.assertEqual(payload["failed_count"], 0)
                forged = root / "forged"
                forged.mkdir()
                (forged / registry.MANIFEST_NAME).write_text("{}", encoding="utf-8")
                try:
                    urlopen(prefix + "?" + urlencode({"input": str(forged), "format": "json"}))
                except HTTPError as error:
                    self.assertEqual(error.code, 422)
                else:
                    self.fail("incomplete audit should return HTTP 422")
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
