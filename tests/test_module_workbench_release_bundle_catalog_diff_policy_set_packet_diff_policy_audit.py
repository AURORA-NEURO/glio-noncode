"""Independent audit tests for packet-diff policy gates."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy import (  # noqa: E501
    evaluate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_json,
)
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit import (  # noqa: E501
    audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy,
    load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_capabilities,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_csv,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_json,
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_schema,
    query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit,
    render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_markdown,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit,
)
from tests.test_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyTest,
)

load_packet_diff_policy_audit = (
    load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit
)
packet_diff_policy_audit_schema = (
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_schema
)
packet_diff_policy_audit_capabilities = (
    module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_capabilities
)


class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyTest(
            "runTest"
        )
        self.source.setUp()
        self.gate = (
            evaluate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(
                self.source.recovery
            )
        )

    def tearDown(self) -> None:
        self.source.tearDown()

    def test_audit_replays_gate_and_round_trips(self) -> None:
        audit = audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(
            self.gate
        )
        self.assertTrue(audit.accepted)
        self.assertEqual(audit.passed_count, 10)
        verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit(
            audit
        )
        restored = load_packet_diff_policy_audit(
            module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_json(
                audit
            ).encode()
        )
        self.assertEqual(restored.content_address, audit.content_address)
        self.assertEqual(
            query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit(
                audit, passed=False
            )["total"],
            0,
        )
        self.assertIn(
            "check_id",
            module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_csv(
                audit
            ),
        )
        self.assertIn(
            "policy-controls",
            render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_markdown(
                audit
            ),
        )

    def test_surface_and_tamper_rejection(self) -> None:
        schema = packet_diff_policy_audit_schema()
        capabilities = packet_diff_policy_audit_capabilities()
        self.assertTrue(schema["independent"])
        self.assertTrue(schema["source_free"])
        self.assertIn("audit_decision_replay", capabilities["operations"])
        audit = audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(
            self.gate
        )
        body = json.loads(
            module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_json(
                audit
            )
        )
        body["checks"][0]["passed"] = not body["checks"][0]["passed"]
        with self.assertRaises(ValidationError):
            load_packet_diff_policy_audit(
                (json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n").encode()
            )

    def test_cli_audit_verify_query_and_contract_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gate_path = root / "gate.json"
            audit_path = root / "audit.json"
            verification_path = root / "verification.json"
            query_path = root / "query.json"
            schema_path = root / "schema.json"
            capabilities_path = root / "capabilities.json"
            gate_path.write_bytes(
                module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_json(
                    self.gate
                ).encode()
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-audit",
                        str(gate_path),
                        "--destination",
                        str(audit_path),
                        "--format",
                        "summary",
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-audit-verify",
                        str(audit_path),
                        "--output",
                        str(verification_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-audit-query",
                        str(audit_path),
                        "--failed",
                        "--output",
                        str(query_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-audit-schema",
                        "--output",
                        str(schema_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-audit-capabilities",
                        "--output",
                        str(capabilities_path),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(verification_path.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(json.loads(query_path.read_text(encoding="utf-8"))["total"], 0)
            self.assertIn("independent", schema_path.read_text(encoding="utf-8"))
            self.assertIn("audit_gate_address", capabilities_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
