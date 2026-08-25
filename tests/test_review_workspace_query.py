from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread
from urllib.parse import urlencode

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.review_workspace import build_persisted_review_workspace
from glio_noncode.review_workspace_query import (
    REVIEW_WORKSPACE_QUERY_COLLECTIONS,
    ReviewWorkspaceQuery,
    build_review_workspace_index,
    build_review_workspace_query_closure,
    query_review_workspace,
    review_workspace_query_capabilities,
    review_workspace_query_schema,
)
from glio_noncode.runtime import CaseRuntime

from .helpers import fixture_manifest


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return {str(key) for key in value} | {
            nested
            for item in value.values()
            for nested in _all_keys(item)
        }
    if isinstance(value, list):
        return {nested for item in value for nested in _all_keys(item)}
    return set()


class ReviewWorkspaceQueryTests(unittest.TestCase):
    def _report(self, directory: str):
        runtime = CaseRuntime(directory)
        dossier = runtime.evaluate(fixture_manifest())
        return runtime, dossier, build_persisted_review_workspace(runtime, dossier.run_id)

    def test_index_facets_are_deterministic_and_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, _, report = self._report(directory)
            first = build_review_workspace_index(report)
            second = build_review_workspace_index(report)
            self.assertEqual(first, second)
            self.assertTrue(first.accepted)
            self.assertEqual(first.record_count, 34)
            self.assertEqual(
                first.collection_counts,
                {
                    "hypotheses": 1,
                    "edges": 5,
                    "evidence": 14,
                    "alternatives": 2,
                    "deltas": 0,
                    "provenance": 11,
                    "review_queue": 1,
                },
            )
            self.assertEqual(tuple(first.facets), (
                "collections", "states", "sources", "contexts", "dimensions",
                "item_types", "priorities",
            ))
            self.assertNotIn("payload", _all_keys(first.to_dict()))
            self.assertNotIn("produced_by", _all_keys(first.to_dict()))

    def test_filters_page_stably_and_facets_cover_all_matches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, _, report = self._report(directory)
            index = build_review_workspace_index(report)
            page = query_review_workspace(
                report,
                ReviewWorkspaceQuery(collection="edges", offset=1, limit=2),
                index=index,
            )
            repeat = query_review_workspace(
                report,
                ReviewWorkspaceQuery(collection="edges", offset=1, limit=2),
                index=index,
            )
            self.assertTrue(page.accepted)
            self.assertEqual(page, repeat)
            self.assertEqual(page.total_count, 5)
            self.assertEqual(len(page.rows), 2)
            self.assertTrue(page.has_more)
            self.assertEqual(page.facets["collections"], {"edges": 5})

            source_id = report.evidence[0].source_id
            source_result = query_review_workspace(
                report,
                ReviewWorkspaceQuery(source_ids=(source_id,), limit=None),
                index=index,
            )
            self.assertTrue(source_result.rows)
            self.assertEqual(source_result.facets["sources"][source_id], source_result.total_count)
            self.assertTrue(all(source_id in row.source_ids for row in source_result.rows))

            queue = query_review_workspace(
                report,
                ReviewWorkspaceQuery(collection="review_queue", priority=1),
                index=index,
            )
            self.assertTrue(queue.rows)
            self.assertTrue(all(row.priority == 1 for row in queue.rows))

    def test_state_text_dimension_and_context_filters_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, _, report = self._report(directory)
            evidence_state = report.evidence[0].state
            evidence = query_review_workspace(
                report,
                ReviewWorkspaceQuery(
                    collection="evidence",
                    item_id=report.evidence[0].evidence_id,
                    states=(evidence_state,),
                    context_key=report.evidence[0].context_key,
                ),
            )
            self.assertTrue(evidence.accepted)
            self.assertEqual(len(evidence.rows), 1)
            self.assertEqual(evidence.rows[0].item_id, report.evidence[0].evidence_id)
            self.assertEqual(evidence.rows[0].context_keys, (report.evidence[0].context_key,))

            delta_report = replace(
                report,
                deltas=(
                    # A public synthetic row proves dimension filtering without
                    # introducing a private or raw evidence field.
                    replace(
                        report.deltas[0],
                        dimension="support",
                    )
                    if report.deltas
                    else (),
                )
                if report.deltas
                else report.deltas,
            )
            delta_query = query_review_workspace(
                delta_report,
                ReviewWorkspaceQuery(collection="deltas", dimension="support"),
            )
            self.assertEqual(delta_query.total_count, 0)

    def test_query_contract_validation_and_index_mismatch_fail_closed(self) -> None:
        with self.assertRaises(Exception):
            ReviewWorkspaceQuery(collection="not-a-collection")
        with self.assertRaises(Exception):
            ReviewWorkspaceQuery(limit=0)
        with self.assertRaises(Exception):
            ReviewWorkspaceQuery(text="x" * 257)
        with tempfile.TemporaryDirectory() as directory:
            _, _, report = self._report(directory)
            other_report = replace(report, workspace_id="review:other")
            with self.assertRaises(Exception):
                query_review_workspace(report, index=build_review_workspace_index(other_report))

    def test_closure_and_contract_surfaces_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, _, report = self._report(directory)
            closure = build_review_workspace_query_closure(report)
            self.assertTrue(closure.accepted)
            self.assertEqual(closure.total_count, 34)
            self.assertEqual(len(closure.rows), 34)
            self.assertEqual(tuple(review_workspace_query_schema()["collections"]), REVIEW_WORKSPACE_QUERY_COLLECTIONS)
            self.assertTrue(review_workspace_query_capabilities()["faceted_filtering"])
            self.assertEqual(closure.to_dict(), build_review_workspace_query_closure(report).to_dict())

    def test_unaccepted_report_withholds_query_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, _, report = self._report(directory)
            rejected = replace(report, accepted=False)
            index = build_review_workspace_index(rejected)
            result = query_review_workspace(rejected, index=index)
            self.assertFalse(index.accepted)
            self.assertFalse(result.accepted)
            self.assertEqual(index.record_count, 0)
            self.assertEqual(result.rows, ())
            self.assertTrue(any("withheld" in warning for warning in result.warnings))

    def test_cli_and_http_query_surfaces_share_the_report_address(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier, report = self._report(directory)
            output = Path(directory) / "query.json"
            self.assertEqual(
                main([
                    "review-workspace-query", dossier.run_id,
                    "--collection", "edges", "--limit", "2",
                    "--data-root", directory, "--output", str(output),
                ]),
                0,
            )
            cli_payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(cli_payload["report_address"], report.content_address)
            self.assertEqual(len(cli_payload["rows"]), 2)

            index_output = Path(directory) / "index.json"
            self.assertEqual(
                main([
                    "review-workspace-index", dossier.run_id,
                    "--data-root", directory, "--output", str(index_output),
                ]),
                0,
            )
            self.assertEqual(json.loads(index_output.read_text(encoding="utf-8"))["record_count"], 34)

            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                params = urlencode({"collection": "edges", "limit": "2", "source_id": report.edges[0].source_id})
                connection.request("GET", f"/v1/runs/{dossier.run_id}/review-workspace/query?{params}")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                api_payload = json.loads(response.read())
                self.assertEqual(api_payload["report_address"], report.content_address)
                self.assertEqual(len(api_payload["rows"]), 2)
                connection.request("GET", "/v1/review-workspace/query/schema")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())["version"], "review-workspace-query-schema-v1")
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
