"""Deep contracts for the release-package admission registry."""

# ruff: noqa: E501

from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry as registry
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import hash_bytes
from tests.test_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_decision_ledger_assurance_history_series_release import ReleaseFixture


class RegistryFixture(unittest.TestCase):
    fixture = ReleaseFixture("runTest")

    def ready(self, suffix: str = "ready"):
        return self.fixture.ready_package(package_id=f"package:{suffix}", release_id=f"release:{suffix}")

    def held(self, suffix: str = "held"):
        return self.fixture.held_package(package_id=f"package:{suffix}", release_id=f"release:{suffix}")

    def blocked(self, suffix: str = "blocked"):
        return self.fixture.blocked_package(package_id=f"package:{suffix}", release_id=f"release:{suffix}")

    @staticmethod
    def build(packages):
        return registry.build_decision_assurance_history_series_release_registry(packages, registry_id="registry:test")

    @staticmethod
    def write(value, path, **kwargs):
        return registry.write_decision_assurance_history_series_release_registry(value, path, **kwargs)

    @staticmethod
    def write_diff(value, path, **kwargs):
        return registry.write_decision_assurance_history_series_release_registry_diff(value, path, **kwargs)


class RegistryCoreTests(RegistryFixture):
    def test_registry_sorts_by_package_id_and_conserves_all_projections(self):
        value = self.build((self.blocked(), self.ready(), self.held()))
        self.assertEqual([entry.package_id for entry in value.entries], ["package:blocked", "package:held", "package:ready"])
        self.assertEqual((value.entry_count, value.ready_count, value.hold_count, value.blocked_count), (3, 1, 1, 1))
        self.assertEqual((value.accepted_count, value.release_ready_count), (2, 1))
        self.assertEqual(value.content_address, registry.address_decision_assurance_history_series_release_registry(value))
        self.assertEqual([entry.ordinal for entry in value.entries], list(range(3)))

    def test_entry_addresses_retain_package_and_release_provenance(self):
        value = self.build((self.ready(), self.held()))
        for entry in value.entries:
            self.assertIn(entry.package_address, {self.ready().content_address, self.held().content_address})
            self.assertIn(entry.release_address, {self.ready().release.content_address, self.held().release.content_address})
            self.assertEqual(entry.content_address, registry.address_decision_assurance_history_series_release_registry_entry(entry))

    def test_registry_mapping_round_trip_is_exact(self):
        value = self.build((self.ready(), self.held(), self.blocked()))
        loaded = registry.decision_assurance_history_series_release_registry_from_mapping(value.to_dict())
        self.assertEqual(loaded.to_dict(), value.to_dict())
        self.assertEqual(registry.decision_assurance_history_series_release_registry_json(value), registry.decision_assurance_history_series_release_registry_json(loaded))

    def test_registry_rejects_empty_non_typed_or_over_capacity_inputs(self):
        with self.assertRaises(ValidationError):
            self.build(())
        with self.assertRaises(ValidationError):
            registry.build_decision_assurance_history_series_release_registry([object()])
        with self.assertRaises(ValidationError):
            registry.build_decision_assurance_history_series_release_registry([self.ready()] * (registry.MAX_ENTRIES + 1))

    def test_registry_and_entries_do_not_cross_private_boundary(self):
        value = self.build((self.ready(), self.held()))
        projection = value.to_dict()
        encoded = json.dumps(projection, sort_keys=True).casefold()
        for token in ("agent", "assistant", "generated_by", "language", "model", "private", "secret", "token"):
            self.assertNotIn(f'"{token}"', encoded)
        self.assertNotIn("\\", encoded)

    def test_direct_entry_and_registry_validation_rejects_state_mismatches(self):
        value = self.build((self.ready(),))
        body = value.entries[0].to_dict()
        body["release_ready"] = False
        body["content_address"] = "pending:entry"
        with self.assertRaises(ValidationError):
            registry.DecisionAssuranceHistorySeriesReleaseRegistryEntry(**body)
        body = value.to_dict()
        body["ready_count"] = 0
        body["content_address"] = "pending:registry"
        body["entries"] = value.entries
        with self.assertRaises(ValidationError):
            registry.DecisionAssuranceHistorySeriesReleaseRegistry(**body)

    def test_mapping_boundaries_reject_unknown_fields_and_invalid_addresses(self):
        value = self.build((self.ready(),))
        body = value.to_dict()
        body["unknown"] = True
        with self.assertRaises(ValidationError):
            registry.decision_assurance_history_series_release_registry_from_mapping(body)
        entry = value.entries[0].to_dict()
        entry["unknown"] = True
        with self.assertRaises(ValidationError):
            registry.decision_assurance_history_series_release_registry_entry_from_mapping(entry)
        entry = value.entries[0].to_dict()
        entry["package_address"] = "not-address"
        with self.assertRaises(ValidationError):
            registry.decision_assurance_history_series_release_registry_entry_from_mapping(entry)


