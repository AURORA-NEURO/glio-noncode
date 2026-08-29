"""Deep contracts for the verified multi-archive observatory registry."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive as archive
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry as registry
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_bytes, canonical_json
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive import ArchiveFixture


class RegistryFixture(ArchiveFixture):
    """Create registry members only through the current public archive boundary."""

    REGISTRY_COMMAND = ArchiveFixture.ARCHIVE_COMMAND + "-registry"

    def archive_file(self, root: Path, name: str, member_ids: tuple[str, ...], *, state: str = "ready") -> Path:
        if state == "ready":
            observatory_value = self.make_observatory(member_ids=member_ids)
        elif state == "held":
            history_value = self.make_history("history:" + name, (self.held_gate,), (name + ":0",))
            observatory_value = self.make_observatory((history_value,), member_ids[:1])
        elif state == "blocked":
            history_value = self.make_history("history:" + name, (self.blocked_gate,), (name + ":0",))
            observatory_value = self.make_observatory((history_value,), member_ids[:1])
        else:
            raise AssertionError(f"unsupported fixture state: {state}")
        observatory_directory = self.write_observatory(observatory_value, root, name + "-observatory")
        archive_value = archive.build_archive_from_directory(observatory_directory, archive_id="archive:" + name)
        return self.write_archive(archive_value, root, name + ".zip")

    def registry_value(self, root: Path, states: tuple[str, ...] = ("ready", "ready")) -> registry.ObservatoryArchiveRegistry:
        sources = tuple(self.archive_file(root, f"member-{index}", (f"source:{index}:a", f"source:{index}:b"), state=state) for index, state in enumerate(states))
        return registry.build_registry_from_archive_files(sources, entry_ids=tuple(f"entry:{index}" for index in range(len(sources))))

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

    def server(self):
        from glio_noncode.api import create_server

        server = create_server("127.0.0.1", 0)
        import threading

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread


class RegistryBuildTests(RegistryFixture):
    def test_entry_is_derived_from_a_verified_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.archive_file(root, "single", ("source:a", "source:b"))
            archive_value = archive.load_archive(source)
            value = registry.entry_from_archive_file(source, entry_id="entry:single")
            self.assertEqual(value.archive_address, archive_value.content_address)
            self.assertEqual(value.observatory_address, archive_value.observatory_address)
            self.assertEqual(value.archive_size, source.stat().st_size)
            self.assertEqual(registry.address_entry(value), value.content_address)
            self.assert_public(value)

    def test_entry_builder_rejects_an_unloaded_public_mapping(self):
        with self.assertRaises(ValidationError):
            registry.entry_from_archive({})

    def test_registry_orders_entries_and_conserves_all_metrics(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.registry_value(Path(temporary))
            self.assertEqual(tuple(entry.entry_id for entry in value.entries), ("entry:0", "entry:1"))
            self.assertEqual(value.entry_count, 2)
            self.assertEqual(value.metrics.entry_count, 2)
            self.assertEqual(value.metrics.archive_bytes, sum(entry.archive_size for entry in value.entries))
            self.assertEqual(value.metrics.member_count, sum(entry.member_count for entry in value.entries))
            self.assertEqual(value.metrics.observatory_entry_count, sum(entry.observatory_entry_count for entry in value.entries))
            self.assertEqual(value.metrics.finding_count, sum(entry.finding_count for entry in value.entries))
            self.assertEqual(value.metrics.check_count, sum(entry.check_count for entry in value.entries))
            self.assertEqual(value.state, registry.RegistryState.READY.value)
            self.assertTrue(value.accepted)
            self.assertTrue(value.release_ready)

    def test_registry_is_deterministic_when_source_order_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.archive_file(root, "first", ("source:first:a", "source:first:b"))
            second = self.archive_file(root, "second", ("source:second:a", "source:second:b"))
            left = registry.build_registry_from_archive_files((first, second), entry_ids=("entry:first", "entry:second"))
            right = registry.build_registry_from_archive_files((second, first), entry_ids=("entry:second", "entry:first"))
            self.assertEqual(left.to_dict(), right.to_dict())
            self.assertEqual(registry.registry_bytes(left), registry.registry_bytes(right))
            self.assertEqual(registry.registry_manifest_json(left), registry.registry_manifest_json(right))

    def test_empty_registry_is_explicit_and_fail_closed(self):
        value = registry.build_registry(())
        self.assertEqual(value.state, registry.RegistryState.EMPTY.value)
        self.assertFalse(value.accepted)
        self.assertFalse(value.release_ready)
        self.assertEqual(value.metrics.to_dict()["entry_count"], 0)
        self.assertEqual(value._verification.state, registry.RegistryVerificationState.HOLD.value)
        self.assertEqual(value._verification.failed_count, 0)

    def test_held_registry_is_not_release_ready(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.registry_value(Path(temporary), ("ready", "held"))
            self.assertEqual(value.state, registry.RegistryState.HELD.value)
            self.assertTrue(value.accepted)
            self.assertFalse(value.release_ready)
            self.assertEqual(value._verification.state, registry.RegistryVerificationState.HOLD.value)
            self.assertEqual(value._verification.failed_count, 0)

    def test_blocked_registry_has_block_verification_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.registry_value(Path(temporary), ("ready", "blocked"))
            self.assertEqual(value.state, registry.RegistryState.BLOCKED.value)
            self.assertFalse(value.release_ready)
            self.assertEqual(value._verification.state, registry.RegistryVerificationState.BLOCK.value)

    def test_mixed_registry_preserves_source_states(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.registry_value(Path(temporary), ("ready", "ready"))
            entries = list(value.entries)
            entries[1] = registry.RegistryEntry(entries[1].entry_id, entries[1].archive_id, entries[1].archive_address, entries[1].observatory_id, entries[1].observatory_address, entries[1].verification_address, entries[1].archive_size, registry.RegistryState.MIXED.value, entries[1].accepted, False, entries[1].member_count, entries[1].observatory_entry_count, entries[1].finding_count, entries[1].check_count, "pending:entry")
            entries[1].content_address = registry.address_entry(entries[1])
            mixed = registry.build_registry(entries)
            self.assertEqual(mixed.state, registry.RegistryState.MIXED.value)
            self.assertFalse(mixed.release_ready)

    def test_duplicate_entry_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.archive_file(root, "first", ("source:first:a", "source:first:b"))
            second = self.archive_file(root, "second", ("source:second:a", "source:second:b"))
            with self.assertRaises(ValidationError):
                registry.build_registry_from_archive_files((first, second), entry_ids=("entry:duplicate", "entry:duplicate"))

    def test_duplicate_archive_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.archive_file(root, "first", ("source:first:a", "source:first:b"))
            value = archive.load_archive(first)
            second = root / "second.zip"
            archive.write_archive(value, second)
            with self.assertRaises(ValidationError):
                registry.build_registry_from_archive_files((first, second), entry_ids=("entry:first", "entry:second"))

    def test_duplicate_observatory_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.archive_file(root, "first", ("source:same:a", "source:same:b"))
            second = self.archive_file(root, "second", ("source:same:a", "source:same:b"))
            with self.assertRaises(ValidationError):
                registry.build_registry_from_archive_files((first, second), entry_ids=("entry:first", "entry:second"))

    def test_registry_mapping_round_trip_is_typed_and_path_free(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.registry_value(Path(temporary))
            mapped = registry.registry_from_mapping(value.to_dict())
            self.assertEqual(mapped.to_dict(), value.to_dict())
            self.assert_public(mapped)
            self.assertNotIn(str(Path(temporary)), canonical_json(mapped.to_dict()))

    def test_registry_mapping_rejects_private_or_unknown_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            document = self.registry_value(Path(temporary)).to_dict()
            with self.assertRaises(ValidationError):
                registry.registry_from_mapping(document | {"private": "secret"})
            with self.assertRaises(ValidationError):
                registry.registry_from_mapping(document | {"source_path": "C:\\private"})

    def test_registry_rejects_freehand_content_address(self):
        with tempfile.TemporaryDirectory() as temporary:
            document = self.registry_value(Path(temporary)).to_dict()
            document["content_address"] = registry.REGISTRY_PREFIX + ":forged"
            with self.assertRaises(ValidationError):
                registry.registry_from_mapping(document)

    def test_registry_verification_contains_eight_reproducible_checks(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.registry_value(Path(temporary))
            verification = value._verification
            self.assertEqual(verification.check_count, 8)
            self.assertEqual(verification.passed_count, 8)
            self.assertEqual(verification.failed_count, 0)
            self.assertEqual(tuple(check.check_id for check in verification.checks), registry.RegistryVerification.CHECK_IDS)
            self.assertTrue(all(check.content_address.startswith(registry.REGISTRY_CHECK_PREFIX + ":") for check in verification.checks))
            self.assertEqual(registry.address_verification(verification), verification.content_address)
            registry.verify_registry(value)


class RegistryPersistenceTests(RegistryFixture):
    def test_registry_has_exact_five_canonical_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.registry_value(Path(temporary))
            payload = registry.registry_bytes(value)
            self.assertEqual(tuple(payload), registry.FILES)
            self.assertEqual(set(payload), set(registry.FILES))
            self.assertTrue(all(canonical_bytes(json.loads(raw)) == raw for raw in payload.values()))

    def test_registry_persistence_round_trip_rehydrates_payload(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.registry_value(root)
            destination = root / "registry"
            self.assertEqual(registry.write_registry(value, destination), destination)
            loaded = registry.load_registry(destination)
            self.assertEqual(loaded.to_dict(), value.to_dict())
            self.assertEqual(loaded.payload_bytes(), registry.registry_bytes(value))
            self.assertEqual(registry.verify_registry_directory(destination).content_address, value.content_address)

    def test_registry_rewrite_requires_explicit_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.registry_value(root)
            destination = root / "registry"
            registry.write_registry(value, destination)
            with self.assertRaises(ValidationError):
                registry.write_registry(value, destination)
            registry.write_registry(value, destination, overwrite=True)

    def test_manifest_contains_four_artifact_receipts_and_registry_links(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.registry_value(root)
            destination = root / "registry"
            registry.write_registry(value, destination)
            manifest = json.loads((destination / registry.MANIFEST_NAME).read_text(encoding="utf-8"))
            self.assertEqual(manifest["artifact_count"], len(registry.FILES) - 1)
            self.assertEqual(tuple(manifest["files"]), registry.FILES[1:])
            self.assertEqual(manifest["registry_address"], value.content_address)
            self.assertEqual(manifest["verification_address"], value.verification_address)
            self.assertEqual(manifest["manifest_address"], registry.registry_manifest_json(value) and manifest["manifest_address"])
            self.assert_public(manifest)

    def test_tampering_any_registry_artifact_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.registry_value(root)
            destination = root / "registry"
            registry.write_registry(value, destination)
            for name in registry.FILES:
                original = (destination / name).read_bytes()
                (destination / name).write_bytes(original + b"\n")
                with self.assertRaises(ValidationError, msg=name):
                    registry.load_registry(destination)
                (destination / name).write_bytes(original)

    def test_extra_directory_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "registry"
            registry.write_registry(self.registry_value(root), destination)
            (destination / "extra.json").write_bytes(b"{}")
            with self.assertRaises(ValidationError):
                registry.load_registry(destination)

    def test_registry_bytes_require_attached_verification(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = registry.registry_from_mapping(self.registry_value(Path(temporary)).to_dict())
            with self.assertRaises(ValidationError):
                registry.registry_bytes(value)

    def test_registry_json_and_manifest_json_are_canonical(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.registry_value(Path(temporary))
            self.assertEqual(registry.registry_json(value), canonical_json(value.to_dict()))
            manifest = json.loads(registry.registry_manifest_json(value))
            self.assertEqual(registry.registry_manifest_json(value), canonical_json(manifest))
            self.assert_public(manifest)


class RegistryQueryTests(RegistryFixture):
    def test_summary_query_is_bounded_and_addressed(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.registry_value(Path(temporary))
            result = registry.query_registry(value)
            self.assertEqual(result.total_count, 1)
            self.assertEqual(result.returned_count, 1)
            self.assertEqual(result.records[0]["registry_id"], value.registry_id)
            self.assertEqual(registry.address_query(result), result.content_address)
            self.assert_public(result)

    def test_entry_queries_filter_by_state_acceptance_and_readiness(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.registry_value(Path(temporary), ("ready", "held"))
            self.assertEqual(registry.query_registry(value, resource="entries").total_count, 2)
            self.assertEqual(registry.query_registry(value, resource="ready").total_count, 1)
            self.assertEqual(registry.query_registry(value, resource="held").total_count, 1)
            self.assertEqual(registry.query_registry(value, resource="accepted").total_count, 2)
            self.assertEqual(registry.query_registry(value, resource="rejected").total_count, 0)
            self.assertEqual(registry.query_registry(value, resource="entries", release_ready=True).total_count, 1)
            self.assertEqual(registry.query_registry(value, resource="entries", state="held").records[0]["state"], "held")

    def test_query_pagination_is_deterministic(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.registry_value(Path(temporary), ("ready", "ready"))
            first = registry.query_registry(value, resource="entries", offset=0, limit=1)
            second = registry.query_registry(value, resource="entries", offset=1, limit=1)
            self.assertEqual(first.total_count, 2)
            self.assertEqual(first.returned_count, 1)
            self.assertEqual(second.returned_count, 1)
            self.assertNotEqual(first.records[0]["entry_id"], second.records[0]["entry_id"])
            self.assertNotEqual(first.content_address, second.content_address)

    def test_query_text_matches_public_entry_projection(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.registry_value(Path(temporary))
            result = registry.query_registry(value, resource="entries", text="entry:1")
            self.assertEqual(result.total_count, 1)
            self.assertEqual(result.records[0]["entry_id"], "entry:1")

    def test_query_object_and_keyword_filters_are_equivalent(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.registry_value(Path(temporary), ("ready", "held"))
            query = registry.RegistryQuery(resource="entries", state="held", limit=2)
            first = registry.query_registry(value, query)
            second = registry.query_registry(value, resource="entries", state="held", limit=2)
            self.assertEqual(first.to_dict(), second.to_dict())

    def test_query_rejects_mixed_object_and_keyword_filters(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.registry_value(Path(temporary))
            with self.assertRaises(ValidationError):
                registry.query_registry(value, registry.RegistryQuery(), resource="entries")

    def test_query_renderers_share_the_same_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = registry.query_registry(self.registry_value(Path(temporary)), resource="entries")
            payload = json.loads(registry.query_json(result))
            csv_text = registry.query_csv(result)
            markdown = registry.render_query_markdown(result)
            self.assertEqual(payload["returned_count"], result.returned_count)
            self.assertIn("entry_id", csv_text)
            self.assertIn("entry:0", markdown)
            self.assertIn(result.content_address, markdown)

    def test_query_renderers_reject_plain_values(self):
        for renderer in (registry.query_json, registry.query_csv, registry.render_query_markdown):
            with self.assertRaises(ValidationError):
                renderer({"records": ()})

    def test_query_result_rejects_bad_registry_address(self):
        with self.assertRaises(ValidationError):
            registry.RegistryQueryResult("not-addressed", registry.RegistryQuery(), 0, (), "pending:query")

    def test_query_result_rejects_window_over_limit(self):
        query = registry.RegistryQuery(resource="entries", limit=1)
        with self.assertRaises(ValidationError):
            registry.RegistryQueryResult(registry.REGISTRY_PREFIX + ":address", query, 2, ({"entry_id": "one"}, {"entry_id": "two"}), "pending:query")

    def test_query_schema_and_capabilities_are_closed_and_bounded(self):
        schema = registry.query_result_schema()
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(tuple(registry.query_schema()["properties"]["resource"]["enum"]), registry.RegistryQuery.RESOURCES)
        self.assertEqual(registry.capabilities()["limits"]["max_entries"], registry.MAX_ENTRIES)
        self.assertEqual(tuple(registry.capabilities()["verification_checks"]), registry.RegistryVerification.CHECK_IDS)
        self.assert_public(registry.capabilities())


class RegistryCliAndApiTests(RegistryFixture):
    def test_cli_build_verify_query_and_capability_contract(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.archive_file(root, "cli", ("source:cli:a", "source:cli:b"))
            destination = root / "registry"
            output = root / "summary.json"
            status = main([self.REGISTRY_COMMAND, "--input", str(source), "--destination", str(destination), "--output", str(output)])
            self.assertEqual(status, 0)
            self.assertEqual(main([self.REGISTRY_COMMAND + "-verify", "--input", str(destination)]), 0)
            self.assertEqual(main([self.REGISTRY_COMMAND + "-query", "--input", str(destination), "--resource", "entries", "--format", "csv"]), 0)
            self.assertEqual(main([self.REGISTRY_COMMAND + "-capabilities"]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["entry_count"], 1)

    def test_http_schema_capabilities_verify_manifest_and_query_routes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.archive_file(root, "http", ("source:http:a", "source:http:b"))
            destination = root / "registry"
            registry.write_registry(registry.build_registry_from_archive_files((source,)), destination)
            server, thread = self.server()
            try:
                prefix = f"http://127.0.0.1:{server.server_port}/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry"
                with urlopen(prefix + "/capabilities") as response:
                    capabilities = json.loads(response.read())
                self.assertEqual(capabilities["limits"]["max_entries"], registry.MAX_ENTRIES)
                with urlopen(prefix + "/schema") as response:
                    self.assertFalse(json.loads(response.read())["additionalProperties"])
                query = urlencode({"input": str(destination), "resource": "entries", "format": "json"})
                with urlopen(prefix + "/query?" + query) as response:
                    payload = json.loads(response.read())
                self.assertEqual(payload["returned_count"], 1)
                with urlopen(prefix + "/verify?" + urlencode({"input": str(destination)})) as response:
                    self.assertTrue(json.loads(response.read())["release_ready"])
                with urlopen(prefix + "/manifest?" + urlencode({"input": str(destination)})) as response:
                    self.assertEqual(json.loads(response.read())["registry_address"], registry.load_registry(destination).content_address)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
