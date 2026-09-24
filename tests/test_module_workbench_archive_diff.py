"""Source-free comparison tests for portable module workbench archives."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.cli import main
from glio_noncode.module_workbench_archive import build_module_workbench_archive
from glio_noncode.module_workbench_archive import write_module_workbench_archive
from glio_noncode.module_workbench_archive_diff import (
    build_module_workbench_archive_diff,
    load_module_workbench_archive_diff,
    module_workbench_archive_diff_capabilities,
    module_workbench_archive_diff_csv,
    module_workbench_archive_diff_json,
    module_workbench_archive_diff_schema,
    query_module_workbench_archive_diff,
    render_module_workbench_archive_diff_markdown,
    verify_module_workbench_archive_diff,
    verify_module_workbench_archive_diff_value,
)
from tests.test_module_workbench import ModuleWorkbenchFixture


class ModuleWorkbenchArchiveDiffTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = ModuleWorkbenchFixture("runTest")
        self.fixture.setUp()
        self.report = self.fixture.report()
        self.archive = build_module_workbench_archive(self.report)
        self.candidate_archive = build_module_workbench_archive(
            self.report,
            archive_id="glio-noncode-module-workbench-candidate-archive",
        )

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def test_same_archive_is_deterministic_and_source_free(self) -> None:
        first = build_module_workbench_archive_diff(self.archive.archive_bytes, self.archive.archive_bytes)
        second = build_module_workbench_archive_diff(self.archive.archive_bytes, self.archive.archive_bytes)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.diff.unchanged_count, len(self.fixture.report().assessments))
        verify_module_workbench_archive_diff_value(first)
        verification = verify_module_workbench_archive_diff(first)
        self.assertTrue(verification.accepted)
        self.assertEqual(
            query_module_workbench_archive_diff(first, kind="unchanged", limit=1)["total"],
            len(first.diff.changes),
        )

    def test_distinct_archive_addresses_are_conserved(self) -> None:
        value = build_module_workbench_archive_diff(self.archive, self.candidate_archive)
        self.assertNotEqual(value.previous_archive_address, value.current_archive_address)
        self.assertEqual(value.previous_workbench_address, value.current_workbench_address)
        self.assertTrue(verify_module_workbench_archive_diff(value).accepted)

    def test_json_csv_markdown_and_schema_round_trip(self) -> None:
        value = build_module_workbench_archive_diff(self.archive, self.archive)
        payload = module_workbench_archive_diff_json(value)
        restored = load_module_workbench_archive_diff(payload.encode("utf-8"))
        self.assertEqual(restored.to_dict(), value.to_dict())
        self.assertIn("module_id", module_workbench_archive_diff_csv(value, limit=1))
        self.assertIn("# Module Workbench Archive Diff", render_module_workbench_archive_diff_markdown(value))
        self.assertTrue(module_workbench_archive_diff_schema()["source_free"])
        self.assertTrue(module_workbench_archive_diff_capabilities()["deterministic"])

    def test_tampered_json_is_rejected(self) -> None:
        value = build_module_workbench_archive_diff(self.archive, self.archive)
        payload = json.loads(module_workbench_archive_diff_json(value))
        payload["current_archive_address"] = "module-workbench-archive:tampered"
        with self.assertRaises(ValidationError):
            load_module_workbench_archive_diff((json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8"))
        verification = verify_module_workbench_archive_diff(payload)
        self.assertFalse(verification.accepted)

    def test_json_file_is_canonical_and_reopenable(self) -> None:
        value = build_module_workbench_archive_diff(self.archive, self.archive)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "archive-diff.json"
            path.write_bytes(module_workbench_archive_diff_json(value).encode("utf-8"))
            self.assertEqual(load_module_workbench_archive_diff(path).content_address, value.content_address)

    def test_cli_build_verify_query_and_contract_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left = root / "left.zip"
            right = root / "right.zip"
            diff = root / "diff.json"
            verification = root / "verification.json"
            query = root / "query.json"
            write_module_workbench_archive(self.archive, left)
            write_module_workbench_archive(self.archive, right)
            self.assertEqual(
                main(
                    [
                        "module-workbench-archive-diff",
                        "--left-archive",
                        str(left),
                        "--right-archive",
                        str(right),
                        "--output",
                        str(diff),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-archive-diff-verify",
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
                        "module-workbench-archive-diff-query",
                        str(diff),
                        "--kind",
                        "unchanged",
                        "--limit",
                        "1",
                        "--output",
                        str(query),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(verification.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(json.loads(query.read_text(encoding="utf-8"))["total"], len(self.archive.entries) + 1)
            schema = root / "schema.json"
            caps = root / "caps.json"
            self.assertEqual(main(["module-workbench-archive-diff-schema", "--output", str(schema)]), 0)
            self.assertEqual(main(["module-workbench-archive-diff-capabilities", "--output", str(caps)]), 0)
            self.assertIn("source_free", schema.read_text(encoding="utf-8"))
            self.assertIn("compare_verified_archives", caps.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