class RegistryQueryExportTests(RegistryFixture):
    def test_each_registry_query_resource_is_bounded_and_addressable(self):
        value = self.build((self.ready(), self.held(), self.blocked()))
        expected = {"summary": 1, "entries": 3, "ready": 1, "hold": 1, "blocked": 1, "accepted": 2, "release-ready": 1, "rejected": 1}
        for resource_name, count in expected.items():
            with self.subTest(resource=resource_name):
                result = registry.query_decision_assurance_history_series_release_registry(value, resource=resource_name, limit=registry.MAX_QUERY_ITEMS)
                self.assertEqual(result.total_count, count)
                self.assertEqual(result.returned_count, count)
                self.assertEqual(result.content_address, registry.address_decision_assurance_history_series_release_registry_query(result))

    def test_registry_query_pagination_and_text_filter_are_deterministic(self):
        value = self.build((self.ready("a"), self.ready("b"), self.held("c")))
        first = registry.query_decision_assurance_history_series_release_registry(value, resource="entries", offset=1, limit=1)
        second = registry.query_decision_assurance_history_series_release_registry(value, resource="entries", offset=1, limit=1)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.items[0]["package_id"], "package:b")
        filtered = registry.query_decision_assurance_history_series_release_registry(value, resource="entries", text="package:c")
        self.assertEqual(filtered.returned_count, 1)
        self.assertEqual(filtered.items[0]["state"], "hold")
        with self.assertRaises(ValidationError):
            registry.ReleaseRegistryQuery(resource="invalid")
        with self.assertRaises(ValidationError):
            registry.ReleaseRegistryQuery(limit=0)
        with self.assertRaises(ValidationError):
            registry.query_decision_assurance_history_series_release_registry(value, query=registry.ReleaseRegistryQuery(), resource="entries")

    def test_registry_exports_are_stable_and_include_every_admission(self):
        value = self.build((self.ready(), self.held(), self.blocked()))
        self.assertEqual(registry.decision_assurance_history_series_release_registry_json(value), registry.decision_assurance_history_series_release_registry_json(value))
        self.assertEqual(len(registry.decision_assurance_history_series_release_registry_csv(value).splitlines()), 4)
        self.assertIn("Decision Assurance History Series Release Registry", registry.render_decision_assurance_history_series_release_registry_markdown(value))
        result = registry.query_decision_assurance_history_series_release_registry(value, resource="blocked")
        self.assertEqual(len(registry.decision_assurance_history_series_release_registry_query_csv(result).splitlines()), 2)
        self.assertIn("Registry Query", registry.render_decision_assurance_history_series_release_registry_query_markdown(result))

    def test_query_result_constructor_rejects_unbounded_or_mismatched_counts(self):
        value = self.build((self.ready(),))
        query = registry.ReleaseRegistryQuery(resource="entries")
        with self.assertRaises(ValidationError):
            registry.ReleaseRegistryQueryResult(value.content_address, query, 1, 2, [], "pending:query")
        with self.assertRaises(ValidationError):
            registry.ReleaseRegistryQueryResult("bad", query, 0, 0, [], "pending:query")


class RegistryPersistenceTests(RegistryFixture):
    def test_registry_persistence_has_exact_three_files_and_reloads(self):
        value = self.build((self.ready(), self.held(), self.blocked()))
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "registry"
            self.write(value, destination)
            self.assertEqual({item.name for item in destination.iterdir()}, set(registry.FILES))
            loaded = registry.load_decision_assurance_history_series_release_registry(destination)
            self.assertEqual(loaded.to_dict(), value.to_dict())
            manifest = json.loads((destination / registry.MANIFEST_NAME).read_text())
            self.assertEqual(manifest["artifact_count"], 2)
            self.assertEqual(tuple(manifest["files"]), registry.FILES)
            entries_raw = (destination / registry.ENTRIES_NAME).read_bytes()
            self.assertEqual(manifest["artifacts"][0]["byte_address"], hash_bytes(entries_raw))

    def test_registry_persistence_repeatability_and_overwrite_guard(self):
        value = self.build((self.ready(), self.held()))
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "registry"
            self.write(value, destination)
            first = {name: (destination / name).read_bytes() for name in registry.FILES}
            with self.assertRaises(ValidationError):
                self.write(value, destination)
            self.write(value, destination, overwrite=True)
            second = {name: (destination / name).read_bytes() for name in registry.FILES}
            self.assertEqual(first, second)

    def test_registry_loader_rejects_missing_extra_noncanonical_and_tampered_files(self):
        value = self.build((self.ready(),))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ValidationError):
                registry.load_decision_assurance_history_series_release_registry(root / "missing")
            destination = root / "registry"
            self.write(value, destination)
            (destination / registry.ENTRIES_NAME).unlink()
            with self.assertRaises(ValidationError):
                registry.load_decision_assurance_history_series_release_registry(destination)
            self.write(value, destination, overwrite=True)
            (destination / "extra.json").write_text("{}")
            with self.assertRaises(ValidationError):
                registry.load_decision_assurance_history_series_release_registry(destination)
            (destination / "extra.json").unlink()
            (destination / registry.REGISTRY_NAME).write_text("{\"tampered\":true}")
            with self.assertRaises(ValidationError):
                registry.load_decision_assurance_history_series_release_registry(destination)

    def test_registry_loader_rejects_manifest_and_projection_mismatches(self):
        value = self.build((self.ready(), self.held()))
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "registry"
            self.write(value, destination)
            manifest = json.loads((destination / registry.MANIFEST_NAME).read_text())
            manifest["registry_address"] = "registry:wrong"
            (destination / registry.MANIFEST_NAME).write_bytes(registry.canonical_bytes(manifest) if hasattr(registry, "canonical_bytes") else json.dumps(manifest).encode())
            with self.assertRaises(ValidationError):
                registry.load_decision_assurance_history_series_release_registry(destination)

    def test_registry_persistence_rejects_file_input_and_symlinked_artifact(self):
        value = self.build((self.ready(),))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            file_path = root / "file"
            file_path.write_text("x")
            with self.assertRaises(ValidationError):
                registry.load_decision_assurance_history_series_release_registry(file_path)
            destination = root / "registry"
            self.write(value, destination)
            try:
                target = root / "target.json"
                target.write_bytes((destination / registry.REGISTRY_NAME).read_bytes())
                (destination / registry.REGISTRY_NAME).unlink()
                (destination / registry.REGISTRY_NAME).symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation unavailable")
            with self.assertRaises(ValidationError):
                registry.load_decision_assurance_history_series_release_registry(destination)


