# ruff: noqa: E501, I001

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory as observatory_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_archive as archive_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_archive_audit as archive_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_archive_query as archive_query_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_archive_query_audit as archive_query_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit

class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryObservatoryArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_downloaded_data_comparison_query_snapshot_registry_history_observatory import DownloadedDataComparisonQuerySnapshotRegistryHistoryObservatoryTests as observatory_tests

        observatory_tests.setUpClass()
        fixture = observatory_tests()
        history_left, history_right = fixture._histories()
        cls.observatory = observatory_model.build_observatory((history_left, history_right), observatory_id="history-observatory-archive-fixture")

    def test_deterministic_archive_audit_query_and_replay(self):
        value = archive_model.build_archive(self.observatory, archive_id="history-observatory-archive-fixture")
        duplicate = archive_model.build_archive(self.observatory, archive_id="history-observatory-archive-fixture")
        raw = archive_model.archive_bytes(value)
        self.assertEqual(raw, archive_model.archive_bytes(duplicate))
        loaded = archive_model.load_archive_bytes(raw)
        self.assertEqual(loaded.content_address, value.content_address)
        self.assertEqual(tuple(loaded.files), tuple(archive_model.ARCHIVE_PAYLOAD_FILES))
        self.assertTrue(archive_model.verify_archive(loaded))
        archive_audit = archive_audit_model.audit_archive(loaded)
        self.assertEqual((archive_audit.check_count, archive_audit.passed_count, archive_audit.accepted), (17, 17, True))
        query = archive_query_model.query_archive(loaded, resources=archive_query_model.RESOURCES, accepted=True, limit=archive_query_model.MAX_LIMIT)
        self.assertGreater(query.returned_count, 0)
        self.assertTrue(archive_query_audit_model.audit_query(query, loaded).accepted)
        public = archive_model.archive_from_mapping(json.loads(archive_model.archive_json(value)))
        self.assertEqual(public.content_address, value.content_address)
        self.assertEqual(json.loads(archive_model.archive_json(public))["archive_id"], value.archive_id)

    def test_archive_file_transport_and_fail_closed_boundaries(self):
        value = archive_model.build_archive(self.observatory, archive_id="history-observatory-archive-failure")
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "observatory.zip"
            archive_model.write_archive(value, destination)
            self.assertEqual(archive_model.load_archive(destination).content_address, value.content_address)
            self.assertEqual(archive_model.verify_archive_file(destination).content_address, value.content_address)
            with self.assertRaises(ValidationError):
                archive_model.load_archive_bytes(archive_model.archive_bytes(value)[:-1])
            (Path(temporary) / "not-a-zip.txt").write_text("nope", encoding="utf-8")
            with self.assertRaises(ValidationError):
                archive_model.load_archive(Path(temporary) / "not-a-zip.txt")
        with self.assertRaises(ValidationError):
            archive_model.build_archive(self.observatory, archive_id="bad/archive")

    def test_cli_http_schemas_and_public_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            observatory = root / "observatory"
            archive = root / "observatory.zip"
            query_json = root / "query.json"
            observatory_model.persist_observatory(self.observatory, observatory)
            command = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-history-observatory-archive"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([command, str(observatory), "--archive-id", "cli-history-archive", "--destination", str(archive), "--format", "summary"]), 0)
                self.assertEqual(main([command + "-verify", str(archive), "--format", "summary"]), 0)
                self.assertEqual(main([command + "-audit", str(archive), "--format", "summary"]), 0)
                self.assertEqual(main([command + "-query", str(archive), "--resource", "summary", "--resource", "histories", "--accepted", "true", "--format", "json", "--output", str(query_json)]), 0)
                self.assertEqual(main([command + "-query-audit", str(archive), "--resource", "summary", "--resource", "histories", "--accepted", "true", "--format", "summary"]), 0)
                self.assertEqual(main([command + "-manifest", str(archive), "--output", str(root / "manifest.json")]), 0)
            self.assertEqual(json.loads(query_json.read_text(encoding="utf-8"))["returned_count"], 3)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                endpoint = f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/query-snapshot/registry/history/observatory/archive"
                params = urlencode({"input": str(observatory), "archive_id": "api-history-archive", "destination": str(root / "api-observatory.zip"), "format": "json"})
                with urlopen(f"{endpoint}?{params}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["archive_id"], "api-history-archive")
                params = urlencode({"input": str(root / "api-observatory.zip"), "format": "json"})
                with urlopen(f"{endpoint}/verify?{params}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["archive_id"], "api-history-archive")
                with urlopen(f"{endpoint}/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read())["accepted"])
                params = urlencode([("input", str(root / "api-observatory.zip")), ("resource", "summary"), ("resource", "histories"), ("accepted", "true"), ("format", "json")])
                with urlopen(f"{endpoint}/query?{params}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["returned_count"], 3)
                with urlopen(f"{endpoint}/query/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read())["accepted"])
                with urlopen(f"{endpoint}/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
        inventory = build_default_public_surface_audit()
        self.assertTrue(inventory.accepted)
        self.assertEqual(len(inventory.checks), 1575)
        for schema in (archive_model.artifact_schema(), archive_model.manifest_schema(), archive_model.archive_schema(), archive_audit_model.check_schema(), archive_audit_model.audit_schema(), archive_query_model.row_schema(), archive_query_model.query_schema(), archive_query_audit_model.check_schema(), archive_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
