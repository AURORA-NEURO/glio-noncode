"""Deep regression coverage for deterministic packet archive transport."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.module_workbench_execution_packet import (
    build_module_workbench_execution_packet,
    load_module_workbench_execution_packet,
    verify_module_workbench_execution_packet,
    write_module_workbench_execution_packet,
)
from glio_noncode.module_workbench_execution_packet_archive import (
    build_module_workbench_execution_packet_archive,
    load_module_workbench_execution_packet_archive,
    module_workbench_execution_packet_archive_bytes,
    module_workbench_execution_packet_archive_capabilities,
    module_workbench_execution_packet_archive_csv,
    module_workbench_execution_packet_archive_json,
    module_workbench_execution_packet_archive_schema,
    query_module_workbench_execution_packet_archive,
    render_module_workbench_execution_packet_archive_markdown,
    unpack_module_workbench_execution_packet_archive,
    verify_module_workbench_execution_packet_archive,
    verify_module_workbench_execution_packet_archive_value,
    write_module_workbench_execution_packet_archive,
)
from glio_noncode.module_workbench_execution_packet_archive_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DEFAULT_CHUNK_SIZE,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_FORMAT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MANIFEST,
    ModuleWorkbenchExecutionPacketArchiveEntryKind,
    ModuleWorkbenchExecutionPacketArchiveState,
    ModuleWorkbenchExecutionPacketArchiveTransferState,
)
from glio_noncode.module_workbench_execution_packet_archive_diff import (
    diff_module_workbench_execution_packet_archives,
    module_workbench_execution_packet_archive_diff_capabilities,
    module_workbench_execution_packet_archive_diff_csv,
    module_workbench_execution_packet_archive_diff_json,
    module_workbench_execution_packet_archive_diff_schema,
    query_module_workbench_execution_packet_archive_diff,
    render_module_workbench_execution_packet_archive_diff_markdown,
    verify_module_workbench_execution_packet_archive_diff,
)
from glio_noncode.module_workbench_execution_packet_archive_index import (
    build_module_workbench_execution_packet_archive_index,
    module_workbench_execution_packet_archive_index_capabilities,
    module_workbench_execution_packet_archive_index_csv,
    module_workbench_execution_packet_archive_index_json,
    module_workbench_execution_packet_archive_index_schema,
    query_module_workbench_execution_packet_archive_index,
    render_module_workbench_execution_packet_archive_index_markdown,
    resolve_module_workbench_execution_packet_archive_index_entry,
    verify_module_workbench_execution_packet_archive_index,
)
from glio_noncode.module_workbench_execution_packet_archive_query import (
    assemble_module_workbench_execution_packet_archive_chunks,
    build_module_workbench_execution_packet_archive_transfer,
    chunk_module_workbench_execution_packet_archive,
    module_workbench_execution_packet_archive_chunks_csv,
    module_workbench_execution_packet_archive_transfer_capabilities,
    module_workbench_execution_packet_archive_transfer_json,
    module_workbench_execution_packet_archive_transfer_schema,
    query_module_workbench_execution_packet_archive_chunks,
    resume_module_workbench_execution_packet_archive_transfer,
    verify_module_workbench_execution_packet_archive_chunk,
    verify_module_workbench_execution_packet_archive_transfer,
)
from glio_noncode.module_workbench_execution_packet_archive_runtime import (
    module_workbench_execution_packet_archive_runtime_capabilities,
    module_workbench_execution_packet_archive_runtime_csv,
    module_workbench_execution_packet_archive_runtime_json,
    module_workbench_execution_packet_archive_runtime_schema,
    query_module_workbench_execution_packet_archive_runtime,
    run_module_workbench_execution_packet_archive_runtime,
    verify_module_workbench_execution_packet_archive_runtime,
)
from glio_noncode.module_workbench_execution_packet_archive_runtime_contracts import (
    ModuleWorkbenchExecutionPacketArchiveRuntimeStageKind,
)
from tests.test_module_workbench_execution import ModuleWorkbenchExecutionFixture


class ModuleWorkbenchExecutionPacketArchiveTests(unittest.TestCase):
    """Exercise archive creation, verification, transport, and extraction."""

    def setUp(self) -> None:
        self.fixture = ModuleWorkbenchExecutionFixture()
        self.fixture.setUp()

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def packet(self):
        return build_module_workbench_execution_packet(self.fixture.report())

    def archive(self):
        return build_module_workbench_execution_packet_archive(self.packet())

    def write_archive(self, archive):
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / "execution-packet.zip"
        write_module_workbench_execution_packet_archive(archive, path)
        self.addCleanup(directory.cleanup)
        return path

    def test_archive_is_deterministic_and_exactly_addressed(self) -> None:
        first = self.archive()
        second = self.archive()
        self.assertTrue(first.accepted)
        self.assertEqual(first.state, ModuleWorkbenchExecutionPacketArchiveState.ACCEPTED)
        self.assertEqual(first.archive_format, MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_FORMAT)
        self.assertEqual(first.archive_bytes, second.archive_bytes)
        self.assertEqual(first.archive_address, second.archive_address)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.entry_count, 14)
        self.assertEqual(first.artifact_count, 13)
        self.assertEqual(
            first.entries[0].kind,
            ModuleWorkbenchExecutionPacketArchiveEntryKind.MANIFEST,
        )
        self.assertEqual(
            first.entries[0].relative_path,
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MANIFEST,
        )
        self.assertEqual(
            tuple(item.ordinal for item in first.entries),
            tuple(range(first.entry_count)),
        )
        self.assertEqual(
            sum(item.byte_count for item in first.entries),
            first.payload_byte_count,
        )
        verify_module_workbench_execution_packet_archive_value(first)
        self.assertEqual(
            module_workbench_execution_packet_archive_bytes(first),
            first.archive_bytes,
        )

    def test_archive_members_have_fixed_zip_metadata(self) -> None:
        archive = self.archive()
        with zipfile.ZipFile(io.BytesIO(archive.archive_bytes), mode="r") as handle:
            infos = handle.infolist()
            self.assertEqual(len(infos), archive.entry_count)
            self.assertEqual(
                tuple(info.filename for info in infos),
                tuple(item.relative_path for item in archive.entries),
            )
            self.assertTrue(all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in infos))
            self.assertTrue(all(info.compress_type == zipfile.ZIP_STORED for info in infos))
            self.assertTrue(all(info.create_system == 0 for info in infos))
            self.assertTrue(all(info.extra == b"" for info in infos))
            self.assertTrue(all(info.comment == b"" for info in infos))

    def test_verify_and_load_work_without_source_tree(self) -> None:
        archive = self.archive()
        receipt = verify_module_workbench_execution_packet_archive(archive.archive_bytes)
        self.assertTrue(receipt.accepted)
        self.assertEqual(receipt.archive_address, archive.archive_address)
        self.assertEqual(receipt.entry_count, archive.entry_count)
        self.assertEqual(receipt.artifact_count, archive.artifact_count)
        self.assertEqual(receipt.present_count, archive.entry_count)
        self.assertEqual(receipt.missing_count, 0)
        self.assertEqual(receipt.failed_count, 0)
        loaded = load_module_workbench_execution_packet_archive(archive.archive_bytes)
        self.assertEqual(loaded.content_address, archive.packet_address)
        self.assertEqual(loaded.artifact_count, archive.artifact_count)

    def test_write_verify_load_and_unpack_round_trip(self) -> None:
        archive = self.archive()
        archive_path = self.write_archive(archive)
        receipt = verify_module_workbench_execution_packet_archive(archive_path)
        self.assertTrue(receipt.accepted)
        loaded = load_module_workbench_execution_packet_archive(archive_path)
        self.assertEqual(loaded.content_address, archive.packet_address)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "packet"
            unpacked = unpack_module_workbench_execution_packet_archive(archive_path, destination)
            self.assertEqual(unpacked, destination)
            self.assertTrue((destination / "manifest.json").is_file())
            self.assertTrue(verify_module_workbench_execution_packet(destination).accepted)
            unpacked_packet = load_module_workbench_execution_packet(destination)
            self.assertEqual(unpacked_packet.content_address, archive.packet_address)

    def test_archive_descriptor_and_exports_are_stable(self) -> None:
        archive = self.archive()
        descriptor = module_workbench_execution_packet_archive_json(archive)
        csv_text = module_workbench_execution_packet_archive_csv(archive)
        markdown = render_module_workbench_execution_packet_archive_markdown(archive)
        parsed = json.loads(descriptor)
        self.assertEqual(
            descriptor,
            json.dumps(parsed, sort_keys=True, separators=(",", ":")) + "\n",
        )
        self.assertNotIn("archive_bytes", descriptor)
        self.assertIn("entry_id,relative_path,kind", csv_text)
        self.assertEqual(csv_text.count("\n"), archive.entry_count + 1)
        self.assertIn("# Module Workbench Execution Packet Archive", markdown)
        self.assertIn("Payload bytes", markdown)

    def test_archive_query_summary_entries_and_filters(self) -> None:
        archive = self.archive()
        summary = query_module_workbench_execution_packet_archive(archive, resource="summary")
        entries = query_module_workbench_execution_packet_archive(archive, resource="entries")
        artifacts = query_module_workbench_execution_packet_archive(
            archive,
            resource="entries",
            kind="artifact",
        )
        manifest = query_module_workbench_execution_packet_archive(
            archive,
            resource="entries",
            entry_id="manifest",
        )
        text = query_module_workbench_execution_packet_archive(
            archive,
            resource="entries",
            text="audit.json",
        )
        self.assertEqual(summary["total"], 1)
        self.assertEqual(entries["total"], archive.entry_count)
        self.assertEqual(artifacts["total"], archive.artifact_count)
        self.assertEqual(manifest["total"], 1)
        self.assertEqual(text["total"], 1)
        self.assertEqual(text["items"][0]["relative_path"], "audit.json")
        self.assertEqual(
            query_module_workbench_execution_packet_archive(
                archive,
                resource="entries",
                offset=2,
                limit=3,
            )["items"][0]["ordinal"],
            2,
        )

    def test_archive_verifier_accepts_bytes_and_rejects_corrupt_zip(self) -> None:
        archive = self.archive()
        self.assertTrue(
            verify_module_workbench_execution_packet_archive(archive.archive_bytes).accepted
        )
        corrupted = archive.archive_bytes[:20] + b"corrupt" + archive.archive_bytes[27:]
        receipt = verify_module_workbench_execution_packet_archive(corrupted)
        self.assertFalse(receipt.accepted)
        self.assertGreaterEqual(receipt.failed_count, 1)
        with self.assertRaises(ValidationError):
            load_module_workbench_execution_packet_archive(corrupted)

    def test_member_byte_tamper_is_blocked(self) -> None:
        archive = self.archive()
        with zipfile.ZipFile(io.BytesIO(archive.archive_bytes), mode="r") as source:
            rebuilt = io.BytesIO()
            with zipfile.ZipFile(rebuilt, mode="w", compression=zipfile.ZIP_STORED) as target:
                for info in source.infolist():
                    payload = source.read(info)
                    if info.filename == "audit.json":
                        payload += b"\n"
                    target.writestr(info, payload)
        receipt = verify_module_workbench_execution_packet_archive(rebuilt.getvalue())
        self.assertFalse(receipt.accepted)
        self.assertTrue(
            any(check.check_id == "artifact-bytes" and not check.passed for check in receipt.checks)
        )
        self.assertTrue(
            any(
                check.check_id == "packet-hydration" and not check.passed
                for check in receipt.checks
            )
        )

    def test_noncanonical_manifest_is_blocked(self) -> None:
        archive = self.archive()
        with zipfile.ZipFile(io.BytesIO(archive.archive_bytes), mode="r") as source:
            rebuilt = io.BytesIO()
            with zipfile.ZipFile(rebuilt, mode="w", compression=zipfile.ZIP_STORED) as target:
                for info in source.infolist():
                    payload = source.read(info)
                    if info.filename == MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_MANIFEST:
                        payload = payload.replace(b"{", b"{ ", 1)
                    target.writestr(info, payload)
        receipt = verify_module_workbench_execution_packet_archive(rebuilt.getvalue())
        self.assertFalse(receipt.accepted)
        self.assertTrue(
            any(
                check.check_id == "manifest-canonical" and not check.passed
                for check in receipt.checks
            )
        )

    def test_traversal_and_duplicate_members_are_blocked(self) -> None:
        traversal = io.BytesIO()
        with zipfile.ZipFile(traversal, mode="w", compression=zipfile.ZIP_STORED) as handle:
            handle.writestr("../escape.json", b"{}")
        receipt = verify_module_workbench_execution_packet_archive(traversal.getvalue())
        self.assertFalse(receipt.accepted)
        self.assertTrue(
            any(check.check_id == "safe-paths" and not check.passed for check in receipt.checks)
        )
        duplicate = io.BytesIO()
        with zipfile.ZipFile(duplicate, mode="w", compression=zipfile.ZIP_STORED) as handle:
            handle.writestr("manifest.json", b"{}")
            handle.writestr("manifest.json", b"{}")
        receipt = verify_module_workbench_execution_packet_archive(duplicate.getvalue())
        self.assertFalse(receipt.accepted)
        self.assertTrue(
            any(check.check_id == "unique-members" and not check.passed for check in receipt.checks)
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValidationError):
                unpack_module_workbench_execution_packet_archive(
                    traversal.getvalue(),
                    Path(directory) / "packet",
                )

    def test_unpack_destination_policy_is_explicit(self) -> None:
        archive = self.archive()
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "packet"
            unpack_module_workbench_execution_packet_archive(archive.archive_bytes, destination)
            with self.assertRaises(ValidationError):
                unpack_module_workbench_execution_packet_archive(archive.archive_bytes, destination)
            unpack_module_workbench_execution_packet_archive(
                archive.archive_bytes,
                destination,
                allow_existing=True,
            )
            self.assertTrue((destination / "manifest.json").is_file())

    def test_chunking_preserves_order_offsets_and_addresses(self) -> None:
        archive = self.archive()
        chunks = chunk_module_workbench_execution_packet_archive(archive, chunk_size=128)
        self.assertGreater(len(chunks), 1)
        self.assertEqual(chunks[0].offset, 0)
        self.assertEqual(
            tuple(item.ordinal for item in chunks),
            tuple(range(len(chunks))),
        )
        self.assertEqual(
            tuple(item.offset for item in chunks),
            tuple(
                sum(previous.byte_count for previous in chunks[:index])
                for index in range(len(chunks))
            ),
        )
        self.assertEqual(sum(item.byte_count for item in chunks), archive.archive_byte_count)
        self.assertTrue(all(item.archive_address == archive.archive_address for item in chunks))
        for chunk in chunks:
            self.assertIs(verify_module_workbench_execution_packet_archive_chunk(chunk), chunk)
        self.assertEqual(
            b"".join(item.payload for item in chunks),
            archive.archive_bytes,
        )

    def test_chunk_queries_include_payloads_only_when_requested(self) -> None:
        archive = self.archive()
        without_payload = query_module_workbench_execution_packet_archive_chunks(
            archive,
            chunk_size=256,
            limit=2,
        )
        with_payload = query_module_workbench_execution_packet_archive_chunks(
            archive,
            chunk_size=256,
            ordinal=0,
            include_payloads=True,
        )
        expected_count = len(
            chunk_module_workbench_execution_packet_archive(archive, chunk_size=256)
        )
        self.assertEqual(without_payload["total"], expected_count)
        self.assertEqual(len(without_payload["items"]), 2)
        self.assertEqual(with_payload["total"], 1)
        self.assertIn("payload_hex", with_payload["items"][0])
        self.assertNotIn("payload_hex", without_payload["items"][0])
        chunks = chunk_module_workbench_execution_packet_archive(archive, chunk_size=256)
        self.assertIn(
            "ordinal,offset,byte_count",
            module_workbench_execution_packet_archive_chunks_csv(chunks),
        )

    def test_transfer_can_start_partial_resume_and_complete(self) -> None:
        archive = self.archive()
        chunks = chunk_module_workbench_execution_packet_archive(archive, chunk_size=256)
        transfer = build_module_workbench_execution_packet_archive_transfer(
            archive,
            chunk_size=256,
        )
        self.assertEqual(transfer.state, ModuleWorkbenchExecutionPacketArchiveTransferState.READY)
        self.assertFalse(transfer.accepted)
        self.assertEqual(transfer.remaining_chunks, len(chunks))
        partial = resume_module_workbench_execution_packet_archive_transfer(transfer, (0, 2))
        self.assertEqual(partial.state, ModuleWorkbenchExecutionPacketArchiveTransferState.PARTIAL)
        self.assertEqual(partial.completed_chunks, (0, 2))
        self.assertAlmostEqual(partial.completion_ratio, round(2 / len(chunks), 6))
        completed = resume_module_workbench_execution_packet_archive_transfer(
            partial,
            range(len(chunks)),
        )
        self.assertTrue(completed.accepted)
        self.assertEqual(
            completed.state,
            ModuleWorkbenchExecutionPacketArchiveTransferState.COMPLETED,
        )
        self.assertEqual(completed.remaining_chunks, 0)
        self.assertIs(
            verify_module_workbench_execution_packet_archive_transfer(completed),
            completed,
        )
        self.assertIn(
            "completion_ratio",
            module_workbench_execution_packet_archive_transfer_json(completed),
        )
        self.assertIn(
            "operation_count",
            module_workbench_execution_packet_archive_transfer_capabilities(),
        )

    def test_reassembly_requires_complete_contiguous_chunks(self) -> None:
        archive = self.archive()
        chunks = chunk_module_workbench_execution_packet_archive(archive, chunk_size=256)
        assembled = assemble_module_workbench_execution_packet_archive_chunks(
            chunks,
            archive_address=archive.archive_address,
            total_byte_count=archive.archive_byte_count,
        )
        self.assertEqual(assembled, archive.archive_bytes)
        with self.assertRaises(ValidationError):
            assemble_module_workbench_execution_packet_archive_chunks(
                chunks[:-1],
                archive_address=archive.archive_address,
                total_byte_count=archive.archive_byte_count,
            )
        with self.assertRaises(ValidationError):
            assemble_module_workbench_execution_packet_archive_chunks(
                chunks,
                archive_address="module-workbench-execution-packet-archive:wrong",
                total_byte_count=archive.archive_byte_count,
            )
        object.__setattr__(chunks[0], "payload", b"tampered")
        with self.assertRaises(ValidationError):
            verify_module_workbench_execution_packet_archive_chunk(chunks[0])

    def test_chunk_and_transfer_bounds_fail_closed(self) -> None:
        archive = self.archive()
        with self.assertRaises(ValidationError):
            chunk_module_workbench_execution_packet_archive(archive, chunk_size=0)
        with self.assertRaises(ValidationError):
            chunk_module_workbench_execution_packet_archive(archive, chunk_size=1048577)
        chunks = chunk_module_workbench_execution_packet_archive(archive, chunk_size=256)
        with self.assertRaises(ValidationError):
            build_module_workbench_execution_packet_archive_transfer(
                archive,
                chunk_size=256,
                completed_chunks=(len(chunks),),
            )
        with self.assertRaises(ValidationError):
            resume_module_workbench_execution_packet_archive_transfer(
                build_module_workbench_execution_packet_archive_transfer(archive),
                (len(chunks),),
            )

    def test_archive_runtime_completes_all_transport_stages(self) -> None:
        archive = self.archive()
        runtime = run_module_workbench_execution_packet_archive_runtime(
            archive,
            chunk_size=512,
        )
        self.assertTrue(runtime.accepted)
        self.assertEqual(runtime.stage_count, 9)
        self.assertEqual(runtime.completed_count, 9)
        self.assertEqual(runtime.blocked_count, 0)
        self.assertEqual(
            tuple(item.kind for item in runtime.stages),
            tuple(ModuleWorkbenchExecutionPacketArchiveRuntimeStageKind),
        )
        self.assertIs(verify_module_workbench_execution_packet_archive_runtime(runtime), runtime)
        self.assertEqual(
            query_module_workbench_execution_packet_archive_runtime(runtime)["total"],
            9,
        )
        self.assertEqual(
            query_module_workbench_execution_packet_archive_runtime(
                runtime,
                resource="summary",
            )["total"],
            1,
        )
        self.assertIn(
            "stage_count",
            module_workbench_execution_packet_archive_runtime_json(runtime),
        )
        self.assertIn("kind", module_workbench_execution_packet_archive_runtime_csv(runtime))

    def test_archive_runtime_can_write_and_unpack(self) -> None:
        archive = self.archive()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = run_module_workbench_execution_packet_archive_runtime(
                archive,
                destination=root / "packet.zip",
                unpack_destination=root / "packet",
                chunk_size=512,
            )
            self.assertTrue(runtime.accepted)
            self.assertTrue((root / "packet.zip").is_file())
            self.assertTrue((root / "packet" / "manifest.json").is_file())
            self.assertEqual(
                verify_module_workbench_execution_packet_archive(
                    root / "packet.zip"
                ).archive_address,
                archive.archive_address,
            )

    def test_schemas_and_capabilities_conserve_operations(self) -> None:
        schema = module_workbench_execution_packet_archive_schema()
        transfer_schema = module_workbench_execution_packet_archive_transfer_schema()
        runtime_schema = module_workbench_execution_packet_archive_runtime_schema()
        for capabilities in (
            module_workbench_execution_packet_archive_capabilities(),
            module_workbench_execution_packet_archive_transfer_capabilities(),
            module_workbench_execution_packet_archive_runtime_capabilities(),
        ):
            self.assertEqual(capabilities["operation_count"], len(capabilities["operations"]))
            self.assertTrue(capabilities["deterministic"])
            self.assertTrue(capabilities["offline"])
            self.assertTrue(capabilities["identity_free"])
        self.assertEqual(schema["format"], MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_FORMAT)
        self.assertTrue(schema["path_free"])
        self.assertTrue(schema["timestamp_free"])
        self.assertEqual(
            transfer_schema["resources"],
            ["chunks", "transfer", "reassembled_archive"],
        )
        self.assertEqual(
            runtime_schema["stage_order"],
            [item.value for item in ModuleWorkbenchExecutionPacketArchiveRuntimeStageKind],
        )
        self.assertEqual(MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_DEFAULT_CHUNK_SIZE, 65536)

    def test_archive_diff_is_addressed_and_classifies_member_changes(self) -> None:
        left = build_module_workbench_execution_packet_archive(
            self.packet(),
            archive_id="left-archive",
        )
        right = build_module_workbench_execution_packet_archive(
            self.packet(),
            archive_id="right-archive",
        )
        report = diff_module_workbench_execution_packet_archives(left, right)
        self.assertTrue(report.accepted)
        self.assertTrue(report.same_archive_bytes)
        self.assertTrue(report.same_packet)
        self.assertTrue(report.compatible)
        self.assertEqual(report.change_count, 14)
        self.assertEqual(report.unchanged_count, 14)
        self.assertEqual(report.modified_count, 0)
        self.assertIs(verify_module_workbench_execution_packet_archive_diff(report), report)
        self.assertEqual(
            query_module_workbench_execution_packet_archive_diff(
                report,
                resource="unchanged",
                relative_path="manifest.json",
            )["total"],
            1,
        )
        self.assertIn("change_count", module_workbench_execution_packet_archive_diff_json(report))
        self.assertIn("relative_path", module_workbench_execution_packet_archive_diff_csv(report))
        self.assertIn(
            "Compatible",
            render_module_workbench_execution_packet_archive_diff_markdown(report),
        )

    def test_archive_diff_detects_packet_manifest_change(self) -> None:
        left = build_module_workbench_execution_packet_archive(self.packet())
        right_packet = build_module_workbench_execution_packet(
            self.fixture.report(),
            packet_id="alternate-execution-packet",
        )
        right = build_module_workbench_execution_packet_archive(right_packet)
        report = diff_module_workbench_execution_packet_archives(left, right)
        self.assertTrue(report.accepted)
        self.assertFalse(report.same_archive_bytes)
        self.assertFalse(report.same_packet)
        self.assertGreater(report.modified_count, 0)
        self.assertEqual(
            query_module_workbench_execution_packet_archive_diff(
                report,
                resource="modified",
            )["total"],
            report.modified_count,
        )

    def test_archive_diff_bounds_and_exports(self) -> None:
        report = diff_module_workbench_execution_packet_archives(self.archive(), self.archive())
        schema = module_workbench_execution_packet_archive_diff_schema()
        capabilities = module_workbench_execution_packet_archive_diff_capabilities()
        self.assertEqual(
            schema["resources"],
            ["summary", "changes", "added", "removed", "modified", "unchanged"],
        )
        self.assertEqual(capabilities["operation_count"], len(capabilities["operations"]))
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_diff(report, limit=513)

    def test_archive_index_conserves_records_and_groups_duplicates(self) -> None:
        archive = build_module_workbench_execution_packet_archive(
            self.packet(),
            archive_id="archive-index-left",
        )
        duplicate = build_module_workbench_execution_packet_archive(
            self.packet(),
            archive_id="archive-index-right",
        )
        index = build_module_workbench_execution_packet_archive_index(
            (archive, duplicate),
            index_id="test-archive-index",
        )
        self.assertTrue(index.accepted)
        self.assertEqual(index.archive_count, 2)
        self.assertEqual(index.unique_archive_count, 1)
        self.assertEqual(index.duplicate_archive_count, 1)
        self.assertEqual(index.unique_packet_count, 1)
        self.assertEqual(len(index.duplicate_groups), 1)
        self.assertIs(verify_module_workbench_execution_packet_archive_index(index), index)
        self.assertEqual(
            query_module_workbench_execution_packet_archive_index(
                index,
                resource="duplicates",
            )["total"],
            1,
        )
        self.assertEqual(
            query_module_workbench_execution_packet_archive_index(
                index,
                resource="packets",
            )["total"],
            1,
        )
        self.assertEqual(
            query_module_workbench_execution_packet_archive_index(
                index,
                archive_id="archive-index-left",
            )["total"],
            1,
        )
        with self.assertRaises(ValidationError):
            resolve_module_workbench_execution_packet_archive_index_entry(
                index,
                archive.archive_address,
            )
        self.assertIn("archive_count", module_workbench_execution_packet_archive_index_json(index))
        self.assertIn("archive_id", module_workbench_execution_packet_archive_index_csv(index))
        self.assertIn(
            "duplicates",
            render_module_workbench_execution_packet_archive_index_markdown(index),
        )

    def test_archive_index_schema_capabilities_and_query_filters(self) -> None:
        index = build_module_workbench_execution_packet_archive_index((self.archive(),))
        schema = module_workbench_execution_packet_archive_index_schema()
        capabilities = module_workbench_execution_packet_archive_index_capabilities()
        self.assertEqual(schema["resources"], ["summary", "archives", "packets", "duplicates"])
        self.assertEqual(capabilities["operation_count"], len(capabilities["operations"]))
        self.assertEqual(
            query_module_workbench_execution_packet_archive_index(
                index,
                resource="summary",
            )["total"],
            1,
        )
        self.assertEqual(
            query_module_workbench_execution_packet_archive_index(index, accepted=True)["total"],
            1,
        )
        self.assertEqual(
            query_module_workbench_execution_packet_archive_index(index, text="packet")["total"],
            1,
        )
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_index(index, resource="unknown")

    def test_cli_archive_surfaces_and_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packet_dir = root / "packet"
            packet_path = root / "packet.zip"
            output = root / "output.json"
            write_module_workbench_execution_packet(self.packet(), packet_dir)
            for command in (
                "module-workbench-execution-packet-archive-schema",
                "module-workbench-execution-packet-archive-capabilities",
                "module-workbench-execution-packet-archive-transfer-schema",
                "module-workbench-execution-packet-archive-transfer-capabilities",
                "module-workbench-execution-packet-archive-runtime-schema",
                "module-workbench-execution-packet-archive-runtime-capabilities",
            ):
                self.assertEqual(main([command, "--output", str(output)]), 0)
                self.assertTrue(output.read_text(encoding="utf-8").strip())
            self.assertEqual(
                main(
                    [
                        "module-workbench-execution-packet-archive",
                        str(packet_dir),
                        "--destination",
                        str(packet_path),
                        "--format",
                        "markdown",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            self.assertIn("Archive", output.read_text(encoding="utf-8"))
            self.assertEqual(
                main(
                    [
                        "module-workbench-execution-packet-archive-verify",
                        str(packet_path),
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
                        "module-workbench-execution-packet-archive-query",
                        str(packet_path),
                        "--resource",
                        "entries",
                        "--kind",
                        "artifact",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            self.assertIn('"total": 13', output.read_text(encoding="utf-8"))

            for command in (
                "module-workbench-execution-packet-archive-diff-schema",
                "module-workbench-execution-packet-archive-diff-capabilities",
                "module-workbench-execution-packet-archive-index-schema",
                "module-workbench-execution-packet-archive-index-capabilities",
            ):
                self.assertEqual(main([command, "--output", str(output)]), 0)
                self.assertTrue(output.read_text(encoding="utf-8").strip())
            self.assertEqual(
                main(
                    [
                        "module-workbench-execution-packet-archive-diff",
                        str(packet_path),
                        str(packet_path),
                        "--resource",
                        "summary",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            self.assertIn('"same_archive_bytes": true', output.read_text(encoding="utf-8"))
            self.assertEqual(
                main(
                    [
                        "module-workbench-execution-packet-archive-index",
                        str(packet_path),
                        "--resource",
                        "summary",
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            self.assertIn('"archive_count": 1', output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
