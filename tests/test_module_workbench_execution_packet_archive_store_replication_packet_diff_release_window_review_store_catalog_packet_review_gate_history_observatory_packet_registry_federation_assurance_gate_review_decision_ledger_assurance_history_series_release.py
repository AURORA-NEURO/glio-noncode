"""Deep contracts for decision-assurance history-series release packages."""

# ruff: noqa: E501

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import (
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_decision_ledger_assurance_history_series_release as release,
)
from glio_noncode import (
    module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_decision_ledger_assurance_history_series_policy as policy,
)
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_bytes, canonical_json, hash_bytes
from tests.test_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_decision_ledger_assurance_history_series import SeriesFixture


class ReleaseFixture(SeriesFixture):
    def build_ready_series(self, series_id: str = "series:ready"):
        return self.build_series((self.ready_history("history:ready"),), series_id)

    def build_held_series(self, series_id: str = "series:held"):
        return self.build_series((self.held_history("history:held"),), series_id)

    def build_blocked_series(self, series_id: str = "series:blocked"):
        return self.build_series((self.blocked_history("history:blocked"),), series_id)

    @staticmethod
    def policy_value(policy_id: str = "policy:test", **updates):
        value = policy.default_decision_assurance_history_series_policy(policy_id=policy_id)
        body = value.to_dict()
        body.update(updates)
        body["content_address"] = "pending:release-policy"
        provisional = policy.DecisionAssuranceHistorySeriesPolicy(**body)
        body["content_address"] = policy.address_decision_assurance_history_series_policy(provisional)
        return policy.DecisionAssuranceHistorySeriesPolicy(**body)

    def ready_package(self, *, package_id: str = "package:ready", release_id: str = "release:ready"):
        return release.build_decision_assurance_history_series_release_package(self.build_ready_series(), package_id=package_id, release_id=release_id)

    def held_package(self, *, package_id: str = "package:held", release_id: str = "release:held"):
        series = self.build_held_series()
        selected_policy = self.policy_value(policy_id="policy:held", maximum_held_histories=0, require_current_release_ready=False)
        evaluation = self.evaluate_policy(series, selected_policy)
        return release.build_decision_assurance_history_series_release_package(series, selected_policy, evaluation, package_id=package_id, release_id=release_id)

    @staticmethod
    def evaluate_policy(series, selected_policy):
        return policy.evaluate_decision_assurance_history_series_policy(series, selected_policy)

    def blocked_package(self, *, package_id: str = "package:blocked", release_id: str = "release:blocked"):
        return release.build_decision_assurance_history_series_release_package(self.build_blocked_series(), package_id=package_id, release_id=release_id)

    @staticmethod
    def write_package(value, destination, **kwargs):
        return release.write_decision_assurance_history_series_release_package(value, destination, **kwargs)

    @staticmethod
    def write_diff(value, destination, **kwargs):
        return release.write_decision_assurance_history_series_release_diff(value, destination, **kwargs)


