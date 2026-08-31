# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff as diff_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy as policy_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_audit as policy_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_query as policy_query_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_query_audit as policy_query_audit_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_runtime as policy_runtime_model
from glio_noncode import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_runtime_audit as policy_runtime_audit_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit
from tests import test_downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff as diff_fixture_module


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        diff_fixture_module.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffTests.setUpClass()
        fixture = diff_fixture_module.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffTests
        cls.value = diff_model.build_diff(fixture.left, fixture.right, diff_id="policy-fixture")
        cls.regressed = diff_model.build_diff(fixture.regressed_left, fixture.regressed_right, diff_id="policy-fixture-regressed")

    def test_policy_evaluation_replays_promote_review_and_block(self):
        promoted = policy_model.evaluate(self.value, evaluation_id="policy-fixture-evaluation")
        self.assertEqual((promoted.state, promoted.decision, promoted.accepted, promoted.release_ready, promoted.passed_rule_count), ("eligible", "promote", True, True, 10))
        self.assertEqual(policy_audit_model.audit_evaluation(promoted).passed_count, 12)
        blocked = policy_model.evaluate(self.regressed, evaluation_id="policy-fixture-regressed-evaluation")
        self.assertEqual((blocked.state, blocked.decision, blocked.accepted, blocked.release_ready), ("blocked", "block", False, False))
        custom = policy_model.default_policy(allowed_directions=("improved", "regressed", "unchanged"), require_candidate_ready=False, max_regressed_delta=diff_model.MAX_ITEMS, require_state_progression=False)
        reviewed = policy_model.evaluate(self.regressed, policy=custom, evaluation_id="policy-fixture-custom-evaluation")
        self.assertEqual((reviewed.state, reviewed.decision), ("eligible", "promote"))

    def test_query_runtime_audit_and_tamper_rejection(self):
        evaluation = policy_model.evaluate(self.value, evaluation_id="policy-fixture-evaluation")
        query = policy_query_model.query_evaluation(evaluation, resource="rules", rule_id="removed-limit")
        self.assertEqual((query.total_count, query.matched_count, query.returned_count, query.rows[0].rule_id), (11, 1, 1, "removed-limit"))
        self.assertEqual(policy_query_audit_model.audit_query(query).passed_count, 10)
        runtime = policy_runtime_model.build_runtime(self.value, runtime_id="policy-fixture-runtime")
        self.assertEqual((runtime.state, runtime.decision, runtime.accepted, runtime.release_ready), ("complete", "promote", True, True))
        runtime_audit = policy_runtime_audit_model.audit_runtime(runtime)
        self.assertEqual((runtime_audit.check_count, runtime_audit.passed_count, runtime_audit.accepted), (16, 16, True))
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "runtime"
            policy_runtime_model.persist_runtime(runtime, destination)
            self.assertEqual(tuple(sorted(path.name for path in destination.iterdir())), tuple(sorted(policy_runtime_model.FILES)))
            self.assertEqual(policy_runtime_model.load_runtime(destination).content_address, runtime.content_address)
            (destination / "policy.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                policy_runtime_model.load_runtime(destination)

    def test_cli_http_schemas_and_public_inventory_expose_policy_surfaces(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            diff_path = root / "diff.json"
            evaluation_path = root / "evaluation.json"
            runtime_dir = root / "runtime"
            diff_path.write_text(json.dumps(self.value.to_dict()), encoding="utf-8")
            self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy", str(diff_path), "--format", "json", "--output", str(evaluation_path)]), 0)
            self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-audit", str(evaluation_path), "--format", "json"]), 0)
            self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-runtime", str(diff_path), "--destination", str(runtime_dir), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-runtime-audit", str(runtime_dir), "--format", "json"]), 0)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                params = urlencode({"input": str(evaluation_path), "resource": "rules", "rule_id": "removed-limit", "format": "json"})
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/query?{params}", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["returned_count"], 1)
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/runtime/schema", timeout=30) as response:
                    self.assertEqual(json.loads(response.read())["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
        inventory = build_default_public_surface_audit()
        self.assertTrue(inventory.accepted)
        self.assertEqual(len(inventory.checks), 1779)
        for schema in (policy_model.policy_schema(), policy_model.rule_schema(), policy_model.evaluation_schema(), policy_audit_model.check_schema(), policy_audit_model.audit_schema(), policy_query_model.row_schema(), policy_query_model.query_schema(), policy_query_audit_model.check_schema(), policy_query_audit_model.audit_schema(), policy_runtime_model.manifest_schema(), policy_runtime_model.runtime_schema(), policy_runtime_audit_model.check_schema(), policy_runtime_audit_model.audit_schema()):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")


if __name__ == "__main__":
    unittest.main()
