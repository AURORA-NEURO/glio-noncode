"""Contract tests for the certificate-observatory archive and transfer boundary."""

# ruff: noqa: E501, I001

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import registry_federation_consensus_gate_certificate_history as history_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory as observatory_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive as archive_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_audit as archive_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_query as archive_query_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_query_audit as archive_query_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_runtime as archive_runtime_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_runtime_audit as archive_runtime_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_transfer as transfer_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_transfer_audit as transfer_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_transfer_recovery as recovery_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_transfer_recovery_audit as recovery_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_transfer_recovery_query as recovery_query_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_audit as observatory_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_package as package_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_package_audit as package_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_query_audit as observatory_query_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_report as report_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_report_audit as report_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from tests.test_registry_federation_consensus_gate_certificate import CertificateFixture


class CertificateObservatoryArchiveTests(CertificateFixture):
    """Exercise the archive graph from typed package to persisted transfer."""

    def _histories(self, root: Path):
        issued = self.certificate_runtime(root / "issued", "primary", "replica")
        withheld = self.certificate_runtime(root / "withheld", "primary", "held")
        first = history_model.build_history(((issued.certificate, issued.certificate_audit),), history_id="issued-history")
        second = history_model.build_history(((withheld.certificate, withheld.certificate_audit),), history_id="withheld-history")
        return first, second

    def _package(self, root: Path, package_id: str = "archive-package"):
        first, second = self._histories(root)
        observatory = observatory_model.build_observatory((first, second), observatory_id="archive-observatory")
        observatory_audit = observatory_audit_model.audit_observatory(observatory)
        query = observatory_model.query_observatory(observatory, resources=observatory_model.RESOURCES, limit=100)
        query_audit = observatory_query_audit_model.audit_query(query)
        report = report_model.build_report(observatory, report_id="archive-report")
        report_audit = report_audit_model.audit_report(report)
        package = package_model.build_package(observatory, query=query, report=report, observatory_audit=observatory_audit, query_audit=query_audit, report_audit=report_audit, package_id=package_id)
        self.assertTrue(package_audit_model.audit_package(package).accepted)
        return package

    def _archive(self, root: Path):
        package = self._package(root)
        archive = archive_model.build_archive(package, archive_id="archive-envelope")
        self.assertTrue(archive_audit_model.audit_archive(archive).accepted)
        return package, archive

    def _transfer(self, root: Path, chunk_size: int = 256):
        package, archive = self._archive(root)
        transfer = transfer_model.build_transfer(archive, transfer_id="archive-transfer", chunk_size=chunk_size)
        return package, archive, transfer

    def test_archive_has_exact_members_and_replays_deterministically(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package, archive = self._archive(root)
            raw = archive_model.archive_bytes(archive)
            self.assertGreater(len(raw), 0)
            self.assertEqual(len(raw), archive.archive_size)
            self.assertEqual(raw, archive_model.archive_bytes(archive))
            self.assertEqual(tuple(archive.files), archive_model.ARCHIVE_PAYLOAD_FILES)
            self.assertEqual(tuple(item.name for item in archive.artifacts), archive_model.ARCHIVE_PAYLOAD_FILES)
            self.assertEqual(archive.package_address, package.content_address)
            loaded = archive_model.load_archive_bytes(raw)
            self.assertEqual(loaded.to_dict(), archive.to_dict())
            self.assertEqual(loaded.package.content_address, package.content_address)
            self.assertEqual(archive_model.manifest_document(loaded)["archive_address"], archive.content_address)
            self.assertEqual(archive_model.archive_from_mapping(archive.to_dict()).to_dict(), archive.to_dict())
            self.assertTrue(archive_audit_model.audit_archive(loaded).accepted)

    def test_archive_zip_order_and_headers_are_stable(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, archive = self._archive(Path(temporary))
            raw = archive_model.archive_bytes(archive)
            with zipfile.ZipFile(io.BytesIO(raw), "r") as stream:
                infos = stream.infolist()
                self.assertEqual(tuple(item.filename for item in infos), archive_model.FILES)
                self.assertTrue(all(item.date_time == archive_model.ZIP_EPOCH for item in infos))
                self.assertTrue(all(item.comment == b"" for item in infos))
                self.assertTrue(all(item.compress_type == zipfile.ZIP_DEFLATED for item in infos))
                self.assertTrue(all(stream.read(item.filename) for item in infos))

    def test_archive_rejects_extra_duplicate_and_unsafe_members(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, archive = self._archive(Path(temporary))
            raw = archive_model.archive_bytes(archive)
            with zipfile.ZipFile(io.BytesIO(raw), "r") as source:
                members = [(info.filename, source.read(info.filename)) for info in source.infolist()]
            variants = []
            variants.append(members + [("unexpected.json", b"{}")])
            variants.append(members + [(members[0][0], members[0][1])])
            variants.append([("../manifest.json", members[0][1])] + members[1:])
            variants.append([("/manifest.json", members[0][1])] + members[1:])
            variants.append([("certificate-observatory\\manifest.json", members[0][1])] + members[1:])
            for variant in variants:
                stream = io.BytesIO()
                with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as target:
                    for name, body in variant:
                        target.writestr(name, body)
                with self.assertRaises(ValidationError):
                    archive_model.load_archive_bytes(stream.getvalue())

    def test_archive_rejects_manifest_and_payload_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, archive = self._archive(Path(temporary))
            raw = archive_model.archive_bytes(archive)
            with zipfile.ZipFile(io.BytesIO(raw), "r") as source:
                members = {info.filename: source.read(info.filename) for info in source.infolist()}
            manifest = json.loads(members[archive_model.ARCHIVE_MANIFEST_NAME])
            manifest["package_id"] = "different-package"
            variants = []
            mutated_manifest = dict(members)
            mutated_manifest[archive_model.ARCHIVE_MANIFEST_NAME] = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
            variants.append(mutated_manifest)
            mutated_payload = dict(members)
            payload_name = archive_model.ARCHIVE_PAYLOAD_FILES[-1]
            mutated_payload[payload_name] = mutated_payload[payload_name] + b" "
            variants.append(mutated_payload)
            for variant in variants:
                stream = io.BytesIO()
                with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as target:
                    for name in archive_model.FILES:
                        target.writestr(name, variant[name])
                with self.assertRaises(ValidationError):
                    archive_model.load_archive_bytes(stream.getvalue())

    def test_archive_audit_exposes_all_independent_checks(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, archive = self._archive(Path(temporary))
            audit = archive_audit_model.audit_archive(archive)
            self.assertTrue(audit.accepted)
            self.assertEqual(audit.check_count, len(archive_audit_model.CHECK_IDS))
            self.assertEqual(audit.passed_count, len(archive_audit_model.CHECK_IDS))
            self.assertEqual(audit.failed_count, 0)
            self.assertEqual(tuple(item.check_id for item in audit.checks), archive_audit_model.CHECK_IDS)
            self.assertEqual(archive_audit_model.audit_from_mapping(audit.to_dict()).to_dict(), audit.to_dict())
            self.assertIn("ZIP", archive_audit_model.render_audit_markdown(audit))
            self.assertTrue(archive_audit_model.audit_json(audit).startswith("{"))
            self.assertIn("check_id", archive_audit_model.audit_csv(audit))

    def test_archive_query_resources_filters_and_pages(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, archive = self._archive(Path(temporary))
            result = archive_query_model.query_archive(archive, resources=archive_query_model.DEFAULT_RESOURCES, limit=100)
            audit = archive_query_audit_model.audit_query(result)
            self.assertTrue(audit.accepted)
            self.assertEqual(result.total, 26)
            self.assertEqual(result.matched, 26)
            self.assertEqual(result.returned, 26)
            self.assertFalse(result.truncated)
            self.assertEqual(result.rows[0].resource, "summary")
            self.assertEqual(result.rows[-1].resource, "evidence")
            self.assertEqual(tuple(row.ordinal for row in result.rows), tuple(range(26)))
            page = archive_query_model.query_archive(archive, resources=("artifacts",), name=archive_model.ARCHIVE_PAYLOAD_FILES[0], limit=1)
            self.assertEqual(page.matched, 1)
            self.assertEqual(page.returned, 1)
            self.assertFalse(page.truncated)
            self.assertEqual(page.rows[0].payload["name"], archive_model.ARCHIVE_PAYLOAD_FILES[0])
            bounded = archive_query_model.query_archive(archive, resources=("artifacts", "files"), text="observatory", offset=1, limit=2)
            self.assertEqual(bounded.returned, 2)
            self.assertTrue(bounded.truncated)
            self.assertEqual(bounded.next_offset, 3)
            self.assertEqual(archive_query_audit_model.audit_query(bounded).accepted, True)

    def test_archive_query_rejects_unsupported_resources_and_bad_ranges(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, archive = self._archive(Path(temporary))
            for resources in (("missing",), ("artifacts", "missing"), ("",)):
                with self.assertRaises(ValidationError):
                    archive_query_model.query_archive(archive, resources=resources)
            with self.assertRaises(ValidationError):
                archive_query_model.query_archive(archive, offset=-1)
            with self.assertRaises(ValidationError):
                archive_query_model.query_archive(archive, limit=0)
            with self.assertRaises(ValidationError):
                archive_query_model.query_archive(archive, limit=archive_query_model.MAX_LIMIT + 1)

    def test_archive_query_mapping_tamper_is_detected_by_typed_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, archive = self._archive(Path(temporary))
            result = archive_query_model.query_archive(archive, resources=("summary", "artifacts"), limit=100)
            mapped = result.to_dict()
            mapped["returned"] = mapped["returned"] + 1
            with self.assertRaises(ValidationError):
                archive_query_model.query_from_mapping(mapped)
            mapped = result.to_dict()
            mapped["rows"] = tuple(mapped["rows"]) + (mapped["rows"][0],)
            with self.assertRaises(ValidationError):
                archive_query_model.query_from_mapping(mapped)
            self.assertEqual(archive_query_model.query_from_mapping(result.to_dict()).to_dict(), result.to_dict())
            self.assertEqual(archive_query_audit_model.audit_from_mapping(archive_query_audit_model.audit_query(result).to_dict()).to_dict(), archive_query_audit_model.audit_query(result).to_dict())

    def test_transfer_conserves_ranges_receipts_and_assembly(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, archive, transfer = self._transfer(Path(temporary), chunk_size=257)
            self.assertGreater(transfer.chunk_count, 1)
            self.assertEqual(transfer.chunks[0].offset, 0)
            self.assertEqual(transfer.chunks[-1].offset + transfer.chunks[-1].size, transfer.archive_size)
            self.assertEqual(sum(item.size for item in transfer.chunks), transfer.archive_size)
            self.assertEqual(transfer_model.transfer_from_mapping(transfer.to_dict()).to_dict(), transfer.to_dict())
            self.assertEqual(transfer_model.manifest_document(transfer)["transfer_address"], transfer.content_address)
            self.assertEqual(transfer_model.assemble_archive_bytes(transfer), archive_model.archive_bytes(archive))
            audit = transfer_audit_model.audit_transfer(transfer)
            self.assertTrue(audit.accepted)
            self.assertEqual(audit.state, "complete")
            self.assertEqual(audit.missing_count, 0)
            self.assertEqual(audit.passed_count, len(transfer_audit_model.CHECK_IDS))
            self.assertEqual(transfer_audit_model.audit_from_mapping(audit.to_dict()).to_dict(), audit.to_dict())

    def test_transfer_persists_and_reloads_exactly(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, archive, transfer = self._transfer(root, chunk_size=512)
            destination = root / "transfer"
            transfer_model.write_transfer(transfer, destination)
            self.assertEqual({item.name for item in destination.iterdir()}, {transfer_model.MANIFEST_NAME, transfer_model.CHUNK_DIRECTORY})
            self.assertEqual({item.name for item in (destination / transfer_model.CHUNK_DIRECTORY).iterdir()}, {transfer_model.chunk_name(index).split("/", 1)[1] for index in range(transfer.chunk_count)})
            loaded = transfer_model.load_transfer(destination)
            self.assertEqual(loaded.to_dict(), transfer.to_dict())
            self.assertEqual(transfer_model.assemble_archive_bytes(loaded), archive_model.archive_bytes(archive))
            self.assertTrue(transfer_audit_model.audit_transfer_directory(str(destination)).accepted)
            self.assertEqual(transfer_model.query_transfer(loaded, resource="chunks", limit=100).returned, transfer.chunk_count)
            self.assertEqual(transfer_model.query_transfer(loaded, resource="progress").rows[0]["complete"], True)

    def test_transfer_rejects_bad_chunk_sizes_receipts_and_members(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, _, transfer = self._transfer(root, chunk_size=300)
            with self.assertRaises(ValidationError):
                transfer_model.build_transfer(transfer.archive, chunk_size=transfer_model.MIN_CHUNK_SIZE - 1)
            destination = root / "transfer"
            transfer_model.write_transfer(transfer, destination)
            bad_chunk = destination / transfer_model.chunk_name(0)
            bad_chunk.write_bytes(bad_chunk.read_bytes() + b"x")
            with self.assertRaises(ValidationError):
                transfer_model.load_transfer(destination)
            bad_chunk.write_bytes(transfer_model.chunk_bytes(transfer, 0))
            (destination / "unexpected.txt").write_text("unexpected", encoding="utf-8")
            with self.assertRaises(ValidationError):
                transfer_model.load_transfer(destination)

    def test_partial_transfer_round_trip_has_explicit_incomplete_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, archive, transfer = self._transfer(root, chunk_size=256)
            assembler = transfer_model.TransferAssembler(transfer)
            assembler.add_chunk(0, transfer_model.chunk_bytes(transfer, 0))
            if transfer.chunk_count > 2:
                assembler.add_chunk(transfer.chunk_count // 2, transfer_model.chunk_bytes(transfer, transfer.chunk_count // 2))
            self.assertFalse(assembler.progress().complete)
            self.assertEqual(assembler.progress().received_bytes, sum(len(value) for value in assembler.received_parts().values()))
            partial_destination = root / "partial-transfer"
            transfer_model.write_partial_transfer(assembler, partial_destination)
            loaded = transfer_model.load_partial_transfer(partial_destination)
            self.assertEqual(loaded.received_indices(), assembler.received_indices())
            partial_audit = transfer_audit_model.audit_transfer(loaded)
            self.assertFalse(partial_audit.accepted)
            self.assertEqual(partial_audit.state, "incomplete")
            self.assertFalse(partial_audit.complete)
            for index in range(transfer.chunk_count):
                if index not in loaded.received_indices():
                    loaded.add_chunk(index, transfer_model.chunk_bytes(transfer, index))
            self.assertTrue(loaded.progress().complete)
            self.assertEqual(loaded.finalize(), archive_model.archive_bytes(archive))
            self.assertTrue(transfer_audit_model.audit_transfer(loaded).accepted)

    def test_transfer_assembler_rejects_duplicate_and_corrupt_chunks(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, transfer = self._transfer(Path(temporary), chunk_size=400)
            assembler = transfer_model.TransferAssembler(transfer)
            first = transfer_model.chunk_bytes(transfer, 0)
            assembler.add_chunk(0, first)
            with self.assertRaises(ValidationError):
                assembler.add_chunk(0, first)
            with self.assertRaises(ValidationError):
                assembler.add_chunk(1, b"wrong")
            with self.assertRaises(ValidationError):
                assembler.add_chunk(transfer.chunk_count, b"wrong")
            self.assertEqual(assembler.received_indices(), (0,))
            self.assertEqual(assembler.progress().missing_indices[0], 1)

    def test_transfer_queries_are_bounded_and_addressed(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, transfer = self._transfer(Path(temporary), chunk_size=256)
            for resource, expected in (("summary", 1), ("chunks", transfer.chunk_count), ("progress", 1), ("evidence", transfer.chunk_count)):
                result = transfer_model.query_transfer(transfer, resource=resource, limit=100)
                self.assertEqual(result.returned, expected)
                self.assertEqual(result.query.resource, resource)
                self.assertEqual(transfer_model.query_from_mapping(result.to_dict()).to_dict(), result.to_dict())
                self.assertTrue(transfer_model.verify_query_result(result))
            page = transfer_model.query_transfer(transfer, resource="chunks", text="chunk", offset=1, limit=2)
            self.assertLessEqual(page.returned, 2)
            self.assertTrue(page.truncated)
            with self.assertRaises(ValidationError):
                transfer_model.query_transfer(transfer, resource="invalid")
            with self.assertRaises(ValidationError):
                transfer_model.query_transfer(transfer, limit=0)

    def test_archive_runtime_links_all_receipts_and_persists_both_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = self._package(root)
            package_dir = root / "package"
            package_model.write_package(package, package_dir)
            archive_destination = root / "runtime.zip"
            transfer_destination = root / "runtime-transfer"
            value = archive_runtime_model.run_runtime((package_dir,), runtime_id="archive-runtime", archive_id="runtime-archive", transfer_id="runtime-transfer", chunk_size=256, limit=100, destination=archive_destination, transfer_destination=transfer_destination)
            audit = archive_runtime_audit_model.audit_runtime(value)
            self.assertTrue(value.accepted)
            self.assertTrue(audit.accepted)
            self.assertTrue(value.archive_written)
            self.assertTrue(value.transfer_written)
            self.assertTrue(archive_destination.is_file())
            self.assertTrue(transfer_destination.is_dir())
            self.assertEqual(value.input_count, 1)
            self.assertEqual(archive_runtime_model.runtime_from_mapping(value.to_dict()).to_dict(), value.to_dict())
            self.assertEqual(archive_runtime_audit_model.audit_from_mapping(audit.to_dict()).to_dict(), audit.to_dict())
            loaded_archive = archive_model.load_archive(archive_destination)
            loaded_transfer = transfer_model.load_transfer(transfer_destination)
            self.assertEqual(loaded_archive.content_address, value.archive_address)
            self.assertEqual(loaded_transfer.content_address, value.transfer_address)
            self.assertEqual(transfer_model.assemble_archive_bytes(loaded_transfer), archive_model.archive_bytes(loaded_archive))

    def test_archive_runtime_rejects_mismatched_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self._package(root / "first")
            second = self._package(root / "second", package_id="archive-package-two")
            first_dir = root / "first-package"
            second_dir = root / "second-package"
            package_model.write_package(first, first_dir)
            package_model.write_package(second, second_dir)
            with self.assertRaises(ValidationError):
                archive_runtime_model.run_runtime((first_dir, second_dir), limit=10)
            self.assertNotEqual(first.content_address, second.content_address)

    def test_cli_archive_transfer_runtime_and_schema_commands(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = self._package(root)
            package_dir = root / "package"
            package_model.write_package(package, package_dir)
            archive_zip = root / "archive.zip"
            archive_json = root / "archive.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["registry-federation-consensus-gate-certificate-observatory-archive", "--input", str(package_dir), "--destination", str(archive_zip), "--format", "json", "--output", str(archive_json)]), 0)
            archive = archive_model.load_archive(archive_zip)
            self.assertEqual(json.loads(archive_json.read_text(encoding="utf-8"))["content_address"], archive.content_address)
            audit_json = root / "archive-audit.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["registry-federation-consensus-gate-certificate-observatory-archive-audit", "--input", str(archive_zip), "--format", "json", "--output", str(audit_json)]), 0)
            self.assertTrue(json.loads(audit_json.read_text(encoding="utf-8"))["accepted"])
            query_json = root / "archive-query.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["registry-federation-consensus-gate-certificate-observatory-archive-query", "--input", str(archive_zip), "--resource", "artifacts", "--limit", "2", "--format", "json", "--output", str(query_json)]), 0)
            self.assertEqual(json.loads(query_json.read_text(encoding="utf-8"))["returned"], 2)
            transfer_dir = root / "transfer"
            transfer_json = root / "transfer.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["registry-federation-consensus-gate-certificate-observatory-archive-transfer", "--input", str(archive_zip), "--chunk-size", "256", "--destination", str(transfer_dir), "--format", "json", "--output", str(transfer_json)]), 0)
            self.assertTrue(transfer_dir.is_dir())
            transfer_audit_json = root / "transfer-audit.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["registry-federation-consensus-gate-certificate-observatory-archive-transfer-audit", "--input", str(transfer_dir), "--format", "json", "--output", str(transfer_audit_json)]), 0)
            self.assertTrue(json.loads(transfer_audit_json.read_text(encoding="utf-8"))["accepted"])
            runtime_json = root / "runtime.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["registry-federation-consensus-gate-certificate-observatory-archive-runtime", "--input", str(package_dir), "--destination", str(root / "runtime.zip"), "--transfer-destination", str(root / "runtime-transfer"), "--format", "json", "--output", str(runtime_json)]), 0)
            self.assertTrue(json.loads(runtime_json.read_text(encoding="utf-8"))["accepted"])
            commands = ("registry-federation-consensus-gate-certificate-observatory-archive-schema", "registry-federation-consensus-gate-certificate-observatory-archive-audit-schema", "registry-federation-consensus-gate-certificate-observatory-archive-query-result-schema", "registry-federation-consensus-gate-certificate-observatory-archive-transfer-schema", "registry-federation-consensus-gate-certificate-observatory-archive-transfer-query-result-schema", "registry-federation-consensus-gate-certificate-observatory-archive-runtime-schema", "registry-federation-consensus-gate-certificate-observatory-archive-runtime-audit-schema")
            for command in commands:
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(main([command]), 0)
                self.assertIsInstance(json.loads(output.getvalue()), dict)

    def test_http_archive_surface_supports_schema_query_and_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = self._package(root)
            package_dir = root / "package"
            package_model.write_package(package, package_dir)
            server = create_server("127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}/v1/registry/federation/consensus/gate/certificate/observatory/archive"
                schemas = ("/schema", "/manifest-schema", "/audit/schema", "/query/schema", "/query/result-schema", "/transfer/schema", "/transfer/query/result-schema", "/runtime/schema", "/runtime/audit/schema", "/capabilities")
                for suffix in schemas:
                    with urlopen(base + suffix, timeout=10) as response:
                        self.assertEqual(response.status, 200)
                        self.assertIsInstance(json.loads(response.read()), dict)
                archive_query = urlencode({"input": str(package_dir), "resource": "artifacts", "limit": "2", "format": "json"})
                with urlopen(base + "/query?" + archive_query, timeout=10) as response:
                    payload = json.loads(response.read())
                    self.assertEqual(payload["returned"], 2)
                archive_path = root / "http.zip"
                archive_request = urlencode({"input": str(package_dir), "destination": str(archive_path), "format": "summary"})
                with urlopen(base + "?" + archive_request, timeout=10) as response:
                    self.assertEqual(response.status, 200)
                    self.assertTrue(json.loads(response.read())["archive_size"] > 0)
                audit_request = urlencode({"input": str(archive_path), "format": "summary"})
                with urlopen(base + "/audit?" + audit_request, timeout=10) as response:
                    self.assertEqual(json.loads(response.read())["accepted"], True)
                transfer_path = root / "http-transfer"
                transfer_request = urlencode({"input": str(archive_path), "destination": str(transfer_path), "chunk_size": "256", "format": "summary"})
                with urlopen(base + "/transfer?" + transfer_request, timeout=10) as response:
                    self.assertEqual(response.status, 200)
                    self.assertTrue(json.loads(response.read())["chunk_count"] > 1)
                runtime_request = urlencode((("input", str(package_dir)), ("destination", str(root / "http-runtime.zip")), ("transfer_destination", str(root / "http-runtime-transfer")), ("format", "summary")))
                with urlopen(base + "/runtime?" + runtime_request, timeout=10) as response:
                    self.assertTrue(json.loads(response.read())["accepted"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_schemas_are_closed_and_capabilities_are_path_free(self):
        schemas = (archive_model.artifact_schema(), archive_model.manifest_schema(), archive_model.archive_schema(), archive_audit_model.check_schema(), archive_audit_model.audit_schema(), archive_query_model.query_schema(), archive_query_model.row_schema(), archive_query_model.result_schema(), archive_query_audit_model.check_schema(), archive_query_audit_model.audit_schema(), transfer_model.chunk_schema(), transfer_model.transfer_schema(), transfer_model.progress_schema(), transfer_model.query_schema(), transfer_model.query_result_schema(), transfer_audit_model.check_schema(), transfer_audit_model.audit_schema(), archive_runtime_model.runtime_schema(), archive_runtime_audit_model.check_schema(), archive_runtime_audit_model.audit_schema())
        for schema in schemas:
            self.assertFalse(schema["additionalProperties"])
            self.assertEqual(set(schema["required"]), set(schema["properties"]))
        capabilities = (archive_model.capabilities(), archive_audit_model.capabilities(), archive_query_model.capabilities(), archive_query_audit_model.capabilities(), transfer_model.capabilities(), transfer_audit_model.capabilities(), archive_runtime_model.capabilities(), archive_runtime_audit_model.capabilities())
        for value in capabilities:
            self.assertNotIn("local_path", json.dumps(value))
            self.assertNotIn("agent", json.dumps(value).lower())
            self.assertIsInstance(value["boundary"], str)

    def test_public_outputs_do_not_leak_paths_or_forbidden_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package, archive, transfer = self._transfer(root)
            values = [package.to_dict(), archive.to_dict(), archive_audit_model.audit_archive(archive).to_dict(), archive_query_model.query_archive(archive).to_dict(), transfer.to_dict(), transfer_audit_model.audit_transfer(transfer).to_dict(), archive_runtime_model.run_runtime((root,), limit=10).to_dict() if False else {}]
            forbidden = ("local_path", "generated_by", "assistant", "agent", "model", "language", "email")
            encoded = json.dumps(values, sort_keys=True).lower()
            for token in forbidden:
                self.assertNotIn(token, encoded)
            self.assertNotIn(str(root).lower(), encoded)

    def test_recovery_receipt_identifies_every_missing_range(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, transfer = self._transfer(Path(temporary), chunk_size=256)
            assembler = transfer_model.TransferAssembler(transfer)
            for index in (0, 2, 4):
                assembler.add_chunk(index, transfer_model.chunk_bytes(transfer, index))
            recovery = recovery_model.build_recovery(assembler, recovery_id="missing-ranges")
            self.assertFalse(recovery.complete)
            self.assertFalse(recovery.resumed)
            self.assertEqual(recovery.received_indices, (0, 2, 4))
            self.assertEqual(recovery.missing_indices, tuple(index for index in range(transfer.chunk_count) if index not in (0, 2, 4)))
            self.assertEqual(recovery.action_count, len(recovery.actions))
            self.assertEqual(tuple(item.index for item in recovery.actions), recovery.missing_indices)
            self.assertEqual(tuple(item.offset for item in recovery.actions), tuple(transfer.chunks[index].offset for index in recovery.missing_indices))
            self.assertEqual(tuple(item.size for item in recovery.actions), tuple(transfer.chunks[index].size for index in recovery.missing_indices))
            self.assertEqual(recovery_model.recovery_from_mapping(recovery.to_dict()).to_dict(), recovery.to_dict())
            self.assertEqual(recovery_model.address_recovery(recovery), recovery.content_address)

    def test_recovery_audit_accepts_valid_incomplete_receipts(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, transfer = self._transfer(Path(temporary), chunk_size=512)
            assembler = transfer_model.TransferAssembler(transfer)
            assembler.add_chunk(0, transfer_model.chunk_bytes(transfer, 0))
            recovery = recovery_model.build_recovery(assembler)
            audit = recovery_audit_model.audit_recovery(recovery)
            self.assertTrue(audit.accepted)
            self.assertFalse(audit.resumed)
            self.assertEqual(audit.check_count, len(recovery_audit_model.CHECK_IDS))
            self.assertEqual(audit.passed_count, len(recovery_audit_model.CHECK_IDS))
            self.assertEqual(audit.failed_count, 0)
            self.assertEqual(tuple(item.check_id for item in audit.checks), recovery_audit_model.CHECK_IDS)
            self.assertEqual(recovery_audit_model.audit_from_mapping(audit.to_dict()).to_dict(), audit.to_dict())
            self.assertIn("completion", recovery_audit_model.render_audit_markdown(audit).lower())
            self.assertIn("check_id", recovery_audit_model.audit_csv(audit))

    def test_recovery_resumes_partial_directory_against_exact_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, archive, transfer = self._transfer(root, chunk_size=256)
            archive_path = root / "source.zip"
            archive_model.write_archive(archive, archive_path)
            partial = transfer_model.TransferAssembler(transfer)
            for index in range(0, transfer.chunk_count, 3):
                partial.add_chunk(index, transfer_model.chunk_bytes(transfer, index))
            partial_path = root / "partial"
            transfer_model.write_partial_transfer(partial, partial_path)
            recovery_before = recovery_model.build_recovery_from_directory(partial_path, recovery_id="directory-recovery")
            self.assertFalse(recovery_before.complete)
            recovered_path = root / "recovered"
            recovery = recovery_model.resume_transfer(partial_path, archive_path, destination=recovered_path, recovery_id="directory-recovery")
            self.assertTrue(recovery.complete)
            self.assertTrue(recovery.resumed)
            self.assertTrue(recovery.persisted)
            self.assertEqual(recovery.missing_indices, ())
            self.assertEqual(recovery.action_count, 0)
            self.assertEqual(recovery.resumed_transfer_address, transfer.content_address)
            self.assertEqual(transfer_model.load_transfer(recovered_path).to_dict(), transfer.to_dict())
            self.assertTrue(recovery_audit_model.audit_recovery(recovery).accepted)
            summary = recovery_query_model.query_recovery(recovery, resource="summary")
            self.assertEqual(summary.returned, 1)
            self.assertFalse(summary.truncated)
            self.assertTrue(recovery_query_model.query_from_mapping(summary.to_dict()).to_dict() == summary.to_dict())

    def test_recovery_rejects_wrong_archive_and_wrong_transfer_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, archive, transfer = self._transfer(root, chunk_size=256)
            archive_path = root / "source.zip"
            archive_model.write_archive(archive, archive_path)
            partial = transfer_model.TransferAssembler(transfer)
            partial.add_chunk(0, transfer_model.chunk_bytes(transfer, 0))
            partial_path = root / "partial"
            transfer_model.write_partial_transfer(partial, partial_path)
            different_package = self._package(root / "different", package_id="different-package")
            different_archive = archive_model.build_archive(different_package, archive_id="different-archive")
            different_path = root / "different.zip"
            archive_model.write_archive(different_archive, different_path)
            with self.assertRaises(ValidationError):
                recovery_model.resume_transfer(partial_path, different_path, destination=root / "wrong")
            tampered = json.loads((partial_path / transfer_model.MANIFEST_NAME).read_text(encoding="utf-8"))
            tampered["transfer_id"] = "wrong-transfer"
            (partial_path / transfer_model.MANIFEST_NAME).write_text(json.dumps(tampered, sort_keys=True, separators=(",", ":")), encoding="utf-8")
            with self.assertRaises(ValidationError):
                recovery_model.build_recovery_from_directory(partial_path)

    def test_recovery_query_resources_filter_and_pagination(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, transfer = self._transfer(Path(temporary), chunk_size=256)
            assembler = transfer_model.TransferAssembler(transfer)
            assembler.add_chunk(0, transfer_model.chunk_bytes(transfer, 0))
            recovery = recovery_model.build_recovery(assembler)
            for resource in recovery_query_model.RESOURCE_NAMES:
                result = recovery_query_model.query_recovery(recovery, resource=resource, limit=100)
                self.assertEqual(result.query.resource, resource)
                self.assertEqual(result.returned, len(result.rows))
                self.assertEqual(recovery_query_model.verify_result(result), result)
            page = recovery_query_model.query_recovery(recovery, resource="actions", text="chunk", offset=1, limit=2)
            self.assertLessEqual(page.returned, 2)
            if page.matched > page.returned:
                self.assertTrue(page.truncated)
            with self.assertRaises(ValidationError):
                recovery_query_model.query_recovery(recovery, resource="unknown")
            with self.assertRaises(ValidationError):
                recovery_query_model.query_recovery(recovery, offset=-1)
            with self.assertRaises(ValidationError):
                recovery_query_model.query_recovery(recovery, limit=0)

    def test_recovery_cli_commands_complete_and_audit_a_repair(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, archive, transfer = self._transfer(root, chunk_size=256)
            archive_path = root / "archive.zip"
            archive_model.write_archive(archive, archive_path)
            partial = transfer_model.TransferAssembler(transfer)
            partial.add_chunk(0, transfer_model.chunk_bytes(transfer, 0))
            partial_path = root / "partial"
            transfer_model.write_partial_transfer(partial, partial_path)
            recovery_json = root / "recovery.json"
            recovered_path = root / "recovered"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["registry-federation-consensus-gate-certificate-observatory-archive-transfer-recovery", "--input", str(partial_path), "--archive-input", str(archive_path), "--destination", str(recovered_path), "--format", "json", "--output", str(recovery_json)]), 0)
            recovery = recovery_model.recovery_from_mapping(json.loads(recovery_json.read_text(encoding="utf-8")))
            self.assertTrue(recovery.resumed)
            audit_json = root / "recovery-audit.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["registry-federation-consensus-gate-certificate-observatory-archive-transfer-recovery-audit", "--input", str(recovery_json), "--format", "json", "--output", str(audit_json)]), 0)
            self.assertTrue(json.loads(audit_json.read_text(encoding="utf-8"))["accepted"])
            query_json = root / "recovery-query.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["registry-federation-consensus-gate-certificate-observatory-archive-transfer-recovery-query", "--input", str(recovery_json), "--resource", "summary", "--format", "json", "--output", str(query_json)]), 0)
            self.assertEqual(json.loads(query_json.read_text(encoding="utf-8"))["returned"], 1)
            for command in ("registry-federation-consensus-gate-certificate-observatory-archive-transfer-recovery-action-schema", "registry-federation-consensus-gate-certificate-observatory-archive-transfer-recovery-schema", "registry-federation-consensus-gate-certificate-observatory-archive-transfer-recovery-audit-schema", "registry-federation-consensus-gate-certificate-observatory-archive-transfer-recovery-query-result-schema"):
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(main([command]), 0)
                self.assertIsInstance(json.loads(output.getvalue()), dict)

    def test_recovery_http_routes_expose_completion_and_query(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, archive, transfer = self._transfer(root, chunk_size=256)
            archive_path = root / "archive.zip"
            archive_model.write_archive(archive, archive_path)
            partial = transfer_model.TransferAssembler(transfer)
            partial.add_chunk(0, transfer_model.chunk_bytes(transfer, 0))
            partial_path = root / "partial"
            transfer_model.write_partial_transfer(partial, partial_path)
            server = create_server("127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}/v1/registry/federation/consensus/gate/certificate/observatory/archive/transfer/recovery"
                for suffix in ("/action-schema", "/schema", "/audit/schema", "/query/schema", "/query/result-schema", "/capabilities"):
                    with urlopen(base + suffix, timeout=10) as response:
                        self.assertEqual(response.status, 200)
                        self.assertIsInstance(json.loads(response.read()), dict)
                recovery_path = root / "http-recovery.json"
                recovered_path = root / "http-recovered"
                recovery_request = urlencode({"input": str(partial_path), "archive_input": str(archive_path), "destination": str(recovered_path), "format": "json"})
                with urlopen(base + "?" + recovery_request, timeout=10) as response:
                    payload = json.loads(response.read())
                    self.assertTrue(payload["resumed"])
                recovery_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
                query_request = urlencode({"input": str(recovery_path), "resource": "summary", "format": "json"})
                with urlopen(base + "/query?" + query_request, timeout=10) as response:
                    self.assertEqual(json.loads(response.read())["returned"], 1)
                audit_request = urlencode({"input": str(recovery_path), "format": "summary"})
                with urlopen(base + "/audit?" + audit_request, timeout=10) as response:
                    self.assertTrue(json.loads(response.read())["accepted"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_recovery_schemas_and_capabilities_are_closed(self):
        for schema in (recovery_model.action_schema(), recovery_model.recovery_schema(), recovery_audit_model.check_schema(), recovery_audit_model.audit_schema(), recovery_query_model.query_schema(), recovery_query_model.result_schema()):
            self.assertFalse(schema["additionalProperties"])
            self.assertEqual(set(schema["required"]), set(schema["properties"]))
        for capabilities in (recovery_model.capabilities(), recovery_audit_model.capabilities(), recovery_query_model.capabilities()):
            encoded = json.dumps(capabilities, sort_keys=True).lower()
            self.assertNotIn("local_path", encoded)
            self.assertNotIn("generated_by", encoded)
            self.assertNotIn("language", encoded)

    def test_recovery_rejects_tampered_state_and_action_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, transfer = self._transfer(Path(temporary), chunk_size=256)
            assembler = transfer_model.TransferAssembler(transfer)
            assembler.add_chunk(0, transfer_model.chunk_bytes(transfer, 0))
            recovery = recovery_model.build_recovery(assembler)
            tampered = recovery.to_dict()
            tampered["missing_indices"] = tuple(reversed(tampered["missing_indices"]))
            with self.assertRaises(ValidationError):
                recovery_model.recovery_from_mapping(tampered)
            tampered = recovery.to_dict()
            tampered["complete"] = True
            with self.assertRaises(ValidationError):
                recovery_model.recovery_from_mapping(tampered)
            tampered = recovery.to_dict()
            action = dict(tampered["actions"][0])
            action["action_address"] = recovery_model.ACTION_PREFIX + ":" + "0" * 64
            tampered["actions"] = (action,) + tuple(tampered["actions"][1:])
            with self.assertRaises(ValidationError):
                recovery_model.recovery_from_mapping(tampered)

    def test_recovery_serializers_are_deterministic_and_complete(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, transfer = self._transfer(Path(temporary), chunk_size=256)
            assembler = transfer_model.TransferAssembler(transfer)
            assembler.add_chunk(0, transfer_model.chunk_bytes(transfer, 0))
            recovery = recovery_model.build_recovery(assembler, recovery_id="serializer-recovery")
            self.assertEqual(recovery_model.recovery_json(recovery), recovery_model.recovery_json(recovery))
            self.assertTrue(recovery_model.recovery_csv(recovery).startswith("index,offset,size"))
            self.assertIn("Missing chunks", recovery_model.render_recovery_markdown(recovery))
            audit = recovery_audit_model.audit_recovery(recovery)
            self.assertEqual(recovery_audit_model.audit_json(audit), recovery_audit_model.audit_json(audit))
            self.assertTrue(recovery_audit_model.audit_csv(audit).startswith("ordinal,check_id"))
            self.assertIn("Recovery Audit", recovery_audit_model.render_audit_markdown(audit))
            for resource in ("summary", "actions", "missing", "evidence"):
                result = recovery_query_model.query_recovery(recovery, resource=resource, limit=200)
                self.assertEqual(recovery_query_model.query_json(result), recovery_query_model.query_json(result))
                self.assertTrue(recovery_query_model.query_csv(result).startswith("resource,payload"))
                self.assertIn("Recovery Query", recovery_query_model.render_query_markdown(result))

    def test_recovery_overwrite_requires_explicit_authorization(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, archive, transfer = self._transfer(root, chunk_size=256)
            archive_path = root / "archive.zip"
            archive_model.write_archive(archive, archive_path)
            partial = transfer_model.TransferAssembler(transfer)
            partial.add_chunk(0, transfer_model.chunk_bytes(transfer, 0))
            partial_path = root / "partial"
            transfer_model.write_partial_transfer(partial, partial_path)
            recovered_path = root / "recovered"
            recovery_model.resume_transfer(partial_path, archive_path, destination=recovered_path)
            with self.assertRaises(ValidationError):
                recovery_model.resume_transfer(partial_path, archive_path, destination=recovered_path)
            repeated = recovery_model.resume_transfer(partial_path, archive_path, destination=recovered_path, overwrite=True)
            self.assertTrue(repeated.resumed and repeated.persisted)

    def test_archive_builds_from_package_directory_and_preserves_projection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = self._package(root)
            package_dir = root / "package"
            package_model.write_package(package, package_dir)
            archive = archive_model.build_archive_from_directory(package_dir, archive_id="directory-archive")
            self.assertEqual(archive.package_id, package.package_id)
            self.assertEqual(archive.package_address, package.content_address)
            self.assertEqual(archive_model.load_archive_bytes(archive_model.archive_bytes(archive)).package.content_address, package.content_address)
            self.assertTrue(archive_audit_model.audit_archive(archive).accepted)
            self.assertEqual(archive_model.manifest_document(archive)["files"], archive_model.ARCHIVE_PAYLOAD_FILES)

    def test_archive_writer_requires_explicit_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, archive = self._archive(root)
            destination = root / "archive.zip"
            archive_model.write_archive(archive, destination)
            with self.assertRaises(ValidationError):
                archive_model.write_archive(archive, destination)
            archive_model.write_archive(archive, destination, overwrite=True)
            self.assertEqual(archive_model.load_archive(destination).content_address, archive.content_address)

    def test_archive_load_rejects_noncanonical_member_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, archive = self._archive(Path(temporary))
            with zipfile.ZipFile(io.BytesIO(archive_model.archive_bytes(archive)), "r") as source:
                members = {info.filename: source.read(info.filename) for info in source.infolist()}
            manifest = json.loads(members[archive_model.ARCHIVE_MANIFEST_NAME])
            members[archive_model.ARCHIVE_MANIFEST_NAME] = json.dumps(manifest, indent=2).encode("utf-8")
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as target:
                for name in archive_model.FILES:
                    target.writestr(name, members[name])
            with self.assertRaises(ValidationError):
                archive_model.load_archive_bytes(stream.getvalue())

    def test_transfer_builders_from_file_and_bytes_replay_the_same_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, archive, transfer = self._transfer(root, chunk_size=512)
            archive_path = root / "archive.zip"
            archive_model.write_archive(archive, archive_path)
            from_file = transfer_model.build_transfer_from_file(archive_path, transfer_id="file-transfer", chunk_size=512)
            from_bytes = transfer_model.build_transfer_from_bytes(archive_model.archive_bytes(archive), archive_address=archive.content_address, transfer_id="bytes-transfer", chunk_size=512, archive=archive)
            self.assertEqual(from_file.archive_address, from_bytes.archive_address)
            self.assertEqual(from_file.archive_size, from_bytes.archive_size)
            self.assertEqual(from_file.chunk_count, from_bytes.chunk_count)
            self.assertEqual(tuple(item.to_dict() for item in from_file.chunks), tuple(item.to_dict() for item in from_bytes.chunks))
            self.assertNotEqual(from_file.content_address, transfer.content_address)
            self.assertEqual(transfer_model.assemble_archive_bytes(from_file), transfer_model.assemble_archive_bytes(from_bytes))

    def test_transfer_manifest_and_chunk_names_are_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, transfer = self._transfer(Path(temporary), chunk_size=1024)
            manifest = transfer_model.manifest_document(transfer)
            self.assertEqual(set(manifest), {"version", "boundary", "transfer_id", "archive_address", "archive_size", "chunk_size", "chunk_count", "chunks", "transfer_address", "manifest_address"})
            self.assertEqual(tuple(transfer_model.chunk_name(index) for index in range(transfer.chunk_count)), tuple(item.to_dict() and transfer_model.chunk_name(item.index) for item in transfer.chunks))
            with self.assertRaises(ValidationError):
                transfer_model.chunk_name(-1)
            with self.assertRaises(ValidationError):
                transfer_model.chunk_name(transfer_model.MAX_CHUNKS)

    def test_partial_writer_requires_received_data_and_rejects_extra_chunks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, _, transfer = self._transfer(root, chunk_size=256)
            empty = transfer_model.TransferAssembler(transfer)
            with self.assertRaises(ValidationError):
                transfer_model.write_partial_transfer(empty, root / "empty")
            partial = transfer_model.TransferAssembler(transfer)
            partial.add_chunk(0, transfer_model.chunk_bytes(transfer, 0))
            destination = root / "partial"
            transfer_model.write_partial_transfer(partial, destination)
            (destination / "unexpected").write_text("bad", encoding="utf-8")
            with self.assertRaises(ValidationError):
                transfer_model.load_partial_transfer(destination)

    def test_recovery_query_tampering_is_rejected_at_result_boundary(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, transfer = self._transfer(Path(temporary), chunk_size=256)
            assembler = transfer_model.TransferAssembler(transfer)
            assembler.add_chunk(0, transfer_model.chunk_bytes(transfer, 0))
            recovery = recovery_model.build_recovery(assembler)
            result = recovery_query_model.query_recovery(recovery, resource="missing", limit=10)
            tampered = result.to_dict()
            tampered["returned"] = tampered["returned"] + 1
            with self.assertRaises(ValidationError):
                recovery_query_model.query_from_mapping(tampered)
            tampered = result.to_dict()
            tampered["query"] = dict(tampered["query"])
            tampered["query"]["resource"] = "invalid"
            with self.assertRaises(ValidationError):
                recovery_query_model.query_from_mapping(tampered)

    def test_recovery_audit_detects_wrong_finding_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, transfer = self._transfer(Path(temporary), chunk_size=256)
            assembler = transfer_model.TransferAssembler(transfer)
            assembler.add_chunk(0, transfer_model.chunk_bytes(transfer, 0))
            recovery = recovery_model.build_recovery(assembler)
            audit = recovery_audit_model.audit_recovery(recovery)
            mapped = audit.to_dict()
            mapped["checks"] = tuple(reversed(mapped["checks"]))
            with self.assertRaises(ValidationError):
                recovery_audit_model.audit_from_mapping(mapped)
            mapped = audit.to_dict()
            mapped["passed_count"] = mapped["passed_count"] - 1
            with self.assertRaises(ValidationError):
                recovery_audit_model.audit_from_mapping(mapped)

    def test_runtime_rejects_missing_inputs_and_runtime_mapping_drift(self):
        with self.assertRaises(ValidationError):
            archive_runtime_model.run_runtime(())
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = self._package(root)
            package_dir = root / "package"
            package_model.write_package(package, package_dir)
            runtime = archive_runtime_model.run_runtime((package_dir,), limit=10)
            mapped = runtime.to_dict()
            mapped["input_count"] = 2
            with self.assertRaises(ValidationError):
                archive_runtime_model.runtime_from_mapping(mapped)
            self.assertTrue(archive_runtime_audit_model.audit_runtime(runtime).accepted)

    def test_complete_transfer_recovery_is_a_noop_plan_with_zero_actions(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, transfer = self._transfer(Path(temporary), chunk_size=256)
            recovery = recovery_model.build_recovery(transfer, recovery_id="complete-plan")
            self.assertTrue(recovery.complete)
            self.assertFalse(recovery.resumed)
            self.assertEqual(recovery.received_indices, tuple(range(transfer.chunk_count)))
            self.assertEqual(recovery.missing_indices, ())
            self.assertEqual(recovery.actions, ())
            self.assertEqual(recovery.action_count, 0)
            self.assertEqual(recovery.received_bytes, transfer.archive_size)
            self.assertTrue(recovery_audit_model.audit_recovery(recovery).accepted)
            self.assertEqual(recovery_query_model.query_recovery(recovery, resource="actions").returned, 0)
            self.assertEqual(recovery_query_model.query_recovery(recovery, resource="missing").returned, 0)

    def test_recovery_action_addresses_are_individually_replayable(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, transfer = self._transfer(Path(temporary), chunk_size=256)
            assembler = transfer_model.TransferAssembler(transfer)
            assembler.add_chunk(0, transfer_model.chunk_bytes(transfer, 0))
            recovery = recovery_model.build_recovery(assembler)
            for action in recovery.actions:
                self.assertEqual(recovery_model.address_action(action), action.action_address)
                self.assertEqual(recovery_model.RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAction.from_mapping(action.to_dict()).to_dict(), action.to_dict())
                self.assertEqual(action.content_address, transfer.chunks[action.index].content_address)
            self.assertEqual(len({action.action_address for action in recovery.actions}), len(recovery.actions))

    def test_runtime_serialization_and_audit_receipts_are_path_free(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = self._package(root)
            package_dir = root / "package"
            package_model.write_package(package, package_dir)
            runtime = archive_runtime_model.run_runtime((package_dir,), runtime_id="serialized-runtime", limit=100)
            audit = archive_runtime_audit_model.audit_runtime(runtime)
            self.assertEqual(archive_runtime_model.runtime_from_mapping(runtime.to_dict()).to_dict(), runtime.to_dict())
            self.assertEqual(archive_runtime_audit_model.audit_from_mapping(audit.to_dict()).to_dict(), audit.to_dict())
            self.assertEqual(archive_runtime_model.runtime_json(runtime), archive_runtime_model.runtime_json(runtime))
            self.assertEqual(archive_runtime_audit_model.audit_json(audit), archive_runtime_audit_model.audit_json(audit))
            encoded = json.dumps({"runtime": runtime.to_dict(), "audit": audit.to_dict()}, sort_keys=True).lower()
            self.assertNotIn(str(root).lower(), encoded)
            self.assertNotIn("local_path", encoded)

    def test_http_transfer_and_recovery_query_surfaces_return_addressed_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, archive, transfer = self._transfer(root, chunk_size=256)
            archive_path = root / "archive.zip"
            archive_model.write_archive(archive, archive_path)
            transfer_path = root / "transfer"
            transfer_model.write_transfer(transfer, transfer_path)
            server = create_server("127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}/v1/registry/federation/consensus/gate/certificate/observatory/archive"
                transfer_query = urlencode({"input": str(transfer_path), "resource": "progress", "format": "json"})
                with urlopen(base + "/transfer/query?" + transfer_query, timeout=10) as response:
                    payload = json.loads(response.read())
                    self.assertEqual(payload["returned"], 1)
                    self.assertTrue(payload["content_address"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_archive_and_transfer_limits_are_explicitly_bounded(self):
        self.assertLessEqual(archive_model.MAX_ARCHIVE_BYTES, 128 * 1024 * 1024)
        self.assertLessEqual(transfer_model.MAX_TRANSFER_BYTES, 128 * 1024 * 1024)
        self.assertGreaterEqual(transfer_model.MAX_CHUNKS, 1024)
        self.assertLessEqual(archive_query_model.MAX_LIMIT, 200)
        self.assertLessEqual(recovery_query_model.MAX_LIMIT, 200)
        self.assertEqual(len(archive_audit_model.CHECK_IDS), 16)
        self.assertEqual(len(transfer_audit_model.CHECK_IDS), 14)
        self.assertEqual(len(recovery_audit_model.CHECK_IDS), 12)

    def test_recovery_receipt_uses_stable_public_field_vocabulary(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, transfer = self._transfer(Path(temporary), chunk_size=256)
            assembler = transfer_model.TransferAssembler(transfer)
            assembler.add_chunk(0, transfer_model.chunk_bytes(transfer, 0))
            receipt = recovery_model.build_recovery(assembler)
            self.assertEqual(tuple(receipt.to_dict()), recovery_model.RECOVERY_FIELDS)
            self.assertEqual(tuple(recovery_model.RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAction.FIELDS), ("index", "offset", "size", "content_address", "action_address"))
            self.assertEqual(set(recovery_model.capabilities()["resources"]), {"summary", "actions", "missing", "evidence"})
            self.assertEqual(set(recovery_query_model.capabilities()["resources"]), set(recovery_query_model.RESOURCE_NAMES))
            for action in receipt.actions:
                self.assertTrue(action.content_address.startswith(transfer_model.CHUNK_PREFIX + ":"))
                self.assertTrue(action.action_address.startswith(recovery_model.ACTION_PREFIX + ":"))

    def test_recovery_destination_is_not_reported_as_a_public_value(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, archive, transfer = self._transfer(root, chunk_size=256)
            archive_path = root / "archive.zip"
            archive_model.write_archive(archive, archive_path)
            partial = transfer_model.TransferAssembler(transfer)
            partial.add_chunk(0, transfer_model.chunk_bytes(transfer, 0))
            partial_path = root / "partial"
            transfer_model.write_partial_transfer(partial, partial_path)
            recovered_path = root / "recovered"
            receipt = recovery_model.resume_transfer(partial_path, archive_path, destination=recovered_path)
            encoded = json.dumps(receipt.to_dict(), sort_keys=True).lower()
            self.assertNotIn(str(partial_path).lower(), encoded)
            self.assertNotIn(str(archive_path).lower(), encoded)
            self.assertNotIn(str(recovered_path).lower(), encoded)
            self.assertIn("persisted", encoded)
            self.assertTrue(receipt.persisted)

    def test_recovery_capability_limits_match_runtime_guards(self):
        self.assertEqual(recovery_model.capabilities()["limits"]["max_actions"], recovery_model.MAX_ACTIONS)
        self.assertEqual(recovery_model.capabilities()["limits"]["max_transfer_bytes"], transfer_model.MAX_TRANSFER_BYTES)
        self.assertEqual(recovery_query_model.capabilities()["limits"]["max_limit"], recovery_query_model.MAX_LIMIT)
        self.assertEqual(recovery_query_model.capabilities()["limits"]["max_items"], recovery_query_model.MAX_ITEMS)
        self.assertEqual(recovery_model.capabilities()["operations"], ("build", "inspect", "resume", "verify", "serialize"))
        self.assertEqual(recovery_audit_model.capabilities()["check_ids"], recovery_audit_model.CHECK_IDS)
        self.assertEqual(recovery_query_model.DEFAULT_RESOURCES, recovery_query_model.RESOURCE_NAMES)
        self.assertTrue(recovery_model.DEFAULT_RECOVERY_ID)
        self.assertTrue(recovery_model.RECOVERY_PREFIX)
        self.assertTrue(recovery_audit_model.AUDIT_PREFIX)
        self.assertTrue(recovery_query_model.QUERY_PREFIX)
        self.assertEqual(len(recovery_model.RECOVERY_FIELDS), 17)
        self.assertEqual(len(recovery_model.RegistryFederationConsensusGateCertificateObservatoryArchiveTransferRecoveryAction.FIELDS), 5)
        self.assertTrue(recovery_model.VERSION.endswith("-recovery-v1"))
        self.assertTrue(recovery_model.BOUNDARY.endswith("_recovery"))
        self.assertTrue(recovery_query_model.BOUNDARY.endswith("_query"))

    def test_archive_path_and_bytes_verification_share_one_address(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, archive = self._archive(root)
            destination = root / "verified.zip"
            archive_model.write_archive(archive, destination)
            from_path = archive_model.verify_archive_file(destination)
            from_bytes = archive_model.load_archive_bytes(destination.read_bytes())
            self.assertEqual(from_path.content_address, archive.content_address)
            self.assertEqual(from_bytes.content_address, archive.content_address)
            self.assertEqual(from_path.to_dict(), from_bytes.to_dict())
            self.assertEqual(archive_model.archive_bytes(from_path), destination.read_bytes())
            self.assertEqual(archive_model.verify_archive(from_bytes).content_address, archive.content_address)
            self.assertIn("archive_address", archive_model.manifest_document(from_path))

    def test_transfer_received_parts_are_copied_and_progress_is_addressed(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, transfer = self._transfer(Path(temporary), chunk_size=256)
            assembler = transfer_model.TransferAssembler(transfer)
            assembler.add_chunk(0, transfer_model.chunk_bytes(transfer, 0))
            parts = assembler.received_parts()
            self.assertEqual(tuple(parts), (0,))
            parts[0] = b"mutated"
            self.assertEqual(assembler.received_parts()[0], transfer_model.chunk_bytes(transfer, 0))
            progress = assembler.progress()
            self.assertEqual(progress.received_indices, (0,))
            self.assertEqual(progress.missing_indices, assembler.missing_indices())
            self.assertFalse(progress.complete)
            self.assertEqual(transfer_model.address_progress(progress), progress.content_address)


if __name__ == "__main__":
    unittest.main()
