from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from glio_noncode.editing_design_frontier_adapters import build_editing_design_adapters, execute_editing_design_adapter
from glio_noncode.editing_design_frontier_contracts import EditingDesignOperation, EditingDesignState
from glio_noncode.editing_design_frontier_depth import build_editing_design_depth
from glio_noncode.editing_design_frontier_fixture_eval import evaluate_editing_design_fixture
from glio_noncode.editing_design_frontier_public_data import default_editing_design_frontier_fixture, editing_design_frontier_fixture_json, load_editing_design_frontier_fixture
from glio_noncode.editing_design_frontier_thresholds import build_editing_design_threshold_report


class EditingDesignExtensionTests(unittest.TestCase):
    def test_schema_rejects_empty_payload(self) -> None:
        result = execute_editing_design_adapter(build_editing_design_adapters(), EditingDesignOperation.CRISPR_DESIGN, {})
        self.assertEqual(result.state, EditingDesignState.REJECTED)
        self.assertIn("schema_invalid", result.issue_codes)

    def test_depth_and_thresholds_close(self) -> None:
        fixture = default_editing_design_frontier_fixture(); evaluation = evaluate_editing_design_fixture(fixture)
        self.assertTrue(build_editing_design_depth(fixture=fixture, evaluation=evaluation).accepted)
        thresholds = build_editing_design_threshold_report()
        self.assertTrue(thresholds.accepted)
        self.assertEqual(thresholds.thresholds["total_checks"], 80)

    def test_public_fixture_json_reload(self) -> None:
        fixture = default_editing_design_frontier_fixture(); text = editing_design_frontier_fixture_json(fixture)
        self.assertIn(fixture.content_address, text)
        self.assertEqual(load_editing_design_frontier_fixture("examples/editing-design-public-aggregate.json").content_address, fixture.content_address)

    def test_fixture_loader_rejects_duplicate_json_keys(self) -> None:
        fixture = default_editing_design_frontier_fixture()
        payload = editing_design_frontier_fixture_json(fixture).rstrip()
        duplicate = payload[:-1] + ',"fixture_id":"shadow"}'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text(duplicate, encoding="utf-8")
            with self.assertRaises(ValueError):
                load_editing_design_frontier_fixture(path)


if __name__ == "__main__":
    unittest.main()
