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

from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package as package_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry as registry_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history as history_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory as observatory_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive as archive_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_audit as archive_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_query as archive_query_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_query_audit as archive_query_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit
from tests import test_downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package as package_fixture_module


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        package_fixture_module.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageTests.setUpClass()
        runtime = package_fixture_module.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageTests.runtime
        package_a = package_model.build_package(runtime, package_id="archive-fixture-a")
        package_b = package_model.build_package(runtime, package_id="archive-fixture-b")
        registry_one = registry_model.build_registry((package_a,), registry_id="archive-fixture")
        registry_two = registry_model.build_registry((package_a, package_b), registry_id="archive-fixture")
        history_left = history_model.build_history((registry_one,), history_id="archive-history-left")
        history_right = history_model.build_history((registry_one, registry_two), history_id="archive-history-right")
        cls.observatory = observatory_model.build_observatory((history_left, history_right), observatory_id="archive-observatory")

    def test_deterministic_archive_round_trip_and_audit(self):
        value = archive_model.build_archive(self.observatory, archive_id="archive-fixture")
        duplicate = archive_model.build_archive(self.observatory, archive_id="archive-fixture")
        raw = archive_model.archive_bytes(value)
        self.assertEqual(raw, archive_model.archive_bytes(duplicate))
        loaded = archive_model.load_archive_bytes(raw)
        self.assertEqual(loaded.content_address, value.content_address)
        self.assertEqual(loaded.observatory_address, self.observatory.content_address)
        self.assertEqual(tuple(loaded.files), tuple(archive_model.ARCHIVE_PAYLOAD_FILES))
        audit = archive_audit_model.audit_archive(loaded)
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (16, 16, True))
        public = archive_model.archive_from_mapping(json.loads(archive_model.archive_json(value)))
        self.assertEqual(public.content_address, value.content_address)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "observatory.zip"
            archive_model.write_archive(value, destination)
            self.assertEqual(archive_model.load_archive(destination).content_address, value.content_address)
            with zipfile.ZipFile(destination, "r") as source:
                bad = Path(temporary) / "unexpected.zip"
                with zipfile.ZipFile(bad, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as target:
                    for info in source.infolist():
                        target.writestr(info, source.read(info.filename))
                    target.writestr("unexpected.json", b"{}")
            with self.assertRaises(ValidationError):
                archive_model.load_archive(bad)

    def test_cli_http_and_schema_surfaces(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            observatory = root / "observatory"
            archive = root / "observatory.zip"
            archive_json = root / "archive.json"
            observatory_model.persist_observatory(self.observatory, observatory)
            command = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([command, str(observatory), "--archive-id", "cli-archive", "--destination", str(archive), "--format", "json", "--output", str(archive_json)]), 0)
                self.assertEqual(main([command + "-audit", str(archive), "--format", "summary"]), 0)
            self.assertEqual(json.loads(archive_json.read_text(encoding="utf-8"))["archive_id"], "cli-archive")
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                endpoint = f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive"
                params = urlencode({"input": str(observatory), "archive_id": "api-archive", "destination": str(root / "api-observatory.zip"), "format": "json"})
                with urlopen(f"{endpoint}?{params}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["archive_id"], "api-archive")
                params = urlencode({"input": str(root / "api-observatory.zip"), "format": "json"})
                with urlopen(f"{endpoint}/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read())["accepted"])
                with urlopen(f"{endpoint}/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
        inventory = build_default_public_surface_audit()
        self.assertTrue(inventory.accepted)
        self.assertEqual(len(inventory.checks), 1984)
        for schema in (archive_model.artifact_schema(), archive_model.manifest_schema(), archive_model.archive_schema(), archive_audit_model.check_schema(), archive_audit_model.audit_schema(), archive_query_model.row_schema(), archive_query_model.query_schema(), archive_query_audit_model.check_schema(), archive_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")

    def test_bounded_archive_queries_round_trip_and_audit(self):
        value = archive_model.build_archive(self.observatory, archive_id="archive-query-fixture")
        query = archive_query_model.query_archive(value, resources=archive_query_model.RESOURCES, limit=archive_query_model.MAX_LIMIT)
        self.assertGreater(query.total_count, query.returned_count - 1)
        self.assertEqual(query.returned_count, query.matched_count)
        self.assertEqual(archive_query_model.address_query(query), query.content_address)
        audit = archive_query_audit_model.audit_query(query)
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (13, 13, True))
        self.assertEqual(archive_query_model.query_from_mapping(json.loads(archive_query_model.query_json(query))).content_address, query.content_address)
        self.assertIn("resource", archive_query_model.query_csv(query).splitlines()[0])
        self.assertIn("Policy Package Registry Observatory Archive Query", archive_query_model.render_query_markdown(query))
        filtered = archive_query_model.query_archive(value, resources=("files",), name="observatory/observatory.json", limit=8)
        self.assertEqual((filtered.total_count, filtered.matched_count, filtered.returned_count), (6, 1, 1))
        self.assertTrue(archive_query_audit_model.audit_query(filtered).accepted)

    def test_cli_http_query_surfaces_and_fail_closed_boundaries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            observatory = root / "observatory"
            archive = root / "observatory.zip"
            query_json = root / "query.json"
            observatory_model.persist_observatory(self.observatory, observatory)
            archive_model.write_archive(archive_model.build_archive_from_directory(observatory, archive_id="query-cli-archive"), archive)
            command = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-query"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([command, str(archive), "--resource", "files", "--name", "observatory/observatory.json", "--format", "json", "--output", str(query_json)]), 0)
                self.assertEqual(main([command + "-audit", str(query_json), "--format", "summary"]), 0)
            payload = json.loads(query_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["returned_count"], 1)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                endpoint = f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/query"
                params = urlencode({"input": str(archive), "resource": "files", "name": "observatory/observatory.json", "format": "json"})
                with urlopen(f"{endpoint}?{params}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["returned_count"], 1)
                params = urlencode({"input": str(query_json), "format": "json"})
                with urlopen(f"{endpoint}-audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read())["accepted"])
                for suffix in ("/row-schema", "/schema", "/capabilities"):
                    with urlopen(f"{endpoint}{suffix}", timeout=30) as response:
                        payload = json.loads(response.read())
                        self.assertEqual(payload["$schema"] if suffix != "/capabilities" else payload["version"], "https://json-schema.org/draft/2020-12/schema" if suffix != "/capabilities" else archive_query_model.VERSION)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
        with self.assertRaises(ValidationError):
            archive_query_model.query_archive(archive_model.build_archive(self.observatory, archive_id="query-boundary"), resources=("unknown",))

    def test_archive_boundaries_fail_closed(self):
        value = archive_model.build_archive(self.observatory, archive_id="archive-failure")
        with self.assertRaises(ValidationError):
            archive_model.load_archive_bytes(archive_model.archive_bytes(value)[:-1])
        with self.assertRaises(ValidationError):
            archive_model.archive_from_mapping(value.to_dict() | {"files": ("observatory/not-a-file.json",)})
        with self.assertRaises(ValidationError):
            archive_model.build_archive(self.observatory, archive_id="bad/archive")


if __name__ == "__main__":
    unittest.main()
