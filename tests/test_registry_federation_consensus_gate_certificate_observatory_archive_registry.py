"""Contract tests for the archive registry, diff, runtime, and history planes.

The fixture starts with the same package-shaped directory used by the existing
downloaded-data tests.  Every assertion stays at the public boundary: paths
are inputs only, while the values under test contain labels, counters,
decisions, and replayable content addresses.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive as archive_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry as registry_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_audit as registry_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_diff as diff_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_diff_audit as diff_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_diff_query as diff_query_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_diff_query_audit as diff_query_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_history as history_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_history_audit as history_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_query as query_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_query_audit as query_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_runtime as runtime_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_runtime_audit as runtime_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_report as report_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_report_audit as report_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_package as package_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from tests import test_registry_federation_consensus_gate_certificate_observatory_archive as source_archive_tests


class ArchiveRegistryFixture(unittest.TestCase):
    """Build repeatable archive inputs from the current downloaded fixture."""

    def setUp(self) -> None:
        self.source_fixture = source_archive_tests.CertificateObservatoryArchiveTests("runTest")
        self.source_fixture.setUp()

    def package(self, root: Path, package_id: str = "downloaded-observatory-package"):
        return self.source_fixture._package(root / package_id, package_id=package_id)

    def package_directory(self, root: Path, package_id: str = "downloaded-observatory-package") -> Path:
        value = self.package(root, package_id)
        destination = root / (package_id + "-directory")
        package_model.write_package(value, destination)
        return destination

    def archive(self, root: Path, archive_id: str, package_id: str = "downloaded-observatory-package"):
        value = self.package(root / archive_id, package_id)
        return archive_model.build_archive(value, archive_id=archive_id)

    def registry(self, root: Path, *archive_ids: str, registry_id: str = "downloaded-observatory-registry"):
        archives = tuple(self.archive(root / "archives", archive_id) for archive_id in archive_ids)
        return registry_model.build_registry_from_archives(archives, entry_ids=tuple("entry-" + item for item in archive_ids), registry_id=registry_id)

    def assert_public(self, value: object) -> None:
        encoded = json.dumps(value.to_dict() if hasattr(value, "to_dict") else value, sort_keys=True, default=list).lower()
        for forbidden in ("local_path", "generated_by", "agent", "assistant", "language", "private_key", "secret", "token"):
            self.assertNotIn(forbidden, encoded)

    def assert_closed_schema(self, schema: dict[str, object]) -> None:
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["required"]), set(schema["properties"]))

    def test_entry_derives_public_metrics_from_an_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = self.archive(Path(temporary), "entry-source")
            entry = registry_model.entry_from_archive(archive, entry_id="first-entry")
            self.assertEqual(entry.entry_id, "first-entry")
            self.assertEqual(entry.archive_id, "entry-source")
            self.assertEqual(entry.archive_address, archive.content_address)
            self.assertEqual(entry.package_address, archive.package_address)
            self.assertGreater(entry.archive_size, 0)
            self.assertGreater(entry.observation_count, 0)
            self.assertGreater(entry.total_check_count, 0)
            self.assertGreaterEqual(entry.total_failed_count, 0)
            self.assertEqual(entry.content_address, registry_model.address_entry(entry))
            self.assert_public(entry)

    def test_entry_from_archive_file_uses_file_size_and_rejects_links(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self.archive(root, "file-source")
            path = root / "source.zip"
            archive_model.write_archive(archive, path)
            entry = registry_model.entry_from_archive_file(path, entry_id="file-entry")
            self.assertEqual(entry.archive_size, path.stat().st_size)
            link = root / "link.zip"
            try:
                link.symlink_to(path)
            except (OSError, NotImplementedError):
                link = None
            if link is not None:
                with self.assertRaises(ValidationError):
                    registry_model.entry_from_archive_file(link)

    def test_registry_sorts_entries_and_builds_package_groups(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = self.package(root, "shared-package")
            first = archive_model.build_archive(package, archive_id="archive-a")
            second = archive_model.build_archive(package, archive_id="archive-b")
            entries = (registry_model.entry_from_archive(second, entry_id="z-entry"), registry_model.entry_from_archive(first, entry_id="a-entry"))
            value = registry_model.build_registry(entries, registry_id="sorted-registry")
            self.assertEqual(tuple(item.entry_id for item in value.entries), ("a-entry", "z-entry"))
            self.assertEqual(value.entry_count, 2)
            self.assertEqual(value.metrics.entry_count, 2)
            self.assertEqual(value.metrics.unique_package_count, 1)
            self.assertEqual(len(value.index.groups), 1)
            self.assertEqual(value.index.groups[0].entry_ids, ("a-entry", "z-entry"))
            self.assertEqual(value.index.groups[0].archive_addresses, (first.content_address, second.content_address))
            self.assertEqual(value.content_address, registry_model.address_registry(value))
            self.assert_public(value)

    def test_registry_rejects_duplicate_entry_archive_and_address_identities(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.archive(root, "duplicate-source")
            duplicate_entry = registry_model.entry_from_archive(first, entry_id="duplicate-entry")
            with self.assertRaises(ValidationError):
                registry_model.build_registry((duplicate_entry, duplicate_entry))
            second = archive_model.build_archive(first.package, archive_id="other-archive")
            duplicate_archive = registry_model.entry_from_archive(second, entry_id="duplicate-entry")
            with self.assertRaises(ValidationError):
                registry_model.build_registry((duplicate_entry, duplicate_archive))
            duplicate_archive_id = registry_model.entry_from_archive(second, entry_id="second-entry")
            duplicate_archive_id.archive_id = first.archive_id
            with self.assertRaises(ValidationError):
                registry_model.build_registry((duplicate_entry, duplicate_archive_id))

    def test_metrics_conserve_entry_projections(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.registry(Path(temporary), "metric-a", "metric-b", "metric-c")
            metrics = value.metrics
            self.assertEqual(metrics.entry_count, len(value.entries))
            self.assertEqual(metrics.archive_bytes, sum(item.archive_size for item in value.entries))
            self.assertEqual(metrics.accepted_count + metrics.held_count, metrics.entry_count)
            self.assertEqual(metrics.observation_count, sum(item.observation_count for item in value.entries))
            self.assertEqual(metrics.total_check_count, sum(item.total_check_count for item in value.entries))
            self.assertEqual(metrics.total_failed_count, sum(item.total_failed_count for item in value.entries))
            self.assertEqual(metrics.alert_count, sum(item.alert_count for item in value.entries))
            self.assertEqual(metrics.unique_package_count, len({item.package_id for item in value.entries}))

    def test_registry_mapping_round_trip_and_address_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.registry(Path(temporary), "mapping-a", "mapping-b")
            encoded = value.to_dict()
            restored = registry_model.registry_from_mapping(encoded)
            self.assertEqual(restored.to_dict(), encoded)
            self.assertEqual(registry_model.registry_json(restored), registry_model.registry_json(value))
            self.assertEqual(registry_model.manifest_document(value), registry_model.manifest_document(restored))
            self.assertEqual(registry_model.address_registry(restored), value.content_address)
            self.assertEqual(registry_model.verify_registry(restored).content_address, value.content_address)

    def test_registry_directory_has_exact_canonical_members_and_reloads(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.registry(root, "persist-a", "persist-b", registry_id="persisted-registry")
            destination = root / "registry"
            registry_model.write_registry(value, destination)
            self.assertEqual(tuple(sorted(item.name for item in destination.iterdir())), tuple(sorted(registry_model.FILES)))
            self.assertEqual(registry_model.verify_registry_directory(destination).content_address, value.content_address)
            loaded = registry_model.load_registry(destination)
            self.assertEqual(loaded.to_dict(), value.to_dict())
            self.assertEqual(registry_model.registry_bytes(loaded), registry_model.registry_bytes(value))
            with self.assertRaises(ValidationError):
                registry_model.write_registry(value, destination)
            registry_model.write_registry(value, destination, overwrite=True)
            self.assertEqual(registry_model.load_registry(destination).content_address, value.content_address)

    def test_registry_persistence_rejects_extra_member_noncanonical_json_and_tampered_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.registry(root, "tamper-a")
            destination = root / "registry"
            registry_model.write_registry(value, destination)
            (destination / "extra.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                registry_model.load_registry(destination)
            (destination / "extra.json").unlink()
            registry_raw = (destination / registry_model.REGISTRY_NAME).read_bytes()
            (destination / registry_model.REGISTRY_NAME).write_bytes(registry_raw + b" ")
            with self.assertRaises(ValidationError):
                registry_model.load_registry(destination)
            (destination / registry_model.REGISTRY_NAME).write_bytes(registry_raw)
            manifest = json.loads((destination / registry_model.MANIFEST_NAME).read_text(encoding="utf-8"))
            manifest["artifacts"][0]["hash"] = "bad:hash"
            (destination / registry_model.MANIFEST_NAME).write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")), encoding="utf-8")
            with self.assertRaises(ValidationError):
                registry_model.load_registry(destination)

    def test_registry_audit_exposes_all_independent_checks(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.registry(Path(temporary), "audit-a", "audit-b")
            audit = registry_audit_model.audit_registry(value)
            self.assertTrue(audit.accepted)
            self.assertEqual(audit.check_count, len(registry_audit_model.CHECK_IDS))
            self.assertEqual(audit.passed_count, len(registry_audit_model.CHECK_IDS))
            self.assertEqual(audit.failed_count, 0)
            self.assertEqual(tuple(item.check_id for item in audit.checks), registry_audit_model.CHECK_IDS)
            self.assertEqual(registry_audit_model.audit_from_mapping(audit.to_dict()).to_dict(), audit.to_dict())
            self.assertIn("archive registry", registry_audit_model.render_audit_markdown(audit).lower())
            self.assertIn("check_id", registry_audit_model.audit_csv(audit))
            self.assertTrue(registry_audit_model.audit_json(audit).startswith("{"))
            self.assert_public(audit)

    def test_registry_query_resources_filters_and_pages(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.registry(Path(temporary), "query-a", "query-b", "query-c")
            result = query_model.query_registry(value, resources=query_model.RESOURCES, limit=4096)
            self.assertTrue(query_audit_model.audit_query(result, value).accepted)
            self.assertEqual(result.total_count, 5)
            self.assertEqual(result.matched_count, 5)
            self.assertEqual(result.returned_count, 5)
            self.assertFalse(result.truncated)
            self.assertEqual(result.rows[0].resource, "summary")
            self.assertEqual(tuple(item.ordinal for item in result.rows), (1, 2, 3, 4, 5))
            entries = query_model.query_registry(value, resources=("entries",), package_id=value.entries[0].package_id, limit=1)
            self.assertEqual(entries.matched_count, 3)
            self.assertEqual(entries.returned_count, 1)
            self.assertTrue(entries.truncated)
            self.assertEqual(entries.next_offset, 1)
            packages = query_model.query_registry(value, resources=("entries",), archive_id="query-b", limit=20)
            self.assertEqual(packages.matched_count, 1)
            self.assertEqual(packages.rows[0].archive_id, "query-b")
            held = query_model.query_registry(value, resources=("accepted",), accepted=False, limit=20)
            self.assertGreaterEqual(held.matched_count, 0)
            self.assertTrue(all(not row.accepted for row in held.rows))

    def test_registry_query_result_mapping_and_audit_tamper_detection(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.registry(Path(temporary), "query-roundtrip-a", "query-roundtrip-b")
            result = query_model.query_registry(value, resources=("summary", "entries", "packages"), limit=20)
            restored = query_model.query_from_mapping(result.to_dict())
            self.assertEqual(restored.to_dict(), result.to_dict())
            self.assertEqual(query_model.query_json(restored), query_model.query_json(result))
            audit = query_audit_model.audit_query(restored, value)
            self.assertTrue(audit.accepted)
            altered = json.loads(query_model.query_json(result))
            altered["rows"][0]["ordinal"] = 99
            with self.assertRaises(ValidationError):
                query_model.query_from_mapping(altered)
            altered = json.loads(query_model.query_json(result))
            altered["query"]["resources"] = ["unknown"]
            with self.assertRaises(ValidationError):
                query_model.query_from_mapping(altered)

    def test_query_schema_and_capability_contracts_are_closed(self):
        schemas = (registry_model.entry_schema(), registry_model.metrics_schema(), registry_model.group_schema(), registry_model.index_schema(), registry_model.manifest_schema(), registry_model.registry_schema(), registry_audit_model.check_schema(), registry_audit_model.audit_schema(), query_model.query_schema(), query_model.row_schema(), query_model.result_schema(), query_audit_model.check_schema(), query_audit_model.audit_schema(), diff_model.item_schema(), diff_model.diff_schema(), diff_audit_model.check_schema(), diff_audit_model.audit_schema(), diff_query_model.query_schema(), diff_query_model.row_schema(), diff_query_model.result_schema(), diff_query_audit_model.check_schema(), diff_query_audit_model.audit_schema(), runtime_model.runtime_schema(), runtime_audit_model.check_schema(), runtime_audit_model.audit_schema(), history_model.entry_schema(), history_model.history_schema(), history_model.manifest_schema(), history_audit_model.check_schema(), history_audit_model.audit_schema())
        for schema in schemas:
            self.assert_closed_schema(schema)
        capabilities = (registry_model.capabilities(), registry_audit_model.capabilities(), query_model.capabilities(), query_audit_model.capabilities(), diff_model.capabilities(), diff_audit_model.capabilities(), diff_query_model.capabilities(), diff_query_audit_model.capabilities(), runtime_model.capabilities(), runtime_audit_model.capabilities(), history_model.capabilities(), history_audit_model.capabilities())
        for capability in capabilities:
            self.assert_public(type("Capability", (), {"to_dict": lambda self, item=capability: item})())
            self.assertIsInstance(capability["boundary"], str)

    def test_diff_reports_added_removed_changed_and_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shared = self.package(root, "diff-shared")
            left_a = archive_model.build_archive(shared, archive_id="same-archive")
            left_b = archive_model.build_archive(shared, archive_id="removed-archive")
            right_a = archive_model.build_archive(shared, archive_id="same-archive")
            right_b = archive_model.build_archive(shared, archive_id="added-archive")
            left = registry_model.build_registry_from_archives((left_a, left_b), entry_ids=("same-entry", "removed-entry"), registry_id="left")
            right = registry_model.build_registry_from_archives((right_a, right_b), entry_ids=("same-entry", "added-entry"), registry_id="right")
            value = diff_model.build_diff(left, right, diff_id="four-way-diff")
            self.assertEqual(value.added_count, 1)
            self.assertEqual(value.removed_count, 1)
            self.assertEqual(value.changed_count, 0)
            self.assertEqual(value.unchanged_count, 1)
            self.assertEqual(tuple(item.change_type for item in value.items), ("added", "removed"))
            self.assertEqual(value.content_address, diff_model.address_diff(value))
            self.assertTrue(diff_audit_model.audit_diff(value, left, right).accepted)

    def test_diff_reports_changed_fields_when_entry_identity_is_stable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = self.package(root, "changed-package")
            left_archive = archive_model.build_archive(package, archive_id="changed-archive")
            right_archive = archive_model.build_archive(package, archive_id="changed-archive")
            left_entry = registry_model.entry_from_archive(left_archive, entry_id="changed-entry", archive_size=left_archive.archive_size)
            right_entry = registry_model.entry_from_archive(right_archive, entry_id="changed-entry", archive_size=left_archive.archive_size + 1)
            left = registry_model.build_registry((left_entry,), registry_id="left-changed")
            right = registry_model.build_registry((right_entry,), registry_id="right-changed")
            value = diff_model.build_diff(left, right)
            self.assertEqual(value.changed_count, 1)
            self.assertEqual(value.items[0].change_type, "changed")
            self.assertIn("archive_size", value.items[0].changed_fields)
            self.assertTrue(diff_audit_model.audit_diff(value, left, right).accepted)

    def test_diff_mapping_query_and_query_audit_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            left = self.registry(Path(temporary) / "left", "diff-left")
            right = self.registry(Path(temporary) / "right", "diff-left", "diff-added")
            value = diff_model.build_diff(left, right, diff_id="queryable-diff")
            restored = diff_model.diff_from_mapping(value.to_dict())
            self.assertEqual(restored.to_dict(), value.to_dict())
            query = diff_query_model.query_diff(value, resources=diff_query_model.RESOURCES, limit=20)
            self.assertEqual(query.total_count, 2)
            self.assertEqual(query.returned_count, 2)
            self.assertEqual(tuple(row.ordinal for row in query.rows), (1, 2))
            self.assertTrue(diff_query_audit_model.audit_query(query, value).accepted)
            added = diff_query_model.query_diff(value, resources=("added",), change_type="added", limit=20)
            self.assertEqual(added.matched_count, 1)
            self.assertEqual(added.rows[0].change_type, "added")
            self.assertEqual(diff_query_model.query_from_mapping(query.to_dict()).to_dict(), query.to_dict())
            altered = json.loads(diff_query_model.query_json(query))
            altered["rows"][0]["content_address"] = "bad:row"
            with self.assertRaises(ValidationError):
                diff_query_model.query_from_mapping(altered)

    def test_runtime_materializes_archives_from_a_downloaded_package_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package_directory = self.package_directory(root, "runtime-package")
            destination = root / "runtime-registry"
            value = runtime_model.run_runtime((package_directory, package_directory), runtime_id="downloaded-registry-runtime", registry_id="runtime-registry", entry_ids=("runtime-primary", "runtime-replica"), archive_ids=("runtime-primary-archive", "runtime-replica-archive"), destination=destination, limit=100)
            self.assertTrue(value.accepted)
            self.assertEqual(value.input_count, 2)
            self.assertTrue(value.registry_written)
            self.assertTrue(destination.is_dir())
            self.assertTrue(runtime_audit_model.audit_runtime(value).accepted)
            self.assertEqual(runtime_model.runtime_from_mapping(value.to_dict()).to_dict(), value.to_dict())

    def test_runtime_rejects_mismatched_archive_and_entry_id_lists_before_io(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package_directory = self.package_directory(root, "runtime-bounds")
            with self.assertRaises(ValidationError):
                runtime_model.run_runtime((package_directory, package_directory), entry_ids=("only-one",))
            with self.assertRaises(ValidationError):
                runtime_model.run_runtime((package_directory, package_directory), archive_ids=("only-one",))
            with self.assertRaises(ValidationError):
                registry_model.build_registry_from_archive_files((root / "missing-a.zip", root / "missing-b.zip"), entry_ids=("only-one",))

    def test_history_preserves_predecessor_chain_and_transition_counts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.registry(root / "one", "history-a", registry_id="history-one-registry")
            second = self.registry(root / "two", "history-a", "history-b", registry_id="history-two-registry")
            third = self.registry(root / "three", "history-b", registry_id="history-three-registry")
            value = history_model.build_history((first, second, third), history_id="archive-registry-history", snapshot_ids=("initial", "expanded", "trimmed"))
            self.assertEqual(value.entry_count, 3)
            self.assertEqual(value.transition_count, 2)
            self.assertEqual(tuple(item.snapshot_id for item in value.entries), ("initial", "expanded", "trimmed"))
            self.assertEqual(value.entries[0].predecessor_address, "")
            self.assertEqual(value.entries[1].predecessor_address, value.entries[0].registry_address)
            self.assertEqual(value.entries[2].predecessor_address, value.entries[1].registry_address)
            self.assertEqual(value.added_count, 1)
            self.assertEqual(value.removed_count, 1)
            self.assertTrue(history_audit_model.audit_history(value, (first, second, third)).accepted)
            self.assertEqual(history_model.history_from_mapping(value.to_dict()).to_dict(), value.to_dict())

    def test_history_directory_replay_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.registry(root / "first", "history-persist-a")
            second = self.registry(root / "second", "history-persist-a", "history-persist-b")
            value = history_model.build_history((first, second), history_id="persisted-history")
            destination = root / "history"
            history_model.write_history(value, destination)
            self.assertEqual(tuple(sorted(item.name for item in destination.iterdir())), tuple(sorted(history_model.FILES)))
            self.assertEqual(history_model.load_history(destination).to_dict(), value.to_dict())
            self.assertEqual(history_model.verify_history_directory(destination).content_address, value.content_address)
            manifest = json.loads((destination / history_model.MANIFEST_NAME).read_text(encoding="utf-8"))
            manifest["history_address"] = "bad:history"
            (destination / history_model.MANIFEST_NAME).write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")), encoding="utf-8")
            with self.assertRaises(ValidationError):
                history_model.load_history(destination)

    def test_cli_builds_a_registry_and_exposes_all_new_schema_commands(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package_directory = self.package_directory(root, "cli-package")
            registry_directory = root / "cli-registry"
            output = root / "registry.json"
            with contextlib.redirect_stdout(io.StringIO()):
                status = main(["registry-federation-consensus-gate-certificate-observatory-archive-registry", "--input", str(package_directory), "--input", str(package_directory), "--entry-id", "cli-entry-a", "--entry-id", "cli-entry-b", "--archive-id", "cli-archive-a", "--archive-id", "cli-archive-b", "--destination", str(registry_directory), "--format", "json", "--output", str(output)])
            self.assertEqual(status, 0)
            self.assertEqual(registry_model.load_registry(registry_directory).entry_count, 2)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["registry-federation-consensus-gate-certificate-observatory-archive-registry-audit", "--input", str(registry_directory), "--format", "json", "--output", str(root / "audit.json")]), 0)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["registry-federation-consensus-gate-certificate-observatory-archive-registry-query", "--input", str(registry_directory), "--resource", "entries", "--format", "json", "--output", str(root / "query.json")]), 0)
            self.assertEqual(json.loads((root / "query.json").read_text(encoding="utf-8"))["returned_count"], 2)
            commands = ("registry-federation-consensus-gate-certificate-observatory-archive-registry-entry-schema", "registry-federation-consensus-gate-certificate-observatory-archive-registry-schema", "registry-federation-consensus-gate-certificate-observatory-archive-registry-query-result-schema", "registry-federation-consensus-gate-certificate-observatory-archive-registry-diff-schema", "registry-federation-consensus-gate-certificate-observatory-archive-registry-diff-query-result-schema", "registry-federation-consensus-gate-certificate-observatory-archive-registry-runtime-schema", "registry-federation-consensus-gate-certificate-observatory-archive-registry-history-schema")
            for command in commands:
                with contextlib.redirect_stdout(io.StringIO()) as captured:
                    self.assertEqual(main([command]), 0)
                self.assertIsInstance(json.loads(captured.getvalue()), dict)

    def test_cli_diff_runtime_and_history_outputs_are_replayable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package_directory = self.package_directory(root, "cli-flow-package")
            left_directory = root / "left-registry"
            right_directory = root / "right-registry"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["registry-federation-consensus-gate-certificate-observatory-archive-registry", "--input", str(package_directory), "--entry-id", "left-entry", "--archive-id", "left-archive", "--destination", str(left_directory)]), 0)
                self.assertEqual(main(["registry-federation-consensus-gate-certificate-observatory-archive-registry", "--input", str(package_directory), "--input", str(package_directory), "--entry-id", "left-entry", "--entry-id", "right-entry", "--archive-id", "left-archive", "--archive-id", "right-archive", "--destination", str(right_directory)]), 0)
            diff_output = root / "diff.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["registry-federation-consensus-gate-certificate-observatory-archive-registry-diff", "--left", str(left_directory), "--right", str(right_directory), "--format", "json", "--output", str(diff_output)]), 0)
            diff_value = diff_model.diff_from_mapping(json.loads(diff_output.read_text(encoding="utf-8")))
            self.assertEqual(diff_value.added_count, 1)
            history_output = root / "history.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["registry-federation-consensus-gate-certificate-observatory-archive-registry-history", "--input", str(left_directory), "--input", str(right_directory), "--format", "json", "--output", str(history_output)]), 0)
            self.assertEqual(history_model.history_from_mapping(json.loads(history_output.read_text(encoding="utf-8"))).transition_count, 1)

    def test_http_registry_namespace_supports_build_query_diff_and_schemas(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package_directory = self.package_directory(root, "http-package")
            left = self.registry(root / "left", "http-left")
            right = self.registry(root / "right", "http-left", "http-right")
            left_directory = root / "left-registry"
            right_directory = root / "right-registry"
            registry_model.write_registry(left, left_directory)
            registry_model.write_registry(right, right_directory)
            server = create_server("127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}/v1/registry/federation/consensus/gate/certificate/observatory/archive/registry"
                for suffix in ("/schema", "/entry-schema", "/audit/schema", "/query/result-schema", "/query-audit/schema", "/diff/schema", "/diff/audit/schema", "/diff/query/result-schema", "/runtime/schema", "/history/schema", "/history/audit/schema", "/report/alert-schema", "/report/schema", "/report/audit/check-schema", "/report/audit/schema", "/capabilities"):
                    with urlopen(base + suffix, timeout=15) as response:
                        self.assertEqual(response.status, 200)
                        self.assertIsInstance(json.loads(response.read()), dict)
                query_request = urlencode({"input": str(right_directory), "resource": "entries", "limit": "1", "format": "json"})
                with urlopen(base + "/query?" + query_request, timeout=15) as response:
                    payload = json.loads(response.read())
                    self.assertEqual(payload["returned_count"], 1)
                    query_path = root / "http-query.json"
                    query_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
                audit_request = urlencode({"input": str(query_path), "format": "json"})
                with urlopen(base + "/query-audit?" + audit_request, timeout=15) as response:
                    self.assertTrue(json.loads(response.read())["accepted"])
                diff_request = urlencode({"left": str(left_directory), "right": str(right_directory), "format": "json"})
                with urlopen(base + "/diff?" + diff_request, timeout=15) as response:
                    diff_payload = json.loads(response.read())
                    self.assertEqual(diff_payload["added_count"], 1)
                    diff_path = root / "http-diff.json"
                    diff_path.write_text(json.dumps(diff_payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
                diff_query_request = urlencode({"input": str(diff_path), "resource": "added", "format": "json"})
                with urlopen(base + "/diff/query?" + diff_query_request, timeout=15) as response:
                    self.assertEqual(json.loads(response.read())["returned_count"], 1)
                build_request = urlencode((("input", str(package_directory)), ("input", str(package_directory)), ("entry_id", "http-entry-a"), ("entry_id", "http-entry-b"), ("archive_id", "http-archive-a"), ("archive_id", "http-archive-b"), ("registry_id", "http-built"), ("format", "summary")))
                with urlopen(base + "?" + build_request, timeout=15) as response:
                    self.assertEqual(json.loads(response.read())["entry_count"], 2)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_every_public_projection_is_path_free(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.registry(root, "public-a", "public-b")
            audit = registry_audit_model.audit_registry(value)
            query = query_model.query_registry(value, resources=query_model.RESOURCES, limit=100)
            query_audit = query_audit_model.audit_query(query, value)
            diff = diff_model.build_diff(self.registry(root / "left", "public-a"), value)
            diff_audit = diff_audit_model.audit_diff(diff)
            diff_query = diff_query_model.query_diff(diff, limit=100)
            diff_query_audit = diff_query_audit_model.audit_query(diff_query)
            history = history_model.build_history((self.registry(root / "history-one", "public-a"), value))
            history_audit = history_audit_model.audit_history(history)
            package_directory = self.package_directory(root, "public-runtime-package")
            runtime = runtime_model.run_runtime((package_directory,), entry_ids=("public-runtime-entry",), archive_ids=("public-runtime-archive",))
            runtime_audit = runtime_audit_model.audit_runtime(runtime)
            report = report_model.build_report(value)
            report_audit = report_audit_model.audit_report(report)
            for item in (value, audit, query, query_audit, diff, diff_audit, diff_query, diff_query_audit, history, history_audit, runtime, runtime_audit, report, report_audit):
                self.assert_public(item)

    def test_bounded_query_offsets_and_resources_are_enforced(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.registry(Path(temporary), "bounds-a")
            with self.assertRaises(ValidationError):
                query_model.query_registry(value, resources=("unknown",))
            with self.assertRaises(ValidationError):
                query_model.query_registry(value, offset=-1)
            with self.assertRaises(ValidationError):
                query_model.query_registry(value, limit=0)
            diff = diff_model.build_diff(value, self.registry(Path(temporary) / "right", "bounds-a", "bounds-b"))
            with self.assertRaises(ValidationError):
                diff_query_model.query_diff(diff, resources=("unknown",))
            with self.assertRaises(ValidationError):
                diff_query_model.query_diff(diff, change_type="unknown")
            with self.assertRaises(ValidationError):
                diff_query_model.query_diff(diff, offset=-1)

    def test_address_corruption_is_detected_at_each_public_layer(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.registry(Path(temporary), "address-a", "address-b")
            mapping = value.to_dict()
            mapping["content_address"] = "wrong:address"
            with self.assertRaises(ValidationError):
                registry_model.registry_from_mapping(mapping)
            audit = registry_audit_model.audit_registry(value).to_dict()
            audit["content_address"] = "wrong:address"
            with self.assertRaises(ValidationError):
                registry_audit_model.audit_from_mapping(audit)
            query = query_model.query_registry(value, limit=100).to_dict()
            query["content_address"] = "wrong:address"
            with self.assertRaises(ValidationError):
                query_model.query_from_mapping(query)

    def test_atomic_registry_write_leaves_no_staging_members(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.registry(root, "atomic-a")
            destination = root / "nested" / "registry"
            registry_model.write_registry(value, destination)
            siblings = tuple(item.name for item in destination.parent.iterdir())
            self.assertEqual(siblings, ("registry",))
            self.assertFalse(any("staging" in item.name or "backup" in item.name for item in destination.parent.iterdir()))

    def test_health_report_explains_status_alerts_and_exports(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.registry(Path(temporary), "report-a", "report-b")
            report = report_model.build_report(value, report_id="registry-health")
            audit = report_audit_model.audit_report(report)
            self.assertIn(report.status, report_model.STATUSES)
            self.assertGreaterEqual(report.alert_count, 0)
            self.assertEqual(report.accepted_count + report.held_count, report.entry_count)
            self.assertEqual(report.content_address, report_model.address_report(report))
            self.assertEqual(report_model.report_from_mapping(report.to_dict()).to_dict(), report.to_dict())
            self.assertIn("# Certificate Observatory Archive Registry Report", report_model.render_report_markdown(report))
            self.assertIn("report_id,status", report_model.report_csv(report))
            self.assertTrue(audit.accepted)
            self.assertEqual(audit.check_count, len(report_audit_model.CHECK_IDS))
            self.assertEqual(report_audit_model.audit_from_mapping(audit.to_dict()).to_dict(), audit.to_dict())
            self.assert_public(report)
            self.assert_public(audit)

    def test_health_report_rejects_counter_and_alert_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = report_model.build_report(self.registry(Path(temporary), "report-tamper"), report_id="report-tamper")
            mapping = report.to_dict()
            mapping["alert_count"] = report.alert_count + 1
            with self.assertRaises(ValidationError):
                report_model.report_from_mapping(mapping)
            audit = report_audit_model.audit_report(report).to_dict()
            audit["check_count"] = audit["check_count"] - 1
            with self.assertRaises(ValidationError):
                report_audit_model.audit_from_mapping(audit)

    def test_cli_and_http_health_report_surfaces_are_replayable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry_directory = self.package_directory(root, "report-cli-package")
            registry_output = root / "registry.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["registry-federation-consensus-gate-certificate-observatory-archive-registry", "--input", str(registry_directory), "--entry-id", "report-cli-entry", "--archive-id", "report-cli-archive", "--format", "json", "--output", str(registry_output)]), 0)
            report_output = root / "report.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["registry-federation-consensus-gate-certificate-observatory-archive-registry-report", "--input", str(registry_output), "--format", "json", "--output", str(report_output)]), 2)
                self.assertEqual(main(["registry-federation-consensus-gate-certificate-observatory-archive-registry-report-audit", "--input", str(report_output), "--format", "json"]), 0)
                self.assertEqual(main(["registry-federation-consensus-gate-certificate-observatory-archive-registry-report-schema"]), 0)
            server = create_server("127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}/v1/registry/federation/consensus/gate/certificate/observatory/archive/registry"
                request = urlencode({"input": str(registry_output), "format": "json"})
                with urlopen(base + "/report?" + request, timeout=15) as response:
                    payload = json.loads(response.read())
                    self.assertEqual(payload["entry_count"], 1)
                    report_path = root / "http-report.json"
                    report_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
                with urlopen(base + "/report/audit?" + urlencode({"input": str(report_path), "format": "json"}), timeout=15) as response:
                    self.assertTrue(json.loads(response.read())["accepted"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_archive_registry_capabilities_advertise_the_complete_plane(self):
        features = " ".join(registry_model.capabilities()["features"])
        for phrase in ("content-addressed", "package-group index", "conserved metrics", "atomic five-file persistence", "canonical reload"):
            self.assertIn(phrase, features)
        self.assertEqual(registry_model.capabilities()["limits"]["max_entries"], registry_model.MAX_ENTRIES)
        self.assertEqual(query_model.capabilities()["resources"], query_model.RESOURCES)
        self.assertEqual(diff_model.capabilities()["change_types"], diff_model.CHANGE_TYPES)
        self.assertEqual(history_model.capabilities()["limits"]["max_snapshots"], history_model.MAX_ENTRIES)
        self.assertEqual(report_model.capabilities()["statuses"], report_model.STATUSES)
        self.assertEqual(report_audit_model.capabilities()["check_ids"], report_audit_model.CHECK_IDS)


if __name__ == "__main__":
    unittest.main()
