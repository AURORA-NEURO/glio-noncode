"""Deep tests for packet comparison, release gating, and diff runtime."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
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
    load_module_workbench_execution_packet_archive_store_replication_packet,
    write_module_workbench_execution_packet_archive_store_replication_packet,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release,
    load_module_workbench_execution_packet_archive_store_replication_packet_diff_inputs,
    module_workbench_execution_packet_archive_store_replication_packet_diff_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_schema_document,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_markdown,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_contracts import (  # noqa: E501
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseState,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffState,
    module_workbench_execution_packet_archive_store_replication_packet_diff_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_runtime_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_runtime_schema,
    module_workbench_execution_packet_archive_store_replication_packet_diff_schema,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_runtime import (  # noqa: E501
    module_workbench_execution_packet_archive_store_replication_packet_diff_runtime_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_runtime_json,
    query_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime,
    run_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_runtime import (
    run_module_workbench_execution_packet_archive_store_replication_runtime,
)
from glio_noncode.serialization import canonical_json
from tests.test_module_workbench_execution import ModuleWorkbenchExecutionFixture


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffTests(unittest.TestCase):
    """Exercise action accounting and release safety rules."""

    def setUp(self) -> None:
        self.fixture = ModuleWorkbenchExecutionFixture()
        self.fixture.setUp()

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def archive(self, packet_id: str, archive_id: str):
        packet = build_module_workbench_execution_packet(self.fixture.report(), packet_id=packet_id)
        return build_module_workbench_execution_packet_archive(packet, archive_id=archive_id)

    def stores(self):
        base = self.archive("base", "base")
        next_archive = self.archive("next", "next")
        target = build_module_workbench_execution_packet_archive_store((base,), store_id="target")
        source = append_module_workbench_execution_packet_archive_store(
            target, next_archive, operation_id="next-operation"
        )
        return source, target

    def packets(self):
        source, target = self.stores()
        plan = build_module_workbench_execution_packet_archive_store_replication(source, target)
        first, first_payloads = (
            build_module_workbench_execution_packet_archive_store_replication_packet(
                plan,
                packet_id="review-packet",
            )
        )
        return plan, first, first_payloads, source, target

    def test_identical_packet_boundaries_are_matched(self) -> None:
        _, packet, _, _, _ = self.packets()
        diff = build_module_workbench_execution_packet_archive_store_replication_packet_diff(
            packet, packet
        )
        self.assertEqual(
            diff.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffState.MATCHED,
        )
        self.assertTrue(diff.accepted)
        self.assertTrue(diff.release_allowed)
        self.assertEqual(diff.added_artifact_count, 0)
        self.assertEqual(diff.removed_artifact_count, 0)
        self.assertEqual(diff.changed_artifact_count, 0)
        self.assertEqual(diff.unchanged_artifact_count, diff.artifact_count)

    def test_runtime_artifacts_are_classified_as_an_extension(self) -> None:
        plan, packet, _, source, target = self.packets()
        runtime = run_module_workbench_execution_packet_archive_store_replication_runtime(
            source, target
        )
        candidate, payloads = (
            build_module_workbench_execution_packet_archive_store_replication_packet(
                plan,
                runtime=runtime,
                packet_id="review-packet",
            )
        )
        self.assertIn("artifacts/runtime.json", payloads)
        diff = build_module_workbench_execution_packet_archive_store_replication_packet_diff(
            packet, candidate
        )
        self.assertEqual(
            diff.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffState.EXTENDED,
        )
        self.assertTrue(diff.accepted)
        self.assertTrue(diff.release_allowed)
        self.assertEqual(diff.added_artifact_count, 2)
        self.assertEqual(diff.changed_artifact_count, 0)
        self.assertEqual(diff.removed_artifact_count, 0)
        self.assertEqual(diff.unchanged_artifact_count, 5)
        self.assertEqual(diff.artifact_count, 7)
        self.assertEqual(source.store_id, target.store_id)

    def test_packet_id_change_is_described_as_divergence(self) -> None:
        plan, packet, _, source, target = self.packets()
        candidate, _ = build_module_workbench_execution_packet_archive_store_replication_packet(
            plan,
            packet_id="different-packet",
        )
        self.assertNotEqual(packet.content_address, candidate.content_address)
        diff = build_module_workbench_execution_packet_archive_store_replication_packet_diff(
            packet, candidate
        )
        self.assertEqual(
            diff.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffState.DIVERGED,
        )
        self.assertTrue(diff.accepted)
        self.assertFalse(diff.release_allowed)
        self.assertEqual(diff.unchanged_artifact_count, diff.artifact_count)

    def test_changed_plan_produces_changed_artifact_actions(self) -> None:
        plan, packet, _, source, target = self.packets()
        changed_plan = build_module_workbench_execution_packet_archive_store_replication(
            source, target, replication_id="different-replication"
        )
        candidate, _ = build_module_workbench_execution_packet_archive_store_replication_packet(
            changed_plan,
            packet_id="review-packet",
        )
        diff = build_module_workbench_execution_packet_archive_store_replication_packet_diff(
            packet, candidate
        )
        self.assertEqual(
            diff.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffState.CHANGED,
        )
        self.assertTrue(diff.accepted)
        self.assertFalse(diff.release_allowed)
        self.assertGreater(diff.changed_artifact_count, 0)
        self.assertEqual(
            sum(
                item.action
                is ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffAction.CHANGED
                for item in diff.artifacts
            ),
            diff.changed_artifact_count,
        )
        self.assertEqual(plan.content_address, packet.plan_address)

    def test_release_promotes_match_and_extension(self) -> None:
        plan, packet, _, source, target = self.packets()
        matched = build_module_workbench_execution_packet_archive_store_replication_packet_diff(
            packet, packet
        )
        matched_release = (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release(
                matched
            )
        )
        self.assertEqual(
            matched_release.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseState.PROMOTABLE,
        )
        self.assertTrue(matched_release.accepted)
        runtime = run_module_workbench_execution_packet_archive_store_replication_runtime(
            source, target
        )
        candidate, _ = build_module_workbench_execution_packet_archive_store_replication_packet(
            plan, runtime=runtime, packet_id="review-packet"
        )
        extension = build_module_workbench_execution_packet_archive_store_replication_packet_diff(
            packet, candidate
        )
        extension_release = (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release(
                extension
            )
        )
        self.assertEqual(
            extension_release.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseState.PROMOTABLE,
        )
        self.assertTrue(extension_release.accepted)

    def test_release_holds_divergence_and_content_changes(self) -> None:
        plan, packet, _, source, target = self.packets()
        different_id, _ = build_module_workbench_execution_packet_archive_store_replication_packet(
            plan, packet_id="different"
        )
        diverged = build_module_workbench_execution_packet_archive_store_replication_packet_diff(
            packet, different_id
        )
        release = (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release(
                diverged
            )
        )
        self.assertEqual(
            release.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseState.HOLD,
        )
        self.assertFalse(release.accepted)
        changed_plan = build_module_workbench_execution_packet_archive_store_replication(
            source, target, replication_id="different"
        )
        changed_packet, _ = (
            build_module_workbench_execution_packet_archive_store_replication_packet(
                changed_plan, packet_id="review-packet"
            )
        )
        changed = build_module_workbench_execution_packet_archive_store_replication_packet_diff(
            packet, changed_packet
        )
        changed_release = (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release(
                changed
            )
        )
        self.assertEqual(
            changed_release.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseState.HOLD,
        )
        self.assertFalse(changed_release.accepted)

    def test_diff_rows_and_nested_addresses_are_reproducible(self) -> None:
        _, packet, _, _, _ = self.packets()
        diff = build_module_workbench_execution_packet_archive_store_replication_packet_diff(
            packet, packet
        )
        verified = verify_module_workbench_execution_packet_archive_store_replication_packet_diff(
            diff
        )
        self.assertIs(verified, diff)
        for item in diff.artifacts:
            self.assertIn("packet-diff-artifact:", item.content_address)
        for item in diff.checks:
            self.assertIn("packet-diff-check:", item.content_address)
        release = (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release(
                diff
            )
        )
        self.assertIs(
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release(
                release
            ),
            release,
        )

    def test_exports_preserve_canonical_shapes(self) -> None:
        _, packet, _, _, _ = self.packets()
        diff = build_module_workbench_execution_packet_archive_store_replication_packet_diff(
            packet, packet
        )
        release = (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release(
                diff
            )
        )
        self.assertEqual(
            json.loads(
                module_workbench_execution_packet_archive_store_replication_packet_diff_json(diff)
            ),
            json.loads(canonical_json(diff.to_dict())),
        )
        self.assertEqual(
            json.loads(
                module_workbench_execution_packet_archive_store_replication_packet_diff_release_json(
                    release
                )
            ),
            json.loads(canonical_json(release.to_dict())),
        )
        csv_text = module_workbench_execution_packet_archive_store_replication_packet_diff_csv(diff)
        self.assertIn("artifact_id", csv_text)
        self.assertIn("resource", csv_text)
        markdown = (
            render_module_workbench_execution_packet_archive_store_replication_packet_diff_markdown(
                diff
            )
        )
        self.assertIn("# Archive Store Replication Packet Diff", markdown)
        self.assertIn(diff.content_address, markdown)

    def test_directory_inputs_round_trip(self) -> None:
        _, packet, payloads, _, _ = self.packets()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left_dir = root / "left"
            right_dir = root / "right"
            write_module_workbench_execution_packet_archive_store_replication_packet(
                packet, payloads, left_dir
            )
            write_module_workbench_execution_packet_archive_store_replication_packet(
                packet, payloads, right_dir
            )
            diff = (
                load_module_workbench_execution_packet_archive_store_replication_packet_diff_inputs(
                    left_dir, right_dir
                )
            )
            self.assertEqual(
                diff.state,
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffState.MATCHED,
            )
            loaded, loaded_payloads = (
                load_module_workbench_execution_packet_archive_store_replication_packet(left_dir)
            )
            self.assertEqual(loaded.content_address, packet.content_address)
            self.assertEqual(loaded_payloads, payloads)

    def test_diff_runtime_closes_all_stages(self) -> None:
        _, packet, _, _, _ = self.packets()
        runtime = (
            run_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime(
                packet, packet
            )
        )
        self.assertTrue(runtime.accepted)
        self.assertEqual(runtime.stage_count, 6)
        self.assertEqual(runtime.completed_count, 6)
        self.assertEqual(runtime.skipped_count, 0)
        self.assertEqual(runtime.blocked_count, 0)
        verify_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime(
            runtime
        )
        self.assertIn(
            "packet-diff-runtime:",
            module_workbench_execution_packet_archive_store_replication_packet_diff_runtime_json(
                runtime
            ),
        )
        self.assertIn(
            "ordinal,kind,state",
            module_workbench_execution_packet_archive_store_replication_packet_diff_runtime_csv(
                runtime
            ),
        )

    def test_diff_runtime_accepts_directory_inputs(self) -> None:
        _, packet, payloads, _, _ = self.packets()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left_dir = root / "left"
            right_dir = root / "right"
            write_module_workbench_execution_packet_archive_store_replication_packet(
                packet, payloads, left_dir
            )
            write_module_workbench_execution_packet_archive_store_replication_packet(
                packet, payloads, right_dir
            )
            runtime = (
                run_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime(
                    left_dir, right_dir
                )
            )
            self.assertTrue(runtime.accepted)
            self.assertEqual(
                runtime.diff_address.split(":", 1)[0],
                "module-workbench-execution-packet-archive-store-replication-packet-diff",
            )

    def test_diff_runtime_query_filters_stage_rows(self) -> None:
        _, packet, _, _, _ = self.packets()
        runtime = (
            run_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime(
                packet, packet
            )
        )
        page = (
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime(
                runtime, resource="stages", kind="compare", limit=5
            )
        )
        self.assertEqual(page["total"], 1)
        self.assertEqual(len(page["items"]), 1)
        self.assertEqual(page["items"][0]["kind"], "compare")
        self.assertTrue(page["accepted"])

    def test_runtime_rejects_mixed_typed_and_directory_inputs(self) -> None:
        _, packet, _, _, _ = self.packets()
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValidationError):
                run_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime(
                    packet, Path(temporary)
                )

    def test_schema_and_capabilities_expose_release_and_runtime(self) -> None:
        schema = module_workbench_execution_packet_archive_store_replication_packet_diff_schema()
        runtime_schema = (
            module_workbench_execution_packet_archive_store_replication_packet_diff_runtime_schema()
        )
        capabilities = (
            module_workbench_execution_packet_archive_store_replication_packet_diff_capabilities()
        )
        runtime_capabilities = (
            module_workbench_execution_packet_archive_store_replication_packet_diff_runtime_capabilities()
        )
        self.assertIn("release_checks", schema["resources"])
        self.assertTrue(schema["fail_closed"])
        self.assertIn("compare_packet_manifests", capabilities["operations"])
        self.assertIn("regression_hold", capabilities["guarantees"])
        self.assertIn("complete", runtime_schema["stage_kinds"])
        self.assertIn("ordered_stages", runtime_capabilities["guarantees"])

    def test_public_documents_do_not_contain_paths_or_identity_fields(self) -> None:
        _, packet, _, _, _ = self.packets()
        diff = build_module_workbench_execution_packet_archive_store_replication_packet_diff(
            packet, packet
        )
        release = (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release(
                diff
            )
        )
        runtime = (
            run_module_workbench_execution_packet_archive_store_replication_packet_diff_runtime(
                packet, packet
            )
        )
        documents = (
            module_workbench_execution_packet_archive_store_replication_packet_diff_json(diff),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_json(
                release
            ),
            module_workbench_execution_packet_archive_store_replication_packet_diff_runtime_json(
                runtime
            ),
        )
        for document in documents:
            lowered = document.casefold()
            self.assertNotIn("agent", lowered)
            self.assertNotIn("assistant", lowered)
            self.assertNotIn("username", lowered)
            self.assertNotIn("c:\\", lowered)

    def test_diff_rejects_non_typed_inputs(self) -> None:
        with self.assertRaises(ValidationError):
            build_module_workbench_execution_packet_archive_store_replication_packet_diff(
                object(), object()
            )

    def test_release_verifier_rejects_tampered_detail(self) -> None:
        _, packet, _, _, _ = self.packets()
        diff = build_module_workbench_execution_packet_archive_store_replication_packet_diff(
            packet, packet
        )
        release = (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release(
                diff
            )
        )
        tampered = replace(release, detail="tampered")
        with self.assertRaises(ValidationError):
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release(
                tampered
            )

    def test_schema_document_alias_matches_contract_schema(self) -> None:
        self.assertEqual(
            module_workbench_execution_packet_archive_store_replication_packet_diff_schema_document(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_schema(),
        )


if __name__ == "__main__":
    unittest.main()
