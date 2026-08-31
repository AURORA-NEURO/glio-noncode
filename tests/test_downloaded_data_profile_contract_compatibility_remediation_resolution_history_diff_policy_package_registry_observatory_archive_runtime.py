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

from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive as archive_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime as runtime_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_audit as runtime_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query as runtime_query_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_audit as runtime_query_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot as runtime_query_snapshot_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_audit as runtime_query_snapshot_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff as runtime_query_snapshot_diff_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_audit as runtime_query_snapshot_diff_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query as runtime_query_snapshot_diff_query_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_audit as runtime_query_snapshot_diff_query_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot as runtime_query_snapshot_diff_query_snapshot_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_audit as runtime_query_snapshot_diff_query_snapshot_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff as runtime_query_snapshot_diff_query_snapshot_diff_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_audit as runtime_query_snapshot_diff_query_snapshot_diff_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query as runtime_query_snapshot_diff_query_snapshot_diff_query_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_audit as runtime_query_snapshot_diff_query_snapshot_diff_query_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot as runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_audit as runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit
from tests import test_downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive as archive_fixture_module


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        archive_fixture_module.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveTests.setUpClass()
        cls.observatory = archive_fixture_module.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveTests.observatory

    def test_runtime_composes_stages_and_reloads_exactly(self):
        archive = archive_model.build_archive(self.observatory, archive_id="runtime-fixture")
        value = runtime_model.build_runtime(archive, runtime_id="runtime-fixture")
        audit = runtime_audit_model.audit_runtime(value)
        self.assertEqual((value.stage_count, value.state, value.accepted), (6, "ready", True))
        self.assertEqual(tuple(item.stage for item in value.stages), runtime_model.STAGES)
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (15, 15, True))
        self.assertEqual(runtime_model.runtime_from_mapping(json.loads(runtime_model.runtime_json(value))).content_address, value.content_address)
        self.assertIn("runtime_id", runtime_model.runtime_csv(value).splitlines()[0])
        self.assertIn("Policy Package Registry Observatory Archive Runtime", runtime_model.render_runtime_markdown(value))
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "runtime"
            runtime_model.persist_runtime(value, destination)
            loaded = runtime_model.load_runtime(destination)
            self.assertEqual(loaded.content_address, value.content_address)
            self.assertEqual(runtime_audit_model.audit_runtime(loaded).accepted, True)
            self.assertEqual(tuple(sorted(item.name for item in destination.iterdir())), tuple(sorted(runtime_model.FILES)))

    def test_runtime_cli_http_schemas_and_tamper_rejection(self):
        archive = archive_model.build_archive(self.observatory, archive_id="runtime-interface")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = root / "observatory.zip"
            runtime_path = root / "runtime"
            runtime_json = root / "runtime.json"
            archive_model.write_archive(archive, archive_path)
            command = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([command, str(archive_path), "--runtime-id", "runtime-cli", "--destination", str(runtime_path), "--format", "json", "--output", str(runtime_json)]), 0)
                self.assertEqual(main([command + "-audit", str(runtime_path), "--format", "summary"]), 0)
                snapshot_command = command + "-query-snapshot"
                snapshot_path = root / "runtime-query-snapshot"
                snapshot_json = root / "runtime-query-snapshot.json"
                self.assertEqual(main([snapshot_command, str(runtime_path), "--snapshot-id", "snapshot-cli", "--destination", str(snapshot_path), "--format", "json", "--output", str(snapshot_json)]), 0)
                self.assertEqual(main([snapshot_command + "-audit", str(snapshot_path), "--format", "summary"]), 0)
                candidate_snapshot_path = root / "runtime-query-snapshot-candidate"
                self.assertEqual(main([snapshot_command, str(runtime_path), "--snapshot-id", "snapshot-cli-candidate", "--resource", "components", "--component", "query", "--destination", str(candidate_snapshot_path), "--format", "summary"]), 0)
                snapshot_diff_command = snapshot_command + "-diff"
                snapshot_diff_path = root / "runtime-query-snapshot-diff"
                snapshot_diff_json = root / "runtime-query-snapshot-diff.json"
                self.assertEqual(main([snapshot_diff_command, str(snapshot_path), str(candidate_snapshot_path), "--diff-id", "snapshot-diff-cli", "--destination", str(snapshot_diff_path), "--format", "json", "--output", str(snapshot_diff_json)]), 0)
                self.assertEqual(main([snapshot_diff_command + "-audit", str(snapshot_diff_path), "--format", "summary"]), 0)
                snapshot_diff_query_command = snapshot_diff_command + "-query"
                snapshot_diff_query_json = root / "runtime-query-snapshot-diff-query.json"
                self.assertEqual(main([snapshot_diff_query_command, str(snapshot_diff_path), "--resource", "changed", "--format", "json", "--output", str(snapshot_diff_query_json)]), 0)
                self.assertEqual(main([snapshot_diff_query_command + "-audit", str(snapshot_diff_query_json), "--format", "summary"]), 0)
                snapshot_diff_query_snapshot_command = snapshot_diff_query_command + "-snapshot"
                snapshot_diff_query_snapshot_path = root / "runtime-query-snapshot-diff-query-snapshot"
                snapshot_diff_query_snapshot_json = root / "runtime-query-snapshot-diff-query-snapshot.json"
                self.assertEqual(main([snapshot_diff_query_snapshot_command, str(snapshot_diff_path), "--snapshot-id", "query-snapshot-cli", "--resource", "changed", "--change", "changed", "--destination", str(snapshot_diff_query_snapshot_path), "--format", "json", "--output", str(snapshot_diff_query_snapshot_json)]), 0)
                self.assertEqual(main([snapshot_diff_query_snapshot_command + "-audit", str(snapshot_diff_query_snapshot_path), "--format", "summary"]), 0)
                comparison_command = snapshot_diff_query_snapshot_command + "-diff"
                comparison_path = root / "runtime-query-snapshot-diff-query-snapshot-diff"
                comparison_json = root / "runtime-query-snapshot-diff-query-snapshot-diff.json"
                self.assertEqual(main([comparison_command, str(snapshot_diff_query_snapshot_path), str(snapshot_diff_query_snapshot_path), "--diff-id", "query-snapshot-diff-cli", "--destination", str(comparison_path), "--format", "json", "--output", str(comparison_json)]), 0)
                self.assertEqual(main([comparison_command + "-audit", str(comparison_path), "--format", "summary"]), 0)
            self.assertEqual(json.loads(runtime_json.read_text(encoding="utf-8"))["state"], "ready")
            self.assertEqual((json.loads(snapshot_json.read_text(encoding="utf-8"))["query_returned_count"], json.loads(snapshot_json.read_text(encoding="utf-8"))["accepted"]), (21, True))
            self.assertEqual((json.loads(snapshot_diff_json.read_text(encoding="utf-8"))["removed_count"], json.loads(snapshot_diff_json.read_text(encoding="utf-8"))["changed_count"]), (20, 1))
            self.assertEqual((json.loads(snapshot_diff_query_json.read_text(encoding="utf-8"))["matched_count"], json.loads(snapshot_diff_query_json.read_text(encoding="utf-8"))["rows"][0]["change"]), (1, "changed"))
            self.assertEqual((json.loads(snapshot_diff_query_snapshot_json.read_text(encoding="utf-8"))["query_returned_count"], json.loads(snapshot_diff_query_snapshot_json.read_text(encoding="utf-8"))["accepted"]), (1, True))
            self.assertEqual((json.loads(comparison_json.read_text(encoding="utf-8"))["unchanged_count"], json.loads(comparison_json.read_text(encoding="utf-8"))["changed_count"]), (1, 0))
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                endpoint = f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime"
                params = urlencode({"input": str(archive_path), "runtime_id": "runtime-api", "destination": str(root / "api-runtime"), "format": "json"})
                with urlopen(f"{endpoint}?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read())["accepted"])
                params = urlencode({"input": str(runtime_path), "format": "json"})
                with urlopen(f"{endpoint}/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read())["accepted"])
                query_endpoint = endpoint + "/query"
                params = urlencode({"input": str(runtime_path), "resource": "components", "component": "query", "format": "json"})
                with urlopen(f"{query_endpoint}?{params}", timeout=30) as response:
                    query_payload = json.loads(response.read())
                    self.assertEqual((query_payload["returned_count"], query_payload["rows"][0]["component"]), (1, "query"))
                query_path = root / "runtime-query.json"
                query_path.write_text(json.dumps(query_payload), encoding="utf-8")
                params = urlencode({"input": str(query_path), "format": "json"})
                with urlopen(f"{endpoint}/query-audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read())["accepted"])
                snapshot_endpoint = endpoint + "/query-snapshot"
                params = urlencode({"input": str(root / "api-runtime"), "snapshot_id": "snapshot-api", "resource": "components", "component": "query", "destination": str(root / "api-snapshot"), "format": "json"})
                with urlopen(f"{snapshot_endpoint}?{params}", timeout=30) as response:
                    snapshot_payload = json.loads(response.read())
                    self.assertEqual((snapshot_payload["query_returned_count"], snapshot_payload["accepted"]), (1, True))
                params = urlencode({"input": str(root / "api-snapshot"), "format": "json"})
                with urlopen(f"{snapshot_endpoint}/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read())["accepted"])
                snapshot_diff_endpoint = snapshot_endpoint + "/diff"
                params = urlencode({"left": str(snapshot_path), "right": str(root / "api-snapshot"), "diff_id": "snapshot-diff-api", "destination": str(root / "api-snapshot-diff"), "format": "json"})
                with urlopen(f"{snapshot_diff_endpoint}?{params}", timeout=30) as response:
                    diff_payload = json.loads(response.read())
                    self.assertEqual((diff_payload["removed_count"], diff_payload["changed_count"]), (20, 1))
                params = urlencode({"input": str(root / "api-snapshot-diff"), "format": "json"})
                with urlopen(f"{snapshot_diff_endpoint}/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read())["accepted"])
                snapshot_diff_query_endpoint = snapshot_diff_endpoint + "/query"
                params = urlencode({"input": str(root / "api-snapshot-diff"), "resource": "field-changes", "field": "component", "format": "json"})
                with urlopen(f"{snapshot_diff_query_endpoint}?{params}", timeout=30) as response:
                    query_payload = json.loads(response.read())
                    self.assertEqual((query_payload["matched_count"], query_payload["rows"][0]["resource"], query_payload["rows"][0]["field"]), (20, "field-changes", "component"))
                query_path = root / "snapshot-diff-query.json"
                query_path.write_text(json.dumps(query_payload), encoding="utf-8")
                params = urlencode({"input": str(query_path), "format": "json"})
                with urlopen(f"{snapshot_diff_endpoint}/query-audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read())["accepted"])
                query_snapshot_endpoint = snapshot_diff_endpoint + "/query-snapshot"
                params = urlencode({"input": str(root / "api-snapshot-diff"), "snapshot_id": "query-snapshot-api", "resource": "changed", "change": "changed", "destination": str(root / "api-query-snapshot"), "format": "json"})
                with urlopen(f"{query_snapshot_endpoint}?{params}", timeout=30) as response:
                    query_snapshot_payload = json.loads(response.read())
                    self.assertEqual((query_snapshot_payload["query_returned_count"], query_snapshot_payload["accepted"]), (1, True))
                params = urlencode({"input": str(root / "api-query-snapshot"), "format": "json"})
                with urlopen(f"{query_snapshot_endpoint}/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read())["accepted"])
                comparison_endpoint = query_snapshot_endpoint + "/diff"
                params = urlencode({"left": str(root / "api-query-snapshot"), "right": str(root / "api-query-snapshot"), "diff_id": "query-snapshot-diff-api", "destination": str(root / "api-query-snapshot-diff"), "format": "json"})
                with urlopen(f"{comparison_endpoint}?{params}", timeout=30) as response:
                    comparison_payload = json.loads(response.read())
                    self.assertEqual((comparison_payload["unchanged_count"], comparison_payload["changed_count"]), (1, 0))
                params = urlencode({"input": str(root / "api-query-snapshot-diff"), "format": "json"})
                with urlopen(f"{comparison_endpoint}/audit?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read())["accepted"])
                server.glio_deployment_guard._rate_windows.clear()
                for suffix in ("/stage-schema", "/manifest-schema", "/schema", "/capabilities", "/audit/check-schema", "/audit/schema", "/audit/capabilities", "/query/row-schema", "/query/schema", "/query/capabilities", "/query-audit/check-schema", "/query-audit/schema", "/query-audit/capabilities", "/query-snapshot/manifest-schema", "/query-snapshot/summary-schema", "/query-snapshot/schema", "/query-snapshot/capabilities", "/query-snapshot/audit/check-schema", "/query-snapshot/audit/schema", "/query-snapshot/audit/capabilities", "/query-snapshot/diff/item-schema", "/query-snapshot/diff/items-schema", "/query-snapshot/diff/manifest-schema", "/query-snapshot/diff/summary-schema", "/query-snapshot/diff/schema", "/query-snapshot/diff/capabilities", "/query-snapshot/diff/audit/check-schema", "/query-snapshot/diff/audit/schema", "/query-snapshot/diff/audit/capabilities", "/query-snapshot/diff/query/row-schema", "/query-snapshot/diff/query/schema", "/query-snapshot/diff/query/capabilities", "/query-snapshot/diff/query-audit/check-schema", "/query-snapshot/diff/query-audit/schema", "/query-snapshot/diff/query-audit/capabilities", "/query-snapshot/diff/query-snapshot/manifest-schema", "/query-snapshot/diff/query-snapshot/summary-schema", "/query-snapshot/diff/query-snapshot/schema", "/query-snapshot/diff/query-snapshot/capabilities", "/query-snapshot/diff/query-snapshot/audit/check-schema", "/query-snapshot/diff/query-snapshot/audit/schema", "/query-snapshot/diff/query-snapshot/audit/capabilities", "/query-snapshot/diff/query-snapshot/diff/item-schema", "/query-snapshot/diff/query-snapshot/diff/items-schema", "/query-snapshot/diff/query-snapshot/diff/manifest-schema", "/query-snapshot/diff/query-snapshot/diff/summary-schema", "/query-snapshot/diff/query-snapshot/diff/schema", "/query-snapshot/diff/query-snapshot/diff/capabilities", "/query-snapshot/diff/query-snapshot/diff/audit/check-schema", "/query-snapshot/diff/query-snapshot/diff/audit/schema", "/query-snapshot/diff/query-snapshot/diff/audit/capabilities", "/query-snapshot/diff/query-snapshot/diff/query/row-schema", "/query-snapshot/diff/query-snapshot/diff/query/schema", "/query-snapshot/diff/query-snapshot/diff/query/capabilities", "/query-snapshot/diff/query-snapshot/diff/query-audit/check-schema", "/query-snapshot/diff/query-snapshot/diff/query-audit/schema", "/query-snapshot/diff/query-snapshot/diff/query-audit/capabilities", "/query-snapshot/diff/query-snapshot/diff/query-snapshot/manifest-schema", "/query-snapshot/diff/query-snapshot/diff/query-snapshot/summary-schema", "/query-snapshot/diff/query-snapshot/diff/query-snapshot/schema", "/query-snapshot/diff/query-snapshot/diff/query-snapshot/capabilities", "/query-snapshot/diff/query-snapshot/diff/query-snapshot/audit/check-schema", "/query-snapshot/diff/query-snapshot/diff/query-snapshot/audit/schema", "/query-snapshot/diff/query-snapshot/diff/query-snapshot/audit/capabilities"):
                    server.glio_deployment_guard._rate_windows.clear()
                    with urlopen(f"{endpoint}{suffix}", timeout=30) as response:
                        payload = json.loads(response.read())
                        if suffix == "/capabilities":
                            self.assertEqual(payload["version"], runtime_model.VERSION)
                        elif suffix == "/audit/capabilities":
                            self.assertEqual(payload["version"], runtime_audit_model.VERSION)
                        elif suffix == "/query/capabilities":
                            self.assertEqual(payload["version"], runtime_query_model.VERSION)
                        elif suffix == "/query-audit/capabilities":
                            self.assertEqual(payload["version"], runtime_query_audit_model.VERSION)
                        elif suffix == "/query-snapshot/capabilities":
                            self.assertEqual(payload["version"], runtime_query_snapshot_model.VERSION)
                        elif suffix == "/query-snapshot/audit/capabilities":
                            self.assertEqual(payload["version"], runtime_query_snapshot_audit_model.VERSION)
                        elif suffix == "/query-snapshot/diff/capabilities":
                            self.assertEqual(payload["version"], runtime_query_snapshot_diff_model.VERSION)
                        elif suffix == "/query-snapshot/diff/audit/capabilities":
                            self.assertEqual(payload["version"], runtime_query_snapshot_diff_audit_model.VERSION)
                        elif suffix == "/query-snapshot/diff/query/capabilities":
                            self.assertEqual(payload["version"], runtime_query_snapshot_diff_query_model.VERSION)
                        elif suffix == "/query-snapshot/diff/query-audit/capabilities":
                            self.assertEqual(payload["version"], runtime_query_snapshot_diff_query_audit_model.VERSION)
                        elif suffix == "/query-snapshot/diff/query-snapshot/capabilities":
                            self.assertEqual(payload["version"], runtime_query_snapshot_diff_query_snapshot_model.VERSION)
                        elif suffix == "/query-snapshot/diff/query-snapshot/audit/capabilities":
                            self.assertEqual(payload["version"], runtime_query_snapshot_diff_query_snapshot_audit_model.VERSION)
                        elif suffix == "/query-snapshot/diff/query-snapshot/diff/capabilities":
                            self.assertEqual(payload["version"], runtime_query_snapshot_diff_query_snapshot_diff_model.VERSION)
                        elif suffix == "/query-snapshot/diff/query-snapshot/diff/audit/capabilities":
                            self.assertEqual(payload["version"], runtime_query_snapshot_diff_query_snapshot_diff_audit_model.VERSION)
                        elif suffix == "/query-snapshot/diff/query-snapshot/diff/query/capabilities":
                            self.assertEqual(payload["version"], runtime_query_snapshot_diff_query_snapshot_diff_query_model.VERSION)
                        elif suffix == "/query-snapshot/diff/query-snapshot/diff/query-audit/capabilities":
                            self.assertEqual(payload["version"], runtime_query_snapshot_diff_query_snapshot_diff_query_audit_model.VERSION)
                        elif suffix == "/query-snapshot/diff/query-snapshot/diff/query-snapshot/capabilities":
                            self.assertEqual(payload["version"], runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_model.VERSION)
                        elif suffix == "/query-snapshot/diff/query-snapshot/diff/query-snapshot/audit/capabilities":
                            self.assertEqual(payload["version"], runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_audit_model.VERSION)
                        else:
                            self.assertEqual(payload["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
            summary = runtime_path / "summary.json"
            summary.write_text(summary.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaises(ValidationError):
                runtime_model.load_runtime(runtime_path)

        inventory = build_default_public_surface_audit()
        self.assertTrue(inventory.accepted)
        self.assertEqual(len(inventory.checks), 1860)
        for schema in (runtime_model.stage_schema(), runtime_model.manifest_schema(), runtime_model.runtime_schema(), runtime_audit_model.check_schema(), runtime_audit_model.audit_schema(), runtime_query_snapshot_model.manifest_schema(), runtime_query_snapshot_model.summary_schema(), runtime_query_snapshot_model.snapshot_schema(), runtime_query_snapshot_audit_model.check_schema(), runtime_query_snapshot_audit_model.audit_schema(), runtime_query_snapshot_diff_model.item_schema(), runtime_query_snapshot_diff_model.items_schema(), runtime_query_snapshot_diff_model.manifest_schema(), runtime_query_snapshot_diff_model.summary_schema(), runtime_query_snapshot_diff_model.diff_schema(), runtime_query_snapshot_diff_audit_model.check_schema(), runtime_query_snapshot_diff_audit_model.audit_schema(), runtime_query_snapshot_diff_query_model.row_schema(), runtime_query_snapshot_diff_query_model.query_schema(), runtime_query_snapshot_diff_query_audit_model.check_schema(), runtime_query_snapshot_diff_query_audit_model.audit_schema(), runtime_query_snapshot_diff_query_snapshot_model.manifest_schema(), runtime_query_snapshot_diff_query_snapshot_model.summary_schema(), runtime_query_snapshot_diff_query_snapshot_model.snapshot_schema(), runtime_query_snapshot_diff_query_snapshot_audit_model.check_schema(), runtime_query_snapshot_diff_query_snapshot_audit_model.audit_schema(), runtime_query_snapshot_diff_query_snapshot_diff_model.item_schema(), runtime_query_snapshot_diff_query_snapshot_diff_model.items_schema(), runtime_query_snapshot_diff_query_snapshot_diff_model.manifest_schema(), runtime_query_snapshot_diff_query_snapshot_diff_model.summary_schema(), runtime_query_snapshot_diff_query_snapshot_diff_model.diff_schema(), runtime_query_snapshot_diff_query_snapshot_diff_audit_model.check_schema(), runtime_query_snapshot_diff_query_snapshot_diff_audit_model.audit_schema(), runtime_query_snapshot_diff_query_snapshot_diff_query_model.row_schema(), runtime_query_snapshot_diff_query_snapshot_diff_query_model.query_schema(), runtime_query_snapshot_diff_query_snapshot_diff_query_audit_model.check_schema(), runtime_query_snapshot_diff_query_snapshot_diff_query_audit_model.audit_schema(), runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_model.manifest_schema(), runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_model.summary_schema(), runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_model.snapshot_schema(), runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_audit_model.check_schema(), runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")

    def test_runtime_boundaries_fail_closed(self):
        archive = archive_model.build_archive(self.observatory, archive_id="runtime-boundary")
        value = runtime_model.build_runtime(archive)
        with self.assertRaises(ValidationError):
            runtime_model.runtime_from_mapping(value.to_dict() | {"state": "empty"})
        with self.assertRaises(ValidationError):
            runtime_model.runtime_from_mapping(value.to_dict() | {"stages": tuple(value.stages[:-1])})
        with self.assertRaises(ValidationError):
            runtime_audit_model.audit_from_mapping(runtime_audit_model.audit_runtime(value).to_dict() | {"accepted": False})

    def test_runtime_query_projects_persisted_receipts_and_audits_them(self):
        archive = archive_model.build_archive(self.observatory, archive_id="runtime-query-fixture")
        value = runtime_model.build_runtime(archive, runtime_id="runtime-query-fixture")
        query = runtime_query_model.query_runtime(value)
        audit = runtime_query_audit_model.audit_query(query)
        self.assertEqual((query.total_count, query.matched_count, query.returned_count), (21, 21, 21))
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (15, 15, True))
        self.assertEqual(tuple(item.stage for item in runtime_query_model.query_runtime(value, resources=("stages",), limit=6).rows), runtime_model.STAGES)
        component_query = runtime_query_model.query_runtime(value, resources=("components",), component="query")
        self.assertEqual((component_query.returned_count, component_query.rows[0].component), (1, "query"))
        artifact_query = runtime_query_model.query_runtime(value, resources=("artifacts",), name="runtime.json")
        self.assertEqual((artifact_query.returned_count, artifact_query.rows[0].name), (1, "runtime.json"))
        self.assertEqual(runtime_query_model.query_from_mapping(json.loads(runtime_query_model.query_json(query))).content_address, query.content_address)
        self.assertIn("resource", runtime_query_model.query_csv(query).splitlines()[0])
        self.assertIn("Archive Runtime Query", runtime_query_model.render_query_markdown(query))
        with self.assertRaises(ValidationError):
            runtime_query_model.query_from_mapping(query.to_dict() | {"matched_count": query.matched_count + 1})

    def test_runtime_query_snapshot_reloads_and_rejects_tampering(self):
        archive = archive_model.build_archive(self.observatory, archive_id="runtime-query-snapshot-fixture")
        value = runtime_model.build_runtime(archive, runtime_id="runtime-query-snapshot-fixture")
        snapshot = runtime_query_snapshot_model.build_snapshot(value, snapshot_id="runtime-query-snapshot-fixture", resources=("components",), component="query")
        audit = runtime_query_snapshot_audit_model.audit_snapshot(snapshot)
        self.assertEqual((snapshot.query_total_count, snapshot.query_matched_count, snapshot.query_returned_count), (4, 1, 1))
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (15, 15, True))
        self.assertEqual(runtime_query_snapshot_model.snapshot_from_mapping(json.loads(runtime_query_snapshot_model.snapshot_json(snapshot))).content_address, snapshot.content_address)
        self.assertIn("snapshot_id", runtime_query_snapshot_model.snapshot_csv(snapshot).splitlines()[0])
        self.assertIn("Runtime Query Snapshot", runtime_query_snapshot_model.render_snapshot_markdown(snapshot))
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "snapshot"
            runtime_query_snapshot_model.persist_snapshot(snapshot, destination)
            loaded = runtime_query_snapshot_model.load_snapshot(destination)
            self.assertEqual(loaded.content_address, snapshot.content_address)
            self.assertTrue(runtime_query_snapshot_audit_model.audit_snapshot(loaded).accepted)
            self.assertEqual(tuple(sorted(item.name for item in destination.iterdir())), tuple(sorted(runtime_query_snapshot_model.FILES)))
            tampered = destination / "snapshot.json"
            tampered.write_text(tampered.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaises(ValidationError):
                runtime_query_snapshot_model.load_snapshot(destination)

    def test_runtime_query_snapshot_diff_classifies_rows_and_reloads_exactly(self):
        archive = archive_model.build_archive(self.observatory, archive_id="runtime-query-snapshot-diff-fixture")
        value = runtime_model.build_runtime(archive, runtime_id="runtime-query-snapshot-diff-fixture")
        left = runtime_query_snapshot_model.build_snapshot(value, snapshot_id="runtime-query-snapshot-diff-left")
        right = runtime_query_snapshot_model.build_snapshot(value, snapshot_id="runtime-query-snapshot-diff-right", resources=("components",), component="query")
        diff = runtime_query_snapshot_diff_model.build_diff(left, right, diff_id="runtime-query-snapshot-diff-fixture")
        audit = runtime_query_snapshot_diff_audit_model.audit_diff(diff)
        self.assertEqual((diff.added_count, diff.removed_count, diff.changed_count, diff.unchanged_count), (0, 20, 1, 0))
        self.assertEqual((diff.direction, diff.left_row_count, diff.right_row_count), ("mixed", 21, 1))
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (15, 15, True))
        self.assertEqual(runtime_query_snapshot_diff_model.diff_from_mapping(json.loads(runtime_query_snapshot_diff_model.diff_json(diff))).content_address, diff.content_address)
        self.assertIn("change", runtime_query_snapshot_diff_model.diff_csv(diff).splitlines()[0])
        self.assertIn("Runtime Query Snapshot Diff", runtime_query_snapshot_diff_model.render_diff_markdown(diff))
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "snapshot-diff"
            runtime_query_snapshot_diff_model.persist_diff(diff, destination)
            loaded = runtime_query_snapshot_diff_model.load_diff(destination)
            self.assertEqual(loaded.content_address, diff.content_address)
            self.assertTrue(runtime_query_snapshot_diff_audit_model.audit_diff(loaded).accepted)
            self.assertEqual(tuple(sorted(item.name for item in destination.iterdir())), tuple(sorted(runtime_query_snapshot_diff_model.FILES)))
            tampered = destination / "items.json"
            tampered.write_text(tampered.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaises(ValidationError):
                runtime_query_snapshot_diff_model.load_diff(destination)

    def test_runtime_query_snapshot_diff_queries_and_audits_the_revision(self):
        archive = archive_model.build_archive(self.observatory, archive_id="runtime-query-snapshot-diff-query-fixture")
        value = runtime_model.build_runtime(archive, runtime_id="runtime-query-snapshot-diff-query-fixture")
        left = runtime_query_snapshot_model.build_snapshot(value, snapshot_id="runtime-query-snapshot-diff-query-left")
        right = runtime_query_snapshot_model.build_snapshot(value, snapshot_id="runtime-query-snapshot-diff-query-right", resources=("components",), component="query")
        diff = runtime_query_snapshot_diff_model.build_diff(left, right, diff_id="runtime-query-snapshot-diff-query-fixture")
        query = runtime_query_snapshot_diff_query_model.query_diff(diff, resources=runtime_query_snapshot_diff_query_model.RESOURCES, limit=runtime_query_snapshot_diff_query_model.MAX_LIMIT)
        changed = runtime_query_snapshot_diff_query_model.query_diff(diff, resources=("changed",), change="changed")
        fields = runtime_query_snapshot_diff_query_model.query_diff(diff, resources=("field-changes",), field="component")
        audit = runtime_query_snapshot_diff_query_audit_model.audit_query(changed)
        self.assertEqual((query.total_count, query.matched_count, query.returned_count), (404, 404, 128))
        self.assertEqual((changed.matched_count, changed.rows[0].change, changed.rows[0].field), (1, "changed", ""))
        self.assertEqual((fields.matched_count, fields.rows[0].resource, fields.rows[0].field), (20, "field-changes", "component"))
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (12, 12, True))
        self.assertEqual(runtime_query_snapshot_diff_query_model.query_from_mapping(json.loads(runtime_query_snapshot_diff_query_model.query_json(changed))).content_address, changed.content_address)
        self.assertEqual(runtime_query_snapshot_diff_query_audit_model.audit_from_mapping(json.loads(runtime_query_snapshot_diff_query_audit_model.audit_json(audit))).content_address, audit.content_address)
        self.assertIn("resource", runtime_query_snapshot_diff_query_model.query_csv(changed).splitlines()[0])
        self.assertIn("Snapshot Diff Query", runtime_query_snapshot_diff_query_model.render_query_markdown(changed))
        self.assertIn("Snapshot Diff Query Audit", runtime_query_snapshot_diff_query_audit_model.render_audit_markdown(audit))
        with self.assertRaises(ValidationError):
            runtime_query_snapshot_diff_query_model.query_from_mapping(changed.to_dict() | {"matched_count": changed.matched_count + 1})

    def test_runtime_query_snapshot_diff_query_snapshot_persists_and_audits_the_handoff(self):
        archive = archive_model.build_archive(self.observatory, archive_id="runtime-query-snapshot-diff-query-snapshot-fixture")
        value = runtime_model.build_runtime(archive, runtime_id="runtime-query-snapshot-diff-query-snapshot-fixture")
        left = runtime_query_snapshot_model.build_snapshot(value, snapshot_id="runtime-query-snapshot-diff-query-snapshot-left")
        right = runtime_query_snapshot_model.build_snapshot(value, snapshot_id="runtime-query-snapshot-diff-query-snapshot-right", resources=("components",), component="query")
        diff = runtime_query_snapshot_diff_model.build_diff(left, right, diff_id="runtime-query-snapshot-diff-query-snapshot-fixture")
        snapshot = runtime_query_snapshot_diff_query_snapshot_model.build_snapshot(diff, snapshot_id="runtime-query-snapshot-diff-query-snapshot-fixture", resources=("changed",), change="changed")
        audit = runtime_query_snapshot_diff_query_snapshot_audit_model.audit_snapshot(snapshot)
        self.assertEqual((snapshot.query_total_count, snapshot.query_matched_count, snapshot.query_returned_count, snapshot.state, snapshot.accepted), (1, 1, 1, "ready", True))
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (15, 15, True))
        self.assertEqual(runtime_query_snapshot_diff_query_snapshot_model.snapshot_from_mapping(json.loads(runtime_query_snapshot_diff_query_snapshot_model.snapshot_json(snapshot))).content_address, snapshot.content_address)
        self.assertIn("snapshot_id", runtime_query_snapshot_diff_query_snapshot_model.snapshot_csv(snapshot).splitlines()[0])
        self.assertIn("Runtime Query Snapshot Diff Query Snapshot", runtime_query_snapshot_diff_query_snapshot_model.render_snapshot_markdown(snapshot))
        self.assertIn("Runtime Query Snapshot Diff Query Snapshot Audit", runtime_query_snapshot_diff_query_snapshot_audit_model.render_audit_markdown(audit))
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "diff-query-snapshot"
            runtime_query_snapshot_diff_query_snapshot_model.persist_snapshot(snapshot, destination)
            loaded = runtime_query_snapshot_diff_query_snapshot_model.load_snapshot(destination)
            self.assertEqual(loaded.content_address, snapshot.content_address)
            self.assertTrue(runtime_query_snapshot_diff_query_snapshot_audit_model.audit_snapshot(loaded).accepted)
            self.assertEqual(tuple(sorted(item.name for item in destination.iterdir())), tuple(sorted(runtime_query_snapshot_diff_query_snapshot_model.FILES)))
            tampered = destination / "summary.json"
            tampered.write_text(tampered.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaises(ValidationError):
                runtime_query_snapshot_diff_query_snapshot_model.load_snapshot(destination)

    def test_runtime_query_snapshot_diff_query_snapshot_diff_compares_persisted_handoffs(self):
        archive = archive_model.build_archive(self.observatory, archive_id="runtime-query-snapshot-diff-query-snapshot-diff-fixture")
        value = runtime_model.build_runtime(archive, runtime_id="runtime-query-snapshot-diff-query-snapshot-diff-fixture")
        left_source = runtime_query_snapshot_model.build_snapshot(value, snapshot_id="comparison-source-left")
        right_source = runtime_query_snapshot_model.build_snapshot(value, snapshot_id="comparison-source-right", resources=("components",), component="query")
        source_diff = runtime_query_snapshot_diff_model.build_diff(left_source, right_source, diff_id="comparison-source-diff")
        left = runtime_query_snapshot_diff_query_snapshot_model.build_snapshot(source_diff, snapshot_id="comparison-left", resources=("changed",), change="changed")
        right = runtime_query_snapshot_diff_query_snapshot_model.build_snapshot(source_diff, snapshot_id="comparison-right", resources=("changed",), change="changed")
        comparison = runtime_query_snapshot_diff_query_snapshot_diff_model.build_diff(left, right, diff_id="comparison-fixture")
        audit = runtime_query_snapshot_diff_query_snapshot_diff_audit_model.audit_diff(comparison)
        self.assertEqual((comparison.added_count, comparison.removed_count, comparison.changed_count, comparison.unchanged_count), (0, 0, 0, 1))
        self.assertEqual((comparison.direction, comparison.query_shape_match), ("unchanged", True))
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (15, 15, True))
        self.assertEqual(runtime_query_snapshot_diff_query_snapshot_diff_model.diff_from_mapping(json.loads(runtime_query_snapshot_diff_query_snapshot_diff_model.diff_json(comparison))).content_address, comparison.content_address)
        self.assertIn("change", runtime_query_snapshot_diff_query_snapshot_diff_model.diff_csv(comparison).splitlines()[0])
        self.assertIn("Runtime Query Snapshot Handoff Comparison", runtime_query_snapshot_diff_query_snapshot_diff_model.render_diff_markdown(comparison))
        self.assertIn("Runtime Query Snapshot Handoff Comparison Audit", runtime_query_snapshot_diff_query_snapshot_diff_audit_model.render_audit_markdown(audit))
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "comparison"
            runtime_query_snapshot_diff_query_snapshot_diff_model.persist_diff(comparison, destination)
            loaded = runtime_query_snapshot_diff_query_snapshot_diff_model.load_diff(destination)
            self.assertEqual(loaded.content_address, comparison.content_address)
            self.assertTrue(runtime_query_snapshot_diff_query_snapshot_diff_audit_model.audit_diff(loaded).accepted)
            self.assertEqual(tuple(sorted(item.name for item in destination.iterdir())), tuple(sorted(runtime_query_snapshot_diff_query_snapshot_diff_model.FILES)))
            tampered = destination / "summary.json"
            tampered.write_text(tampered.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaises(ValidationError):
                runtime_query_snapshot_diff_query_snapshot_diff_model.load_diff(destination)

    def test_runtime_query_snapshot_diff_query_snapshot_diff_query_filters_and_audits(self):
        archive = archive_model.build_archive(self.observatory, archive_id="runtime-query-snapshot-diff-query-snapshot-diff-query-fixture")
        value = runtime_model.build_runtime(archive, runtime_id="runtime-query-snapshot-diff-query-snapshot-diff-query-fixture")
        left_source = runtime_query_snapshot_model.build_snapshot(value, snapshot_id="comparison-query-source-left")
        right_source = runtime_query_snapshot_model.build_snapshot(value, snapshot_id="comparison-query-source-right", resources=("components",), component="query")
        left_source_diff = runtime_query_snapshot_diff_model.build_diff(left_source, right_source, diff_id="comparison-query-source-diff-left")
        right_source_diff = runtime_query_snapshot_diff_model.build_diff(left_source, right_source, diff_id="comparison-query-source-diff-right")
        left = runtime_query_snapshot_diff_query_snapshot_model.build_snapshot(left_source_diff, snapshot_id="comparison-query-left", resources=("changed",), change="changed")
        right = runtime_query_snapshot_diff_query_snapshot_model.build_snapshot(right_source_diff, snapshot_id="comparison-query-right", resources=("changed",), change="changed")
        comparison = runtime_query_snapshot_diff_query_snapshot_diff_model.build_diff(left, right, diff_id="comparison-query-fixture")
        item = comparison.items[0]
        field = item.changed_fields[0]
        query = runtime_query_snapshot_diff_query_snapshot_diff_query_model.query_diff(comparison, resources=("field-changes",), change=item.change, source_resource=item.resource, key=item.key, identity=item.identity, field=field, direction=comparison.direction)
        audit = runtime_query_snapshot_diff_query_snapshot_diff_query_audit_model.audit_query(query)
        self.assertEqual((query.total_count, query.matched_count, query.returned_count, query.rows[0].field), (len(item.changed_fields), 1, 1, field))
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (12, 12, True))
        self.assertEqual(runtime_query_snapshot_diff_query_snapshot_diff_query_model.query_from_mapping(json.loads(runtime_query_snapshot_diff_query_snapshot_diff_query_model.query_json(query))).content_address, query.content_address)
        self.assertEqual(runtime_query_snapshot_diff_query_snapshot_diff_query_audit_model.audit_from_mapping(json.loads(runtime_query_snapshot_diff_query_snapshot_diff_query_audit_model.audit_json(audit))).content_address, audit.content_address)
        self.assertIn("source_resource", runtime_query_snapshot_diff_query_snapshot_diff_query_model.query_csv(query).splitlines()[0])
        self.assertIn("Query Snapshot Diff Query", runtime_query_snapshot_diff_query_snapshot_diff_query_model.render_query_markdown(query))
        self.assertIn("Query Snapshot Diff Query Audit", runtime_query_snapshot_diff_query_snapshot_diff_query_audit_model.render_audit_markdown(audit))
        for schema in (runtime_query_snapshot_diff_query_snapshot_diff_query_model.row_schema(), runtime_query_snapshot_diff_query_snapshot_diff_query_model.query_schema(), runtime_query_snapshot_diff_query_snapshot_diff_query_audit_model.check_schema(), runtime_query_snapshot_diff_query_snapshot_diff_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            comparison_path = root / "comparison"
            runtime_query_snapshot_diff_query_snapshot_diff_model.persist_diff(comparison, comparison_path)
            query_json = root / "query.json"
            command = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([command, str(comparison_path), "--resource", "field-changes", "--change", item.change, "--source-resource", item.resource, "--key", item.key, "--identity", item.identity, "--field", field, "--direction", comparison.direction, "--format", "json", "--output", str(query_json)]), 0)
                self.assertEqual(main([command + "-audit", str(query_json), "--format", "summary"]), 0)
            cli_payload = json.loads(query_json.read_text(encoding="utf-8"))
            self.assertEqual((cli_payload["matched_count"], cli_payload["rows"][0]["field"]), (1, field))
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                endpoint = f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/query"
                params = urlencode({"input": str(comparison_path), "resource": "field-changes", "change": item.change, "source_resource": item.resource, "key": item.key, "identity": item.identity, "field": field, "direction": comparison.direction, "format": "json"})
                with urlopen(f"{endpoint}?{params}", timeout=30) as response:
                    api_payload = json.loads(response.read())
                    self.assertEqual((api_payload["matched_count"], api_payload["rows"][0]["field"]), (1, field))
                query_json.write_text(json.dumps(api_payload), encoding="utf-8")
                with urlopen(f"{endpoint}/audit?{urlencode({'input': str(query_json), 'format': 'json'})}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read())["accepted"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_persists_and_audits(self):
        archive = archive_model.build_archive(self.observatory, archive_id="comparison-query-snapshot-fixture")
        value = runtime_model.build_runtime(archive, runtime_id="comparison-query-snapshot-fixture")
        left_source = runtime_query_snapshot_model.build_snapshot(value, snapshot_id="comparison-query-snapshot-source-left")
        right_source = runtime_query_snapshot_model.build_snapshot(value, snapshot_id="comparison-query-snapshot-source-right", resources=("components",), component="query")
        left_source_diff = runtime_query_snapshot_diff_model.build_diff(left_source, right_source, diff_id="comparison-query-snapshot-source-diff-left")
        right_source_diff = runtime_query_snapshot_diff_model.build_diff(left_source, right_source, diff_id="comparison-query-snapshot-source-diff-right")
        left = runtime_query_snapshot_diff_query_snapshot_model.build_snapshot(left_source_diff, snapshot_id="comparison-query-snapshot-left", resources=("changed",), change="changed")
        right = runtime_query_snapshot_diff_query_snapshot_model.build_snapshot(right_source_diff, snapshot_id="comparison-query-snapshot-right", resources=("changed",), change="changed")
        comparison = runtime_query_snapshot_diff_query_snapshot_diff_model.build_diff(left, right, diff_id="comparison-query-snapshot-comparison")
        item = comparison.items[0]
        field = item.changed_fields[0]
        query = runtime_query_snapshot_diff_query_snapshot_diff_query_model.query_diff(comparison, resources=("field-changes",), change=item.change, source_resource=item.resource, key=item.key, identity=item.identity, field=field, direction=comparison.direction)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot_path = root / "snapshot"
            snapshot = runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_model.run_snapshot(query, snapshot_id="comparison-query-snapshot-handoff", destination=snapshot_path)
            loaded = runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_model.load_snapshot(snapshot_path)
            audit = runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_audit_model.audit_snapshot(loaded)
            self.assertEqual((loaded.content_address, snapshot.content_address, loaded.query_address, loaded.query_returned_count), (snapshot.content_address, snapshot.content_address, query.content_address, 1))
            self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (15, 15, True))
            self.assertEqual(tuple(sorted(path.name for path in snapshot_path.iterdir())), tuple(sorted(runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_model.FILES)))
            self.assertEqual(runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_model.snapshot_from_mapping(json.loads(runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_model.snapshot_json(loaded))).content_address, loaded.content_address)
            self.assertIn("query_address", runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_model.snapshot_csv(loaded).splitlines()[0])
            self.assertIn("Comparison Query Snapshot", runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_model.render_snapshot_markdown(loaded))
            self.assertIn("Comparison Query Snapshot Audit", runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_audit_model.render_audit_markdown(audit))
            for schema in (runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_model.manifest_schema(), runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_model.summary_schema(), runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_model.snapshot_schema(), runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_audit_model.check_schema(), runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_audit_model.audit_schema()):
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            query_json = root / "query.json"
            query_json.write_text(runtime_query_snapshot_diff_query_snapshot_diff_query_model.query_json(query), encoding="utf-8")
            cli_snapshot_path = root / "cli-snapshot"
            cli_snapshot_json = root / "cli-snapshot.json"
            command = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([command, str(query_json), "--snapshot-id", "comparison-query-snapshot-cli", "--destination", str(cli_snapshot_path), "--format", "json", "--output", str(cli_snapshot_json)]), 0)
                self.assertEqual(main([command + "-audit", str(cli_snapshot_path), "--format", "summary"]), 0)
            cli_payload = json.loads(cli_snapshot_json.read_text(encoding="utf-8"))
            self.assertEqual((cli_payload["query_address"], cli_payload["query_returned_count"], cli_payload["accepted"]), (query.content_address, 1, True))
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                endpoint = "http://127.0.0.1:%s/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/query-snapshot" % server.server_port
                api_snapshot_path = root / "api-snapshot"
                params = urlencode({"input": str(query_json), "snapshot_id": "comparison-query-snapshot-api", "destination": str(api_snapshot_path), "format": "json"})
                with urlopen(f"{endpoint}?{params}", timeout=30) as response:
                    api_payload = json.loads(response.read())
                    self.assertEqual((api_payload["query_address"], api_payload["query_returned_count"], api_payload["accepted"]), (query.content_address, 1, True))
                with urlopen(f"{endpoint}/audit?{urlencode({'input': str(api_snapshot_path), 'format': 'json'})}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read())["accepted"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
            tampered = snapshot_path / "summary.json"
            tampered.write_text(tampered.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaises(ValidationError):
                runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_model.load_snapshot(snapshot_path)


if __name__ == "__main__":
    unittest.main()
