"""Independent audit tests for packet catalog diff policy gates."""

# ruff: noqa: E501

from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet import (
    build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet,
)
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog import (
    build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog,
)
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff import (
    build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff,
)
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy import (
    evaluate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy,
    release_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy,
)
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit import (
    audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit_capabilities,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit_csv,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit_json,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit_schema,
    query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit,
    render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit_markdown,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit,
    write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit,
)
from tests.test_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketTest,
)


class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketCatalogDiffPolicyAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyPacketTest("runTest")
        self.source.setUp()
        self.packet = self.source._build()
        self.second = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet(self.source.diff, self.source.gate, self.source.audit, packet_id="audit-candidate-second")

    def tearDown(self) -> None:
        self.source.tearDown()

    def _gate(self):
        baseline = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog([self.packet], catalog_id="audit-baseline")
        candidate = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog([self.packet, self.second], catalog_id="audit-candidate")
        diff = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff(baseline, candidate)
        return evaluate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy(diff, release_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy())

    def test_audit_replays_gate_and_projects_checks(self) -> None:
        gate = self._gate()
        audit = audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy(gate)
        self.assertTrue(audit.accepted)
        self.assertEqual(audit.passed_count, 10)
        self.assertEqual(audit.failed_count, 0)
        verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit(audit)
        result = query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit(audit, passed=True)
        self.assertEqual(result["total"], 10)
        self.assertIn("check_id", module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit_csv(audit))
        self.assertIn("policy_gate_address", module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit_json(audit))
        self.assertIn("Policy Audit", render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit_markdown(audit))
        self.assertTrue(module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit_schema()["independent"])
        self.assertTrue(module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit_capabilities()["source_free"])

    def test_blocked_gate_can_still_have_accepted_independent_audit(self) -> None:
        baseline = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog([self.packet], catalog_id="strict-baseline")
        candidate = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog([self.packet, self.second], catalog_id="strict-candidate")
        diff = build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff(baseline, candidate)
        gate = evaluate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy(diff)
        self.assertFalse(gate.accepted)
        audit = audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy(gate)
        self.assertTrue(audit.accepted)

    def test_tamper_and_atomic_round_trip(self) -> None:
        audit = audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy(self._gate())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.json"
            write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit(audit, path)
            self.assertEqual(path.read_text(encoding="utf-8"), module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit_json(audit))
        with self.assertRaises(ValidationError):
            verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_packet_catalog_diff_policy_audit(replace(audit, diff_address="tampered"))


if __name__ == "__main__":
    unittest.main()
