"""Portable packet-diff policy review packet tests."""

# The test names mirror the full public boundary.
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
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_packet_diff import (
    build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_json,
)
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy import (
    build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy,
    evaluate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_json,
)
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit import (
    audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_json,
)
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet import (
    build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet,
    load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_capabilities,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_csv,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_json,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_schema,
    query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet,
    render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_markdown,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_value,
    write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet,
)
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_contracts import (
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_AUDIT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_DIFF,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_GATE,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_MANIFEST,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_REVIEW,
)
from tests.test_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyTest,
)


class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyTest(
            "runTest"
        )
        self.source.setUp()
        self.diff = self.source.recovery
        self.gate = (
            evaluate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(
                self.diff
            )
        )
        self.audit = (
            audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(
                self.gate
            )
        )

    def tearDown(self) -> None:
        self.source.tearDown()

    def _build(self):
        return (
            build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(
                self.diff, self.gate, self.audit
            )
        )

    def test_deterministic_five_member_round_trip(self) -> None:
        first = self._build()
        second = self._build()
        self.assertEqual(first.packet_bytes, second.packet_bytes)
        self.assertEqual(first.packet_address, second.packet_address)
        self.assertEqual(
            tuple(item.relative_path for item in first.members),
            (
                MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_MANIFEST,
                MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_DIFF,
                MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_GATE,
                MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_AUDIT,
                MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_REVIEW,
            ),
        )
        with zipfile.ZipFile(io.BytesIO(first.packet_bytes), "r") as archive:
            self.assertEqual(archive.namelist(), [item.relative_path for item in first.members])
            self.assertTrue(
                all(info.compress_type == zipfile.ZIP_STORED for info in archive.infolist())
            )
            self.assertTrue(
                all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist())
            )
        verification = verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(
            first.packet_bytes
        )
        self.assertTrue(verification.accepted)
        self.assertEqual(verification.entry_count, 5)
        self.assertEqual(verification.passed_count, 17)
        self.assertEqual(verification.failed_count, 0)
        loaded_diff, loaded_gate, loaded_audit, review = (
            load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(
                first.packet_bytes
            )
        )
        self.assertEqual(loaded_diff.content_address, self.diff.content_address)
        self.assertEqual(loaded_gate.content_address, self.gate.content_address)
        self.assertEqual(loaded_audit.content_address, self.audit.content_address)
        self.assertIn("Packet-Diff Policy Review Packet", review)
        verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_value(
            first
        )
        self.assertIn(
            "packet_address",
            module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_json(
                first
            ),
        )

    def test_blocked_policy_gate_is_preserved_but_audit_controls_packet_admission(self) -> None:
        blocked_policy = (
            build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(
                policy_id="test-blocked-packet-policy",
                maximum_changed_count=0,
                allowed_directions=("unchanged",),
                allowed_state_transitions=("unchanged",),
                require_previous_accepted=False,
                require_current_accepted=True,
                allow_unchanged=True,
            )
        )
        blocked_gate = (
            evaluate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(
                self.diff, blocked_policy
            )
        )
        blocked_audit = (
            audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(
                blocked_gate
            )
        )
        self.assertFalse(blocked_gate.accepted)
        self.assertTrue(blocked_audit.accepted)
        packet = (
            build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(
                self.diff, blocked_gate, blocked_audit
            )
        )
        verification = verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(
            packet.packet_bytes
        )
        self.assertTrue(verification.accepted)
        loaded_diff, loaded_gate, loaded_audit, _ = (
            load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(
                packet.packet_bytes
            )
        )
        self.assertEqual(loaded_diff.content_address, self.diff.content_address)
        self.assertFalse(loaded_gate.accepted)
        self.assertTrue(loaded_audit.accepted)

    def test_lineage_mismatch_and_audit_requirement_fail_closed(self) -> None:
        other_diff = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff(
            self.source.accepted_packet.packet_bytes,
            self.source.blocked_packet.packet_bytes,
        )
        other_gate = (
            evaluate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(
                other_diff
            )
        )
        other_audit = (
            audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(
                other_gate
            )
        )
        with self.assertRaises(ValidationError):
            build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(
                self.diff, other_gate, other_audit
            )
        blocked_policy = (
            build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(
                policy_id="test-blocked-audit-policy",
                maximum_changed_count=0,
                allowed_directions=("unchanged",),
                allowed_state_transitions=("unchanged",),
            )
        )
        blocked_gate = (
            evaluate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(
                self.diff, blocked_policy
            )
        )
        broken_audit = (
            audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(
                blocked_gate
            )
        )
        object.__setattr__(broken_audit, "accepted", False)
        with self.assertRaises(ValidationError):
            build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(
                self.diff, blocked_gate, broken_audit
            )

    def test_tampering_is_detected_at_member_and_nested_payload_boundaries(self) -> None:
        packet = self._build()
        with zipfile.ZipFile(io.BytesIO(packet.packet_bytes), "r") as source:
            output = io.BytesIO()
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as target:
                for info in source.infolist():
                    payload = source.read(info)
                    if (
                        info.filename
                        == MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_REVIEW
                    ):
                        payload += b"\ntampered\n"
                    target.writestr(info.filename, payload)
        verification = verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(
            output.getvalue()
        )
        self.assertFalse(verification.accepted)
        self.assertGreater(verification.failed_count, 0)
        with self.assertRaises(ValidationError):
            load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(
                output.getvalue()
            )

        with zipfile.ZipFile(io.BytesIO(packet.packet_bytes), "r") as source:
            output = io.BytesIO()
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as target:
                for info in source.infolist():
                    payload = source.read(info)
                    if (
                        info.filename
                        == MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_PACKET_GATE
                    ):
                        body = json.loads(payload)
                        body["accepted"] = not body["accepted"]
                        payload = (
                            json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n"
                        ).encode()
                    target.writestr(info.filename, payload)
        tampered_verification = verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(
            output.getvalue()
        )
        self.assertFalse(tampered_verification.accepted)
        self.assertIn("policy-gate-valid", {item.check_id for item in tampered_verification.checks})

    def test_queries_exports_and_source_free_markdown(self) -> None:
        packet = self._build()
        for resource in (
            "members",
            "summary",
            "manifest",
            "packet-diff",
            "policy-gate",
            "policy-audit",
            "review",
        ):
            result = query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(
                packet.packet_bytes, resource=resource
            )
            self.assertTrue(result["accepted"])
            self.assertEqual(result["total"], 1 if resource != "members" else 5)
        csv_text = (
            module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_csv(
                packet.packet_bytes
            )
        )
        self.assertIn("byte_address", csv_text)
        markdown = render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_markdown(
            packet.packet_bytes
        )
        self.assertIn("Independent audit", markdown)
        schema = module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_schema()
        capabilities = module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_capabilities()
        self.assertTrue(schema["blocked_gate_preserved"])
        self.assertTrue(schema["independent_audit_required"])
        self.assertIn("verify_exact_allowlist", capabilities["operations"])

    def test_atomic_write_and_cli_surfaces(self) -> None:
        packet = self._build()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diff_path = root / "diff.json"
            gate_path = root / "gate.json"
            audit_path = root / "audit.json"
            packet_path = root / "packet.zip"
            descriptor_path = root / "descriptor.json"
            verification_path = root / "verification.json"
            loaded_path = root / "loaded.json"
            query_path = root / "query.json"
            csv_path = root / "members.csv"
            schema_path = root / "schema.json"
            capabilities_path = root / "capabilities.json"
            diff_path.write_bytes(
                module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_json(
                    self.diff
                ).encode("utf-8")
            )
            gate_path.write_bytes(
                module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_json(
                    self.gate
                ).encode("utf-8")
            )
            audit_path.write_bytes(
                module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_json(
                    self.audit
                ).encode("utf-8")
            )
            write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(
                packet, root / "direct.zip"
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet",
                        "--diff",
                        str(diff_path),
                        "--policy-gate",
                        str(gate_path),
                        "--policy-audit",
                        str(audit_path),
                        "--destination",
                        str(packet_path),
                        "--format",
                        "summary",
                        "--output",
                        str(descriptor_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet-verify",
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
                        "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet-load",
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
                        "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet-query",
                        str(packet_path),
                        "--resource",
                        "policy-audit",
                        "--output",
                        str(query_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet-query",
                        str(packet_path),
                        "--resource",
                        "members",
                        "--format",
                        "csv",
                        "--output",
                        str(csv_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet-schema",
                        "--output",
                        str(schema_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet-capabilities",
                        "--output",
                        str(capabilities_path),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(verification_path.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(json.loads(query_path.read_text(encoding="utf-8"))["total"], 1)
            self.assertIn("packet_diff", loaded_path.read_text(encoding="utf-8"))
            self.assertIn("packet-diff.json", schema_path.read_text(encoding="utf-8"))
            self.assertIn("verify_review_replay", capabilities_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
