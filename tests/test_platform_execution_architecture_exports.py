"""D16 package export tests."""

from __future__ import annotations

import unittest

import glio_noncode as root
from glio_noncode.platform_execution_architecture_exports import (
    PlatformExecutionFixture,
    PlatformExecutionRuntime,
    default_platform_execution_fixture,
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


if __name__ == "__main__":
    unittest.main()
