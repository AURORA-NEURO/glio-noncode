"""Release-bundle catalog diff policy-set tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.module_workbench_release_bundle_catalog_diff import (
    module_workbench_release_bundle_catalog_diff_json,
)
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set import (
    evaluate_module_workbench_release_bundle_catalog_diff_policy_set,
    load_module_workbench_release_bundle_catalog_diff_policy_set_gate,
    module_workbench_release_bundle_catalog_diff_policy_set_capabilities,
    module_workbench_release_bundle_catalog_diff_policy_set_csv,
    module_workbench_release_bundle_catalog_diff_policy_set_json,
    module_workbench_release_bundle_catalog_diff_policy_set_schema,
    query_module_workbench_release_bundle_catalog_diff_policy_set,
    render_module_workbench_release_bundle_catalog_diff_policy_set_markdown,
    strict_release_module_workbench_release_bundle_catalog_diff_policy_set,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_gate,
)
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set_contracts import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySet,
)
from tests.test_module_workbench_release_bundle_catalog_diff_policy import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicyTest,
)


class ModuleWorkbenchReleaseBundleCatalogDiffPolicySetTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source = ModuleWorkbenchReleaseBundleCatalogDiffPolicyTest("runTest")
        self.source.setUp()

    def tearDown(self) -> None:
        self.source.tearDown()

    def test_any_selection_preserves_strict_failure_and_release_admission(self) -> None:
        policy_set = strict_release_module_workbench_release_bundle_catalog_diff_policy_set()
        gate = evaluate_module_workbench_release_bundle_catalog_diff_policy_set(
            self.source.diff, policy_set
        )
        self.assertTrue(gate.accepted)
        self.assertEqual(gate.policy_set.selection_mode, "any")
        self.assertEqual(gate.passed_policy_count, 1)
        self.assertEqual(gate.failed_policy_count, 1)
        self.assertEqual(
            tuple(item.policy.policy_id for item in gate.gates),
            (
                "module-workbench-release-bundle-catalog-diff-release",
                "module-workbench-release-bundle-catalog-diff-strict",
            ),
        )

    def test_all_selection_and_query_round_trip(self) -> None:
        any_gate = evaluate_module_workbench_release_bundle_catalog_diff_policy_set(
            self.source.diff,
            strict_release_module_workbench_release_bundle_catalog_diff_policy_set(),
        )
        all_set = ModuleWorkbenchReleaseBundleCatalogDiffPolicySet(
            policy_set_id=any_gate.policy_set.policy_set_id,
            selection_mode="all",
            policies=any_gate.policy_set.policies,
            content_address="pending",
        )
        from glio_noncode.module_workbench_release_bundle_catalog_diff_policy_set import (
            build_module_workbench_release_bundle_catalog_diff_policy_set,
        )

        all_set = build_module_workbench_release_bundle_catalog_diff_policy_set(
            all_set.policies,
            policy_set_id="module-workbench-release-bundle-catalog-diff-strict-and-release-set",
            selection_mode="all",
        )
        gate = evaluate_module_workbench_release_bundle_catalog_diff_policy_set(
            self.source.diff, all_set
        )
        self.assertFalse(gate.accepted)
        verify_module_workbench_release_bundle_catalog_diff_policy_set_gate(gate)
        restored = load_module_workbench_release_bundle_catalog_diff_policy_set_gate(
            module_workbench_release_bundle_catalog_diff_policy_set_json(gate).encode("utf-8")
        )
        self.assertEqual(restored.content_address, gate.content_address)
        self.assertEqual(
            query_module_workbench_release_bundle_catalog_diff_policy_set(gate, accepted=True)[
                "total"
            ],
            1,
        )
        self.assertEqual(
            query_module_workbench_release_bundle_catalog_diff_policy_set(gate, accepted=False)[
                "total"
            ],
            1,
        )
        self.assertIn(
            "policy_id", module_workbench_release_bundle_catalog_diff_policy_set_csv(gate)
        )
        self.assertIn(
            "# Module Workbench Release Bundle Catalog Diff Policy Set",
            render_module_workbench_release_bundle_catalog_diff_policy_set_markdown(gate),
        )
        self.assertTrue(module_workbench_release_bundle_catalog_diff_policy_set_schema()["source_free"])
        self.assertTrue(
            module_workbench_release_bundle_catalog_diff_policy_set_capabilities()["deterministic"]
        )

    def test_tamper_rejection_and_cli_contracts(self) -> None:
        gate = evaluate_module_workbench_release_bundle_catalog_diff_policy_set(
            self.source.diff,
            strict_release_module_workbench_release_bundle_catalog_diff_policy_set(),
        )
        body = json.loads(module_workbench_release_bundle_catalog_diff_policy_set_json(gate))
        body["accepted"] = not body["accepted"]
        with self.assertRaises(ValidationError):
            load_module_workbench_release_bundle_catalog_diff_policy_set_gate(
                (json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
            )
        body = json.loads(module_workbench_release_bundle_catalog_diff_policy_set_json(gate))
        body["policy_set"]["policies"].append("invalid-policy")
        with self.assertRaises(ValidationError):
            load_module_workbench_release_bundle_catalog_diff_policy_set_gate(body)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diff = root / "diff.json"
            gate_path = root / "policy-set.json"
            verification = root / "verification.json"
            query = root / "query.json"
            schema = root / "schema.json"
            capabilities = root / "capabilities.json"
            diff.write_bytes(module_workbench_release_bundle_catalog_diff_json(self.source.diff).encode("utf-8"))
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set",
                        "--diff",
                        str(diff),
                        "--policy",
                        "strict",
                        "--policy",
                        "release",
                        "--selection-mode",
                        "any",
                        "--destination",
                        str(gate_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-verify",
                        str(gate_path),
                        "--output",
                        str(verification),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-query",
                        str(gate_path),
                        "--accepted",
                        "--output",
                        str(query),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-schema",
                        "--output",
                        str(schema),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-set-capabilities",
                        "--output",
                        str(capabilities),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(verification.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(json.loads(query.read_text(encoding="utf-8"))["total"], 1)
            self.assertIn("selection_modes", schema.read_text(encoding="utf-8"))
            self.assertIn("select_any_policy", capabilities.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
