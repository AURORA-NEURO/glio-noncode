"""Source-free packet review catalog tests."""

# ruff: noqa: E501

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet import (
    build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet,
)
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog import (
    build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog,
    load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_capabilities,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_csv,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_json,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_schema,
    query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog,
    render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_markdown,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_value,
    write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog,
)
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit import (
    audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit_capabilities,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit_csv,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit_json,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit_schema,
    render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit_markdown,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit,
)
from tests.test_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketTest,
)


class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketTest("runTest")
        self.source.setUp()
        self.packet = self.source._build()
        self.blocked_packet = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(
            self.source.diff,
            self.source.gate,
            self.source.audit,
            packet_id="catalog-second-packet",
        )

    def tearDown(self) -> None:
        self.source.tearDown()

    def test_deterministic_catalog_round_trip_and_audit(self) -> None:
        first = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog(
            [self.packet, self.blocked_packet], catalog_id="two-packet-catalog"
        )
        second = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog(
            [self.packet, self.blocked_packet], catalog_id="two-packet-catalog"
        )
        self.assertEqual(first.catalog_bytes, second.catalog_bytes)
        self.assertEqual(first.entry_count, 2)
        self.assertEqual(first.accepted_count, 2)
        self.assertEqual(first.policy_gate_blocked_count, 0)
        verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_value(first)
        verification = verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog(first.catalog_bytes)
        self.assertTrue(verification.accepted)
        self.assertEqual(verification.passed_count, 17)
        restored = load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog(first.catalog_bytes)
        self.assertEqual(restored.content_address, first.content_address)
        audit = audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog(restored)
        self.assertTrue(audit.accepted)
        self.assertEqual(audit.passed_count, 15)
        verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit(audit)

    def test_blocked_gate_evidence_is_preserved_in_catalog(self) -> None:
        blocked_policy = self.source._build()
        del blocked_policy
        from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy import (
            build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy,
            evaluate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy,
        )
        from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit import (
            audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy,
        )
        policy = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(
            policy_id="catalog-blocked-policy",
            maximum_changed_count=0,
            allowed_directions=("unchanged",),
            allowed_state_transitions=("unchanged",),
            require_previous_accepted=False,
            require_current_accepted=True,
            allow_unchanged=True,
        )
        gate = evaluate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(self.source.diff, policy)
        audit = audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(gate)
        packet = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(
            self.source.diff, gate, audit, packet_id="catalog-blocked-gate"
        )
        catalog = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog([packet])
        self.assertTrue(catalog.accepted)
        self.assertEqual(catalog.policy_gate_blocked_count, 1)
        self.assertFalse(catalog.entries[0].policy_gate_accepted)
        result = query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog(
            catalog.catalog_bytes, resource="entries", policy_gate_accepted=False
        )
        self.assertEqual(result["total"], 1)

    def test_duplicate_and_tampered_catalogs_fail_closed(self) -> None:
        with self.assertRaises(ValidationError):
            build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog(
                [self.packet, self.packet]
            )
        catalog = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog([self.packet])
        body = json.loads(catalog.catalog_bytes.decode("utf-8"))
        body["entries"][0]["packet_id"] = "tampered"
        tampered = (json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        verification = verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog(tampered)
        self.assertFalse(verification.accepted)
        with self.assertRaises(ValidationError):
            load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog(tampered)

    def test_queries_exports_schema_and_atomic_persistence(self) -> None:
        catalog = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog([self.packet])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog(catalog, path)
            self.assertEqual(path.read_bytes(), catalog.catalog_bytes)
            self.assertIn("packet_id", module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_csv(catalog.catalog_bytes))
        self.assertIn("catalog_address", module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_json(catalog))
        self.assertIn("Packet", render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_markdown(catalog))
        self.assertTrue(module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_schema()["source_free"])
        self.assertTrue(module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_capabilities()["payload_free"])
        audit = audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog(catalog)
        self.assertIn("check_id", module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit_csv(audit))
        self.assertIn("catalog_address", module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit_json(audit))
        self.assertIn("Catalog", render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit_markdown(audit))
        self.assertTrue(module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit_schema()["independent"])
        self.assertTrue(module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_audit_capabilities()["source_free"])

    def test_cli_catalog_and_audit_contract_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packet_a = root / "a.zip"
            packet_b = root / "b.zip"
            catalog = root / "catalog.json"
            audit = root / "audit.json"
            packet_a.write_bytes(self.packet.packet_bytes)
            packet_b.write_bytes(self.blocked_packet.packet_bytes)
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet-catalog",
                        "--packet",
                        str(packet_a),
                        "--packet",
                        str(packet_b),
                        "--catalog-id",
                        "cli-catalog",
                        "--destination",
                        str(catalog),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet-catalog-verify",
                        str(catalog),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet-catalog-audit",
                        str(catalog),
                        "--destination",
                        str(audit),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet-catalog-audit-verify",
                        str(audit),
                    ]
                ),
                0,
            )


if __name__ == "__main__":
    unittest.main()
