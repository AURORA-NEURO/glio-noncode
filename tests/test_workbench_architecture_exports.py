"""D15 package export tests."""

from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

import glio_noncode as root
from glio_noncode.workbench_architecture_exports import (
    WorkbenchArchitectureFixture,
    WorkbenchArchitectureRuntime,
    default_workbench_architecture_fixture,
    load_workbench_architecture_fixture,
    workbench_architecture_fixture_json,
    run_workbench_architecture,
)


class WorkbenchArchitectureExportTests(unittest.TestCase):
    def test_typed_exports_and_root_surface(self) -> None:
        fixture = default_workbench_architecture_fixture()
        runtime = run_workbench_architecture(fixture)
        self.assertIsInstance(fixture, WorkbenchArchitectureFixture)
        self.assertIsInstance(runtime, WorkbenchArchitectureRuntime)
        self.assertTrue(runtime.accepted)
        self.assertIs(
            root.default_workbench_architecture_fixture, default_workbench_architecture_fixture
        )
        self.assertIs(root.run_workbench_architecture, run_workbench_architecture)
        self.assertIn("WorkbenchArchitectureFixture", root.__all__)
        self.assertIn("run_workbench_architecture", root.__all__)

    def test_fixture_loader_rejects_duplicate_json_keys(self) -> None:
        payload = workbench_architecture_fixture_json().rstrip()
        duplicate = payload[:-1] + ',"fixture_id":"shadow"}'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text(duplicate, encoding="utf-8")
            with self.assertRaises(ValueError):
                load_workbench_architecture_fixture(path)


if __name__ == "__main__":
    unittest.main()
