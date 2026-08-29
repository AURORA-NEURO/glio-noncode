"""Deep contract tests for resumable observatory archive transfer."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from examples import release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_transfer_demo as transfer_demo
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive as archive
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_transfer as transfer
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_bytes, canonical_json
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive import ArchiveFixture


class TransferFixture(ArchiveFixture):
    """Build verified archive inputs without copying any external repository."""

    TRANSFER_COMMAND = ArchiveFixture.ARCHIVE_COMMAND + "-transfer"

    def archive_file(self, root: Path) -> Path:
        value = self.archive_value(root)
        target = root / "observatory.zip"
        archive.write_archive(value, target)
        return target

    def transfer_value(self, root: Path, chunk_size: int = 256) -> transfer.ArchiveTransfer:
        return transfer.build_transfer_from_bytes(self.archive_file(root).read_bytes(), transfer_id="transfer:test", chunk_size=chunk_size)


class TransferModelTests(TransferFixture):
    def test_transfer_is_anchored_to_verified_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            self.assertTrue(value.archive_address.startswith(archive.ARCHIVE_PREFIX + ":"))
            self.assertEqual(value.archive_address, archive.load_archive(Path(temporary) / "observatory.zip").content_address)
            self.assertEqual(value.archive_size, len(archive.archive_bytes(archive.load_archive(Path(temporary) / "observatory.zip"))))

    def test_transfer_chunks_conserve_bytes_in_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            self.assertEqual(value.chunk_count, 21)
            self.assertEqual(sum(chunk.size for chunk in value.chunks), value.archive_size)
            self.assertEqual(tuple(chunk.index for chunk in value.chunks), tuple(range(value.chunk_count)))
            self.assertEqual(tuple(chunk.offset for chunk in value.chunks[:3]), (0, 256, 512))
            self.assertEqual(value.chunks[-1].size, value.archive_size - 20 * 256)

    def test_chunk_receipts_are_addressed_and_fixed(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            payload = value.payload_bytes()
            for chunk in value.chunks:
                self.assertEqual(chunk.content_address, transfer.address_chunk(payload[chunk.index]))
                self.assertEqual(chunk.size, len(payload[chunk.index]))
                self.assertEqual(transfer.chunk_name(chunk.index), f"chunks/chunk-{chunk.index:08d}.bin")

    def test_transfer_identity_is_reproducible(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.transfer_value(root)
            second = transfer.build_transfer_from_bytes((root / "observatory.zip").read_bytes(), transfer_id="transfer:test", chunk_size=256)
            self.assertEqual(first.to_dict(), second.to_dict())
            self.assertEqual(transfer.address_transfer(first), first.content_address)
            self.assertEqual(transfer.manifest_json(first), transfer.manifest_json(second))

    def test_transfer_identity_changes_when_chunking_policy_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.transfer_value(root, 256)
            second = transfer.build_transfer_from_bytes((root / "observatory.zip").read_bytes(), transfer_id="transfer:test", chunk_size=512)
            self.assertEqual(first.archive_address, second.archive_address)
            self.assertNotEqual(first.content_address, second.content_address)
            self.assertNotEqual(first.chunk_count, second.chunk_count)

    def test_transfer_identity_changes_when_transfer_id_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.transfer_value(root)
            second = transfer.build_transfer_from_bytes((root / "observatory.zip").read_bytes(), transfer_id="transfer:other", chunk_size=256)
            self.assertNotEqual(first.content_address, second.content_address)
            self.assertEqual(first.archive_address, second.archive_address)

    def test_build_from_typed_archive_matches_build_from_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_value = archive.load_archive(self.archive_file(root))
            typed = transfer.build_transfer(archive_value, transfer_id="transfer:test", chunk_size=256)
            raw = transfer.build_transfer_from_bytes((root / "observatory.zip").read_bytes(), transfer_id="transfer:test", chunk_size=256)
            self.assertEqual(typed.to_dict(), raw.to_dict())

    def test_transfer_mapping_round_trip_is_public(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            mapped = transfer.transfer_from_mapping(value.to_dict())
            self.assertEqual(mapped.to_dict(), value.to_dict())
            self.assertNotIn("C:\\", canonical_json(mapped.to_dict()))
            self.assertEqual(transfer.query_transfer(mapped, resource="missing").total_count, value.chunk_count)

    def test_transfer_mapping_rejects_unknown_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            document = self.transfer_value(Path(temporary)).to_dict()
            document["source_path"] = "C:\\private"
            with self.assertRaises(ValidationError):
                transfer.transfer_from_mapping(document)

    def test_transfer_constructor_rejects_non_typed_archive(self):
        with self.assertRaises(ValidationError):
            transfer.build_transfer({"archive_address": "archive:test"})

    def test_address_chunk_requires_non_empty_bytes(self):
        for value in (b"", "text", bytearray(b"bytes")):
            with self.assertRaises(ValidationError):
                transfer.address_chunk(value)

    def test_chunk_size_bounds_are_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            raw = self.archive_file(Path(temporary)).read_bytes()
            for size in (0, transfer.MIN_CHUNK_SIZE - 1, transfer.MAX_CHUNK_SIZE + 1, "256", True):
                with self.assertRaises(ValidationError):
                    transfer.build_transfer_from_bytes(raw, chunk_size=size)

    def test_chunk_bytes_returns_exact_payload(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            self.assertEqual(transfer.chunk_bytes(value, 0), value.payload_bytes()[0])
            with self.assertRaises(ValidationError):
                transfer.chunk_bytes(value, value.chunk_count)

    def test_assemble_archive_bytes_reconstructs_verified_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.transfer_value(root)
            raw = transfer.assemble_archive_bytes(value)
            self.assertEqual(raw, (root / "observatory.zip").read_bytes())
            self.assertEqual(archive.load_archive_bytes(raw).content_address, value.archive_address)

    def test_assemble_accepts_explicit_parts(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            parts = value.payload_bytes()
            self.assertEqual(transfer.assemble_archive_bytes(value, parts), archive.archive_bytes(archive.load_archive(Path(temporary) / "observatory.zip")))

    def test_assemble_rejects_missing_chunk(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            parts = dict(value.payload_bytes())
            del parts[0]
            with self.assertRaises(ValidationError):
                transfer.assemble_archive_bytes(value, parts)

    def test_assemble_rejects_changed_chunk(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            parts = dict(value.payload_bytes())
            parts[0] = bytes([parts[0][0] ^ 1]) + parts[0][1:]
            with self.assertRaises(ValidationError):
                transfer.assemble_archive_bytes(value, parts)

    def test_verify_without_payload_only_verifies_public_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            manifest_only = transfer.transfer_from_mapping(value.to_dict())
            self.assertIs(transfer.verify_transfer(manifest_only), manifest_only)

    def test_verify_with_payload_replays_nested_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            self.assertIs(transfer.verify_transfer(value), value)

    def test_transfer_version_and_boundary_are_explicit(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            self.assertTrue(value.version.endswith("-transfer-v1"))
            self.assertTrue(value.boundary.endswith("_transfer"))

    def test_transfer_public_projection_excludes_payload_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            public = canonical_json(value.to_dict())
            self.assertNotIn("PK", public)
            self.assertNotIn("agent", public.lower())
            self.assertNotIn("language", public.lower())

    def test_assembler_starts_with_all_chunks_missing(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            assembler = transfer.TransferAssembler(transfer.transfer_from_mapping(value.to_dict()))
            progress = assembler.progress()
            self.assertEqual(progress.received_indices, ())
            self.assertEqual(progress.missing_indices, tuple(range(value.chunk_count)))
            self.assertFalse(progress.complete)
            self.assertEqual(progress.received_bytes, 0)

    def test_assembler_accepts_chunks_in_any_arrival_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            assembler = transfer.TransferAssembler(value)
            payload = value.payload_bytes()
            assembler.add_chunk(2, payload[2])
            progress = assembler.add_chunk(0, payload[0])
            self.assertEqual(progress.received_indices, (0, 2))
            self.assertEqual(progress.missing_indices, tuple(index for index in range(value.chunk_count) if index not in (0, 2)))

    def test_assembler_duplicate_identical_chunk_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            assembler = transfer.TransferAssembler(value)
            raw = value.payload_bytes()[0]
            first = assembler.add_chunk(0, raw)
            second = assembler.add_chunk(0, raw)
            self.assertEqual(first.to_dict(), second.to_dict())

    def test_assembler_conflicting_duplicate_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            assembler = transfer.TransferAssembler(value)
            raw = value.payload_bytes()[0]
            assembler.add_chunk(0, raw)
            conflicting = bytes([raw[0] ^ 1]) + raw[1:]
            with self.assertRaises(ValidationError):
                assembler.add_chunk(0, conflicting)

    def test_assembler_rejects_wrong_index_and_wrong_type(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            assembler = transfer.TransferAssembler(value)
            raw = value.payload_bytes()[0]
            with self.assertRaises(ValidationError):
                assembler.add_chunk(value.chunk_count, raw)
            with self.assertRaises(ValidationError):
                assembler.add_chunk(0, bytearray(raw))

    def test_assembler_rejects_wrong_chunk_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            assembler = transfer.TransferAssembler(value)
            raw = value.payload_bytes()[0]
            with self.assertRaises(ValidationError):
                assembler.add_chunk(0, raw[:-1])

    def test_assembler_progress_is_addressed(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            assembler = transfer.TransferAssembler(value)
            progress = assembler.add_chunk(0, value.payload_bytes()[0])
            self.assertTrue(progress.content_address.startswith(transfer.TRANSFER_PROGRESS_PREFIX + ":"))
            self.assertEqual(transfer.address_progress(progress), progress.content_address)

    def test_assembler_add_chunks_returns_conserved_progress(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            assembler = transfer.TransferAssembler(value)
            progress = assembler.add_chunks({0: value.payload_bytes()[0], 1: value.payload_bytes()[1]})
            self.assertEqual(progress.received_indices, (0, 1))
            self.assertEqual(progress.received_bytes, value.chunks[0].size + value.chunks[1].size)

    def test_assembler_finalize_rejects_incomplete_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            assembler = transfer.TransferAssembler(value)
            assembler.add_chunk(0, value.payload_bytes()[0])
            with self.assertRaises(ValidationError):
                assembler.finalize()

    def test_assembler_finalize_reproduces_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.transfer_value(root)
            assembler = transfer.TransferAssembler(value)
            for index in reversed(range(value.chunk_count)):
                assembler.add_chunk(index, value.payload_bytes()[index])
            self.assertTrue(assembler.is_complete())
            self.assertEqual(assembler.finalize(), (root / "observatory.zip").read_bytes())

    def test_progress_schema_is_closed_and_complete(self):
        schema = transfer.progress_schema()
        self.assertFalse(schema["additionalProperties"])
        self.assertIn("received_indices", schema["required"])
        self.assertIn("complete", schema["required"])

    def test_progress_query_reports_complete_loaded_transfer(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            result = transfer.query_transfer(value, resource="progress")
            record = result.records[0]
            self.assertTrue(record["complete"])
            self.assertEqual(record["received_bytes"], value.archive_size)
            self.assertEqual(record["missing_indices"], ())

    def test_progress_query_reports_incomplete_manifest_transfer(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            manifest_only = transfer.transfer_from_mapping(value.to_dict())
            result = transfer.query_transfer(manifest_only, resource="progress")
            record = result.records[0]
            self.assertFalse(record["complete"])
            self.assertEqual(record["received_indices"], ())
            self.assertEqual(len(record["missing_indices"]), value.chunk_count)


class TransferManifestTests(TransferFixture):
    def test_manifest_is_canonical_and_linked(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            document = transfer.manifest_document(value)
            self.assertEqual(canonical_bytes(document), transfer.manifest_json(value).encode())
            self.assertEqual(document["transfer_address"], value.content_address)
            self.assertTrue(document["manifest_address"].startswith(transfer.TRANSFER_MANIFEST_PREFIX + ":"))

    def test_manifest_has_exact_chunk_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            document = transfer.manifest_document(value)
            self.assertEqual(tuple(item["index"] for item in document["chunks"]), tuple(range(value.chunk_count)))
            self.assertEqual(tuple(item["offset"] for item in document["chunks"]), tuple(chunk.offset for chunk in value.chunks))

    def test_manifest_schema_is_closed(self):
        for builder in (transfer.chunk_schema, transfer.transfer_schema, transfer.manifest_schema, transfer.query_schema, transfer.query_result_schema):
            self.assertFalse(builder()["additionalProperties"])

    def test_transfer_schema_declares_bounds(self):
        schema = transfer.transfer_schema()
        self.assertEqual(schema["properties"]["chunk_count"]["maximum"], transfer.MAX_CHUNKS)
        self.assertEqual(schema["properties"]["archive_size"]["maximum"], transfer.MAX_TRANSFER_BYTES)
        self.assertEqual(schema["properties"]["chunk_size"]["minimum"], transfer.MIN_CHUNK_SIZE)

    def test_capabilities_are_path_free_and_complete(self):
        capabilities = transfer.capabilities()
        self.assertEqual(tuple(capabilities["resources"]), transfer.TransferQuery.RESOURCES)
        self.assertIn("fail-closed chunk reassembly", capabilities["features"])
        self.assertNotIn("C:\\", canonical_json(capabilities))


class TransferDirectoryTests(TransferFixture):
    def test_partial_write_persists_only_received_chunks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.transfer_value(root)
            assembler = transfer.TransferAssembler(value)
            assembler.add_chunks({0: value.payload_bytes()[0], 2: value.payload_bytes()[2]})
            destination = root / "partial"
            transfer.write_partial_transfer(assembler, destination)
            names = {item.relative_to(destination).as_posix() for item in destination.rglob("*")}
            self.assertEqual(names, {"manifest.json", "chunks", transfer.chunk_name(0), transfer.chunk_name(2)})
            self.assertEqual(transfer.verify_partial_transfer(destination).received_indices, (0, 2))

    def test_partial_writer_method_matches_function(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.transfer_value(root)
            assembler = transfer.TransferAssembler(value)
            assembler.add_chunk(1, value.payload_bytes()[1])
            destination = root / "partial"
            self.assertEqual(assembler.write_partial(destination), destination)
            resumed = transfer.load_partial_transfer(destination)
            self.assertEqual(resumed.received_indices(), (1,))

    def test_partial_round_trip_can_resume_and_finalize(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.transfer_value(root)
            assembler = transfer.TransferAssembler(value)
            assembler.add_chunks({0: value.payload_bytes()[0], 4: value.payload_bytes()[4]})
            destination = root / "partial"
            transfer.write_partial_transfer(assembler, destination)
            resumed = transfer.load_partial_transfer(destination)
            for index in range(value.chunk_count):
                if index not in resumed.received_indices():
                    resumed.add_chunk(index, value.payload_bytes()[index])
            self.assertTrue(resumed.is_complete())
            self.assertEqual(resumed.finalize(), (root / "observatory.zip").read_bytes())

    def test_partial_empty_directory_is_a_valid_manifest_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.transfer_value(root)
            destination = root / "partial"
            transfer.write_partial_transfer(transfer.TransferAssembler(value), destination)
            resumed = transfer.load_partial_transfer(destination)
            self.assertEqual(resumed.received_indices(), ())
            self.assertEqual(resumed.missing_indices(), tuple(range(value.chunk_count)))

    def test_partial_writer_requires_explicit_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.transfer_value(root)
            assembler = transfer.TransferAssembler(value)
            destination = root / "partial"
            transfer.write_partial_transfer(assembler, destination)
            with self.assertRaises(ValidationError):
                transfer.write_partial_transfer(assembler, destination)

    def test_partial_overwrite_rejects_another_transfer(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.transfer_value(root)
            second = transfer.build_transfer_from_bytes((root / "observatory.zip").read_bytes(), transfer_id="transfer:other", chunk_size=256)
            destination = root / "partial"
            transfer.write_partial_transfer(transfer.TransferAssembler(first), destination)
            with self.assertRaises(ValidationError):
                transfer.write_partial_transfer(transfer.TransferAssembler(second), destination, overwrite=True)

    def test_partial_extra_chunk_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.transfer_value(root)
            destination = root / "partial"
            transfer.write_partial_transfer(transfer.TransferAssembler(value), destination)
            (destination / "chunks" / "chunk-99999999.bin").write_bytes(b"unexpected")
            with self.assertRaises(ValidationError):
                transfer.load_partial_transfer(destination)

    def test_partial_noncanonical_chunk_name_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.transfer_value(root)
            assembler = transfer.TransferAssembler(value)
            assembler.add_chunk(0, value.payload_bytes()[0])
            destination = root / "partial"
            transfer.write_partial_transfer(assembler, destination)
            (destination / transfer.chunk_name(0)).rename(destination / "chunks" / "chunk-0.bin")
            with self.assertRaises(ValidationError):
                transfer.load_partial_transfer(destination)

    def test_partial_chunk_tamper_is_rejected_on_resume(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.transfer_value(root)
            assembler = transfer.TransferAssembler(value)
            assembler.add_chunk(0, value.payload_bytes()[0])
            destination = root / "partial"
            transfer.write_partial_transfer(assembler, destination)
            chunk = destination / transfer.chunk_name(0)
            raw = chunk.read_bytes()
            chunk.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
            with self.assertRaises(ValidationError):
                transfer.load_partial_transfer(destination)

    def test_partial_manifest_tamper_is_rejected_before_reading_chunks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.transfer_value(root)
            destination = root / "partial"
            transfer.write_partial_transfer(transfer.TransferAssembler(value), destination)
            document = json.loads((destination / "manifest.json").read_bytes())
            document["chunk_size"] = 512
            (destination / "manifest.json").write_bytes(canonical_bytes(document))
            with self.assertRaises(ValidationError):
                transfer.load_partial_transfer(destination)

    def test_partial_progress_can_be_queried_after_resume(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.transfer_value(root)
            assembler = transfer.TransferAssembler(value)
            assembler.add_chunk(3, value.payload_bytes()[3])
            destination = root / "partial"
            transfer.write_partial_transfer(assembler, destination)
            resumed = transfer.load_partial_transfer(destination)
            progress = resumed.progress()
            self.assertFalse(progress.complete)
            self.assertEqual(progress.received_indices, (3,))

    def test_write_creates_exact_manifest_and_chunk_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.transfer_value(root)
            destination = root / "transfer"
            self.assertEqual(transfer.write_transfer(value, destination), destination)
            names = {item.relative_to(destination).as_posix() for item in destination.rglob("*")}
            self.assertEqual(names, {"manifest.json", "chunks", *(transfer.chunk_name(index) for index in range(value.chunk_count))})

    def test_load_directory_round_trips_and_reassembles(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.transfer_value(root)
            destination = root / "transfer"
            transfer.write_transfer(value, destination)
            loaded = transfer.load_transfer(destination)
            self.assertEqual(loaded.to_dict(), value.to_dict())
            self.assertEqual(transfer.assemble_archive_bytes(loaded), (root / "observatory.zip").read_bytes())

    def test_verify_directory_returns_loaded_value(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.transfer_value(root)
            destination = root / "transfer"
            transfer.write_transfer(value, destination)
            self.assertEqual(transfer.verify_transfer_directory(destination).content_address, value.content_address)

    def test_directory_requires_explicit_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.transfer_value(root)
            destination = root / "transfer"
            transfer.write_transfer(value, destination)
            with self.assertRaises(ValidationError):
                transfer.write_transfer(value, destination)

    def test_directory_overwrite_requires_exact_shape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.transfer_value(root)
            destination = root / "transfer"
            transfer.write_transfer(value, destination)
            (destination / "extra.bin").write_bytes(b"unexpected")
            with self.assertRaises(ValidationError):
                transfer.write_transfer(value, destination, overwrite=True)

    def test_directory_overwrite_replaces_exact_shape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.transfer_value(root)
            destination = root / "transfer"
            transfer.write_transfer(value, destination)
            (destination / transfer.chunk_name(0)).write_bytes((destination / transfer.chunk_name(0)).read_bytes())
            transfer.write_transfer(value, destination, overwrite=True)
            self.assertEqual(transfer.load_transfer(destination).content_address, value.content_address)

    def test_missing_chunk_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.transfer_value(root)
            destination = root / "transfer"
            transfer.write_transfer(value, destination)
            (destination / transfer.chunk_name(0)).unlink()
            with self.assertRaises(ValidationError):
                transfer.load_transfer(destination)

    def test_extra_chunk_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.transfer_value(root)
            destination = root / "transfer"
            transfer.write_transfer(value, destination)
            (destination / "chunks" / "chunk-99999999.bin").write_bytes(b"unexpected")
            with self.assertRaises(ValidationError):
                transfer.load_transfer(destination)

    def test_chunk_hash_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.transfer_value(root)
            destination = root / "transfer"
            transfer.write_transfer(value, destination)
            chunk = destination / transfer.chunk_name(0)
            raw = chunk.read_bytes()
            chunk.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
            with self.assertRaises(ValidationError):
                transfer.load_transfer(destination)

    def test_manifest_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.transfer_value(root)
            destination = root / "transfer"
            transfer.write_transfer(value, destination)
            document = json.loads((destination / "manifest.json").read_bytes())
            document["transfer_id"] = "transfer:tampered"
            (destination / "manifest.json").write_bytes(canonical_bytes(document))
            with self.assertRaises(ValidationError):
                transfer.load_transfer(destination)

    def test_noncanonical_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.transfer_value(root)
            destination = root / "transfer"
            transfer.write_transfer(value, destination)
            document = json.loads((destination / "manifest.json").read_bytes())
            (destination / "manifest.json").write_text(json.dumps(document, indent=2), encoding="utf-8")
            with self.assertRaises(ValidationError):
                transfer.load_transfer(destination)

    def test_non_directory_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = self.archive_file(root)
            with self.assertRaises(ValidationError):
                transfer.load_transfer(archive_path)

    def test_missing_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "transfer"
            directory.mkdir()
            with self.assertRaises(ValidationError):
                transfer.load_transfer(directory)

    def test_directory_query_can_read_persisted_transfer(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            value = self.transfer_value(root)
            destination = root / "transfer"
            transfer.write_transfer(value, destination)
            result = transfer.query_transfer_directory(destination, resource="chunks", limit=2)
            self.assertEqual(result.total_count, value.chunk_count)
            self.assertEqual(result.returned_count, 2)


class TransferQueryTests(TransferFixture):
    def test_all_resources_are_bounded(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            expected = {"summary": 1, "chunks": value.chunk_count, "missing": 0, "progress": 1}
            for resource, count in expected.items():
                result = transfer.query_transfer(value, resource=resource, limit=2)
                self.assertEqual(result.total_count, count)
                self.assertLessEqual(result.returned_count, 2)

    def test_manifest_only_transfer_reports_missing_chunks(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            result = transfer.query_transfer(transfer.transfer_from_mapping(value.to_dict()), resource="missing", limit=3)
            self.assertEqual(result.total_count, value.chunk_count)
            self.assertEqual(result.returned_count, 3)

    def test_summary_query_returns_summary(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            result = transfer.query_transfer(value, resource="summary")
            self.assertEqual(result.records[0], value.summary())

    def test_chunk_query_returns_receipts(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            result = transfer.query_transfer(value, resource="chunks", limit=1)
            self.assertEqual(result.records[0], value.chunks[0].to_dict())

    def test_text_filter_is_case_insensitive(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            upper = transfer.query_transfer(value, resource="chunks", text="CONTENT_ADDRESS")
            lower = transfer.query_transfer(value, resource="chunks", text="content_address")
            self.assertEqual(upper.records, lower.records)

    def test_pagination_is_deterministic(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            first = transfer.query_transfer(value, resource="chunks", offset=0, limit=2)
            second = transfer.query_transfer(value, resource="chunks", offset=2, limit=2)
            self.assertEqual(first.total_count, second.total_count)
            self.assertNotEqual(first.records, second.records)
            self.assertEqual(transfer.address_transfer_query(first), first.content_address)

    def test_query_result_is_path_free(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = transfer.query_transfer(self.transfer_value(Path(temporary)), resource="chunks", limit=2)
            self.assertNotIn("C:\\", canonical_json(result.to_dict()))

    def test_invalid_query_resource_and_window_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            for kwargs in ({"resource": "invalid"}, {"resource": "chunks", "limit": 0}, {"resource": "chunks", "offset": -1}):
                with self.assertRaises(ValidationError):
                    transfer.query_transfer(value, **kwargs)

    def test_query_rejects_mixed_query_object_and_filters(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.transfer_value(Path(temporary))
            query = transfer.TransferQuery(resource="chunks")
            with self.assertRaises(ValidationError):
                transfer.query_transfer(value, query, text="chunk")

    def test_query_renderers_are_deterministic(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = transfer.query_transfer(self.transfer_value(Path(temporary)), resource="chunks", limit=2)
            self.assertEqual(json.loads(transfer.transfer_query_json(result)), json.loads(canonical_json(result.to_dict())))
            self.assertIn("content_address", transfer.transfer_query_csv(result))
            self.assertIn("archive transfer query", transfer.render_transfer_query_markdown(result))

    def test_renderers_reject_plain_values(self):
        with self.assertRaises(ValidationError):
            transfer.transfer_query_json({})
        with self.assertRaises(ValidationError):
            transfer.transfer_query_csv({})
        with self.assertRaises(ValidationError):
            transfer.render_transfer_query_markdown({})


class TransferOperatorTests(TransferFixture):
    def test_downloaded_archive_transfer_demo_runs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = self.archive_file(root)
            destination = root / "transfer"
            status = transfer_demo.main(["--input", str(archive_path), "--destination", str(destination), "--chunk-size", "256", "--resource", "chunks", "--limit", "2", "--format", "json"])
            self.assertEqual(status, 0)
            self.assertEqual(transfer.load_transfer(destination).chunk_count, 21)

    def test_cli_build_verify_manifest_query_and_schemas(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = self.archive_file(root)
            destination = root / "transfer"
            status, output = self.capture_cli([self.TRANSFER_COMMAND, "--input", str(archive_path), "--destination", str(destination), "--transfer-id", "transfer:cli", "--chunk-size", "256", "--format", "summary"])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output)["chunk_count"], 21)
            status, output = self.capture_cli([self.TRANSFER_COMMAND + "-verify", "--input", str(destination)])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output)["transfer_id"], "transfer:cli")
            status, output = self.capture_cli([self.TRANSFER_COMMAND + "-manifest", "--input", str(destination)])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output)["transfer_address"], transfer.load_transfer(destination).content_address)
            status, output = self.capture_cli([self.TRANSFER_COMMAND + "-query", "--input", str(destination), "--resource", "chunks", "--limit", "2"])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output)["returned_count"], 2)
            for suffix in ("schema", "chunk-schema", "manifest-schema", "progress-schema", "query-schema", "query-result-schema", "capabilities"):
                status, output = self.capture_cli([self.TRANSFER_COMMAND + "-" + suffix])
                self.assertEqual(status, 0)
                self.assertIsInstance(json.loads(output), dict)

    def test_cli_transfer_renderers_are_available(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = self.archive_file(root)
            destination = root / "transfer"
            self.capture_cli([self.TRANSFER_COMMAND, "--input", str(archive_path), "--destination", str(destination), "--chunk-size", "256"])
            for output_format, marker in (("json", "transfer_id"), ("csv", "content_address"), ("markdown", "Assurance history observatory archive transfer") ):
                status, output = self.capture_cli([self.TRANSFER_COMMAND + "-query", "--input", str(destination), "--resource", "summary", "--format", output_format])
                self.assertEqual(status, 0)
                self.assertIn(marker, output)

    def test_http_transfer_routes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = self.archive_file(root)
            destination = root / "transfer"
            server, thread = self.server()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                prefix = "/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/transfer"
                for suffix in ("/schema", "/chunk-schema", "/manifest-schema", "/progress-schema", "/query-schema", "/query-result-schema", "/capabilities"):
                    with urlopen(base + prefix + suffix) as response:
                        self.assertEqual(response.status, 200)
                        self.assertIsInstance(json.loads(response.read()), dict)
                query = urlencode({"input": str(archive_path), "destination": str(destination), "chunk_size": "256", "transfer_id": "transfer:http"})
                with urlopen(base + prefix + "?" + query) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read())["transfer_id"], "transfer:http")
                with urlopen(base + prefix + "/verify?input=" + str(destination)) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read())["chunk_count"], 21)
                with urlopen(base + prefix + "/manifest?input=" + str(destination)) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read())["chunk_count"], 21)
                query = urlencode({"input": str(destination), "resource": "chunks", "limit": "2"})
                with urlopen(base + prefix + "/query?" + query) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.loads(response.read())["returned_count"], 2)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
