"""Deep regression tests for analysis-only release-window policy sensitivity."""

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
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_policy,
)
from glio_noncode.module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_from_directories,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_query_capabilities,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_query_csv,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_query_json,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_query_schema,
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_schema,
    query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_markdown,
    render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_query_markdown,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_query,
)
from glio_noncode.serialization import canonical_json
from tests.test_module_workbench_execution import ModuleWorkbenchExecutionFixture


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowSensitivityTests(
    unittest.TestCase
):
    """Exercise policy comparison, conservation, exports, and routes."""

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

    def _packet(self, packet_id: str = "base-packet"):
        base = self._archive("base")
        next_archive = self._archive("next")
        target = build_module_workbench_execution_packet_archive_store((base,), store_id="target")
        source = append_module_workbench_execution_packet_archive_store(
            target, next_archive, operation_id="next-operation"
        )
        plan = build_module_workbench_execution_packet_archive_store_replication(source, target)
        packet, _ = build_module_workbench_execution_packet_archive_store_replication_packet(
            plan, packet_id=packet_id
        )
        return packet

    def _batch(self, divergent: bool = False):
        left = self._packet("left-packet")
        right = self._packet("right-packet") if divergent else left
        diff = build_module_workbench_execution_packet_archive_store_replication_packet_diff(
            left, right
        )
        release = (
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release(
                diff
            )
        )
        return build_module_workbench_execution_packet_archive_store_replication_packet_diff_batch(
            (("review", diff, release),), batch_id="sensitivity-batch"
        )

    def _policies(self):
        strict = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_policy(
            policy_id="strict-policy"
        )
        relaxed = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_policy(
            policy_id="relaxed-policy",
            minimum_score=0.5,
        )
        review = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_policy(
            policy_id="review-policy",
            minimum_score=0.0,
            maximum_hold_count=1,
            require_all_release_ready=False,
        )
        return strict, relaxed, review

    def test_matched_matrix_conserves_promotable_policy_scenarios(self) -> None:
        strict, relaxed, _ = self._policies()
        value = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity(
            self._batch(),
            (("strict", strict), ("relaxed", relaxed)),
            sensitivity_id="matched-sensitivity",
        )
        self.assertEqual(value.scenario_count, 2)
        self.assertEqual(value.accepted_count, 2)
        self.assertEqual(value.promotable_count, 2)
        self.assertEqual(value.hold_count, 0)
        self.assertEqual(value.blocked_count, 0)
        self.assertTrue(value.accepted)
        self.assertTrue(value.analysis_only)
        self.assertEqual(value.best_promotable_scenario_id, "strict")
        self.assertTrue(value.best_promotable_window_address)
        self.assertEqual([item.ordinal for item in value.scenarios], [0, 1])
        self.assertIs(
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity(
                value
            ),
            value,
        )

    def test_divergent_matrix_shows_strict_block_and_review_hold(self) -> None:
        strict, _, review = self._policies()
        value = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity(
            self._batch(divergent=True),
            (("strict", strict), ("review", review)),
            sensitivity_id="divergent-sensitivity",
        )
        self.assertTrue(value.accepted)
        self.assertEqual(value.promotable_count, 0)
        self.assertEqual(value.hold_count, 1)
        self.assertEqual(value.blocked_count, 1)
        self.assertIsNone(value.best_promotable_scenario_id)
        self.assertIsNone(value.best_promotable_window_address)
        self.assertEqual(
            [item.state for item in value.scenarios],
            ["blocked", "hold"],
        )
        self.assertTrue(
            all(item.policy_address.startswith("module-workbench") for item in value.scenarios)
        )

    def test_best_scenario_tie_break_is_stable_and_analysis_only(self) -> None:
        strict, relaxed, _ = self._policies()
        value = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity(
            self._batch(),
            (("first", strict), ("second", relaxed)),
            sensitivity_id="tie-sensitivity",
        )
        self.assertEqual(value.best_promotable_scenario_id, "first")
        payload = value.to_dict()
        self.assertTrue(payload["analysis_only"])
        self.assertIn("no scenario is an approval", canonical_json(payload).casefold())
        self.assertEqual(payload["scenario_count"], len(payload["scenarios"]))
        self.assertEqual(payload["accepted_count"], 2)

    def test_input_validation_rejects_empty_duplicate_and_untyped_scenarios(self) -> None:
        strict, _, _ = self._policies()
        batch = self._batch()
        with self.assertRaises(ValidationError):
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity(
                batch, (), sensitivity_id="empty"
            )
        with self.assertRaises(ValidationError):
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity(
                batch, (("same", strict), ("same", strict)), sensitivity_id="duplicate"
            )
        with self.assertRaises(ValidationError):
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity(
                batch, (("wrong", object()),), sensitivity_id="untyped"
            )

    def test_input_validation_rejects_more_than_published_scenario_limit(self) -> None:
        strict, _, _ = self._policies()
        scenarios = tuple((f"scenario-{index}", strict) for index in range(65))
        with self.assertRaises(ValidationError):
            build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity(
                self._batch(), scenarios, sensitivity_id="too-many"
            )

    def test_json_csv_and_markdown_exports_preserve_analysis_marker(self) -> None:
        strict, relaxed, _ = self._policies()
        value = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity(
            self._batch(),
            (("strict", strict), ("relaxed", relaxed)),
            sensitivity_id="export-sensitivity",
        )
        encoded = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_json(
            value
        )
        self.assertTrue(json.loads(encoded)["analysis_only"])
        csv_text = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_csv(
            value
        )
        self.assertIn("scenario_id", csv_text)
        self.assertEqual(len(csv_text.splitlines()), 3)
        markdown = render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_markdown(
            value
        )
        self.assertIn("analysis-only", markdown)
        self.assertIn("strict", markdown)

    def test_query_filters_pages_and_detects_tamper(self) -> None:
        strict, relaxed, _ = self._policies()
        value = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity(
            self._batch(),
            (("strict", strict), ("relaxed", relaxed)),
            sensitivity_id="query-sensitivity",
        )
        summary = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity(
            value
        )
        self.assertEqual(summary["resource"], "summary")
        self.assertEqual(summary["total"], 1)
        scenarios = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity(
            value, resource="scenarios", state="promotable", offset=1, limit=1
        )
        self.assertEqual(scenarios["total"], 2)
        self.assertEqual(len(scenarios["items"]), 1)
        self.assertEqual(scenarios["items"][0]["scenario_id"], "relaxed")
        self.assertEqual(
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_query(
                scenarios
            ),
            scenarios,
        )
        tampered = dict(scenarios)
        tampered["analysis_only"] = False
        with self.assertRaises(ValidationError):
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_query(
                tampered
            )
        tampered = dict(scenarios)
        tampered["content_address"] = "sensitivity-query:tampered"
        with self.assertRaises(ValidationError):
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_query(
                tampered
            )

    def test_query_exports_and_invalid_filters_are_bounded(self) -> None:
        strict, relaxed, _ = self._policies()
        value = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity(
            self._batch(), (("strict", strict), ("relaxed", relaxed)), sensitivity_id="query-export"
        )
        result = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity(
            value, resource="scenarios", accepted=True, text="policy", limit=50
        )
        self.assertEqual(result["total"], 2)
        self.assertIn(
            "scenario_id",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_query_json(
                result
            ),
        )
        self.assertIn(
            "scenario_id",
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_query_csv(
                result
            ),
        )
        self.assertIn(
            "Scenario",
            render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_query_markdown(
                result
            ),
        )
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity(
                value, resource="unknown"
            )
        with self.assertRaises(ValidationError):
            query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity(
                value, limit=513
            )

    def test_directory_builder_uses_persisted_packet_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            left = Path(temp) / "left"
            right = Path(temp) / "right"
            source = self._archive("base")
            target = build_module_workbench_execution_packet_archive_store(
                (source,), store_id="persisted-target"
            )
            plan = build_module_workbench_execution_packet_archive_store_replication(target, target)
            stored_packet, payloads = (
                build_module_workbench_execution_packet_archive_store_replication_packet(
                    plan, packet_id="directory-packet"
                )
            )
            write_module_workbench_execution_packet_archive_store_replication_packet(
                stored_packet, payloads, left
            )
            write_module_workbench_execution_packet_archive_store_replication_packet(
                stored_packet, payloads, right
            )
            strict, relaxed, _ = self._policies()
            value = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_from_directories(
                (("persisted", left, right),),
                (("strict", strict), ("relaxed", relaxed)),
                batch_id="persisted-sensitivity-batch",
                sensitivity_id="persisted-sensitivity",
            )
            self.assertEqual(value.scenario_count, 2)
            self.assertEqual(value.promotable_count, 2)

    def test_http_api_exposes_sensitivity_routes_on_persisted_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            left = Path(temp) / "left"
            right = Path(temp) / "right"
            source = self._archive("base")
            target = build_module_workbench_execution_packet_archive_store(
                (source,), store_id="api-target"
            )
            plan = build_module_workbench_execution_packet_archive_store_replication(target, target)
            stored_packet, payloads = (
                build_module_workbench_execution_packet_archive_store_replication_packet(
                    plan, packet_id="api-persisted-packet"
                )
            )
            write_module_workbench_execution_packet_archive_store_replication_packet(
                stored_packet, payloads, left
            )
            write_module_workbench_execution_packet_archive_store_replication_packet(
                stored_packet, payloads, right
            )
            server = create_server("127.0.0.1", 0, temp)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = None
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                query = urlencode(
                    [
                        ("pair", f"same={left}={right}"),
                        ("scenario", "strict=1.0=0"),
                        ("scenario", "relaxed=0.5=0"),
                        ("format", "summary"),
                    ]
                )
                path = (
                    "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/sensitivity?"
                    + query
                )
                connection.request("GET", path)
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                payload = json.loads(response.read())
                self.assertTrue(payload["analysis_only"])
                self.assertEqual(payload["scenario_count"], 2)
                query_query = urlencode(
                    [
                        ("pair", f"same={left}={right}"),
                        ("scenario", "strict=1.0=0"),
                        ("scenario", "relaxed=0.5=0"),
                        ("resource", "scenarios"),
                        ("state", "promotable"),
                    ]
                )
                connection.request(
                    "GET",
                    "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/sensitivity/query?"
                    + query_query,
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())["total"], 2)
                connection.request(
                    "GET",
                    "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/sensitivity/schema",
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertTrue(json.loads(response.read())["identity_free"])
            finally:
                if connection is not None:
                    connection.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_schema_and_capabilities_are_identity_free_and_analysis_only(self) -> None:
        values = (
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_schema(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_capabilities(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_query_schema(),
            module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity_query_capabilities(),
        )
        for value in values:
            encoded = canonical_json(value).casefold()
            self.assertTrue(value["analysis_only"])
            self.assertNotIn("agent", encoded)
            self.assertNotIn("model", encoded)
            self.assertNotIn("private", encoded)
            self.assertNotIn("language", encoded)
            self.assertTrue(value["identity_free"])


if __name__ == "__main__":
    unittest.main()
