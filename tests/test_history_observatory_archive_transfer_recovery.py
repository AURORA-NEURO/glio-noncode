# ruff: noqa: E501, I001

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_archive_transfer as transfer_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_archive_transfer_recovery as recovery_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_archive_transfer_recovery_audit as recovery_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_archive_transfer_recovery_query as recovery_query_model
from glio_noncode import history_observatory_archive_transfer_recovery_query_audit as recovery_query_audit_model
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit


class HistoryObservatoryArchiveTransferRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_downloaded_data_comparison_query_snapshot_registry_history_observatory import DownloadedDataComparisonQuerySnapshotRegistryHistoryObservatoryTests as observatory_tests

        observatory_tests.setUpClass()
        fixture = observatory_tests()
        history_left, history_right = fixture._histories()
        from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory as observatory_model

        cls.observatory = observatory_model.build_observatory((history_left, history_right), observatory_id="history-observatory-recovery-fixture")

    @classmethod
    def _transfer(cls):
        from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_archive as archive_model

        archive = archive_model.build_archive(cls.observatory, archive_id="history-observatory-recovery-fixture")
        return archive, transfer_model.build_transfer(archive, transfer_id="history-observatory-recovery-fixture", chunk_size=256)

    def test_complete_and_partial_recovery_audit_query(self):
        _, transfer = self._transfer()
        complete = recovery_model.build_recovery(transfer)
        assembler = transfer_model.TransferAssembler(transfer)
        payload = transfer.payload_bytes()
        assembler.add_chunk(0, payload[0])
        assembler.add_chunk(transfer.chunk_count - 1, payload[transfer.chunk_count - 1])
        partial = recovery_model.build_recovery(assembler, checkpointed=True)
        self.assertEqual((complete.state, complete.decision, complete.action_count), ("complete", "assemble", 0))
        self.assertEqual((partial.state, partial.decision, partial.action_count, partial.next_index, partial.checkpointed), ("partial", "resume", transfer.chunk_count - 2, 1, True))
        audit = recovery_audit_model.audit_recovery(partial)
        self.assertEqual((audit.check_count, audit.passed), (15, True))
        query = recovery_query_model.query_recovery(partial, resources=recovery_query_model.RESOURCES, limit=recovery_query_model.MAX_LIMIT)
        query_audit = recovery_query_audit_model.audit_query(query, partial)
        self.assertEqual((query.row_count, query_audit.check_count, query_audit.passed), (45, 12, True))
        self.assertEqual(recovery_model.recovery_from_mapping(json.loads(recovery_model.recovery_json(partial))).content_address, partial.content_address)
        self.assertEqual(recovery_audit_model.audit_from_mapping(json.loads(recovery_audit_model.audit_json(audit))).content_address, audit.content_address)
        self.assertEqual(recovery_query_model.query_from_mapping(json.loads(recovery_query_model.query_json(query))).content_address, query.content_address)

    def test_partial_directory_checkpoint_and_fail_closed_tamper(self):
        _, transfer = self._transfer()
        assembler = transfer_model.TransferAssembler(transfer)
        payload = transfer.payload_bytes()
        assembler.add_chunk(0, payload[0])
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "partial-transfer"
            transfer_model.write_partial_transfer(assembler, directory)
            recovery = recovery_model.build_recovery_from_directory(directory)
            self.assertTrue(recovery.checkpointed)
            self.assertEqual(recovery.missing_indices, tuple(range(1, transfer.chunk_count)))
            persisted = Path(temporary) / "recovery.json"
            persisted.write_text(recovery_model.recovery_json(recovery), encoding="utf-8")
            self.assertEqual(recovery_model.recovery_from_mapping(json.loads(persisted.read_text(encoding="utf-8"))).content_address, recovery.content_address)
        tampered = recovery.to_dict()
        tampered["next_index"] = tampered["next_index"] + 1
        with self.assertRaises(ValidationError):
            recovery_model.recovery_from_mapping(tampered)

    def test_cli_schemas_and_inventory(self):
        archive, _ = self._transfer()
        from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_archive as archive_model

        command = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-history-observatory-archive-transfer-recovery"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = root / "archive.zip"
            recovery_path = root / "recovery.json"
            query_path = root / "query.json"
            archive_model.write_archive(archive, archive_path)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([command, str(archive_path), "--format", "json", "--output", str(recovery_path)]), 0)
                self.assertEqual(main([command + "-verify", str(recovery_path), "--format", "summary"]), 0)
                self.assertEqual(main([command + "-audit", str(recovery_path), "--format", "summary"]), 0)
                self.assertEqual(main([command + "-query", str(recovery_path), "--resource", "summary", "--resource", "missing", "--limit", "8", "--format", "json", "--output", str(query_path)]), 0)
                self.assertEqual(main([command + "-query-audit", str(recovery_path), "--resource", "summary", "--resource", "missing", "--limit", "8", "--format", "summary"]), 0)
                for suffix in ("action-schema", "schema", "capabilities", "audit-check-schema", "audit-schema", "audit-capabilities", "query-row-schema", "query-schema", "query-capabilities", "query-audit-check-schema", "query-audit-schema", "query-audit-capabilities"):
                    self.assertEqual(main([command + "-" + suffix]), 0)
            self.assertGreater(json.loads(query_path.read_text(encoding="utf-8"))["row_count"], 0)
        inventory = build_default_public_surface_audit()
        self.assertTrue(inventory.accepted)
        self.assertEqual(len(inventory.checks), 1830)
        for schema in (recovery_model.action_schema(), recovery_model.recovery_schema(), recovery_audit_model.check_schema(), recovery_audit_model.audit_schema(), recovery_query_model.row_schema(), recovery_query_model.query_schema(), recovery_query_audit_model.check_schema(), recovery_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
