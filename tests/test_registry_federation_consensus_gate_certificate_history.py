"""Contract tests for append-only consensus certificate history."""

# ruff: noqa: E501, I001

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import registry_federation_consensus_gate_certificate as certificate_model
from glio_noncode import registry_federation_consensus_gate_certificate_history as history_model
from glio_noncode import registry_federation_consensus_gate_certificate_history_audit as audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_package as package_model
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from tests.test_registry_federation_consensus_gate_certificate import CertificateFixture


class CertificateHistoryTests(CertificateFixture):
    def _values(self, root: Path):
        issued = self.certificate_runtime(root / "issued", "primary", "replica")
        withheld = self.certificate_runtime(root / "withheld", "primary", "held")
        return issued, withheld

    def test_build_history_conserves_issued_and_withheld_decisions(self):
        with tempfile.TemporaryDirectory() as temporary:
            issued, withheld = self._values(Path(temporary))
            value = history_model.build_history(
                ((issued.certificate, issued.certificate_audit), (withheld.certificate, withheld.certificate_audit)),
                history_id="certificate-history",
            )
            self.assertEqual(value.history_id, "certificate-history")
            self.assertEqual(value.entry_count, 2)
            self.assertEqual((value.issued_count, value.withheld_count), (1, 1))
            self.assertEqual(tuple(entry.ordinal for entry in value.entries), (1, 2))
            self.assertEqual(value.entries[0].state, "issued")
            self.assertEqual(value.entries[1].state, "withheld")
            self.assertTrue(value.entries[0].accepted)
            self.assertFalse(value.entries[1].accepted)
            self.assertTrue(value.content_address.startswith(history_model.HISTORY_PREFIX + ":"))
            self.assertTrue(all(entry.content_address.startswith(history_model.ENTRY_PREFIX + ":") for entry in value.entries))
            self.assertEqual(history_model.history_from_mapping(value.to_dict()).to_dict(), value.to_dict())

    def test_append_only_extension_preserves_existing_entry_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            issued, withheld = self._values(Path(temporary))
            first = history_model.build_history(((issued.certificate, issued.certificate_audit),), history_id="append-history")
            extended = history_model.append_history(first, withheld.certificate, withheld.certificate_audit)
            self.assertEqual(first.entry_count, 1)
            self.assertEqual(extended.entry_count, 2)
            self.assertEqual(extended.entries[0].content_address, first.entries[0].content_address)
            self.assertEqual(extended.entries[0].certificate_address, first.entries[0].certificate_address)
            self.assertEqual(extended.entries[1].ordinal, 2)
            self.assertNotEqual(extended.content_address, first.content_address)
            self.assertEqual((extended.issued_count, extended.withheld_count), (1, 1))

    def test_history_rejects_bad_links_and_nonconserved_acceptance(self):
        with tempfile.TemporaryDirectory() as temporary:
            issued, withheld = self._values(Path(temporary))
            value = history_model.build_history(((issued.certificate, issued.certificate_audit),), history_id="validation-history")
            entry = dict(value.entries[0].to_dict())
            entry["accepted"] = False
            tampered = dict(value.to_dict())
            tampered["entries"] = [entry]
            with self.assertRaises(ValidationError):
                history_model.history_from_mapping(tampered)
            with self.assertRaises(ValidationError):
                history_model.build_history(((issued.certificate, withheld.certificate_audit),), history_id="wrong-link")
            with self.assertRaises(ValidationError):
                history_model.build_history((), history_id="empty-history")

    def test_three_file_persistence_is_exact_and_canonical(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            issued, withheld = self._values(root)
            value = history_model.build_history(((issued.certificate, issued.certificate_audit), (withheld.certificate, withheld.certificate_audit)), history_id="disk-history")
            destination = root / "history"
            history_model.write_history(value, destination)
            self.assertEqual({path.name for path in destination.iterdir()}, set(history_model.FILES))
            loaded = history_model.load_history(destination)
            self.assertEqual(loaded.to_dict(), value.to_dict())
            self.assertEqual(history_model.history_bytes(value), {name: (destination / name).read_bytes() for name in history_model.FILES})
            with self.assertRaises(ValidationError):
                history_model.write_history(value, destination)
            history_model.write_history(value, destination, overwrite=True)
            self.assertEqual(history_model.load_history(destination).content_address, value.content_address)

    def test_persistence_rejects_extra_member_noncanonical_projection_and_tamper(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            issued, withheld = self._values(root)
            value = history_model.build_history(((issued.certificate, issued.certificate_audit),), history_id="tamper-history")
            destination = root / "history"
            history_model.write_history(value, destination)
            (destination / "unexpected.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                history_model.load_history(destination)
            (destination / "unexpected.json").unlink()
            entries_path = destination / history_model.ENTRIES_NAME
            entries_path.write_text("[]\n", encoding="utf-8")
            with self.assertRaises(ValidationError):
                history_model.load_history(destination)

    def test_independent_history_audit_has_full_check_set_and_replays(self):
        with tempfile.TemporaryDirectory() as temporary:
            issued, withheld = self._values(Path(temporary))
            history = history_model.build_history(((issued.certificate, issued.certificate_audit), (withheld.certificate, withheld.certificate_audit)), history_id="audit-history")
            value = audit_model.audit_history(history)
            self.assertTrue(value.accepted)
            self.assertEqual((value.passed_count, value.failed_count), (len(audit_model.CHECK_IDS), 0))
            self.assertEqual(tuple(item.check_id for item in value.checks), audit_model.CHECK_IDS)
            self.assertEqual(audit_model.audit_from_mapping(value.to_dict()).to_dict(), value.to_dict())
            self.assertEqual(value.history_address, history.content_address)
            self.assertIn("entry count is conserved", audit_model.render_audit_markdown(value).lower())
            self.assertIn("check_id", audit_model.audit_csv(value).splitlines()[0])

    def test_history_audit_detects_invalid_content_address_before_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            issued, _ = self._values(Path(temporary))
            history = history_model.build_history(((issued.certificate, issued.certificate_audit),), history_id="audit-tamper-history")
            raw = history.to_dict()
            raw["content_address"] = history_model.HISTORY_PREFIX + ":tampered"
            with self.assertRaises(ValidationError):
                history_model.history_from_mapping(raw)
            self.assertEqual(history_model.address_history(history), history.content_address)

    def test_history_schemas_and_capabilities_are_closed_and_path_free(self):
        schemas = (history_model.manifest_schema(), history_model.entry_schema(), history_model.history_schema(), audit_model.check_schema(), audit_model.audit_schema())
        for schema in schemas:
            self.assertEqual(schema["type"], "object")
            self.assertFalse(schema["additionalProperties"])
            self.assertEqual(set(schema["required"]), set(schema["properties"]))
        descriptors = (history_model.capabilities(), audit_model.capabilities())
        encoded = json.dumps(descriptors, sort_keys=True)
        self.assertNotIn("C:\\Users\\", encoded)
        self.assertNotIn("/home/", encoded)
        self.assertTrue(all(isinstance(item, str) and item for item in history_model.capabilities()["features"]))

    def test_cli_builds_and_audits_history_from_package_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            issued, withheld = self._values(root)
            issued_package = package_model.build_package(issued.gate_runtime, issued.certificate, gate_audit=issued.gate_runtime.audit, gate_query=issued.gate_runtime.query, certificate_audit=issued.certificate_audit, certificate_query=issued.certificate_query)
            withheld_package = package_model.build_package(withheld.gate_runtime, withheld.certificate, gate_audit=withheld.gate_runtime.audit, gate_query=withheld.gate_runtime.query, certificate_audit=withheld.certificate_audit, certificate_query=withheld.certificate_query)
            issued_dir = root / "issued-package"
            withheld_dir = root / "withheld-package"
            package_model.write_package(issued_package, issued_dir)
            package_model.write_package(withheld_package, withheld_dir)
            history_dir = root / "cli-history"
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(["registry-federation-consensus-gate-certificate-history", "--input", str(issued_dir), "--input", str(withheld_dir), "--destination", str(history_dir), "--format", "summary"])
            self.assertEqual(code, 0)
            summary = json.loads(output.getvalue())
            self.assertEqual(summary["entry_count"], 2)
            self.assertTrue(history_dir.is_dir())
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(["registry-federation-consensus-gate-certificate-history-audit", "--input", str(history_dir), "--format", "summary"])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue())["passed_count"], len(audit_model.CHECK_IDS))


if __name__ == "__main__":
    unittest.main()
