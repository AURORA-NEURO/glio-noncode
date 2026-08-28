"""Deep contracts for multi-history decision-assurance series."""

# ruff: noqa: E501

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import (
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_decision_ledger_assurance_history as history,
)
from glio_noncode import (
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_decision_ledger_assurance_history_series as series,
)
from glio_noncode.errors import ValidationError
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.serialization import canonical_bytes, canonical_json
from tests.test_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_decision_ledger_assurance_history import HistoryFixture


class SeriesFixture(HistoryFixture):
    def ready_history(self, history_id: str) -> history.DecisionAssuranceHistory:
        return history.build_decision_assurance_history(self.build_ready_assurance_gate(), history_id=history_id)

    def held_history(self, history_id: str) -> history.DecisionAssuranceHistory:
        return history.build_decision_assurance_history(self.build_held_assurance_gate(), history_id=history_id)

    def blocked_history(self, history_id: str) -> history.DecisionAssuranceHistory:
        return history.build_decision_assurance_history(self.build_blocked_assurance_gate(), history_id=history_id)

    def improving_history(self, history_id: str) -> history.DecisionAssuranceHistory:
        value = self.held_history(history_id)
        return history.append_decision_assurance_history(value, self.build_ready_assurance_gate(), snapshot_id=f"{history_id}:ready")

    def regressing_history(self, history_id: str) -> history.DecisionAssuranceHistory:
        value = self.ready_history(history_id)
        return history.append_decision_assurance_history(value, self.build_held_assurance_gate(), snapshot_id=f"{history_id}:held")

    def build_series(self, values=(), series_id="series:test"):
        return series.build_decision_assurance_history_series(tuple(values), series_id=series_id)

    def write_series(self, value, destination, **kwargs):
        return series.write_decision_assurance_history_series(value, destination, **kwargs)


class SeriesCoreTests(SeriesFixture):
    def test_empty_series_is_addressed_and_replayable(self):
        value = self.build_series()
        self.assertEqual(value.history_count, 0)
        self.assertEqual(value.current_state, "empty")
        self.assertEqual(value.observation_count, 0)
        replay = series.replay_decision_assurance_history_series(value)
        self.assertTrue(replay.accepted)
        self.assertFalse(replay.release_ready)
        self.assertEqual(replay.passed_count, 8)

    def test_histories_are_sorted_without_changing_the_source_order(self):
        first = self.ready_history("history:z")
        second = self.held_history("history:a")
        value = self.build_series((first, second))
        self.assertEqual([entry.history_id for entry in value.entries], ["history:a", "history:z"])
        self.assertEqual(value.current_state, "mixed")
        self.assertEqual(value.ready_history_count, 1)
        self.assertEqual(value.held_history_count, 1)
        self.assertEqual(value.current_ready_count, 1)
        self.assertEqual(value.current_held_count, 1)

    def test_series_conserves_history_observations_and_transitions(self):
        values = (self.ready_history("history:ready"), self.improving_history("history:improving"), self.regressing_history("history:regressing"), self.blocked_history("history:blocked"))
        value = self.build_series(values)
        self.assertEqual(value.history_count, 4)
        self.assertEqual(value.observation_count, 6)
        self.assertEqual(value.initial_count, 4)
        self.assertEqual(value.improved_count, 1)
        self.assertEqual(value.regressed_count, 1)
        self.assertEqual(value.accepted_observation_count, sum(item.accepted_count for item in values))
        self.assertEqual(value.release_ready_observation_count, sum(item.release_ready_count for item in values))
        self.assertEqual(value.current_blocked_count, 1)

    def test_live_series_append_requires_expected_address_and_preserves_sources(self):
        first = self.ready_history("history:first")
        value = self.build_series((first,))
        with self.assertRaises(ValidationError):
            series.append_decision_assurance_history_series(value, self.held_history("history:second"), expected_address="series:stale")
        extended = series.append_decision_assurance_history_series(value, self.held_history("history:second"), expected_address=value.content_address)
        self.assertEqual(extended.history_count, 2)
        self.assertEqual([item.history_id for item in extended.entries], ["history:first", "history:second"])
        self.assertNotEqual(extended.content_address, value.content_address)

    def test_loaded_series_cannot_append_without_source_histories(self):
        value = self.build_series((self.ready_history("history:one"),))
        with tempfile.TemporaryDirectory() as temporary:
            self.write_series(value, Path(temporary) / "series")
            loaded = series.load_decision_assurance_history_series(Path(temporary) / "series")
            with self.assertRaises(ValidationError):
                series.append_decision_assurance_history_series(loaded, self.ready_history("history:two"))

    def test_duplicate_and_untyped_histories_are_rejected(self):
        value = self.ready_history("history:duplicate")
        with self.assertRaises(ValidationError):
            self.build_series((value, value))
        with self.assertRaises(ValidationError):
            self.build_series([object()])

    def test_mapping_round_trip_recomputes_all_addresses(self):
        value = self.build_series((self.ready_history("history:mapped"), self.held_history("history:held")))
        restored = series.decision_assurance_history_series_from_mapping(value.to_dict())
        self.assertEqual(restored.to_dict(), value.to_dict())
        body = value.to_dict()
        body["private"] = True
        with self.assertRaises(ValidationError):
            series.decision_assurance_history_series_from_mapping(body)
        body = value.to_dict()
        body["entries"][0]["history_id"] = "history:tampered"
        with self.assertRaises(ValidationError):
            series.decision_assurance_history_series_from_mapping(body)

    def test_direct_shapes_reject_bad_state_and_counter_projection(self):
        value = self.build_series((self.ready_history("history:direct"),))
        body = value.to_dict()
        body["current_state"] = "blocked"
        with self.assertRaises(ValidationError):
            series.DecisionAssuranceHistorySeries(**{key: body[key] for key in body if key != "entries"}, entries=tuple(series.decision_assurance_history_series_entry_from_mapping(item) for item in value.to_dict()["entries"]))
        entry = value.entries[0].to_dict()
        entry["current_gate_state"] = "block"
        entry["current_state"] = "blocked"
        entry["content_address"] = "series-entry:tampered"
        with self.assertRaises(ValidationError):
            series.DecisionAssuranceHistorySeriesEntry(**entry)

    def test_public_projection_excludes_paths_and_private_metadata(self):
        value = self.build_series((self.ready_history("history:public"),))
        payload = canonical_json(value.to_dict()).casefold()
        self.assertNotIn(str(self.real_packet()).casefold(), payload)
        self.assertNotIn("source_path", payload)
        for forbidden in ("agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"):
            self.assertNotIn(f'"{forbidden}"', payload)


