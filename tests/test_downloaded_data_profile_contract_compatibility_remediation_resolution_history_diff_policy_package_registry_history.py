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
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history as history_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history_audit as history_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history_query as history_query_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history_query_audit as history_query_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history_diff as diff_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history_diff_audit as diff_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history_diff_query as diff_query_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history_diff_query_audit as diff_query_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit
from tests import test_downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package as package_fixture_module


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        package_fixture_module.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageTests.setUpClass()
        runtime = package_fixture_module.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageTests.runtime
        cls.package_a = package_model.build_package(runtime, package_id="history-fixture-a")
        cls.package_b = package_model.build_package(runtime, package_id="history-fixture-b")
        cls.registry_one = registry_model.build_registry((cls.package_a,), registry_id="history-fixture")
        cls.registry_two = registry_model.build_registry((cls.package_a, cls.package_b), registry_id="history-fixture")
        cls.history_left = history_model.build_history((cls.registry_one,), history_id="history-fixture")
        cls.history_right = history_model.build_history((cls.registry_one, cls.registry_two), history_id="history-fixture")

    def test_history_audit_query_and_exact_reload(self):
        value = self.history_right
        self.assertEqual((value.state, value.entry_count, value.initial_count, value.improved_count), ("ready", 2, 1, 1))
        self.assertEqual(tuple(sorted(value.manifest.files)), tuple(sorted(history_model.FILES)))
        audit = history_audit_model.audit_history(value)
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (15, 15, True))
        query = history_query_model.query_history(value, resources=history_query_model.RESOURCES, transition="improved")
        self.assertEqual((query.total_count, query.matched_count, query.returned_count), (9, 5, 5))
        self.assertTrue(history_query_audit_model.audit_query(query).accepted)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "history"
            history_model.persist_history(value, destination)
            self.assertEqual(history_model.load_history(destination).content_address, value.content_address)
            (destination / "summary.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                history_model.load_history(destination)

    def test_diff_audit_query_and_exact_reload(self):
        value = diff_model.build_diff(self.history_left, self.history_right, diff_id="history-diff-fixture")
        self.assertEqual((value.direction, value.added_count, value.removed_count, value.changed_count, value.unchanged_count), ("improved", 1, 0, 0, 1))
        audit = diff_audit_model.audit_diff(value)
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (14, 14, True))
        query = diff_query_model.query_diff(value, resources=diff_query_model.RESOURCES, change="added")
        self.assertEqual((query.total_count, query.matched_count, query.returned_count), (5, 2, 2))
        self.assertTrue(diff_query_audit_model.audit_query(query).accepted)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "diff"
            diff_model.persist_diff(value, destination)
            self.assertEqual(diff_model.load_diff(destination).content_address, value.content_address)
            (destination / "items.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                diff_model.load_diff(destination)

    def test_cli_http_schemas_and_public_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry_one = root / "registry-one"
            registry_two = root / "registry-two"
            history_left = root / "history-left"
            history_right = root / "history-right"
            diff = root / "diff"
            query = root / "query.json"
            history_query = root / "history-query.json"
            registry_model.persist_registry(self.registry_one, registry_one)
            registry_model.persist_registry(self.registry_two, registry_two)
            history_model.persist_history(self.history_left, history_left)
            history_model.persist_history(self.history_right, history_right)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-history", str(registry_one), str(registry_two), "--history-id", "history-cli", "--destination", str(root / "history-cli"), "--format", "summary"]), 0)
                self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-history-audit", str(root / "history-cli"), "--format", "summary"]), 0)
                self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-history-query", str(root / "history-cli"), "--resource", "transitions", "--transition", "improved", "--format", "json", "--output", str(history_query)]), 0)
                self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-history-query-audit", str(history_query), "--format", "summary"]), 0)
                self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-history-diff", str(history_left), str(history_right), "--diff-id", "diff-cli", "--destination", str(diff), "--format", "summary"]), 0)
                self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-history-diff-audit", str(diff), "--format", "summary"]), 0)
                self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-history-diff-query", str(diff), "--resource", "added", "--change", "added", "--format", "json", "--output", str(query)]), 0)
                self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-history-diff-query-audit", str(query), "--format", "summary"]), 0)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                params = urlencode({"input": str(history_right), "resource": "transitions", "transition": "improved", "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/history/query?{params}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["returned_count"], 1)
                params = urlencode({"left": str(history_left), "right": str(history_right), "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/history/diff?{params}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["direction"], "improved")
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/history/diff/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
        inventory = build_default_public_surface_audit()
        self.assertTrue(inventory.accepted)
        self.assertEqual(len(inventory.checks), 1830)
        for schema in (history_model.entry_schema(), history_model.entries_schema(), history_model.manifest_schema(), history_model.summary_schema(), history_model.history_schema(), history_audit_model.check_schema(), history_audit_model.audit_schema(), history_query_model.row_schema(), history_query_model.query_schema(), history_query_audit_model.check_schema(), history_query_audit_model.audit_schema(), diff_model.item_schema(), diff_model.items_schema(), diff_model.manifest_schema(), diff_model.summary_schema(), diff_model.diff_schema(), diff_audit_model.check_schema(), diff_audit_model.audit_schema(), diff_query_model.row_schema(), diff_query_model.query_schema(), diff_query_audit_model.check_schema(), diff_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
