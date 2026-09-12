"""Regression tests for the consolidated CI CLI contract runner."""

from __future__ import annotations

import ast
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
        self.assertEqual(
            tuple(item.ordinal for item in self.inventory.contracts), tuple(range(1, 2108))
        )

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

    def test_in_process_execution_does_not_force_full_heap_collection(self):
        synthetic = tuple(
            contracts.CliContract(
                ordinal=index,
                step_name="heap collection sentinel",
                argv=("fixture-command",),
            )
            for index in range(1, 101)
        )
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch("glio_noncode.cli.main", return_value=0),
            patch(
                "gc.collect",
                side_effect=AssertionError("contract execution must not force full collection"),
            ),
        ):
            batch_count = contracts.execute_contracts(
                synthetic,
                parser=object(),
                output_root=Path(temporary),
                progress_every=0,
                isolate_batches=False,
            )

        self.assertEqual(batch_count, 1)

    def test_workspace_output_is_remapped_out_of_the_checkout(self):
        root = Path("isolated-output")
        self.assertEqual(
            contracts.remap_temporary_paths(
                ("service-surface", "--output", "data/service-surface-closure.json"), root
            )[-1],
            str(root / "workspace" / "data" / "service-surface-closure.json"),
        )

    def test_remapped_workspace_output_executes_with_historical_parent_directory(self):
        parser = contracts.validate_contracts(self.inventory)
        contract = self.inventory.contracts[1270]
        self.assertEqual(contract.step_name, "Local service surface closure")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contracts.execute_contracts(
                (contract,),
                parser=parser,
                output_root=root,
                progress_every=0,
            )
            output = Path(contracts.remap_temporary_paths(contract.argv, root)[-1])
            self.assertTrue(output.is_file())
            self.assertIsInstance(json.loads(output.read_text(encoding="utf-8")), dict)

    def test_execution_cannot_accept_a_stale_declared_output(self):
        contract = contracts.CliContract(
            1,
            "stale output fixture",
            ("fixture-command", "--output", "/tmp/stale.json"),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = Path(contracts.remap_temporary_paths(contract.argv, root)[-1])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text('{"stale": true}', encoding="utf-8")

            with (
                patch("glio_noncode.cli.main", return_value=0),
                self.assertRaisesRegex(contracts.ContractInventoryError, "did not create"),
            ):
                contracts.execute_contracts(
                    (contract,),
                    parser=object(),
                    output_root=root,
                    progress_every=0,
                    isolate_batches=False,
                )

            self.assertFalse(output.exists())

    def test_inventory_classifies_all_architecture_bundle_outputs_as_directories(self):
        classified = {}
        for contract in self.inventory.contracts:
            for artifact in contracts._declared_artifacts(contract.argv):
                if artifact.kind == "output" and artifact.is_directory:
                    classified[contract.command] = artifact.required_files

        self.assertEqual(set(classified), set(contracts.DIRECTORY_OUTPUT_REQUIREMENTS))
        self.assertEqual(len(classified), 14)
        self.assertTrue(
            all(
                required == contracts.ARCHITECTURE_BUNDLE_REQUIRED_FILES
                for required in classified.values()
            )
        )

    def test_directory_output_is_fresh_and_requires_real_bundle_files(self):
        contract = contracts.CliContract(
            1,
            "architecture bundle fixture",
            ("specimen-architecture-bundle", "--output", "/tmp/fresh-bundle"),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = root / "fresh-bundle"
            bundle.mkdir()
            stale = bundle / "stale.json"
            stale.write_text('{"stale": true}', encoding="utf-8")

            def write_bundle(argv):
                output = contracts._declared_output(argv)
                assert output is not None
                output.mkdir()
                for filename in contracts.ARCHITECTURE_BUNDLE_REQUIRED_FILES:
                    (output / filename).write_text('{"fresh": true}', encoding="utf-8")
                return 0

            with patch("glio_noncode.cli.main", side_effect=write_bundle):
                contracts.execute_contracts(
                    (contract,),
                    parser=object(),
                    output_root=root,
                    progress_every=0,
                    isolate_batches=False,
                )

            self.assertFalse(stale.exists())
            self.assertTrue(bundle.is_dir())
            self.assertTrue(
                all(
                    (bundle / filename).is_file()
                    for filename in contracts.ARCHITECTURE_BUNDLE_REQUIRED_FILES
                )
            )

    def test_directory_output_rejects_missing_required_bundle_file(self):
        contract = contracts.CliContract(
            1,
            "incomplete architecture bundle fixture",
            ("specimen-architecture-bundle", "--output", "/tmp/incomplete-bundle"),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            def write_incomplete_bundle(argv):
                output = contracts._declared_output(argv)
                assert output is not None
                output.mkdir()
                for filename in contracts.ARCHITECTURE_BUNDLE_REQUIRED_FILES:
                    if filename != "report.json":
                        (output / filename).write_text("{}", encoding="utf-8")
                return 0

            with (
                patch("glio_noncode.cli.main", side_effect=write_incomplete_bundle),
                self.assertRaisesRegex(
                    contracts.ContractInventoryError,
                    r"required regular file\(s\) report\.json",
                ),
            ):
                contracts.execute_contracts(
                    (contract,),
                    parser=object(),
                    output_root=root,
                    progress_every=0,
                    isolate_batches=False,
                )

    def test_directory_output_rejects_preexisting_wrong_kind_without_cleanup(self):
        contract = contracts.CliContract(
            1,
            "wrong architecture bundle kind fixture",
            ("specimen-architecture-bundle", "--output", "/tmp/not-a-bundle"),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "not-a-bundle"
            target.write_text("keep", encoding="utf-8")
            with (
                patch("glio_noncode.cli.main") as mocked_main,
                self.assertRaisesRegex(
                    contracts.ContractInventoryError,
                    "output target is not a directory",
                ),
            ):
                contracts.execute_contracts(
                    (contract,),
                    parser=object(),
                    output_root=root,
                    progress_every=0,
                    isolate_batches=False,
                )
            mocked_main.assert_not_called()
            self.assertEqual(target.read_text(encoding="utf-8"), "keep")

    def test_directory_output_rejects_preexisting_symlink_without_unlinking(self):
        contract = contracts.CliContract(
            1,
            "linked architecture bundle fixture",
            ("specimen-architecture-bundle", "--output", "/tmp/linked-bundle"),
        )
        with (
            tempfile.TemporaryDirectory() as temporary,
            tempfile.TemporaryDirectory() as external_temporary,
        ):
            root = Path(temporary)
            external = Path(external_temporary)
            marker = external / "keep.txt"
            marker.write_text("keep", encoding="utf-8")
            target = root / "linked-bundle"
            try:
                target.symlink_to(external, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"directory symlinks unavailable: {exc}")
            try:
                with (
                    patch("glio_noncode.cli.main") as mocked_main,
                    self.assertRaisesRegex(
                        contracts.ContractInventoryError,
                        "output target is a link or reparse point",
                    ),
                ):
                    contracts.execute_contracts(
                        (contract,),
                        parser=object(),
                        output_root=root,
                        progress_every=0,
                        isolate_batches=False,
                    )
                mocked_main.assert_not_called()
                self.assertTrue(target.is_symlink())
                self.assertEqual(marker.read_text(encoding="utf-8"), "keep")
            finally:
                if target.is_symlink():
                    target.unlink()

    def test_preflight_rejects_in_root_parent_symlink_without_following_it(self):
        contract = contracts.CliContract(
            1,
            "linked output parent fixture",
            ("fixture-command", "--output", "/tmp/linked-parent/output.json"),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            actual_parent = root / "actual-parent"
            actual_parent.mkdir()
            marker = actual_parent / "keep.txt"
            marker.write_text("keep", encoding="utf-8")
            linked_parent = root / "linked-parent"
            try:
                linked_parent.symlink_to(actual_parent, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"directory symlinks unavailable: {exc}")
            try:
                with (
                    patch("glio_noncode.cli.main") as mocked_main,
                    self.assertRaisesRegex(
                        contracts.ContractInventoryError,
                        "output path contains a link or reparse point",
                    ),
                ):
                    contracts.execute_contracts(
                        (contract,),
                        parser=object(),
                        output_root=root,
                        progress_every=0,
                        isolate_batches=False,
                    )
                mocked_main.assert_not_called()
                self.assertTrue(linked_parent.is_symlink())
                self.assertEqual(marker.read_text(encoding="utf-8"), "keep")
                self.assertFalse((actual_parent / "output.json").exists())
            finally:
                if linked_parent.is_symlink():
                    linked_parent.unlink()

    def test_preflight_rejects_stale_directory_child_symlink_without_cleanup(self):
        contract = contracts.CliContract(
            1,
            "stale linked bundle member fixture",
            ("specimen-architecture-bundle", "--output", "/tmp/stale-linked-bundle"),
        )
        with (
            tempfile.TemporaryDirectory() as temporary,
            tempfile.TemporaryDirectory() as external_temporary,
        ):
            root = Path(temporary)
            external = Path(external_temporary)
            external_marker = external / "keep.txt"
            external_marker.write_text("keep", encoding="utf-8")
            bundle = root / "stale-linked-bundle"
            bundle.mkdir()
            stale_marker = bundle / "stale.txt"
            stale_marker.write_text("keep", encoding="utf-8")
            linked_child = bundle / "linked-child"
            try:
                linked_child.symlink_to(external, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"directory symlinks unavailable: {exc}")
            try:
                with (
                    patch("glio_noncode.cli.main") as mocked_main,
                    self.assertRaisesRegex(
                        contracts.ContractInventoryError,
                        "link or reparse point inside declared output",
                    ),
                ):
                    contracts.execute_contracts(
                        (contract,),
                        parser=object(),
                        output_root=root,
                        progress_every=0,
                        isolate_batches=False,
                    )
                mocked_main.assert_not_called()
                self.assertTrue(bundle.is_dir())
                self.assertTrue(linked_child.is_symlink())
                self.assertEqual(stale_marker.read_text(encoding="utf-8"), "keep")
                self.assertEqual(external_marker.read_text(encoding="utf-8"), "keep")
            finally:
                if linked_child.is_symlink():
                    linked_child.unlink()

    def test_directory_output_rejects_post_execution_symlink(self):
        contract = contracts.CliContract(
            1,
            "post-execution linked bundle fixture",
            ("specimen-architecture-bundle", "--output", "/tmp/linked-bundle"),
        )
        with (
            tempfile.TemporaryDirectory() as temporary,
            tempfile.TemporaryDirectory() as external_temporary,
        ):
            root = Path(temporary)
            external = Path(external_temporary)
            target = root / "linked-bundle"

            def link_bundle(_argv):
                target.symlink_to(external, target_is_directory=True)
                return 0

            try:
                with (
                    patch("glio_noncode.cli.main", side_effect=link_bundle),
                    self.assertRaisesRegex(
                        contracts.ContractInventoryError,
                        "did not create a new real artifact",
                    ),
                ):
                    contracts.execute_contracts(
                        (contract,),
                        parser=object(),
                        output_root=root,
                        progress_every=0,
                        isolate_batches=False,
                    )
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"directory symlinks unavailable: {exc}")
            finally:
                if target.is_symlink():
                    target.unlink()

    def test_inline_declared_output_is_remapped_cleared_and_required(self):
        contract = contracts.CliContract(
            1,
            "inline stale output fixture",
            ("fixture-command", "--output=/tmp/inline-stale.json"),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            remapped = contracts.remap_temporary_paths(contract.argv, root)
            self.assertEqual(remapped[1], f"--output={root / 'inline-stale.json'}")
            output = contracts._declared_output(remapped)
            self.assertEqual(output, root / "inline-stale.json")
            assert output is not None
            output.write_text('{"stale": true}', encoding="utf-8")

            with (
                patch("glio_noncode.cli.main", return_value=0),
                self.assertRaisesRegex(contracts.ContractInventoryError, "did not create"),
            ):
                contracts.execute_contracts(
                    (contract,),
                    parser=object(),
                    output_root=root,
                    progress_every=0,
                    isolate_batches=False,
                )

            self.assertFalse(output.exists())

    def test_split_and_inline_duplicate_artifact_flags_are_rejected(self):
        fixtures = (
            (
                "--output",
                (
                    "fixture-command",
                    "--output",
                    "/tmp/first.json",
                    "--output=/tmp/second.json",
                ),
            ),
            (
                "--destination",
                (
                    "fixture-command",
                    "--destination=/tmp/first",
                    "--destination",
                    "/tmp/second",
                ),
            ),
        )
        for flag, argv in fixtures:
            with self.subTest(flag=flag), tempfile.TemporaryDirectory() as temporary:
                contract = contracts.CliContract(1, "duplicate fixture", argv)
                with (
                    patch("glio_noncode.cli.main") as mocked_main,
                    self.assertRaisesRegex(
                        contracts.ContractInventoryError,
                        f"{flag} must occur at most once",
                    ),
                ):
                    contracts.execute_contracts(
                        (contract,),
                        parser=object(),
                        output_root=Path(temporary),
                        progress_every=0,
                        isolate_batches=False,
                    )
                mocked_main.assert_not_called()

    def test_execution_cannot_accept_a_stale_declared_destination(self):
        contract = contracts.CliContract(
            1,
            "stale destination fixture",
            (
                "fixture-command",
                "--destination",
                "/tmp/stale-bundle",
                "--output",
                "/tmp/stale-bundle.json",
            ),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            remapped = contracts.remap_temporary_paths(contract.argv, root)
            destination = Path(remapped[2])
            output = Path(remapped[4])
            destination.mkdir(parents=True)
            (destination / "stale.json").write_text('{"stale": true}', encoding="utf-8")

            def write_only_output(_argv):
                output.write_text('{"fresh": true}', encoding="utf-8")
                return 0

            with (
                patch("glio_noncode.cli.main", side_effect=write_only_output),
                self.assertRaisesRegex(
                    contracts.ContractInventoryError,
                    "did not create a new directory.*declared destination",
                ),
            ):
                contracts.execute_contracts(
                    (contract,),
                    parser=object(),
                    output_root=root,
                    progress_every=0,
                    isolate_batches=False,
                )

            self.assertFalse(destination.exists())
            self.assertTrue(output.is_file())

    def test_declared_destination_cannot_erase_the_isolation_root(self):
        contract = contracts.CliContract(
            1,
            "broad destination fixture",
            ("fixture-command", "--destination", "/tmp"),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            marker = root / "keep.txt"
            marker.write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(
                contracts.ContractInventoryError,
                "cannot target the isolated output root itself",
            ):
                contracts.execute_contracts(
                    (contract,),
                    parser=object(),
                    output_root=root,
                    progress_every=0,
                    isolate_batches=False,
                )
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_all_artifacts_are_preflighted_before_stale_output_cleanup(self):
        contract = contracts.CliContract(
            1,
            "atomic preflight fixture",
            (
                "fixture-command",
                "--output",
                "/tmp/stale.json",
                "--destination=/tmp",
            ),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "stale.json"
            output.write_text("keep", encoding="utf-8")
            with (
                patch("glio_noncode.cli.main") as mocked_main,
                self.assertRaisesRegex(
                    contracts.ContractInventoryError,
                    "cannot target the isolated output root itself",
                ),
            ):
                contracts.execute_contracts(
                    (contract,),
                    parser=object(),
                    output_root=root,
                    progress_every=0,
                    isolate_batches=False,
                )
            mocked_main.assert_not_called()
            self.assertEqual(output.read_text(encoding="utf-8"), "keep")

    def test_preflight_rejects_wrong_stale_artifact_types_without_cleanup(self):
        fixtures = (
            ("output", "--output", "is a directory"),
            ("destination", "--destination", "is not a directory"),
        )
        for kind, flag, error in fixtures:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                target = root / "wrong-type"
                if kind == "output":
                    target.mkdir()
                    marker = target / "keep.txt"
                    marker.write_text("keep", encoding="utf-8")
                else:
                    target.write_text("keep", encoding="utf-8")
                    marker = target
                contract = contracts.CliContract(
                    1,
                    "wrong artifact type fixture",
                    ("fixture-command", flag, f"/tmp/{target.name}"),
                )
                with (
                    patch("glio_noncode.cli.main") as mocked_main,
                    self.assertRaisesRegex(contracts.ContractInventoryError, error),
                ):
                    contracts.execute_contracts(
                        (contract,),
                        parser=object(),
                        output_root=root,
                        progress_every=0,
                        isolate_batches=False,
                    )
                mocked_main.assert_not_called()
                self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_post_execution_artifact_cannot_escape_through_parent_symlink(self):
        contract = contracts.CliContract(
            1,
            "post-execution escape fixture",
            ("fixture-command", "--output", "/tmp/nested/output.json"),
        )
        with (
            tempfile.TemporaryDirectory() as temporary,
            tempfile.TemporaryDirectory() as external_temporary,
        ):
            root = Path(temporary)
            external = Path(external_temporary)
            probe = root / "symlink-probe"
            try:
                probe.symlink_to(external, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"directory symlinks unavailable: {exc}")
            else:
                probe.unlink()

            link_parent = root / "nested"

            def redirect_output(argv):
                output = contracts._declared_output(argv)
                assert output is not None
                output.parent.rmdir()
                output.parent.symlink_to(external, target_is_directory=True)
                output.write_text('{"fresh": true}', encoding="utf-8")
                return 0

            try:
                with (
                    patch("glio_noncode.cli.main", side_effect=redirect_output),
                    self.assertRaisesRegex(
                        contracts.ContractInventoryError,
                        "output path contains a link or reparse point",
                    ),
                ):
                    contracts.execute_contracts(
                        (contract,),
                        parser=object(),
                        output_root=root,
                        progress_every=0,
                        isolate_batches=False,
                    )
                self.assertTrue((external / "output.json").is_file())
            finally:
                if link_parent.is_symlink():
                    link_parent.unlink()

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
        workflow = (contracts.REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
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
        workflow = (contracts.REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        discovered = set()
        for path in (contracts.REPOSITORY_ROOT / "tests").glob("test*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            if any(
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name.startswith("test_")
                for node in tree.body
            ):
                discovered.add(path.relative_to(contracts.REPOSITORY_ROOT).as_posix())
        self.assertEqual(len(discovered), 16)
        self.assertTrue(discovered)
        self.assertEqual(discovered - {line.strip() for line in workflow.splitlines()}, set())


if __name__ == "__main__":
    unittest.main()
