"""Deep contract, failure, persistence, and public-surface tests for replication."""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread
from urllib.parse import urlencode

from glio_noncode import (
    module_workbench_execution_packet_archive_store_replication_runtime_capabilities,
    module_workbench_execution_packet_archive_store_replication_runtime_schema,
)
from glio_noncode.api import create_server
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
    load_module_workbench_execution_packet_archive_store,
    write_module_workbench_execution_packet_archive_store,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication import (
    apply_module_workbench_execution_packet_archive_store_replication,
    apply_module_workbench_execution_packet_archive_store_replication_from_directories,
    build_module_workbench_execution_packet_archive_store_promotion,
    build_module_workbench_execution_packet_archive_store_replication,
    load_module_workbench_execution_packet_archive_store_replication_inputs,
    module_workbench_execution_packet_archive_store_promotion_json,
    module_workbench_execution_packet_archive_store_replication_csv,
    module_workbench_execution_packet_archive_store_replication_from_mapping,
    module_workbench_execution_packet_archive_store_replication_json,
    render_module_workbench_execution_packet_archive_store_replication_markdown,
    verify_module_workbench_execution_packet_archive_store_promotion,
    verify_module_workbench_execution_packet_archive_store_replication,
    verify_module_workbench_execution_packet_archive_store_replication_receipt,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_contracts import (
    ModuleWorkbenchExecutionPacketArchiveStorePromotionState,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationEntryAction,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationOperationAction,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceiptState,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationState,
    module_workbench_execution_packet_archive_store_replication_capabilities,
    module_workbench_execution_packet_archive_store_replication_schema,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_query import (
    module_workbench_execution_packet_archive_store_replication_query_capabilities,
    module_workbench_execution_packet_archive_store_replication_query_csv,
    module_workbench_execution_packet_archive_store_replication_query_json,
    module_workbench_execution_packet_archive_store_replication_query_schema,
    query_module_workbench_execution_packet_archive_store_promotion,
    query_module_workbench_execution_packet_archive_store_replication,
    query_module_workbench_execution_packet_archive_store_replication_receipt,
    render_module_workbench_execution_packet_archive_store_replication_query_markdown,
    verify_module_workbench_execution_packet_archive_store_replication_query,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_runtime import (
    module_workbench_execution_packet_archive_store_replication_runtime_csv,
    module_workbench_execution_packet_archive_store_replication_runtime_json,
    query_module_workbench_execution_packet_archive_store_replication_runtime,
    run_module_workbench_execution_packet_archive_store_replication_runtime,
    verify_module_workbench_execution_packet_archive_store_replication_runtime,
)
from tests.test_module_workbench_execution import ModuleWorkbenchExecutionFixture


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationTests(unittest.TestCase):
    """Exercise the entire offline replication boundary."""

    def setUp(self) -> None:
        self.fixture = ModuleWorkbenchExecutionFixture()
        self.fixture.setUp()

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def archive(self, packet_id: str, archive_id: str):
        packet = build_module_workbench_execution_packet(self.fixture.report(), packet_id=packet_id)
        return build_module_workbench_execution_packet_archive(packet, archive_id=archive_id)

    def store(self, *archives, store_id: str = "replication-store"):
        return build_module_workbench_execution_packet_archive_store(
            archives or (self.archive("base", "base"),), store_id=store_id
        )

    def test_exact_match_is_a_verified_noop(self) -> None:
        store = self.store()
        plan = build_module_workbench_execution_packet_archive_store_replication(store, store)
        self.assertEqual(
            plan.state, ModuleWorkbenchExecutionPacketArchiveStoreReplicationState.MATCHED
        )
        self.assertTrue(plan.accepted)
        self.assertFalse(plan.apply_allowed)
        self.assertEqual(plan.object_copy_count, 0)
        self.assertEqual(plan.object_reuse_count, 1)
        self.assertEqual(plan.operation_copy_count, 0)
        self.assertEqual(plan.operation_reuse_count, 1)
        self.assertEqual(plan.required_byte_count, 0)
        verify_module_workbench_execution_packet_archive_store_replication(plan)

    def test_append_only_extension_plans_object_and_operation_copy(self) -> None:
        base_archive = self.archive("base", "base")
        next_archive = self.archive("next", "next")
        target = self.store(base_archive)
        source = append_module_workbench_execution_packet_archive_store(
            target, next_archive, operation_id="next-operation"
        )
        plan = build_module_workbench_execution_packet_archive_store_replication(source, target)
        self.assertEqual(
            plan.state, ModuleWorkbenchExecutionPacketArchiveStoreReplicationState.EXTENDED
        )
        self.assertTrue(plan.accepted)
        self.assertTrue(plan.apply_allowed)
        self.assertEqual(plan.object_copy_count, 1)
        self.assertEqual(plan.object_reuse_count, 1)
        self.assertEqual(plan.operation_copy_count, 1)
        self.assertEqual(plan.operation_reuse_count, 1)
        self.assertEqual(
            plan.entries[0].action,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationEntryAction.REUSE,
        )
        self.assertEqual(
            plan.entries[1].action,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationEntryAction.COPY,
        )
        self.assertEqual(
            plan.operations[0].action,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationOperationAction.REUSE,
        )
        self.assertEqual(
            plan.operations[1].action,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationOperationAction.COPY,
        )
        self.assertEqual(plan.required_byte_count, next_archive.archive_bytes.__len__())
        self.assertAlmostEqual(
            plan.transfer_ratio, plan.required_byte_count / source.total_byte_count
        )

    def test_duplicate_registration_requires_only_journal_copy(self) -> None:
        archive = self.archive("base", "base")
        target = self.store(archive)
        source = append_module_workbench_execution_packet_archive_store(
            target, archive, operation_id="duplicate-registration"
        )
        plan = build_module_workbench_execution_packet_archive_store_replication(source, target)
        self.assertTrue(plan.accepted)
        self.assertEqual(plan.object_copy_count, 0)
        self.assertEqual(plan.object_reuse_count, 1)
        self.assertEqual(plan.operation_copy_count, 1)
        self.assertEqual(plan.required_byte_count, 0)

    def test_divergent_journal_is_fail_closed(self) -> None:
        source = self.store(self.archive("source", "source"))
        target = self.store(self.archive("target", "target"))
        plan = build_module_workbench_execution_packet_archive_store_replication(source, target)
        self.assertEqual(
            plan.state, ModuleWorkbenchExecutionPacketArchiveStoreReplicationState.DIVERGED
        )
        self.assertFalse(plan.accepted)
        self.assertFalse(plan.apply_allowed)
        self.assertTrue(any(not check.passed for check in plan.checks))
        self.assertIn("blocked", plan.detail)

    def test_foreign_store_identity_is_blocked_even_with_matching_payload(self) -> None:
        source = self.store(store_id="source-store")
        target = self.store(store_id="target-store")
        plan = build_module_workbench_execution_packet_archive_store_replication(source, target)
        self.assertFalse(plan.accepted)
        self.assertEqual(
            plan.state, ModuleWorkbenchExecutionPacketArchiveStoreReplicationState.DIVERGED
        )
        identity = next(
            check for check in plan.checks if check.detail.startswith("source and target store IDs")
        )
        self.assertFalse(identity.passed)

    def test_expected_head_guard_is_part_of_plan_address(self) -> None:
        target = self.store(self.archive("base", "base"))
        source = append_module_workbench_execution_packet_archive_store(
            target, self.archive("next", "next"), operation_id="next"
        )
        accepted = build_module_workbench_execution_packet_archive_store_replication(
            source, target, expected_target_head_address=target.head_address
        )
        blocked = build_module_workbench_execution_packet_archive_store_replication(
            source, target, expected_target_head_address="wrong:head"
        )
        self.assertTrue(accepted.accepted)
        self.assertFalse(blocked.accepted)
        self.assertNotEqual(accepted.content_address, blocked.content_address)
        self.assertTrue(
            any(check.detail.startswith("target head changed") for check in blocked.checks)
        )

    def test_plan_mapping_round_trip_preserves_nested_addresses(self) -> None:
        target = self.store(self.archive("base", "base"))
        source = append_module_workbench_execution_packet_archive_store(
            target, self.archive("next", "next"), operation_id="next"
        )
        plan = build_module_workbench_execution_packet_archive_store_replication(source, target)
        restored = module_workbench_execution_packet_archive_store_replication_from_mapping(
            plan.to_dict()
        )
        self.assertEqual(restored, plan)
        self.assertEqual(
            module_workbench_execution_packet_archive_store_replication_json(plan),
            module_workbench_execution_packet_archive_store_replication_json(restored),
        )

    def test_apply_writes_verified_source_boundary_and_is_idempotent(self) -> None:
        target = self.store(self.archive("base", "base"))
        source = append_module_workbench_execution_packet_archive_store(
            target, self.archive("next", "next"), operation_id="next"
        )
        plan = build_module_workbench_execution_packet_archive_store_replication(
            source, target, expected_target_head_address=target.head_address
        )
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "target"
            write_module_workbench_execution_packet_archive_store(
                target, destination, allow_existing=False
            )
            receipt = apply_module_workbench_execution_packet_archive_store_replication(
                plan,
                source,
                target,
                destination=destination,
                expected_target_head_address=target.head_address,
                allow_existing=True,
            )
            self.assertEqual(
                receipt.state,
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceiptState.APPLIED,
            )
            self.assertTrue(receipt.accepted)
            self.assertEqual(receipt.after_target_address, source.content_address)
            self.assertEqual(
                load_module_workbench_execution_packet_archive_store(destination), source
            )
            verify_module_workbench_execution_packet_archive_store_replication_receipt(receipt)
            same_plan = build_module_workbench_execution_packet_archive_store_replication(
                source, source
            )
            noop = apply_module_workbench_execution_packet_archive_store_replication(
                same_plan, source, source, destination=destination, allow_existing=True
            )
            self.assertEqual(
                noop.state, ModuleWorkbenchExecutionPacketArchiveStoreReplicationReceiptState.NOOP
            )
            self.assertEqual(noop.after_target_address, source.content_address)

    def test_apply_rejects_stale_plan_before_writing(self) -> None:
        target = self.store(self.archive("base", "base"))
        source = append_module_workbench_execution_packet_archive_store(
            target, self.archive("next", "next"), operation_id="next"
        )
        plan = build_module_workbench_execution_packet_archive_store_replication(
            source, target, expected_target_head_address=target.head_address
        )
        changed_target = append_module_workbench_execution_packet_archive_store(
            target, self.archive("changed", "changed"), operation_id="changed"
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValidationError):
                apply_module_workbench_execution_packet_archive_store_replication(
                    plan,
                    source,
                    changed_target,
                    destination=Path(directory) / "target",
                    expected_target_head_address=target.head_address,
                )

    def test_directory_helpers_keep_locations_out_of_public_receipts(self) -> None:
        target = self.store(self.archive("base", "base"))
        source = append_module_workbench_execution_packet_archive_store(
            target, self.archive("next", "next"), operation_id="next"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_dir = root / "source"
            target_dir = root / "target"
            destination = root / "result"
            write_module_workbench_execution_packet_archive_store(source, source_dir)
            write_module_workbench_execution_packet_archive_store(target, target_dir)
            plan = load_module_workbench_execution_packet_archive_store_replication_inputs(
                source_dir, target_dir, expected_target_head_address=target.head_address
            )
            receipt = (
                apply_module_workbench_execution_packet_archive_store_replication_from_directories(
                    source_dir,
                    target_dir,
                    destination=destination,
                    expected_target_head_address=target.head_address,
                )
            )
            text = module_workbench_execution_packet_archive_store_replication_json(plan) + str(
                receipt.to_dict()
            )
            self.assertNotIn(str(root), text)
            self.assertNotIn("source_dir", text)
            self.assertEqual(
                load_module_workbench_execution_packet_archive_store(destination), source
            )

    def test_promotion_holds_until_extension_is_applied(self) -> None:
        target = self.store(self.archive("base", "base"))
        source = append_module_workbench_execution_packet_archive_store(
            target, self.archive("next", "next"), operation_id="next"
        )
        plan = build_module_workbench_execution_packet_archive_store_replication(source, target)
        held = build_module_workbench_execution_packet_archive_store_promotion(plan)
        self.assertEqual(held.state, ModuleWorkbenchExecutionPacketArchiveStorePromotionState.HOLD)
        self.assertFalse(held.accepted)
        with tempfile.TemporaryDirectory() as directory:
            receipt = apply_module_workbench_execution_packet_archive_store_replication(
                plan, source, target, destination=Path(directory) / "target"
            )
            promoted = build_module_workbench_execution_packet_archive_store_promotion(
                plan, receipt
            )
            self.assertEqual(
                promoted.state, ModuleWorkbenchExecutionPacketArchiveStorePromotionState.PROMOTABLE
            )
            self.assertTrue(promoted.release_allowed)
            verify_module_workbench_execution_packet_archive_store_promotion(promoted)

    def test_blocked_plan_produces_blocked_promotion(self) -> None:
        source = self.store(self.archive("source", "source"))
        target = self.store(self.archive("target", "target"))
        plan = build_module_workbench_execution_packet_archive_store_replication(source, target)
        promotion = build_module_workbench_execution_packet_archive_store_promotion(plan)
        self.assertEqual(
            promotion.state, ModuleWorkbenchExecutionPacketArchiveStorePromotionState.BLOCKED
        )
        self.assertFalse(promotion.accepted)

    def test_plan_exports_are_stable_and_identity_free(self) -> None:
        store = self.store()
        plan = build_module_workbench_execution_packet_archive_store_replication(store, store)
        output = (
            module_workbench_execution_packet_archive_store_replication_json(plan)
            + module_workbench_execution_packet_archive_store_replication_csv(plan)
            + render_module_workbench_execution_packet_archive_store_replication_markdown(plan)
        )
        self.assertIn("# Archive Store Replication Plan", output)
        self.assertIn("resource,ordinal,address", output)
        for forbidden in ('"agent"', '"private"', '"language"', '"path"', '"timestamp"'):
            self.assertNotIn(forbidden, output)
        promotion = build_module_workbench_execution_packet_archive_store_promotion(plan)
        self.assertNotIn(
            '"path"', module_workbench_execution_packet_archive_store_promotion_json(promotion)
        )

    def test_queries_support_resource_filters_and_address_verification(self) -> None:
        target = self.store(self.archive("base", "base"))
        source = append_module_workbench_execution_packet_archive_store(
            target, self.archive("next", "next"), operation_id="next"
        )
        plan = build_module_workbench_execution_packet_archive_store_replication(source, target)
        summary = query_module_workbench_execution_packet_archive_store_replication(plan)
        copies = query_module_workbench_execution_packet_archive_store_replication(
            plan, resource="entries", action="copy", offset=0, limit=1
        )
        checks = query_module_workbench_execution_packet_archive_store_replication(
            plan, resource="checks", accepted=True, limit=512
        )
        self.assertEqual(summary["total"], 1)
        self.assertEqual(copies["total"], 1)
        self.assertGreaterEqual(checks["total"], 1)
        verify_module_workbench_execution_packet_archive_store_replication_query(summary)
        verify_module_workbench_execution_packet_archive_store_replication_query(copies)
        self.assertIn(
            "# Archive Store Replication Query",
            render_module_workbench_execution_packet_archive_store_replication_query_markdown(
                copies
            ),
        )
        self.assertIn(
            "resource,ordinal,address",
            module_workbench_execution_packet_archive_store_replication_query_csv(copies),
        )
        self.assertEqual(
            module_workbench_execution_packet_archive_store_replication_query_json(summary),
            module_workbench_execution_packet_archive_store_replication_query_json(summary),
        )
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store_replication(plan, limit=513)

    def test_receipt_and_promotion_queries_are_bounded(self) -> None:
        target = self.store(self.archive("base", "base"))
        source = append_module_workbench_execution_packet_archive_store(
            target, self.archive("next", "next"), operation_id="next"
        )
        plan = build_module_workbench_execution_packet_archive_store_replication(source, target)
        with tempfile.TemporaryDirectory() as directory:
            receipt = apply_module_workbench_execution_packet_archive_store_replication(
                plan, source, target, destination=Path(directory) / "target"
            )
            promotion = build_module_workbench_execution_packet_archive_store_promotion(
                plan, receipt
            )
            receipt_page = (
                query_module_workbench_execution_packet_archive_store_replication_receipt(receipt)
            )
            promotion_page = query_module_workbench_execution_packet_archive_store_promotion(
                promotion, resource="checks", passed=True
            )
            self.assertEqual(receipt_page["total"], 1)
            self.assertGreaterEqual(promotion_page["total"], 1)
            with self.assertRaises(ValidationError):
                query_module_workbench_execution_packet_archive_store_promotion(
                    promotion, resource="checks", limit=513
                )

    def test_runtime_plan_only_is_accepted_and_apply_is_explicitly_skipped(self) -> None:
        target = self.store(self.archive("base", "base"))
        source = append_module_workbench_execution_packet_archive_store(
            target, self.archive("next", "next"), operation_id="next"
        )
        runtime = run_module_workbench_execution_packet_archive_store_replication_runtime(
            source, target, apply=False
        )
        self.assertTrue(runtime.accepted)
        self.assertFalse(runtime.apply_requested)
        self.assertEqual(runtime.skipped_count, 1)
        self.assertIsNone(runtime.receipt_address)
        verify_module_workbench_execution_packet_archive_store_replication_runtime(runtime)

    def test_runtime_apply_promotes_and_reloads_result(self) -> None:
        target = self.store(self.archive("base", "base"))
        source = append_module_workbench_execution_packet_archive_store(
            target, self.archive("next", "next"), operation_id="next"
        )
        with tempfile.TemporaryDirectory() as directory:
            runtime = run_module_workbench_execution_packet_archive_store_replication_runtime(
                source,
                target,
                apply=True,
                destination=Path(directory) / "target",
                allow_existing=False,
            )
            self.assertTrue(runtime.accepted)
            self.assertEqual(runtime.completed_count, runtime.stage_count)
            self.assertIsNotNone(runtime.receipt_address)
            self.assertIn(
                "replication",
                module_workbench_execution_packet_archive_store_replication_runtime_json(runtime),
            )
            self.assertIn(
                "ordinal,kind,state",
                module_workbench_execution_packet_archive_store_replication_runtime_csv(runtime),
            )
            page = query_module_workbench_execution_packet_archive_store_replication_runtime(
                runtime, resource="stages", kind="apply"
            )
            self.assertEqual(page["total"], 1)

    def test_runtime_blocks_requested_apply_without_destination(self) -> None:
        store = self.store()
        runtime = run_module_workbench_execution_packet_archive_store_replication_runtime(
            store, store, apply=True
        )
        self.assertFalse(runtime.accepted)
        self.assertEqual(runtime.blocked_count, 1)
        self.assertIn("blocked", runtime.detail)

    def test_runtime_schema_capabilities_and_plan_schema_are_explicit(self) -> None:
        schema = module_workbench_execution_packet_archive_store_replication_schema()
        query_schema = module_workbench_execution_packet_archive_store_replication_query_schema()
        runtime_schema = (
            module_workbench_execution_packet_archive_store_replication_runtime_schema()
        )
        capabilities = module_workbench_execution_packet_archive_store_replication_capabilities()
        query_capabilities = (
            module_workbench_execution_packet_archive_store_replication_query_capabilities()
        )
        runtime_capabilities = (
            module_workbench_execution_packet_archive_store_replication_runtime_capabilities()
        )
        self.assertEqual(schema["resources"][0], "summary")
        self.assertIn("expected_head", schema["guards"])
        self.assertIn("entries", query_schema["resources"])
        self.assertIn("apply_stage", runtime_capabilities["operations"])
        self.assertIn("no_filesystem_paths_in_public_receipts", capabilities["guarantees"])
        self.assertIn("verify_query_address", query_capabilities["operations"])
        self.assertTrue(runtime_schema["path_free"])

    def test_tampered_plan_and_nested_receipts_fail_closed(self) -> None:
        store = self.store()
        plan = build_module_workbench_execution_packet_archive_store_replication(store, store)
        with self.assertRaises(ValidationError):
            verify_module_workbench_execution_packet_archive_store_replication(
                replace(plan, detail="tampered")
            )
        with tempfile.TemporaryDirectory() as directory:
            receipt = apply_module_workbench_execution_packet_archive_store_replication(
                plan, store, store, destination=Path(directory) / "target"
            )
            with self.assertRaises(ValidationError):
                verify_module_workbench_execution_packet_archive_store_replication_receipt(
                    replace(receipt, detail="tampered")
                )

    def test_api_exposes_plan_query_promotion_runtime_and_contract_routes(self) -> None:
        target = self.store(self.archive("base", "base"))
        source = append_module_workbench_execution_packet_archive_store(
            target, self.archive("next", "next"), operation_id="next"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_dir = root / "source"
            target_dir = root / "target"
            write_module_workbench_execution_packet_archive_store(source, source_dir)
            write_module_workbench_execution_packet_archive_store(target, target_dir)
            server = create_server(host="127.0.0.1", port=0)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = HTTPConnection("127.0.0.1", server.server_port, timeout=30)

                def get(route: str) -> tuple[int, dict[str, object]]:
                    connection.request("GET", route)
                    response = connection.getresponse()
                    import json

                    return response.status, json.loads(response.read().decode("utf-8"))

                for route, marker in (
                    (
                        "/v1/module-workbench/execution/packet/archive/store/replication/schema",
                        "guards",
                    ),
                    (
                        "/v1/module-workbench/execution/packet/archive/store/replication/capabilities",
                        "guarantees",
                    ),
                    (
                        "/v1/module-workbench/execution/packet/archive/store/replication/runtime/schema",
                        "stage_kinds",
                    ),
                    (
                        "/v1/module-workbench/execution/packet/archive/store/replication/runtime/capabilities",
                        "operations",
                    ),
                ):
                    status, payload = get(route)
                    self.assertEqual(status, 200)
                    self.assertIn(marker, payload)
                query = urlencode(
                    {
                        "source_directory": source_dir,
                        "target_directory": target_dir,
                        "resource": "entries",
                        "action": "copy",
                    }
                )
                status, payload = get(
                    "/v1/module-workbench/execution/packet/archive/store/replication/query?" + query
                )
                self.assertEqual(status, 200)
                self.assertEqual(payload["total"], 1)
                common = urlencode(
                    {
                        "source_directory": source_dir,
                        "target_directory": target_dir,
                    }
                )
                status, payload = get(
                    "/v1/module-workbench/execution/packet/archive/store/replication?" + common
                )
                self.assertEqual(status, 200)
                self.assertEqual(payload["state"], "extended")
                status, payload = get(
                    "/v1/module-workbench/execution/packet/archive/store/replication/promotion?"
                    + common
                )
                self.assertEqual(status, 422)
                self.assertEqual(payload["state"], "hold")
                status, payload = get(
                    "/v1/module-workbench/execution/packet/archive/store/replication/runtime?"
                    + common
                )
                self.assertEqual(status, 200)
                self.assertTrue(payload["accepted"])
                self.assertIsNone(payload["receipt_address"])
                for value in (payload,):
                    self.assertNotIn("path", value)
                    self.assertNotIn("agent", value)
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)


if __name__ == "__main__":
    unittest.main()
