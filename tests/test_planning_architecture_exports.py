"""D13 package export tests."""

from __future__ import annotations

import unittest

import glio_noncode as root
from glio_noncode.planning_architecture_exports import (
    PlanningArchitectureFixture,
    PlanningArchitectureRuntime,
    default_planning_architecture_fixture,
    run_planning_architecture,
)


class PlanningArchitectureExportTests(unittest.TestCase):
    def test_typed_exports_and_root_surface(self) -> None:
        fixture = default_planning_architecture_fixture()
        runtime = run_planning_architecture(fixture)
        self.assertIsInstance(fixture, PlanningArchitectureFixture)
        self.assertIsInstance(runtime, PlanningArchitectureRuntime)
        self.assertTrue(runtime.accepted)
        self.assertIs(
            root.default_planning_architecture_fixture, default_planning_architecture_fixture
        )
        self.assertIs(root.run_planning_architecture, run_planning_architecture)
        self.assertIn("PlanningArchitectureFixture", root.__all__)
        self.assertIn("run_planning_architecture", root.__all__)


if __name__ == "__main__":
    unittest.main()
