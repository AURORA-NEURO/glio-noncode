"""Deep tests for bounded multi-packet diff matrices."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.module_workbench_execution_packet import (
    build_module_workbench_execution_packet,
)
from glio_noncode.module_workbench_execution_packet_archive import (
    build_module_workbench_execution_packet_archive,
)
from glio_noncode.module_workbench_execution_packet_archive_store import (
    append_module_workbench_execution_packet_archive_store,
    build_module_workbench_execution_packet_archive_store,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication import (
    build_module_workbench_execution_packet_archive_store_replication,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet import (
    build_module_workbench_execution_packet_archive_store_replication_packet,
    write_module_workbench_execution_packet_archive_store_replication_packet,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_batch import (  # noqa: E501
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffBatch,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_batch,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_batch,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_batch_from_directories,
    module_workbench_execution_packet_archive_store_replication_packet_diff_batch_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_batch_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_batch_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_batch_query_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_batch_query_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_batch_schema,
    query_module_workbench_execution_packet_archive_store_replication_packet_diff_batch,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_batch_markdown,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_batch_query_markdown,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_batch,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_batch_query,
)
from glio_noncode.serialization import canonical_json
from tests.test_module_workbench_execution import ModuleWorkbenchExecutionFixture


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffBatchTests(unittest.TestCase):
    """Exercise matrix construction, conservation, queries, and persistence."""

    def setUp(self) -> None:
        self.fixture = ModuleWorkbenchExecutionFixture()
        self.fixture.setUp()

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def _archive(self, packet_id: str, archive_id: str):
        packet = build_module_workbench_execution_packet(self.fixture.report(), packet_id=packet_id)
        return build_module_workbench_execution_packet_archive(packet, archive_id=archive_id)

    def _stores(self):
        base = self._archive("base", "base")
        next_archive = self._archive("next", "next")
        target = build_module_workbench_execution_packet_archive_store((base,), store_id="target")
        source = append_module_workbench_execution_packet_archive_store(
            target, next_archive, operation_id="next-operation"
        )
        return source, target

    def _packet(self, packet_id: str = "base-packet"):
        source, target = self._stores()
        plan = build_module_workbench_execution_packet_archive_store_replication(source, target)
        return build_module_workbench_execution_packet_archive_store_replication_packet(
            plan, packet_id=packet_id
        )

    def _values(self):
        packet, _ = self._packet()
        changed, _ = self._packet("changed-packet")
        matched = build_module_workbench_execution_packet_archive_store_replication_packet_diff(
            packet, packet
        )
        divergent = build_module_workbench_execution_packet_archive_store_replication_packet_diff(
            packet, changed
        )
        matched_release = (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release(
                matched
            )
        )
        divergent_release = (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release(
                divergent
            )
        )
        return packet, matched, matched_release, divergent, divergent_release

    def _batch(self):
        _, matched, matched_release, divergent, divergent_release = self._values()
        return build_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(
            (
                ("matched", matched, matched_release),
                ("review", divergent, divergent_release),
            ),
            batch_id="batch-fixture",
        )

    def test_matrix_conserves_pair_and_release_counts(self) -> None:
        batch = self._batch()
        self.assertIsInstance(
            batch, ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffBatch
        )
        self.assertEqual(batch.item_count, 2)
        self.assertEqual(batch.accepted_count, 2)
        self.assertEqual(batch.release_ready_count, 1)
        self.assertEqual(batch.matched_count, 1)
        self.assertEqual(batch.diverged_count, 1)
        self.assertEqual(batch.promotable_count, 1)
        self.assertEqual(batch.hold_count, 1)
        self.assertEqual(batch.score, 0.5)
        self.assertTrue(batch.accepted)
        self.assertFalse(batch.release_ready)

    def test_item_addresses_and_batch_address_are_stable(self) -> None:
        batch = self._batch()
        self.assertIs(
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(
                batch
            ),
            batch,
        )
        self.assertEqual(
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(
                batch
            ),
            batch.content_address,
        )
        self.assertEqual(tuple(item.ordinal for item in batch.items), (0, 1))
        self.assertEqual(len({item.content_address for item in batch.items}), 2)
        self.assertIn("diff-batch:", batch.content_address)

    def test_summary_query_filters_state_and_readiness(self) -> None:
        batch = self._batch()
        summary = (
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(
                batch
            )
        )
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["items"][0]["batch_id"], "batch-fixture")
        review = (
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(
                batch,
                resource="items",
                state="diverged",
                release_ready=False,
            )
        )
        self.assertEqual(review["total"], 1)
        self.assertEqual(review["items"][0]["pair_id"], "review")
        verify_module_workbench_execution_packet_archive_store_replication_packet_diff_batch_query(
            review
        )

    def test_query_text_and_paging_are_bounded(self) -> None:
        batch = self._batch()
        result = (
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(
                batch, resource="items", text="review", offset=0, limit=1
            )
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(len(result["items"]), 1)
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(
                batch, limit=513
            )
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(
                batch, offset=-1
            )

    def test_json_csv_markdown_exports_are_reviewable(self) -> None:
        batch = self._batch()
        self.assertEqual(
            json.loads(
                module_workbench_execution_packet_archive_store_replication_packet_diff_batch_json(
                    batch
                )
            ),
            json.loads(canonical_json(batch.to_dict())),
        )
        csv_text = (
            module_workbench_execution_packet_archive_store_replication_packet_diff_batch_csv(batch)
        )
        markdown = render_module_workbench_execution_packet_archive_store_replication_packet_diff_batch_markdown(  # noqa: E501
            batch
        )
        self.assertIn("pair_id", csv_text)
        self.assertIn("# Archive Store Replication Packet Diff Batch", markdown)
        query = query_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(
            batch, resource="items"
        )
        self.assertIn(
            "pair_id",
            module_workbench_execution_packet_archive_store_replication_packet_diff_batch_query_csv(
                query
            ),
        )
        self.assertIn(
            "# Archive Store Replication Packet Diff Batch Query",
            render_module_workbench_execution_packet_archive_store_replication_packet_diff_batch_query_markdown(
                query
            ),
        )
        self.assertEqual(
            json.loads(
                module_workbench_execution_packet_archive_store_replication_packet_diff_batch_query_json(
                    query
                )
            ),
            json.loads(canonical_json(query)),
        )

    def test_directory_loader_verifies_two_persisted_pairs(self) -> None:
        packet, payloads = self._packet()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left = root / "left"
            right = root / "right"
            write_module_workbench_execution_packet_archive_store_replication_packet(
                packet, payloads, left
            )
            write_module_workbench_execution_packet_archive_store_replication_packet(
                packet, payloads, right
            )
            batch = build_module_workbench_execution_packet_archive_store_replication_packet_diff_batch_from_directories(  # noqa: E501
                (("persisted", left, right),),
                batch_id="directory-batch",
            )
        self.assertTrue(batch.accepted)
        self.assertTrue(batch.release_ready)
        self.assertEqual(batch.matched_count, 1)

    def test_duplicate_pair_ids_and_empty_batches_fail_closed(self) -> None:
        _, matched, matched_release, _, _ = self._values()
        with self.assertRaises(ValidationError):
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(())
        with self.assertRaises(ValidationError):
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(
                (
                    ("same", matched, matched_release),
                    ("same", matched, matched_release),
                )
            )
        with self.assertRaises(ValidationError):
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(
                (
                    ("bad", matched, matched_release),
                    ("bad-shape", matched, matched_release, "extra"),
                )
            )

    def test_tampered_batch_and_query_addresses_are_rejected(self) -> None:
        batch = self._batch()
        batch.detail = "changed"
        with self.assertRaises(ValidationError):
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(
                batch
            )
        clean = self._batch()
        query = query_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(
            clean, resource="items"
        )
        with self.assertRaises(ValidationError):
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_batch_query(
                query | {"accepted": False}
            )

    def test_schema_and_capabilities_state_the_matrix_contract(self) -> None:
        schema = (
            module_workbench_execution_packet_archive_store_replication_packet_diff_batch_schema()
        )
        capabilities = (
            module_workbench_execution_packet_archive_store_replication_packet_diff_batch_capabilities()
        )
        self.assertIn("release_states", schema)
        self.assertIn("conserved_counts", schema["conservation"])
        self.assertIn("build_release_matrix", capabilities["operations"])
        self.assertIn("unique_pair_ids", capabilities["guarantees"])

    def test_public_matrix_documents_do_not_expose_paths_or_identity(self) -> None:
        batch = self._batch()
        documents = (
            module_workbench_execution_packet_archive_store_replication_packet_diff_batch_json(
                batch
            ),
            module_workbench_execution_packet_archive_store_replication_packet_diff_batch_csv(
                batch
            ),
            render_module_workbench_execution_packet_archive_store_replication_packet_diff_batch_markdown(
                batch
            ),
        )
        for document in documents:
            lowered = document.casefold()
            self.assertNotIn("c:\\", lowered)
            self.assertNotIn("agent", lowered)
            self.assertNotIn("assistant", lowered)
            self.assertNotIn("username", lowered)


if __name__ == "__main__":
    unittest.main()
