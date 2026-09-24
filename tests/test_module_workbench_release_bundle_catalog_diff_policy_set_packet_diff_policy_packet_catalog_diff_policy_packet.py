"""Portable source-free packet-catalog diff policy packet tests."""

# ruff: noqa: E501

from __future__ import annotations

import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet import (
    build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet,
)
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog import (
    build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog,
)
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff import (
    build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_json,
)
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy import (
    evaluate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_json,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_schema,
)
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit import (
    audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit_json,
)
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet import (
    build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet,
    load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_capabilities,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_csv,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_json,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_schema,
    query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet,
    render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_markdown,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_value,
    write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet,
)
from tests.test_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketTest,
)


class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketTest("runTest")
        self.source.setUp()
        first = self.source._build()
        second = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(self.source.diff, self.source.gate, self.source.audit, packet_id="catalog-candidate-second")
        baseline = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog([first], catalog_id="baseline")
        candidate = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog([first, second], catalog_id="candidate")
        self.diff = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff(baseline, candidate, diff_id="catalog-review")
        self.gate = evaluate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy(self.diff)
        self.audit = audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy(self.gate)

    def tearDown(self) -> None:
        self.source.tearDown()

    def _build(self):
        return build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(self.diff, self.gate, self.audit, packet_id="catalog-review-packet")

    def test_deterministic_five_member_round_trip(self) -> None:
        first = self._build()
        second = self._build()
        self.assertEqual(first.packet_bytes, second.packet_bytes)
        self.assertEqual(first.packet_address, second.packet_address)
        with zipfile.ZipFile(io.BytesIO(first.packet_bytes)) as archive:
            self.assertEqual(archive.namelist(), ["manifest.json", "catalog-diff.json", "policy-gate.json", "policy-audit.json", "review.md"])
            self.assertTrue(all(info.compress_type == zipfile.ZIP_STORED for info in archive.infolist()))
            self.assertTrue(all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist()))
        verification = verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(first.packet_bytes)
        self.assertTrue(verification.accepted)
        self.assertEqual((verification.entry_count, verification.passed_count, verification.failed_count), (5, 10, 0))
        loaded_diff, loaded_gate, loaded_audit, review = load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(first.packet_bytes)
        self.assertEqual(loaded_diff.content_address, self.diff.content_address)
        self.assertEqual(loaded_gate.content_address, self.gate.content_address)
        self.assertEqual(loaded_audit.content_address, self.audit.content_address)
        self.assertIn("Packet Catalog Diff Policy Review Packet", review)
        verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_value(first)

    def test_blocked_gate_is_retained_when_independent_audit_passes(self) -> None:
        self.assertFalse(self.gate.accepted)
        self.assertTrue(self.audit.accepted)
        packet = self._build()
        self.assertTrue(verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(packet.packet_bytes).accepted)
        loaded_diff, loaded_gate, loaded_audit, _ = load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(packet.packet_bytes)
        self.assertEqual(loaded_diff.content_address, self.diff.content_address)
        self.assertFalse(loaded_gate.accepted)
        self.assertTrue(loaded_audit.accepted)

    def test_tampered_review_and_unsafe_member_fail_closed(self) -> None:
        packet = self._build()
        with zipfile.ZipFile(io.BytesIO(packet.packet_bytes)) as source:
            output = io.BytesIO()
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as target:
                for info in source.infolist():
                    payload = source.read(info)
                    if info.filename == "review.md":
                        payload += b"\ntampered\n"
                    target.writestr(info.filename, payload)
        verification = verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(output.getvalue())
        self.assertFalse(verification.accepted)
        with self.assertRaises(ValidationError):
            load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(output.getvalue())

    def test_queries_exports_and_cli_are_source_free(self) -> None:
        packet = self._build()
        for resource in ("members", "summary", "catalog-diff", "policy-gate", "policy-audit", "review"):
            result = query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(packet.packet_bytes, resource=resource)
            self.assertEqual(result["resource"], resource)
        self.assertIn("verify_addresses", module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_capabilities()["operations"])
        self.assertIn("relative_path", module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_csv(packet.packet_bytes))
        self.assertIn("Catalog comparison", render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_markdown(packet.packet_bytes))
        self.assertIn("packet_address", module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_json(packet))
        self.assertTrue(module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_schema()["source_free"])
        self.assertTrue(module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_schema()["source_free"])

    def test_cli_and_atomic_write_round_trip(self) -> None:
        packet = self._build()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diff_path, gate_path, audit_path = root / "diff.json", root / "gate.json", root / "audit.json"
            packet_path, verification_path, query_path = root / "packet.zip", root / "verification.json", root / "query.json"
            diff_path.write_bytes(module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_json(self.diff).encode("utf-8"))
            gate_path.write_bytes(module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_json(self.gate).encode("utf-8"))
            audit_path.write_bytes(module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit_json(self.audit).encode("utf-8"))
            write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(packet, root / "direct.zip")
            command = "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet-catalog-diff-policy-packet"
            self.assertEqual(main([command, "--diff", str(diff_path), "--gate", str(gate_path), "--audit", str(audit_path), "--destination", str(packet_path)]), 0)
            verify_command = command + "-verify"
            self.assertEqual(main([verify_command, str(packet_path), "--output", str(verification_path)]), 0)
            query_command = command + "-query"
            self.assertEqual(main([query_command, str(packet_path), "--resource", "members", "--output", str(query_path)]), 0)
            self.assertTrue(verification_path.is_file())
            self.assertEqual(json.loads(verification_path.read_text(encoding="utf-8"))["passed_count"], 10)
            self.assertEqual(json.loads(query_path.read_text(encoding="utf-8"))["total"], 5)


if __name__ == "__main__":
    unittest.main()
