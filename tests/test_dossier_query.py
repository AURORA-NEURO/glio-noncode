"""Contract tests for dossier summaries, evidence queries, and lineage."""

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
from glio_noncode.dossier_query import (
    DOSSIER_QUERY_MAX_LIMIT,
    build_dossier_lineage,
    build_dossier_query_closure,
    query_dossier,
    query_persisted_dossier,
    summarize_dossier,
    summarize_persisted_dossier,
)
from glio_noncode.errors import ValidationError
from glio_noncode.runtime import CaseRuntime

from .helpers import fixture_manifest


class DossierQueryTests(unittest.TestCase):
    def test_summary_preserves_counts_and_review_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dossier = CaseRuntime(directory).evaluate(fixture_manifest())
            summary = summarize_dossier(dossier)
            self.assertTrue(summary.accepted)
            self.assertEqual(summary.hypothesis_count, len(dossier.hypotheses))
            self.assertEqual(summary.edge_count, sum(len(item.edges) for item in dossier.hypotheses))
            self.assertEqual(summary.evidence_count, len(dossier.evidence))
            self.assertEqual(sum(summary.evidence_state_counts.values()), len(dossier.evidence))
            self.assertFalse(summary.is_releasable)

    def test_bounded_queries_cover_all_dossier_planes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            hypotheses = query_dossier(dossier, "hypotheses", limit=1)
            evidence = query_dossier(dossier, "evidence", text="", limit=DOSSIER_QUERY_MAX_LIMIT)
            experiments = query_dossier(dossier, "experiments", limit=DOSSIER_QUERY_MAX_LIMIT)
            self.assertTrue(hypotheses.accepted)
            self.assertTrue(hypotheses.has_more or hypotheses.total_count <= 1)
            self.assertEqual(evidence.total_count, len(dossier.evidence))
            self.assertEqual(experiments.total_count, len(dossier.experiments))
            self.assertTrue(all("content_address" in row for row in evidence.rows))
            self.assertEqual(
                query_persisted_dossier(runtime, dossier.run_id, "hypotheses").total_count,
                len(dossier.hypotheses),
            )

    def test_lineage_joins_edges_to_claims_and_detects_missing_references(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dossier = CaseRuntime(directory).evaluate(fixture_manifest())
            lineage = build_dossier_lineage(dossier)
            self.assertTrue(lineage.accepted)
            self.assertEqual(lineage.edge_count, sum(len(item.edges) for item in dossier.hypotheses))
            self.assertGreater(lineage.claim_count, 0)
            self.assertEqual(lineage.missing_claim_ids, ())
            subset = build_dossier_lineage(dossier, hypothesis_id=dossier.hypotheses[0].hypothesis_id)
            self.assertEqual(subset.hypothesis_ids, (dossier.hypotheses[0].hypothesis_id,))
            self.assertTrue(subset.accepted)
            first = dossier.hypotheses[0]
            broken_edge = replace(first.edges[0], claim_ids=first.edges[0].claim_ids + ("missing-claim",))
            broken_hypothesis = replace(first, edges=(broken_edge,) + first.edges[1:])
            broken = replace(dossier, hypotheses=(broken_hypothesis,) + dossier.hypotheses[1:])
            broken_lineage = build_dossier_lineage(broken)
            self.assertFalse(broken_lineage.accepted)
            self.assertEqual(broken_lineage.missing_claim_ids, ("missing-claim",))

    def test_query_closure_contains_all_bounded_planes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dossier = CaseRuntime(directory).evaluate(fixture_manifest())
            closure = build_dossier_query_closure(dossier)
            self.assertTrue(closure["accepted"])
            self.assertTrue(closure["content_address"].startswith("dossier-query-closure:"))
            self.assertEqual(closure["summary"]["evidence_count"], len(dossier.evidence))
            self.assertEqual(closure["hypotheses"]["total_count"], len(dossier.hypotheses))
            self.assertEqual(closure["evidence"]["total_count"], len(dossier.evidence))
            self.assertEqual(closure["experiments"]["total_count"], len(dossier.experiments))
            self.assertTrue(closure["lineage"]["accepted"])

    def test_queries_reject_invalid_bounds_and_states(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dossier = CaseRuntime(directory).evaluate(fixture_manifest())
            with self.assertRaises(ValueError):
                query_dossier(dossier, "evidence", limit=DOSSIER_QUERY_MAX_LIMIT + 1)
            with self.assertRaises(ValueError):
                query_dossier(dossier, "evidence", state="not-a-state")
            with self.assertRaises(ValueError):
                query_dossier(dossier, "unknown")

    def test_persisted_query_requires_replay_integrity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            run_record = runtime.get_run(dossier.run_id)
            event_path = runtime.store.store.objects / f"{run_record['event_address'].split(':', 1)[1]}.json"
            event_record = json.loads(event_path.read_text(encoding="utf-8"))
            event_record["events"][0]["event_hash"] = "sha256:tampered"
            event_path.write_text(json.dumps(event_record), encoding="utf-8")
            with self.assertRaises(ValidationError):
                summarize_persisted_dossier(runtime, dossier.run_id)

    def test_cli_query_commands_write_projections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            summary_path = Path(directory) / "summary.json"
            lineage_path = Path(directory) / "lineage.json"
            closure_path = Path(directory) / "closure.json"
            self.assertEqual(
                main(
                    [
                        "run-query",
                        dossier.run_id,
                        "summary",
                        "--data-root",
                        directory,
                        "--output",
                        str(summary_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "run-query",
                        dossier.run_id,
                        "lineage",
                        "--data-root",
                        directory,
                        "--output",
                        str(lineage_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "run-query",
                        dossier.run_id,
                        "closure",
                        "--data-root",
                        directory,
                        "--output",
                        str(closure_path),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(summary_path.read_text(encoding="utf-8"))["accepted"])
            self.assertTrue(json.loads(lineage_path.read_text(encoding="utf-8"))["accepted"])
            self.assertTrue(json.loads(closure_path.read_text(encoding="utf-8"))["accepted"])

    def test_http_query_routes_and_filters(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                body = json.dumps(fixture_manifest().to_dict()).encode("utf-8")
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

                for resource in ("summary", "hypotheses", "evidence", "experiments", "lineage"):
                    connection.request("GET", f"/v1/runs/{run_id}/{resource}")
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertTrue(json.loads(response.read())["accepted"])

                connection.request("GET", f"/v1/runs/{run_id}/query-closure")
                closure = connection.getresponse()
                self.assertEqual(closure.status, 200)
                self.assertTrue(json.loads(closure.read())["accepted"])

                connection.request("GET", f"/v1/runs/{run_id}/evidence?state=not-a-state")
                invalid = connection.getresponse()
                self.assertEqual(invalid.status, 400)
                self.assertEqual(json.loads(invalid.read())["error"], "invalid_query")

                connection.request("GET", f"/v1/runs/{run_id}/hypotheses?limit=101")
                invalid_limit = connection.getresponse()
                self.assertEqual(invalid_limit.status, 400)
                self.assertEqual(json.loads(invalid_limit.read())["error"], "invalid_query")
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
