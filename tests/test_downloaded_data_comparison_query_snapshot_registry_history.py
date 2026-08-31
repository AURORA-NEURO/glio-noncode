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

from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot as snapshot_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry as registry_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history as history_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_audit as history_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_query as history_query_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_query_audit as history_query_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError


HISTORY_COMMAND = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-history"


class DownloadedDataComparisonQuerySnapshotRegistryHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_downloaded_data_comparison_query_snapshot_registry import DownloadedDataComparisonQuerySnapshotRegistryTests as registry_tests

        registry_tests.setUpClass()
        cls.registry_tests = registry_tests

    def _registries(self):
        fixture = self.registry_tests()
        fixture.observatory = self.registry_tests.observatory
        query = fixture._query()
        first = snapshot_model.build_snapshot(query, snapshot_id="comparison-query-snapshot-history-first")
        second = snapshot_model.build_snapshot(query, snapshot_id="comparison-query-snapshot-history-second")
        baseline = registry_model.build_registry((first,), registry_id="comparison-query-snapshot-history-registry")
        candidate = registry_model.build_registry((first, second), registry_id="comparison-query-snapshot-history-registry")
        return baseline, candidate, first, second

    def test_history_transitions_audit_query_and_reload_are_deterministic(self):
        baseline, candidate, _first, second = self._registries()
        history = history_model.build_history((baseline, candidate), history_id="comparison-query-snapshot-history")
        audit = history_audit_model.audit_history(history)
        query = history_query_model.query_history(
            history,
            resources=("summary", "entries", "initial", "improved", "accepted", "ready", "transitions"),
            accepted=True,
            limit=history_query_model.MAX_LIMIT,
        )
        query_audit = history_query_audit_model.audit_query(query)
        self.assertEqual((history.entry_count, history.initial_count, history.improved_count, history.state), (2, 1, 1, "ready"))
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (16, 16, True))
        self.assertEqual((query.returned_count, query.matched_count, query_audit.check_count, query_audit.passed_count, query_audit.accepted), (11, 11, 12, 12, True))
        self.assertEqual(history.entries.entries[0].transition, "initial")
        self.assertEqual(history.entries.entries[1].transition, "improved")
        self.assertEqual(history_model.history_from_mapping(json.loads(history_model.history_json(history))).content_address, history.content_address)
        self.assertEqual(history_query_model.query_from_mapping(json.loads(history_query_model.query_json(query))).content_address, query.content_address)
        self.assertIn("transition", history_model.history_csv(history).splitlines()[0])
        self.assertIn("Snapshot Registry History", history_model.render_history_markdown(history))
        self.assertIn("Comparison-Query Snapshot Registry History Query", history_query_model.render_query_markdown(query))
        for schema in (history_model.entry_schema(), history_model.entries_schema(), history_model.manifest_schema(), history_model.summary_schema(), history_model.history_schema(), history_audit_model.check_schema(), history_audit_model.audit_schema(), history_query_model.row_schema(), history_query_model.query_schema(), history_query_audit_model.check_schema(), history_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        with self.assertRaises(ValidationError):
            history_model.build_history((baseline, baseline), history_id="duplicate-history-address")
        with self.assertRaises(ValidationError):
            history_model.build_history((baseline, registry_model.build_registry((second,), registry_id="other-registry")), history_id="mixed-history")

    def test_history_cli_api_persistence_and_tamper_rejection(self):
        baseline, candidate, _first, _second = self._registries()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline_path = root / "baseline"
            candidate_path = root / "candidate"
            history_path = root / "history"
            history_json = root / "history.json"
            query_json = root / "history-query.json"
            registry_model.persist_registry(baseline, baseline_path)
            registry_model.persist_registry(candidate, candidate_path)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([HISTORY_COMMAND, str(baseline_path), str(candidate_path), "--history-id", "comparison-query-snapshot-history-cli", "--destination", str(history_path), "--format", "json", "--output", str(history_json)]), 0)
                self.assertEqual(main([HISTORY_COMMAND + "-audit", str(history_path), "--format", "summary"]), 0)
                self.assertEqual(main([HISTORY_COMMAND + "-query", str(history_path), "--resource", "summary", "--resource", "improved", "--accepted", "--format", "json", "--output", str(query_json)]), 0)
                self.assertEqual(main([HISTORY_COMMAND + "-query-audit", str(query_json), "--format", "summary"]), 0)
            self.assertEqual(history_model.load_history(history_path).content_address, history_model.history_from_mapping(json.loads(history_json.read_text(encoding="utf-8"))).content_address)
            self.assertTrue(json.loads(query_json.read_text(encoding="utf-8"))["accepted"])

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = "http://127.0.0.1:%s/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/query-snapshot/registry/history" % server.server_port
                params = urlencode([("input", str(baseline_path)), ("input", str(candidate_path)), ("history_id", "comparison-query-snapshot-history-api"), ("destination", str(root / "api-history")), ("format", "json")])
                server.glio_deployment_guard._rate_windows.clear()
                with urlopen(f"{base}?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read())["accepted"])
                server.glio_deployment_guard._rate_windows.clear()
                with urlopen(f"{base}/audit?{urlencode({'input': str(root / 'api-history'), 'format': 'json'})}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read())["accepted"])
                server.glio_deployment_guard._rate_windows.clear()
                query_endpoint = f"{base}/query"
                query_params = urlencode([("input", str(root / "api-history")), ("resource", "summary"), ("resource", "improved"), ("accepted", "true"), ("format", "json")])
                with urlopen(f"{query_endpoint}?{query_params}", timeout=30) as response:
                    api_query = json.loads(response.read())
                    self.assertEqual((api_query["returned_count"], api_query["accepted"]), (2, True))
                    (root / "api-query.json").write_text(json.dumps(api_query), encoding="utf-8")
                server.glio_deployment_guard._rate_windows.clear()
                with urlopen(f"{query_endpoint}/audit?{urlencode({'input': str(root / 'api-query.json'), 'format': 'json'})}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read())["accepted"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

            tampered = history_path / "summary.json"
            tampered.write_text(tampered.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaises(ValidationError):
                history_model.load_history(history_path)


if __name__ == "__main__":
    unittest.main()
