"""Static dependency coverage for the generated lazy public-surface manifest."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from glio_noncode.module_inventory import build_module_inventory


class LazySurfaceModuleInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.package = Path(self.directory.name) / "src" / "glio_noncode"
        self.package.mkdir(parents=True)
        (self.package / "__init__.py").write_text(
            "from . import _public_surface as _surface\n",
            encoding="utf-8",
        )
        (self.package / "_public_surface.py").write_text(
            """\
LAZY_MODULES = (
    "glio_noncode.alpha",
    ["glio_noncode.beta", "external.vendor"],
    {"gamma": "glio_noncode.gamma"},
    "glio_noncode.alpha",
    "glio_noncode._private_helper",
    42,
)
EXPORTS = {
    "Alpha": ("glio_noncode.alpha", "Alpha"),
    "Beta": ["glio_noncode.beta", "Beta"],
    "Gamma": {"module": "glio_noncode.gamma", "attribute": "Gamma"},
    "External": ("vendor.external", "External"),
    "Malformed": {"attribute": "glio_noncode.decoy"},
    "_helper": ("glio_noncode._private_helper", "helper"),
}
""",
            encoding="utf-8",
        )
        (self.package / "ordinary.py").write_text(
            """\
import glio_noncode.alpha
from .beta import Beta
from .gamma import Gamma

LAZY_MODULES = ("glio_noncode.decoy",)
EXPORTS = {"Decoy": ("glio_noncode.decoy", "Decoy")}
""",
            encoding="utf-8",
        )
        for name in ("alpha", "beta", "gamma", "decoy", "_private_helper"):
            (self.package / f"{name}.py").write_text(
                f"class {name.title().replace('_', '')}:\n    pass\n",
                encoding="utf-8",
            )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def _dependencies(self, source: str):
        inventory = build_module_inventory(
            self.package,
            test_root=Path(self.directory.name) / "tests",
        )
        return tuple(
            dependency
            for dependency in inventory.dependencies
            if dependency.source_module == source
        )

    def test_literal_lazy_dependencies_are_present_once_and_resolved(self) -> None:
        dependencies = self._dependencies("glio_noncode._public_surface")
        targets = tuple(dependency.target_module for dependency in dependencies)
        self.assertEqual(
            targets,
            (
                "glio_noncode.alpha",
                "glio_noncode.beta",
                "glio_noncode.gamma",
            ),
        )
        self.assertTrue(all(dependency.resolved for dependency in dependencies))

    def test_private_malformed_and_external_literals_do_not_inflate_graph(self) -> None:
        dependencies = self._dependencies("glio_noncode._public_surface")
        targets = {dependency.target_module for dependency in dependencies}
        self.assertNotIn("glio_noncode._private_helper", targets)
        self.assertNotIn("glio_noncode.decoy", targets)
        self.assertTrue(all(target.startswith("glio_noncode.") for target in targets))
        self.assertEqual(len(dependencies), 3)

    def test_ordinary_import_extraction_ignores_manifest_named_variables(self) -> None:
        dependencies = self._dependencies("glio_noncode.ordinary")
        self.assertEqual(
            tuple(dependency.target_module for dependency in dependencies),
            (
                "glio_noncode.alpha",
                "glio_noncode.beta",
                "glio_noncode.gamma",
            ),
        )
        self.assertTrue(all(dependency.resolved for dependency in dependencies))


if __name__ == "__main__":
    unittest.main()
