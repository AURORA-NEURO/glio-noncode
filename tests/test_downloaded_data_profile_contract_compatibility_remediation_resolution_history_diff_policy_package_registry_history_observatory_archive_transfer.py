# ruff: noqa: E501, I001

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory as observatory_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_archive as archive_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_archive_transfer as transfer_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_archive_transfer_audit as transfer_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_archive_transfer_query as transfer_query_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_archive_transfer_query_audit as transfer_query_audit_model
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryObservatoryArchiveTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_downloaded_data_comparison_query_snapshot_registry_history_observatory import DownloadedDataComparisonQuerySnapshotRegistryHistoryObservatoryTests as observatory_tests

        observatory_tests.setUpClass()
        fixture = observatory_tests()
        history_left, history_right = fixture._histories()
        cls.observatory = observatory_model.build_observatory((history_left, history_right), observatory_id="history-observatory-transfer-fixture")

    @classmethod
    def _transfer(cls):
        archive = archive_model.build_archive(cls.observatory, archive_id="history-observatory-transfer-fixture")
        return archive, transfer_model.build_transfer(archive, transfer_id="history-observatory-transfer-fixture", chunk_size=256)

    def test_transfer_audit_query_and_public_replay(self):
        archive, transfer = self._transfer()
        duplicate = transfer_model.build_transfer(archive, transfer_id=transfer.transfer_id, chunk_size=transfer.chunk_size)
        self.assertEqual(transfer_model.transfer_json(transfer), transfer_model.transfer_json(duplicate))
        self.assertEqual(transfer_model.assemble_archive_bytes(transfer), archive_model.archive_bytes(archive))
        self.assertTrue(transfer_model.verify_transfer(transfer))
        self.assertEqual((transfer.chunk_count, transfer.chunks[0].offset, transfer.chunks[-1].offset + transfer.chunks[-1].size), (22, 0, transfer.archive_size))
        transfer_audit = transfer_audit_model.audit_transfer(transfer)
        self.assertEqual((transfer_audit.check_count, transfer_audit.passed_count, transfer_audit.accepted), (16, 16, True))
        query = transfer_query_model.query_transfer(transfer, resources=transfer_query_model.RESOURCES, limit=transfer_query_model.MAX_LIMIT)
        self.assertGreater(query.returned_count, 0)
        query_audit = transfer_query_audit_model.audit_query(query, transfer)
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (12, 12, True))
        self.assertEqual(transfer_query_model.query_from_mapping(json.loads(transfer_query_model.query_json(query))).content_address, query.content_address)
        self.assertEqual(transfer_audit_model.audit_from_mapping(json.loads(transfer_audit_model.audit_json(transfer_audit))).content_address, transfer_audit.content_address)

    def test_partial_resume_persistence_and_fail_closed_assembly(self):
        archive, transfer = self._transfer()
        raw = transfer_model.assemble_archive_bytes(transfer)
        assembler = transfer_model.TransferAssembler(transfer)
        payload = transfer.payload_bytes()
        assembler.add_chunk(transfer.chunk_count - 1, payload[transfer.chunk_count - 1])
        assembler.add_chunk(0, payload[0])
        assembler.add_chunk(0, payload[0])
        self.assertEqual(assembler.progress().received_indices, (0, transfer.chunk_count - 1))
        with self.assertRaises(ValidationError):
            assembler.add_chunk(0, b"bad")
        with tempfile.TemporaryDirectory() as temporary:
            partial = Path(temporary) / "partial-transfer"
            complete = Path(temporary) / "complete-transfer"
            transfer_model.write_partial_transfer(assembler, partial)
            self.assertEqual(transfer_model.verify_partial_transfer(partial).received_indices, (0, transfer.chunk_count - 1))
            loaded_partial = transfer_model.load_partial_transfer(partial)
            loaded_partial.add_chunks(payload)
            self.assertEqual(loaded_partial.finalize(), raw)
            loaded_partial.write_partial(complete)
            self.assertEqual(transfer_model.assemble_transfer_directory(complete), raw)
            self.assertEqual(transfer_model.load_transfer(complete).content_address, transfer.content_address)
        self.assertEqual(archive_model.load_archive_bytes(raw).content_address, archive.content_address)

    def test_cli_schemas_and_public_inventory(self):
        archive, _ = self._transfer()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = root / "archive.zip"
            transfer_path = root / "transfer"
            command = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-history-observatory-archive"
            transfer_command = command + "-transfer"
            archive_model.write_archive(archive, archive_path)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([transfer_command, str(archive_path), "--transfer-id", "cli-transfer", "--chunk-size", "256", "--destination", str(transfer_path), "--format", "summary"]), 0)
                self.assertEqual(main([transfer_command + "-verify", str(transfer_path), "--format", "summary"]), 0)
                self.assertEqual(main([transfer_command + "-audit", str(transfer_path), "--format", "summary"]), 0)
                self.assertEqual(main([transfer_command + "-query", str(transfer_path), "--resource", "summary", "--resource", "missing", "--limit", "8", "--format", "json", "--output", str(root / "query.json")]), 0)
                self.assertEqual(main([transfer_command + "-query-audit", str(transfer_path), "--resource", "summary", "--resource", "missing", "--limit", "8", "--format", "summary"]), 0)
                for suffix in ("chunk-schema", "schema", "manifest-schema", "progress-schema", "capabilities", "audit-check-schema", "audit-schema", "audit-capabilities", "query-row-schema", "query-schema", "query-capabilities", "query-audit-check-schema", "query-audit-schema", "query-audit-capabilities"):
                    self.assertEqual(main([transfer_command + "-" + suffix]), 0)
            self.assertGreater(json.loads((root / "query.json").read_text(encoding="utf-8"))["returned_count"], 0)
        inventory = build_default_public_surface_audit()
        self.assertTrue(inventory.accepted)
        self.assertEqual(len(inventory.checks), 1684)
        for schema in (transfer_model.chunk_schema(), transfer_model.transfer_schema(), transfer_model.manifest_schema(), transfer_model.progress_schema(), transfer_audit_model.check_schema(), transfer_audit_model.audit_schema(), transfer_query_model.row_schema(), transfer_query_model.query_schema(), transfer_query_audit_model.check_schema(), transfer_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