class SeriesDiffTests(SeriesFixture):
    def test_diff_reports_added_removed_unchanged_and_changed_histories(self):
        unchanged = self.ready_history("history:unchanged")
        baseline = self.build_series((unchanged, self.held_history("history:improve"), self.ready_history("history:remove")), "series:baseline")
        candidate = self.build_series((unchanged, self.improving_history("history:improve"), self.ready_history("history:add")), "series:candidate")
        value = series.diff_decision_assurance_history_series(baseline, candidate)
        self.assertEqual(value.added_count, 1)
        self.assertEqual(value.removed_count, 1)
        self.assertEqual(value.unchanged_count, 1)
        self.assertEqual(value.changed_count, 1)
        self.assertEqual(value.improved_count, 1)
        self.assertEqual(value.regressed_count, 0)
        self.assertEqual(value.state_changed_count, 1)
        items = {item.history_id: item for item in value.items}
        self.assertEqual(items["history:improve"].direction, "improved")
        self.assertEqual(items["history:add"].action, "added")
        self.assertEqual(items["history:remove"].action, "removed")
        self.assertEqual(items["history:unchanged"].action, "unchanged")

    def test_diff_reports_regression_and_same_state_semantic_change(self):
        baseline = self.build_series((self.ready_history("history:regress"),), "series:baseline")
        candidate = self.build_series((self.regressing_history("history:regress"),), "series:candidate")
        value = series.diff_decision_assurance_history_series(baseline, candidate)
        self.assertEqual(value.changed_count, 1)
        self.assertEqual(value.regressed_count, 1)
        self.assertEqual(value.items[0].direction, "regressed")
        same_state_baseline = self.build_series((self.held_history("history:same-state"),), "series:old")
        same_state_candidate = self.build_series((self.improving_history("history:same-state"),), "series:new")
        semantic = series.diff_decision_assurance_history_series(same_state_baseline, same_state_candidate)
        self.assertEqual(semantic.items[0].action, "changed")
        self.assertEqual(semantic.items[0].direction, "improved")

    def test_diff_mapping_and_tamper_rejection(self):
        baseline = self.build_series((self.held_history("history:diff"),))
        candidate = self.build_series((self.ready_history("history:diff"),))
        value = series.diff_decision_assurance_history_series(baseline, candidate)
        restored = series.decision_assurance_history_series_diff_from_mapping(value.to_dict())
        self.assertEqual(restored.to_dict(), value.to_dict())
        body = value.to_dict()
        body["items"][0]["direction"] = "regressed"
        with self.assertRaises(ValidationError):
            series.decision_assurance_history_series_diff_from_mapping(body)
        item = value.items[0].to_dict()
        item["content_address"] = "diff-item:tampered"
        with self.assertRaises(ValidationError):
            series.decision_assurance_history_series_diff_item_from_mapping(item)

    def test_diff_empty_series_is_deterministic(self):
        baseline = self.build_series((), "series:empty-old")
        candidate = self.build_series((), "series:empty-new")
        value = series.diff_decision_assurance_history_series(baseline, candidate)
        self.assertEqual(value.items, ())
        self.assertEqual(value.added_count, 0)
        self.assertEqual(value.removed_count, 0)
        self.assertEqual(series.decision_assurance_history_series_diff_json(value), series.decision_assurance_history_series_diff_json(value))


