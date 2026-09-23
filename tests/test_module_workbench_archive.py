"""Portable module workbench archive contract and tamper tests."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.cli import main
from glio_noncode.module_workbench_archive import (
    build_module_workbench_archive,
    load_module_workbench_archive,
    module_workbench_archive_bytes,
    module_workbench_archive_capabilities,
    module_workbench_archive_csv,
    module_workbench_archive_schema,
    query_module_workbench_archive,
    render_module_workbench_archive_markdown,
    verify_module_workbench_archive,
    verify_module_workbench_archive_value,
    write_module_workbench_archive,
)
from glio_noncode.module_workbench_archive_contracts import (
    MODULE_WORKBENCH_ARCHIVE_MANIFEST,
    MODULE_WORKBENCH_ARCHIVE_REPORT,
)
from tests.test_module_workbench import ModuleWorkbenchFixture


class ModuleWorkbenchArchiveTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = ModuleWorkbenchFixture("runTest")
        self.fixture.setUp()
        self.report = self.fixture.report()

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def test_build_is_deterministic_and_round_trips_without_source(self) -> None:
        first = build_module_workbench_archive(self.report)
        second = build_module_workbench_archive(self.report)
        self.assertEqual(module_workbench_archive_bytes(first), module_workbench_archive_bytes(second))
        self.assertEqual(first.archive_address, second.archive_address)
        self.assertEqual(first.content_address, second.content_address)
        verify_module_workbench_archive_value(first)
        verification = verify_module_workbench_archive(first.archive_bytes)
        self.assertTrue(verification.accepted)
        restored = load_module_workbench_archive(first.archive_bytes)
        self.assertEqual(restored.to_dict(), self.report.to_dict())

    def test_archive_queries_and_exports_are_bounded(self) -> None:
        archive = build_module_workbench_archive(self.report)
        entries = query_module_workbench_archive(archive, resource="entries", limit=10)
        self.assertEqual(entries["total"], 2)
        modules = query_module_workbench_archive(archive, resource="modules", limit=10)
        self.assertEqual(modules["total"], len(self.report.assessments))
        self.assertEqual(modules["archive_address"], archive.archive_address)
        self.assertIn("entry_id", module_workbench_archive_csv(archive))
        filtered_csv = module_workbench_archive_csv(
            archive,
            "modules",
            risk="high",
            limit=1,
        )
        self.assertEqual(filtered_csv.count("\n"), 2)
        self.assertIn("# Module Workbench Archive", render_module_workbench_archive_markdown(archive))
        self.assertTrue(module_workbench_archive_schema()["path_free"])
        self.assertTrue(module_workbench_archive_capabilities()["source_free_reload"])

    def test_write_is_atomic_and_existing_destination_is_guarded(self) -> None:
        archive = build_module_workbench_archive(self.report)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "workbench.zip"
            written = write_module_workbench_archive(archive, destination)
            self.assertEqual(written.archive_address, archive.archive_address)
            self.assertEqual(destination.read_bytes(), archive.archive_bytes)
            with self.assertRaises(ValidationError):
                write_module_workbench_archive(archive, destination)
            write_module_workbench_archive(archive, destination, allow_existing=True)

    def test_report_payload_tampering_is_rejected(self) -> None:
        archive = build_module_workbench_archive(self.report)
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(archive.archive_bytes), mode="r") as source:
            with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_STORED) as target:
                for info in source.infolist():
                    payload = source.read(info)
                    if info.filename == MODULE_WORKBENCH_ARCHIVE_REPORT:
                        payload = payload.replace(
                            b'"content_address":"',
                            b'"content_address":"tampered-',
                            1,
                        )
                    target.writestr(info.filename, payload)
        verification = verify_module_workbench_archive(output.getvalue())
        self.assertFalse(verification.accepted)
        self.assertTrue(any(not check.passed for check in verification.checks))
        with self.assertRaises(ValidationError):
            load_module_workbench_archive(output.getvalue())

    def test_manifest_and_report_members_are_required(self) -> None:
        output = io.BytesIO()
        with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_STORED) as target:
            target.writestr(MODULE_WORKBENCH_ARCHIVE_MANIFEST, b"{}\n")
        verification = verify_module_workbench_archive(output.getvalue())
        self.assertFalse(verification.accepted)
        self.assertTrue(any(check.check_id == "declared-members" and not check.passed for check in verification.checks))

    def test_cli_build_verify_and_source_free_query(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive_path = root / "workbench.zip"
            summary_path = root / "archive.json"
            restored_path = root / "restored.json"
            self.assertEqual(
                main(
                    [
                        "module-workbench-archive",
                        "--source-root",
                        str(self.fixture.package),
                        "--test-root",
                        str(self.fixture.tests),
                        "--docs-root",
                        str(self.fixture.docs),
                        "--destination",
                        str(archive_path),
                        "--format",
                        "json",
                        "--output",
                        str(summary_path),
                    ]
                ),
                0,
            )
            self.assertEqual(main(["module-workbench-archive-verify", str(archive_path)]), 0)
            self.assertEqual(
                main(
                    [
                        "module-workbench-archive-query",
                        str(archive_path),
                        "--resource",
                        "modules",
                        "--limit",
                        "1",
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-archive-load",
                        str(archive_path),
                        "--output",
                        str(restored_path),
                    ]
                ),
                0,
            )
            self.assertEqual(json.loads(restored_path.read_text(encoding="utf-8"))["module_count"], 3)


if __name__ == "__main__":
    unittest.main()
