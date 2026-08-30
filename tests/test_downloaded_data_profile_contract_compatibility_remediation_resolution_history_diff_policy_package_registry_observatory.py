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

from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory as observatory_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_audit as observatory_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_query as observatory_query_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_query_audit as observatory_query_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package as package_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history as history_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry as registry_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit
from tests import test_downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package as package_fixture_module


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        package_fixture_module.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageTests.setUpClass()
        runtime = package_fixture_module.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageTests.runtime
        package_a = package_model.build_package(runtime, package_id="observatory-package-a")
        package_b = package_model.build_package(runtime, package_id="observatory-package-b")
        registry_one = registry_model.build_registry((package_a,), registry_id="observatory-fixture")
        registry_two = registry_model.build_registry((package_a, package_b), registry_id="observatory-fixture")
        cls.history_left = history_model.build_history((registry_one,), history_id="observatory-history-left")
        cls.history_right = history_model.build_history((registry_one, registry_two), history_id="observatory-history-right")
        cls.observatory = observatory_model.build_observatory((cls.history_left, cls.history_right), observatory_id="observatory-fixture")

    def test_observatory_audit_query_and_exact_reload(self):
        value = self.observatory
        self.assertEqual((value.member_count, value.transition_count, value.state, value.decision, value.accepted, value.release_ready), (2, 3, "ready", "promote", True, True))
        self.assertEqual(tuple(sorted(value.manifest.files)), tuple(sorted(observatory_model.FILES)))
        audit = observatory_audit_model.audit_observatory(value)
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (16, 16, True))
        query = observatory_query_model.query_observatory(value, resources=observatory_query_model.RESOURCES, transition="improved")
        self.assertEqual((query.total_count, query.matched_count, query.returned_count), (10, 1, 1))
        self.assertTrue(observatory_query_audit_model.audit_query(query).accepted)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "observatory"
            observatory_model.persist_observatory(value, destination)
            self.assertEqual(observatory_model.load_observatory(destination).content_address, value.content_address)
            self.assertEqual(tuple(sorted(item.name for item in destination.iterdir())), tuple(sorted(observatory_model.FILES)))
            (destination / "summary.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                observatory_model.load_observatory(destination)

    def test_cli_http_schemas_and_public_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            history_left = root / "history-left"
            history_right = root / "history-right"
            observatory = root / "observatory"
            query = root / "query.json"
            history_model.persist_history(self.history_left, history_left)
            history_model.persist_history(self.history_right, history_right)
            command = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory"
            audit_command = command + "-audit"
            query_command = command + "-query"
            query_audit_command = query_command + "-audit"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([command, str(history_left), str(history_right), "--observatory-id", "cli-observatory", "--destination", str(observatory), "--format", "summary"]), 0)
                self.assertEqual(main([audit_command, str(observatory), "--format", "summary"]), 0)
                self.assertEqual(main([query_command, str(observatory), "--resource", "transitions", "--transition", "improved", "--format", "json", "--output", str(query)]), 0)
                self.assertEqual(main([query_audit_command, str(query), "--format", "summary"]), 0)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                endpoint = f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory"
                params = urlencode([("input", str(history_left)), ("input", str(history_right)), ("destination", str(root / "observatory-api")), ("format", "json")])
                with urlopen(f"{endpoint}?{params}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["member_count"], 2)
                params = urlencode({"input": str(observatory), "resource": "transitions", "transition": "improved", "format": "json"})
                with urlopen(f"{endpoint}/query?{params}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["returned_count"], 1)
                with urlopen(f"{endpoint}/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
        inventory = build_default_public_surface_audit()
        self.assertTrue(inventory.accepted)
        self.assertEqual(len(inventory.checks), 1502)
        schemas = (observatory_model.member_schema(), observatory_model.members_schema(), observatory_model.transition_schema(), observatory_model.transitions_schema(), observatory_model.manifest_schema(), observatory_model.summary_schema(), observatory_model.observatory_schema(), observatory_audit_model.check_schema(), observatory_audit_model.audit_schema(), observatory_query_model.row_schema(), observatory_query_model.query_schema(), observatory_query_audit_model.check_schema(), observatory_query_audit_model.audit_schema())
        for schema in schemas:
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")

    def test_duplicate_identity_tamper_and_query_boundaries_fail_closed(self):
        with self.assertRaises(ValidationError):
            observatory_model.build_observatory((self.history_left, self.history_left))
        with self.assertRaises(ValidationError):
            observatory_query_model.query_observatory(self.observatory, resources=("not-a-resource",))
        with self.assertRaises(ValidationError):
            observatory_model.observatory_from_mapping(self.observatory.to_dict() | {"member_count": 0})
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "observatory"
            observatory_model.persist_observatory(self.observatory, destination)
            (destination / "unexpected.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                observatory_model.load_observatory(destination)


if __name__ == "__main__":
    unittest.main()
