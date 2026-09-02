"""Focused compatibility and performance tests for the lazy package root."""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import textwrap
import types
import unittest
from pathlib import Path

import glio_noncode
from glio_noncode import _public_surface

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class LazyPackageRootTests(unittest.TestCase):
    def test_representative_classes_functions_constants_and_aliases(self) -> None:
        self.assertIs(
            glio_noncode.CaseManifest,
            importlib.import_module("glio_noncode.models").CaseManifest,
        )
        self.assertIs(
            glio_noncode.AssayQCEvaluator,
            importlib.import_module("glio_noncode.assay_qc").AssayQCEvaluator,
        )
        self.assertEqual(glio_noncode.__version__, "0.1.0")
        source = importlib.import_module(
            "glio_noncode.validation_release_frontier_public_data"
        )
        self.assertIs(
            glio_noncode.default_validation_release_fixture,
            source.default_validation_release_frontier_fixture,
        )

    def test_stale_eager_exports_are_now_resolvable(self) -> None:
        dictionary = importlib.import_module(
            "glio_noncode.atlas_architecture_data_dictionary"
        )
        release = importlib.import_module("glio_noncode.review_workspace_execution_release")
        self.assertIs(
            glio_noncode.AtlasArchitectureField,
            dictionary.AtlasArchitectureField,
        )
        self.assertIs(
            glio_noncode.query_review_workspace_execution_release_transitions_view,
            release.query_review_workspace_execution_release_transitions_view,
        )

    def test_canonical_collisions_survive_child_imports(self) -> None:
        inventory_before = glio_noncode.module_inventory_schema
        inventory_child = importlib.import_module("glio_noncode.module_inventory_schema")
        self.assertIsInstance(inventory_before, types.ModuleType)
        self.assertIs(inventory_before, inventory_child)
        self.assertIs(glio_noncode.module_inventory_schema, inventory_before)

        schema_before = glio_noncode.atlas_architecture_schema
        schema_child = importlib.import_module("glio_noncode.atlas_architecture_schema")
        self.assertIsInstance(schema_child, types.ModuleType)
        self.assertIs(glio_noncode.atlas_architecture_schema, schema_before)
        self.assertIs(
            schema_before,
            importlib.import_module(
                "glio_noncode.atlas_architecture_exports"
            ).atlas_architecture_schema,
        )

    def test_child_import_before_first_export_lookup_keeps_canonical_value(self) -> None:
        code = textwrap.dedent(
            """
            import importlib
            import types
            import glio_noncode

            child = importlib.import_module("glio_noncode.atlas_architecture_schema")
            value = glio_noncode.atlas_architecture_schema
            source = importlib.import_module("glio_noncode.atlas_architecture_exports")
            assert isinstance(child, types.ModuleType)
            assert value is source.atlas_architecture_schema
            assert glio_noncode.atlas_architecture_schema is value
            """
        )
        result = self._run_python(code)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_direct_child_fallback_and_from_import(self) -> None:
        self.assertIs(glio_noncode.cli, importlib.import_module("glio_noncode.cli"))
        from glio_noncode import AtlasArchitectureField, CaseManifest

        self.assertIs(AtlasArchitectureField, glio_noncode.AtlasArchitectureField)
        self.assertIs(CaseManifest, glio_noncode.CaseManifest)

    def test_star_import_sample_uses_the_legacy_all_contract(self) -> None:
        original = glio_noncode.__all__
        sample = ["CaseManifest", "AssayQCEvaluator", "AtlasArchitectureField"]
        try:
            glio_noncode.__all__ = sample
            namespace: dict[str, object] = {}
            exec("from glio_noncode import *", namespace)
        finally:
            glio_noncode.__all__ = original
        self.assertEqual(set(sample), set(namespace) - {"__builtins__"})
        self.assertIs(namespace["CaseManifest"], glio_noncode.CaseManifest)
        self.assertIs(
            namespace["AtlasArchitectureField"],
            glio_noncode.AtlasArchitectureField,
        )

    def test_all_and_dir_are_complete_deterministic_and_non_resolving(self) -> None:
        self.assertIsInstance(glio_noncode.__all__, list)
        self.assertEqual(tuple(glio_noncode.__all__), _public_surface.ALL)
        self.assertGreater(len(glio_noncode.__all__), len(set(glio_noncode.__all__)))
        names = dir(glio_noncode)
        self.assertEqual(names, sorted(set(names)))
        for name in (
            "CaseManifest",
            "AtlasArchitectureField",
            "atlas_architecture_schema",
            "module_inventory_schema",
            "cli",
            "__version__",
        ):
            self.assertIn(name, names)

    def test_missing_attribute_is_deterministic(self) -> None:
        name = "this_surface_does_not_exist"
        with self.assertRaisesRegex(
            AttributeError,
            "^module 'glio_noncode' has no attribute 'this_surface_does_not_exist'$",
        ):
            getattr(glio_noncode, name)

    def test_user_assignment_and_deletion_restore_the_canonical_export(self) -> None:
        canonical = glio_noncode.CaseManifest
        replacement = object()
        glio_noncode.CaseManifest = replacement
        try:
            self.assertIs(glio_noncode.CaseManifest, replacement)
            self.assertIs(vars(glio_noncode)["CaseManifest"], replacement)
        finally:
            del glio_noncode.CaseManifest
        self.assertIs(glio_noncode.CaseManifest, canonical)
        self.assertNotIn("CaseManifest", vars(glio_noncode))

    def test_cold_import_stays_small(self) -> None:
        code = textwrap.dedent(
            """
            import json
            import os
            import sys
            import time

            try:
                import psutil
            except ImportError:
                process = None
                before = None
            else:
                process = psutil.Process(os.getpid())
                before = process.memory_info().rss

            started = time.perf_counter()
            import glio_noncode
            seconds = time.perf_counter() - started
            after = process.memory_info().rss if process is not None else None
            modules = sorted(
                name
                for name in sys.modules
                if name == "glio_noncode" or name.startswith("glio_noncode.")
            )
            print(json.dumps({
                "seconds": seconds,
                "modules": modules,
                "rss_delta_mib": (
                    None if before is None else (after - before) / (1024 * 1024)
                ),
                "all_count": len(glio_noncode.__all__),
            }))
            """
        )
        result = self._run_python(code)
        self.assertEqual(result.returncode, 0, result.stderr)
        metrics = json.loads(result.stdout)
        self.assertLess(metrics["seconds"], 2.0, metrics)
        self.assertLess(len(metrics["modules"]), 25, metrics)
        self.assertEqual(metrics["modules"], [
            "glio_noncode",
            "glio_noncode._public_surface",
        ])
        self.assertEqual(metrics["all_count"], len(_public_surface.ALL))
        if metrics["rss_delta_mib"] is not None:
            self.assertLess(metrics["rss_delta_mib"], 32.0, metrics)

    @staticmethod
    def _run_python(code: str) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        source_root = str(REPOSITORY_ROOT / "src")
        existing = environment.get("PYTHONPATH")
        environment["PYTHONPATH"] = (
            source_root if not existing else source_root + os.pathsep + existing
        )
        return subprocess.run(
            [sys.executable, "-c", code],
            cwd=REPOSITORY_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )


if __name__ == "__main__":
    unittest.main()
