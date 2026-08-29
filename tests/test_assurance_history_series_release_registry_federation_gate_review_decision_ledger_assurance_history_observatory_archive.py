"""Deep contracts for deterministic observatory archive transport."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from examples import release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_demo as archive_demo
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive as archive
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_bytes, canonical_json
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory import ObservatoryFixture


class ArchiveFixture(ObservatoryFixture):
    """Build current observatory directories for archive tests."""

    COMMAND = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-packet-registry-federation-assurance-gate-review-decision-ledger-assurance-history-observatory"
    ARCHIVE_COMMAND = COMMAND + "-archive"

    @staticmethod
    def write_archive(value: archive.ObservatoryArchive, root: Path, name: str = "observatory.zip") -> Path:
        target = root / name
        archive.write_archive(value, target)
        return target

    def observatory_directory(self, root: Path, name: str = "observatory") -> Path:
        value = self.make_observatory()
        target = root / name
        self.write_observatory(value, root, name)
        return target

    def archive_value(self, root: Path) -> archive.ObservatoryArchive:
        return archive.build_archive_from_directory(self.observatory_directory(root))

    @staticmethod
    def rewrite_zip(source: Path, destination: Path, transform, *, comment: bytes | None = None) -> None:
        with zipfile.ZipFile(source, "r") as reader:
            entries = [(info, reader.read(info)) for info in reader.infolist()]
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as writer:
            for info, raw in transform(entries):
                writer.writestr(info, raw)
            if comment is not None:
                writer.comment = comment

    @staticmethod
    def capture_cli(argv):
        from glio_noncode.cli import main

        output = StringIO()
        with redirect_stdout(output):
            status = main(argv)
        return status, output.getvalue()


class ArchiveModelTests(ArchiveFixture):
    def test_build_from_directory_preserves_observatory_linkage(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.archive_value(Path(temporary))
            self.assertEqual(value.observatory_id, "observatory:test")
            self.assertTrue(value.observatory_address.startswith("module-workbench-"))
            self.assertTrue(value.verification_address.startswith("module-workbench-"))
            self.assertEqual(value.artifact_count, 5)
            self.assertEqual(value.files, archive.ARCHIVE_PAYLOAD_FILES)

    def test_build_in_memory_and_from_directory_are_equal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            observatory_value = self.make_observatory()
            direct = archive.build_archive(observatory_value)
            directory = archive.build_archive_from_directory(self.write_observatory(observatory_value, root), archive_id=direct.archive_id)
            self.assertEqual(direct.to_dict(), directory.to_dict())
            self.assertEqual(archive.archive_bytes(direct), archive.archive_bytes(directory))

    def test_custom_archive_identity_changes_only_archive_projection(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.archive_value(Path(temporary))
            changed = archive.build_archive_from_directory(self.observatory_directory(Path(temporary), "second"), archive_id="archive:custom")
            self.assertEqual(value.observatory_address, changed.observatory_address)
            self.assertEqual(value.verification_address, changed.verification_address)
            self.assertNotEqual(value.content_address, changed.content_address)

    def test_archive_address_is_reproducible(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.archive_value(Path(temporary))
            self.assertEqual(archive.address_archive(value), value.content_address)
            self.assertTrue(value.content_address.startswith(archive.ARCHIVE_PREFIX + ":"))

    def test_archive_constructor_requires_typed_observatory_builder(self):
        with self.assertRaises(ValidationError):
            archive.build_archive({"observatory_id": "plain"})

    def test_archive_mapping_round_trip_is_path_free(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.archive_value(Path(temporary))
            mapped = archive.archive_from_mapping(value.to_dict())
            self.assertEqual(mapped.to_dict(), value.to_dict())
            self.assert_public(mapped)

    def test_archive_mapping_rejects_unknown_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.archive_value(Path(temporary)).to_dict()
            value["private"] = "forbidden"
            with self.assertRaises(ValidationError):
                archive.archive_from_mapping(value)

    def test_archive_mapping_without_payload_cannot_be_written(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = archive.archive_from_mapping(self.archive_value(Path(temporary)).to_dict())
            with self.assertRaises(ValidationError):
                archive.archive_bytes(value)

    def test_public_archive_has_no_local_path_or_attribution_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.archive_value(Path(temporary))
            self.assert_public(value)
            self.assertNotIn(str(Path(temporary)), canonical_json(value.to_dict()))

    def test_archive_version_and_boundary_are_explicit(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.archive_value(Path(temporary))
            self.assertTrue(value.version.endswith("-archive-v1"))
            self.assertEqual(value.boundary, "public_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive")

    def test_archive_artifact_receipts_are_ordered_and_addressed(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.archive_value(Path(temporary))
            self.assertEqual(tuple(item["name"] for item in value.artifacts), archive.ARCHIVE_PAYLOAD_FILES)
            self.assertTrue(all(item["hash"].startswith(archive.ARCHIVE_PREFIX + "-artifact:") for item in value.artifacts))
            self.assertTrue(all(item["size"] > 0 for item in value.artifacts))

    def test_archive_payload_bytes_match_receipts(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.archive_value(Path(temporary))
            for item in value.artifacts:
                self.assertEqual(item["size"], len(value.payload_bytes()[item["name"]]))
            archive.verify_archive(value)


class ArchiveZipTests(ArchiveFixture):
    def test_archive_has_exact_six_zip_members(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.archive_value(root)
            target = self.write_archive(value, root)
            with zipfile.ZipFile(target) as reader:
                self.assertEqual(tuple(info.filename for info in reader.infolist()), archive.FILES)

    def test_archive_bytes_are_deterministic(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.archive_value(Path(temporary))
            first = archive.archive_bytes(value)
            second = archive.archive_bytes(value)
            self.assertEqual(first, second)
            self.assertGreater(len(first), 0)

    def test_zip_metadata_is_fixed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = self.write_archive(self.archive_value(root), root)
            with zipfile.ZipFile(target) as reader:
                for info in reader.infolist():
                    self.assertEqual(info.date_time, archive.ZIP_EPOCH)
                    self.assertEqual(info.compress_type, zipfile.ZIP_DEFLATED)
                    self.assertFalse(info.flag_bits & 0x1)
                    self.assertEqual(info.comment, b"")

    def test_load_archive_round_trip_rehydrates_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.archive_value(root)
            target = self.write_archive(value, root)
            loaded = archive.load_archive(target)
            self.assertEqual(loaded.to_dict(), value.to_dict())
            self.assertEqual(archive.load_archive_package(target).observatory.content_address, value.observatory_address)

    def test_load_archive_bytes_matches_file_loading(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.archive_value(root)
            target = self.write_archive(value, root)
            raw = target.read_bytes()
            self.assertEqual(archive.load_archive_bytes(raw).to_dict(), value.to_dict())
            self.assertEqual(archive.verify_archive_bytes(raw).content_address, value.content_address)
            self.assertEqual(archive.query_archive_bytes(raw, resource="files").total_count, 5)

    def test_byte_loader_rejects_non_bytes_without_coercion(self):
        with self.assertRaises(ValidationError):
            archive.load_archive_bytes(bytearray(b"not-a-zip"))
        with self.assertRaises(ValidationError):
            archive.verify_archive_bytes("not-a-zip")

    def test_manifest_document_is_canonical_and_path_free(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.archive_value(Path(temporary))
            document = archive.manifest_document(value)
            self.assertEqual(json.loads(archive.manifest_json(value)), json.loads(canonical_json(document)))
            self.assertEqual(canonical_bytes(document), archive.manifest_json(value).encode())
            self.assertEqual(document["archive_address"], value.content_address)
            self.assertTrue(document["manifest_address"].startswith(archive.MANIFEST_PREFIX + ":"))
            self.assert_public(document)

    def test_manifest_schema_is_closed_and_declares_linkage(self):
        schema = archive.manifest_schema()
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["artifact_count"]["maximum"], archive.MAX_FILES)
        self.assertIn("manifest_address", schema["required"])

    def test_verify_archive_file_returns_loaded_value(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.archive_value(root)
            target = self.write_archive(value, root)
            self.assertEqual(archive.verify_archive_file(target).to_dict(), value.to_dict())

    def test_archive_json_is_canonical(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.archive_value(Path(temporary))
            rendered = archive.archive_json(value)
            self.assertEqual(rendered, canonical_json(value.to_dict()))
            self.assertNotIn(" ", rendered)

    def test_archive_manifest_is_canonical_and_linked(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = self.write_archive(self.archive_value(root), root)
            with zipfile.ZipFile(target) as reader:
                manifest_raw = reader.read(archive.ARCHIVE_MANIFEST_NAME)
                manifest = json.loads(manifest_raw)
            self.assertEqual(canonical_bytes(manifest), manifest_raw)
            self.assertEqual(manifest["archive_address"], archive.load_archive(target).content_address)
            self.assertEqual(manifest["files"], list(archive.ARCHIVE_PAYLOAD_FILES))

    def test_archive_comment_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.write_archive(self.archive_value(root), root)
            target = root / "comment.zip"
            self.rewrite_zip(source, target, lambda entries: entries, comment=b"unexpected")
            with self.assertRaises(ValidationError):
                archive.load_archive(target)

    def test_archive_extra_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.write_archive(self.archive_value(root), root)
            target = root / "extra.zip"

            def add_extra(entries):
                return entries + [(zipfile.ZipInfo("extra.json"), b"{}")]

            self.rewrite_zip(source, target, add_extra)
            with self.assertRaises(ValidationError):
                archive.load_archive(target)

    def test_archive_duplicate_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.write_archive(self.archive_value(root), root)
            target = root / "duplicate.zip"

            def duplicate(entries):
                return entries + [entries[0]]

            self.rewrite_zip(source, target, duplicate)
            with self.assertRaises(ValidationError):
                archive.load_archive(target)

    def test_archive_noncanonical_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.write_archive(self.archive_value(root), root)
            target = root / "noncanonical.zip"

            def reformat(entries):
                return [(info, json.dumps(json.loads(raw), indent=2).encode() if info.filename == archive.ARCHIVE_MANIFEST_NAME else raw) for info, raw in entries]

            self.rewrite_zip(source, target, reformat)
            with self.assertRaises(ValidationError):
                archive.load_archive(target)

    def test_archive_payload_hash_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.write_archive(self.archive_value(root), root)
            target = root / "payload-tamper.zip"

            def tamper(entries):
                return [(info, raw + b" ") if info.filename == archive.PAYLOAD_PREFIX + "observatory.json" else (info, raw) for info, raw in entries]

            self.rewrite_zip(source, target, tamper)
            with self.assertRaises(ValidationError):
                archive.load_archive(target)

    def test_archive_manifest_identity_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.write_archive(self.archive_value(root), root)
            target = root / "manifest-tamper.zip"

            def tamper(entries):
                changed = []
                for info, raw in entries:
                    if info.filename == archive.ARCHIVE_MANIFEST_NAME:
                        document = json.loads(raw)
                        document["archive_id"] = "archive:tampered"
                        raw = canonical_bytes(document)
                    changed.append((info, raw))
                return changed

            self.rewrite_zip(source, target, tamper)
            with self.assertRaises(ValidationError):
                archive.load_archive(target)

    def test_archive_symlink_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.write_archive(self.archive_value(root), root)
            target = root / "symlink.zip"

            def symlink(entries):
                changed = []
                for info, raw in entries:
                    if info.filename == archive.PAYLOAD_PREFIX + "metrics.json":
                        info = zipfile.ZipInfo(info.filename, archive.ZIP_EPOCH)
                        info.create_system = 3
                        info.external_attr = 0o120777 << 16
                    changed.append((info, raw))
                return changed

            self.rewrite_zip(source, target, symlink)
            with self.assertRaises(ValidationError):
                archive.load_archive(target)

    def test_archive_traversal_name_is_rejected_by_exact_shape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.write_archive(self.archive_value(root), root)
            target = root / "traversal.zip"

            def traversal(entries):
                return [(zipfile.ZipInfo("../observatory.json", archive.ZIP_EPOCH), raw) if info.filename == archive.PAYLOAD_PREFIX + "observatory.json" else (info, raw) for info, raw in entries]

            self.rewrite_zip(source, target, traversal)
            with self.assertRaises(ValidationError):
                archive.load_archive(target)

    def test_missing_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValidationError):
                archive.load_archive(Path(temporary) / "missing.zip")


class ArchiveExtractionTests(ArchiveFixture):
    def test_extract_archive_rehydrates_exact_observatory_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.write_archive(self.archive_value(root), root)
            target = root / "extracted"
            returned = archive.extract_archive(source, target)
            self.assertEqual(returned, target)
            self.assertEqual({item.name for item in target.iterdir()}, set(archive.observatory_model.FILES))
            loaded = archive.observatory_model.load_package(target)
            self.assertEqual(loaded.observatory.content_address, archive.load_archive(source).observatory_address)

    def test_extract_requires_explicit_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.write_archive(self.archive_value(root), root)
            target = root / "extracted"
            archive.extract_archive(source, target)
            with self.assertRaises(ValidationError):
                archive.extract_archive(source, target)

    def test_extract_overwrites_exact_compatible_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.write_archive(self.archive_value(root), root)
            target = root / "extracted"
            archive.extract_archive(source, target)
            (target / "metrics.json").write_bytes((target / "metrics.json").read_bytes())
            archive.extract_archive(source, target, overwrite=True)
            self.assertEqual(archive.observatory_model.load_package(target).observatory.observatory_id, "observatory:test")

    def test_extract_rejects_extra_destination_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.write_archive(self.archive_value(root), root)
            target = root / "extracted"
            archive.extract_archive(source, target)
            (target / "extra.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                archive.extract_archive(source, target, overwrite=True)

    def test_write_archive_requires_explicit_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.archive_value(root)
            target = root / "archive.zip"
            archive.write_archive(value, target)
            with self.assertRaises(ValidationError):
                archive.write_archive(value, target)
            archive.write_archive(value, target, overwrite=True)
            self.assertEqual(archive.load_archive(target).content_address, value.content_address)

    def test_write_archive_rejects_directory_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "directory").mkdir()
            with self.assertRaises(ValidationError):
                archive.write_archive(self.archive_value(root), root / "directory", overwrite=True)


class ArchiveQueryTests(ArchiveFixture):
    def loaded(self, root: Path) -> archive.ObservatoryArchive:
        value = self.archive_value(root)
        target = self.write_archive(value, root)
        return archive.load_archive(target)

    def test_all_archive_resources_are_bounded(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.loaded(Path(temporary))
            expected = {"summary": 1, "files": 5, "members": 2, "checks": 8, "failed": 0, "required": 8, "optional": 0}
            for resource, count in expected.items():
                result = archive.query_archive(value, resource=resource, limit=2)
                self.assertEqual(result.total_count, count)
                self.assertLessEqual(result.returned_count, 2)

    def test_archive_summary_query_returns_archive_projection(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.loaded(Path(temporary))
            result = archive.query_archive(value, resource="summary")
            self.assertEqual(result.records[0], value.summary())
            self.assertEqual(result.total_count, 1)

    def test_archive_file_query_returns_receipts(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = archive.query_archive(self.loaded(Path(temporary)), resource="files", text="metrics")
            self.assertEqual(result.total_count, 1)
            self.assertEqual(result.records[0]["name"], archive.PAYLOAD_PREFIX + "metrics.json")

    def test_archive_member_query_returns_member_summaries(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = archive.query_archive(self.loaded(Path(temporary)), resource="members")
            self.assertEqual(tuple(item["member_id"] for item in result.records), ("source:0", "source:1"))

    def test_archive_check_query_supports_severity_and_pass_filters(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = archive.query_archive(self.loaded(Path(temporary)), resource="checks", severity="required", passed=True, limit=3)
            self.assertEqual(result.total_count, 8)
            self.assertEqual(result.returned_count, 3)
            self.assertTrue(all(item["severity"] == "required" and item["passed"] for item in result.records))

    def test_archive_query_filters_failed_and_optional_checks(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.loaded(Path(temporary))
            self.assertEqual(archive.query_archive(value, resource="failed").total_count, 0)
            self.assertEqual(archive.query_archive(value, resource="optional").total_count, 0)
            self.assertEqual(archive.query_archive(value, resource="required").total_count, 8)

    def test_archive_query_text_is_case_insensitive(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.loaded(Path(temporary))
            upper = archive.query_archive(value, resource="checks", text="PUBLIC")
            lower = archive.query_archive(value, resource="checks", text="public")
            self.assertEqual(upper.records, lower.records)
            self.assertEqual(upper.total_count, lower.total_count)

    def test_archive_query_pagination_is_deterministic(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.loaded(Path(temporary))
            first = archive.query_archive(value, resource="checks", offset=0, limit=2)
            second = archive.query_archive(value, resource="checks", offset=2, limit=2)
            self.assertEqual(first.total_count, 8)
            self.assertEqual(second.total_count, 8)
            self.assertNotEqual(first.records, second.records)
            self.assertEqual(archive.address_archive_query(first), first.content_address)

    def test_archive_query_empty_window_is_addressed(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = archive.query_archive(self.loaded(Path(temporary)), resource="checks", offset=8, limit=1)
            self.assertEqual(result.records, ())
            self.assertTrue(result.content_address.startswith(archive.ARCHIVE_QUERY_PREFIX + ":"))

    def test_archive_query_requires_typed_query(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValidationError):
                archive.query_archive(self.loaded(Path(temporary)), query={"resource": "files"})

    def test_archive_query_rejects_invalid_window_and_resource(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.loaded(Path(temporary))
            for kwargs in ({"resource": "unknown"}, {"resource": "files", "limit": 0}, {"resource": "files", "offset": -1}):
                with self.assertRaises(ValidationError):
                    archive.query_archive(value, **kwargs)

    def test_archive_query_result_is_path_free(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = archive.query_archive(self.loaded(Path(temporary)), resource="checks", limit=2)
            self.assert_public(result)

    def test_archive_query_renderers_share_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = archive.query_archive(self.loaded(Path(temporary)), resource="checks", limit=2)
            self.assertEqual(json.loads(archive.query_json(result)), json.loads(canonical_json(result.to_dict())))
            self.assertIn("check_id", archive.query_csv(result))
            self.assertIn("Assurance history observatory archive query", archive.render_query_markdown(result))

    def test_archive_renderers_reject_plain_values(self):
        with self.assertRaises(ValidationError):
            archive.query_json({"records": ()})
        with self.assertRaises(ValidationError):
            archive.query_csv({"records": ()})
        with self.assertRaises(ValidationError):
            archive.render_query_markdown({"records": ()})


class ArchiveSchemaTests(ArchiveFixture):
    def test_schemas_are_closed(self):
        for schema_builder in (archive.artifact_schema, archive.archive_schema, archive.manifest_schema, archive.query_schema, archive.query_result_schema):
            self.assertFalse(schema_builder()["additionalProperties"])

    def test_archive_schema_declares_exact_payload_count(self):
        schema = archive.archive_schema()
        self.assertEqual(schema["properties"]["artifact_count"]["maximum"], archive.MAX_FILES)
        self.assertEqual(schema["properties"]["files"]["minItems"], archive.MAX_FILES)
        self.assertEqual(schema["properties"]["artifacts"]["maxItems"], archive.MAX_FILES)

    def test_query_schema_declares_all_resources(self):
        schema = archive.query_schema()
        self.assertEqual(tuple(schema["properties"]["resource"]["enum"]), archive.ArchiveQuery.RESOURCES)
        self.assertEqual(schema["properties"]["limit"]["minimum"], 1)

    def test_capabilities_are_path_free_and_complete(self):
        capabilities = archive.capabilities()
        self.assertEqual(tuple(capabilities["archive_files"]), archive.FILES)
        self.assertEqual(tuple(capabilities["resources"]), archive.ArchiveQuery.RESOURCES)
        self.assertIn("secure regular-file rehydration", capabilities["features"])
        self.assertNotIn("C:\\", canonical_json(capabilities))


class ArchiveOperatorTests(ArchiveFixture):
    def test_cli_archive_build_verify_query_extract_and_schemas(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            observatory_directory = self.observatory_directory(root)
            archive_path = root / "archive.zip"
            status, output = self.capture_cli([self.ARCHIVE_COMMAND, "--input", str(observatory_directory), "--destination", str(archive_path), "--format", "summary"])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output)["artifact_count"], 5)
            status, output = self.capture_cli([self.ARCHIVE_COMMAND + "-verify", "--input", str(archive_path)])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output)["observatory_id"], "observatory:test")
            status, output = self.capture_cli([self.ARCHIVE_COMMAND + "-query", "--input", str(archive_path), "--resource", "checks", "--severity", "required", "--passed"])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output)["total_count"], 8)
            extracted = root / "extracted"
            status, output = self.capture_cli([self.ARCHIVE_COMMAND + "-extract", "--input", str(archive_path), "--destination", str(extracted)])
            self.assertEqual(status, 0)
            self.assertTrue(json.loads(output)["extracted"])
            status, output = self.capture_cli([self.ARCHIVE_COMMAND + "-manifest", "--input", str(archive_path)])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output)["archive_address"], archive.load_archive(archive_path).content_address)
            for suffix in ("schema", "artifact-schema", "manifest-schema", "query-schema", "query-result-schema", "capabilities"):
                status, output = self.capture_cli([self.ARCHIVE_COMMAND + "-" + suffix])
                self.assertEqual(status, 0)
                self.assertIsInstance(json.loads(output), dict)

    def test_cli_archive_formats_are_available(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.observatory_directory(root)
            destination = root / "archive.zip"
            self.capture_cli([self.ARCHIVE_COMMAND, "--input", str(source), "--destination", str(destination)])
            for output_format, marker in (("json", "archive_id"), ("csv", "archive_id"), ("markdown", "Assurance history observatory archive")):
                status, output = self.capture_cli([self.ARCHIVE_COMMAND + "-query", "--input", str(destination), "--resource", "summary", "--format", output_format])
                self.assertEqual(status, 0)
                self.assertIn(marker, output)

    def test_http_archive_routes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.observatory_directory(root)
            archive_path = root / "archive.zip"
            archive.write_archive(archive.build_archive_from_directory(source), archive_path)
            server, thread = self.server()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                prefix = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive"
                for suffix in ("/schema", "/artifact-schema", "/manifest-schema", "/query-schema", "/query-result-schema", "/capabilities"):
                    with urlopen(base + prefix + suffix) as response:
                        self.assertEqual(response.status, 200)
                        self.assertIsInstance(json.loads(response.read()), dict)
                with urlopen(base + prefix + "/manifest?input=" + str(archive_path)) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read())["artifact_count"], 5)
                with urlopen(base + prefix + "/verify?input=" + str(archive_path)) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read())["artifact_count"], 5)
                query = urlencode({"input": str(archive_path), "resource": "checks", "severity": "required", "passed": "true"})
                with urlopen(base + prefix + "/query?" + query) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read())["total_count"], 8)
                extracted = root / "http-extracted"
                query = urlencode({"input": str(archive_path), "destination": str(extracted)})
                with urlopen(base + prefix + "/extract?" + query) as response:
                    self.assertEqual(response.status, 200)
                    self.assertTrue(json.loads(response.read())["extracted"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_archive_demo_runs_on_persisted_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.observatory_directory(root)
            archive_path = root / "archive.zip"
            archive.write_archive(archive.build_archive_from_directory(source), archive_path)
            output = StringIO()
            with redirect_stdout(output):
                status = archive_demo.main(["--input", str(archive_path), "--resource", "checks", "--severity", "required", "--passed", "--format", "summary"])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output.getvalue())["total_count"], 8)

    def test_archive_demo_rejects_missing_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = StringIO()
            with redirect_stdout(output):
                status = archive_demo.main(["--input", str(Path(temporary) / "missing.zip")])
            self.assertEqual(status, 1)
            self.assertIn("error", json.loads(output.getvalue()))


if __name__ == "__main__":
    unittest.main()
