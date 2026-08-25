"""Deep tests for replay-gated cross-run search and its public boundaries."""

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
from glio_noncode.run_search import (
    RUN_SEARCH_MAX_LIMIT,
    build_run_search_closure,
    search_persisted_runs,
)
from glio_noncode.runtime import CaseRuntime

from .helpers import fixture_manifest


class RunSearchTests(unittest.TestCase):
    def _runtime_with_two_runs(self, directory: str) -> tuple[CaseRuntime, object, object]:
        runtime = CaseRuntime(directory)
        first = runtime.evaluate(fixture_manifest())
        second = runtime.evaluate(
            replace(
                fixture_manifest(),
                case_id="case-demo-002",
                requested_by="researcher-2",
            )
        )
        return runtime, first, second

    def test_searches_all_public_resource_planes_across_runs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, first, second = self._runtime_with_two_runs(directory)
            hypotheses = search_persisted_runs(
                runtime,
                query="GENE_DEMO_A",
                resource="hypotheses",
            )
            self.assertTrue(hypotheses.accepted)
            self.assertEqual(hypotheses.scanned_run_count, 2)
            self.assertEqual(
                {row.case_id for row in hypotheses.rows},
                {first.case_id, second.case_id},
            )
            self.assertTrue(all(row.resource == "hypotheses" for row in hypotheses.rows))

            evidence = search_persisted_runs(
                runtime,
                resource="evidence",
                state="supported",
                tier="computed",
                channel="motif_delta",
            )
            self.assertTrue(evidence.accepted)
            self.assertEqual({row.payload["channel"] for row in evidence.rows}, {"motif_delta"})
            self.assertEqual({row.payload["state"] for row in evidence.rows}, {"supported"})

            review = ReviewDecision(
                review_id="review-search-1",
                case_id=first.case_id,
                reviewer="scientific-reviewer",
                state=ReviewState.ACCEPTED,
                reviewed_hypothesis_ids=(first.hypotheses[0].hypothesis_id,),
                rationale="The search projection retains the research-only review boundary.",
                checked_claim_ids=tuple(item.evidence_id for item in first.evidence),
            )
            runtime.review_run(first.run_id, review)
            reviews = search_persisted_runs(
                runtime,
                query="scientific-reviewer",
                resource="reviews",
                reviewer="scientific-reviewer",
                review_state="accepted",
            )
            self.assertTrue(reviews.accepted)
            self.assertEqual(reviews.total_count, 1)
            self.assertEqual(reviews.rows[0].record_id, review.review_id)

            experiments = search_persisted_runs(
                runtime,
                resource="experiments",
                assay="rna_measurement",
            )
            self.assertEqual(experiments.total_count, 2)
            self.assertTrue(
                all(row.payload["assay"] == "rna_measurement" for row in experiments.rows)
            )

    def test_filters_pagination_and_ranking_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, first, _ = self._runtime_with_two_runs(directory)
            kwargs = {
                "runtime": runtime,
                "resource": "all",
                "case_id": first.case_id,
                "min_support": 0.0,
                "max_uncertainty": 1.0,
                "limit": 3,
            }
            page = search_persisted_runs(**kwargs)
            repeated = search_persisted_runs(**kwargs)
            self.assertTrue(page.accepted)
            self.assertEqual(page.to_dict(), repeated.to_dict())
            self.assertEqual(page.total_count, 17)
            self.assertEqual(len(page.rows), 3)
            self.assertTrue(page.has_more)
            self.assertEqual(
                [row.resource for row in page.rows],
                ["runs", "hypotheses", "evidence"],
            )

            second_page = search_persisted_runs(**(kwargs | {"offset": 3}))
            self.assertEqual(second_page.rows[0].resource, "evidence")
            self.assertNotEqual(page.rows[0].record_id, second_page.rows[0].record_id)

            closure = build_run_search_closure(
                runtime,
                resource="experiments",
                case_id=first.case_id,
            )
            self.assertTrue(closure["accepted"])
            self.assertFalse(closure["page"]["has_more"])
            self.assertEqual(closure["page"]["total_count"], 1)
            self.assertTrue(closure["content_address"].startswith("run-search-closure:"))

    def test_corrupt_runs_are_blocked_and_never_scientific_hits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            run_record = runtime.get_run(dossier.run_id)
            event_address = run_record["event_address"].split(":", 1)[1]
            event_path = runtime.store.store.objects / f"{event_address}.json"
            event_record = json.loads(event_path.read_text(encoding="utf-8"))
            event_record["events"][1]["event_hash"] = "sha256:corrupted-search"
            event_path.write_text(json.dumps(event_record), encoding="utf-8")

            blocked = search_persisted_runs(runtime, query="blocked", resource="all")
            self.assertFalse(blocked.accepted)
            self.assertEqual(blocked.blocked_run_count, 1)
            self.assertEqual(blocked.total_count, 1)
            self.assertEqual(blocked.rows[0].status, "blocked")
            self.assertFalse(blocked.rows[0].accepted)

            scientific = search_persisted_runs(runtime, resource="hypotheses")
            self.assertFalse(scientific.accepted)
            self.assertEqual(scientific.blocked_run_count, 1)
            self.assertEqual(scientific.total_count, 0)

            accepted_only = search_persisted_runs(runtime, resource="all", accepted_only=True)
            self.assertFalse(accepted_only.accepted)
            self.assertEqual(accepted_only.total_count, 0)

    def test_closure_is_complete_addressed_and_public(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, _, _ = self._runtime_with_two_runs(directory)
            closure = build_run_search_closure(runtime, resource="all")
            payload = json.dumps(closure, sort_keys=True).lower()
            self.assertTrue(closure["accepted"])
            self.assertFalse(closure["page"]["has_more"])
            self.assertEqual(closure["page"]["scanned_run_count"], 2)
            self.assertEqual(closure["page"]["blocked_run_count"], 0)
            self.assertNotIn("agent_id", payload)
            self.assertNotIn("agent_name", payload)
            self.assertNotIn("assistant_id", payload)
            self.assertNotIn("assistant_name", payload)
            self.assertNotIn("generated_by", payload)
            self.assertNotIn("model_name", payload)
            self.assertNotIn("author_name", payload)
            self.assertNotIn("programming_language", payload)

    def test_invalid_filters_and_bounds_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            runtime.evaluate(fixture_manifest())
            with self.assertRaises(ValidationError):
                search_persisted_runs(runtime, resource="not-a-resource")
            with self.assertRaises(ValidationError):
                search_persisted_runs(runtime, limit=RUN_SEARCH_MAX_LIMIT + 1)
            with self.assertRaises(ValidationError):
                search_persisted_runs(runtime, min_support=1.01)
            with self.assertRaises(ValidationError):
                search_persisted_runs(runtime, resource="evidence", state="not-an-evidence-state")
            with self.assertRaises(ValidationError):
                search_persisted_runs(runtime, resource="experiments", assay="not-an-assay")

    def test_cli_and_http_surfaces_return_search_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            cli_path = Path(directory) / "search.json"
            closure_path = Path(directory) / "search-closure.json"
            self.assertEqual(
                main(
                    [
                        "run-search",
                        "--data-root",
                        directory,
                        "--query",
                        "GENE_DEMO_A",
                        "--resource",
                        "hypotheses",
                        "--output",
                        str(cli_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "run-search",
                        "--data-root",
                        directory,
                        "--resource",
                        "evidence",
                        "--state",
                        "supported",
                        "--closure",
                        "--output",
                        str(closure_path),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(cli_path.read_text(encoding="utf-8"))["accepted"])
            self.assertFalse(json.loads(closure_path.read_text(encoding="utf-8"))["page"]["has_more"])

            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                connection.request("GET", "/v1/search?q=GENE_DEMO_A&resource=hypotheses")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                result = json.loads(response.read())
                self.assertEqual(result["total_count"], 1)
                self.assertEqual(result["rows"][0]["case_id"], dossier.case_id)

                connection.request("GET", "/v1/search/closure?resource=evidence&state=supported")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertFalse(json.loads(response.read())["page"]["has_more"])

                connection.request("GET", "/v1/search?resource=not-a-resource")
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
