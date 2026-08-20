from __future__ import annotations

import unittest

from glio_noncode.controls import ExportTarget, LocalDataController, default_local_policy
from glio_noncode.errors import PolicyViolation


class ControlsTests(unittest.TestCase):
    def test_pseudonymization_is_stable_and_scoped(self) -> None:
        first = LocalDataController(default_local_policy("project-a")).pseudonymize("subject-123")
        second = LocalDataController(default_local_policy("project-a")).pseudonymize("subject-123")
        other = LocalDataController(default_local_policy("project-b")).pseudonymize("subject-123")
        self.assertEqual(first, second)
        self.assertNotEqual(first, other)
        self.assertTrue(first.startswith("subject-"))

    def test_sanitize_metadata_drops_direct_identifiers(self) -> None:
        controller = LocalDataController(default_local_policy("project-a"))
        sanitized = controller.sanitize_metadata({"Name": "Example", "purpose": "fixture", "custom key": "value"})
        self.assertNotIn("name", sanitized)
        self.assertEqual(sanitized["purpose"], "fixture")
        self.assertEqual(sanitized["custom_key"], "value")

    def test_public_export_is_rejected_for_case_inputs(self) -> None:
        controller = LocalDataController(default_local_policy("project-a"))
        decision = controller.decide_export("case_manifest", ExportTarget.PUBLIC_ARTIFACT)
        self.assertFalse(decision.allowed)
        with self.assertRaises(PolicyViolation):
            controller.enforce_export("case_manifest", ExportTarget.PUBLIC_ARTIFACT)

    def test_synthetic_fixture_may_be_shared(self) -> None:
        controller = LocalDataController(default_local_policy("project-a"))
        decision = controller.enforce_export("synthetic_fixture", ExportTarget.COLLABORATOR)
        self.assertTrue(decision.allowed)
