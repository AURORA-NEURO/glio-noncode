"""Deep tests for non-mutating archive store recovery diagnostics."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main
from glio_noncode.module_workbench_execution_packet import build_module_workbench_execution_packet
from glio_noncode.module_workbench_execution_packet_archive import (
    build_module_workbench_execution_packet_archive,
    write_module_workbench_execution_packet_archive,
)
from glio_noncode.module_workbench_execution_packet_archive_store import (
    build_module_workbench_execution_packet_archive_store,
    write_module_workbench_execution_packet_archive_store,
)
from glio_noncode.module_workbench_execution_packet_archive_store_recovery import (
    ModuleWorkbenchExecutionPacketArchiveStoreRecoveryPlane,
    inspect_module_workbench_execution_packet_archive_store,
    module_workbench_execution_packet_archive_store_recovery_capabilities,
    module_workbench_execution_packet_archive_store_recovery_csv,
    module_workbench_execution_packet_archive_store_recovery_json,
    module_workbench_execution_packet_archive_store_recovery_schema,
    query_module_workbench_execution_packet_archive_store_recovery,
    render_module_workbench_execution_packet_archive_store_recovery_markdown,
    verify_module_workbench_execution_packet_archive_store_recovery,
)
from tests.test_module_workbench_execution import ModuleWorkbenchExecutionFixture


class ModuleWorkbenchExecutionPacketArchiveStoreRecoveryTests(unittest.TestCase):
    """Exercise healthy-store inspection and every material storage failure."""

    def setUp(self) -> None:
        self.fixture = ModuleWorkbenchExecutionFixture()
        self.fixture.setUp()

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def packet(self, packet_id: str = "recovery-packet"):
        return build_module_workbench_execution_packet(self.fixture.report(), packet_id=packet_id)

    def archive(self):
        return build_module_workbench_execution_packet_archive(
            self.packet(), archive_id="recovery-archive"
        )

    def write_store(self, root: Path) -> Path:
        archive_path = root / "archive.zip"
        store_path = root / "store"
        write_module_workbench_execution_packet_archive(self.archive(), archive_path)
        store = build_module_workbench_execution_packet_archive_store(
            (archive_path,), store_id="recovery-store"
        )
        write_module_workbench_execution_packet_archive_store(store, store_path)
        return store_path

    def test_healthy_store_report_is_addressed_and_conserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store_path = self.write_store(Path(directory))
            report = inspect_module_workbench_execution_packet_archive_store(store_path)
            self.assertTrue(report.accepted)
            self.assertGreaterEqual(report.finding_count, 7)
            self.assertEqual(report.blocked_count, 0)
            self.assertEqual(report.passed_count, report.finding_count)
            verify_module_workbench_execution_packet_archive_store_recovery(report)
            self.assertTrue(
                report.manifest_address.startswith(
                    "module-workbench-execution-packet-archive-store:"
                )
            )

    def test_healthy_store_has_each_recovery_plane(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = inspect_module_workbench_execution_packet_archive_store(
                self.write_store(Path(directory))
            )
            planes = {item.plane for item in report.findings}
            self.assertIn(ModuleWorkbenchExecutionPacketArchiveStoreRecoveryPlane.DIRECTORY, planes)
            self.assertIn(ModuleWorkbenchExecutionPacketArchiveStoreRecoveryPlane.MANIFEST, planes)
            self.assertIn(ModuleWorkbenchExecutionPacketArchiveStoreRecoveryPlane.OBJECTS, planes)
            self.assertIn(ModuleWorkbenchExecutionPacketArchiveStoreRecoveryPlane.ADDRESS, planes)
            self.assertIn(ModuleWorkbenchExecutionPacketArchiveStoreRecoveryPlane.PUBLIC, planes)

    def test_missing_object_is_reported_without_loader_exception(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store_path = self.write_store(Path(directory))
            object_path = next((store_path / "objects").iterdir())
            object_path.unlink()
            report = inspect_module_workbench_execution_packet_archive_store(store_path)
            self.assertFalse(report.accepted)
            self.assertGreater(report.blocked_count, 0)
            self.assertTrue(any(item.code == "object-set-conserved" for item in report.findings))

    def test_extra_object_is_reported_without_loader_exception(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store_path = self.write_store(Path(directory))
            (
                store_path
                / "objects"
                / "module-workbench-execution-packet-archive-store-object-extra.zip"
            ).write_bytes(b"extra")
            report = inspect_module_workbench_execution_packet_archive_store(store_path)
            self.assertFalse(report.accepted)
            self.assertTrue(any(item.code == "object-set-conserved" for item in report.findings))

    def test_tampered_object_bytes_are_addressed_and_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store_path = self.write_store(Path(directory))
            object_path = next((store_path / "objects").iterdir())
            object_path.write_bytes(object_path.read_bytes() + b"tamper")
            report = inspect_module_workbench_execution_packet_archive_store(store_path)
            self.assertFalse(report.accepted)
            self.assertTrue(any(item.code == "object-address-matches" for item in report.findings))

    def test_noncanonical_manifest_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store_path = self.write_store(Path(directory))
            manifest_path = store_path / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            report = inspect_module_workbench_execution_packet_archive_store(store_path)
            self.assertFalse(report.accepted)
            self.assertTrue(any(item.code == "manifest-canonical" for item in report.findings))

    def test_forbidden_manifest_key_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store_path = self.write_store(Path(directory))
            manifest_path = store_path / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["agent"] = "forbidden"
            manifest_path.write_text(
                json.dumps(manifest, sort_keys=True, separators=(",", ":")), encoding="utf-8"
            )
            report = inspect_module_workbench_execution_packet_archive_store(store_path)
            self.assertFalse(report.accepted)
            self.assertTrue(
                any(item.code == "manifest-public-boundary" for item in report.findings)
            )

    def test_unsafe_object_key_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store_path = self.write_store(Path(directory))
            manifest_path = store_path / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["entries"][0]["object_key"] = "../escape.zip"
            manifest_path.write_text(
                json.dumps(manifest, sort_keys=True, separators=(",", ":")), encoding="utf-8"
            )
            report = inspect_module_workbench_execution_packet_archive_store(store_path)
            self.assertFalse(report.accepted)
            self.assertTrue(any(item.code == "object-key-safe" for item in report.findings))

    def test_missing_and_symlinked_directories_are_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = inspect_module_workbench_execution_packet_archive_store(
                Path(directory) / "missing"
            )
            self.assertFalse(missing.accepted)
            self.assertEqual(missing.store_id, "unknown-store")
            self.assertEqual(missing.blocked_count, 1)

    def test_recovery_query_filters_planes_and_pages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = inspect_module_workbench_execution_packet_archive_store(
                self.write_store(Path(directory))
            )
            result = query_module_workbench_execution_packet_archive_store_recovery(
                report,
                plane="objects",
                accepted=True,
                offset=0,
                limit=2,
            )
            self.assertTrue(result["accepted"])
            self.assertLessEqual(len(result["items"]), 2)
            self.assertGreaterEqual(result["total"], len(result["items"]))
            self.assertTrue(all(item["plane"] == "objects" for item in result["items"]))

    def test_blocked_recovery_query_retains_failure_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store_path = self.write_store(Path(directory))
            (store_path / "objects").rename(store_path / "objects-old")
            report = inspect_module_workbench_execution_packet_archive_store(store_path)
            result = query_module_workbench_execution_packet_archive_store_recovery(report)
            self.assertFalse(report.accepted)
            self.assertFalse(result["accepted"])
            self.assertGreater(result["total"], 0)

    def test_exports_are_deterministic_and_path_free(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = inspect_module_workbench_execution_packet_archive_store(
                self.write_store(Path(directory))
            )
            first = module_workbench_execution_packet_archive_store_recovery_json(report)
            second = module_workbench_execution_packet_archive_store_recovery_json(report)
            self.assertEqual(first, second)
            self.assertIn(
                "recovery_address",
                query_module_workbench_execution_packet_archive_store_recovery(report),
            )
            self.assertIn(
                "code", module_workbench_execution_packet_archive_store_recovery_csv(report)
            )
            self.assertIn(
                "# Archive Store Recovery Report",
                render_module_workbench_execution_packet_archive_store_recovery_markdown(report),
            )
            for text in (
                first,
                module_workbench_execution_packet_archive_store_recovery_csv(report),
            ):
                self.assertNotIn(str(Path(directory)), text)
                self.assertNotIn('"agent"', text)
                self.assertNotIn('"language"', text)

    def test_schema_capabilities_and_address_verification_are_explicit(self) -> None:
        schema = module_workbench_execution_packet_archive_store_recovery_schema()
        capabilities = module_workbench_execution_packet_archive_store_recovery_capabilities()
        self.assertEqual(
            schema["version"], "module-workbench-execution-packet-archive-store-recovery-v1"
        )
        self.assertEqual(capabilities["operation_count"], len(capabilities["operations"]))
        self.assertTrue(schema["mutates_storage"] is False)
        self.assertTrue(capabilities["fail_closed"])
        with tempfile.TemporaryDirectory() as directory:
            report = inspect_module_workbench_execution_packet_archive_store(
                self.write_store(Path(directory))
            )
            self.assertIs(
                verify_module_workbench_execution_packet_archive_store_recovery(report), report
            )

    def test_cli_recovery_and_recovery_query(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store_path = self.write_store(root)
            output = root / "recovery.json"
            self.assertEqual(
                main(
                    [
                        "module-workbench-execution-packet-archive-store-recovery",
                        str(store_path),
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            self.assertIn('"accepted":true', output.read_text(encoding="utf-8"))
            self.assertEqual(
                main(
                    [
                        "module-workbench-execution-packet-archive-store-recovery-query",
                        str(store_path),
                        "--plane",
                        "objects",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            self.assertIn('"accepted": true', output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
