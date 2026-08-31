"""Regression coverage for portable runtime-registry federation archives."""

from __future__ import annotations

# ruff: noqa: E501, I001

import contextlib
import io
import json
import struct
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory as observatory_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_archive as source_archive_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_archive_transfer as transfer_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_archive_transfer_recovery as recovery_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution as execution_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime as runtime_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry as registry_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation as federation_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive as archive_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_audit as archive_audit_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_query as archive_query_model
from glio_noncode import history_observatory_archive_transfer_recovery_execution_runtime_registry_federation_archive_query_audit as archive_query_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit


COMMAND = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-history-observatory-archive-transfer-recovery-execution-runtime-registry-federation-archive"
API_PATH = "/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/query-snapshot/registry/history/observatory/archive/transfer/recovery/execution/runtime/registry/federation/archive"


class HistoryObservatoryArchiveTransferRecoveryExecutionRuntimeRegistryFederationArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_downloaded_data_comparison_query_snapshot_registry_history_observatory import DownloadedDataComparisonQuerySnapshotRegistryHistoryObservatoryTests as observatory_tests

        observatory_tests.setUpClass()
        fixture = observatory_tests()
        history_left, history_right = fixture._histories()
        cls.observatory = observatory_model.build_observatory((history_left, history_right), observatory_id="history-observatory-execution-runtime-registry-federation-archive-fixture")

    @classmethod
    def _federation(cls):
        source_archive = source_archive_model.build_archive(cls.observatory, archive_id="history-observatory-execution-runtime-registry-federation-archive-fixture")
        transfer = transfer_model.build_transfer(source_archive, transfer_id="history-observatory-execution-runtime-registry-federation-archive-fixture", chunk_size=256)
        assembler = transfer_model.TransferAssembler(transfer)
        payload = transfer.payload_bytes()
        assembler.add_chunk(0, payload[0])
        assembler.add_chunk(transfer.chunk_count - 1, payload[transfer.chunk_count - 1])
        recovery = recovery_model.build_recovery(assembler, recovery_id="execution-runtime-registry-federation-archive-plan", checkpointed=True)
        assembler.add_chunk(1, payload[1])
        execution = execution_model.build_execution_from_assembler(recovery, assembler, execution_id="execution-runtime-registry-federation-archive-progress", checkpointed=True)
        primary = runtime_model.build_runtime(execution, runtime_id="execution-runtime-registry-federation-archive-primary")
        secondary = runtime_model.build_runtime(execution, runtime_id="execution-runtime-registry-federation-archive-secondary")
        return federation_model.build_federation(
            (
                registry_model.build_registry((primary,), registry_id="execution-runtime-registry-federation-archive-primary"),
                registry_model.build_registry((secondary,), registry_id="execution-runtime-registry-federation-archive-secondary"),
            ),
            federation_id="execution-runtime-registry-federation-archive-fixture",
        )

    @staticmethod
    def _rewrite(raw: bytes, *, order=None, comment=b"", extra=False, mutate=None, symlink=False, encrypted=False) -> bytes:
        source = io.BytesIO(raw)
        output = io.BytesIO()
        with zipfile.ZipFile(source, "r") as original, zipfile.ZipFile(output, "w") as rewritten:
            infos = original.infolist()
            if order is not None:
                infos = [infos[index] for index in order]
            for info in infos:
                copied = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                copied.compress_type = info.compress_type
                copied.create_system = info.create_system
                copied.external_attr = info.external_attr
                copied.comment = info.comment
                copied.flag_bits = info.flag_bits
                if mutate is not None and info.filename == "manifest.json":
                    data = mutate(original.read(info.filename))
                else:
                    data = original.read(info.filename)
                if symlink and info.filename == "manifest.json":
                    copied.create_system = 3
                    copied.external_attr = (0o120000 | 0o777) << 16
                if encrypted and info.filename == "manifest.json":
                    copied.flag_bits |= 0x1
                rewritten.writestr(copied, data)
            if extra:
                rewritten.writestr("unexpected.json", b"{}")
            rewritten.comment = comment
        result = output.getvalue()
        if not encrypted:
            return result
        data = bytearray(result)
        with zipfile.ZipFile(io.BytesIO(result), "r") as written:
            info = written.getinfo("manifest.json")
            local_flags = struct.unpack_from("<H", data, info.header_offset + 6)[0]
            struct.pack_into("<H", data, info.header_offset + 6, local_flags | 0x1)
        cursor = 0
        while True:
            cursor = data.find(bytes((0x50, 0x4B, 0x01, 0x02)), cursor)
            if cursor < 0:
                break
            name_length = struct.unpack_from("<H", data, cursor + 28)[0]
            if bytes(data[cursor + 46:cursor + 46 + name_length]) == b"manifest.json":
                central_flags = struct.unpack_from("<H", data, cursor + 8)[0]
                struct.pack_into("<H", data, cursor + 8, central_flags | 0x1)
                break
            cursor += 4
        return bytes(data)

    def test_downloaded_archive_round_trip_audits_queries_and_persistence(self):
        federation = self._federation()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            federation_directory = root / "federation"
            federation_model.persist_federation(federation, federation_directory)
            value = archive_model.build_archive_from_directory(federation_directory, archive_id="execution-runtime-registry-federation-archive-round-trip")
            raw = archive_model.archive_bytes(value)
            loaded = archive_model.load_archive_bytes(raw)
            audit = archive_audit_model.audit_archive(loaded)
            query = archive_query_model.query_archive(loaded, resources=archive_query_model.RESOURCES, limit=archive_query_model.MAX_LIMIT)
            query_audit = archive_query_audit_model.audit_query(query, loaded)
            destination = root / "federation.zip"
            archive_model.write_archive(value, destination)

            self.assertEqual(archive_model.FILES, ("manifest.json", "federation/manifest.json", "federation/federation.json", "federation/members.json", "federation/entries.json", "federation/summary.json"))
            self.assertEqual((value.artifact_count, value.archive_size, len(raw)), (5, len(raw), len(raw)))
            self.assertEqual(archive_model.archive_bytes(loaded), raw)
            self.assertEqual(archive_model.load_archive(destination).content_address, value.content_address)
            self.assertEqual((audit.check_count, audit.passed_count, audit.failed_count, audit.passed), (18, 18, 0, True))
            self.assertEqual((query.total_count, query.returned_count, query.truncated), (len(query.rows), len(query.rows), False))
            self.assertGreater(query.total_count, 0)
            self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.failed_count, query_audit.passed), (12, 12, 0, True))
            self.assertEqual(archive_model.archive_from_mapping(json.loads(archive_model.archive_json(value))).content_address, value.content_address)
            self.assertEqual(archive_audit_model.audit_from_mapping(json.loads(archive_audit_model.audit_json(audit))).content_address, audit.content_address)
            self.assertEqual(archive_query_model.query_from_mapping(json.loads(archive_query_model.query_json(query))).content_address, query.content_address)
            self.assertEqual(archive_query_audit_model.audit_from_mapping(json.loads(archive_query_audit_model.audit_json(query_audit))).content_address, query_audit.content_address)
            self.assertTrue(archive_model.archive_csv(value).startswith("archive_id,"))
            self.assertIn("# Runtime Registry Federation Archive", archive_model.render_archive_markdown(value))

    def test_exact_zip_vocabulary_metadata_and_fail_closed_controls(self):
        federation = self._federation()
        value = archive_model.build_archive(federation, archive_id="execution-runtime-registry-federation-archive-safety")
        raw = archive_model.archive_bytes(value)
        with zipfile.ZipFile(io.BytesIO(raw), "r") as archive:
            self.assertEqual(tuple(info.filename for info in archive.infolist()), archive_model.FILES)
            self.assertTrue(all(info.date_time == archive_model.ZIP_EPOCH and info.create_system == 0 and info.external_attr == 0o600 << 16 and not info.comment for info in archive.infolist()))
            self.assertEqual(archive.comment, b"")
        for label, malformed in (
            ("extra", self._rewrite(raw, extra=True)),
            ("order", self._rewrite(raw, order=(5, 4, 3, 2, 1, 0))),
            ("comment", self._rewrite(raw, comment=b"unexpected")),
            ("noncanonical", self._rewrite(raw, mutate=lambda data: data + b"\n")),
            ("symlink", self._rewrite(raw, symlink=True)),
            ("encrypted", self._rewrite(raw, encrypted=True)),
        ):
            with self.subTest(label=label), self.assertRaises(ValidationError):
                archive_model.load_archive_bytes(malformed)

    def test_cli_http_schema_surfaces_and_public_inventory(self):
        federation = self._federation()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            federation_directory = root / "federation"
            federation_model.persist_federation(federation, federation_directory)
            archive_path = root / "federation.zip"
            archive_json_path = root / "archive.json"
            query_path = root / "query.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([COMMAND, str(federation_directory), "--archive-id", "execution-runtime-registry-federation-archive-cli", "--destination", str(archive_path), "--format", "json", "--output", str(archive_json_path)]), 0)
                self.assertEqual(main([COMMAND + "-verify", str(archive_path), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-audit", str(archive_path), "--format", "summary"]), 0)
                self.assertEqual(main([COMMAND + "-query", str(archive_path), "--resource", "states", "--limit", "8", "--format", "json", "--output", str(query_path)]), 0)
                self.assertEqual(main([COMMAND + "-query-audit", str(query_path), "--archive-input", str(archive_path), "--format", "summary"]), 0)
                for suffix in ("artifact-schema", "manifest-schema", "schema", "capabilities", "audit-check-schema", "audit-schema", "audit-capabilities", "query-row-schema", "query-schema", "query-capabilities", "query-audit-check-schema", "query-audit-schema", "query-audit-capabilities"):
                    self.assertEqual(main([COMMAND + "-" + suffix]), 0)
            self.assertEqual(json.loads(archive_json_path.read_text(encoding="utf-8"))["archive_id"], "execution-runtime-registry-federation-archive-cli")
            self.assertEqual(json.loads(query_path.read_text(encoding="utf-8"))["archive_id"], "execution-runtime-registry-federation-archive-cli")

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                server.glio_deployment_guard._rate_windows.clear()
                params = urlencode({"input": str(federation_directory), "archive_id": "execution-runtime-registry-federation-archive-api", "destination": str(root / "api-federation.zip"), "overwrite": "true", "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}?{params}", timeout=30) as response:
                    api_archive = json.loads(response.read().decode("utf-8"))
                api_archive_path = root / "api-federation.zip"
                self.assertEqual((api_archive["archive_id"], api_archive["artifact_count"]), ("execution-runtime-registry-federation-archive-api", 5))
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/verify?{urlencode({'input': str(api_archive_path), 'format': 'json'})}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["archive_id"], api_archive["archive_id"])
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/audit?{urlencode({'input': str(api_archive_path), 'format': 'json'})}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["accepted"])
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query?{urlencode({'input': str(api_archive_path), 'resource': 'states', 'limit': '8', 'format': 'json'})}", timeout=30) as response:
                    api_query = json.loads(response.read().decode("utf-8"))
                api_query_path = root / "api-query.json"
                api_query_path.write_text(json.dumps(api_query), encoding="utf-8")
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/query/audit?{urlencode({'input': str(api_query_path), 'archive_input': str(api_archive_path), 'format': 'summary'})}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read().decode("utf-8"))["accepted"])
                with urlopen(f"http://127.0.0.1:{server.server_port}{API_PATH}/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read().decode("utf-8"))["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

        inventory = build_default_public_surface_audit()
        self.assertEqual((inventory.surface_count, inventory.passed_surface_count, inventory.failed_surface_count, inventory.accepted), (1805, 1805, 0, True))
        for schema in (archive_model.artifact_schema(), archive_model.manifest_schema(), archive_model.archive_schema(), archive_audit_model.check_schema(), archive_audit_model.audit_schema(), archive_query_model.row_schema(), archive_query_model.query_schema(), archive_query_audit_model.check_schema(), archive_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