class ReleaseCoreTests(ReleaseFixture):
    def test_ready_package_has_eight_passed_stages_and_is_release_ready(self):
        value = self.ready_package()
        self.assertEqual(value.release.stage_count, 8)
        self.assertEqual(value.release.passed_count, 8)
        self.assertEqual(value.release.warning_count, 0)
        self.assertEqual(value.release.blocker_count, 0)
        self.assertEqual(value.release.state, "ready")
        self.assertTrue(value.release.accepted)
        self.assertTrue(value.release.release_ready)
        self.assertEqual(value.release.series_address, value.series.content_address)
        self.assertEqual(value.release.policy_address, value.policy.content_address)
        self.assertEqual(value.release.evaluation_address, value.evaluation.content_address)
        self.assertEqual(release.address_decision_assurance_history_series_release(value.release), value.release.content_address)
        self.assertEqual(release.address_decision_assurance_history_series_release_package(value), value.content_address)

    def test_each_stage_is_contiguous_addressable_and_has_fixed_state_projection(self):
        value = self.ready_package()
        self.assertEqual([stage.ordinal for stage in value.release.stages], list(range(8)))
        self.assertEqual([stage.state for stage in value.release.stages], ["passed"] * 8)
        self.assertEqual(len({stage.stage_id for stage in value.release.stages}), 8)
        self.assertEqual(len({stage.content_address for stage in value.release.stages}), 8)
        for stage in value.release.stages:
            self.assertEqual(release.address_decision_assurance_history_series_release_stage(stage), stage.content_address)
            self.assertEqual(stage.evidence_address.startswith("pending:"), False)

    def test_ready_package_public_projection_is_path_free_and_identity_free(self):
        value = self.ready_package()
        payload = canonical_json(value.to_dict()).casefold()
        for forbidden in ("source_path", "filesystem", "agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"):
            self.assertNotIn(f'"{forbidden}"', payload)
        self.assertNotIn("c:\\", payload)
        self.assertNotIn("/users/", payload)

    def test_package_mapping_round_trip_preserves_nested_components(self):
        value = self.ready_package()
        restored = release.DecisionAssuranceHistorySeriesReleasePackage(
            package_id=value.package_id,
            version=value.version,
            boundary=value.boundary,
            series=value.series,
            policy=value.policy,
            evaluation=value.evaluation,
            release=value.release,
            content_address=value.content_address,
        )
        self.assertEqual(restored.to_dict(), value.to_dict())
        self.assertEqual(release.verify_decision_assurance_history_series_release_package(restored).content_address, value.content_address)
        mapped_release = release.decision_assurance_history_series_release_from_mapping(value.release.to_dict())
        self.assertEqual(mapped_release.to_dict(), value.release.to_dict())

    def test_package_address_changes_when_release_identity_changes(self):
        first = self.ready_package(package_id="package:first", release_id="release:first")
        second = self.ready_package(package_id="package:second", release_id="release:first")
        third = self.ready_package(package_id="package:first", release_id="release:second")
        self.assertNotEqual(first.content_address, second.content_address)
        self.assertNotEqual(first.content_address, third.content_address)
        self.assertEqual(first.series.content_address, second.series.content_address)
        self.assertEqual(first.evaluation.content_address, second.evaluation.content_address)

    def test_held_and_blocked_evaluations_produce_distinct_release_states(self):
        held = self.held_package()
        blocked = self.blocked_package()
        self.assertEqual(held.release.state, "hold")
        self.assertTrue(held.release.accepted)
        self.assertFalse(held.release.release_ready)
        self.assertEqual(held.release.blocker_count, 0)
        self.assertGreater(held.release.warning_count, 0)
        self.assertEqual(blocked.release.state, "blocked")
        self.assertFalse(blocked.release.accepted)
        self.assertFalse(blocked.release.release_ready)
        self.assertGreater(blocked.release.blocker_count, 0)
        self.assertEqual(blocked.release.stages[4].kind, "evaluation-acceptance")

    def test_direct_stage_and_release_validation_rejects_tampering(self):
        value = self.ready_package()
        stage = value.release.stages[0].to_dict()
        stage["detail"] = "tampered"
        stage["content_address"] = value.release.stages[0].content_address
        with self.assertRaises(ValidationError):
            release.decision_assurance_history_series_release_stage_from_mapping(stage)
        body = value.release.to_dict()
        body["passed_count"] = 7
        with self.assertRaises(ValidationError):
            release.decision_assurance_history_series_release_from_mapping(body)
        package_body = value.to_dict()
        package_body["private"] = True
        with self.assertRaises((ValidationError, TypeError)):
            release.DecisionAssuranceHistorySeriesReleasePackage(**package_body)

    def test_unknown_fields_are_rejected_at_release_mapping_boundaries(self):
        value = self.ready_package()
        body = value.release.to_dict()
        body["unknown"] = True
        with self.assertRaises(ValidationError):
            release.decision_assurance_history_series_release_from_mapping(body)
        body = value.release.stages[0].to_dict()
        body["unknown"] = True
        with self.assertRaises(ValidationError):
            release.decision_assurance_history_series_release_stage_from_mapping(body)
        body = value.release.to_dict()
        body["stages"][0]["state"] = "hold"
        with self.assertRaises(ValidationError):
            release.decision_assurance_history_series_release_from_mapping(body)


