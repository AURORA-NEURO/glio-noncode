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
            self.assertEqual(json.loads(runtime_json.read_text(encoding="utf-8"))["state"], "ready")
            self.assertEqual((json.loads(snapshot_json.read_text(encoding="utf-8"))["query_returned_count"], json.loads(snapshot_json.read_text(encoding="utf-8"))["accepted"]), (21, True))
            self.assertEqual((json.loads(snapshot_diff_json.read_text(encoding="utf-8"))["removed_count"], json.loads(snapshot_diff_json.read_text(encoding="utf-8"))["changed_count"]), (20, 1))
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
                for suffix in ("/stage-schema", "/manifest-schema", "/schema", "/capabilities", "/audit/check-schema", "/audit/schema", "/audit/capabilities", "/query/row-schema", "/query/schema", "/query/capabilities", "/query-audit/check-schema", "/query-audit/schema", "/query-audit/capabilities", "/query-snapshot/manifest-schema", "/query-snapshot/summary-schema", "/query-snapshot/schema", "/query-snapshot/capabilities", "/query-snapshot/audit/check-schema", "/query-snapshot/audit/schema", "/query-snapshot/audit/capabilities", "/query-snapshot/diff/item-schema", "/query-snapshot/diff/items-schema", "/query-snapshot/diff/manifest-schema", "/query-snapshot/diff/summary-schema", "/query-snapshot/diff/schema", "/query-snapshot/diff/capabilities", "/query-snapshot/diff/audit/check-schema", "/query-snapshot/diff/audit/schema", "/query-snapshot/diff/audit/capabilities"):
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
        self.assertEqual(len(inventory.checks), 1480)
        for schema in (runtime_model.stage_schema(), runtime_model.manifest_schema(), runtime_model.runtime_schema(), runtime_audit_model.check_schema(), runtime_audit_model.audit_schema(), runtime_query_snapshot_model.manifest_schema(), runtime_query_snapshot_model.summary_schema(), runtime_query_snapshot_model.snapshot_schema(), runtime_query_snapshot_audit_model.check_schema(), runtime_query_snapshot_audit_model.audit_schema(), runtime_query_snapshot_diff_model.item_schema(), runtime_query_snapshot_diff_model.items_schema(), runtime_query_snapshot_diff_model.manifest_schema(), runtime_query_snapshot_diff_model.summary_schema(), runtime_query_snapshot_diff_model.diff_schema(), runtime_query_snapshot_diff_audit_model.check_schema(), runtime_query_snapshot_diff_audit_model.audit_schema()):
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


if __name__ == "__main__":
    unittest.main()