class RegistryDiffTests(RegistryFixture):
    def test_registry_diff_conserves_actions_and_classifies_membership(self):
        baseline = self.build((self.ready("same"), self.held("removed")))
        candidate = self.build((self.ready("same"), self.blocked("added")))
        value = registry.build_decision_assurance_history_series_release_registry_diff(baseline, candidate, diff_id="diff:test")
        self.assertEqual(value.item_count, 3)
        self.assertEqual(value.added_count, 1)
        self.assertEqual(value.removed_count, 1)
        self.assertEqual(value.unchanged_count, 1)
        self.assertEqual(value.added_count + value.removed_count + value.unchanged_count + value.changed_count, value.item_count)
        self.assertEqual(value.content_address, registry.address_decision_assurance_history_series_release_registry_diff(value))

    def test_same_registry_diff_is_unchanged_and_ready(self):
        value = self.build((self.ready("same"), self.held("held")))
        diff = registry.build_decision_assurance_history_series_release_registry_diff(value, value)
        self.assertEqual((diff.state, diff.regressed_count, diff.release_ready), ("unchanged", 0, True))
        self.assertEqual(diff.unchanged_count, 2)

    def test_same_key_ready_to_blocked_is_regressed(self):
        baseline = self.build((self.ready("same"),))
        candidate = self.build((self.blocked("same"),))
        diff = registry.build_decision_assurance_history_series_release_registry_diff(baseline, candidate)
        self.assertEqual((diff.state, diff.regressed_count, diff.release_ready), ("regressed", 1, False))
        self.assertEqual(diff.items[0].direction, "regressed")

    def test_same_key_blocked_to_ready_is_improved(self):
        baseline = self.build((self.blocked("same"),))
        candidate = self.build((self.ready("same"),))
        diff = registry.build_decision_assurance_history_series_release_registry_diff(baseline, candidate)
        self.assertEqual((diff.state, diff.improved_count, diff.release_ready), ("improved", 1, True))

    def test_diff_queries_exports_and_mapping_round_trip(self):
        baseline = self.build((self.held("same"),))
        candidate = self.build((self.ready("same"), self.ready("added")))
        value = registry.build_decision_assurance_history_series_release_registry_diff(baseline, candidate)
        for resource in registry.ReleaseRegistryDiffQuery.RESOURCES:
            result = registry.query_decision_assurance_history_series_release_registry_diff(value, resource=resource)
            self.assertLessEqual(result.returned_count, result.query.limit)
        self.assertEqual(registry.decision_assurance_history_series_release_registry_diff_from_mapping(value.to_dict()).to_dict(), value.to_dict())
        self.assertIn("Registry Diff", registry.render_decision_assurance_history_series_release_registry_diff_markdown(value))
        self.assertTrue(registry.decision_assurance_history_series_release_registry_diff_json(value).startswith("{"))
        self.assertGreater(len(registry.decision_assurance_history_series_release_registry_diff_csv(value).splitlines()), 1)

    def test_diff_mapping_rejects_unknown_fields_direction_and_receipt(self):
        baseline = self.build((self.ready("same"),))
        candidate = self.build((self.blocked("same"),))
        value = registry.build_decision_assurance_history_series_release_registry_diff(baseline, candidate)
        body = value.to_dict()
        body["unknown"] = True
        with self.assertRaises(ValidationError):
            registry.decision_assurance_history_series_release_registry_diff_from_mapping(body)
        body = value.to_dict()
        body["items"][0]["direction"] = "improved"
        with self.assertRaises(ValidationError):
            registry.decision_assurance_history_series_release_registry_diff_from_mapping(body)
        body = value.to_dict()
        body["content_address"] = "diff:tampered"
        with self.assertRaises(ValidationError):
            registry.decision_assurance_history_series_release_registry_diff_from_mapping(body)

    def test_diff_persistence_has_exact_two_files_and_reloads(self):
        baseline = self.build((self.ready("same"),))
        candidate = self.build((self.blocked("same"),))
        value = registry.build_decision_assurance_history_series_release_registry_diff(baseline, candidate)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "diff"
            self.write_diff(value, destination)
            self.assertEqual({item.name for item in destination.iterdir()}, set(registry.DIFF_FILES))
            loaded = registry.load_decision_assurance_history_series_release_registry_diff(destination)
            self.assertEqual(loaded.to_dict(), value.to_dict())
            manifest = json.loads((destination / registry.MANIFEST_NAME).read_text())
            self.assertEqual(manifest["artifact_count"], 1)

    def test_diff_persistence_rejects_tamper_extra_and_missing_files(self):
        baseline = self.build((self.ready("same"),))
        candidate = self.build((self.held("same"),))
        value = registry.build_decision_assurance_history_series_release_registry_diff(baseline, candidate)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "diff"
            self.write_diff(value, destination)
            (destination / registry.DIFF_NAME).write_text("{}")
            with self.assertRaises(ValidationError):
                registry.load_decision_assurance_history_series_release_registry_diff(destination)
            self.write_diff(value, destination, overwrite=True)
            (destination / "extra").write_text("x")
            with self.assertRaises(ValidationError):
                registry.load_decision_assurance_history_series_release_registry_diff(destination)
            (destination / "extra").unlink()
            (destination / registry.MANIFEST_NAME).unlink()
            with self.assertRaises(ValidationError):
                registry.load_decision_assurance_history_series_release_registry_diff(destination)