class ReleaseQueryExportTests(ReleaseFixture):
    def test_release_queries_cover_summary_stage_failure_and_severity_resources(self):
        value = self.held_package().release
        summary = release.query_decision_assurance_history_series_release(value)
        self.assertEqual(summary.total_count, 1)
        self.assertEqual(summary.items[0]["release_id"], value.release_id)
        stages = release.query_decision_assurance_history_series_release(value, resource="stages", limit=32)
        self.assertEqual(stages.total_count, value.stage_count)
        failed = release.query_decision_assurance_history_series_release(value, resource="failed", limit=32)
        self.assertEqual(failed.total_count, value.warning_count + value.blocker_count)
        warnings = release.query_decision_assurance_history_series_release(value, resource="warnings", limit=32)
        blockers = release.query_decision_assurance_history_series_release(self.blocked_package().release, resource="blockers", limit=32)
        self.assertEqual(warnings.total_count, value.warning_count)
        self.assertGreater(blockers.total_count, 0)
        self.assertEqual(stages.items[0]["ordinal"], 0)

    def test_release_queries_are_bounded_addressed_and_text_filterable(self):
        value = self.ready_package().release
        page = release.query_decision_assurance_history_series_release(value, resource="stages", offset=1, limit=2, text="verification")
        self.assertLessEqual(page.returned_count, 2)
        self.assertEqual(page.returned_count, len(page.items))
        self.assertEqual(release.address_decision_assurance_history_series_release_query(page), page.content_address)
        with self.assertRaises(ValidationError):
            release.SeriesReleaseQuery(resource="unknown")
        with self.assertRaises(ValidationError):
            release.SeriesReleaseQuery(resource="stages", limit=0)
        with self.assertRaises(ValidationError):
            release.query_decision_assurance_history_series_release(value, release.SeriesReleaseQuery(resource="stages"), limit=2)

    def test_release_json_csv_and_markdown_are_deterministic(self):
        value = self.ready_package().release
        self.assertEqual(release.decision_assurance_history_series_release_json(value), release.decision_assurance_history_series_release_json(value))
        csv_text = release.decision_assurance_history_series_release_csv(value)
        self.assertEqual(len(csv_text.splitlines()), value.stage_count + 1)
        self.assertTrue(csv_text.startswith("ordinal,stage_id,kind,required,passed,state,detail,evidence_address,content_address\n"))
        markdown = release.render_decision_assurance_history_series_release_markdown(value)
        self.assertLess(markdown.index("## Summary"), markdown.index("## Records"))
        self.assertIn("transport-contract", markdown)
        self.assertEqual(markdown, release.render_decision_assurance_history_series_release_markdown(value))

    def test_package_exports_include_full_nested_components(self):
        value = self.ready_package()
        rendered = release.decision_assurance_history_series_release_package_json(value)
        body = json.loads(rendered)
        self.assertEqual(body["series"]["series_id"], value.series.series_id)
        self.assertEqual(body["policy"]["policy_id"], value.policy.policy_id)
        self.assertEqual(body["evaluation"]["content_address"], value.evaluation.content_address)
        self.assertEqual(body["release"]["release_id"], value.release.release_id)
        self.assertEqual(rendered.encode(), canonical_bytes(body))
        self.assertEqual(len(release.decision_assurance_history_series_release_package_csv(value).splitlines()), 2)
        self.assertIn("Release Package", release.render_decision_assurance_history_series_release_package_markdown(value))

    def test_schemas_and_capabilities_describe_the_transport_contract(self):
        capabilities = release.capabilities()
        self.assertEqual(capabilities["version"], release.VERSION if hasattr(release, "VERSION") else capabilities["version"])
        self.assertEqual(capabilities["package"]["files"], list(release.FILES))
        self.assertEqual(capabilities["diff"]["actions"], [item.value for item in release.SeriesReleaseDiffAction])
        self.assertEqual(set(release.decision_assurance_history_series_release_schema()["required"]), {"release_id", "version", "boundary", "series_id", "series_address", "policy_id", "policy_address", "evaluation_address", "stage_count", "state", "accepted", "release_ready", "stages", "content_address"})
        self.assertFalse(release.decision_assurance_history_series_release_stage_schema()["additionalProperties"])
        self.assertIn("release", release.decision_assurance_history_series_release_package_schema()["properties"])
        self.assertIn("resource", release.decision_assurance_history_series_release_query_schema()["properties"])


