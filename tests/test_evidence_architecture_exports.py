"""D14 package export tests."""

from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

import glio_noncode as root
from glio_noncode.evidence_architecture_exports import (
    EvidenceArchitectureFixture,
    EvidenceArchitectureRuntime,
    default_evidence_architecture_fixture,
    evidence_architecture_fixture_json,
    load_evidence_architecture_fixture,
    run_evidence_architecture,
)


class EvidenceArchitectureExportTests(unittest.TestCase):
    def test_typed_exports_and_root_surface(self) -> None:
        fixture = default_evidence_architecture_fixture()
        runtime = run_evidence_architecture(fixture)
        self.assertIsInstance(fixture, EvidenceArchitectureFixture)
        self.assertIsInstance(runtime, EvidenceArchitectureRuntime)
        self.assertTrue(runtime.accepted)
        self.assertIs(
            root.default_evidence_architecture_fixture, default_evidence_architecture_fixture
        )
        self.assertIs(root.run_evidence_architecture, run_evidence_architecture)
        self.assertIn("EvidenceArchitectureFixture", root.__all__)
        self.assertIn("run_evidence_architecture", root.__all__)

    def test_fixture_loader_rejects_duplicate_json_keys(self) -> None:
        payload = evidence_architecture_fixture_json().rstrip()
        duplicate = payload[:-1] + ',"fixture_id":"shadow"}'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text(duplicate, encoding="utf-8")
            with self.assertRaises(ValueError):
                load_evidence_architecture_fixture(path)


if __name__ == "__main__":
    unittest.main()
