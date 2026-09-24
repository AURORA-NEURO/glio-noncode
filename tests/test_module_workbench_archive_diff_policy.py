"""Source-free release policy tests for portable workbench comparisons."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.cli import main
from glio_noncode.module_workbench_archive import build_module_workbench_archive
from glio_noncode.module_workbench_archive_diff import (
    build_module_workbench_archive_diff,
    module_workbench_archive_diff_json,
)
from glio_noncode.module_workbench_archive_diff_policy import (
    build_module_workbench_archive_diff_policy,
    default_module_workbench_archive_diff_policy,
    evaluate_module_workbench_archive_diff_policy,
    load_module_workbench_archive_diff_policy_gate,
    module_workbench_archive_diff_policy_capabilities,
    module_workbench_archive_diff_policy_csv,
    module_workbench_archive_diff_policy_json,
    module_workbench_archive_diff_policy_schema,
    query_module_workbench_archive_diff_policy,
    render_module_workbench_archive_diff_policy_markdown,
    verify_module_workbench_archive_diff_policy_gate,
)
from tests.test_module_workbench import ModuleWorkbenchFixture


class ModuleWorkbenchArchiveDiffPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = ModuleWorkbenchFixture("runTest")
        self.fixture.setUp()
        report = self.fixture.report()
        archive = build_module_workbench_archive(report)
        self.diff = build_module_workbench_archive_diff(archive, archive)

    def tearDown(self) -> None:
        self.fixture.tearDown()

    def test_default_strict_policy_accepts_identical_archives(self) -> None:
        gate = evaluate_module_workbench_archive_diff_policy(self.diff)
        verify_module_workbench_archive_diff_policy_gate(gate)
        self.assertTrue(gate.accepted)
        self.assertEqual(gate.failed_count, 0)
        self.assertEqual(query_module_workbench_archive_diff_policy(gate, passed=True)["total"], 9)
        self.assertIn("check_id", module_workbench_archive_diff_policy_csv(gate))
        self.assertIn("# Module Workbench Archive Diff Policy", render_module_workbench_archive_diff_policy_markdown(gate))

    def test_threshold_failure_is_explained(self) -> None:
        policy = build_module_workbench_archive_diff_policy(
            minimum_score_delta=0.01,
            policy_id="strict-score-improvement",
        )
        gate = evaluate_module_workbench_archive_diff_policy(self.diff, policy)
        self.assertFalse(gate.accepted)
        failed = query_module_workbench_archive_diff_policy(gate, passed=False)
        self.assertEqual(failed["total"], 1)
        self.assertEqual(failed["items"][0]["check_id"], "minimum-score-delta")

    def test_gate_json_round_trip_and_tamper_rejection(self) -> None:
        gate = evaluate_module_workbench_archive_diff_policy(self.diff)
        raw = module_workbench_archive_diff_policy_json(gate)
        restored = load_module_workbench_archive_diff_policy_gate(raw.encode("utf-8"))
        self.assertEqual(restored.to_dict(), gate.to_dict())
        payload = json.loads(raw)
        payload["accepted"] = False
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "gate.json"
            path.write_bytes((json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8"))
            with self.assertRaises(ValidationError):
                load_module_workbench_archive_diff_policy_gate(path)

    def test_contracts_are_source_free_and_default_is_addressed(self) -> None:
        policy = default_module_workbench_archive_diff_policy()
        self.assertEqual(policy, build_module_workbench_archive_diff_policy())
        self.assertTrue(module_workbench_archive_diff_policy_schema()["source_free"])
        self.assertIn(
            "evaluate_regression_budget",
            module_workbench_archive_diff_policy_capabilities()["operations"],
        )

    def test_cli_policy_verify_query_and_contract_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diff_path = root / "diff.json"
            gate_path = root / "gate.json"
            verification_path = root / "verification.json"
            query_path = root / "query.csv"
            diff_path.write_bytes(module_workbench_archive_diff_json(self.diff).encode("utf-8"))
            self.assertEqual(
                main(
                    [
                        "module-workbench-archive-diff-policy",
                        "--diff",
                        str(diff_path),
                        "--format",
                        "json",
                        "--output",
                        str(gate_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-archive-diff-policy-verify",
                        str(gate_path),
                        "--output",
                        str(verification_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "module-workbench-archive-diff-policy-query",
                        str(gate_path),
                        "--passed",
                        "--format",
                        "csv",
                        "--output",
                        str(query_path),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(verification_path.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(query_path.read_text(encoding="utf-8").count("\n"), 10)
            schema = root / "schema.json"
            caps = root / "caps.json"
            self.assertEqual(main(["module-workbench-archive-diff-policy-schema", "--output", str(schema)]), 0)
            self.assertEqual(main(["module-workbench-archive-diff-policy-capabilities", "--output", str(caps)]), 0)
            self.assertIn("maximum_regression_count", schema.read_text(encoding="utf-8"))
            self.assertIn("verify_addresses", caps.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