class ReleasePersistenceTests(ReleaseFixture):
    def test_package_persistence_has_exact_five_files_and_round_trips(self):
        value = self.ready_package()
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "release"
            self.write_package(value, destination)
            self.assertEqual({item.name for item in destination.iterdir()}, set(release.FILES))
            loaded = release.load_decision_assurance_history_series_release_package(destination)
            self.assertEqual(loaded.to_dict(), value.to_dict())
            self.assertEqual(release.verify_decision_assurance_history_series_release_package_directory(destination).content_address, value.content_address)

    def test_package_persistence_is_repeatable_and_receipts_are_exact(self):
        value = self.ready_package()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first"
            second = root / "second"
            self.write_package(value, first)
            self.write_package(value, second)
            for name in release.FILES:
                self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())
            manifest = json.loads((first / release.MANIFEST_NAME).read_text())
            self.assertEqual(manifest["artifact_count"], 4)
            self.assertEqual(tuple(manifest["files"]), release.FILES)
            for artifact in manifest["artifacts"]:
                raw = (first / artifact["name"]).read_bytes()
                self.assertEqual(artifact["bytes"], len(raw))
                self.assertEqual(artifact["byte_address"], hash_bytes(raw))
                self.assertEqual(canonical_bytes(json.loads(raw.decode())), raw)

    def test_package_persistence_rejects_noncanonical_missing_extra_and_tampered_files(self):
        value = self.ready_package()
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "release"
            self.write_package(value, destination)
            (destination / release.RELEASE_NAME).write_text('{"tampered": true}')
            with self.assertRaises(ValidationError):
                release.load_decision_assurance_history_series_release_package(destination)
            self.write_package(value, destination, overwrite=True)
            (destination / "extra.json").write_text("x")
            with self.assertRaises(ValidationError):
                release.load_decision_assurance_history_series_release_package(destination)
            (destination / "extra.json").unlink()
            (destination / release.MANIFEST_NAME).write_bytes(canonical_bytes({"version": "tampered"}))
            with self.assertRaises(ValidationError):
                release.load_decision_assurance_history_series_release_package(destination)

    def test_package_persistence_rejects_symlinks_and_nonempty_without_overwrite(self):
        value = self.ready_package()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "release"
            destination.mkdir()
            (destination / "existing").write_text("x")
            with self.assertRaises(ValidationError):
                self.write_package(value, destination)
            self.write_package(value, destination, overwrite=True)
            link_destination = root / "link"
            try:
                link_destination.symlink_to(destination, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            with self.assertRaises(ValidationError):
                self.write_package(value, link_destination)

    def test_directory_builder_can_use_a_persisted_series_and_policy_evaluation(self):
        value = self.ready_package()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            series_directory = root / "series"
            evaluation_directory = root / "evaluation"
            self.write_series(value.series, series_directory)
            from glio_noncode import (
                module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_decision_ledger_assurance_history_series_policy as policy,
            )

            policy.write_decision_assurance_history_series_policy_evaluation(value.evaluation, evaluation_directory)
            rebuilt = release.build_decision_assurance_history_series_release_package_from_directories(series_directory, evaluation_directory, package_id="package:directory", release_id="release:directory")
            self.assertEqual(rebuilt.series.content_address, value.series.content_address)
            self.assertEqual(rebuilt.policy.content_address, value.policy.content_address)
            self.assertEqual(rebuilt.evaluation.content_address, value.evaluation.content_address)
            self.assertEqual(rebuilt.release.state, "ready")


class ReleaseDiffTests(ReleaseFixture):
    def test_identical_releases_have_unchanged_diff_and_release_ready_state(self):
        value = self.ready_package().release
        diff = release.build_decision_assurance_history_series_release_diff(value, value, diff_id="diff:identical")
        self.assertEqual(diff.state, "unchanged")
        self.assertTrue(diff.accepted)
        self.assertTrue(diff.release_ready)
        self.assertEqual(diff.unchanged_count, diff.item_count)
        self.assertEqual(diff.improved_count, 0)
        self.assertEqual(diff.regressed_count, 0)
        self.assertEqual(release.address_decision_assurance_history_series_release_diff(diff), diff.content_address)

    def test_hold_to_ready_diff_is_improved_and_ready(self):
        baseline = self.held_package().release
        candidate = self.ready_package().release
        diff = release.build_decision_assurance_history_series_release_diff(baseline, candidate, diff_id="diff:improved")
        self.assertEqual(diff.state, "improved")
        self.assertTrue(diff.accepted)
        self.assertTrue(diff.release_ready)
        self.assertGreater(diff.improved_count, 0)
        self.assertEqual(diff.regressed_count, 0)
        self.assertEqual(diff.baseline_address, baseline.content_address)
        self.assertEqual(diff.candidate_address, candidate.content_address)

    def test_ready_to_blocked_diff_is_regressed_and_not_release_ready(self):
        baseline = self.ready_package().release
        candidate = self.blocked_package().release
        diff = release.build_decision_assurance_history_series_release_diff(baseline, candidate, diff_id="diff:regressed")
        self.assertEqual(diff.state, "regressed")
        self.assertFalse(diff.accepted)
        self.assertFalse(diff.release_ready)
        self.assertGreater(diff.regressed_count, 0)

    def test_diff_contains_release_and_stage_keys_with_conserved_actions(self):
        diff = release.build_decision_assurance_history_series_release_diff(self.held_package().release, self.ready_package().release)
        keys = {item.key for item in diff.items}
        self.assertIn("release", keys)
        self.assertEqual(len(keys), 9)
        self.assertEqual(diff.added_count + diff.removed_count + diff.unchanged_count + diff.changed_count, diff.item_count)
        self.assertEqual(diff.item_count, len(diff.items))
        self.assertEqual([item.ordinal for item in diff.items], list(range(diff.item_count)))

    def test_diff_mapping_rejects_tampered_action_direction_or_receipt(self):
        value = release.build_decision_assurance_history_series_release_diff(self.held_package().release, self.ready_package().release)
        body = value.to_dict()
        body["items"][0]["action"] = "added"
        with self.assertRaises(ValidationError):
            release.decision_assurance_history_series_release_diff_from_mapping(body)
        body = value.to_dict()
        body["items"][0]["direction"] = "regressed"
        with self.assertRaises(ValidationError):
            release.decision_assurance_history_series_release_diff_from_mapping(body)
        body = value.to_dict()
        body["content_address"] = "diff:tampered"
        with self.assertRaises(ValidationError):
            release.decision_assurance_history_series_release_diff_from_mapping(body)

    def test_diff_queries_and_exports_are_deterministic(self):
        value = release.build_decision_assurance_history_series_release_diff(self.held_package().release, self.ready_package().release)
        improved = release.query_decision_assurance_history_series_release_diff(value, resource="improved", limit=64)
        self.assertEqual(improved.total_count, value.improved_count)
        summary = release.query_decision_assurance_history_series_release_diff(value)
        self.assertEqual(summary.total_count, 1)
        self.assertEqual(release.address_decision_assurance_history_series_release_diff_query(improved), improved.content_address)
        self.assertTrue(release.decision_assurance_history_series_release_diff_json(value).startswith("{"))
        self.assertEqual(len(release.decision_assurance_history_series_release_diff_csv(value).splitlines()), value.item_count + 1)
        self.assertIn("Release Diff", release.render_decision_assurance_history_series_release_diff_markdown(value))
        with self.assertRaises(ValidationError):
            release.SeriesReleaseDiffQuery(resource="invalid")

    def test_diff_persistence_has_exact_two_files_and_round_trips(self):
        value = release.build_decision_assurance_history_series_release_diff(self.held_package().release, self.ready_package().release, diff_id="diff:persisted")
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "diff"
            self.write_diff(value, destination)
            self.assertEqual({item.name for item in destination.iterdir()}, set(release.DIFF_FILES))
            loaded = release.load_decision_assurance_history_series_release_diff(destination)
            self.assertEqual(loaded.to_dict(), value.to_dict())
            manifest = json.loads((destination / release.MANIFEST_NAME).read_text())
            self.assertEqual(manifest["artifact_count"], 1)
            self.assertEqual(manifest["artifacts"][0]["byte_address"], hash_bytes((destination / release.DIFF_NAME).read_bytes()))


class ReleaseCliApiTests(ReleaseFixture):
    base = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-series-release"

    @staticmethod
    def capture_cli(arguments):
        from contextlib import redirect_stdout
        from io import StringIO

        output = StringIO()
        with redirect_stdout(output):
            status = main(arguments)
        return status, output.getvalue()

    def test_cli_builds_queries_verifies_schemas_capabilities_and_diff(self):
        first = self.ready_package(package_id="package:cli-first", release_id="release:cli-first")
        second = self.held_package(package_id="package:cli-second", release_id="release:cli-second")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first_directory = root / "first"
            second_directory = root / "second"
            diff_directory = root / "diff"
            self.write_package(first, first_directory)
            self.write_package(second, second_directory)
            status, output = self.capture_cli([self.base, "--input", str(first_directory), "--destination", str(root / "cli-release"), "--format", "summary"])
            self.assertEqual(status, 0)
            self.assertIn('"state": "ready"', output)
            status, output = self.capture_cli([self.base + "-verify", "--input", str(root / "cli-release")])
            self.assertEqual(status, 0)
            self.assertIn('"release_ready": true', output)
            status, output = self.capture_cli([self.base + "-query", "--input", str(root / "cli-release"), "--resource", "stages"])
            self.assertEqual(status, 0)
            self.assertIn('"returned_count": 8', output)
            status, output = self.capture_cli([self.base + "-diff", "--baseline", str(first_directory), "--candidate", str(second_directory), "--format", "summary", "--output", str(diff_directory)])
            self.assertEqual(status, 0)
            self.assertTrue((diff_directory / release.DIFF_NAME).is_file())
            status, output = self.capture_cli([self.base + "-diff-verify", "--input", str(diff_directory)])
            self.assertEqual(status, 0)
            self.assertIn('"state": "regressed"', output)
            for suffix in ("-schema", "-stage-schema", "-package-schema", "-query-schema", "-capabilities", "-diff-schema", "-diff-item-schema", "-diff-query-schema"):
                status, output = self.capture_cli([self.base + suffix])
                self.assertEqual(status, 0)
                self.assertTrue(output.strip())

    def test_api_reads_release_package_queries_verifies_and_reads_diff(self):
        value = self.ready_package(package_id="package:api", release_id="release:api")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package_directory = root / "package"
            diff_directory = root / "diff"
            self.write_package(value, package_directory)
            diff = release.build_decision_assurance_history_series_release_diff(value.release, self.held_package().release, diff_id="diff:api")
            self.write_diff(diff, diff_directory)
            server = create_server("127.0.0.1", 0)
            server.glio_assurance_history_series_release_directory = str(package_directory)
            server.glio_assurance_history_series_release_diff_directory = str(diff_directory)
            import threading

            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release"
                summary = json.loads(urlopen(base + "?format=summary", timeout=10).read().decode())
                self.assertEqual(summary["state"], "ready")
                stages = json.loads(urlopen(base + "/query?" + urlencode({"resource": "stages"}), timeout=10).read().decode())
                self.assertEqual(stages["returned_count"], 8)
                verified = json.loads(urlopen(base + "/verify", timeout=10).read().decode())
                self.assertTrue(verified["release_ready"])
                diff_summary = json.loads(urlopen(base + "/diff?format=summary", timeout=10).read().decode())
                self.assertEqual(diff_summary["state"], "regressed")
                schema = json.loads(urlopen(base + "/schema", timeout=10).read().decode())
                self.assertFalse(schema["additionalProperties"])
                capabilities = json.loads(urlopen(base + "/capabilities", timeout=10).read().decode())
                self.assertEqual(capabilities["package"]["files"], list(release.FILES))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)


