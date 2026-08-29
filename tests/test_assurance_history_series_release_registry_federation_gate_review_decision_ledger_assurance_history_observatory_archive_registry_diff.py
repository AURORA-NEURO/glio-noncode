"""Deep contracts for verified observatory archive registry diffs."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry as registry
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff as diff
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry import RegistryFixture


class DiffFixture(RegistryFixture):
    """Build both sides through the verified archive-registry boundary."""

    DIFF_COMMAND = RegistryFixture.REGISTRY_COMMAND + "-diff"

    def one_registry(self, root: Path, name: str, *, state: str = "ready", registry_id: str | None = None) -> registry.ObservatoryArchiveRegistry:
        source = self.archive_file(root, name, (f"source:{name}:a", f"source:{name}:b"), state=state)
        return registry.build_registry_from_archive_files((source,), entry_ids=("entry:0",), registry_id=registry_id or "registry:" + name)

    def assert_public(self, value) -> None:
        payload = value.to_dict() if hasattr(value, "to_dict") else value
        rendered = canonical_json(payload)
        self.assertNotIn("C:\\", rendered)
        self.assertNotIn("/Users/", rendered)
        forbidden = {"agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"}

        def walk(node):
            if isinstance(node, dict):
                for key, item in node.items():
                    self.assertNotIn(key.lower(), forbidden)
                    walk(item)
            elif isinstance(node, (list, tuple)):
                for item in node:
                    walk(item)

        walk(payload)


class RegistryDiffBuildTests(DiffFixture):
    def test_identical_registry_is_unchanged_and_deterministic(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.one_registry(Path(temporary), "same")
            first = diff.build_diff(value, value)
            second = diff.build_diff(value, value)
            self.assertEqual(first.to_dict(), second.to_dict())
            self.assertEqual(first.state, diff.RegistryDiffState.UNCHANGED.value)
            self.assertEqual(first.item_count, 1)
            self.assertEqual(first.unchanged_count, 1)
            self.assertEqual(first.registry_changed_fields, ())
            self.assertEqual(first.items[0].action, diff.RegistryDiffAction.UNCHANGED.value)
            self.assertEqual(diff.address_diff(first), first.content_address)
            self.assert_public(first)

    def test_entry_membership_classifies_added_and_removed_keys(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = self.one_registry(root, "baseline")
            candidate = self.one_registry(root, "candidate")
            baseline_entry = registry.entry_from_archive_file(self.archive_file(root, "removed", ("source:removed:a", "source:removed:b")), entry_id="entry:removed")
            candidate_entry = registry.entry_from_archive_file(self.archive_file(root, "added", ("source:added:a", "source:added:b")), entry_id="entry:added")
            baseline = registry.build_registry((baseline.entries[0], baseline_entry), registry_id="registry:membership-baseline")
            candidate = registry.build_registry((candidate.entries[0], candidate_entry), registry_id="registry:membership-candidate")
            value = diff.build_diff(baseline, candidate)
            actions = {item.entry_id: item.action for item in value.items}
            self.assertEqual(actions["entry:0"], diff.RegistryDiffAction.CHANGED.value)
            self.assertEqual(actions["entry:added"], diff.RegistryDiffAction.ADDED.value)
            self.assertEqual(actions["entry:removed"], diff.RegistryDiffAction.REMOVED.value)
            self.assertEqual(value.added_count, 1)
            self.assertEqual(value.removed_count, 1)
            self.assertEqual(value.changed_count, 1)
            self.assertEqual(value.unchanged_count, 0)
            self.assertEqual(tuple(item.ordinal for item in value.items), (1, 2, 3))

    def test_changed_entry_exposes_exact_changed_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            baseline = self.one_registry(Path(temporary), "field-baseline")
            original = baseline.entries[0]
            modified = registry.RegistryEntry(original.entry_id, original.archive_id, original.archive_address, original.observatory_id, original.observatory_address, original.verification_address, original.archive_size + 1, original.state, original.accepted, original.release_ready, original.member_count, original.observatory_entry_count, original.finding_count, original.check_count, "pending:entry")
            modified.content_address = registry.address_entry(modified)
            candidate = registry.build_registry((modified,), registry_id=baseline.registry_id)
            value = diff.build_diff(baseline, candidate)
            item = value.items[0]
            self.assertEqual(item.action, diff.RegistryDiffAction.CHANGED.value)
            self.assertEqual(item.changed_fields, ("archive_size", "content_address"))
            self.assertIn("archive_size, content_address", item.detail)
            self.assertEqual(value.registry_changed_fields, ("metrics", "verification_address"))
            self.assertEqual(value.state, diff.RegistryDiffState.MIXED.value)

    def test_state_and_readiness_transition_regresses(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = self.one_registry(root, "ready", state="ready")
            candidate = self.one_registry(root, "held", state="held")
            value = diff.build_diff(baseline, candidate)
            self.assertEqual(value.baseline_state, registry.RegistryState.READY.value)
            self.assertEqual(value.candidate_state, registry.RegistryState.HELD.value)
            self.assertTrue(value.baseline_release_ready)
            self.assertFalse(value.candidate_release_ready)
            self.assertEqual(value.state, diff.RegistryDiffState.REGRESSED.value)
            item = value.items[0]
            self.assertEqual(item.action, diff.RegistryDiffAction.CHANGED.value)
            self.assertIn("state", item.changed_fields)
            self.assertIn("release_ready", item.changed_fields)

    def test_aggregate_registry_change_is_visible_even_when_entries_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            baseline = self.one_registry(Path(temporary), "aggregate", registry_id="registry:baseline")
            candidate = registry.build_registry(baseline.entries, registry_id="registry:candidate")
            value = diff.build_diff(baseline, candidate)
            self.assertEqual(value.item_count, 1)
            self.assertEqual(value.unchanged_count, 1)
            self.assertEqual(value.registry_changed_fields, ("registry_id", "verification_address"))
            self.assertEqual(value.state, diff.RegistryDiffState.MIXED.value)
            changes = diff.query_diff(value, resource="registry-changes")
            self.assertEqual(changes.total_count, 1)
            self.assertEqual(changes.records[0]["changed_fields"], ("registry_id", "verification_address"))

    def test_directory_builder_loads_both_exact_registry_packages(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = self.one_registry(root, "directory-baseline")
            candidate = self.one_registry(root, "directory-candidate")
            baseline_dir = root / "baseline-registry"
            candidate_dir = root / "candidate-registry"
            registry.write_registry(baseline, baseline_dir)
            registry.write_registry(candidate, candidate_dir)
            value = diff.build_diff_from_directories(baseline_dir, candidate_dir, diff_id="diff:directories")
            self.assertEqual(value.diff_id, "diff:directories")
            self.assertEqual(value.baseline_address, baseline.content_address)
            self.assertEqual(value.candidate_address, candidate.content_address)

    def test_mapping_round_trip_reproduces_exact_address(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = diff.build_diff(self.one_registry(Path(temporary), "mapping"), self.one_registry(Path(temporary), "mapping-candidate"))
            loaded = diff.diff_from_mapping(value.to_dict())
            self.assertEqual(loaded.to_dict(), value.to_dict())
            self.assertEqual(diff.diff_json(loaded), diff.diff_json(value))
            self.assertEqual(diff.verify_diff(loaded), loaded)
            self.assert_public(loaded)


class RegistryDiffQueryTests(DiffFixture):
    def test_each_query_resource_is_bounded_and_addressable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = self.one_registry(root, "query-baseline")
            candidate = self.one_registry(root, "query-candidate")
            value = diff.build_diff(baseline, candidate)
            for resource in diff.RegistryDiffQuery.RESOURCES:
                result = diff.query_diff(value, resource=resource)
                self.assertLessEqual(result.returned_count, result.total_count)
                self.assertEqual(diff.address_query(result), result.content_address)
                self.assert_public(result)

    def test_action_state_and_readiness_filters_are_deterministic(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = self.one_registry(root, "filter-ready", state="ready")
            candidate = self.one_registry(root, "filter-held", state="held")
            value = diff.build_diff(baseline, candidate)
            self.assertEqual(diff.query_diff(value, resource="changed").total_count, 1)
            self.assertEqual(diff.query_diff(value, resource="changed", action="changed").total_count, 1)
            self.assertEqual(diff.query_diff(value, resource="state-transitions").total_count, 1)
            self.assertEqual(diff.query_diff(value, resource="readiness-transitions").total_count, 1)
            self.assertEqual(diff.query_diff(value, resource="added").total_count, 0)
            first = diff.query_diff(value, resource="items", offset=0, limit=1)
            second = diff.query_diff(value, resource="items", offset=1, limit=1)
            self.assertEqual(first.returned_count, 1)
            self.assertEqual(second.returned_count, 0)
            self.assertNotEqual(first.content_address, second.content_address)

    def test_query_object_and_keyword_filters_match(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = diff.build_diff(self.one_registry(Path(temporary), "object-a"), self.one_registry(Path(temporary), "object-b"))
            query = diff.RegistryDiffQuery(resource="changed", action="changed", limit=4)
            first = diff.query_diff(value, query)
            second = diff.query_diff(value, resource="changed", action="changed", limit=4)
            self.assertEqual(first.to_dict(), second.to_dict())
            with self.assertRaises(ValidationError):
                diff.query_diff(value, query, resource="items")

    def test_query_result_mapping_and_renderers_are_exact(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = diff.build_diff(self.one_registry(Path(temporary), "render-a"), self.one_registry(Path(temporary), "render-b"))
            result = diff.query_diff(value, resource="items")
            loaded = diff.query_result_from_mapping(result.to_dict())
            self.assertEqual(loaded.to_dict(), result.to_dict())
            self.assertIn("entry_id", diff.diff_query_csv(result))
            self.assertIn("Registry Diff Query", diff.render_query_markdown(result))
            self.assertIn("Registry Diff", diff.render_markdown(value))
            self.assertTrue(diff.diff_json(value).startswith("{"))
            self.assertGreater(len(diff.diff_csv(value).splitlines()), 1)

    def test_query_and_renderers_reject_plain_values_or_invalid_filters(self):
        with self.assertRaises(ValidationError):
            diff.diff_json({})
        with self.assertRaises(ValidationError):
            diff.diff_query_json({})
        with self.assertRaises(ValidationError):
            diff.RegistryDiffQuery(resource="invalid")
        with self.assertRaises(ValidationError):
            diff.RegistryDiffQuery(action="invalid")
        with self.assertRaises(ValidationError):
            diff.RegistryDiffQuery(limit=0)

    def test_schema_and_capabilities_are_closed_and_public(self):
        for schema in (diff.diff_item_schema(), diff.diff_schema(), diff.query_schema(), diff.query_result_schema()):
            self.assertFalse(schema["additionalProperties"])
            self.assertIn("required", schema)
            self.assert_public(schema)
        capabilities = diff.capabilities()
        self.assertEqual(tuple(capabilities["actions"]), tuple(item.value for item in diff.RegistryDiffAction))
        self.assertEqual(tuple(capabilities["resources"]), diff.RegistryDiffQuery.RESOURCES)
        self.assert_public(capabilities)


class RegistryDiffTamperAndBoundaryTests(DiffFixture):
    def test_diff_mapping_rejects_unknown_private_and_forged_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = diff.build_diff(self.one_registry(Path(temporary), "tamper-a"), self.one_registry(Path(temporary), "tamper-b"))
            document = value.to_dict()
            with self.assertRaises(ValidationError):
                diff.diff_from_mapping(document | {"private": "secret"})
            with self.assertRaises(ValidationError):
                diff.diff_from_mapping(document | {"source_path": "C:\\private"})
            forged = dict(document)
            forged["content_address"] = diff.DIFF_PREFIX + ":forged"
            with self.assertRaises(ValidationError):
                diff.diff_from_mapping(forged)

    def test_item_mapping_rejects_wrong_action_sides_or_address(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = diff.build_diff(self.one_registry(Path(temporary), "item-a"), self.one_registry(Path(temporary), "item-b"))
            item = value.items[0].to_dict()
            with self.assertRaises(ValidationError):
                diff.RegistryDiffItem.from_mapping(item | {"action": "added"})
            with self.assertRaises(ValidationError):
                diff.RegistryDiffItem.from_mapping(item | {"content_address": diff.DIFF_ITEM_PREFIX + ":forged"})
            with self.assertRaises(ValidationError):
                diff.RegistryDiffItem.from_mapping(item | {"changed_fields": ("unknown",)})

    def test_diff_rejects_non_typed_registries_and_bad_result_windows(self):
        with self.assertRaises(ValidationError):
            diff.build_diff({}, {})
        query = diff.RegistryDiffQuery(resource="items", limit=1)
        with self.assertRaises(ValidationError):
            diff.RegistryDiffQueryResult(diff.DIFF_PREFIX + ":address", query, 2, ({"entry_id": "one"}, {"entry_id": "two"}), "pending:query")

    def test_real_downloaded_registry_self_diff_is_verified_when_present(self):
        source = Path(tempfile.gettempdir()) / "glio-noncode-history-observatory-demo-current" / "registry-v1"
        if not source.is_dir():
            self.skipTest("the optional local downloaded-data demo is not present")
        value = diff.build_diff_from_directories(source, source)
        self.assertEqual(value.state, diff.RegistryDiffState.UNCHANGED.value)
        self.assertEqual(value.item_count, 1)
        self.assertEqual(value.unchanged_count, 1)
        self.assertEqual(diff.verify_diff(value).content_address, value.content_address)


class RegistryDiffCliAndApiTests(DiffFixture):
    def server(self):
        from glio_noncode.api import create_server

        server = create_server("127.0.0.1", 0)
        import threading

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def test_cli_build_query_and_schema_contract(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = self.one_registry(root, "cli-baseline")
            candidate = self.one_registry(root, "cli-candidate")
            baseline_dir = root / "baseline"
            candidate_dir = root / "candidate"
            registry.write_registry(baseline, baseline_dir)
            registry.write_registry(candidate, candidate_dir)
            output = root / "diff.json"
            self.assertEqual(main([self.DIFF_COMMAND, "--baseline", str(baseline_dir), "--candidate", str(candidate_dir), "--format", "json", "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["item_count"], 1)
            self.assertEqual(main([self.DIFF_COMMAND + "-query", "--baseline", str(baseline_dir), "--candidate", str(candidate_dir), "--resource", "items", "--format", "csv"]), 0)
            self.assertEqual(main([self.DIFF_COMMAND + "-schema"]), 0)
            self.assertEqual(main([self.DIFF_COMMAND + "-capabilities"]), 0)

    def test_http_diff_query_schema_and_capabilities_routes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = self.one_registry(root, "http-baseline")
            candidate = self.one_registry(root, "http-candidate")
            baseline_dir = root / "baseline"
            candidate_dir = root / "candidate"
            registry.write_registry(baseline, baseline_dir)
            registry.write_registry(candidate, candidate_dir)
            server, thread = self.server()
            try:
                prefix = f"http://127.0.0.1:{server.server_port}/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/diff"
                params = {"baseline": str(baseline_dir), "candidate": str(candidate_dir), "format": "json"}
                with urlopen(prefix + "?" + urlencode(params)) as response:
                    payload = json.loads(response.read())
                self.assertEqual(payload["item_count"], 1)
                with urlopen(prefix + "/query?" + urlencode(params | {"resource": "items"})) as response:
                    query_payload = json.loads(response.read())
                self.assertEqual(query_payload["returned_count"], 1)
                with urlopen(prefix + "/schema") as response:
                    self.assertFalse(json.loads(response.read())["additionalProperties"])
                with urlopen(prefix + "/capabilities") as response:
                    self.assertEqual(tuple(json.loads(response.read())["resources"]), diff.RegistryDiffQuery.RESOURCES)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
