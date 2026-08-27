"""Deep regression coverage for durable packet archive stores."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.module_workbench_execution_packet import (
    build_module_workbench_execution_packet,
)
from glio_noncode.module_workbench_execution_packet_archive import (
    build_module_workbench_execution_packet_archive,
)
from glio_noncode.module_workbench_execution_packet_archive_store import (
    append_module_workbench_execution_packet_archive_store,
    append_module_workbench_execution_packet_archive_store_batch,
    build_module_workbench_execution_packet_archive_store,
    load_module_workbench_execution_packet_archive_store,
    replay_module_workbench_execution_packet_archive_store,
    verify_module_workbench_execution_packet_archive_store,
    write_module_workbench_execution_packet_archive_store,
)
from glio_noncode.module_workbench_execution_packet_archive_store_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_GENESIS,
    ModuleWorkbenchExecutionPacketArchiveStoreOperationKind,
)
from glio_noncode.module_workbench_execution_packet_archive_store_query import (
    diff_module_workbench_execution_packet_archive_stores,
    module_workbench_execution_packet_archive_store_capabilities,
    module_workbench_execution_packet_archive_store_csv,
    module_workbench_execution_packet_archive_store_diff_csv,
    module_workbench_execution_packet_archive_store_json,
    module_workbench_execution_packet_archive_store_schema,
    query_module_workbench_execution_packet_archive_store,
    render_module_workbench_execution_packet_archive_store_markdown,
    verify_module_workbench_execution_packet_archive_store_diff,
)
from glio_noncode.module_workbench_execution_packet_archive_store_runtime import (
    module_workbench_execution_packet_archive_store_runtime_capabilities,
    module_workbench_execution_packet_archive_store_runtime_csv,
    module_workbench_execution_packet_archive_store_runtime_json,
    module_workbench_execution_packet_archive_store_runtime_schema,
    query_module_workbench_execution_packet_archive_store_runtime,
    run_module_workbench_execution_packet_archive_store_runtime,
    verify_module_workbench_execution_packet_archive_store_runtime,
)
from glio_noncode.module_workbench_execution_packet_archive_store_runtime_contracts import (
    ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStageKind,
)
from tests.test_module_workbench_execution import ModuleWorkbenchExecutionFixture


class ModuleWorkbenchExecutionPacketArchiveStoreTests(unittest.TestCase):
    """Exercise the durable archive object catalog and its lifecycle."""

    def setUp(self) -> None:
        self.fixture = ModuleWorkbenchExecutionFixture()
        self.fixture.setUp()

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def packet(self, packet_id: str = "store-test-packet"):
        return build_module_workbench_execution_packet(
            self.fixture.report(),
            packet_id=packet_id,
        )

    def archive(self, packet_id: str = "store-test-packet", archive_id: str = "store-test-archive"):
        return build_module_workbench_execution_packet_archive(
            self.packet(packet_id),
            archive_id=archive_id,
        )

    def store(self, *archives):
        selected = archives or (self.archive(),)
        return build_module_workbench_execution_packet_archive_store(
            selected,
            store_id="store-test",
        )

    def test_store_is_deterministic_and_deduplicates_equal_archive_bytes(self) -> None:
        first = self.archive(archive_id="archive-left")
        duplicate = self.archive(archive_id="archive-right")
        left = self.store(first, duplicate)
        right = self.store(duplicate, first)
        self.assertTrue(left.accepted)
        self.assertEqual(left.content_address, right.content_address)
        self.assertEqual(left.archive_count, 1)
        self.assertEqual(left.object_count, 1)
        self.assertEqual(left.operation_count, 2)
        self.assertEqual(left.duplicate_registration_count, 1)
        self.assertEqual(
            left.operations[0].kind,
            ModuleWorkbenchExecutionPacketArchiveStoreOperationKind.REGISTER,
        )
        self.assertEqual(
            left.operations[1].kind,
            ModuleWorkbenchExecutionPacketArchiveStoreOperationKind.DEDUPLICATE,
        )
        self.assertEqual(
            left.operations[0].previous_address,
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_GENESIS,
        )
        self.assertEqual(left.head_address, left.operations[-1].content_address)
        self.assertEqual(left.total_byte_count, len(first.archive_bytes))

    def test_store_keeps_distinct_packet_objects(self) -> None:
        left = self.store(self.archive(packet_id="packet-left"))
        right_archive = self.archive(packet_id="packet-right")
        result = append_module_workbench_execution_packet_archive_store(
            left,
            right_archive,
            operation_id="append-right",
            expected_head_address=left.head_address,
        )
        self.assertTrue(result.accepted)
        self.assertEqual(result.archive_count, 2)
        self.assertEqual(result.object_count, 2)
        self.assertEqual(result.operation_count, 2)
        self.assertEqual(result.duplicate_registration_count, 0)
        self.assertEqual(result.unique_packet_count, 2)
        self.assertNotEqual(result.content_address, left.content_address)

    def test_append_is_idempotent_and_enforces_optimistic_head(self) -> None:
        initial = self.store()
        candidate = self.archive(packet_id="append-packet")
        appended = append_module_workbench_execution_packet_archive_store(
            initial,
            candidate,
            operation_id="stable-operation",
            expected_head_address=initial.head_address,
        )
        retried = append_module_workbench_execution_packet_archive_store(
            appended,
            candidate,
            operation_id="stable-operation",
            expected_head_address=appended.head_address,
        )
        self.assertEqual(appended.content_address, retried.content_address)
        self.assertEqual(retried.operation_count, 2)
        with self.assertRaises(ValidationError):
            append_module_workbench_execution_packet_archive_store(
                appended,
                self.archive(packet_id="stale-packet"),
                operation_id="stale-operation",
                expected_head_address=initial.head_address,
            )
        with self.assertRaises(ValidationError):
            append_module_workbench_execution_packet_archive_store(
                appended,
                self.archive(packet_id="different-packet"),
                operation_id="stable-operation",
            )

    def test_append_batch_preserves_operation_order(self) -> None:
        initial = self.store()
        result = append_module_workbench_execution_packet_archive_store_batch(
            initial,
            (
                self.archive(packet_id="batch-one"),
                self.archive(packet_id="batch-two"),
            ),
            expected_head_address=initial.head_address,
        )
        self.assertEqual(result.archive_count, 3)
        self.assertEqual(result.operation_count, 3)
        self.assertEqual(
            tuple(item.ordinal for item in result.operations),
            (0, 1, 2),
        )
        self.assertEqual(
            tuple(item.previous_address for item in result.operations[1:]),
            tuple(item.content_address for item in result.operations[:2]),
        )

    def test_typed_verification_recomputes_all_planes(self) -> None:
        store = self.store()
        receipt = verify_module_workbench_execution_packet_archive_store(store)
        self.assertTrue(receipt.accepted)
        self.assertEqual(receipt.entry_count, 1)
        self.assertEqual(receipt.object_count, 1)
        self.assertEqual(receipt.operation_count, 1)
        self.assertEqual(receipt.passed_count, receipt.check_count)
        self.assertEqual(receipt.failed_count, 0)
        self.assertEqual(receipt.check_count, 9)
        self.assertEqual(
            tuple(item.plane.value for item in receipt.checks),
            (
                "manifest",
                "address",
                "address",
                "index",
                "object",
                "manifest",
                "public",
                "index",
                "storage",
            ),
        )

    def test_tampered_typed_store_is_rejected_before_export(self) -> None:
        store = self.store()
        with self.assertRaises(ValidationError):
            replace(store, total_byte_count=store.total_byte_count + 1)

    def test_write_load_and_replay_preserve_store_address(self) -> None:
        store = self.store(
            self.archive(archive_id="write-one", packet_id="write-one"),
            self.archive(archive_id="write-two", packet_id="write-two"),
        )
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "store"
            result = write_module_workbench_execution_packet_archive_store(store, destination)
            self.assertEqual(result, destination)
            self.assertTrue((destination / "manifest.json").is_file())
            objects = tuple((destination / "objects").iterdir())
            self.assertEqual(len(objects), 2)
            loaded = load_module_workbench_execution_packet_archive_store(destination)
            self.assertEqual(loaded.content_address, store.content_address)
            self.assertEqual(
                verify_module_workbench_execution_packet_archive_store(destination).accepted,
                True,
            )
            replay = replay_module_workbench_execution_packet_archive_store(loaded)
            self.assertTrue(replay.accepted)
            self.assertEqual(replay.store_address, store.content_address)
            self.assertEqual(replay.replayed_store_address, store.content_address)

    def test_existing_destination_requires_explicit_overwrite(self) -> None:
        store = self.store()
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "store"
            write_module_workbench_execution_packet_archive_store(store, destination)
            with self.assertRaises(ValidationError):
                write_module_workbench_execution_packet_archive_store(store, destination)
            write_module_workbench_execution_packet_archive_store(
                store,
                destination,
                allow_existing=True,
            )
            self.assertTrue(
                verify_module_workbench_execution_packet_archive_store(destination).accepted
            )

    def test_manifest_tamper_is_blocked_without_loading_objects(self) -> None:
        store = self.store()
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "store"
            write_module_workbench_execution_packet_archive_store(store, destination)
            manifest = destination / "manifest.json"
            mapping = json.loads(manifest.read_text(encoding="utf-8"))
            mapping["store_id"] = "tampered-store"
            manifest.write_text(json.dumps(mapping), encoding="utf-8")
            receipt = verify_module_workbench_execution_packet_archive_store(destination)
            self.assertFalse(receipt.accepted)
            self.assertGreater(receipt.failed_count, 0)
            with self.assertRaises(ValidationError):
                load_module_workbench_execution_packet_archive_store(destination)

    def test_object_tamper_extra_object_and_traversal_are_blocked(self) -> None:
        store = self.store()
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "store"
            write_module_workbench_execution_packet_archive_store(store, destination)
            object_path = next((destination / "objects").iterdir())
            original = object_path.read_bytes()
            object_path.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
            self.assertFalse(
                verify_module_workbench_execution_packet_archive_store(destination).accepted
            )
            object_path.write_bytes(original)
            (destination / "objects" / "unlisted.zip").write_bytes(original)
            self.assertFalse(
                verify_module_workbench_execution_packet_archive_store(destination).accepted
            )
            (destination / "objects" / "unlisted.zip").unlink()
            mapping = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
            mapping["entries"][0]["object_key"] = "../outside.zip"
            (destination / "manifest.json").write_text(
                json.dumps(mapping, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            self.assertFalse(
                verify_module_workbench_execution_packet_archive_store(destination).accepted
            )

    def test_queries_exports_and_store_diff_are_deterministic(self) -> None:
        left = self.store()
        right = append_module_workbench_execution_packet_archive_store(
            left,
            self.archive(packet_id="diff-packet"),
            operation_id="diff-operation",
        )
        entries = query_module_workbench_execution_packet_archive_store(
            right,
            resource="entries",
            accepted=True,
        )
        operations = query_module_workbench_execution_packet_archive_store(
            right,
            resource="operations",
            kind="register",
        )
        summary = query_module_workbench_execution_packet_archive_store(
            right,
            resource="summary",
        )
        self.assertEqual(entries["total"], 2)
        self.assertEqual(operations["total"], 2)
        self.assertEqual(summary["total"], 1)
        self.assertEqual(
            query_module_workbench_execution_packet_archive_store(
                right,
                resource="operations",
                text="deduplicated",
            )["total"],
            0,
        )
        self.assertIn("store_id", module_workbench_execution_packet_archive_store_json(right))
        self.assertIn("object_key", module_workbench_execution_packet_archive_store_csv(right))
        self.assertIn(
            "Store", render_module_workbench_execution_packet_archive_store_markdown(right)
        )
        report = diff_module_workbench_execution_packet_archive_stores(left, right)
        self.assertTrue(report["accepted"])
        self.assertTrue(report["head_changed"])
        self.assertEqual(report["added_archive_count"], 1)
        self.assertEqual(report["entry_change_count"], 2)
        verify_module_workbench_execution_packet_archive_store_diff(report)
        self.assertIn(
            "archive_address", module_workbench_execution_packet_archive_store_diff_csv(report)
        )

    def test_query_limits_and_diff_tamper_are_rejected(self) -> None:
        store = self.store()
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store(store, limit=513)
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store(store, resource="unknown")
        report = diff_module_workbench_execution_packet_archive_stores(store, store)
        report["content_address"] = "tampered"
        with self.assertRaises(ValidationError):
            verify_module_workbench_execution_packet_archive_store_diff(report)

    def test_store_schemas_and_capabilities_conserve_operations(self) -> None:
        schema = module_workbench_execution_packet_archive_store_schema()
        capabilities = module_workbench_execution_packet_archive_store_capabilities()
        self.assertEqual(capabilities["operation_count"], len(capabilities["operations"]))
        self.assertEqual(schema["resources"], ["summary", "entries", "operations"])
        self.assertTrue(schema["path_free"])
        self.assertTrue(schema["timestamp_free"])
        self.assertTrue(schema["identity_free"])
        self.assertTrue(capabilities["atomic_writes"])
        self.assertTrue(capabilities["deduplicated"])
        self.assertTrue(capabilities["replayable"])

    def test_store_runtime_completes_all_stages(self) -> None:
        store = self.store(
            self.archive(packet_id="runtime-one"),
            self.archive(packet_id="runtime-two"),
        )
        runtime = run_module_workbench_execution_packet_archive_store_runtime(store)
        self.assertTrue(runtime.accepted)
        self.assertEqual(runtime.stage_count, 8)
        self.assertEqual(runtime.completed_count, 8)
        self.assertEqual(runtime.blocked_count, 0)
        self.assertEqual(
            tuple(item.kind for item in runtime.stages),
            tuple(ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStageKind),
        )
        self.assertIs(
            verify_module_workbench_execution_packet_archive_store_runtime(runtime),
            runtime,
        )
        self.assertEqual(
            query_module_workbench_execution_packet_archive_store_runtime(runtime)["total"],
            8,
        )
        self.assertEqual(
            query_module_workbench_execution_packet_archive_store_runtime(
                runtime,
                resource="summary",
            )["total"],
            1,
        )
        self.assertIn(
            "stage_count", module_workbench_execution_packet_archive_store_runtime_json(runtime)
        )
        self.assertIn(
            "artifact_address", module_workbench_execution_packet_archive_store_runtime_csv(runtime)
        )

    def test_store_runtime_can_persist_and_verify_the_directory(self) -> None:
        store = self.store()
        with tempfile.TemporaryDirectory() as directory:
            runtime = run_module_workbench_execution_packet_archive_store_runtime(
                store,
                destination=Path(directory) / "store",
            )
            self.assertTrue(runtime.accepted)
            self.assertTrue(
                verify_module_workbench_execution_packet_archive_store(
                    Path(directory) / "store"
                ).accepted
            )

    def test_runtime_schemas_and_capabilities_conserve_operations(self) -> None:
        schema = module_workbench_execution_packet_archive_store_runtime_schema()
        capabilities = module_workbench_execution_packet_archive_store_runtime_capabilities()
        self.assertEqual(capabilities["operation_count"], len(capabilities["operations"]))
        self.assertEqual(
            schema["stage_order"],
            [item.value for item in ModuleWorkbenchExecutionPacketArchiveStoreRuntimeStageKind],
        )
        self.assertTrue(capabilities["ordered"])
        self.assertTrue(capabilities["atomic_writes"])

    def test_cli_store_schema_and_runtime_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packet = root / "packet"
            store_path = root / "store"
            output = root / "output.json"
            archive = root / "archive.zip"
            from glio_noncode.module_workbench_execution_packet import (
                write_module_workbench_execution_packet,
            )

            write_module_workbench_execution_packet(self.packet(), packet)
            self.assertEqual(
                main(
                    [
                        "module-workbench-execution-packet-archive",
                        str(packet),
                        "--destination",
                        str(archive),
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            for command in (
                "module-workbench-execution-packet-archive-store-schema",
                "module-workbench-execution-packet-archive-store-capabilities",
                "module-workbench-execution-packet-archive-store-runtime-schema",
                "module-workbench-execution-packet-archive-store-runtime-capabilities",
            ):
                self.assertEqual(main([command, "--output", str(output)]), 0)
                self.assertTrue(output.read_text(encoding="utf-8").strip())
            self.assertEqual(
                main(
                    [
                        "module-workbench-execution-packet-archive-store",
                        str(archive),
                        "--destination",
                        str(store_path),
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            self.assertIn('"archive_count":1', output.read_text(encoding="utf-8"))
            self.assertEqual(
                main(
                    [
                        "module-workbench-execution-packet-archive-store-verify",
                        str(store_path),
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            self.assertIn('"accepted": true', output.read_text(encoding="utf-8"))
            self.assertEqual(
                main(
                    [
                        "module-workbench-execution-packet-archive-store-runtime",
                        str(archive),
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            self.assertIn('"stage_count":8', output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
