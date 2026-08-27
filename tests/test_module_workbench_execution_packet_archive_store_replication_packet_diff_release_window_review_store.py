"""Deep regression coverage for durable release-window review stores."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.module_workbench_execution_packet import build_module_workbench_execution_packet
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
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_batch import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_batch,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store import (
    append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_decision,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store,
    load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_schema,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_markdown,
    replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store,
    write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_query_schema,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_schema,
    query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_markdown,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_contracts import (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiffState,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreOperationKind,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreState,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_query_schema,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_schema,
    query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_markdown,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_query import (
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_query_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_query_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_query_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_query_schema,
    query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_query_markdown,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_query,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime import (
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_query_schema,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_schema,
    query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_markdown,
    run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime,
)
from glio_noncode.serialization import canonical_json
from tests.test_module_workbench_execution import ModuleWorkbenchExecutionFixture


class DurableReviewStoreTests(unittest.TestCase):
    """Exercise creation, persistence, verification, replay, and projections."""

    def setUp(self) -> None:
        self.fixture = ModuleWorkbenchExecutionFixture()
        self.fixture.setUp()

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def _archive(self, archive_id: str):
        packet = build_module_workbench_execution_packet(
            self.fixture.report(), packet_id=archive_id
        )
        return build_module_workbench_execution_packet_archive(packet, archive_id=archive_id)

    def _packet(self, packet_id: str = "durable-store-packet"):
        base = self._archive("durable-base")
        next_archive = self._archive("durable-next")
        target = build_module_workbench_execution_packet_archive_store(
            (base,), store_id="durable-target"
        )
        source = append_module_workbench_execution_packet_archive_store(
            target, next_archive, operation_id="durable-next"
        )
        plan = build_module_workbench_execution_packet_archive_store_replication(source, target)
        packet, _ = build_module_workbench_execution_packet_archive_store_replication_packet(
            plan, packet_id=packet_id
        )
        return packet

    def _evidence(self, divergent: bool = False):
        left = self._packet("durable-left")
        right = self._packet("durable-right") if divergent else left
        diff = build_module_workbench_execution_packet_archive_store_replication_packet_diff(
            left, right
        )
        release = (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release(
                diff
            )
        )
        batch = build_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(
            (("durable", diff, release),), batch_id="durable-batch"
        )
        window = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
            batch, window_id="durable-window"
        )
        from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime import (
            run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime,
        )

        packet_runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime(
            batch, window_id=window.window_id
        )
        packet_assurance = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance(
            window, packet_runtime
        )
        return window, packet_assurance

    def _store(self, decisions=(), store_id="durable-store", divergent=False):
        window, packet_assurance = self._evidence(divergent=divergent)
        ledger = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review(
            window, packet_assurance, decisions=decisions, ledger_id=f"{store_id}:ledger"
        )
        return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
            ledger, store_id=store_id
        )

    def _ready_store(self, store_id="ready-store"):
        return self._store(
            (
                {
                    "entry_id": "promote",
                    "decision": "promote",
                    "rationale": "verified evidence is ready",
                },
            ),
            store_id=store_id,
        )

    def _held_store(self, store_id="held-store"):
        return self._store(
            (
                {
                    "entry_id": "hold",
                    "decision": "hold",
                    "rationale": "review is required",
                    "required_actions": ("inspect",),
                },
            ),
            store_id=store_id,
            divergent=True,
        )

    def test_ready_store_has_genesis_and_conserved_checks(self) -> None:
        store = self._ready_store()
        self.assertEqual(
            store.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreState.READY.value,
        )
        self.assertTrue(store.release_ready)
        self.assertTrue(store.accepted)
        self.assertTrue(store.append_only)
        self.assertEqual(store.entry_count, 1)
        self.assertEqual(store.operation_count, 1)
        self.assertEqual(
            store.operations[0].kind,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreOperationKind.GENESIS.value,
        )
        self.assertEqual(store.operations[0].output_address, store.ledger_address)
        self.assertEqual(store.head_address, store.ledger.head_address)
        self.assertEqual(store.check_count, len(store.checks))
        verification = verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
            store
        )
        self.assertTrue(verification.accepted)

    def test_empty_store_retains_genesis_but_is_not_accepted(self) -> None:
        store = self._store()
        self.assertEqual(
            store.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreState.EMPTY.value,
        )
        self.assertFalse(store.accepted)
        self.assertFalse(store.release_ready)
        self.assertIsNone(store.head_address)
        self.assertEqual(len(store.operations), 1)
        self.assertEqual(store.operations[0].kind, "genesis")

    def test_held_store_is_accepted_but_not_release_ready(self) -> None:
        store = self._held_store()
        self.assertEqual(
            store.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreState.HELD.value,
        )
        self.assertTrue(store.accepted)
        self.assertFalse(store.release_ready)
        self.assertGreater(store.entry_count, 0)

    def test_store_json_csv_markdown_are_stable(self) -> None:
        store = self._ready_store()
        first = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_json(
            store
        )
        second = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_json(
            store
        )
        self.assertEqual(first, second)
        self.assertEqual(json.loads(first)["content_address"], store.content_address)
        csv_text = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_csv(
            store
        )
        rows = list(csv.DictReader(csv_text.splitlines()))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["store_id"], store.store_id)
        markdown = render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_markdown(
            store
        )
        self.assertIn("Durable Release-Window Review Store", markdown)
        self.assertIn(store.content_address, markdown)

    def test_atomic_write_load_and_replay_preserve_exact_projection(self) -> None:
        store = self._ready_store()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "review-store"
            result = write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
                store, destination
            )
            self.assertEqual(result, destination)
            self.assertEqual(
                {item.name for item in destination.iterdir()},
                {"review-store.json", "review-ledger.json", "review-operations.json"},
            )
            loaded = load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
                destination
            )
            self.assertEqual(loaded.to_dict(), store.to_dict())
            self.assertEqual(loaded.ledger.to_dict(), store.ledger.to_dict())
            replay = replay_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
                loaded
            )
            self.assertEqual(replay.state, "matched")
            self.assertTrue(replay.accepted)

    def test_write_requires_explicit_overwrite(self) -> None:
        store = self._ready_store()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "review-store"
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
                store, destination
            )
            with self.assertRaises(ValidationError):
                write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
                    store, destination
                )
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
                store, destination, overwrite=True
            )
            self.assertTrue((destination / "review-store.json").is_file())

    def test_load_rejects_missing_extra_and_noncanonical_artifacts(self) -> None:
        store = self._ready_store()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "review-store"
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
                store, destination
            )
            (destination / "review-operations.json").unlink()
            with self.assertRaises(ValidationError):
                load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
                    destination
                )
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
                store, destination, overwrite=True
            )
            (destination / "extra.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
                    destination
                )
            (destination / "extra.json").unlink()
            (destination / "extra-directory").mkdir()
            with self.assertRaises(ValidationError):
                load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
                    destination
                )
            (destination / "extra-directory").rmdir()
            manifest = destination / "review-store.json"
            manifest.write_bytes(manifest.read_bytes() + b" ")
            with self.assertRaises(ValidationError):
                load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
                    destination
                )

    def test_load_rejects_manifest_and_ledger_tampering(self) -> None:
        store = self._ready_store()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "review-store"
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
                store, destination
            )
            ledger_path = destination / "review-ledger.json"
            body = json.loads(ledger_path.read_text(encoding="utf-8"))
            body["state"] = "hold"
            ledger_path.write_text(json.dumps(body, separators=(",", ":")), encoding="utf-8")
            with self.assertRaises(ValidationError):
                load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
                    destination
                )

    def test_query_exposes_bounded_store_resources(self) -> None:
        store = self._ready_store()
        for resource, expected in (
            ("summary", 1),
            ("operations", 1),
            ("checks", store.check_count),
            ("entries", 1),
        ):
            value = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
                store, resource=resource, limit=2
            )
            self.assertEqual(value["resource"], resource)
            self.assertEqual(value["total"], expected)
            self.assertLessEqual(len(value["items"]), 2)
            self.assertEqual(
                value["content_address"],
                query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
                    store, resource=resource, limit=2
                )["content_address"],
            )
            self.assertIsInstance(
                verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_query(
                    value
                ),
                dict,
            )

    def test_query_filters_and_exports_are_addressed(self) -> None:
        store = self._ready_store()
        operations = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
            store, resource="operations", kind="genesis", accepted=True
        )
        self.assertEqual(operations["total"], 1)
        checks = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
            store, resource="checks", passed=True, text="ledger"
        )
        self.assertGreaterEqual(checks["total"], 1)
        entries = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
            store, resource="entries", state="promoted"
        )
        self.assertEqual(entries["total"], 1)
        self.assertEqual(
            json.loads(
                module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_query_json(
                    entries
                )
            )["total"],
            1,
        )
        self.assertIn(
            "resource",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_query_csv(
                entries
            ).splitlines()[0],
        )
        self.assertIn(
            "Durable Release-Window Review Store Query",
            render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_query_markdown(
                entries
            ),
        )

    def test_query_rejects_unbounded_arguments(self) -> None:
        store = self._ready_store()
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
                store, limit=0
            )
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
                store, offset=-1
            )
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
                store, resource="unknown"
            )

    def test_runtime_completes_ready_store(self) -> None:
        store = self._ready_store()
        runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime(
            store
        )
        self.assertEqual(runtime.state, "completed")
        self.assertTrue(runtime.accepted)
        self.assertTrue(runtime.release_ready)
        self.assertEqual(runtime.stage_count, 8)
        self.assertEqual(runtime.completed_count, 8)
        self.assertEqual(runtime.blocked_count, 0)
        self.assertIs(
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime(
                runtime
            ),
            runtime,
        )
        self.assertEqual(len(runtime.to_dict()["stages"]), 8)
        self.assertEqual(
            len(
                module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_csv(
                    runtime
                ).splitlines()
            ),
            9,
        )
        self.assertIn(
            "Durable Release-Window Review Store Runtime",
            render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_markdown(
                runtime
            ),
        )
        self.assertEqual(
            json.loads(
                module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_json(
                    runtime
                )
            )["stage_count"],
            8,
        )

    def test_runtime_blocks_empty_store(self) -> None:
        runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime(
            self._store()
        )
        self.assertEqual(runtime.state, "blocked")
        self.assertFalse(runtime.accepted)
        self.assertFalse(runtime.release_ready)
        self.assertGreater(runtime.blocked_count, 0)

    def test_runtime_blocks_divergent_hydrated_ledger(self) -> None:
        store = self._ready_store()
        other = self._held_store("other-store")
        store.ledger = other.ledger
        runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime(
            store
        )
        self.assertEqual(runtime.state, "blocked")
        self.assertFalse(runtime.accepted)
        self.assertEqual(runtime.stages[2].kind, "verify_ledger")
        self.assertEqual(runtime.stages[2].state, "blocked")

    def test_runtime_query_and_schema_are_stable(self) -> None:
        runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime(
            self._ready_store()
        )
        result = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime(
            runtime, state="completed", accepted=True, limit=3
        )
        self.assertEqual(result["total"], 8)
        self.assertEqual(result["runtime"]["stage_count"], 8)
        self.assertEqual(
            len(
                module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_schema()[
                    "stages"
                ]
            ),
            8,
        )
        self.assertTrue(
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_query_schema()[
                "bounded"
            ]
        )
        self.assertTrue(
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_capabilities()[
                "fail_closed"
            ]
        )

    def test_assurance_passes_ready_store(self) -> None:
        assurance = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance(
            self._ready_store()
        )
        self.assertEqual(assurance.state, "passed")
        self.assertTrue(assurance.accepted)
        self.assertTrue(assurance.release_ready)
        self.assertEqual(assurance.finding_count, 8)
        self.assertEqual(assurance.blocker_count, 0)
        self.assertEqual(assurance.warning_count, 0)
        self.assertIs(
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance(
                assurance
            ),
            assurance,
        )
        self.assertEqual(
            json.loads(
                module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_json(
                    assurance
                )
            )["finding_count"],
            8,
        )
        self.assertEqual(
            len(
                module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_csv(
                    assurance
                ).splitlines()
            ),
            9,
        )
        self.assertIn(
            "Durable Release-Window Review Store Assurance",
            render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_markdown(
                assurance
            ),
        )

    def test_assurance_warns_on_held_store(self) -> None:
        assurance = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance(
            self._held_store()
        )
        self.assertEqual(assurance.state, "warning")
        self.assertTrue(assurance.accepted)
        self.assertFalse(assurance.release_ready)
        self.assertEqual(assurance.warning_count, 1)
        result = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance(
            assurance, severity="warning", passed=False
        )
        self.assertEqual(result["total"], 1)

    def test_assurance_blocks_empty_store(self) -> None:
        assurance = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance(
            self._store()
        )
        self.assertEqual(assurance.state, "blocked")
        self.assertFalse(assurance.accepted)
        self.assertEqual(assurance.blocker_count, 1)

    def test_assurance_detects_hydrated_ledger_divergence(self) -> None:
        store = self._ready_store()
        store.ledger = self._held_store("other-assurance-store").ledger
        assurance = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance(
            store
        )
        self.assertEqual(assurance.state, "blocked")
        self.assertFalse(assurance.accepted)
        self.assertGreaterEqual(assurance.blocker_count, 1)

    def test_store_diff_exact_and_append_only(self) -> None:
        ready = self._ready_store("same-store")
        exact = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff(
            ready, ready
        )
        self.assertEqual(
            exact.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreDiffState.EXACT.value,
        )
        self.assertTrue(exact.append_only)
        self.assertTrue(exact.accepted)
        empty = self._store(store_id="empty-for-diff")
        append = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff(
            empty, ready
        )
        self.assertEqual(append.state, "append_only")
        self.assertTrue(append.append_only)
        self.assertEqual(append.added_count, 1)
        self.assertEqual(append.removed_count, 0)

    def test_store_diff_detects_removed_and_changed_entries(self) -> None:
        ready = self._ready_store("left-diff")
        empty = self._store(store_id="right-empty")
        removed = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff(
            ready, empty
        )
        self.assertEqual(removed.state, "divergent")
        self.assertFalse(removed.accepted)
        self.assertEqual(removed.removed_count, 1)
        changed_left = self._store(
            ({"entry_id": "same", "decision": "promote", "rationale": "one"},),
            store_id="changed-left",
        )
        changed_right = self._store(
            ({"entry_id": "same", "decision": "promote", "rationale": "two"},),
            store_id="changed-right",
        )
        changed = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff(
            changed_left, changed_right
        )
        self.assertEqual(changed.state, "divergent")
        self.assertEqual(changed.changed_count, 1)
        self.assertFalse(changed.append_only)

    def test_store_diff_exports_and_query(self) -> None:
        left = self._store(store_id="diff-left")
        right = self._ready_store("diff-right")
        diff = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff(
            left, right
        )
        result = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff(
            diff, action="added", limit=10
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["diff"]["state"], "append_only")
        self.assertEqual(
            len(
                module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_csv(
                    diff
                ).splitlines()
            ),
            2,
        )
        self.assertEqual(
            json.loads(
                module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_json(
                    diff
                )
            )["added_count"],
            1,
        )
        self.assertIn(
            "Durable Release-Window Review Store Diff",
            render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_markdown(
                diff
            ),
        )
        self.assertTrue(
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_schema()[
                "identity_free"
            ]
        )
        self.assertTrue(
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_capabilities()[
                "append_only_proof"
            ]
        )
        self.assertTrue(
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_query_schema()[
                "bounded"
            ]
        )
        self.assertIs(
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff(
                diff
            ),
            diff,
        )

    def test_append_decision_uses_expected_head_guard(self) -> None:
        window, assurance = self._evidence()
        ledger = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review(
            window, assurance, decisions=(), ledger_id="append-ledger"
        )
        store = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
            ledger, store_id="append-store"
        )
        with self.assertRaises(ValidationError):
            append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_decision(
                store,
                ledger,
                window,
                assurance,
                entry_id="bad",
                decision="promote",
                rationale="wrong guard",
                expected_head_address="review:wrong",
            )
        updated = append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_decision(
            store,
            ledger,
            window,
            assurance,
            entry_id="promote",
            decision="promote",
            rationale="verified evidence is ready",
            expected_head_address=store.head_address,
        )
        self.assertEqual(updated.entry_count, 1)
        self.assertEqual(updated.operation_count, 2)
        self.assertEqual(updated.operations[-1].kind, "append")
        self.assertEqual(
            updated.operations[-1].previous_operation_address, store.operations[-1].content_address
        )
        self.assertTrue(updated.accepted)

    def test_contract_schemas_and_capabilities_are_identity_free(self) -> None:
        documents = [
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_schema(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_query_schema(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_schema(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_query_schema(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_schema(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_query_schema(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_schema(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_query_schema(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_query_capabilities(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_runtime_capabilities(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance_capabilities(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff_capabilities(),
        ]
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
                    yield from walk(item)
            elif isinstance(value, list):
                for item in value:
                    yield from walk(item)

        for document in documents:
            list(walk(document))
            self.assertTrue(document.get("identity_free", True))
            self.assertNotIn('"timestamp":', canonical_json(document).casefold())

    def test_store_query_limit_is_predictably_bounded(self) -> None:
        store = self._ready_store()
        value = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
            store, resource="checks", offset=1, limit=1
        )
        self.assertEqual(value["offset"], 1)
        self.assertEqual(value["limit"], 1)
        self.assertEqual(len(value["items"]), 1)
        value = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
            store, resource="checks", offset=1000, limit=1
        )
        self.assertEqual(value["items"], [])

    def test_assurance_query_rejects_invalid_filter(self) -> None:
        assurance = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance(
            self._ready_store()
        )
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance(
                assurance, severity="invalid"
            )
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_assurance(
                assurance, limit=0
            )

    def test_diff_requires_hydrated_ledgers(self) -> None:
        left = self._ready_store("left-unhydrated")
        right = self._ready_store("right-unhydrated")
        del left.ledger
        with self.assertRaises(ValidationError):
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_diff(
                left, right
            )

    def test_persisted_load_requires_canonical_operation_projection(self) -> None:
        store = self._ready_store()
        with tempfile.TemporaryDirectory() as root:
            destination = Path(root) / "review-store"
            write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
                store, destination
            )
            operations = destination / "review-operations.json"
            body = json.loads(operations.read_text(encoding="utf-8"))
            operations.write_text(json.dumps(body, indent=2), encoding="utf-8")
            with self.assertRaises(ValidationError):
                load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store(
                    destination
                )


if __name__ == "__main__":
    unittest.main()
