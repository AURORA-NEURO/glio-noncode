"""D16 package export tests."""

from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

import glio_noncode as root
from glio_noncode.platform_execution_architecture_exports import (
    PlatformExecutionFixture,
    PlatformExecutionRuntime,
    default_platform_execution_fixture,
    load_platform_execution_fixture,
    platform_execution_fixture_json,
    run_platform_execution_architecture,
)


class PlatformExecutionArchitectureExportTests(unittest.TestCase):
    def test_typed_exports_and_root_surface(self) -> None:
        fixture = default_platform_execution_fixture()
        runtime = run_platform_execution_architecture(fixture)
        self.assertIsInstance(fixture, PlatformExecutionFixture)
        self.assertIsInstance(runtime, PlatformExecutionRuntime)
        self.assertTrue(runtime.accepted)
        self.assertIs(root.default_platform_execution_fixture, default_platform_execution_fixture)
        self.assertIs(root.run_platform_execution_architecture, run_platform_execution_architecture)
        self.assertIn("PlatformExecutionFixture", root.__all__)
        self.assertIn("run_platform_execution_architecture", root.__all__)

    def test_fixture_loader_rejects_duplicate_json_keys(self) -> None:
        payload = platform_execution_fixture_json().rstrip()
        duplicate = payload[:-1] + ',"fixture_id":"shadow"}'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text(duplicate, encoding="utf-8")
            with self.assertRaises(ValueError):
                load_platform_execution_fixture(path)


if __name__ == "__main__":
    unittest.main()