class ReleaseBoundaryMatrixTests(ReleaseFixture):
    def test_release_state_matrix_matches_required_and_optional_failures(self):
        ready = self.ready_package().release
        held = self.held_package().release
        blocked = self.blocked_package().release
        self.assertEqual((ready.accepted, ready.release_ready, ready.state), (True, True, "ready"))
        self.assertEqual((held.accepted, held.release_ready, held.state), (True, False, "hold"))
        self.assertEqual((blocked.accepted, blocked.release_ready, blocked.state), (False, False, "blocked"))
        for value in (ready, held, blocked):
            self.assertEqual(value.passed_count + value.warning_count + value.blocker_count, value.stage_count)
            self.assertEqual(value.accepted, value.blocker_count == 0)
            self.assertEqual(value.release_ready, value.blocker_count == 0 and value.warning_count == 0)

    def test_package_loader_rejects_directory_and_file_inputs(self):
        value = self.ready_package()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ValidationError):
                release.load_decision_assurance_history_series_release_package(root / "missing")
            file_path = root / "file"
            file_path.write_text("x")
            with self.assertRaises(ValidationError):
                release.load_decision_assurance_history_series_release_package(file_path)
            self.write_package(value, root / "release")
            self.assertTrue(release.load_decision_assurance_history_series_release_package(root / "release").release.release_ready)

    def test_release_package_and_diff_exports_do_not_accept_invalid_typed_values(self):
        value = self.ready_package()
        release_body = value.release.to_dict()
        release_body["stages"] = value.release.stages
        release_body["content_address"] = "pending:tampered"
        tampered = release.DecisionAssuranceHistorySeriesRelease(**release_body)
        tampered.content_address = "release:tampered"
        for renderer in (release.decision_assurance_history_series_release_json, release.decision_assurance_history_series_release_csv, release.render_decision_assurance_history_series_release_markdown):
            with self.subTest(renderer=renderer.__name__), self.assertRaises(ValidationError):
                renderer(tampered)


if __name__ == "__main__":
    unittest.main()