class SeriesReplayQueryExportTests(SeriesFixture):
    def build_long_series(self):
        return self.build_series((self.ready_history("history:ready"), self.held_history("history:held"), self.blocked_history("history:blocked"), self.improving_history("history:improving"), self.regressing_history("history:regressing")))

    def test_replay_has_eight_addressed_checks(self):
        value = self.build_long_series()
        replay = series.replay_decision_assurance_history_series(value)
        self.assertEqual(replay.check_count, 8)
        self.assertEqual(replay.passed_count, 8)
        self.assertEqual(replay.failure_count, 0)
        self.assertTrue(replay.accepted)
        self.assertTrue(replay.release_ready)
        restored = series.decision_assurance_history_series_replay_from_mapping(replay.to_dict())
        self.assertEqual(restored.to_dict(), replay.to_dict())

    def test_query_supports_summary_states_filters_and_paging(self):
        value = self.build_long_series()
        summary = series.query_decision_assurance_history_series(value, resource="summary")
        self.assertEqual(summary.total_count, 1)
        self.assertEqual(summary.items[0]["history_count"], 5)
        held = series.query_decision_assurance_history_series(value, resource="held")
        self.assertEqual([item["history_id"] for item in held.items], ["history:held", "history:regressing"])
        accepted = series.query_decision_assurance_history_series(value, resource="accepted")
        self.assertEqual(accepted.total_count, 4)
        blocked = series.query_decision_assurance_history_series(value, resource="histories", state="blocked", limit=1)
        self.assertEqual(blocked.items[0]["history_id"], "history:blocked")
        page = series.query_decision_assurance_history_series(value, resource="histories", offset=1, limit=2)
        self.assertEqual(page.returned_count, 2)
        self.assertEqual(page.items[0]["history_id"], "history:held")
        states = series.query_decision_assurance_history_series(value, resource="states")
        self.assertTrue(states.items)
        with self.assertRaises(ValidationError):
            series.AssuranceHistorySeriesQuery(resource="unknown")
        with self.assertRaises(ValidationError):
            series.AssuranceHistorySeriesQuery(resource="histories", offset=4090, limit=10)

    def test_exports_schemas_capabilities_and_markdown_are_stable(self):
        value = self.build_long_series()
        diff = series.diff_decision_assurance_history_series(value, value)
        replay = series.replay_decision_assurance_history_series(value)
        query = series.query_decision_assurance_history_series(value, resource="histories")
        self.assertIn('"series_id"', series.decision_assurance_history_series_json(value))
        self.assertIn("history_id", series.decision_assurance_history_series_csv(value))
        self.assertIn("action", series.decision_assurance_history_series_diff_csv(diff))
        self.assertIn("check_id", series.decision_assurance_history_series_replay_csv(replay))
        self.assertIn("history_id", series.decision_assurance_history_series_query_csv(query))
        self.assertIn("# Federation Review Decision Assurance History Series", series.render_decision_assurance_history_series_markdown(value))
        self.assertIn("# Federation Review Decision Assurance History Series Diff", series.render_decision_assurance_history_series_diff_markdown(diff))
        self.assertIn("# Federation Review Decision Assurance History Series Replay", series.render_decision_assurance_history_series_replay_markdown(replay))
        self.assertIn("# Federation Review Decision Assurance History Series Query", series.render_decision_assurance_history_series_query_markdown(query))
        for schema in (series.decision_assurance_history_series_schema(), series.decision_assurance_history_series_entry_schema(), series.decision_assurance_history_series_diff_schema(), series.decision_assurance_history_series_diff_item_schema(), series.decision_assurance_history_series_replay_schema(), series.decision_assurance_history_series_query_schema()):
            self.assertEqual(schema["additionalProperties"], False)
        self.assertEqual(series.capabilities()["replay"]["checks"], 8)

    def test_replay_mapping_rejects_tampered_check(self):
        replay = series.replay_decision_assurance_history_series(self.build_long_series())
        body = replay.to_dict()
        body["checks"][0]["detail"] = "tampered"
        with self.assertRaises(ValidationError):
            series.decision_assurance_history_series_replay_from_mapping(body)


