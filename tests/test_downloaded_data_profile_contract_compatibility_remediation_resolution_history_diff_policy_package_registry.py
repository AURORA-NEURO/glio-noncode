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

from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package as package_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry as registry_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_audit as registry_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_query as registry_query_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_query_audit as registry_query_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit
from tests import test_downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package as package_fixture_module


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        package_fixture_module.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageTests.setUpClass()
        cls.runtime = package_fixture_module.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageTests.runtime
        cls.package_a = package_model.build_package(cls.runtime, package_id="registry-fixture-a")
        cls.package_b = package_model.build_package(cls.runtime, package_id="registry-fixture-b")

    def test_registry_admits_multiple_packages_and_folds_state(self):
        registry = registry_model.build_registry((self.package_b, self.package_a), registry_id="registry-fixture")
        self.assertEqual((registry.state, registry.entry_count, registry.accepted_count, registry.release_ready_count, registry.promote_count, registry.hold_count, registry.block_count), ("ready", 2, 2, 2, 2, 0, 0))
        self.assertEqual([item.package_id for item in registry.entries], ["registry-fixture-a", "registry-fixture-b"])
        audit = registry_audit_model.audit_registry(registry)
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (15, 15, True))
        query = registry_query_model.query_registry(registry, resources=("summary", "entries", "ready", "decisions"), decision="promote")
        self.assertEqual((query.total_count, query.matched_count, query.returned_count), (7, 7, 7))
        query_audit = registry_query_audit_model.audit_query(query)
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (10, 10, True))

    def test_exact_persistence_reload_and_tamper_rejection(self):
        registry = registry_model.build_registry((self.package_a, self.package_b), registry_id="registry-persistence")
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "registry"
            registry_model.persist_registry(registry, destination)
            self.assertEqual(tuple(sorted(path.name for path in destination.iterdir())), tuple(sorted(registry_model.FILES)))
            self.assertEqual(registry_model.load_registry(destination).content_address, registry.content_address)
            (destination / "summary.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                registry_model.load_registry(destination)

    def test_cli_http_schemas_and_public_inventory_expose_registry(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package_a_dir = root / "package-a"
            package_b_dir = root / "package-b"
            registry_dir = root / "registry"
            query_path = root / "query.json"
            package_model.persist_package(self.package_a, package_a_dir)
            package_model.persist_package(self.package_b, package_b_dir)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry", str(package_a_dir), str(package_b_dir), "--registry-id", "registry-cli", "--destination", str(registry_dir), "--format", "summary"]), 0)
                self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-audit", str(registry_dir), "--format", "summary"]), 0)
                self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-query", str(registry_dir), "--resource", "entries", "--decision", "promote", "--format", "json", "--output", str(query_path)]), 0)
                self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-query-audit", str(query_path), "--format", "summary"]), 0)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                params = urlencode({"input": str(registry_dir), "resource": "entries", "decision": "promote", "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/query?{params}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["returned_count"], 2)
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
        inventory = build_default_public_surface_audit()
        self.assertTrue(inventory.accepted)
        self.assertEqual(len(inventory.checks), 1736)
        for schema in (registry_model.manifest_schema(), registry_model.entry_schema(), registry_model.summary_schema(), registry_model.registry_schema(), registry_audit_model.check_schema(), registry_audit_model.audit_schema(), registry_query_model.row_schema(), registry_query_model.query_schema(), registry_query_audit_model.check_schema(), registry_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
