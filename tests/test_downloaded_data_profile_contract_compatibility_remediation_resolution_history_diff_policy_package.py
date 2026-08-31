# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package as package_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_audit as package_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_query as package_query_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_query_audit as package_query_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_runtime as runtime_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit
from tests import test_downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy as policy_fixture_module


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        policy_fixture_module.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyTests.setUpClass()
        fixture = policy_fixture_module.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyTests
        cls.runtime = runtime_model.build_runtime(fixture.value, runtime_id="package-fixture-runtime")

    def test_package_builds_complete_and_audits_independently(self):
        package = package_model.build_package(self.runtime, package_id="package-fixture")
        self.assertTrue(package.accepted)
        self.assertTrue(package.release_ready)
        self.assertEqual(package.manifest.files, ("manifest.json", "runtime.json", "policy-audit.json", "runtime-audit.json", "summary.json"))
        package_audit = package_audit_model.audit_package(package)
        self.assertEqual((package_audit.check_count, package_audit.passed_count, package_audit.accepted), (14, 14, True))
        query = package_query_model.query_package(package, resources=("summary", "policy-rules"), text="removed-limit")
        self.assertEqual((query.total_count, query.matched_count, query.returned_count), (11, 1, 1))
        query_audit = package_query_audit_model.audit_query(query)
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (10, 10, True))

    def test_persistence_is_exact_and_tamper_evident(self):
        package = package_model.build_package(self.runtime, package_id="package-persistence")
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "package"
            package_model.persist_package(package, destination)
            self.assertEqual(tuple(sorted(path.name for path in destination.iterdir())), tuple(sorted(package_model.FILES)))
            loaded = package_model.load_package(destination)
            self.assertEqual(loaded.content_address, package.content_address)
            (destination / "summary.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                package_model.load_package(destination)

    def test_cli_http_schemas_and_public_inventory_expose_package_surfaces(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime_dir = root / "runtime"
            package_dir = root / "package"
            query_path = root / "query.json"
            runtime_model.persist_runtime(self.runtime, runtime_dir)
            self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package", str(runtime_dir), "--destination", str(package_dir), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-audit", str(package_dir), "--format", "json"]), 0)
            self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-query", str(package_dir), "--resource", "policy-rules", "--text", "removed-limit", "--format", "json", "--output", str(query_path)]), 0)
            self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-query-audit", str(query_path), "--format", "json"]), 0)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                package_params = urlencode({"input": str(runtime_dir), "destination": str(root / "http-package"), "format": "summary"})
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package?{package_params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read())["release_ready"])
                params = urlencode({"input": str(package_dir), "resource": "policy-rules", "text": "removed-limit", "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/query?{params}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["returned_count"], 1)
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/query-audit?{urlencode({'input': str(query_path), 'format': 'json'})}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read())["accepted"])
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
        inventory = build_default_public_surface_audit()
        self.assertTrue(inventory.accepted)
        self.assertEqual(len(inventory.checks), 1658)
        for schema in (package_model.manifest_schema(), package_model.summary_schema(), package_model.package_schema(), package_audit_model.check_schema(), package_audit_model.audit_schema(), package_query_model.row_schema(), package_query_model.query_schema(), package_query_audit_model.check_schema(), package_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
