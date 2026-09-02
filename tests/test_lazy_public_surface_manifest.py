"""Contract tests for the generated lazy-root public-surface manifest."""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import importlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import ModuleType

import glio_noncode
from glio_noncode import _public_surface

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_TOOL = REPOSITORY_ROOT / "tools" / "migrate_public_surface.py"


def _load_migration_tool() -> ModuleType:
    specification = importlib.util.spec_from_file_location(
        "glio_noncode_surface_migration_test_support",
        MIGRATION_TOOL,
    )
    if specification is None or specification.loader is None:
        raise RuntimeError(f"cannot load {MIGRATION_TOOL}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


migration = _load_migration_tool()


def _resolve(descriptor: tuple[str, str | None]) -> object:
    module_name, attribute = descriptor
    module = importlib.import_module(module_name)
    return module if attribute is None else getattr(module, attribute)


class LazyPublicSurfaceManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = migration.build_manifest(REPOSITORY_ROOT)

    def test_manifest_and_stub_generation_are_deterministic(self) -> None:
        repeated = migration.build_manifest(REPOSITORY_ROOT)
        self.assertEqual(repeated, self.manifest)
        manifest_path, stub_path = migration.generated_paths(REPOSITORY_ROOT)
        self.assertEqual(
            manifest_path.read_text(encoding="utf-8"),
            migration.render_manifest(self.manifest),
        )
        self.assertEqual(
            stub_path.read_text(encoding="utf-8"),
            migration.render_stub(self.manifest),
        )
        ast.parse(stub_path.read_text(encoding="utf-8"), filename=str(stub_path))

    def test_all_preserves_the_eager_order_duplicates_and_digest(self) -> None:
        self.assertEqual(_public_surface.ALL, tuple(glio_noncode.__all__))
        self.assertGreater(len(_public_surface.ALL), len(set(_public_surface.ALL)))
        payload = json.dumps(
            _public_surface.ALL,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        self.assertEqual(_public_surface.ALL_DIGEST, hashlib.sha256(payload).hexdigest())
        self.assertEqual(_public_surface.ALL_DIGEST, self.manifest.all_digest)

    def test_every_descriptor_preserves_final_runtime_identity(self) -> None:
        migration.validate_manifest(self.manifest, REPOSITORY_ROOT)
        self.assertEqual(_public_surface.EXPORTS, self.manifest.exports)
        for name, descriptor in _public_surface.EXPORTS.items():
            resolved = _resolve(descriptor)
            if name in _public_surface.REPAIRED_EXPORTS:
                continue
            if hasattr(glio_noncode, name):
                self.assertIs(
                    getattr(glio_noncode, name),
                    resolved,
                    f"runtime identity changed for {name}",
                )

    def test_child_modules_lazy_modules_and_conflicts_are_closed(self) -> None:
        expected_conflicts = tuple(
            sorted(set(_public_surface.EXPORTS).intersection(_public_surface.CHILD_MODULES))
        )
        self.assertEqual(
            _public_surface.CANONICAL_EXPORT_CHILD_CONFLICTS,
            expected_conflicts,
        )
        expected_lazy_modules = tuple(
            sorted(
                {module for module, _attribute in _public_surface.EXPORTS.values()}
                | set(_public_surface.CHILD_MODULES.values())
            )
        )
        self.assertEqual(_public_surface.LAZY_MODULES, expected_lazy_modules)
        self.assertNotIn("__main__", _public_surface.CHILD_MODULES)
        self.assertNotIn("_public_surface", _public_surface.CHILD_MODULES)

    def test_checker_rejects_child_inventory_drift(self) -> None:
        children = dict(self.manifest.child_modules)
        children.pop("cli")
        stale = dataclasses.replace(self.manifest, child_modules=children)
        with self.assertRaisesRegex(
            migration.SurfaceMigrationError,
            "CHILD_MODULES differs from the package directory",
        ):
            migration.validate_manifest(stale, REPOSITORY_ROOT)

    def test_representative_collisions_keep_the_eager_winner(self) -> None:
        self.assertEqual(
            _public_surface.EXPORTS["module_inventory_schema"],
            ("glio_noncode.module_inventory_schema", None),
        )
        self.assertIsInstance(glio_noncode.module_inventory_schema, ModuleType)
        self.assertIs(
            glio_noncode.module_inventory_schema,
            importlib.import_module("glio_noncode.module_inventory_schema"),
        )
        self.assertEqual(
            _public_surface.EXPORTS["atlas_architecture_schema"],
            ("glio_noncode.atlas_architecture_exports", "atlas_architecture_schema"),
        )
        self.assertIs(
            glio_noncode.atlas_architecture_schema,
            importlib.import_module(
                "glio_noncode.atlas_architecture_exports"
            ).atlas_architecture_schema,
        )
        for name in ("module_inventory_schema", "atlas_architecture_schema"):
            self.assertIn(name, _public_surface.CANONICAL_EXPORT_CHILD_CONFLICTS)

    def test_assigned_aliases_and_constants_are_explicit(self) -> None:
        self.assertEqual(_public_surface.CONSTANTS, {"__version__": "0.1.0"})
        self.assertEqual(glio_noncode.__version__, _public_surface.CONSTANTS["__version__"])
        descriptor = (
            "glio_noncode.validation_release_frontier_public_data",
            "default_validation_release_frontier_fixture",
        )
        self.assertEqual(
            _public_surface.ASSIGNED_ALIASES["default_validation_release_fixture"],
            descriptor,
        )
        self.assertEqual(
            _public_surface.EXPORTS["default_validation_release_fixture"],
            descriptor,
        )

    def test_stale_exports_are_repaired_by_explicit_descriptors(self) -> None:
        expected = {
            "AtlasArchitectureField": (
                "glio_noncode.atlas_architecture_data_dictionary",
                "AtlasArchitectureField",
            ),
            "query_review_workspace_execution_release_transitions_view": (
                "glio_noncode.review_workspace_execution_release",
                "query_review_workspace_execution_release_transitions_view",
            ),
        }
        self.assertEqual(_public_surface.REPAIRED_EXPORTS, expected)
        for name, descriptor in expected.items():
            self.assertIn(name, _public_surface.ALL)
            self.assertEqual(_public_surface.EXPORTS[name], descriptor)
            self.assertIsNotNone(_resolve(descriptor))


if __name__ == "__main__":
    unittest.main()
