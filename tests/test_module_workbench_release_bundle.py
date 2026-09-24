"""Portable release-evidence bundle tests."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
import zipfile
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
    load_module_workbench_release_bundle,
    module_workbench_release_bundle_capabilities,
    module_workbench_release_bundle_csv,
    module_workbench_release_bundle_json,
    module_workbench_release_bundle_schema,
    query_module_workbench_release_bundle,
    render_module_workbench_release_bundle_markdown,
    verify_module_workbench_release_bundle,
    verify_module_workbench_release_bundle_value,
)
from glio_noncode.module_workbench_release_bundle_contracts import (
    MODULE_WORKBENCH_RELEASE_BUNDLE_DIFF,
)
from tests.test_module_workbench import ModuleWorkbenchFixture


class ModuleWorkbenchReleaseBundleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = ModuleWorkbenchFixture("runTest")
        self.fixture.setUp()
        report = self.fixture.report()
        self.archive = build_module_workbench_archive(report)

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def test_deterministic_round_trip_and_projections(self) -> None:
        first = build_module_workbench_release_bundle(self.archive, self.archive)
        second = build_module_workbench_release_bundle(self.archive, self.archive)
        self.assertEqual(first.bundle_bytes, second.bundle_bytes)
        verify_module_workbench_release_bundle_value(first)
        verification = verify_module_workbench_release_bundle(first.bundle_bytes)
        self.assertTrue(verification.accepted)
        self.assertEqual(verification.failed_count, 0)
        restored = load_module_workbench_release_bundle(first.bundle_bytes)
        self.assertEqual(restored.content_address, first.content_address)
        self.assertEqual(query_module_workbench_release_bundle(first)["total"], 6)
        self.assertIn("relative_path", module_workbench_release_bundle_csv(first))
        self.assertIn(
            "# Module Workbench Release Evidence",
            render_module_workbench_release_bundle_markdown(first),
        )
        self.assertIn("bundle_format", module_workbench_release_bundle_json(first))
        self.assertTrue(module_workbench_release_bundle_schema()["source_free"])
        self.assertTrue(module_workbench_release_bundle_capabilities()["deterministic"])

    def test_blocked_policy_is_preserved_as_reviewable_evidence(self) -> None:
        diff = build_module_workbench_archive_diff(self.archive, self.archive)
        policy = build_module_workbench_archive_diff_policy(minimum_score_delta=0.01)
        gate = evaluate_module_workbench_archive_diff_policy(diff, policy)
        self.assertFalse(gate.accepted)
        bundle = build_module_workbench_release_bundle(
            self.archive, self.archive, diff=diff, policy_gate=gate
        )
        self.assertFalse(bundle.accepted)
        self.assertTrue(verify_module_workbench_release_bundle(bundle.bundle_bytes).accepted)
        self.assertEqual(
            load_module_workbench_release_bundle(bundle.bundle_bytes).state.value, "blocked"
        )

    def test_nested_payload_tampering_is_rejected(self) -> None:
        bundle = build_module_workbench_release_bundle(self.archive, self.archive)
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(bundle.bundle_bytes), mode="r") as source:
            with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_STORED) as target:
                for info in source.infolist():
                    payload = source.read(info)
                    if info.filename == MODULE_WORKBENCH_RELEASE_BUNDLE_DIFF:
                        payload = payload.replace(b'"accepted":true', b'"accepted":false', 1)
                    target.writestr(info.filename, payload)
        verification = verify_module_workbench_release_bundle(output.getvalue())
        self.assertFalse(verification.accepted)
        self.assertGreater(verification.failed_count, 0)
        with self.assertRaises(ValidationError):
            load_module_workbench_release_bundle(output.getvalue())

    def test_cli_build_verify_query_and_contract_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left = root / "left.zip"
            right = root / "right.zip"
            bundle = root / "bundle.zip"
            document = root / "bundle.json"
            verification = root / "verification.json"
            query = root / "query.json"
            write_module_workbench_archive(self.archive, left)
            write_module_workbench_archive(self.archive, right)
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle",
                        "--left-archive",
                        str(left),
                        "--right-archive",
                        str(right),
                        "--destination",
                        str(bundle),
                        "--output",
                        str(document),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-verify",
                        str(bundle),
                        "--output",
                        str(verification),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-release-bundle-query",
                        str(bundle),
                        "--resource",
                        "entries",
                        "--limit",
                        "6",
                        "--output",
                        str(query),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(verification.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(json.loads(query.read_text(encoding="utf-8"))["total"], 6)
            schema = root / "schema.json"
            caps = root / "caps.json"
            self.assertEqual(
                main(["module-workbench-release-bundle-schema", "--output", str(schema)]), 0
            )
            self.assertEqual(
                main(["module-workbench-release-bundle-capabilities", "--output", str(caps)]), 0
            )
            self.assertIn("previous-workbench.zip", schema.read_text(encoding="utf-8"))
            self.assertIn("bundle_policy_gate", caps.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
