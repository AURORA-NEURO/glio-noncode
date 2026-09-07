"""Regression tests for the consolidated CI CLI contract runner."""

from __future__ import annotations

import ast
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from tools import run_ci_cli_contracts as contracts


class CiCliContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inventory = contracts.load_contract_inventory()
        contracts.assert_expected_inventory(cls.inventory)

    def test_sidecar_preserves_every_exact_contract_in_source_order(self):
        self.assertEqual(len(self.inventory.contracts), 2107)
        self.assertEqual(self.inventory.literal_count, 1614)
        self.assertEqual(self.inventory.loop_expansion_count, 493)
        self.assertEqual(self.inventory.source_step_count, 790)
        self.assertEqual(len({item.command for item in self.inventory.contracts}), 2080)
        self.assertEqual(len({item.argv for item in self.inventory.contracts}), 2107)
        self.assertEqual(tuple(item.ordinal for item in self.inventory.contracts), tuple(range(1, 2108)))

    def test_every_exact_argv_is_accepted_by_the_generated_parser(self):
        parser = contracts.validate_contracts(self.inventory)
        choices = parser._subparsers._group_actions[0].choices
        self.assertTrue(all(item.command in choices for item in self.inventory.contracts))

    def test_small_batch_executes_with_one_cached_parser_and_real_outputs(self):
        parser = contracts.validate_contracts(self.inventory)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch_count = contracts.execute_contracts(
                self.inventory.contracts[:3],
                parser=parser,
                output_root=root,
                progress_every=0,
                batch_size=2,
            )
            self.assertEqual(batch_count, 2 if hasattr(os, "fork") else 1)
            for item in self.inventory.contracts[:3]:
                output = contracts.remap_temporary_paths(item.argv, root)[-1]
                self.assertIsInstance(json.loads(Path(output).read_text(encoding="utf-8")), dict)

    def test_workspace_output_is_remapped_out_of_the_checkout(self):
        root = Path("isolated-output")
        self.assertEqual(
            contracts.remap_temporary_paths(("service-surface", "--output", "data/service-surface-closure.json"), root)[-1],
            str(root / "workspace" / "data" / "service-surface-closure.json"),
        )

    def test_script_runner_restores_original_workflow_import_context(self):
        repository = str(contracts.REPOSITORY_ROOT)
        original = sys.path[:]
        try:
            sys.path[:] = [entry for entry in sys.path if entry != repository]
            contracts._ensure_repository_import_path()
            self.assertEqual(sys.path[0], repository)
        finally:
            sys.path[:] = original

    def test_active_workflow_batches_cli_and_retains_all_python_versions(self):
        workflow = (contracts.REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertNotIn("python -m glio_noncode", workflow)
        self.assertEqual(workflow.count('python-version: ["3.11", "3.12", "3.13"]'), 3)
        self.assertEqual(workflow.count("python -m unittest discover -s tests -t . -v"), 1)
        self.assertIn("python tools/run_ci_cli_contracts.py --check", workflow)
        self.assertIn("python tools/run_ci_cli_contracts.py --execute", workflow)
        for path in (
            "tests/test_topology_beta_frontier.py",
            "tests/test_topology_alpha_frontier.py",
            "tests/test_topology_alpha_frontier_depth.py",
            "tests/test_link_graph_alpha_frontier.py",
            "tests/test_link_graph_alpha_frontier_cli.py",
            "tests/test_link_graph_foundation_frontier.py",
            "tests/test_link_graph_beta_frontier.py",
            "tests/test_link_graph_beta_frontier_depth.py",
            "tests/test_link_graph_beta_frontier_integration.py",
            "tests/test_link_graph_beta_frontier_operational_matrix.py",
            "tests/test_link_graph_beta_frontier_operational_matrix_contracts.py",
        ):
            self.assertIn(path, workflow)

    def test_active_workflow_includes_every_pytest_only_module(self):
        workflow = (contracts.REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        discovered = set()
        for path in (contracts.REPOSITORY_ROOT / "tests").glob("test*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            if any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_") for node in tree.body):
                discovered.add(path.relative_to(contracts.REPOSITORY_ROOT).as_posix())
        self.assertEqual(len(discovered), 16)
        self.assertTrue(discovered)
        self.assertEqual(discovered - {line.strip() for line in workflow.splitlines()}, set())


if __name__ == "__main__":
    unittest.main()
