"""Deep tests for immutable archive store checkpoints and ancestry proofs."""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.module_workbench_execution_packet import (
    build_module_workbench_execution_packet,
    write_module_workbench_execution_packet,
)
from glio_noncode.module_workbench_execution_packet_archive import (
    build_module_workbench_execution_packet_archive,
    write_module_workbench_execution_packet_archive,
)
from glio_noncode.module_workbench_execution_packet_archive_store import (
    append_module_workbench_execution_packet_archive_store,
    build_module_workbench_execution_packet_archive_store,
    load_module_workbench_execution_packet_archive_store,
    write_module_workbench_execution_packet_archive_store,
)
from glio_noncode.module_workbench_execution_packet_archive_store_checkpoint import (
    ModuleWorkbenchExecutionPacketArchiveStoreComparisonState,
    build_module_workbench_execution_packet_archive_store_checkpoint,
    checkpoint_module_workbench_execution_packet_archive_store_from_mapping,
    compare_module_workbench_execution_packet_archive_store_to_checkpoint,
    module_workbench_execution_packet_archive_store_checkpoint_capabilities,
    module_workbench_execution_packet_archive_store_checkpoint_csv,
    module_workbench_execution_packet_archive_store_checkpoint_json,
    module_workbench_execution_packet_archive_store_checkpoint_schema,
    module_workbench_execution_packet_archive_store_comparison_csv,
    module_workbench_execution_packet_archive_store_comparison_json,
    query_module_workbench_execution_packet_archive_store_checkpoint,
    render_module_workbench_execution_packet_archive_store_checkpoint_markdown,
    verify_module_workbench_execution_packet_archive_store_checkpoint,
    verify_module_workbench_execution_packet_archive_store_comparison,
)
from tests.test_module_workbench_execution import ModuleWorkbenchExecutionFixture


