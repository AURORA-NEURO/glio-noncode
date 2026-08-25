"""Deep tests for persisted-run cataloging and service inspection routes."""

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
from glio_noncode.run_catalog import (
    RUN_CATALOG_MAX_LIMIT,
    build_run_catalog_closure,
    build_run_catalog_page,
    get_run_dossier,
    get_run_events,
    inspect_run,
)
from glio_noncode.runtime import CaseRuntime

from .helpers import fixture_manifest


class RunCatalogTests(unittest.TestCase):
    def _runtime_with_two_runs(self, directory: str) -> tuple[CaseRuntime, str, str]:
        runtime = CaseRuntime(directory)
        first = runtime.evaluate(fixture_manifest())
        second = runtime.evaluate(
            replace(
                fixture_manifest(),
                case_id="case-demo-002",
                requested_by="researcher-2",
            )
        )
        return runtime, first.run_id, second.run_id

    def test_catalog_pages_are_bounded_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, first_id, second_id = self._runtime_with_two_runs(directory)
            page = build_run_catalog_page(runtime, limit=1)
            self.assertTrue(page.accepted)
            self.assertEqual(page.total_count, 2)
            self.assertEqual(len(page.rows), 1)
            self.assertTrue(page.has_more)
            self.assertEqual(page.rows[0].run_id, min(first_id, second_id))
            next_page = build_run_catalog_page(runtime, offset=1, limit=1)
            self.assertFalse(next_page.has_more)
            self.assertEqual(next_page.rows[0].run_id, max(first_id, second_id))
            filtered = build_run_catalog_page(runtime, case_id="case-demo-002")
            self.assertEqual(filtered.total_count, 1)
            self.assertEqual(filtered.rows[0].case_id, "case-demo-002")

    def test_inspection_reopens_dossier_events_and_replay_integrity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, run_id, _ = self._runtime_with_two_runs(directory)
            inspection = inspect_run(runtime, run_id)
            self.assertTrue(inspection.accepted)
            self.assertTrue(inspection.replay.event_chain_valid)
            self.assertTrue(inspection.replay.stored_dossier_matches_address)
            self.assertGreaterEqual(inspection.summary.event_count, 4)
            self.assertEqual(get_run_dossier(runtime, run_id)["run_id"], run_id)
            events = get_run_events(runtime, run_id)
            self.assertEqual(events["run_id"], run_id)
            self.assertEqual(len(events["events"]), inspection.summary.event_count)
            self.assertTrue(events["accepted"])

    def test_existing_corruption_is_reported_without_being_promoted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            run_record = runtime.get_run(dossier.run_id)
            event_path = runtime.store.store.objects / f"{run_record['event_address'].split(':', 1)[1]}.json"
            event_record = json.loads(event_path.read_text(encoding="utf-8"))
            event_record["events"][1]["event_hash"] = "sha256:corrupted"
            event_path.write_text(json.dumps(event_record), encoding="utf-8")
            inspection = inspect_run(runtime, dossier.run_id)
            self.assertFalse(inspection.accepted)
            self.assertFalse(inspection.replay.event_chain_valid)
            self.assertTrue(inspection.replay.warnings)
            self.assertFalse(get_run_events(runtime, dossier.run_id)["accepted"])
            with self.assertRaises(ValidationError):
                runtime.review_run(
                    dossier.run_id,
                    ReviewDecision(
                        review_id="review-corrupted-1",
                        case_id=dossier.case_id,
                        reviewer="scientific-reviewer",
                        state=ReviewState.ACCEPTED,
                        reviewed_hypothesis_ids=(dossier.hypotheses[0].hypothesis_id,),
                        rationale="This review must not promote a corrupted run.",
                        checked_claim_ids=tuple(item.evidence_id for item in dossier.evidence),
                    ),
                )

    def test_persisted_run_can_be_reviewed_into_a_new_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            original = runtime.evaluate(fixture_manifest())
            review = ReviewDecision(
                review_id="review-persisted-1",
                case_id=original.case_id,
                reviewer="scientific-reviewer",
                state=ReviewState.ACCEPTED,
                reviewed_hypothesis_ids=(original.hypotheses[0].hypothesis_id,),
                rationale="Reviewed the persisted evidence and retained the research-only boundary.",
                checked_claim_ids=tuple(item.evidence_id for item in original.evidence),
            )
            released = runtime.review_run(original.run_id, review)
            self.assertTrue(released.is_releasable)
            self.assertNotEqual(released.content_address, original.content_address)
            inspection = inspect_run(runtime, original.run_id)
            self.assertTrue(inspection.summary.is_releasable)
            self.assertEqual(inspection.dossier_record["review"]["review_id"], review.review_id)

    def test_catalog_rejects_unbounded_pagination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            with self.assertRaises(ValueError):
                build_run_catalog_page(runtime, limit=RUN_CATALOG_MAX_LIMIT + 1)
            with self.assertRaises(ValueError):
                build_run_catalog_page(runtime, offset=-1)

    def test_closure_contains_every_persisted_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _, _ = self._runtime_with_two_runs(directory)
            closure = build_run_catalog_closure(runtime)
            self.assertTrue(closure["accepted"])
            self.assertEqual(closure["page"]["total_count"], 2)
            self.assertEqual(len(closure["inspections"]), 2)
            self.assertTrue(closure["content_address"].startswith("run-catalog-closure:"))
            self.assertNotIn("agent_id", json.dumps(closure).lower())
            self.assertNotIn("model_name", json.dumps(closure).lower())

    def test_cli_catalog_and_inspection_commands_write_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            catalog_path = Path(directory) / "catalog.json"
            inspection_path = Path(directory) / "inspection.json"
            review_path = Path(directory) / "review.json"
            reviewed_path = Path(directory) / "reviewed.json"
            review_path.write_text(
                json.dumps(
                    {
                        "review_id": "review-cli-1",
                        "case_id": dossier.case_id,
                        "reviewer": "scientific-reviewer",
                        "state": "accepted",
                        "reviewed_hypothesis_ids": [dossier.hypotheses[0].hypothesis_id],
                        "rationale": "The CLI review preserves the research-only boundary.",
                        "checked_claim_ids": [item.evidence_id for item in dossier.evidence],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                main(
                    [
                        "run-catalog",
                        "--data-root",
                        directory,
                        "--output",
                        str(catalog_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "run-inspect",
                        dossier.run_id,
                        "--data-root",
                        directory,
                        "--output",
                        str(inspection_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "run-review",
                        dossier.run_id,
                        str(review_path),
                        "--data-root",
                        directory,
                        "--output",
                        str(reviewed_path),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(catalog_path.read_text(encoding="utf-8"))["accepted"])
            self.assertTrue(json.loads(inspection_path.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(
                json.loads(reviewed_path.read_text(encoding="utf-8"))["status"],
                "released_research",
            )

    def test_http_routes_expose_catalog_and_replay_views(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                manifest = fixture_manifest().to_dict()
                body = json.dumps(manifest).encode("utf-8")
                connection.request(
                    "POST",
                    "/v1/evaluate",
                    body=body,
                    headers={"Content-Type": "application/json"},
                )
                evaluated = connection.getresponse()
                self.assertEqual(evaluated.status, 200)
                dossier = json.loads(evaluated.read())
                run_id = dossier["run_id"]

                connection.request("GET", "/v1/runs?limit=1")
                catalog = connection.getresponse()
                self.assertEqual(catalog.status, 200)
                catalog_payload = json.loads(catalog.read())
                self.assertEqual(catalog_payload["total_count"], 1)
                self.assertEqual(catalog_payload["rows"][0]["run_id"], run_id)

                connection.request("GET", f"/v1/runs/{run_id}")
                summary = connection.getresponse()
                self.assertEqual(summary.status, 200)
                self.assertEqual(json.loads(summary.read())["run_id"], run_id)

                connection.request("GET", f"/v1/runs/{run_id}/events")
                events = connection.getresponse()
                self.assertEqual(events.status, 200)
                self.assertTrue(json.loads(events.read())["accepted"])

                connection.request("GET", f"/v1/runs/{run_id}/dossier")
                stored_dossier = connection.getresponse()
                self.assertEqual(stored_dossier.status, 200)
                self.assertEqual(json.loads(stored_dossier.read())["content_address"], dossier["content_address"])

                connection.request("GET", f"/v1/runs/{run_id}/replay")
                replay = connection.getresponse()
                self.assertEqual(replay.status, 200)
                self.assertTrue(json.loads(replay.read())["accepted"])

                connection.request("GET", f"/v1/runs/{run_id}/inspection")
                inspection = connection.getresponse()
                self.assertEqual(inspection.status, 200)
                inspection_payload = json.loads(inspection.read())
                self.assertEqual(inspection_payload["summary"]["run_id"], run_id)
                self.assertTrue(inspection_payload["accepted"])

                review_body = json.dumps(
                    {
                        "review_id": "review-http-1",
                        "case_id": dossier["case_id"],
                        "reviewer": "scientific-reviewer",
                        "state": "accepted",
                        "reviewed_hypothesis_ids": [dossier["hypotheses"][0]["hypothesis_id"]],
                        "rationale": "The persisted research object was reviewed with its limitations retained.",
                        "checked_claim_ids": [item["evidence_id"] for item in dossier["evidence"]],
                    }
                ).encode("utf-8")
                connection.request(
                    "POST",
                    f"/v1/runs/{run_id}/review",
                    body=review_body,
                    headers={"Content-Type": "application/json"},
                )
                reviewed = connection.getresponse()
                self.assertEqual(reviewed.status, 200)
                reviewed_dossier = json.loads(reviewed.read())
                self.assertEqual(reviewed_dossier["status"], "released_research")
                self.assertTrue(reviewed_dossier["review"]["state"] == "accepted")

                connection.request("GET", "/v1/runs?limit=101")
                invalid = connection.getresponse()
                self.assertEqual(invalid.status, 400)
                self.assertEqual(json.loads(invalid.read())["error"], "invalid_query")

                connection.request("GET", "/v1/runs/run-does-not-exist")
                missing = connection.getresponse()
                self.assertEqual(missing.status, 404)
                self.assertEqual(json.loads(missing.read())["error"], "not_found")
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
