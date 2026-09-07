from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from glio_noncode._cli_index import COMMAND_BY_NAME, LEGACY_COMMANDS, SHELL_COMMANDS
from glio_noncode._cli_report import build_parser
from glio_noncode.cli import main
from glio_noncode.reports import (
    DossierReport,
    RenderedReport,
    build_report,
    report_capabilities,
)
from glio_noncode.runtime import CaseRuntime

from .helpers import fixture_manifest


class ReportCliTests(unittest.TestCase):
    def test_parser_and_static_index_expose_exact_top_level_commands(self) -> None:
        choices = build_parser()._subparsers._group_actions[0].choices
        self.assertEqual(set(choices), {"report-capabilities", "run-report"})
        shell_names = {name for name, _ in SHELL_COMMANDS}
        legacy_names = {name for name, _ in LEGACY_COMMANDS}
        self.assertTrue({"report-capabilities", "run-report"}.issubset(shell_names))
        self.assertTrue({"report-capabilities", "run-report"}.issubset(COMMAND_BY_NAME))
        self.assertTrue({"report-capabilities", "run-report"}.isdisjoint(legacy_names))

    def test_capabilities_are_deterministic_and_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            first_path = Path(temporary) / "first.json"
            second_path = Path(temporary) / "second.json"
            self.assertEqual(
                main(["report-capabilities", "--output", str(first_path)]),
                0,
            )
            self.assertEqual(
                main(["report-capabilities", "--output", str(second_path)]),
                0,
            )
            self.assertEqual(first_path.read_bytes(), second_path.read_bytes())
            self.assertEqual(
                json.loads(first_path.read_text(encoding="utf-8")),
                report_capabilities(),
            )

    def test_run_report_reopens_verified_snapshot_and_emits_addressed_envelopes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data_root = root / "data"
            dossier = CaseRuntime(data_root).evaluate(fixture_manifest())
            review_path = root / "review.json"
            public_path = root / "public.json"
            opened: list[str] = []
            original = CaseRuntime.load_run_snapshot

            def tracked(runtime: CaseRuntime, run_id: str):
                opened.append(run_id)
                return original(runtime, run_id)

            with patch.object(CaseRuntime, "load_run_snapshot", new=tracked):
                self.assertEqual(
                    main(
                        [
                            "run-report",
                            dossier.run_id,
                            "--data-root",
                            str(data_root),
                            "--output",
                            str(review_path),
                        ]
                    ),
                    0,
                )
                self.assertEqual(
                    main(
                        [
                            "run-report",
                            dossier.run_id,
                            "--data-root",
                            str(data_root),
                            "--audience",
                            "public",
                            "--format",
                            "markdown",
                            "--output",
                            str(public_path),
                        ]
                    ),
                    0,
                )

            self.assertEqual(opened, [dossier.run_id, dossier.run_id])

            review = RenderedReport.from_dict(
                json.loads(review_path.read_text(encoding="utf-8"))
            )
            self.assertEqual((review.audience, review.format), ("review", "json"))
            embedded = DossierReport.from_dict(json.loads(review.payload))
            expected_review = build_report(dossier, audience="review")
            self.assertEqual(embedded, expected_review)
            self.assertTrue(review.verify(expected_review))

            public = RenderedReport.from_dict(
                json.loads(public_path.read_text(encoding="utf-8"))
            )
            expected_public = build_report(dossier, audience="public")
            self.assertEqual((public.audience, public.format), ("public", "markdown"))
            self.assertTrue(public.verify(expected_public))
            self.assertTrue(public.payload.startswith("# Public Dossier Report\n"))
            self.assertNotIn(dossier.case_id, public.payload)
            self.assertNotIn(dossier.run_id, public.payload)

    def test_missing_run_fails_closed_without_writing_an_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "missing.json"
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = main(
                    [
                        "run-report",
                        "run-does-not-exist",
                        "--data-root",
                        str(Path(temporary) / "data"),
                        "--output",
                        str(output),
                    ]
                )
            self.assertEqual(code, 2)
            self.assertFalse(output.exists())
            self.assertIn("error:", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
