"""Regression coverage for relative imports in the package initializer."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from glio_noncode.module_inventory import build_module_inventory


class RootPackageRelativeImportTests(unittest.TestCase):
    def test_initializer_relative_module_import_is_resolved_inside_package(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "src" / "glio_noncode"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text(
                "from .module_a import value\nfrom . import module_b\n",
                encoding="utf-8",
            )
            (package / "module_a.py").write_text("value = 1\n", encoding="utf-8")
            (package / "module_b.py").write_text("value = 2\n", encoding="utf-8")

            inventory = build_module_inventory(package, test_root=Path(directory) / "tests")
            dependencies = [
                dependency
                for dependency in inventory.dependencies
                if dependency.source_module == "glio_noncode"
            ]

            self.assertTrue(
                any(
                    dependency.target_module == "glio_noncode.module_a" and dependency.resolved
                    for dependency in dependencies
                )
            )
            self.assertTrue(
                any(
                    dependency.target_module == "glio_noncode.module_b" and dependency.resolved
                    for dependency in dependencies
                )
            )


if __name__ == "__main__":
    unittest.main()
