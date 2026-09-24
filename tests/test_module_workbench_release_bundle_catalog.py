"""Portable release-bundle catalog tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.module_workbench_archive import (
    build_module_workbench_archive,
    write_module_workbench_archive,
)
from glio_noncode.module_workbench_archive_diff import build_module_workbench_archive_diff
from glio_noncode.module_workbench_archive_diff_policy import (
    build_module_workbench_archive_diff_policy,
    evaluate_module_workbench_archive_diff_policy,
)
from glio_noncode.module_workbench_release_bundle import (
    build_module_workbench_release_bundle,
    write_module_workbench_release_bundle,
)
from glio_noncode.module_workbench_release_bundle_catalog import (
    build_module_workbench_release_bundle_catalog,
    load_module_workbench_release_bundle_catalog,
    module_workbench_release_bundle_catalog_capabilities,
    module_workbench_release_bundle_catalog_csv,
    module_workbench_release_bundle_catalog_json,
    module_workbench_release_bundle_catalog_schema,
    query_module_workbench_release_bundle_catalog,
    render_module_workbench_release_bundle_catalog_markdown,
    verify_module_workbench_release_bundle_catalog,
    verify_module_workbench_release_bundle_catalog_value,
)
from glio_noncode.serialization import canonical_json
from tests.test_module_workbench import ModuleWorkbenchFixture


class ModuleWorkbenchReleaseBundleCatalogTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = ModuleWorkbenchFixture("runTest")
        self.fixture.setUp()
        self.archive = build_module_workbench_archive(self.fixture.report())
        self.accepted_bundle = build_module_workbench_release_bundle(
            self.archive, self.archive, bundle_id="accepted-bundle"
        )
        diff = build_module_workbench_archive_diff(self.archive, self.archive)
        policy = build_module_workbench_archive_diff_policy(minimum_score_delta=0.01)
        gate = evaluate_module_workbench_archive_diff_policy(diff, policy)
        self.blocked_bundle = build_module_workbench_release_bundle(
            self.archive,
            self.archive,
            diff=diff,
            policy_gate=gate,
            bundle_id="blocked-bundle",
        )

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def test_deterministic_round_trip_and_projections(self) -> None:
        first = build_module_workbench_release_bundle_catalog([self.accepted_bundle])
        second = build_module_workbench_release_bundle_catalog([self.accepted_bundle])
        self.assertEqual(first.catalog_bytes, second.catalog_bytes)
        verify_module_workbench_release_bundle_catalog_value(first)
        verification = verify_module_workbench_release_bundle_catalog(first.catalog_bytes)
        self.assertTrue(verification.accepted)
        self.assertEqual(verification.failed_count, 0)
        restored = load_module_workbench_release_bundle_catalog(first.catalog_bytes)
        self.assertEqual(restored.content_address, first.content_address)
        self.assertEqual(query_module_workbench_release_bundle_catalog(first)["total"], 1)
        self.assertIn("bundle_id", module_workbench_release_bundle_catalog_csv(first))
        self.assertIn(
            "# Module Workbench Release Bundle Catalog",
            render_module_workbench_release_bundle_catalog_markdown(first),
        )
        self.assertIn("catalog_address", module_workbench_release_bundle_catalog_json(first))
        self.assertTrue(module_workbench_release_bundle_catalog_schema()["source_free"])
        self.assertTrue(module_workbench_release_bundle_catalog_capabilities()["payload_free"])
        self.assertTrue(module_workbench_release_bundle_catalog_capabilities()["deterministic"])

    def test_mixed_policy_outcomes_are_preserved_as_reviewable_state(self) -> None:
        catalog = build_module_workbench_release_bundle_catalog(
            [self.accepted_bundle, self.blocked_bundle],
            catalog_id="mixed-policy-catalog",
        )
        self.assertFalse(catalog.accepted)
        self.assertEqual(catalog.state.value, "blocked")
        verification = verify_module_workbench_release_bundle_catalog(catalog.catalog_bytes)
        self.assertTrue(verification.accepted)
        accepted = query_module_workbench_release_bundle_catalog(catalog, state="accepted")
        blocked = query_module_workbench_release_bundle_catalog(catalog, state="blocked")
        self.assertEqual(accepted["total"], 1)
        self.assertEqual(blocked["total"], 1)

    def test_duplicate_and_tampered_catalogs_fail_closed(self) -> None:
        with self.assertRaises(ValidationError):
            build_module_workbench_release_bundle_catalog(
                [self.accepted_bundle, self.accepted_bundle]
            )
        catalog = build_module_workbench_release_bundle_catalog([self.accepted_bundle])
        body = json.loads(catalog.catalog_bytes.decode("utf-8"))
        body["entries"][0]["bundle_byte_count"] += 1
        tampered = (canonical_json(body) + "\n").encode("utf-8")
        verification = verify_module_workbench_release_bundle_catalog(tampered)
        self.assertFalse(verification.accepted)
        self.assertGreater(verification.failed_count, 0)
        with self.assertRaises(ValidationError):
            load_module_workbench_release_bundle_catalog(tampered)

    def test_cli_catalog_build_verify_query_and_contract_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            accepted_archive = root / "accepted.zip"
            blocked_archive = root / "blocked.zip"
            accepted_bundle = root / "accepted-bundle.zip"
            blocked_bundle = root / "blocked-bundle.zip"
            catalog = root / "catalog.json"
            verification = root / "verification.json"
            query = root / "query.json"
            write_module_workbench_archive(self.archive, accepted_archive)
            write_module_workbench_archive(self.archive, blocked_archive)
            write_module_workbench_release_bundle(self.accepted_bundle, accepted_bundle)
            write_module_workbench_release_bundle(self.blocked_bundle, blocked_bundle)
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog",
                        "--bundle",
                        str(accepted_bundle),
                        "--bundle",
                        str(blocked_bundle),
                        "--catalog-id",
                        "cli-catalog",
                        "--destination",
                        str(catalog),
                    ]
                ),
                2,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-verify",
                        str(catalog),
                        "--output",
                        str(verification),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-query",
                        str(catalog),
                        "--state",
                        "blocked",
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
                    [
                        "module-workbench-release-bundle-catalog-schema",
                        "--output",
                        str(schema),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-catalog-capabilities",
                        "--output",
                        str(caps),
                    ]
                ),
                0,
            )
            self.assertIn("retains_payloads", schema.read_text(encoding="utf-8"))
            self.assertIn("filter_state", caps.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
