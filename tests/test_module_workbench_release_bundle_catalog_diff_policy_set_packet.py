"""Portable policy-set packet tests."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set import (
    evaluate_module_workbench_release_bundle_catalog_diff_policy_set,
    module_workbench_release_bundle_catalog_diff_policy_set_json,
    strict_release_module_workbench_release_bundle_catalog_diff_policy_set,
)
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_audit import (
    audit_module_workbench_release_bundle_catalog_diff_policy_set,
    module_workbench_release_bundle_catalog_diff_policy_set_audit_json,
)
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_packet import (
    build_module_workbench_release_bundle_catalog_diff_policy_set_packet,
    load_module_workbench_release_bundle_catalog_diff_policy_set_packet,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_capabilities,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_json,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_schema,
    query_module_workbench_release_bundle_catalog_diff_policy_set_packet,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_value,
    write_module_workbench_release_bundle_catalog_diff_policy_set_packet,
)
from tests.test_module_workbench_release_bundle_catalog_diff_policy import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicyTest,
)


class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source = ModuleWorkbenchReleaseBundleCatalogDiffPolicyTest("runTest")
        self.source.setUp()
        policy_set = strict_release_module_workbench_release_bundle_catalog_diff_policy_set()
        self.gate = evaluate_module_workbench_release_bundle_catalog_diff_policy_set(
            self.source.diff, policy_set
        )
        self.audit = audit_module_workbench_release_bundle_catalog_diff_policy_set(self.gate)

    def tearDown(self) -> None:
        self.source.tearDown()

    def test_deterministic_round_trip_and_queries(self) -> None:
        first = build_module_workbench_release_bundle_catalog_diff_policy_set_packet(
            self.gate, self.audit
        )
        second = build_module_workbench_release_bundle_catalog_diff_policy_set_packet(
            self.gate, self.audit
        )
        self.assertEqual(first.packet_bytes, second.packet_bytes)
        self.assertEqual(first.packet_address, second.packet_address)
        verification = verify_module_workbench_release_bundle_catalog_diff_policy_set_packet(
            first.packet_bytes
        )
        self.assertTrue(verification.accepted)
        self.assertEqual(verification.passed_count, 14)
        gate, audit, review = load_module_workbench_release_bundle_catalog_diff_policy_set_packet(
            first.packet_bytes
        )
        self.assertEqual(gate.content_address, self.gate.content_address)
        self.assertEqual(audit.content_address, self.audit.content_address)
        self.assertIn("Policy-Set Packet", review)
        self.assertEqual(
            query_module_workbench_release_bundle_catalog_diff_policy_set_packet(
                first.packet_bytes, resource="members"
            )["total"],
            4,
        )
        self.assertTrue(
            module_workbench_release_bundle_catalog_diff_policy_set_packet_schema()["source_free"]
        )
        self.assertTrue(
            module_workbench_release_bundle_catalog_diff_policy_set_packet_capabilities()[
                "deterministic"
            ]
        )
        verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_value(first)
        self.assertIn(
            "packet_address",
            module_workbench_release_bundle_catalog_diff_policy_set_packet_json(first),
        )

    def test_atomic_write_and_tamper_rejection(self) -> None:
        packet = build_module_workbench_release_bundle_catalog_diff_policy_set_packet(
            self.gate, self.audit
        )
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "packet.zip"
            write_module_workbench_release_bundle_catalog_diff_policy_set_packet(
                packet, destination
            )
            self.assertEqual(destination.read_bytes(), packet.packet_bytes)
            with self.assertRaises(ValidationError):
                write_module_workbench_release_bundle_catalog_diff_policy_set_packet(
                    packet, destination
                )

        with zipfile.ZipFile(io.BytesIO(packet.packet_bytes), "r") as source:
            output = io.BytesIO()
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as target:
                for info in source.infolist():
                    payload = source.read(info)
                    if info.filename == "review.md":
                        payload += b"tampered\n"
                    target.writestr(info.filename, payload)
        verification = verify_module_workbench_release_bundle_catalog_diff_policy_set_packet(
            output.getvalue()
        )
        self.assertFalse(verification.accepted)
        self.assertGreater(verification.failed_count, 0)
        with self.assertRaises(ValidationError):
            load_module_workbench_release_bundle_catalog_diff_policy_set_packet(output.getvalue())

    def test_manifest_and_payload_inputs_are_canonical(self) -> None:
        gate_bytes = module_workbench_release_bundle_catalog_diff_policy_set_json(self.gate)
        audit_bytes = module_workbench_release_bundle_catalog_diff_policy_set_audit_json(self.audit)
        self.assertEqual(json.loads(gate_bytes)["content_address"], self.gate.content_address)
        self.assertEqual(json.loads(audit_bytes)["content_address"], self.audit.content_address)

    def test_cli_build_verify_load_query_and_contract_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gate_path = root / "gate.json"
            audit_path = root / "audit.json"
            packet_path = root / "packet.zip"
            descriptor_path = root / "descriptor.json"
            verification_path = root / "verification.json"
            loaded_path = root / "loaded.json"
            query_path = root / "query.json"
            schema_path = root / "schema.json"
            capabilities_path = root / "capabilities.json"
            gate_path.write_bytes(
                module_workbench_release_bundle_catalog_diff_policy_set_json(self.gate).encode(
                    "utf-8"
                )
            )
            audit_path.write_bytes(
                module_workbench_release_bundle_catalog_diff_policy_set_audit_json(
                    self.audit
                ).encode("utf-8")
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-packet",
                        "--gate",
                        str(gate_path),
                        "--audit",
                        str(audit_path),
                        "--destination",
                        str(packet_path),
                        "--output",
                        str(descriptor_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-packet-verify",
                        str(packet_path),
                        "--output",
                        str(verification_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-packet-load",
                        str(packet_path),
                        "--output",
                        str(loaded_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-packet-query",
                        str(packet_path),
                        "--resource",
                        "audit",
                        "--output",
                        str(query_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-packet-schema",
                        "--output",
                        str(schema_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-packet-capabilities",
                        "--output",
                        str(capabilities_path),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(verification_path.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(json.loads(query_path.read_text(encoding="utf-8"))["total"], 1)
            self.assertIn("gate", loaded_path.read_text(encoding="utf-8"))
            self.assertIn("members", schema_path.read_text(encoding="utf-8"))
            self.assertIn("verify_member_bytes", capabilities_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