class ModuleWorkbenchExecutionPacketArchiveStoreCheckpointTests(unittest.TestCase):
    """Exercise checkpoint capture, replay, comparison, and shell surfaces."""

    def setUp(self) -> None:
        self.fixture = ModuleWorkbenchExecutionFixture()
        self.fixture.setUp()

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def packet(self, packet_id: str = "checkpoint-packet"):
        return build_module_workbench_execution_packet(self.fixture.report(), packet_id=packet_id)

    def archive(self, packet_id: str = "checkpoint-packet", archive_id: str = "checkpoint-archive"):
        return build_module_workbench_execution_packet_archive(
            self.packet(packet_id), archive_id=archive_id
        )

    def store(self, *archives):
        return build_module_workbench_execution_packet_archive_store(
            archives or (self.archive(),), store_id="checkpoint-store"
        )

    def test_checkpoint_is_deterministic_and_captures_complete_boundary(self) -> None:
        store = self.store(
            self.archive(archive_id="one"), self.archive(archive_id="two", packet_id="two")
        )
        first = build_module_workbench_execution_packet_archive_store_checkpoint(
            store, checkpoint_id="stable-checkpoint"
        )
        second = build_module_workbench_execution_packet_archive_store_checkpoint(
            store, checkpoint_id="stable-checkpoint"
        )
        self.assertTrue(first.accepted)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.archive_count, 2)
        self.assertEqual(first.object_count, 2)
        self.assertEqual(first.operation_count, 2)
        self.assertEqual(len(first.operation_addresses), 2)
        self.assertEqual(len(first.entry_addresses), 2)
        self.assertEqual(first.head_address, store.head_address)
        verify_module_workbench_execution_packet_archive_store_checkpoint(first)

    def test_checkpoint_round_trip_from_exported_mapping(self) -> None:
        checkpoint = build_module_workbench_execution_packet_archive_store_checkpoint(self.store())
        restored = checkpoint_module_workbench_execution_packet_archive_store_from_mapping(
            checkpoint.to_dict()
        )
        self.assertEqual(restored, checkpoint)
        self.assertEqual(
            module_workbench_execution_packet_archive_store_checkpoint_json(checkpoint),
            module_workbench_execution_packet_archive_store_checkpoint_json(restored),
        )

    def test_checkpoint_proves_exact_match(self) -> None:
        store = self.store()
        checkpoint = build_module_workbench_execution_packet_archive_store_checkpoint(store)
        comparison = compare_module_workbench_execution_packet_archive_store_to_checkpoint(
            store, checkpoint
        )
        self.assertEqual(
            comparison.state,
            ModuleWorkbenchExecutionPacketArchiveStoreComparisonState.MATCHED,
        )
        self.assertTrue(comparison.accepted)
        self.assertTrue(comparison.ancestor)
        self.assertEqual(comparison.added_operation_addresses, ())
        self.assertEqual(comparison.missing_operation_addresses, ())
        self.assertEqual(comparison.added_entry_addresses, ())
        self.assertEqual(comparison.missing_entry_addresses, ())
        verify_module_workbench_execution_packet_archive_store_comparison(comparison)

    def test_checkpoint_proves_append_only_extension(self) -> None:
        base = self.store(self.archive(packet_id="base", archive_id="base"))
        checkpoint = build_module_workbench_execution_packet_archive_store_checkpoint(base)
        current = append_module_workbench_execution_packet_archive_store(
            base,
            self.archive(packet_id="next", archive_id="next"),
            operation_id="next-operation",
            expected_head_address=base.head_address,
        )
        comparison = compare_module_workbench_execution_packet_archive_store_to_checkpoint(
            current, checkpoint
        )
        self.assertEqual(
            comparison.state,
            ModuleWorkbenchExecutionPacketArchiveStoreComparisonState.EXTENDED,
        )
        self.assertTrue(comparison.accepted)
        self.assertTrue(comparison.ancestor)
        self.assertEqual(len(comparison.added_operation_addresses), 1)
        self.assertEqual(len(comparison.added_entry_addresses), 1)
        self.assertEqual(comparison.missing_operation_addresses, ())
        self.assertEqual(comparison.missing_entry_addresses, ())

    def test_checkpoint_detects_deduplicated_append_as_operation_extension(self) -> None:
        base = self.store(self.archive(packet_id="base", archive_id="base"))
        checkpoint = build_module_workbench_execution_packet_archive_store_checkpoint(base)
        current = append_module_workbench_execution_packet_archive_store(
            base,
            self.archive(packet_id="base", archive_id="different-label"),
            operation_id="duplicate-operation",
            expected_head_address=base.head_address,
        )
        comparison = compare_module_workbench_execution_packet_archive_store_to_checkpoint(
            current, checkpoint
        )
        self.assertEqual(
            comparison.state,
            ModuleWorkbenchExecutionPacketArchiveStoreComparisonState.EXTENDED,
        )
        self.assertEqual(len(comparison.added_operation_addresses), 1)
        self.assertEqual(comparison.added_entry_addresses, ())
        self.assertEqual(current.archive_count, base.archive_count)
        self.assertEqual(current.operation_count, base.operation_count + 1)

    def test_checkpoint_detects_journal_divergence(self) -> None:
        base = self.store(self.archive(packet_id="base", archive_id="base"))
        checkpoint = build_module_workbench_execution_packet_archive_store_checkpoint(base)
        divergent = self.store(self.archive(packet_id="other", archive_id="other"))
        comparison = compare_module_workbench_execution_packet_archive_store_to_checkpoint(
            divergent, checkpoint
        )
        self.assertEqual(
            comparison.state,
            ModuleWorkbenchExecutionPacketArchiveStoreComparisonState.DIVERGED,
        )
        self.assertFalse(comparison.accepted)
        self.assertFalse(comparison.ancestor)
        self.assertEqual(len(comparison.missing_operation_addresses), 1)
        self.assertEqual(len(comparison.added_operation_addresses), 1)

    def test_checkpoint_blocks_foreign_store_identity(self) -> None:
        store = self.store()
        checkpoint = build_module_workbench_execution_packet_archive_store_checkpoint(store)
        foreign = build_module_workbench_execution_packet_archive_store(
            (self.archive(),), store_id="foreign-store"
        )
        comparison = compare_module_workbench_execution_packet_archive_store_to_checkpoint(
            foreign, checkpoint
        )
        self.assertEqual(
            comparison.state,
            ModuleWorkbenchExecutionPacketArchiveStoreComparisonState.BLOCKED,
        )
        self.assertFalse(comparison.accepted)

    def test_checkpoint_query_has_bounded_resources_and_addresses_result(self) -> None:
        base = self.store(self.archive(packet_id="base", archive_id="base"))
        checkpoint = build_module_workbench_execution_packet_archive_store_checkpoint(base)
        current = append_module_workbench_execution_packet_archive_store(
            base,
            self.archive(packet_id="next", archive_id="next"),
            operation_id="next-operation",
        )
        comparison = compare_module_workbench_execution_packet_archive_store_to_checkpoint(
            current, checkpoint
        )
        summary = query_module_workbench_execution_packet_archive_store_checkpoint(comparison)
        added = query_module_workbench_execution_packet_archive_store_checkpoint(
            comparison, resource="added_operations", offset=0, limit=1
        )
        self.assertTrue(summary["accepted"])
        self.assertEqual(summary["total"], 1)
        self.assertEqual(added["total"], 1)
        self.assertEqual(len(added["items"]), 1)
        self.assertIn("content_address", summary)
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store_checkpoint(comparison, limit=513)

    def test_checkpoint_exports_are_stable_and_identity_free(self) -> None:
        checkpoint = build_module_workbench_execution_packet_archive_store_checkpoint(self.store())
        self.assertIn(
            "# Archive Store Checkpoint",
            render_module_workbench_execution_packet_archive_store_checkpoint_markdown(checkpoint),
        )
        self.assertIn(
            "checkpoint_id",
            module_workbench_execution_packet_archive_store_checkpoint_csv(checkpoint),
        )
        comparison = compare_module_workbench_execution_packet_archive_store_to_checkpoint(
            self.store(), checkpoint
        )
        self.assertIn(
            "content_address",
            module_workbench_execution_packet_archive_store_comparison_json(comparison),
        )
        self.assertIn(
            "resource", module_workbench_execution_packet_archive_store_comparison_csv(comparison)
        )
        for text in (
            module_workbench_execution_packet_archive_store_checkpoint_json(checkpoint),
            module_workbench_execution_packet_archive_store_checkpoint_csv(checkpoint),
            render_module_workbench_execution_packet_archive_store_checkpoint_markdown(checkpoint),
            module_workbench_execution_packet_archive_store_comparison_json(comparison),
        ):
            self.assertNotIn('"agent"', text)
            self.assertNotIn('"private"', text)
            self.assertNotIn('"language"', text)

    def test_checkpoint_verification_rejects_address_tampering(self) -> None:
        checkpoint = build_module_workbench_execution_packet_archive_store_checkpoint(self.store())
        tampered = replace(checkpoint, checkpoint_id="changed")
        with self.assertRaises(ValidationError):
            verify_module_workbench_execution_packet_archive_store_checkpoint(tampered)
        comparison = compare_module_workbench_execution_packet_archive_store_to_checkpoint(
            self.store(), checkpoint
        )
        tampered_comparison = replace(comparison, detail="changed")
        with self.assertRaises(ValidationError):
            verify_module_workbench_execution_packet_archive_store_comparison(tampered_comparison)

    def test_schema_and_capabilities_are_explicit_and_deterministic(self) -> None:
        schema = module_workbench_execution_packet_archive_store_checkpoint_schema()
        capabilities = module_workbench_execution_packet_archive_store_checkpoint_capabilities()
        self.assertEqual(schema["resources"][0], "summary")
        self.assertEqual(schema["states"], ["accepted", "blocked"])
        self.assertTrue(schema["identity_free"])
        self.assertEqual(capabilities["operation_count"], len(capabilities["operations"]))
        self.assertTrue(capabilities["append_only_proof"])
        self.assertTrue(capabilities["deterministic"])

    def test_checkpoint_survives_store_directory_round_trip(self) -> None:
        store = self.store()
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "store"
            write_module_workbench_execution_packet_archive_store(store, destination)
            loaded = load_module_workbench_execution_packet_archive_store(destination)
            checkpoint = build_module_workbench_execution_packet_archive_store_checkpoint(loaded)
            comparison = compare_module_workbench_execution_packet_archive_store_to_checkpoint(
                loaded, checkpoint
            )
            self.assertEqual(
                comparison.state, ModuleWorkbenchExecutionPacketArchiveStoreComparisonState.MATCHED
            )

    def test_cli_checkpoint_and_comparison_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packet_path = root / "packet"
            archive_path = root / "archive.zip"
            store_path = root / "store"
            checkpoint_path = root / "checkpoint.json"
            output_path = root / "output.json"
            write_module_workbench_execution_packet(self.packet(), packet_path)
            write_module_workbench_execution_packet_archive(
                build_module_workbench_execution_packet_archive(packet_path), archive_path
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-execution-packet-archive-store",
                        str(archive_path),
                        "--destination",
                        str(store_path),
                        "--output",
                        str(output_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-execution-packet-archive-store-checkpoint",
                        str(store_path),
                        "--output",
                        str(checkpoint_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-execution-packet-archive-store-checkpoint-compare",
                        str(store_path),
                        str(checkpoint_path),
                        "--output",
                        str(output_path),
                    ]
                ),
                0,
            )
            self.assertIn('"state":"matched"', output_path.read_text(encoding="utf-8"))
            self.assertEqual(
                main(
                    [
                        "module-workbench-execution-packet-archive-store-checkpoint-query",
                        str(store_path),
                        str(checkpoint_path),
                        "--resource",
                        "summary",
                        "--output",
                        str(output_path),
                    ]
                ),
                0,
            )
            self.assertIn('"accepted": true', output_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
