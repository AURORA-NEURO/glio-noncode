"""Deep tests for cross-run portfolio and release-readiness projections."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.models import ReviewDecision, ReviewState
from glio_noncode.run_portfolio import build_run_portfolio, build_run_portfolio_closure
from glio_noncode.runtime import CaseRuntime

from .helpers import fixture_manifest

AS_OF = "2026-09-01T12:00:00Z"


def accepted_review(case_id: str, hypothesis_id: str, claim_ids: tuple[str, ...], review_id: str) -> ReviewDecision:
    return ReviewDecision(
        review_id=review_id,
        case_id=case_id,
        reviewer="portfolio-reviewer",
        state=ReviewState.ACCEPTED,
        reviewed_hypothesis_ids=(hypothesis_id,),
        rationale="The portfolio test review preserves the research boundary.",
        checked_claim_ids=claim_ids,
    )


class RunPortfolioTests(unittest.TestCase):
    def _runtime_with_lifecycle(self, directory: str) -> tuple[CaseRuntime, object, object]:
        runtime = CaseRuntime(directory)
        pending = runtime.evaluate(fixture_manifest())
        reviewed_manifest = replace(
            fixture_manifest(),
            case_id="portfolio-case-002",
            requested_by="portfolio-requester-002",
        )
        reviewed = runtime.evaluate(reviewed_manifest)
        runtime.review_run(
            reviewed.run_id,
            accepted_review(
                reviewed.case_id,
                reviewed.hypotheses[0].hypothesis_id,
                tuple(item.evidence_id for item in reviewed.evidence),
                "portfolio-review-002",
            ),
        )
        return runtime, pending, reviewed

    def test_portfolio_reconciles_review_workspace_and_release_states(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, pending, reviewed = self._runtime_with_lifecycle(directory)
            portfolio = build_run_portfolio(runtime, as_of=AS_OF)
            self.assertTrue(portfolio.accepted)
            self.assertEqual(portfolio.total_count, 2)
            self.assertEqual(len(portfolio.rows), 2)
            self.assertEqual(portfolio.counts["release_ready"], 1)
            self.assertEqual(portfolio.counts["release_blocked"], 1)
            self.assertEqual(portfolio.counts["integrity_accepted"], 2)
            self.assertEqual(portfolio.counts["workspace_accepted"], 2)
            by_run = {row.run_id: row for row in portfolio.rows}
            self.assertFalse(by_run[pending.run_id].release_ready)
            self.assertEqual(by_run[pending.run_id].release_state, "blocked")
            self.assertIn("review-accepted", by_run[pending.run_id].release_failed_check_ids)
            self.assertTrue(by_run[reviewed.run_id].release_ready)
            self.assertEqual(by_run[reviewed.run_id].review_state, "accepted")
            self.assertEqual(by_run[reviewed.run_id].due_state, "completed")

    def test_portfolio_is_deterministic_and_filters_operationally(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, pending, reviewed = self._runtime_with_lifecycle(directory)
            first = build_run_portfolio(runtime, as_of=AS_OF)
            second = build_run_portfolio(runtime, as_of=AS_OF)
            self.assertEqual(first.to_dict(), second.to_dict())
            ready = build_run_portfolio(
                runtime,
                as_of=AS_OF,
                release_ready_only=True,
            )
            self.assertEqual([row.run_id for row in ready.rows], [reviewed.run_id])
            completed = build_run_portfolio(runtime, as_of=AS_OF, due_state="completed")
            self.assertEqual([row.run_id for row in completed.rows], [reviewed.run_id])
            blocked = build_run_portfolio(runtime, as_of=AS_OF, release_state="blocked")
            self.assertEqual([row.run_id for row in blocked.rows], [pending.run_id])
            searched = build_run_portfolio(runtime, as_of=AS_OF, text="portfolio-case-002")
            self.assertEqual([row.run_id for row in searched.rows], [reviewed.run_id])
            with self.assertRaises(ValidationError):
                build_run_portfolio(runtime, as_of=AS_OF, due_state="unknown")
            with self.assertRaises(ValidationError):
                build_run_portfolio(runtime, as_of=AS_OF, release_state="unknown")
            with self.assertRaises(ValidationError):
                build_run_portfolio(runtime, as_of=AS_OF, limit=101)

    def test_portfolio_closure_is_complete_and_public(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _, _ = self._runtime_with_lifecycle(directory)
            closure = build_run_portfolio_closure(runtime, as_of=AS_OF)
            self.assertTrue(closure["complete"])
            self.assertTrue(closure["accepted"])
            self.assertFalse(closure["has_more"])
            self.assertIsNone(closure["limit"])
            self.assertEqual(closure["count"], 2)
            self.assertTrue(closure["content_address"].startswith("run-portfolio-closure:"))
            serialized = json.dumps(closure, sort_keys=True).lower()
            for forbidden in (
                "subject_id",
                "sample_id",
                "agent_id",
                "agent_name",
                "assistant_id",
                "generated_by",
                "model_name",
                "author_name",
                "programming_language",
            ):
                self.assertNotIn(forbidden, serialized)

    def test_corrupt_run_remains_visible_but_blocks_portfolio_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, pending, _ = self._runtime_with_lifecycle(directory)
            run_record = runtime.get_run(pending.run_id)
            event_address = str(run_record["event_address"]).split(":", 1)[1]
            event_path = runtime.store.store.objects / f"{event_address}.json"
            event = json.loads(event_path.read_text(encoding="utf-8"))
            event["events"][1]["event_hash"] = "sha256:portfolio-tampered"
            event_path.write_text(json.dumps(event), encoding="utf-8")

            portfolio = build_run_portfolio(runtime, as_of=AS_OF)
            row = next(item for item in portfolio.rows if item.run_id == pending.run_id)
            self.assertFalse(portfolio.accepted)
            self.assertFalse(row.accepted)
            self.assertFalse(row.integrity_accepted)
            self.assertEqual(row.workspace_state, "blocked")
            self.assertEqual(row.release_state, "blocked")
            self.assertTrue(row.warnings)

    def test_cli_and_http_surfaces_return_the_same_portfolio_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _, _ = self._runtime_with_lifecycle(directory)
            page_path = Path(directory) / "portfolio.json"
            closure_path = Path(directory) / "portfolio-closure.json"
            self.assertEqual(
                main(
                    [
                        "run-portfolio",
                        "--data-root",
                        directory,
                        "--as-of",
                        AS_OF,
                        "--output",
                        str(page_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "run-portfolio",
                        "--data-root",
                        directory,
                        "--closure",
                        "--as-of",
                        AS_OF,
                        "--output",
                        str(closure_path),
                    ]
                ),
                0,
            )
            page = json.loads(page_path.read_text(encoding="utf-8"))
            closure = json.loads(closure_path.read_text(encoding="utf-8"))
            self.assertTrue(page["accepted"])
            self.assertEqual(page["total_count"], 2)
            self.assertTrue(closure["complete"])
            self.assertEqual(closure["count"], 2)

            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                connection.request("GET", f"/v1/portfolio?as_of={AS_OF}")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                api_page = json.loads(response.read())
                self.assertTrue(api_page["accepted"])
                self.assertEqual(api_page["content_address"], page["content_address"])

                connection.request("GET", f"/v1/portfolio/closure?as_of={AS_OF}")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                api_closure = json.loads(response.read())
                self.assertTrue(api_closure["complete"])
                self.assertEqual(api_closure["content_address"], closure["content_address"])

                connection.request("GET", "/v1/portfolio?due_state=not-a-state")
                response = connection.getresponse()
                self.assertEqual(response.status, 422)
                self.assertEqual(json.loads(response.read())["error"], "validation_error")
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