class SeriesPersistenceTests(SeriesFixture):
    def setUp(self):
        super().setUp()
        self.value = self.build_series((self.ready_history("history:persist-ready"), self.held_history("history:persist-held"), self.improving_history("history:persist-improving")))

    def test_persistence_has_exact_three_file_set_and_round_trips(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "series"
            self.write_series(self.value, destination)
            self.assertEqual({item.name for item in destination.iterdir()}, set(series.FILES))
            loaded = series.load_decision_assurance_history_series(destination)
            self.assertEqual(loaded.to_dict(), self.value.to_dict())
            self.assertEqual(canonical_bytes(json.loads((destination / "series.json").read_text())), (destination / "series.json").read_bytes())

    def test_persistence_is_repeatable_and_manifest_has_receipts(self):
        with tempfile.TemporaryDirectory() as temporary:
            first = Path(temporary) / "first"
            second = Path(temporary) / "second"
            self.write_series(self.value, first)
            self.write_series(self.value, second)
            self.assertEqual([path.read_bytes() for path in first.iterdir()], [path.read_bytes() for path in second.iterdir()])
            manifest = json.loads((first / "manifest.json").read_text())
            self.assertEqual(manifest["artifact_count"], 2)
            self.assertEqual(manifest["history_count"], self.value.history_count)
            self.assertEqual({item["name"] for item in manifest["artifacts"]}, {"series.json", "entries.json"})

    def test_persistence_rejects_missing_extra_tampered_and_noncanonical_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "series"
            self.write_series(self.value, destination)
            (destination / "entries.json").unlink()
            with self.assertRaises(ValidationError):
                series.load_decision_assurance_history_series(destination)
            self.write_series(self.value, destination, overwrite=True)
            (destination / "extra.json").write_text("{}")
            with self.assertRaises(ValidationError):
                series.load_decision_assurance_history_series(destination)
            (destination / "extra.json").unlink()
            (destination / "series.json").write_text('{ "series_id": "tampered" }')
            with self.assertRaises(ValidationError):
                series.load_decision_assurance_history_series(destination)
            self.write_series(self.value, destination, overwrite=True)
            (destination / "series.json").write_text(json.dumps(json.loads((destination / "series.json").read_text()), indent=2))
            with self.assertRaises(ValidationError):
                series.load_decision_assurance_history_series(destination)

    def test_persistence_rejects_manifest_receipt_tamper_and_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "series"
            self.write_series(self.value, destination)
            manifest = json.loads((destination / "manifest.json").read_text())
            manifest["series_address"] = "series:tampered"
            (destination / "manifest.json").write_bytes(canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                series.load_decision_assurance_history_series(destination)
            self.write_series(self.value, destination, overwrite=True)
            target = destination / "series-link.json"
            try:
                target.symlink_to(destination / "series.json")
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            with self.assertRaises(ValidationError):
                series.load_decision_assurance_history_series(destination)

    def test_persistence_requires_empty_or_explicit_overwrite_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "series"
            destination.mkdir()
            (destination / "existing").write_text("x")
            with self.assertRaises(ValidationError):
                self.write_series(self.value, destination)
            self.write_series(self.value, destination, overwrite=True)
            self.assertEqual({item.name for item in destination.iterdir()}, set(series.FILES))


class SeriesRealDataTests(SeriesFixture):
    def test_downloaded_packet_can_drive_multiple_history_observations(self):
        first = self.ready_history("download:baseline")
        second = self.held_history("download:review")
        value = self.build_series((second, first), "download:series")
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "downloaded-series"
            self.write_series(value, destination)
            loaded = series.load_decision_assurance_history_series(destination)
            replay = series.replay_decision_assurance_history_series(loaded)
            self.assertTrue(replay.accepted)
            self.assertEqual(loaded.history_count, 2)
            self.assertEqual(loaded.observation_count, 2)
            payload = canonical_json(loaded.to_dict()).casefold()
            self.assertNotIn(str(self.real_packet()).casefold(), payload)
            self.assertNotIn("source_path", payload)


class SeriesCliTests(SeriesFixture):
    def test_cli_build_query_replay_verify_schema_and_capabilities(self):
        first = self.ready_history("cli:ready")
        second = self.held_history("cli:held")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first_dir = root / "first"
            second_dir = root / "second"
            destination = root / "series"
            self.write_history(first, first_dir)
            self.write_history(second, second_dir)
            base = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decisions-assurance-history-series"
            output = self.capture_cli([base, "--history", str(first_dir), "--history", str(second_dir), "--series-id", "cli:series", "--destination", str(destination), "--format", "summary"])
            self.assertIn('"history_count": 2', output)
            self.assertIn('"current_state": "mixed"', output)
            self.assertIn("series", self.capture_cli([base + "-query", "--input", str(destination), "--resource", "histories"]))
            self.assertIn('"accepted":true', self.capture_cli([base + "-replay", "--input", str(destination)]))
            self.assertIn('"history_count": 2', self.capture_cli([base + "-verify", "--input", str(destination)]))
            for command in ("assurance-history-series-schema", "assurance-history-series-entry-schema", "assurance-history-series-diff-schema", "assurance-history-series-diff-item-schema", "assurance-history-series-replay-schema", "assurance-history-series-query-schema", "assurance-history-series-capabilities", "assurance-history-series-replay-capabilities", "assurance-history-series-query-capabilities"):
                self.assertTrue(self.capture_cli([base.replace("assurance-history-series", command)]))

    def capture_cli(self, arguments):
        from contextlib import redirect_stdout
        from io import StringIO

        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(arguments), 0)
        return output.getvalue()


class SeriesApiTests(SeriesFixture):
    def test_api_serves_series_query_replay_verify_schemas_and_capabilities(self):
        value = self.build_series((self.ready_history("api:ready"), self.held_history("api:held")), "api:series")
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "series"
            self.write_series(value, destination)
            server = create_server("127.0.0.1", 0)
            server.glio_assurance_history_series_directory = str(destination)
            thread = self.start_server(server)
            try:
                base = f"http://127.0.0.1:{server.server_port}/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decisions/assurance-history-series"
                root = self.get_json(base)
                self.assertEqual(root["history_count"], 2)
                query = self.get_json(base + "/query?" + urlencode({"resource": "held"}))
                self.assertEqual(query["returned_count"], 1)
                self.assertTrue(self.get_json(base + "/replay")["accepted"])
                self.assertTrue(self.get_json(base + "/verify")["accepted"])
                for suffix in ("schema", "entry-schema", "diff/schema", "diff/item-schema", "replay/schema", "query/schema", "capabilities", "replay-capabilities", "query-capabilities"):
                    self.assertTrue(self.get_json(base + "/" + suffix))
                markdown = urlopen(base + "/query?format=markdown&resource=histories", timeout=10).read().decode()
                self.assertIn("# Federation Review Decision Assurance History Series Query", markdown)
            finally:
                server.shutdown()
                thread.join(timeout=10)

    def start_server(self, server):
        import threading

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return thread

    def get_json(self, url):
        return json.loads(urlopen(url, timeout=10).read().decode())


if __name__ == "__main__":
    unittest.main()
