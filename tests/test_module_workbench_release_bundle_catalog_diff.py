"""Portable release-bundle catalog diff tests."""

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
    load_module_workbench_release_bundle_catalog_diff,
    module_workbench_release_bundle_catalog_diff_capabilities,
    module_workbench_release_bundle_catalog_diff_csv,
    module_workbench_release_bundle_catalog_diff_json,
    module_workbench_release_bundle_catalog_diff_schema,
    query_module_workbench_release_bundle_catalog_diff,
    render_module_workbench_release_bundle_catalog_diff_markdown,
    verify_module_workbench_release_bundle_catalog_diff,
    verify_module_workbench_release_bundle_catalog_diff_value,
)
from glio_noncode.serialization import canonical_json
from tests.test_module_workbench import ModuleWorkbenchFixture


class ModuleWorkbenchReleaseBundleCatalogDiffTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = ModuleWorkbenchFixture("runTest")
        self.fixture.setUp()
        archive = build_module_workbench_archive(self.fixture.report())
        self.alpha = build_module_workbench_release_bundle(archive, archive, bundle_id="alpha")
        self.beta = build_module_workbench_release_bundle(archive, archive, bundle_id="beta")
        self.delta = build_module_workbench_release_bundle(archive, archive, bundle_id="delta")
        diff = build_module_workbench_archive_diff(archive, archive)
        gate = evaluate_module_workbench_archive_diff_policy(
            diff, build_module_workbench_archive_diff_policy(minimum_score_delta=0.01)
        )
        self.alpha_blocked = build_module_workbench_release_bundle(
            archive,
            archive,
            diff=diff,
            policy_gate=gate,
            bundle_id="alpha",
        )
        self.gamma = build_module_workbench_release_bundle(archive, archive, bundle_id="gamma")
        self.previous = build_module_workbench_release_bundle_catalog(
            [self.alpha, self.beta, self.delta], catalog_id="previous-catalog"
        )
        self.current = build_module_workbench_release_bundle_catalog(
            [self.alpha_blocked, self.beta, self.gamma], catalog_id="current-catalog"
        )

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def test_deterministic_four_way_classification_and_projections(self) -> None:
        first = build_module_workbench_release_bundle_catalog_diff(self.previous, self.current)
        second = build_module_workbench_release_bundle_catalog_diff(self.previous, self.current)
        self.assertEqual(
            module_workbench_release_bundle_catalog_diff_json(first),
            module_workbench_release_bundle_catalog_diff_json(second),
        )
        self.assertEqual(
            (first.added_count, first.changed_count, first.removed_count, first.unchanged_count),
            (1, 1, 1, 1),
        )
        self.assertEqual(first.direction.value, "changed")
        self.assertEqual(first.state_transition.value, "accepted_to_blocked")
        verify_module_workbench_release_bundle_catalog_diff_value(first)
        verification = verify_module_workbench_release_bundle_catalog_diff(first)
        self.assertTrue(verification.accepted)
        self.assertEqual(verification.failed_count, 0)
        restored = load_module_workbench_release_bundle_catalog_diff(
            module_workbench_release_bundle_catalog_diff_json(first).encode("utf-8")
        )
        self.assertEqual(restored.content_address, first.content_address)
        self.assertEqual(
            query_module_workbench_release_bundle_catalog_diff(first, kind="changed")["total"],
            1,
        )
        self.assertEqual(
            query_module_workbench_release_bundle_catalog_diff(first, direction="regressed")[
                "total"
            ],
            1,
        )
        self.assertIn("bundle_id", module_workbench_release_bundle_catalog_diff_csv(first))
        self.assertIn(
            "# Module Workbench Release Bundle Catalog Diff",
            render_module_workbench_release_bundle_catalog_diff_markdown(first),
        )
        self.assertTrue(module_workbench_release_bundle_catalog_diff_schema()["source_free"])
        self.assertTrue(module_workbench_release_bundle_catalog_diff_capabilities()["payload_free"])

    def test_tampering_and_invalid_inputs_fail_closed(self) -> None:
        diff = build_module_workbench_release_bundle_catalog_diff(self.previous, self.current)
        body = json.loads(module_workbench_release_bundle_catalog_diff_json(diff))
        body["changes"][0]["direction"] = "improved"
        tampered = (canonical_json(body) + "\n").encode("utf-8")
        verification = verify_module_workbench_release_bundle_catalog_diff(tampered)
        self.assertFalse(verification.accepted)
        self.assertGreater(verification.failed_count, 0)
        with self.assertRaises(ValidationError):
            load_module_workbench_release_bundle_catalog_diff(tampered)
        with self.assertRaises(ValidationError):
            query_module_workbench_release_bundle_catalog_diff(diff, kind="unknown")

    def test_cli_diff_verify_query_and_contract_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous = root / "previous.json"
            current = root / "current.json"
            output = root / "diff.json"
            verification = root / "verification.json"
            query = root / "query.json"
            write_module_workbench_release_bundle_catalog(self.previous, previous)
            write_module_workbench_release_bundle_catalog(self.current, current)
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff",
                        "--left-catalog",
                        str(previous),
                        "--right-catalog",
                        str(current),
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-verify",
                        str(output),
                        "--output",
                        str(verification),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-query",
                        str(output),
                        "--direction",
                        "regressed",
                        "--limit",
                        "2",
                        "--output",
                        str(query),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(verification.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(json.loads(query.read_text(encoding="utf-8"))["total"], 1)
            schema = root / "schema.json"
            caps = root / "caps.json"
            self.assertEqual(
                main(
                    ["module-workbench-release-bundle-catalog-diff-schema", "--output", str(schema)]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-diff-capabilities",
                        "--output",
                        str(caps),
                    ]
                ),
                0,
            )
            self.assertIn("state_transitions", schema.read_text(encoding="utf-8"))
            self.assertIn("field_level_deltas", caps.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
