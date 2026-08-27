"""Deep regression coverage for review-store catalogs and federation."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from glio_noncode.errors import ValidationError
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog import (
    append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog,
    load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_schema,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_markdown,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog,
    write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MANIFEST,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogState,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_from_directories,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_query_schema,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_schema,
    query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_markdown,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_from_directory,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_query_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_query_schema,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_schema,
    query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_markdown,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_query import (
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_query_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_query_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_query_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_query_schema,
    query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_query_markdown,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_query,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime import (
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_query_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_query_schema,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_schema,
    query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_markdown,
    run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime,
)


class ReviewStoreCatalogTests(unittest.TestCase):
    """Exercise the collection boundary without requiring private fixtures."""

    @staticmethod
    def _store(
        store_id: str,
        *,
        state: str = "ready",
        release_ready: bool = True,
        accepted: bool = True,
        window_address: str = "window:one",
        ledger_address: str | None = None,
    ) -> SimpleNamespace:
        ledger = SimpleNamespace(
            window_address=window_address,
            content_address=ledger_address or f"ledger:{store_id}",
            head_address=f"entry:{store_id}",
            entry_count=1,
        )
        return SimpleNamespace(
            store_id=store_id,
            content_address=f"store:{store_id}",
            ledger_address=ledger.content_address,
            head_address=ledger.head_address,
            entry_count=1,
            state=state,
            release_ready=release_ready,
            accepted=accepted,
            append_only=True,
            operation_count=1,
            ledger=ledger,
        )

    def _catalog(self, *stores: SimpleNamespace, catalog_id: str = "catalog"):
        return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
            stores,
            catalog_id=catalog_id,
        )

    def _ready(self):
        return self._catalog(self._store("alpha"), self._store("beta"))

    def test_empty_catalog_retains_genesis_and_blocks_readiness(self) -> None:
        catalog = self._catalog()
        self.assertEqual(
            catalog.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogState.EMPTY.value,
        )
        self.assertFalse(catalog.accepted)
        self.assertFalse(catalog.release_ready)
        self.assertEqual(catalog.entry_count, 0)
        self.assertEqual(catalog.operation_count, 1)
        self.assertEqual(catalog.operations[0].kind, "genesis")

    def test_ready_catalog_conserves_members_and_registration_journal(self) -> None:
        catalog = self._ready()
        self.assertEqual(catalog.state, "ready")
        self.assertTrue(catalog.release_ready)
        self.assertTrue(catalog.accepted)
        self.assertEqual(catalog.entry_count, 2)
        self.assertEqual(catalog.operation_count, 3)
        self.assertEqual(catalog.check_count, 8)
        self.assertEqual([entry.store_id for entry in catalog.entries], ["alpha", "beta"])
        self.assertTrue(all(operation.accepted for operation in catalog.operations))
        self.assertTrue(
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
                catalog
            ).accepted
        )

    def test_catalog_order_is_independent_of_input_order(self) -> None:
        left = self._catalog(self._store("beta"), self._store("alpha"))
        right = self._catalog(self._store("alpha"), self._store("beta"))
        self.assertEqual(left.to_dict(), right.to_dict())
        self.assertEqual(left.content_address, right.content_address)

    def test_held_member_holds_catalog_without_losing_acceptance(self) -> None:
        catalog = self._catalog(self._store("held", state="held", release_ready=False))
        self.assertEqual(catalog.state, "held")
        self.assertTrue(catalog.accepted)
        self.assertFalse(catalog.release_ready)
        self.assertTrue(all(check.passed for check in catalog.checks))

    def test_blocked_member_blocks_catalog(self) -> None:
        catalog = self._catalog(
            self._store("blocked", state="blocked", release_ready=False, accepted=False)
        )
        self.assertEqual(catalog.state, "blocked")
        self.assertFalse(catalog.accepted)
        self.assertFalse(catalog.release_ready)
        self.assertFalse(
            next(check for check in catalog.checks if check.kind == "member-acceptance").passed
        )

    def test_duplicate_store_ids_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            self._catalog(self._store("same"), self._store("same"))

    def test_catalog_append_requires_expected_address(self) -> None:
        catalog = self._catalog(self._store("alpha"))
        extended = append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
            catalog, [self._store("beta")], expected_catalog_address=catalog.content_address
        )
        self.assertEqual(extended.entry_count, 2)
        self.assertEqual(extended.operation_count, 3)
        self.assertEqual(extended.entries[0].store_id, "alpha")
        self.assertEqual(extended.entries[1].store_id, "beta")
        with self.assertRaises(ValidationError):
            append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
                catalog, [self._store("gamma")], expected_catalog_address="catalog:stale"
            )

    def test_catalog_append_rejects_duplicate_and_preserves_prior_chain(self) -> None:
        catalog = self._catalog(self._store("alpha"))
        with self.assertRaises(ValidationError):
            append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
                catalog, [self._store("alpha")]
            )
        extended = append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
            catalog, [self._store("beta")]
        )
        self.assertEqual(
            extended.operations[0].content_address, catalog.operations[0].content_address
        )
        self.assertEqual(
            extended.operations[1].content_address, catalog.operations[1].content_address
        )
        self.assertEqual(
            extended.operations[2].previous_operation_address,
            extended.operations[1].content_address,
        )

    def test_atomic_catalog_write_load_round_trip(self) -> None:
        catalog = self._ready()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "catalog"
            self.assertEqual(
                write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
                    catalog, destination
                ),
                destination,
            )
            self.assertEqual(
                {item.name for item in destination.iterdir()},
                {
                    "review-store-catalog.json",
                    "review-store-catalog-entries.json",
                    "review-store-catalog-operations.json",
                },
            )
            loaded = load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
                destination
            )
            self.assertEqual(loaded.to_dict(), catalog.to_dict())
            self.assertEqual(loaded.content_address, catalog.content_address)

    def test_catalog_write_requires_explicit_overwrite(self) -> None:
        catalog = self._ready()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "catalog"
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
                catalog, destination
            )
            with self.assertRaises(ValidationError):
                write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
                    catalog, destination
                )
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
                catalog, destination, overwrite=True
            )

    def test_catalog_load_rejects_missing_extra_and_symlink_artifacts(self) -> None:
        catalog = self._ready()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "catalog"
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
                catalog, destination
            )
            (destination / "extra.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
                    destination
                )
            (destination / "extra.json").unlink()
            (destination / "review-store-catalog-entries.json").unlink()
            with self.assertRaises(ValidationError):
                load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
                    destination
                )

    def test_catalog_load_rejects_manifest_tampering(self) -> None:
        catalog = self._ready()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "catalog"
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
                catalog, destination
            )
            manifest = json.loads(
                (
                    destination
                    / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MANIFEST
                ).read_text(encoding="utf-8")
            )
            manifest["entry_count"] = 99
            (
                destination
                / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MANIFEST
            ).write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(ValidationError):
                load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
                    destination
                )

    def test_catalog_load_from_directory_is_path_free(self) -> None:
        catalog = self._ready()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "catalog"
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
                catalog, destination
            )
            loaded = load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
                destination
            )
            self.assertNotIn(str(destination), json.dumps(loaded.to_dict()))
            self.assertEqual(loaded.entry_count, 2)

    def test_catalog_exports_are_deterministic(self) -> None:
        catalog = self._ready()
        first = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_json(
            catalog
        )
        self.assertEqual(
            first,
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_json(
                catalog
            ),
        )
        self.assertEqual(json.loads(first)["content_address"], catalog.content_address)
        rows = list(
            csv.DictReader(
                module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_csv(
                    catalog
                ).splitlines()
            )
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["entry_count"], "2")
        markdown = render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_markdown(
            catalog
        )
        self.assertIn("Durable Review-Store Catalog", markdown)
        self.assertIn("alpha", markdown)

    def test_catalog_query_resources_filters_and_receipts(self) -> None:
        catalog = self._ready()
        result = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
            catalog, resource="entries", store_id="beta", accepted=True, release_ready=True, limit=1
        )
        self.assertTrue(result["accepted"])
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["returned"], 1)
        self.assertTrue(
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_query(
                result
            )
        )
        self.assertIn(
            "beta",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_query_json(
                result
            ),
        )
        self.assertIn(
            "store_id",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_query_csv(
                result
            ).splitlines()[0],
        )
        self.assertIn(
            "Review-Store Catalog Query",
            render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_query_markdown(
                result
            ),
        )

    def test_catalog_query_resources_include_operations_checks_and_summary(self) -> None:
        catalog = self._ready()
        for resource, expected in (("summary", 1), ("operations", 3), ("checks", 8)):
            result = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
                catalog, resource=resource
            )
            self.assertEqual(result["total"], expected)
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
                catalog, resource="entries", limit=0
            )
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
                catalog, resource="not-a-resource"
            )

    def test_catalog_query_rejects_tampered_receipt(self) -> None:
        result = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
            self._ready(), resource="entries"
        )
        result["total"] = 99
        self.assertFalse(
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_query(
                result
            )
        )

    def test_catalog_runtime_closes_ready_catalog(self) -> None:
        runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime(
            self._ready()
        )
        self.assertEqual(runtime.state, "completed")
        self.assertTrue(runtime.accepted)
        self.assertTrue(runtime.release_ready)
        self.assertEqual(runtime.completed_count, 8)
        self.assertEqual(runtime.blocked_count, 0)
        self.assertEqual(runtime.skipped_count, 0)
        self.assertTrue(
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime(
                runtime
            )
        )
        self.assertEqual(
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime(
                runtime, state="completed"
            )["total"],
            8,
        )

    def test_catalog_runtime_blocks_empty_and_held_catalogs(self) -> None:
        empty_runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime(
            self._catalog()
        )
        self.assertEqual(empty_runtime.state, "blocked")
        self.assertFalse(empty_runtime.accepted)
        held_runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime(
            self._catalog(self._store("held", state="held", release_ready=False))
        )
        self.assertEqual(held_runtime.state, "blocked")
        self.assertFalse(held_runtime.release_ready)
        self.assertEqual(held_runtime.blocked_count, 1)
        self.assertEqual(held_runtime.skipped_count, 1)

    def test_catalog_runtime_exports_and_query_receipts_are_stable(self) -> None:
        runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime(
            self._ready()
        )
        self.assertEqual(
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_json(
                runtime
            ),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_json(
                runtime
            ),
        )
        self.assertEqual(
            len(
                module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_csv(
                    runtime
                ).splitlines()
            ),
            9,
        )
        self.assertIn(
            "Review-Store Catalog Runtime",
            render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_markdown(
                runtime
            ),
        )
        self.assertIn(
            "stage_count",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_schema(),
        )
        self.assertIn(
            "run",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_capabilities()[
                "operations"
            ],
        )
        self.assertIn(
            "query",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_query_capabilities()[
                "operations"
            ],
        )

    def test_catalog_runtime_from_directory_rehydrates(self) -> None:
        catalog = self._ready()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "catalog"
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
                catalog, destination
            )
            runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime(
                load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
                    destination
                )
            )
            self.assertTrue(runtime.accepted)

    def test_federation_selects_ready_members_and_closes_policy(self) -> None:
        federation = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation(
            self._ready(), minimum_members=2, minimum_ready=2
        )
        self.assertEqual(federation.state, "ready")
        self.assertTrue(federation.accepted)
        self.assertTrue(federation.release_ready)
        self.assertEqual(federation.member_count, 2)
        self.assertEqual(federation.ready_count, 2)
        self.assertEqual(federation.distinct_window_count, 1)
        self.assertEqual(federation.distinct_ledger_count, 2)
        self.assertTrue(all(check.passed for check in federation.checks))

    def test_federation_filters_window_and_store_selection(self) -> None:
        catalog = self._catalog(
            self._store("alpha"), self._store("beta", window_address="window:two")
        )
        federation = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation(
            catalog,
            selected_window_address="window:one",
            store_ids=("alpha",),
            minimum_members=1,
            minimum_ready=1,
        )
        self.assertEqual(federation.member_count, 1)
        self.assertEqual(federation.members[0].store_id, "alpha")
        self.assertTrue(federation.release_ready)

    def test_federation_mixed_window_and_unknown_selection_fail_closed(self) -> None:
        catalog = self._catalog(
            self._store("alpha"), self._store("beta", window_address="window:two")
        )
        mixed = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation(
            catalog,
            store_ids=("alpha", "beta"),
            require_same_window=False,
            minimum_members=2,
            minimum_ready=2,
        )
        self.assertEqual(mixed.state, "mixed")
        self.assertTrue(mixed.accepted)
        self.assertFalse(mixed.release_ready)
        blocked = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation(
            catalog, store_ids=("missing",), minimum_members=1, minimum_ready=1
        )
        self.assertEqual(blocked.state, "blocked")
        self.assertFalse(blocked.accepted)
        self.assertFalse(
            next(check for check in blocked.checks if check.kind == "known-store-selection").passed
        )

    def test_federation_holds_or_blocks_member_states(self) -> None:
        held = self._catalog(self._store("held", state="held", release_ready=False))
        held_federation = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation(
            held
        )
        self.assertEqual(held_federation.state, "held")
        self.assertTrue(held_federation.accepted)
        self.assertFalse(held_federation.release_ready)
        blocked = self._catalog(
            self._store("blocked", state="blocked", release_ready=False, accepted=False)
        )
        blocked_federation = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation(
            blocked
        )
        self.assertEqual(blocked_federation.state, "blocked")
        self.assertFalse(blocked_federation.accepted)

    def test_federation_query_and_exports_are_addressed(self) -> None:
        federation = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation(
            self._ready()
        )
        for resource, expected in (("summary", 1), ("members", 2), ("checks", 9)):
            result = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation(
                federation, resource=resource
            )
            self.assertEqual(result["total"], expected)
            self.assertIn("query_address", result)
        self.assertIn(
            "Federation",
            render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_markdown(
                federation
            ),
        )
        self.assertEqual(
            len(
                module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_csv(
                    federation
                ).splitlines()
            ),
            3,
        )
        self.assertIn(
            "federation_id",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_json(
                federation
            ),
        )
        self.assertIn(
            "federate",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_capabilities()[
                "operations"
            ],
        )
        self.assertIn(
            "members",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_schema()[
                "resources"
            ],
        )
        self.assertIn(
            "passed",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_query_schema()[
                "filters"
            ],
        )
        self.assertIn(
            "query",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_query_capabilities()[
                "operations"
            ],
        )

    def test_federation_from_directory_rehydrates(self) -> None:
        catalog = self._ready()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "catalog"
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
                catalog, destination
            )
            federation = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_from_directory(
                destination
            )
            self.assertTrue(federation.release_ready)

    def test_catalog_diff_exact_append_only_and_divergent_states(self) -> None:
        base = self._catalog(self._store("alpha"), catalog_id="same")
        exact = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff(
            base, base
        )
        self.assertEqual(exact.state, "exact")
        self.assertTrue(exact.append_only)
        self.assertEqual(exact.unchanged_count, 1)
        extended = append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
            base, [self._store("beta")]
        )
        append_only = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff(
            base, extended
        )
        self.assertEqual(append_only.state, "append_only")
        self.assertTrue(append_only.append_only)
        self.assertEqual(append_only.added_count, 1)
        changed = self._catalog(
            self._store("alpha", state="held", release_ready=False), catalog_id="same"
        )
        divergent = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff(
            base, changed
        )
        self.assertEqual(divergent.state, "divergent")
        self.assertFalse(divergent.append_only)
        self.assertEqual(divergent.changed_count, 1)

    def test_catalog_diff_detects_removed_members(self) -> None:
        left = self._catalog(self._store("alpha"), self._store("beta"))
        right = self._catalog(self._store("alpha"))
        diff = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff(
            left, right
        )
        self.assertEqual(diff.removed_count, 1)
        self.assertEqual(diff.state, "divergent")
        self.assertFalse(diff.append_only)

    def test_catalog_diff_query_and_exports_are_stable(self) -> None:
        base = self._catalog(self._store("alpha"))
        extended = append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
            base, [self._store("beta")]
        )
        diff = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff(
            base, extended
        )
        result = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff(
            diff, action="added"
        )
        self.assertEqual(result["total"], 1)
        self.assertIn(
            "beta",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_json(
                diff
            ),
        )
        self.assertEqual(
            len(
                module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_csv(
                    diff
                ).splitlines()
            ),
            3,
        )
        self.assertIn(
            "Catalog Diff",
            render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_markdown(
                diff
            ),
        )
        self.assertIn(
            "changed",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_schema()[
                "actions"
            ],
        )
        self.assertIn(
            "actions",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_query_schema()[
                "resource"
            ],
        )
        self.assertIn(
            "compare",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_capabilities()[
                "operations"
            ],
        )

    def test_catalog_diff_from_directories_rehydrates(self) -> None:
        left = self._catalog(self._store("alpha"))
        right = append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
            left, [self._store("beta")]
        )
        with tempfile.TemporaryDirectory() as root:
            left_path = Path(root) / "left"
            right_path = Path(root) / "right"
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
                left, left_path
            )
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
                right, right_path
            )
            diff = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_from_directories(
                left_path, right_path
            )
            self.assertEqual(diff.state, "append_only")

    def test_schemas_and_capabilities_remain_identity_free(self) -> None:
        forbidden = {
            "agent",
            "assistant",
            "author",
            "email",
            "language",
            "model",
            "private",
            "secret",
            "token",
            "user",
        }

        def walk(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    self.assertNotIn(str(key).casefold(), forbidden)
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        projections = (
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_schema(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_capabilities(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_query_schema(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_query_capabilities(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_schema(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_capabilities(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_query_schema(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime_query_capabilities(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_schema(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_capabilities(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_query_schema(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_query_capabilities(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_schema(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_capabilities(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_diff_query_schema(),
        )
        for projection in projections:
            walk(projection)


if __name__ == "__main__":
    unittest.main()
