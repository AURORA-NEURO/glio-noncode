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

from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history as history_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory as observatory_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_audit as observatory_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_query as observatory_query_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history_observatory_query_audit as observatory_query_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError


COMMAND = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-history-observatory"


class DownloadedDataComparisonQuerySnapshotRegistryHistoryObservatoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_downloaded_data_comparison_query_snapshot_registry_history import DownloadedDataComparisonQuerySnapshotRegistryHistoryTests as history_tests

        history_tests.setUpClass()
        cls.history_tests = history_tests

    def _histories(self):
        fixture = self.history_tests()
        baseline, candidate, _first, _second = fixture._registries()
        primary = history_model.build_history((baseline, candidate), history_id="comparison-history-observatory-primary")
        secondary = history_model.build_history((baseline,), history_id="comparison-history-observatory-secondary")
        return primary, secondary

    def test_observatory_folds_histories_and_exposes_independent_queries(self):
        primary, secondary = self._histories()
        value = observatory_model.build_observatory((primary, secondary), observatory_id="comparison-history-observatory")
        audit = observatory_audit_model.audit_observatory(value)
        query = observatory_query_model.query_observatory(value, resources=("summary", "members", "transitions", "improved", "stable"), accepted=True, limit=observatory_query_model.MAX_LIMIT)
        query_audit = observatory_query_audit_model.audit_query(query)
        self.assertEqual((value.member_count, value.transition_count, value.state, value.accepted), (2, 3, "ready", True))
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (15, 15, True))
        self.assertGreater(query.returned_count, 0)
        self.assertEqual((query_audit.check_count, query_audit.passed_count, query_audit.accepted), (11, 11, True))
        self.assertEqual(observatory_model.observatory_from_mapping(json.loads(observatory_model.observatory_json(value))).content_address, value.content_address)
        self.assertEqual(observatory_query_model.query_from_mapping(json.loads(observatory_query_model.query_json(query))).content_address, query.content_address)
        self.assertIn("latest_state", observatory_model.observatory_csv(value).splitlines()[0])
        self.assertIn("Comparison Query Snapshot Registry History Observatory", observatory_model.render_observatory_markdown(value))
        self.assertIn("resource", observatory_query_model.query_csv(query).splitlines()[0])
        self.assertIn("History Observatory Query", observatory_query_model.render_query_markdown(query))
        for schema in (observatory_model.member_schema(), observatory_model.members_schema(), observatory_model.transition_schema(), observatory_model.transitions_schema(), observatory_model.manifest_schema(), observatory_model.summary_schema(), observatory_model.observatory_schema(), observatory_audit_model.check_schema(), observatory_audit_model.audit_schema(), observatory_query_model.row_schema(), observatory_query_model.query_schema(), observatory_query_audit_model.check_schema(), observatory_query_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        with self.assertRaises(ValidationError):
            observatory_model.build_observatory((primary, primary), observatory_id="duplicate-history-observatory")

    def test_observatory_persistence_cli_and_http_surfaces(self):
        primary, secondary = self._histories()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            primary_path = root / "primary"
            secondary_path = root / "secondary"
            observatory_path = root / "observatory"
            observatory_json = root / "observatory.json"
            history_model.persist_history(primary, primary_path)
            history_model.persist_history(secondary, secondary_path)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([COMMAND, str(primary_path), str(secondary_path), "--observatory-id", "comparison-history-observatory-cli", "--destination", str(observatory_path), "--format", "json", "--output", str(observatory_json)]), 0)
                self.assertEqual(main([COMMAND + "-audit", str(observatory_path), "--format", "summary"]), 0)
            loaded = observatory_model.load_observatory(observatory_path)
            self.assertEqual(loaded.content_address, observatory_model.observatory_from_mapping(json.loads(observatory_json.read_text(encoding="utf-8"))).content_address)
            query_json = root / "observatory-query.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([COMMAND + "-query", str(observatory_path), "--resource", "summary", "--resource", "members", "--resource", "transitions", "--accepted", "--format", "json", "--output", str(query_json)]), 0)
                self.assertEqual(main([COMMAND + "-query-audit", str(query_json), "--format", "summary"]), 0)
            self.assertTrue(json.loads(query_json.read_text(encoding="utf-8"))["accepted_filter"])

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = "http://127.0.0.1:%s/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/query-snapshot/registry/history/observatory" % server.server_port
                params = urlencode([("input", str(primary_path)), ("input", str(secondary_path)), ("observatory_id", "comparison-history-observatory-api"), ("destination", str(root / "api-observatory")), ("format", "json")])
                server.glio_deployment_guard._rate_windows.clear()
                with urlopen(f"{base}?{params}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read())["accepted"])
                server.glio_deployment_guard._rate_windows.clear()
                with urlopen(f"{base}/audit?{urlencode({'input': str(root / 'api-observatory'), 'format': 'json'})}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read())["accepted"])
                server.glio_deployment_guard._rate_windows.clear()
                query_params = urlencode([("input", str(root / "api-observatory")), ("resource", "summary"), ("resource", "members"), ("resource", "transitions"), ("accepted", "true"), ("format", "json")])
                with urlopen(f"{base}/query?{query_params}", timeout=30) as response:
                    api_query = json.loads(response.read())
                    self.assertGreater(api_query["returned_count"], 0)
                    (root / "api-query.json").write_text(json.dumps(api_query), encoding="utf-8")
                server.glio_deployment_guard._rate_windows.clear()
                with urlopen(f"{base}/query/audit?{urlencode({'input': str(root / 'api-query.json'), 'format': 'json'})}", timeout=30) as response:
                    self.assertTrue(json.loads(response.read())["accepted"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

            tampered = observatory_path / "summary.json"
            tampered.write_text(tampered.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaises(ValidationError):
                observatory_model.load_observatory(observatory_path)


if __name__ == "__main__":
    unittest.main()
