"""Deep negative and operator tests for transfer audits."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_transfer as transfer
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_transfer_audit as audit
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_bytes, canonical_json
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_transfer import TransferFixture


class AuditFixture(TransferFixture):
    def transfer_directory(self, root: Path, chunk_size: int = 256) -> Path:
        value = self.transfer_value(root, chunk_size=chunk_size)
        destination = root / "transfer"
        transfer.write_transfer(value, destination)
        return destination


class AuditModelTests(AuditFixture):
    def test_complete_transfer_audit_passes_all_checks(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            report = audit.audit_transfer(value)
            self.assertEqual(report.state, "complete")
            self.assertTrue(report.complete)
            self.assertEqual(report.check_count, len(audit.CHECK_IDS))
            self.assertEqual(report.failed_count, 0)
            self.assertEqual(report.passed_count, len(audit.CHECK_IDS))
            self.assertEqual(tuple(check.check_id for check in report.checks), audit.CHECK_IDS)

    def test_directory_audit_reloads_and_replays_transfer(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = self.transfer_directory(root)
            report = audit.audit_transfer_directory(directory)
            self.assertEqual(report.state, "complete")
            self.assertEqual(report.transfer_address, transfer.load_transfer(directory).content_address)

    def test_partial_audit_is_valid_but_not_complete(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.transfer_value(root)
            assembler = transfer.TransferAssembler(value)
            assembler.add_chunks({0: value.payload_bytes()[0], 2: value.payload_bytes()[2]})
            report = audit.audit_transfer(assembler)
            self.assertEqual(report.state, "incomplete")
            self.assertFalse(report.complete)
            self.assertEqual(report.failed_count, 2)
            self.assertFalse(next(check for check in report.checks if check.check_id == "assembly-complete").passed)
            self.assertFalse(next(check for check in report.checks if check.check_id == "nested-archive").passed)

    def test_partial_directory_audit_preserves_received_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.transfer_value(root)
            assembler = transfer.TransferAssembler(value)
            assembler.add_chunk(4, value.payload_bytes()[4])
            destination = root / "partial"
            transfer.write_partial_transfer(assembler, destination)
            report = audit.audit_partial_transfer_directory(destination)
            self.assertEqual(report.state, "incomplete")
            self.assertEqual(report.transfer_address, value.content_address)

    def test_audit_is_reproducible_for_equal_transfer_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.transfer_value(root)
            first = audit.audit_transfer(value)
            second = audit.audit_transfer(value)
            self.assertEqual(first.to_dict(), second.to_dict())
            self.assertEqual(audit.address_audit(first), first.content_address)

    def test_audit_mapping_round_trip_is_public(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = audit.audit_transfer(self.transfer_value(Path(temporary)))
            mapped = audit.audit_from_mapping(report.to_dict())
            self.assertEqual(mapped.to_dict(), report.to_dict())
            self.assertNotIn("C:\\", canonical_json(mapped.to_dict()))
            self.assertNotIn("agent", canonical_json(mapped.to_dict()).lower())
            self.assertNotIn("language", canonical_json(mapped.to_dict()).lower())

    def test_audit_mapping_rejects_unknown_field(self):
        with tempfile.TemporaryDirectory() as temporary:
            document = audit.audit_transfer(self.transfer_value(Path(temporary))).to_dict()
            document["private_path"] = "C:\\private"
            with self.assertRaises(ValidationError):
                audit.audit_from_mapping(document)

    def test_audit_rejects_plain_transfer_value(self):
        with self.assertRaises(ValidationError):
            audit.audit_transfer({"content_address": "transfer:test"})

    def test_audit_check_addresses_are_independent(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = audit.audit_transfer(self.transfer_value(Path(temporary)))
            addresses = tuple(check.content_address for check in report.checks)
            self.assertEqual(len(set(addresses)), len(addresses))
            self.assertTrue(all(address.startswith(audit.AUDIT_CHECK_PREFIX + ":") for address in addresses))

    def test_audit_check_constructor_rejects_non_boolean_state(self):
        with self.assertRaises(ValidationError):
            audit.TransferAuditCheck("test", "true", "detail", "evidence:1")

    def test_audit_reports_all_expected_evidence_namespaces(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = audit.audit_transfer(self.transfer_value(Path(temporary)))
            for check in report.checks:
                self.assertIn(":", check.evidence_address)
                self.assertNotIn("\\", check.evidence_address)

    def test_audit_json_is_canonical(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = audit.audit_transfer(self.transfer_value(Path(temporary)))
            self.assertEqual(audit.audit_json(report), canonical_json(report.to_dict()))

    def test_audit_markdown_contains_every_check(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = audit.audit_transfer(self.transfer_value(Path(temporary)))
            rendered = audit.render_audit_markdown(report)
            self.assertIn("archive transfer audit", rendered)
            for check_id in audit.CHECK_IDS:
                self.assertIn(check_id, rendered)

    def test_audit_renderers_reject_plain_value(self):
        with self.assertRaises(ValidationError):
            audit.audit_json({})
        with self.assertRaises(ValidationError):
            audit.render_audit_markdown({})

    def test_audit_schema_is_closed(self):
        self.assertFalse(audit.audit_schema()["additionalProperties"])
        self.assertFalse(audit.check_schema()["additionalProperties"])
        self.assertEqual(tuple(audit.audit_schema()["properties"]["state"]["enum"]), audit.STATES)
        self.assertEqual(audit.audit_schema()["properties"]["check_count"]["maximum"], len(audit.CHECK_IDS))

    def test_audit_capabilities_are_path_free(self):
        capabilities = audit.capabilities()
        self.assertEqual(tuple(capabilities["checks"]), audit.CHECK_IDS)
        self.assertIn("partial-transfer progress audit", capabilities["features"])
        self.assertNotIn("C:\\", canonical_json(capabilities))

    def test_verify_audit_returns_same_typed_value(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = audit.audit_transfer(self.transfer_value(Path(temporary)))
            self.assertIs(audit.verify_audit(report), report)

    def test_tampered_check_address_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            document = audit.audit_transfer(self.transfer_value(Path(temporary))).to_dict()
            document["checks"][0]["content_address"] = "audit-check:tampered"
            with self.assertRaises(ValidationError):
                audit.audit_from_mapping(document)

    def test_tampered_passed_count_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            document = audit.audit_transfer(self.transfer_value(Path(temporary))).to_dict()
            document["passed_count"] = 0
            with self.assertRaises(ValidationError):
                audit.audit_from_mapping(document)

    def test_tampered_state_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            document = audit.audit_transfer(self.transfer_value(Path(temporary))).to_dict()
            document["state"] = "incomplete"
            document["complete"] = False
            with self.assertRaises(ValidationError):
                audit.audit_from_mapping(document)

    def test_partial_audit_becomes_complete_after_resume(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.transfer_value(root)
            assembler = transfer.TransferAssembler(value)
            assembler.add_chunk(0, value.payload_bytes()[0])
            self.assertEqual(audit.audit_transfer(assembler).state, "incomplete")
            for index in range(1, value.chunk_count):
                assembler.add_chunk(index, value.payload_bytes()[index])
            report = audit.audit_transfer(assembler)
            self.assertEqual(report.state, "complete")
            self.assertEqual(report.failed_count, 0)


class AuditOperatorTests(AuditFixture):
    def test_cli_complete_and_partial_audits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.transfer_value(root)
            complete = root / "complete"
            partial = root / "partial"
            transfer.write_transfer(value, complete)
            assembler = transfer.TransferAssembler(value)
            assembler.add_chunk(0, value.payload_bytes()[0])
            transfer.write_partial_transfer(assembler, partial)
            status, output = self.capture_cli([self.TRANSFER_COMMAND + "-audit", "--input", str(complete), "--format", "summary"])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output)["failed_count"], 0)
            status, output = self.capture_cli([self.TRANSFER_COMMAND + "-audit", "--input", str(partial), "--partial", "--format", "json"])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output)["state"], "incomplete")

    def test_cli_audit_renderers_and_schemas(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.transfer_value(root)
            directory = root / "transfer"
            transfer.write_transfer(value, directory)
            for output_format, marker in (("json", "check_id"), ("markdown", "transfer audit")):
                status, output = self.capture_cli([self.TRANSFER_COMMAND + "-audit", "--input", str(directory), "--format", output_format])
                self.assertEqual(status, 0)
                self.assertIn(marker, output)
            for suffix in ("audit-schema", "audit-check-schema", "audit-capabilities"):
                status, output = self.capture_cli([self.TRANSFER_COMMAND + "-" + suffix])
                self.assertEqual(status, 0)
                self.assertIsInstance(json.loads(output), dict)

    def test_http_audit_routes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = self.transfer_directory(root)
            server, thread = self.server()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                prefix = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/transfer/audit"
                for suffix in ("/schema", "/check-schema", "/capabilities"):
                    with urlopen(base + prefix + suffix) as response:
                        self.assertEqual(response.status, 200)
                        self.assertIsInstance(json.loads(response.read()), dict)
                with urlopen(base + prefix + "?input=" + str(directory)) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read())["failed_count"], 0)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
