from __future__ import annotations

import contextlib
import io
import unittest

from glio_noncode.cli import main
from glio_noncode.reference_release_frontier_cli import (
    REFERENCE_RELEASE_COMMANDS,
    run_reference_release_operation,
)
from glio_noncode.reference_release_frontier_public_data import default_reference_release_fixture


class ReferenceReleaseCliTests(unittest.TestCase):
    def test_command_family_is_complete(self) -> None:
        self.assertEqual(len(REFERENCE_RELEASE_COMMANDS), 27)
        self.assertEqual(len(set(REFERENCE_RELEASE_COMMANDS)), 27)
        fixture = default_reference_release_fixture()
        for command in REFERENCE_RELEASE_COMMANDS:
            result = run_reference_release_operation(command, fixture)
            if command == "export-reference-release-review-csv":
                self.assertIn("record_id,operation", result)
            else:
                self.assertTrue(hasattr(result, "to_dict"))

    def test_data_audit_command_emits_json(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = main(["reference-release-data-audit"])
        self.assertEqual(status, 0)
        self.assertIn('"accepted": true', output.getvalue())
        self.assertIn('"release-data-001"', output.getvalue())

    def test_csv_command_emits_text(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = main(["export-reference-release-review-csv"])
        self.assertEqual(status, 0)
        self.assertTrue(output.getvalue().startswith("row_id,record_id,operation"))
        self.assertIn("C16-CTRL-003", output.getvalue())

    def test_pipeline_command_emits_accepted_manifest(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = main(["reference-release-pipeline"])
        self.assertEqual(status, 0)
        text = output.getvalue()
        self.assertIn('"accepted": true', text)
        self.assertIn('"release"', text)
        self.assertIn('"review_queue"', text)

    def test_operational_command_emits_workload_trace(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = main(["reference-release-operational"])
        self.assertEqual(status, 0)
        text = output.getvalue()
        self.assertIn('"accepted": true', text)
        self.assertIn('"total_work_units": 661', text)
        self.assertIn('"check_count": 18', text)


if __name__ == "__main__":
    unittest.main()