class RegistrySchemaCapabilityTests(RegistryFixture):
    def test_schemas_are_closed_and_match_registry_contract(self):
        schemas = (registry.decision_assurance_history_series_release_registry_schema(), registry.decision_assurance_history_series_release_registry_entry_schema(), registry.decision_assurance_history_series_release_registry_query_schema(), registry.decision_assurance_history_series_release_registry_diff_schema(), registry.decision_assurance_history_series_release_registry_diff_item_schema(), registry.decision_assurance_history_series_release_registry_diff_query_schema())
        for schema in schemas:
            self.assertFalse(schema["additionalProperties"])
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")

    def test_capabilities_describe_transport_query_and_public_boundary(self):
        value = registry.capabilities()
        self.assertEqual(value["package"]["files"], list(registry.FILES))
        self.assertEqual(value["diff"]["files"], list(registry.DIFF_FILES))
        self.assertEqual(value["queries"]["max_limit"], registry.MAX_QUERY_ITEMS)
        self.assertFalse(value["public_boundary"]["source_paths"])

    def test_query_and_diff_query_reject_invalid_limits_and_resources(self):
        with self.assertRaises(ValidationError):
            registry.ReleaseRegistryDiffQuery(resource="invalid")
        with self.assertRaises(ValidationError):
            registry.ReleaseRegistryDiffQuery(limit=0)
        with self.assertRaises(ValidationError):
            registry.ReleaseRegistryQuery(offset=-1)


