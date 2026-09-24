"""Source-free longitudinal comparisons for policy-set packets."""

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
    load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_capabilities,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_csv,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_json,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_schema,
    query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff,
    render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_markdown,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff,
)
from tests.test_module_workbench_release_bundle_catalog_diff_policy import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicyTest,
)


class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffTest(unittest.TestCase):
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

    def tearDown(self) -> None:
        self.source.tearDown()

    def test_improvement_round_trip_and_replay(self) -> None:
        value = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff(
            self.blocked_packet.packet_bytes,
            self.accepted_packet.packet_bytes,
        )
        self.assertEqual(value.direction.value, "improved")
        self.assertEqual(value.state_transition.value, "blocked_to_accepted")
        self.assertGreater(value.changed_count, 0)
        verification = verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff(
            value
        )
        self.assertTrue(verification.accepted)
        self.assertEqual(verification.passed_count, 7)
        restored = load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff(
            module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_json(value).encode()
        )
        self.assertEqual(restored.content_address, value.content_address)
        self.assertEqual(
            query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff(value)[
                "total"
            ],
            value.changed_count,
        )
        self.assertIn(
            "field_name",
            module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_csv(value),
        )
        self.assertIn(
            "blocked_to_accepted",
            render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_markdown(
                value
            ),
        )

    def test_unchanged_and_tamper_rejection(self) -> None:
        value = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff(
            self.accepted_packet.packet_bytes,
            self.accepted_packet.packet_bytes,
        )
        self.assertEqual(value.direction.value, "unchanged")
        self.assertEqual(value.changed_count, 0)
        self.assertTrue(
            verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff(
                value
            ).accepted
        )
        body = json.loads(
            module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_json(value)
        )
        body["current_accepted"] = not body["current_accepted"]
        with self.assertRaises(ValidationError):
            load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff(
                (json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n").encode()
            )

    def test_contract_surface(self) -> None:
        schema = module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_schema()
        capabilities = (
            module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_capabilities()
        )
        self.assertTrue(schema["source_free"])
        self.assertTrue(schema["timestamp_free"])
        self.assertIn("compare_verified_packets", capabilities["operations"])

    def test_cli_compare_verify_and_query(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left = root / "left.zip"
            right = root / "right.zip"
            diff = root / "diff.json"
            verification = root / "verification.json"
            query = root / "query.json"
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
                        "--format",
                        "summary",
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-verify",
                        str(diff),
                        "--output",
                        str(verification),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-query",
                        str(diff),
                        "--field",
                        "gate_accepted",
                        "--output",
                        str(query),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(verification.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(json.loads(query.read_text(encoding="utf-8"))["total"], 1)


if __name__ == "__main__":
    unittest.main()
