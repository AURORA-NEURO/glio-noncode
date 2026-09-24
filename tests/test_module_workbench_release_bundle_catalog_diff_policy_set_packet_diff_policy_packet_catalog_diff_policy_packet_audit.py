"""Independent audit tests for portable catalog-diff policy review packets."""

# ruff: noqa: E501

from __future__ import annotations

import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from glio_noncode.cli import main
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit import (
    audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet,
    load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit_capabilities,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit_csv,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit_json,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit_schema,
    query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit,
    render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit_markdown,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit,
    write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit,
)
from tests import (
    test_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet as packet_test,
)


class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source = packet_test.ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyPacketTest("runTest")
        self.source.setUp()
        self.packet = self.source._build()

    def tearDown(self) -> None:
        self.source.tearDown()

    def test_real_packet_has_fourteen_independent_checks(self) -> None:
        result = audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(self.packet.packet_bytes)
        self.assertTrue(result.accepted)
        self.assertEqual((result.entry_count, result.passed_count, result.failed_count), (5, 14, 0))
        self.assertEqual(result.packet_address, self.packet.packet_address)
        self.assertEqual(verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit(result), result)
        self.assertIn("review-replay", {item.check_id for item in result.checks})

    def test_source_free_round_trip_queries_and_projections(self) -> None:
        result = audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(self.packet.packet_bytes)
        loaded = load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit(module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit_json(result).encode("utf-8"))
        self.assertEqual(loaded, result)
        all_checks = query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit(loaded)
        passed_checks = query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit(loaded, passed=True)
        failed_checks = query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit(loaded, passed=False)
        self.assertEqual((all_checks["total"], passed_checks["total"], failed_checks["total"]), (14, 14, 0))
        self.assertIn("check_id", module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit_csv(loaded))
        self.assertIn("14 / 0", render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit_markdown(loaded))
        self.assertTrue(module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit_schema()["source_free"])
        self.assertTrue(module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit_capabilities()["independent"])

    def test_tampered_zip_fails_closed(self) -> None:
        with zipfile.ZipFile(io.BytesIO(self.packet.packet_bytes)) as source:
            output = io.BytesIO()
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as target:
                for info in source.infolist():
                    payload = source.read(info)
                    if info.filename == "review.md":
                        payload += b"\ntampered\n"
                    target.writestr(info.filename, payload)
        result = audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(output.getvalue())
        self.assertFalse(result.accepted)
        self.assertGreater(result.failed_count, 0)
        self.assertIn("input-readable", {item.check_id for item in result.checks})

    def test_atomic_write_and_cli_round_trip(self) -> None:
        result = audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet(self.packet.packet_bytes)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit_path = root / "audit.json"
            packet_path = root / "packet.zip"
            verify_path = root / "verification.json"
            query_path = root / "query.json"
            packet_path.write_bytes(self.packet.packet_bytes)
            write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_packet_audit(result, audit_path)
            command = "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet-catalog-diff-policy-packet-audit"
            self.assertEqual(main([command, str(packet_path), "--output", str(root / "summary.json")]), 0)
            self.assertEqual(main([command + "-verify", str(audit_path), "--output", str(verify_path)]), 0)
            self.assertEqual(main([command + "-query", str(audit_path), "--failed", "--output", str(query_path)]), 0)
            self.assertEqual(json.loads(verify_path.read_text(encoding="utf-8"))["accepted"], True)
            self.assertEqual(json.loads(query_path.read_text(encoding="utf-8"))["total"], 0)


if __name__ == "__main__":
    unittest.main()
