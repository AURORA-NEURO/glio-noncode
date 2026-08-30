# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history as history_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff as diff_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_audit as diff_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_query as diff_query_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_query_audit as diff_query_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_runtime as diff_runtime_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_runtime_audit as diff_runtime_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit
from tests import test_downloaded_data_profile_contract_compatibility_remediation_resolution_history as history_fixture_module


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.pending, cls.closed, cls.rejected = history_fixture_module.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryTests._snapshots()
        cls.left = history_model.build_history((cls.pending,), history_id="diff-fixture-left")
        cls.right = history_model.build_history((cls.pending, cls.closed), history_id="diff-fixture-right")
        cls.regressed_left = history_model.build_history((cls.pending, cls.closed), history_id="diff-fixture-regressed-left")
        cls.regressed_right = history_model.build_history((cls.pending, cls.closed, cls.rejected), history_id="diff-fixture-regressed-right")

    def test_value_free_diff_replays_added_unchanged_and_regressed_transitions(self):
        value = diff_model.build_diff(self.left, self.right, diff_id="diff-fixture")
        self.assertEqual((value.added_count, value.removed_count, value.changed_count, value.unchanged_count), (1, 0, 0, 1))
        self.assertEqual((value.direction, value.state_transition, value.improved_delta, value.regressed_delta), ("improved", "review-clear", 1, 0))
        self.assertEqual(tuple(item.change for item in value.items), ("unchanged", "added"))
        self.assertEqual(diff_model.diff_from_mapping(value.to_dict()).content_address, value.content_address)
        regressed = diff_model.build_diff(self.regressed_left, self.regressed_right, diff_id="diff-fixture-regressed")
        self.assertEqual((regressed.direction, regressed.state_transition, regressed.release_ready if hasattr(regressed, "release_ready") else regressed.right_release_ready), ("regressed", "clear-blocked", False))
        with self.assertRaises(ValidationError):
            diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffItem(1, "summary", "bad", "added", (), "", "", {}, {}, diff_model.ITEM_PREFIX + ":pending")

    def test_independent_audits_bounded_query_and_exact_six_file_runtime(self):
        value = diff_model.build_diff(self.left, self.right, diff_id="diff-fixture")
        audit = diff_audit_model.audit_diff(value)
        self.assertEqual((audit.check_count, audit.passed_count, audit.accepted), (12, 12, True))
        query = diff_query_model.query_diff(value, change="added", limit=1)
        self.assertEqual((query.total_count, query.matched_count, query.returned_count, query.rows[0].change), (3, 1, 1, "added"))
        self.assertEqual(diff_query_audit_model.audit_query(query).check_count, diff_query_audit_model.MAX_CHECKS)
        direction_query = diff_query_model.query_diff(value, direction="improved")
        self.assertEqual((direction_query.matched_count, direction_query.rows[0].resource), (1, "summary"))
        runtime = diff_runtime_model.build_runtime(value, runtime_id="diff-fixture-runtime")
        self.assertEqual((runtime.accepted, runtime.release_ready, runtime.state), (True, True, "complete"))
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "diff-runtime"
            diff_runtime_model.persist_runtime(runtime, destination)
            self.assertEqual(tuple(sorted(path.name for path in destination.iterdir())), tuple(sorted(diff_runtime_model.FILES)))
            loaded = diff_runtime_model.load_runtime(destination)
            self.assertEqual(loaded.content_address, runtime.content_address)
            runtime_audit = diff_runtime_audit_model.audit_runtime(loaded)
            self.assertEqual((runtime_audit.check_count, runtime_audit.passed_count, runtime_audit.accepted), (15, 15, True))
            (destination / "diff.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                diff_runtime_model.load_runtime(destination)

    def test_cli_http_schema_and_public_inventory_expose_diff_surfaces(self):
        value = diff_model.build_diff(self.left, self.right, diff_id="diff-fixture")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_path = root / "left-right.json"
            diff_path = root / "diff.json"
            query_path = root / "query.json"
            input_path.write_text(json.dumps({"left": self.left.to_dict(), "right": self.right.to_dict()}), encoding="utf-8")
            self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff", str(input_path), "--diff-id", "diff-cli", "--format", "json", "--output", str(diff_path)]), 0)
            self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-query", str(diff_path), "--change", "added", "--format", "json", "--output", str(query_path)]), 0)
            self.assertEqual(json.loads(query_path.read_text(encoding="utf-8"))["returned_count"], 1)
            runtime_dir = root / "runtime"
            self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-runtime", str(diff_path), "--destination", str(runtime_dir), "--format", "json", "--output", str(root / "runtime.json")]), 0)
            self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-runtime-audit", str(runtime_dir), "--format", "json"]), 0)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                params = urlencode({"input": str(diff_path), "change": "added", "limit": "1", "format": "summary"})
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/query?{params}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["returned_count"], 1)
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/runtime/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
        inventory = build_default_public_surface_audit()
        self.assertTrue(inventory.accepted)
        self.assertEqual(len(inventory.checks), 1458)
        for schema in (diff_model.item_schema(), diff_model.diff_schema(), diff_audit_model.check_schema(), diff_audit_model.audit_schema(), diff_query_model.row_schema(), diff_query_model.query_schema(), diff_query_audit_model.check_schema(), diff_query_audit_model.audit_schema(), diff_runtime_model.manifest_schema(), diff_runtime_model.runtime_schema(), diff_runtime_audit_model.check_schema(), diff_runtime_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(value.content_address, diff_model.build_diff(self.left, self.right, diff_id="diff-fixture").content_address)


if __name__ == "__main__":
    unittest.main()
