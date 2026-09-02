"""Contract tests for curated post-migration scientific root exports."""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import importlib
import importlib.util
import json
import os
import subprocess
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
        "glio_noncode_curated_surface_test_support",
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


class CuratedPublicSurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = migration.build_manifest(REPOSITORY_ROOT)

    def test_generated_curated_contract_matches_configuration_exactly(self) -> None:
        expected = migration.CURATED_EXPORTS
        self.assertEqual(_public_surface.CURATED_EXPORTS, expected)
        self.assertEqual(_public_surface.CURATED_ALL, tuple(expected))
        self.assertEqual(_public_surface.ALL[-len(expected) :], tuple(expected))
        self.assertEqual(len(expected), 71)
        for name, descriptor in expected.items():
            self.assertEqual(_public_surface.ALL.count(name), 1, name)
            self.assertEqual(_public_surface.EXPORTS[name], descriptor)

        legacy_all = _public_surface.ALL[: -len(expected)]
        payload = json.dumps(
            legacy_all,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        self.assertEqual(hashlib.sha256(payload).hexdigest(), migration.LEGACY_ALL_DIGEST)

    def test_every_curated_descriptor_resolves_through_the_lazy_root(self) -> None:
        for name, descriptor in migration.CURATED_EXPORTS.items():
            self.assertIs(getattr(glio_noncode, name), _resolve(descriptor), name)

        self.assertIs(
            glio_noncode.case_workflow_capabilities,
            importlib.import_module("glio_noncode.case_workflow").capabilities,
        )
        self.assertIs(
            glio_noncode.expression_evidence_public_projection,
            importlib.import_module("glio_noncode.expression_evidence").public_projection,
        )
        self.assertIs(
            glio_noncode.expression_claim_public_projection,
            importlib.import_module("glio_noncode.expression_claims").public_projection,
        )
        self.assertEqual(
            glio_noncode.EXPRESSION_EVIDENCE_SCHEMA_VERSION,
            importlib.import_module("glio_noncode.expression_evidence").SCHEMA_VERSION,
        )
        self.assertEqual(
            glio_noncode.EXPRESSION_CLAIMS_SCHEMA_VERSION,
            importlib.import_module("glio_noncode.expression_claims").SCHEMA_VERSION,
        )

    def test_static_stub_declares_every_curated_name(self) -> None:
        stub_path = REPOSITORY_ROOT / "src" / "glio_noncode" / "__init__.pyi"
        tree = ast.parse(stub_path.read_text(encoding="utf-8"), filename=str(stub_path))
        names: set[str] = set()
        for statement in tree.body:
            if isinstance(statement, ast.ImportFrom):
                names.update(alias.asname or alias.name for alias in statement.names)
            elif isinstance(statement, ast.Import):
                names.update(alias.asname or alias.name for alias in statement.names)
        self.assertEqual(set(migration.CURATED_EXPORTS) - names, set())

    def test_rendering_and_regeneration_inputs_are_byte_deterministic(self) -> None:
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
        migration.check_generated(self.manifest, REPOSITORY_ROOT)

    def test_checker_rejects_stale_curated_configuration_metadata(self) -> None:
        stale_exports = dict(self.manifest.curated_exports)
        stale_exports.pop("prepare_case")
        stale = dataclasses.replace(self.manifest, curated_exports=stale_exports)
        with self.assertRaisesRegex(
            migration.SurfaceMigrationError,
            "CURATED_EXPORTS differs from configured additions",
        ):
            migration.validate_manifest(stale, REPOSITORY_ROOT)

    def test_plain_import_still_loads_only_manifest_and_package(self) -> None:
        code = """
import json
import sys
import glio_noncode
print(json.dumps(sorted(
    name for name in sys.modules
    if name == "glio_noncode" or name.startswith("glio_noncode.")
)))
"""
        environment = os.environ.copy()
        source_root = str(REPOSITORY_ROOT / "src")
        existing = environment.get("PYTHONPATH")
        environment["PYTHONPATH"] = (
            source_root if not existing else source_root + os.pathsep + existing
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=REPOSITORY_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            ["glio_noncode", "glio_noncode._public_surface"],
        )


if __name__ == "__main__":
    unittest.main()
