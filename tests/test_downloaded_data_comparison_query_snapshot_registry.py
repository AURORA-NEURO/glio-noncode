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

from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query as query_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot as snapshot_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry as registry_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_audit as registry_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_query as registry_query_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_query_audit as registry_query_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError


class DownloadedDataComparisonQuerySnapshotRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests import test_downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive as fixture_module

        fixture_module.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveTests.setUpClass()
        cls.observatory = fixture_module.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveTests.observatory

    def _query(self):
        from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive as archive_model
        from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime as runtime_model
        from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot as runtime_snapshot_model
        from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff as runtime_diff_model
        from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot as runtime_query_snapshot_model
        from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff as runtime_query_snapshot_diff_model

        archive = archive_model.build_archive(self.observatory, archive_id="comparison-query-snapshot-registry-fixture")
        runtime = runtime_model.build_runtime(archive, runtime_id="comparison-query-snapshot-registry-fixture")
        left_source = runtime_snapshot_model.build_snapshot(runtime, snapshot_id="comparison-query-snapshot-registry-source-left")
        right_source = runtime_snapshot_model.build_snapshot(runtime, snapshot_id="comparison-query-snapshot-registry-source-right", resources=("components",), component="query")
        left_source_diff = runtime_diff_model.build_diff(left_source, right_source, diff_id="comparison-query-snapshot-registry-source-diff-left")
        right_source_diff = runtime_diff_model.build_diff(left_source, right_source, diff_id="comparison-query-snapshot-registry-source-diff-right")
        left = runtime_query_snapshot_model.build_snapshot(left_source_diff, snapshot_id="comparison-query-snapshot-registry-left", resources=("changed",), change="changed")
        right = runtime_query_snapshot_model.build_snapshot(right_source_diff, snapshot_id="comparison-query-snapshot-registry-right", resources=("changed",), change="changed")
        comparison = runtime_query_snapshot_diff_model.build_diff(left, right, diff_id="comparison-query-snapshot-registry-comparison")
        item = comparison.items[0]
        return query_model.query_diff(comparison, resources=("field-changes",), change=item.change, source_resource=item.resource, key=item.key, identity=item.identity, field=item.changed_fields[0], direction=comparison.direction)

    def test_registry_audits_persists_queries_and_rejects_duplicates(self):
        query = self._query()
        first = snapshot_model.build_snapshot(query, snapshot_id="comparison-query-snapshot-registry-first")
        second = snapshot_model.build_snapshot(query, snapshot_id="comparison-query-snapshot-registry-second")
        registry = registry_model.build_registry((first, second), registry_id="comparison-query-snapshot-registry-fixture")
        registry_audit = registry_audit_model.audit_registry(registry)
        self.assertEqual((registry.entry_count, registry.state, registry.accepted), (2, "ready", True))
        self.assertEqual((registry_audit.check_count, registry_audit.passed_count, registry_audit.accepted), (16, 16, True))
        self.assertEqual(registry_model.registry_from_mapping(json.loads(registry_model.registry_json(registry))).content_address, registry.content_address)
        self.assertIn("snapshot_id", registry_model.registry_csv(registry).splitlines()[0])
        self.assertIn("Comparison Query Snapshot Registry", registry_model.render_registry_markdown(registry))
        self.assertEqual(tuple(item.name for item in registry.manifest.artifacts), registry_model.MANIFEST_ARTIFACT_FILES)
        with self.assertRaises(ValidationError):
            registry_model.build_registry((first, first), registry_id="duplicate-registry")

        query_value = registry_query_model.query_registry(registry, resources=("summary", "entries", "ready", "diffs", "queries"), accepted=True, limit=16)
        query_audit = registry_query_audit_model.audit_query(query_value)
        self.assertEqual((query_value.returned_count, query_value.matched_count), (7, 7))
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (12, 12, True))
        self.assertIn("Comparison Query Snapshot Registry Query", registry_query_model.render_query_markdown(query_value))
        self.assertIn("resource", registry_query_model.query_csv(query_value).splitlines()[0])
        self.assertEqual(registry_query_model.query_from_mapping(json.loads(registry_query_model.query_json(query_value))).content_address, query_value.content_address)
        for schema in (registry_model.entry_schema(), registry_model.entries_schema(), registry_model.manifest_schema(), registry_model.summary_schema(), registry_model.registry_schema(), registry_audit_model.check_schema(), registry_audit_model.audit_schema(), registry_query_model.row_schema(), registry_query_model.query_schema(), registry_query_audit_model.check_schema(), registry_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")

    def test_registry_reload_tamper_cli_and_http_surfaces(self):
        query = self._query()
        first = snapshot_model.build_snapshot(query, snapshot_id="comparison-query-snapshot-registry-cli-first")
        second = snapshot_model.build_snapshot(query, snapshot_id="comparison-query-snapshot-registry-cli-second")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first_path = root / "first"
            second_path = root / "second"
            registry_path = root / "registry"
            first_json = root / "first.json"
            second_json = root / "second.json"
            snapshot_model.persist_snapshot(first, first_path)
            snapshot_model.persist_snapshot(second, second_path)
            first_json.write_text(snapshot_model.snapshot_json(first), encoding="utf-8")
            second_json.write_text(snapshot_model.snapshot_json(second), encoding="utf-8")
            command = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry"
            registry_json = root / "registry.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([command, str(first_path), str(second_path), "--registry-id", "comparison-query-snapshot-registry-cli", "--destination", str(registry_path), "--format", "json", "--output", str(registry_json)]), 0)
                self.assertEqual(main([command + "-audit", str(registry_path), "--format", "summary"]), 0)
            loaded = registry_model.load_registry(registry_path)
            self.assertEqual(loaded.content_address, registry_model.registry_from_mapping(json.loads(registry_json.read_text(encoding="utf-8"))).content_address)
            query_command = command + "-query"
            query_json = root / "registry-query.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([query_command, str(registry_path), "--resource", "summary", "--resource", "entries", "--resource", "ready", "--accepted", "--format", "json", "--output", str(query_json)]), 0)
                self.assertEqual(main([query_command + "-audit", str(query_json), "--format", "summary"]), 0)
            self.assertTrue(json.loads(query_json.read_text(encoding="utf-8"))["accepted_filter"])

            tampered = registry_path / "summary.json"
            tampered.write_text(tampered.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaises(ValidationError):
                registry_model.load_registry(registry_path)

            api_registry_path = root / "api-registry"
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = "http://127.0.0.1:%s/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/query-snapshot/registry" % server.server_port
                params = urlencode([("input", str(first_path)), ("input", str(second_path)), ("registry_id", "comparison-query-snapshot-registry-api"), ("destination", str(api_registry_path)), ("format", "json")])
                server.glio_deployment_guard._rate_windows.clear()
                with urlopen(f"{base}?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read())["accepted"])
                server.glio_deployment_guard._rate_windows.clear()
                with urlopen(f"{base}/audit?{urlencode({'input': str(api_registry_path), 'format': 'json'})}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read())["accepted"])
                server.glio_deployment_guard._rate_windows.clear()
                query_endpoint = f"{base}/query"
                query_params = urlencode([("input", str(api_registry_path)), ("resource", "summary"), ("resource", "ready"), ("accepted", "true"), ("format", "json")])
                with urlopen(f"{query_endpoint}?{query_params}", timeout=30) as response:
                    api_query = json.loads(response.read())
                    self.assertEqual((api_query["returned_count"], api_query["accepted_filter"]), (3, True))
                    query_json.write_text(json.dumps(api_query), encoding="utf-8")
                server.glio_deployment_guard._rate_windows.clear()
                with urlopen(f"{query_endpoint}/audit?{urlencode({'input': str(query_json), 'format': 'json'})}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read())["accepted"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
