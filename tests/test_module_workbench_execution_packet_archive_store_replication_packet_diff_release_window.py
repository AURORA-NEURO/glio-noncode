"""Deep regression tests for release-window policy governance."""

# ruff: noqa: E501

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread
from urllib.parse import urlencode

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
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_batch import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_batch,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_from_directories,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_policy,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_schema,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_markdown,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_query_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_query_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_query_schema,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_schema,
    query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_markdown,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_query_markdown,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_query,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_contracts import (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceState,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowState,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_policy,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_query import (
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_query_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_query_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_query_schema,
    query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_query_markdown,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_query,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime import (
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_query_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_query_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_query_schema,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_schema,
    query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_markdown,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_query_markdown,
    run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_query,
)
from glio_noncode.serialization import canonical_json
from tests.test_module_workbench_execution import ModuleWorkbenchExecutionFixture


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowTests(
    unittest.TestCase
):
    """Exercise policy thresholds, runtime closure, assurance, and exports."""

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
        packet, _ = build_module_workbench_execution_packet_archive_store_replication_packet(
            plan, packet_id=packet_id
        )
        return packet

    def _batch(self, divergent: bool = False):
        packet = self._packet()
        candidate = self._packet("candidate-packet") if divergent else packet
        diff = build_module_workbench_execution_packet_archive_store_replication_packet_diff(
            packet, candidate
        )
        release = (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release(
                diff
            )
        )
        return build_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(
            (("review", diff, release),), batch_id="window-batch"
        )

    def test_default_policy_promotes_a_fully_matched_window(self) -> None:
        window = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
            self._batch()
        )
        self.assertEqual(
            window.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowState.PROMOTABLE.value,
        )
        self.assertTrue(window.release_ready)
        self.assertEqual(window.check_count, 11)
        self.assertEqual(window.passed_count, 11)
        self.assertEqual(window.blocker_count, 0)
        self.assertEqual(window.warning_count, 0)
        self.assertIs(
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
                window
            ),
            window,
        )

    def test_default_policy_blocks_divergent_window(self) -> None:
        window = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
            self._batch(divergent=True)
        )
        self.assertEqual(
            window.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowState.BLOCKED.value,
        )
        self.assertFalse(window.release_ready)
        self.assertGreaterEqual(window.blocker_count, 1)
        kinds = {item.kind for item in window.checks if not item.passed}
        self.assertIn("minimum_score", kinds)
        self.assertIn("hold_limit", kinds)

    def test_review_policy_holds_without_promoting(self) -> None:
        policy = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_policy(
            policy_id="review-policy",
            minimum_score=0,
            maximum_hold_count=1,
            require_all_release_ready=False,
        )
        window = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
            self._batch(divergent=True), policy, window_id="review-window"
        )
        self.assertEqual(
            window.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowState.HOLD.value,
        )
        self.assertFalse(window.release_ready)
        self.assertEqual(window.warning_count, 1)
        self.assertEqual(window.blocker_count, 0)

    def test_policy_addresses_are_deterministic_and_identity_free(self) -> None:
        first = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_policy(
            policy_id="stable"
        )
        second = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_policy(
            policy_id="stable"
        )
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_policy(
                first
            ),
            first.content_address,
        )
        encoded = canonical_json(first.to_dict()).casefold()
        for forbidden in ("agent", "assistant", "author", "model", "private", "user"):
            self.assertNotIn(forbidden, encoded)

    def test_exports_are_canonical_and_reviewable(self) -> None:
        window = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
            self._batch()
        )
        self.assertEqual(
            json.loads(
                module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_json(
                    window
                )
            ),
            json.loads(canonical_json(window.to_dict())),
        )
        self.assertIn(
            "window_id",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_csv(
                window
            ),
        )
        self.assertIn(
            "# Archive Store Replication Packet Diff Release Window",
            render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_markdown(
                window
            ),
        )

    def test_window_query_filters_checks_and_verifies_address(self) -> None:
        window = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
            self._batch(divergent=True)
        )
        result = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
            window, resource="checks", passed=False, offset=0, limit=2
        )
        self.assertEqual(result["total"], window.blocker_count)
        self.assertLessEqual(len(result["items"]), 2)
        verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_query(
            result
        )
        self.assertIn(
            "check_id",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_query_csv(
                result
            ),
        )
        self.assertIn(
            "# Archive Store Replication Packet Diff Release Window Query",
            render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_query_markdown(
                result
            ),
        )
        self.assertEqual(
            json.loads(
                module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_query_json(
                    result
                )
            ),
            result,
        )
        result["items"][0]["detail"] = "tampered"
        with self.assertRaises(ValidationError):
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_query(
                result
            )

    def test_runtime_closes_promotable_window(self) -> None:
        runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime(
            self._batch()
        )
        self.assertEqual(runtime.stage_count, 7)
        self.assertEqual(runtime.completed_count, 7)
        self.assertEqual(runtime.blocked_count, 0)
        self.assertEqual(runtime.skipped_count, 0)
        self.assertTrue(runtime.accepted)
        verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime(
            runtime
        )
        self.assertIn(
            "stage_count",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_json(
                runtime
            ),
        )
        self.assertIn(
            "ordinal",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_csv(
                runtime
            ),
        )
        self.assertIn(
            "# Archive Store Replication Packet Diff Release Window Runtime",
            render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_markdown(
                runtime
            ),
        )

    def test_runtime_fails_closed_and_skips_release_after_blocker(self) -> None:
        runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime(
            self._batch(divergent=True)
        )
        self.assertEqual(runtime.blocked_count, 1)
        self.assertEqual(runtime.completed_count, 4)
        self.assertEqual(runtime.skipped_count, 2)
        self.assertFalse(runtime.accepted)
        stage_query = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime(
            runtime, resource="stages", state="blocked"
        )
        verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_query(
            stage_query
        )
        self.assertIn(
            "kind",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_query_json(
                stage_query
            ),
        )
        self.assertIn(
            "kind",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_query_csv(
                stage_query
            ),
        )
        self.assertIn(
            "# Archive Store Replication Packet Diff Release Window Runtime Query",
            render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_query_markdown(
                stage_query
            ),
        )

    def test_assurance_accepts_matched_window_with_closed_runtime(self) -> None:
        window = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
            self._batch()
        )
        runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime(
            self._batch()
        )
        assurance = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance(
            window, runtime
        )
        self.assertEqual(
            assurance.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceState.ACCEPTED.value,
        )
        self.assertTrue(assurance.release_ready)
        self.assertEqual(assurance.finding_count, 9)
        self.assertEqual(assurance.warning_count, 0)
        self.assertEqual(assurance.blocker_count, 0)
        verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance(
            assurance
        )
        self.assertIn(
            "finding_id",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_csv(
                assurance
            ),
        )
        self.assertIn(
            "# Archive Store Replication Packet Diff Release Window Assurance",
            render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_markdown(
                assurance
            ),
        )

    def test_assurance_blocks_window_with_policy_blockers(self) -> None:
        window = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
            self._batch(divergent=True)
        )
        assurance = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance(
            window
        )
        self.assertEqual(
            assurance.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowAssuranceState.BLOCKED.value,
        )
        self.assertFalse(assurance.release_ready)
        self.assertGreaterEqual(assurance.blocker_count, 1)

    def test_assurance_query_filters_and_detects_tamper(self) -> None:
        window = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
            self._batch(divergent=True)
        )
        assurance = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance(
            window
        )
        result = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance(
            assurance, resource="findings", severity="blocker", passed=False, limit=3
        )
        self.assertGreaterEqual(result["total"], 1)
        verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_query(
            result
        )
        self.assertIn(
            "finding_id",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_query_csv(
                result
            ),
        )
        self.assertIn(
            "# Archive Store Replication Packet Diff Release Window Assurance Query",
            render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_query_markdown(
                result
            ),
        )
        self.assertEqual(
            json.loads(
                module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_query_json(
                    result
                )
            ),
            result,
        )
        result["items"][0]["detail"] = "tampered"
        with self.assertRaises(ValidationError):
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_query(
                result
            )

    def test_assurance_rejects_runtime_from_another_window(self) -> None:
        first = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
            self._batch()
        )
        second = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
            self._batch(), window_id="second-window"
        )
        runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime(
            self._batch(), window_id=first.window_id
        )
        with self.assertRaises(ValidationError):
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance(
                second, runtime
            )

    def test_directory_builder_writes_and_reloads_packet_pairs(self) -> None:
        source, target = self._stores()
        plan = build_module_workbench_execution_packet_archive_store_replication(source, target)
        packet, payloads = build_module_workbench_execution_packet_archive_store_replication_packet(
            plan, packet_id="directory-packet"
        )
        with tempfile.TemporaryDirectory() as temp:
            left = Path(temp) / "left"
            right = Path(temp) / "right"
            write_module_workbench_execution_packet_archive_store_replication_packet(
                packet, payloads, left
            )
            write_module_workbench_execution_packet_archive_store_replication_packet(
                packet, payloads, right
            )
            window = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_from_directories(
                (("persisted", left, right),),
                batch_id="directory-batch",
                window_id="directory-window",
            )
            self.assertTrue(window.release_ready)
            self.assertEqual(window.item_count, 1)

    def test_http_api_exposes_window_runtime_assurance_and_schema(self) -> None:
        source, target = self._stores()
        plan = build_module_workbench_execution_packet_archive_store_replication(source, target)
        packet, payloads = build_module_workbench_execution_packet_archive_store_replication_packet(
            plan, packet_id="api-packet"
        )
        with tempfile.TemporaryDirectory() as temp:
            left = Path(temp) / "left"
            right = Path(temp) / "right"
            write_module_workbench_execution_packet_archive_store_replication_packet(
                packet, payloads, left
            )
            write_module_workbench_execution_packet_archive_store_replication_packet(
                packet, payloads, right
            )
            server = create_server("127.0.0.1", 0, temp)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = None
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                query = urlencode(
                    [("pair", f"same={left}={right}"), ("format", "summary")]
                )
                connection.request(
                    "GET",
                    "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window?"
                    + query,
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                window_payload = json.loads(response.read())
                self.assertEqual(window_payload["state"], "promotable")
                self.assertTrue(window_payload["release_ready"])
                connection.request(
                    "GET",
                    "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/runtime?"
                    + query,
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())["stage_count"], 7)
                connection.request(
                    "GET",
                    "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/assurance?"
                    + query,
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())["state"], "accepted")
                connection.request(
                    "GET",
                    "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/runtime/schema",
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertTrue(json.loads(response.read())["fail_closed"])
                connection.request(
                    "GET",
                    "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/assurance/query?"
                    + query
                    + "&resource=findings&severity=blocker&passed=false",
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())["total"], 0)
            finally:
                if connection is not None:
                    connection.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_schema_and_capabilities_declare_boundaries(self) -> None:
        schema = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_schema()
        capabilities = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_capabilities()
        assurance_schema = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_schema()
        assurance_capabilities = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_capabilities()
        runtime_schema = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_schema()
        runtime_capabilities = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_capabilities()
        query_schema = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_query_schema()
        assurance_query_schema = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance_query_schema()
        runtime_query_schema = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_query_schema()
        for value in (
            schema,
            capabilities,
            assurance_schema,
            assurance_capabilities,
            runtime_schema,
            runtime_capabilities,
            query_schema,
            assurance_query_schema,
            runtime_query_schema,
        ):
            encoded = canonical_json(value).casefold()
            self.assertNotIn("agent", encoded)
            self.assertNotIn("model", encoded)
            self.assertNotIn("private", encoded)
        self.assertTrue(schema["fail_closed"])
        self.assertTrue(runtime_schema["fail_closed"])
        self.assertTrue(assurance_schema["fail_closed"])


if __name__ == "__main__":
    unittest.main()