class RegistryAdditionalBoundaryTests(RegistryFixture):
    def test_builder_does_not_mutate_input_package_order_or_projection(self):
        ready = self.ready("z")
        held = self.held("a")
        before = (ready.to_dict(), held.to_dict())
        value = self.build((ready, held))
        self.assertEqual((ready.to_dict(), held.to_dict()), before)
        self.assertEqual([item.package_id for item in value.entries], ["package:a", "package:z"])

    def test_registry_rejects_bad_version_boundary_counts_and_ordinals(self):
        value = self.build((self.ready(),))
        base = value.to_dict()
        base["content_address"] = "pending:registry"
        base["version"] = "wrong"
        base["entries"] = value.entries
        with self.assertRaises(ValidationError):
            registry.DecisionAssuranceHistorySeriesReleaseRegistry(**base)
        base = value.to_dict()
        base["content_address"] = "pending:registry"
        base["boundary"] = "wrong"
        base["entries"] = value.entries
        with self.assertRaises(ValidationError):
            registry.DecisionAssuranceHistorySeriesReleaseRegistry(**base)
        base = value.to_dict()
        base["content_address"] = "pending:registry"
        base["entry_count"] = 0
        base["entries"] = value.entries
        with self.assertRaises(ValidationError):
            registry.DecisionAssuranceHistorySeriesReleaseRegistry(**base)
        entry = value.entries[0]
        with self.assertRaises(ValidationError):
            registry.DecisionAssuranceHistorySeriesReleaseRegistryEntry(
                ordinal=1,
                package_id=entry.package_id,
                release_id=entry.release_id,
                package_address=entry.package_address,
                release_address=entry.release_address,
                state=entry.state,
                accepted=entry.accepted,
                release_ready=False,
                content_address="pending:entry",
            )

    def test_duplicate_package_and_release_identity_is_rejected(self):
        first = self.ready("same")
        second = self.held("same")
        with self.assertRaises(ValidationError):
            self.build((first, second))

    def test_entry_validation_rejects_boolean_counts_and_invalid_projection(self):
        entry = self.build((self.ready(),)).entries[0]
        fields = entry.to_dict()
        fields["ordinal"] = True
        with self.assertRaises(ValidationError):
            registry.DecisionAssuranceHistorySeriesReleaseRegistryEntry(**fields)
        fields = entry.to_dict()
        fields["state"] = "blocked"
        fields["accepted"] = False
        fields["release_ready"] = False
        fields["content_address"] = "pending:entry"
        self.assertEqual(registry.DecisionAssuranceHistorySeriesReleaseRegistryEntry(**fields).state, "blocked")
        fields["state"] = "ready"
        with self.assertRaises(ValidationError):
            registry.DecisionAssuranceHistorySeriesReleaseRegistryEntry(**fields)

    def test_registry_query_rejects_boolean_offsets_and_too_large_limits(self):
        value = self.build((self.ready(),))
        with self.assertRaises(ValidationError):
            registry.ReleaseRegistryQuery(offset=True)
        with self.assertRaises(ValidationError):
            registry.ReleaseRegistryQuery(limit=registry.MAX_QUERY_ITEMS + 1)
        with self.assertRaises(ValidationError):
            registry.query_decision_assurance_history_series_release_registry(value, resource="entries", offset=registry.MAX_QUERY_ITEMS + 1)

    def test_registry_query_empty_page_preserves_total_and_address(self):
        value = self.build((self.ready(), self.held()))
        result = registry.query_decision_assurance_history_series_release_registry(value, resource="entries", offset=10, limit=2)
        self.assertEqual((result.total_count, result.returned_count, result.items), (2, 0, ()))
        self.assertEqual(result.content_address, registry.address_decision_assurance_history_series_release_registry_query(result))

    def test_registry_diff_direction_counts_and_query_filter_are_conserved(self):
        baseline = self.build((self.ready("same"), self.held("removed")))
        candidate = self.build((self.blocked("same"), self.ready("added")))
        diff = registry.build_decision_assurance_history_series_release_registry_diff(baseline, candidate)
        self.assertEqual(diff.regressed_count, 1)
        self.assertEqual(diff.improved_count, 1)
        filtered = registry.query_decision_assurance_history_series_release_registry_diff(diff, resource="regressed", text="package:same")
        self.assertEqual(filtered.returned_count, 1)
        self.assertEqual(filtered.items[0]["key"], "package:package:same")
        self.assertEqual(filtered.content_address, registry.address_decision_assurance_history_series_release_registry_diff_query(filtered))

    def test_diff_query_rejects_boolean_bounds_and_mixed_query_arguments(self):
        value = self.build((self.ready(),))
        diff = registry.build_decision_assurance_history_series_release_registry_diff(value, value)
        with self.assertRaises(ValidationError):
            registry.ReleaseRegistryDiffQuery(offset=True)
        with self.assertRaises(ValidationError):
            registry.ReleaseRegistryDiffQuery(limit=0)
        with self.assertRaises(ValidationError):
            registry.query_decision_assurance_history_series_release_registry_diff(diff, query=registry.ReleaseRegistryDiffQuery(), resource="items")

    def test_diff_item_constructor_rejects_invalid_join_shapes(self):
        value = self.build((self.ready(),))
        diff = registry.build_decision_assurance_history_series_release_registry_diff(value, value)
        item = diff.items[0]
        with self.assertRaises(ValidationError):
            registry.DecisionAssuranceHistorySeriesReleaseRegistryDiffItem(item.ordinal, item.key, "added", "improved", item.baseline_value, item.candidate_value, item.detail, "pending:item")
        with self.assertRaises(ValidationError):
            registry.DecisionAssuranceHistorySeriesReleaseRegistryDiffItem(item.ordinal, item.key, item.action, "invalid", item.baseline_value, item.candidate_value, item.detail, "pending:item")

    def test_diff_mapping_rejects_non_contiguous_items_and_bad_count_conservation(self):
        value = self.build((self.ready(), self.held()))
        diff = registry.build_decision_assurance_history_series_release_registry_diff(value, value)
        body = diff.to_dict()
        body["items"][0]["ordinal"] = 1
        with self.assertRaises(ValidationError):
            registry.decision_assurance_history_series_release_registry_diff_from_mapping(body)
        body = diff.to_dict()
        body["unchanged_count"] = 0
        with self.assertRaises(ValidationError):
            registry.decision_assurance_history_series_release_registry_diff_from_mapping(body)

    def test_registry_reload_rejects_entries_document_divergence(self):
        value = self.build((self.ready(), self.held()))
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "registry"
            self.write(value, destination)
            document = json.loads((destination / registry.ENTRIES_NAME).read_text())
            document["entries"].reverse()
            (destination / registry.ENTRIES_NAME).write_bytes(registry.canonical_bytes(document))
            with self.assertRaises(ValidationError):
                registry.load_decision_assurance_history_series_release_registry(destination)

    def test_registry_reload_rejects_artifact_receipt_and_manifest_file_list_tampering(self):
        value = self.build((self.ready(),))
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "registry"
            self.write(value, destination)
            manifest = json.loads((destination / registry.MANIFEST_NAME).read_text())
            manifest["artifacts"][0]["bytes"] += 1
            (destination / registry.MANIFEST_NAME).write_bytes(registry.canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                registry.load_decision_assurance_history_series_release_registry(destination)
            self.write(value, destination, overwrite=True)
            manifest = json.loads((destination / registry.MANIFEST_NAME).read_text())
            manifest["files"] = [registry.MANIFEST_NAME]
            (destination / registry.MANIFEST_NAME).write_bytes(registry.canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                registry.load_decision_assurance_history_series_release_registry(destination)

    def test_diff_reload_rejects_manifest_receipt_and_linkage_tampering(self):
        value = self.build((self.ready(),))
        diff = registry.build_decision_assurance_history_series_release_registry_diff(value, value)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "diff"
            self.write_diff(diff, destination)
            manifest = json.loads((destination / registry.MANIFEST_NAME).read_text())
            manifest["diff_address"] = "diff:wrong"
            (destination / registry.MANIFEST_NAME).write_bytes(registry.canonical_bytes(manifest))
            with self.assertRaises(ValidationError):
                registry.load_decision_assurance_history_series_release_registry_diff(destination)

    def test_public_projection_has_no_private_keys_in_schemas_or_capabilities(self):
        projection = {"schemas": [registry.decision_assurance_history_series_release_registry_schema(), registry.decision_assurance_history_series_release_registry_diff_schema()], "capabilities": registry.capabilities()}
        forbidden = {"agent", "assistant", "author", "generated_by", "language", "model", "private", "secret", "token", "user"}

        def keys(value):
            if isinstance(value, dict):
                return {str(key).casefold() for key in value} | set().union(*(keys(item) for item in value.values()))
            if isinstance(value, list):
                return set().union(*(keys(item) for item in value)) if value else set()
            return set()

        self.assertFalse(keys(projection) & forbidden)

    def test_registry_file_helpers_reject_non_directories_and_directory_symlink(self):
        value = self.build((self.ready(),))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            file_path = root / "file"
            file_path.write_text("data")
            with self.assertRaises(ValidationError):
                registry.verify_decision_assurance_history_series_release_registry_directory(file_path)
            destination = root / "registry"
            self.write(value, destination)
            link = root / "registry-link"
            try:
                link.symlink_to(destination, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlink creation unavailable")
            with self.assertRaises(ValidationError):
                registry.load_decision_assurance_history_series_release_registry(link)

    def test_persisted_release_directories_can_be_admitted_and_reloaded(self):
        ready, held = self.ready("persisted"), self.held("persisted-held")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ready_directory, held_directory = root / "ready", root / "held"
            self.fixture.write_package(ready, ready_directory)
            self.fixture.write_package(held, held_directory)
            loaded = tuple(registry.release_model.load_decision_assurance_history_series_release_package(path) for path in (ready_directory, held_directory))
            value = self.build(loaded)
            destination = root / "registry"
            self.write(value, destination)
            self.assertEqual(registry.load_decision_assurance_history_series_release_registry(destination).summary(), value.summary())

    def test_registry_diff_stable_keys_are_sorted_and_distinguish_all_membership_actions(self):
        baseline = self.build((self.ready("same"), self.held("removed")))
        candidate = self.build((self.blocked("same"), self.ready("added")))
        value = registry.build_decision_assurance_history_series_release_registry_diff(baseline, candidate)
        self.assertEqual([item.key for item in value.items], sorted(item.key for item in value.items))
        self.assertEqual({item.action for item in value.items}, {"added", "removed", "changed"})
        self.assertEqual({item.direction for item in value.items}, {"improved", "regressed", "changed"})

    def test_reloaded_registry_has_the_same_canonical_exports_and_receipt(self):
        value = self.build((self.ready(), self.held()))
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "registry"
            self.write(value, destination)
            loaded = registry.load_decision_assurance_history_series_release_registry(destination)
            self.assertEqual(registry.decision_assurance_history_series_release_registry_json(loaded), registry.decision_assurance_history_series_release_registry_json(value))
            self.assertEqual(registry.decision_assurance_history_series_release_registry_csv(loaded), registry.decision_assurance_history_series_release_registry_csv(value))
            self.assertEqual(loaded.content_address, value.content_address)

    def test_blocked_only_registry_is_valid_but_release_readiness_is_false(self):
        value = self.build((self.blocked("blocked"),))
        self.assertEqual((value.accepted_count, value.release_ready_count, value.blocked_count), (0, 0, 1))
        self.assertFalse(value.entries[0].accepted)
        self.assertFalse(value.entries[0].release_ready)
        self.assertEqual(registry.query_decision_assurance_history_series_release_registry(value, resource="rejected").returned_count, 1)

    def test_query_projections_keep_only_public_registry_fields(self):
        value = self.build((self.ready(), self.held()))
        result = registry.query_decision_assurance_history_series_release_registry(value, resource="entries")
        allowed = {"ordinal", "package_id", "release_id", "package_address", "release_address", "state", "accepted", "release_ready", "content_address"}
        self.assertTrue(all(set(item) <= allowed for item in result.items))

    def test_typed_diff_and_registry_exports_fail_after_mutation(self):
        value = self.build((self.ready(),))
        diff = registry.build_decision_assurance_history_series_release_registry_diff(value, value)
        value.content_address = "registry:tampered"
        with self.assertRaises(ValidationError):
            registry.decision_assurance_history_series_release_registry_json(value)
        diff.content_address = "diff:tampered"
        with self.assertRaises(ValidationError):
            registry.decision_assurance_history_series_release_registry_diff_json(diff)

    def test_registry_summary_query_is_single_row_even_for_many_entries(self):
        value = self.build((self.ready("one"), self.ready("two"), self.held("three")))
        result = registry.query_decision_assurance_history_series_release_registry(value, resource="summary", limit=registry.MAX_QUERY_ITEMS)
        self.assertEqual(result.returned_count, 1)
        self.assertEqual(result.items[0]["entry_count"], 3)

    def test_release_ready_query_excludes_held_and_blocked_entries(self):
        value = self.build((self.ready(), self.held(), self.blocked()))
        result = registry.query_decision_assurance_history_series_release_registry(value, resource="release-ready")
        self.assertEqual([item["state"] for item in result.items], ["ready"])

    def test_diff_summary_query_is_single_row_and_keeps_direction_counts(self):
        value = self.build((self.ready(),))
        diff = registry.build_decision_assurance_history_series_release_registry_diff(value, value)
        result = registry.query_decision_assurance_history_series_release_registry_diff(diff, resource="summary")
        self.assertEqual(result.returned_count, 1)
        self.assertEqual(result.items[0]["unchanged_count"], 1)

    def test_diff_item_addresses_remain_unique_after_multiple_changes(self):
        baseline = self.build((self.ready("one"), self.held("two"), self.blocked("three")))
        candidate = self.build((self.blocked("one"), self.ready("two"), self.ready("four")))
        diff = registry.build_decision_assurance_history_series_release_registry_diff(baseline, candidate)
        addresses = [item.content_address for item in diff.items]
        self.assertEqual(len(addresses), len(set(addresses)))

    def test_registry_schema_limits_are_consistent_with_runtime_bounds(self):
        schema = registry.decision_assurance_history_series_release_registry_schema()
        self.assertEqual(schema["properties"]["entry_count"]["maximum"], registry.MAX_ENTRIES)
        self.assertEqual(schema["$defs"]["entry"]["properties"]["ordinal"]["maximum"], registry.MAX_ENTRIES - 1)


class RegistryDeepContractTests(RegistryFixture):
    def test_duplicate_package_identity_is_rejected_before_sorting(self):
        with self.assertRaises(ValidationError):
            self.build((self.ready("duplicate"), self.ready("duplicate")))

    def test_duplicate_release_identity_is_rejected_even_with_distinct_packages(self):
        first = self.fixture.ready_package(package_id="package:first", release_id="release:shared")
        second = self.fixture.ready_package(package_id="package:second", release_id="release:shared")
        with self.assertRaises(ValidationError):
            self.build((first, second))

    def test_verify_returns_the_same_canonical_registry_projection(self):
        value = self.build((self.ready("one"), self.held("two"), self.blocked("three")))
        verified = registry.verify_decision_assurance_history_series_release_registry(value)
        self.assertEqual(verified.to_dict(), value.to_dict())
        self.assertEqual(verified.content_address, value.content_address)
        self.assertEqual(verified.accepted_count, 2)
        self.assertEqual(verified.release_ready_count, 1)

    def test_query_text_filter_matches_public_identity_fields_case_insensitively(self):
        value = self.build((self.ready("alpha"), self.held("beta"), self.blocked("gamma")))
        result = registry.query_decision_assurance_history_series_release_registry(value, resource="entries", text="PACKAGE:BETA")
        self.assertEqual(result.returned_count, 1)
        self.assertEqual(result.items[0]["package_id"], "package:beta")
        self.assertEqual(result.items[0]["state"], "hold")

    def test_registry_query_exports_are_canonical_after_pagination(self):
        value = self.build((self.ready("one"), self.ready("two"), self.held("three")))
        query = registry.ReleaseRegistryQuery(resource="entries", offset=1, limit=1, text="package")
        result = registry.query_decision_assurance_history_series_release_registry(value, query=query)
        body = result.to_dict()
        reloaded = registry.ReleaseRegistryQueryResult(
            body["registry_address"],
            registry.ReleaseRegistryQuery(**body["query"]),
            body["total_count"],
            body["returned_count"],
            body["items"],
            body["content_address"],
        )
        self.assertEqual(reloaded.to_dict(), result.to_dict())
        self.assertEqual(registry.decision_assurance_history_series_release_registry_query_json(result), registry.decision_assurance_history_series_release_registry_query_json(reloaded))
        self.assertEqual(result.items[0]["ordinal"], 1)

    def test_diff_resources_partition_added_removed_changed_and_unchanged(self):
        baseline = self.build((self.ready("same"), self.ready("removed"), self.blocked("changed")))
        candidate = self.build((self.ready("same"), self.ready("added"), self.ready("changed")))
        value = registry.build_decision_assurance_history_series_release_registry_diff(baseline, candidate)
        expected = {
            "items": 4,
            "added": 1,
            "removed": 1,
            "changed": 1,
            "unchanged": 1,
            "improved": 2,
            "regressed": 1,
        }
        for resource, count in expected.items():
            with self.subTest(resource=resource):
                result = registry.query_decision_assurance_history_series_release_registry_diff(value, resource=resource)
                self.assertEqual(result.total_count, count)
                self.assertEqual(result.returned_count, count)

    def test_diff_query_text_filter_does_not_expose_nested_release_payloads(self):
        baseline = self.build((self.ready("same"),))
        candidate = self.build((self.blocked("same"), self.ready("added")))
        value = registry.build_decision_assurance_history_series_release_registry_diff(baseline, candidate)
        result = registry.query_decision_assurance_history_series_release_registry_diff(value, resource="regressed", text="package:same")
        self.assertEqual(result.returned_count, 1)
        serialized = json.dumps(result.to_dict(), sort_keys=True).casefold()
        for forbidden in ("source_path", "raw_payload", "agent", "language", "model"):
            self.assertNotIn(f'"{forbidden}"', serialized)

    def test_diff_projection_round_trip_preserves_action_direction_and_addresses(self):
        baseline = self.build((self.blocked("same"), self.held("removed")))
        candidate = self.build((self.ready("same"), self.ready("added")))
        value = registry.build_decision_assurance_history_series_release_registry_diff(baseline, candidate)
        loaded = registry.decision_assurance_history_series_release_registry_diff_from_mapping(value.to_dict())
        self.assertEqual([(item.key, item.action, item.direction) for item in loaded.items], [(item.key, item.action, item.direction) for item in value.items])
        self.assertEqual([item.content_address for item in loaded.items], [item.content_address for item in value.items])
        self.assertEqual(loaded.content_address, value.content_address)

    def test_contract_schemas_list_only_transportable_public_fields(self):
        registry_fields = set(registry.decision_assurance_history_series_release_registry_schema()["properties"])
        entry_fields = set(registry.decision_assurance_history_series_release_registry_entry_schema()["properties"])
        diff_fields = set(registry.decision_assurance_history_series_release_registry_diff_schema()["properties"])
        self.assertEqual(registry_fields, {"registry_id", "version", "boundary", "entry_count", "ready_count", "hold_count", "blocked_count", "accepted_count", "release_ready_count", "entries", "content_address"})
        self.assertEqual(entry_fields, {"ordinal", "package_id", "release_id", "package_address", "release_address", "state", "accepted", "release_ready", "content_address"})
        self.assertEqual(diff_fields, {"diff_id", "version", "boundary", "baseline_address", "candidate_address", "item_count", "added_count", "removed_count", "unchanged_count", "changed_count", "improved_count", "regressed_count", "state", "accepted", "release_ready", "items", "content_address"})
        self.assertTrue(registry_fields.isdisjoint({"source_path", "raw_payload", "private_metadata"}))


class RegistryCliApiTests(RegistryFixture):
    base = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-series-release-registry"

    @staticmethod
    def capture_cli(arguments):
        output = StringIO()
        with redirect_stdout(output):
            status = main(arguments)
        return status, output.getvalue()

    def test_cli_builds_verifies_queries_diffs_and_schemas(self):
        first_package = self.ready("first")
        held_package = self.held("held")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first_directory, held_directory = root / "first", root / "held"
            self.fixture.write_package(first_package, first_directory)
            self.fixture.write_package(held_package, held_directory)
            registry_directory = root / "registry"
            status, output = self.capture_cli([self.base, "--input", str(first_directory), "--input", str(held_directory), "--registry-id", "registry:cli", "--destination", str(registry_directory), "--format", "summary"])
            self.assertEqual(status, 0)
            self.assertIn('"entry_count": 2', output)
            status, output = self.capture_cli([self.base + "-verify", "--input", str(registry_directory)])
            self.assertEqual(status, 0)
            self.assertIn('"accepted_count": 2', output)
            status, output = self.capture_cli([self.base + "-query", "--input", str(registry_directory), "--resource", "entries"])
            self.assertEqual(status, 0)
            self.assertIn('"returned_count": 2', output)
            diff_directory = root / "diff"
            status, output = self.capture_cli([self.base + "-diff", "--baseline", str(registry_directory), "--candidate", str(registry_directory), "--destination", str(diff_directory), "--format", "summary"])
            self.assertEqual(status, 0)
            self.assertTrue((diff_directory / registry.DIFF_NAME).is_file())
            status, output = self.capture_cli([self.base + "-diff-verify", "--input", str(diff_directory)])
            self.assertEqual(status, 0)
            self.assertIn('"state": "unchanged"', output)
            for suffix in ("-schema", "-entry-schema", "-query-schema", "-diff-schema", "-diff-item-schema", "-diff-query-schema", "-capabilities"):
                status, output = self.capture_cli([self.base + suffix])
                self.assertEqual(status, 0)
                self.assertTrue(output.strip())

    def test_api_reads_registry_queries_verifies_diff_and_contracts(self):
        value = self.build((self.ready("api"), self.held("api-held")))
        diff = registry.build_decision_assurance_history_series_release_registry_diff(value, value, diff_id="diff:api")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry_directory, diff_directory = root / "registry", root / "diff"
            self.write(value, registry_directory)
            self.write_diff(diff, diff_directory)
            server = create_server("127.0.0.1", 0)
            server.glio_assurance_history_series_release_registry_directory = str(registry_directory)
            server.glio_assurance_history_series_release_registry_diff_directory = str(diff_directory)
            import threading

            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry"
                summary = json.loads(urlopen(base + "?format=summary", timeout=10).read().decode())
                self.assertEqual(summary["entry_count"], 2)
                query = json.loads(urlopen(base + "/query?resource=ready", timeout=10).read().decode())
                self.assertEqual(query["returned_count"], 1)
                verified = json.loads(urlopen(base + "/verify", timeout=10).read().decode())
                self.assertEqual(verified["accepted_count"], 2)
                diff_summary = json.loads(urlopen(base + "/diff?format=summary", timeout=10).read().decode())
                self.assertEqual(diff_summary["state"], "unchanged")
                schema = json.loads(urlopen(base + "/schema", timeout=10).read().decode())
                self.assertFalse(schema["additionalProperties"])
                capabilities = json.loads(urlopen(base + "/capabilities", timeout=10).read().decode())
                self.assertEqual(capabilities["package"]["files"], list(registry.FILES))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)


if __name__ == "__main__":
    unittest.main()
