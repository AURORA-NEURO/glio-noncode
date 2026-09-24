"""Release-bundle catalog diff policy tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.module_workbench_archive import build_module_workbench_archive
from glio_noncode.module_workbench_archive_diff import build_module_workbench_archive_diff
from glio_noncode.module_workbench_archive_diff_policy import (
    build_module_workbench_archive_diff_policy,
    evaluate_module_workbench_archive_diff_policy,
)
from glio_noncode.module_workbench_release_bundle import build_module_workbench_release_bundle
from glio_noncode.module_workbench_release_bundle_catalog import (
    build_module_workbench_release_bundle_catalog,
    write_module_workbench_release_bundle_catalog,
)
from glio_noncode.module_workbench_release_bundle_catalog_diff import (
    build_module_workbench_release_bundle_catalog_diff,
)
from glio_noncode.module_workbench_release_bundle_catalog_diff_policy import (
    default_module_workbench_release_bundle_catalog_diff_policy,
    evaluate_module_workbench_release_bundle_catalog_diff_policy,
    load_module_workbench_release_bundle_catalog_diff_policy_gate,
    module_workbench_release_bundle_catalog_diff_policy_capabilities,
    module_workbench_release_bundle_catalog_diff_policy_csv,
    module_workbench_release_bundle_catalog_diff_policy_json,
    module_workbench_release_bundle_catalog_diff_policy_schema,
    query_module_workbench_release_bundle_catalog_diff_policy,
    release_module_workbench_release_bundle_catalog_diff_policy,
    render_module_workbench_release_bundle_catalog_diff_policy_markdown,
    verify_module_workbench_release_bundle_catalog_diff_policy_gate,
)
from tests.test_module_workbench import ModuleWorkbenchFixture


class ModuleWorkbenchReleaseBundleCatalogDiffPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = ModuleWorkbenchFixture("runTest")
        self.fixture.setUp()
        archive = build_module_workbench_archive(self.fixture.report())
        self.accepted = build_module_workbench_release_bundle(
            archive, archive, bundle_id="accepted"
        )
        self.unchanged = build_module_workbench_release_bundle(
            archive, archive, bundle_id="unchanged"
        )
        diff = build_module_workbench_archive_diff(archive, archive)
        gate = evaluate_module_workbench_archive_diff_policy(
            diff, build_module_workbench_archive_diff_policy(minimum_score_delta=0.01)
        )
        self.blocked = build_module_workbench_release_bundle(
            archive, archive, diff=diff, policy_gate=gate, bundle_id="blocked"
        )
        self.previous = build_module_workbench_release_bundle_catalog(
            [self.blocked, self.unchanged], catalog_id="blocked-baseline"
        )
        self.current = build_module_workbench_release_bundle_catalog(
            [self.unchanged], catalog_id="accepted-candidate"
        )
        self.diff = build_module_workbench_release_bundle_catalog_diff(self.previous, self.current)

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def test_strict_blocks_and_release_accepts_recovery(self) -> None:
        strict = evaluate_module_workbench_release_bundle_catalog_diff_policy(
            self.diff, default_module_workbench_release_bundle_catalog_diff_policy()
        )
        release = evaluate_module_workbench_release_bundle_catalog_diff_policy(
            self.diff, release_module_workbench_release_bundle_catalog_diff_policy()
        )
        self.assertFalse(strict.accepted)
        self.assertTrue(release.accepted)
        self.assertEqual(self.diff.state_transition.value, "blocked_to_accepted")
        self.assertEqual(self.diff.removed_count, 1)
        self.assertGreater(strict.failed_count, 0)
        self.assertEqual(release.failed_count, 0)

    def test_round_trip_query_and_tamper_rejection(self) -> None:
        gate = evaluate_module_workbench_release_bundle_catalog_diff_policy(
            self.diff, release_module_workbench_release_bundle_catalog_diff_policy()
        )
        verify_module_workbench_release_bundle_catalog_diff_policy_gate(gate)
        restored = load_module_workbench_release_bundle_catalog_diff_policy_gate(
            module_workbench_release_bundle_catalog_diff_policy_json(gate).encode("utf-8")
        )
        self.assertEqual(restored.content_address, gate.content_address)
        self.assertEqual(
            query_module_workbench_release_bundle_catalog_diff_policy(gate, passed=False)["total"],
            0,
        )
        self.assertIn("check_id", module_workbench_release_bundle_catalog_diff_policy_csv(gate))
        self.assertIn(
            "# Module Workbench Release Bundle Catalog Diff Policy",
            render_module_workbench_release_bundle_catalog_diff_policy_markdown(gate),
        )
        self.assertTrue(module_workbench_release_bundle_catalog_diff_policy_schema()["source_free"])
        self.assertTrue(
            module_workbench_release_bundle_catalog_diff_policy_capabilities()["deterministic"]
        )
        body = json.loads(module_workbench_release_bundle_catalog_diff_policy_json(gate))
        body["checks"][0]["passed"] = not body["checks"][0]["passed"]
        with self.assertRaises(ValidationError):
            load_module_workbench_release_bundle_catalog_diff_policy_gate(
                (json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
            )

    def test_cli_policy_build_verify_query_and_contract_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous = root / "previous.json"
            current = root / "current.json"
            diff = root / "diff.json"
            gate = root / "gate.json"
            verification = root / "verification.json"
            query = root / "query.json"
            write_module_workbench_release_bundle_catalog(self.previous, previous)
            write_module_workbench_release_bundle_catalog(self.current, current)
            from glio_noncode.module_workbench_release_bundle_catalog_diff import (
                module_workbench_release_bundle_catalog_diff_json,
            )

            diff_value = build_module_workbench_release_bundle_catalog_diff(previous, current)
            diff.write_bytes(
                module_workbench_release_bundle_catalog_diff_json(diff_value).encode("utf-8")
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy",
                        "--diff",
                        str(diff),
                        "--maximum-removed-count",
                        "1",
                        "--allowed-direction",
                        "changed",
                        "--allow-unaccepted",
                        "--format",
                        "json",
                        "--output",
                        str(gate),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-verify",
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
                        "module-workbench-release-bundle-catalog-diff-policy-query",
                        str(gate),
                        "--failed",
                        "--limit",
                        "2",
                        "--output",
                        str(query),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(verification.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(json.loads(query.read_text(encoding="utf-8"))["total"], 0)
            schema = root / "schema.json"
            caps = root / "caps.json"
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-schema",
                        "--output",
                        str(schema),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-policy-capabilities",
                        "--output",
                        str(caps),
                    ]
                ),
                0,
            )
            self.assertIn("allowed_directions", schema.read_text(encoding="utf-8"))
            self.assertIn("evaluate_direction", caps.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
