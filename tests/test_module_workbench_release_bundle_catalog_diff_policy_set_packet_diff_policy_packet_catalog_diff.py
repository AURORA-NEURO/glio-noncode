"""Source-free packet catalog comparison and admission tests."""

# ruff: noqa: E501

from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
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
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_capabilities,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_csv,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_json,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_schema,
    query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff,
    render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_markdown,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_value,
    write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff,
)
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_contracts import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffDirection,
)
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy import (
    evaluate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_capabilities,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_csv,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_json,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_schema,
    release_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy,
    render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_markdown,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_gate,
    write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy,
)
from tests.test_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketTest,
)


class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketTest("runTest")
        self.source.setUp()
        self.packet = self.source._build()
        self.second = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(self.source.diff, self.source.gate, self.source.audit, packet_id="catalog-candidate-second")

    def tearDown(self) -> None:
        self.source.tearDown()

    def test_added_packet_diff_and_policy_modes(self) -> None:
        baseline = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog([self.packet], catalog_id="baseline")
        candidate = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog([self.packet, self.second], catalog_id="candidate")
        diff = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff(baseline, candidate, diff_id="demo-diff")
        self.assertEqual(diff.added_count, 1)
        self.assertEqual(diff.changed_count, 0)
        self.assertEqual(diff.removed_count, 0)
        self.assertEqual(diff.direction, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffDirection.CHANGED)
        self.assertTrue(verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff(diff).accepted)
        strict = evaluate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy(diff)
        release = evaluate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy(diff, release_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy())
        self.assertFalse(strict.accepted)
        self.assertTrue(release.accepted)
        self.assertGreater(strict.failed_count, 0)
        verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_gate(release)

    def test_unchanged_round_trip_query_exports_and_persistence(self) -> None:
        baseline = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog([self.packet], catalog_id="same")
        candidate = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog([self.packet], catalog_id="same")
        diff = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff(baseline, candidate)
        self.assertEqual(diff.unchanged_count, 1)
        self.assertEqual(diff.direction.value, "unchanged")
        result = query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff(diff, kind="unchanged")
        self.assertEqual(result["total"], 1)
        self.assertIn("packet_id", module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_csv(diff))
        self.assertIn("Packet", render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_markdown(diff))
        self.assertIn("diff_id", module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_json(diff))
        self.assertTrue(module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_schema()["source_free"])
        self.assertTrue(module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_capabilities()["payload_free"])
        gate = evaluate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy(diff)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "diff.json"
            write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff(diff, path)
            self.assertEqual(path.read_text(encoding="utf-8"), module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_json(diff))
            gate_path = Path(directory) / "gate.json"
            write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy(gate, gate_path)
            self.assertEqual(gate_path.read_text(encoding="utf-8"), module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_json(gate))
        self.assertIn("check_id", module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_csv(gate))
        self.assertIn("Policy", render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_markdown(gate))
        self.assertTrue(module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_schema()["source_free"])
        self.assertTrue(module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_capabilities()["source_free"])

    def test_tampered_diff_fails_closed(self) -> None:
        catalog = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog([self.packet], catalog_id="tamper")
        diff = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff(catalog, catalog)
        with self.assertRaises(ValidationError):
            verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_value(replace(diff, diff_id="tampered"))

    def test_cli_diff_and_release_policy_commands(self) -> None:
        baseline = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog([self.packet], catalog_id="cli-baseline")
        candidate = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog([self.packet, self.second], catalog_id="cli-candidate")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline_path, candidate_path = root / "baseline.json", root / "candidate.json"
            diff_path, gate_path = root / "diff.json", root / "gate.json"
            baseline_path.write_bytes(baseline.catalog_bytes)
            candidate_path.write_bytes(candidate.catalog_bytes)
            self.assertEqual(main(["module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet-catalog-diff", "--previous-catalog", str(baseline_path), "--current-catalog", str(candidate_path), "--destination", str(diff_path)]), 0)
            self.assertEqual(main(["module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-packet-catalog-diff-policy", str(diff_path), "--profile", "release", "--destination", str(gate_path)]), 0)
            self.assertTrue(gate_path.is_file())


if __name__ == "__main__":
    unittest.main()
