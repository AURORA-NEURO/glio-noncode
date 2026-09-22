from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import downloaded_data_quality_d494_release_evidence_archive as archive_model
from glio_noncode._cli_evidence import _markdown_cell
from glio_noncode._cli_index import COMMAND_BY_NAME
from glio_noncode.cli import main
from tests.test_downloaded_data_quality_d494 import _inputs, _rewrite_zip


class ReleaseEvidenceCliTests(unittest.TestCase):
    def _archive_path(self, root: Path, *, blocked: bool = False) -> Path:
        bundle = _inputs(query_resources=("checks",) if blocked else None)[-1]
        path = root / ("blocked.zip" if blocked else "ready.zip")
        archive_model.persist_archive(bundle, path)
        return path

    def _run(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = main(arguments)
        return status, stdout.getvalue(), stderr.getvalue()

    def test_command_is_discoverable_from_the_lightweight_shell(self) -> None:
        self.assertIn("verify-release-evidence", COMMAND_BY_NAME)
        status, output, _ = self._run(["commands", "show", "verify-release-evidence"])
        self.assertEqual(status, 0)
        self.assertIn("portable release-evidence ZIP", output)

    def test_ready_archive_is_loaded_audited_and_reported_without_local_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self._archive_path(root)
            status, output, error = self._run(["verify-release-evidence", str(archive)])

            result = json.loads(output)
            self.assertEqual(status, 0, error)
            self.assertTrue(result["archive_valid"])
            self.assertEqual(result["status"], "ready")
            self.assertTrue(result["release_ready"])
            self.assertTrue(result["audit"]["accepted"])
            self.assertEqual(result["audit"]["passed_count"], result["audit"]["check_count"])
            self.assertEqual(len(result["files"]), 8)
            self.assertIn("publisher identity is not authenticated", result["verification_scope"])
            self.assertNotIn(str(root), output)

    def test_valid_but_blocked_archive_has_a_distinct_exit_status(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive = self._archive_path(Path(temporary), blocked=True)
            status, output, error = self._run(["verify-release-evidence", str(archive)])

            result = json.loads(output)
            self.assertEqual(status, 3, error)
            self.assertTrue(result["archive_valid"])
            self.assertEqual(result["status"], "blocked")
            self.assertFalse(result["release_ready"])
            self.assertTrue(result["audit"]["accepted"])
            self.assertIn("manifest_not_release_ready", result["blocked_reasons"])

    def test_nonarchive_and_missing_input_return_structured_invalid_results(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            malformed = root / "malformed.zip"
            malformed.write_bytes(b"not a ZIP archive")
            for path, expected_code in (
                (malformed, "invalid_archive"),
                (root / "missing.zip", "archive_read_error"),
            ):
                with self.subTest(path=path.name):
                    status, output, error = self._run(["verify-release-evidence", str(path)])
                    result = json.loads(output)
                    self.assertEqual(status, 2, error)
                    self.assertFalse(result["archive_valid"])
                    self.assertEqual(result["status"], "invalid")
                    self.assertEqual(result["error"]["code"], expected_code)
                    self.assertNotIn(str(root), output)

    def test_tampered_payload_is_rejected_after_valid_zip_decoding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = _inputs()[-1]
            tampered = root / "tampered.zip"
            raw = _rewrite_zip(
                archive_model.archive_bytes(bundle),
                changed=archive_model.FILE_NAMES[0],
            )
            tampered.write_bytes(raw)

            status, output, error = self._run(["verify-release-evidence", str(tampered)])
            result = json.loads(output)
            self.assertEqual(status, 2, error)
            self.assertFalse(result["archive_valid"])
            self.assertEqual(result["error"]["code"], "invalid_archive")

    def test_markdown_cells_escape_table_delimiters_and_line_breaks(self) -> None:
        self.assertEqual(_markdown_cell("left|right\nnext`cell"), "left\\|right next\\`cell")

    def test_markdown_can_be_written_atomically_and_source_cannot_be_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = self._archive_path(root)
            rendered_path = root / "audit.md"
            status, _, error = self._run(
                [
                    "verify-release-evidence",
                    str(archive),
                    "--format",
                    "markdown",
                    "--output",
                    str(rendered_path),
                ]
            )
            self.assertEqual(status, 0, error)
            rendered = rendered_path.read_text(encoding="utf-8")
            self.assertIn("# Release-evidence verification", rendered)
            self.assertIn("## Independent audit", rendered)
            self.assertIn("## Allowlisted members", rendered)

            original = archive.read_bytes()
            status, _, error = self._run(
                ["verify-release-evidence", str(archive), "--output", str(archive)]
            )
            self.assertEqual(status, 2)
            self.assertIn("must not replace", error)
            self.assertEqual(archive.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
