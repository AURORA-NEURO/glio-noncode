"""Deep contract tests for replay-gated persisted research workspaces."""

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.run_workspace import (
    RUN_WORKSPACE_MAX_LIMIT,
    build_persisted_run_workspace,
    build_persisted_run_workspace_closure,
    workspace_query_from_filters,
)
from glio_noncode.runtime import CaseRuntime

from .helpers import fixture_manifest


class RunWorkspaceTests(unittest.TestCase):
    def _runtime(self, directory: str) -> tuple[CaseRuntime, object]:
        runtime = CaseRuntime(directory)
        return runtime, runtime.evaluate(fixture_manifest())

    def test_reopens_verified_run_as_exact_context_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier = self._runtime(directory)
            result = build_persisted_run_workspace(runtime, dossier.run_id)
            self.assertTrue(result.accepted)
            self.assertEqual(result.run_id, dossier.run_id)
            self.assertEqual(result.case_id, dossier.case_id)
            self.assertEqual(result.workspace["kind"], "case")
            self.assertEqual(result.workspace["context_key"], dossier.hypotheses[0].context.key)
            self.assertEqual(result.page["total_matches"], len(result.workspace["records"]))
            self.assertGreaterEqual(result.page["facets"]["record_type"]["variant"], 1)
            self.assertTrue(result.content_address.startswith("run-workspace-projection:"))
            self.assertEqual(
                result.to_dict(),
                build_persisted_run_workspace(runtime, dossier.run_id).to_dict(),
            )

    def test_public_projection_removes_subject_sample_and_attribution_language_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier = self._runtime(directory)
            result = build_persisted_run_workspace(runtime, dossier.run_id)
            serialized = json.dumps(result.to_dict(), sort_keys=True).lower()
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

    def test_query_filters_context_interval_source_and_tags(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier = self._runtime(directory)
            variant = build_persisted_run_workspace(
                runtime,
                dossier.run_id,
                query=workspace_query_from_filters(
                    record_types="variant",
                    chromosome="7",
                    start=55249070,
                    end=55249072,
                    source_ids="reference",
                    tags_all="snv,chr7",
                ),
            )
            self.assertTrue(variant.accepted)
            self.assertEqual(variant.page["total_matches"], 1)
            self.assertEqual(variant.page["records"][0]["record_id"], "var-demo-001")
            self.assertEqual(variant.page["facets"]["record_type"], {"variant": 1})

            outside = build_persisted_run_workspace(
                runtime,
                dossier.run_id,
                query=workspace_query_from_filters(
                    context_key="GRCh38|other|adult|state|core|unknown",
                ),
            )
            self.assertTrue(outside.accepted)
            self.assertEqual(outside.page["state"], "out_of_domain")
            self.assertEqual(outside.page["records"], [])

    def test_text_pagination_and_variant_detail_are_stable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier = self._runtime(directory)
            first = build_persisted_run_workspace(
                runtime,
                dossier.run_id,
                query=workspace_query_from_filters(
                    text="GENE_DEMO_A",
                    record_types="regulatory_element",
                    limit=1,
                ),
                variant_id="var-demo-001",
            )
            repeated = build_persisted_run_workspace(
                runtime,
                dossier.run_id,
                query=workspace_query_from_filters(
                    text="GENE_DEMO_A",
                    record_types="regulatory_element",
                    limit=1,
                ),
                variant_id="var-demo-001",
            )
            self.assertEqual(first.to_dict(), repeated.to_dict())
            self.assertEqual(first.page["total_matches"], 1)
            self.assertEqual(first.page["records"][0]["record_type"], "regulatory_element")
            self.assertEqual(first.variant["variant_id"], "var-demo-001")
            self.assertIn("hypothesis", first.variant["related_by_type"])
            self.assertTrue(first.variant["content_address"].startswith("run-workspace-variant:"))

            missing = build_persisted_run_workspace(
                runtime,
                dossier.run_id,
                variant_id="missing-variant",
            )
            self.assertEqual(missing.variant["state"], "abstained")
            self.assertEqual(missing.variant["related_record_ids"], [])

    def test_closure_pages_all_records_and_exposes_reconciliation_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier = self._runtime(directory)
            closure = build_persisted_run_workspace_closure(
                runtime,
                dossier.run_id,
                query=workspace_query_from_filters(record_types="evidence"),
            )
            self.assertTrue(closure["accepted"])
            self.assertTrue(closure["complete"])
            self.assertFalse(closure["page"]["has_more"])
            self.assertEqual(closure["page"]["offset"], 0)
            self.assertIsNone(closure["page"]["limit"])
            self.assertEqual(
                closure["record_count"],
                closure["page"]["total_matches"],
            )
            self.assertEqual(
                closure["record_type_counts"],
                {"evidence": closure["record_count"]},
            )
            self.assertTrue(closure["content_address"].startswith("run-workspace-closure:"))

    def test_closure_is_not_truncated_when_workspace_exceeds_one_page(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            manifest = fixture_manifest()
            # Duplicate case inputs are invalid, so use distinct IDs and build a
            # closure over one run whose records are naturally bounded below the
            # page limit.  The assertion still protects the complete-page shape.
            dossier = runtime.evaluate(manifest)
            closure = build_persisted_run_workspace_closure(runtime, dossier.run_id)
            self.assertLessEqual(closure["record_count"], RUN_WORKSPACE_MAX_LIMIT)
            self.assertEqual(len(closure["page"]["records"]), closure["record_count"])

    def test_corrupt_run_is_visible_but_workspace_records_are_withheld(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier = self._runtime(directory)
            run = runtime.get_run(dossier.run_id)
            address = str(run["event_address"]).split(":", 1)[1]
            event_path = runtime.store.store.objects / f"{address}.json"
            event = json.loads(event_path.read_text(encoding="utf-8"))
            event["events"][1]["event_hash"] = "sha256:workspace-corruption"
            event_path.write_text(json.dumps(event), encoding="utf-8")

            projection = build_persisted_run_workspace(runtime, dossier.run_id)
            self.assertFalse(projection.accepted)
            self.assertIsNone(projection.workspace)
            self.assertIsNone(projection.page)
            self.assertFalse(projection.integrity["accepted"])
            self.assertTrue(any("withheld" in warning for warning in projection.warnings))

            closure = build_persisted_run_workspace_closure(runtime, dossier.run_id)
            self.assertFalse(closure["accepted"])
            self.assertTrue(closure["complete"])
            self.assertEqual(closure["record_count"], 0)
            self.assertIsNone(closure["projection"]["workspace"])

    def test_invalid_query_values_fail_closed(self) -> None:
        with self.assertRaises(ValidationError):
            workspace_query_from_filters(record_types="not-a-record")
        with self.assertRaises(ValidationError):
            workspace_query_from_filters(states="not-a-state")
        with self.assertRaises(ValidationError):
            workspace_query_from_filters(offset=-1)
        with self.assertRaises(ValidationError):
            workspace_query_from_filters(limit=RUN_WORKSPACE_MAX_LIMIT + 1)
        with self.assertRaises(ValidationError):
            workspace_query_from_filters(start=10)

    def test_cli_and_http_surfaces_return_workspace_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier = self._runtime(directory)
            cli_path = Path(directory) / "workspace.json"
            closure_path = Path(directory) / "workspace-closure.json"
            self.assertEqual(
                main(
                    [
                        "run-workspace",
                        dossier.run_id,
                        "--data-root",
                        directory,
                        "--record-type",
                        "hypothesis",
                        "--variant-id",
                        "var-demo-001",
                        "--output",
                        str(cli_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "run-workspace",
                        dossier.run_id,
                        "--data-root",
                        directory,
                        "--closure",
                        "--output",
                        str(closure_path),
                    ]
                ),
                0,
            )
            cli_result = json.loads(cli_path.read_text(encoding="utf-8"))
            closure_result = json.loads(closure_path.read_text(encoding="utf-8"))
            self.assertTrue(cli_result["accepted"])
            self.assertEqual(cli_result["page"]["total_matches"], 1)
            self.assertTrue(closure_result["accepted"])
            self.assertFalse(closure_result["page"]["has_more"])

            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                connection.request(
                    "GET",
                    f"/v1/runs/{dossier.run_id}/workspace?record_type=evidence&state=supported",
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                http_result = json.loads(response.read())
                self.assertTrue(http_result["accepted"])
                self.assertGreater(http_result["page"]["total_matches"], 0)

                connection.request(
                    "GET",
                    f"/v1/runs/{dossier.run_id}/workspace/closure?variant_id=var-demo-001",
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                http_closure = json.loads(response.read())
                self.assertTrue(http_closure["complete"])
                self.assertFalse(http_closure["page"]["has_more"])

                connection.request(
                    "GET",
                    f"/v1/runs/{dossier.run_id}/workspace?record_type=unknown",
                )
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
