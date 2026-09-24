"""Independent policy-set audit tests."""

from __future__ import annotations

import json
import tempfile
import unittest
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
    load_module_workbench_release_bundle_catalog_diff_policy_set_audit,
    module_workbench_release_bundle_catalog_diff_policy_set_audit_capabilities,
    module_workbench_release_bundle_catalog_diff_policy_set_audit_csv,
    module_workbench_release_bundle_catalog_diff_policy_set_audit_json,
    module_workbench_release_bundle_catalog_diff_policy_set_audit_schema,
    query_module_workbench_release_bundle_catalog_diff_policy_set_audit,
    render_module_workbench_release_bundle_catalog_diff_policy_set_audit_markdown,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_audit,
)
from tests.test_module_workbench_release_bundle_catalog_diff_policy import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicyTest,
)


class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source = ModuleWorkbenchReleaseBundleCatalogDiffPolicyTest("runTest")
        self.source.setUp()
        policy_set = strict_release_module_workbench_release_bundle_catalog_diff_policy_set()
        self.gate = evaluate_module_workbench_release_bundle_catalog_diff_policy_set(
            self.source.diff, policy_set
        )

    def tearDown(self) -> None:
        self.source.tearDown()

    def test_independent_replay_and_projections(self) -> None:
        audit = audit_module_workbench_release_bundle_catalog_diff_policy_set(self.gate)
        self.assertTrue(audit.accepted)
        self.assertEqual(audit.passed_count, 9)
        self.assertEqual(audit.failed_count, 0)
        verify_module_workbench_release_bundle_catalog_diff_policy_set_audit(audit)
        restored = load_module_workbench_release_bundle_catalog_diff_policy_set_audit(
            module_workbench_release_bundle_catalog_diff_policy_set_audit_json(audit).encode(
                "utf-8"
            )
        )
        self.assertEqual(restored.content_address, audit.content_address)
        self.assertEqual(
            query_module_workbench_release_bundle_catalog_diff_policy_set_audit(
                audit, passed=True
            )["total"],
            9,
        )
        self.assertIn(
            "check_id", module_workbench_release_bundle_catalog_diff_policy_set_audit_csv(audit)
        )
        self.assertIn(
            "# Module Workbench Release Bundle Catalog Diff Policy Set Audit",
            render_module_workbench_release_bundle_catalog_diff_policy_set_audit_markdown(audit),
        )
        self.assertTrue(module_workbench_release_bundle_catalog_diff_policy_set_audit_schema()["independent"])
        self.assertTrue(
            module_workbench_release_bundle_catalog_diff_policy_set_audit_capabilities()["deterministic"]
        )

    def test_tamper_rejection_and_cli_contracts(self) -> None:
        audit = audit_module_workbench_release_bundle_catalog_diff_policy_set(self.gate)
        body = json.loads(module_workbench_release_bundle_catalog_diff_policy_set_audit_json(audit))
        body["checks"][0]["passed"] = not body["checks"][0]["passed"]
        with self.assertRaises(ValidationError):
            load_module_workbench_release_bundle_catalog_diff_policy_set_audit(
                (json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n").encode(
                    "utf-8"
                )
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gate_path = root / "gate.json"
            audit_path = root / "audit.json"
            summary_path = root / "summary.json"
            verification_path = root / "verification.json"
            query_path = root / "query.json"
            schema_path = root / "schema.json"
            capabilities_path = root / "capabilities.json"
            gate_path.write_bytes(
                module_workbench_release_bundle_catalog_diff_policy_set_json(self.gate).encode(
                    "utf-8"
                )
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-audit",
                        str(gate_path),
                        "--destination",
                        str(audit_path),
                        "--format",
                        "summary",
                        "--output",
                        str(summary_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-audit-verify",
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
                        "module-workbench-release-bundle-catalog-diff-policy-set-audit-query",
                        str(audit_path),
                        "--passed",
                        "--output",
                        str(query_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-audit-schema",
                        "--output",
                        str(schema_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-audit-capabilities",
                        "--output",
                        str(capabilities_path),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(verification_path.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(json.loads(query_path.read_text(encoding="utf-8"))["total"], 9)
            self.assertIn("independent", schema_path.read_text(encoding="utf-8"))
            self.assertIn("audit_address_replay", capabilities_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
