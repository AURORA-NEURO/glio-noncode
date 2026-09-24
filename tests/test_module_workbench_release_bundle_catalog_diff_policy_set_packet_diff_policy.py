"""Admission policy tests for portable policy-set packet diffs."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set import (
    default_module_workbench_release_bundle_catalog_diff_policy_set,
    evaluate_module_workbench_release_bundle_catalog_diff_policy_set,
    strict_release_module_workbench_release_bundle_catalog_diff_policy_set,
)
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_audit import (
    audit_module_workbench_release_bundle_catalog_diff_policy_set,
)
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_packet import (
    build_module_workbench_release_bundle_catalog_diff_policy_set_packet,
    write_module_workbench_release_bundle_catalog_diff_policy_set_packet,
)
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_packet_diff import (
    build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff,
)
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy import (  # noqa: E501
    evaluate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy,
    load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_gate,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_capabilities,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_csv,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_json,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_schema,
    query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy,
    release_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy,
    render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_markdown,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_gate,
)
from tests.test_module_workbench_release_bundle_catalog_diff_policy import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicyTest,
)

evaluate_packet_diff_policy = (
    evaluate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy
)
packet_diff_policy_capabilities = (
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_capabilities
)


class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source = ModuleWorkbenchReleaseBundleCatalogDiffPolicyTest("runTest")
        self.source.setUp()
        blocked_gate = evaluate_module_workbench_release_bundle_catalog_diff_policy_set(
            self.source.diff,
            default_module_workbench_release_bundle_catalog_diff_policy_set(),
        )
        accepted_gate = evaluate_module_workbench_release_bundle_catalog_diff_policy_set(
            self.source.diff,
            strict_release_module_workbench_release_bundle_catalog_diff_policy_set(),
        )
        self.blocked_packet = build_module_workbench_release_bundle_catalog_diff_policy_set_packet(
            blocked_gate,
            audit_module_workbench_release_bundle_catalog_diff_policy_set(blocked_gate),
        )
        self.accepted_packet = build_module_workbench_release_bundle_catalog_diff_policy_set_packet(
            accepted_gate,
            audit_module_workbench_release_bundle_catalog_diff_policy_set(accepted_gate),
        )
        self.recovery = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff(
            self.blocked_packet.packet_bytes,
            self.accepted_packet.packet_bytes,
        )

    def tearDown(self) -> None:
        self.source.tearDown()

    def test_recovery_policy_accepts_and_round_trips(self) -> None:
        gate = evaluate_packet_diff_policy(self.recovery)
        self.assertTrue(gate.accepted)
        self.assertEqual(gate.passed_count, 9)
        verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_gate(gate)
        restored = (
            load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_gate(
                module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_json(
                    gate
                ).encode()
            )
        )
        self.assertEqual(restored.content_address, gate.content_address)
        self.assertEqual(
            query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(
                gate, passed=False
            )["total"],
            0,
        )
        self.assertIn(
            "check_id",
            module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_csv(gate),
        )
        self.assertIn(
            "blocked_to_accepted",
            render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_markdown(
                gate
            ),
        )

    def test_strict_rejects_regression_release_retains_it(self) -> None:
        regression = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff(
            self.accepted_packet.packet_bytes,
            self.blocked_packet.packet_bytes,
        )
        strict_gate = evaluate_packet_diff_policy(regression)
        release_gate = evaluate_packet_diff_policy(
            regression,
            release_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(),
        )
        self.assertFalse(strict_gate.accepted)
        self.assertTrue(release_gate.accepted)
        self.assertGreater(strict_gate.failed_count, 0)
        self.assertEqual(regression.direction.value, "regressed")

    def test_surface_and_tamper_rejection(self) -> None:
        schema = module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_schema()
        capabilities = packet_diff_policy_capabilities()
        self.assertTrue(schema["source_free"])
        self.assertTrue(schema["timestamp_free"])
        self.assertIn("evaluate_current_state", capabilities["operations"])
        body = json.loads(
            module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_json(
                evaluate_packet_diff_policy(self.recovery)
            )
        )
        body["policy"]["maximum_changed_count"] = 0
        with self.assertRaises(ValidationError):
            load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_gate(
                (json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n").encode()
            )

    def test_cli_build_verify_query_and_contract_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left = root / "left.zip"
            right = root / "right.zip"
            diff = root / "diff.json"
            gate = root / "gate.json"
            verification = root / "verification.json"
            query = root / "query.json"
            schema = root / "schema.json"
            capabilities = root / "capabilities.json"
            write_module_workbench_release_bundle_catalog_diff_policy_set_packet(
                self.blocked_packet, left
            )
            write_module_workbench_release_bundle_catalog_diff_policy_set_packet(
                self.accepted_packet, right
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff",
                        "--left-packet",
                        str(left),
                        "--right-packet",
                        str(right),
                        "--destination",
                        str(diff),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy",
                        "--diff",
                        str(diff),
                        "--destination",
                        str(gate),
                        "--format",
                        "summary",
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-verify",
                        str(gate),
                        "--output",
                        str(verification),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-query",
                        str(gate),
                        "--failed",
                        "--output",
                        str(query),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-schema",
                        "--output",
                        str(schema),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-capabilities",
                        "--output",
                        str(capabilities),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(verification.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(json.loads(query.read_text(encoding="utf-8"))["total"], 0)
            self.assertIn("thresholds", schema.read_text(encoding="utf-8"))
            self.assertIn("evaluate_direction", capabilities.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
