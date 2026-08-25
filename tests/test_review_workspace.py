from __future__ import annotations

import json
import csv
import io
import tempfile
import unittest
from dataclasses import replace
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.review_workspace import (
    ReviewWorkspaceConfig,
    ReviewWorkspaceState,
    build_persisted_review_workspace,
    build_review_workspace,
    review_workspace_capabilities,
    review_workspace_schema,
)
from glio_noncode.review_workspace_exports import (
    build_review_workspace_release,
    render_review_workspace_markdown,
    review_workspace_export_payloads,
    verify_review_workspace_release,
    write_review_workspace_release,
)
from glio_noncode.runtime import CaseRuntime

from .helpers import fixture_manifest


def _keys(value: object) -> set[str]:
    if isinstance(value, dict):
        result = {str(key) for key in value}
        for item in value.values():
            result.update(_keys(item))
        return result
    if isinstance(value, list):
        result: set[str] = set()
        for item in value:
            result.update(_keys(item))
        return result
    return set()


class ReviewWorkspaceTests(unittest.TestCase):
    def _runtime(self, directory: str):
        runtime = CaseRuntime(directory)
        return runtime, runtime.evaluate(fixture_manifest())

    def test_persisted_projection_preserves_edges_alternatives_and_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier = self._runtime(directory)
            report = build_persisted_review_workspace(runtime, dossier.run_id)
            self.assertTrue(report.accepted)
            self.assertEqual(report.state, ReviewWorkspaceState.REVIEW)
            self.assertEqual(len(report.hypotheses), 1)
            self.assertEqual(len(report.edges), 5)
            self.assertEqual(len(report.evidence), 14)
            self.assertEqual(len(report.alternatives), 2)
            self.assertGreaterEqual(len(report.provenance), 1)
            self.assertTrue(report.review_queue)
            self.assertTrue(report.content_address.startswith("review-workspace:"))
            payload = report.to_dict()
            keys = _keys(payload)
            self.assertNotIn("payload", keys)
            self.assertNotIn("produced_by", keys)
            self.assertNotIn("subject_id", keys)
            self.assertNotIn("sample_id", keys)
            self.assertEqual(payload, build_persisted_review_workspace(runtime, dossier.run_id).to_dict())

    def test_deltas_are_per_dimension_and_do_not_collapse_to_one_score(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, dossier = self._runtime(directory)
            hypothesis = dossier.hypotheses[0]
            changed_hypothesis = replace(
                hypothesis,
                support=round(hypothesis.support + 0.1, 6),
                uncertainty=round(max(0.0, hypothesis.uncertainty - 0.1), 6),
            )
            changed = replace(dossier, hypotheses=(changed_hypothesis,))
            report = build_review_workspace(
                changed,
                run_id="current-run",
                baseline_dossier=dossier,
                baseline_run_id="baseline-run",
            )
            self.assertTrue(report.accepted)
            self.assertTrue(report.deltas)
            dimensions = {(item.item_type, item.dimension) for item in report.deltas}
            self.assertIn(("hypothesis", "support"), dimensions)
            self.assertIn(("hypothesis", "uncertainty"), dimensions)
            self.assertTrue(all(item.baseline_run_id == "baseline-run" for item in report.deltas))
            self.assertTrue(all(item.current_run_id == "current-run" for item in report.deltas))
            self.assertNotIn("overall_score", _keys(report.to_dict()))

    def test_failed_replay_withholds_reasoning_collections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier = self._runtime(directory)
            run = runtime.get_run(dossier.run_id)
            address = str(run["event_address"]).split(":", 1)[1]
            event_path = runtime.store.store.objects / f"{address}.json"
            event = json.loads(event_path.read_text(encoding="utf-8"))
            event["events"][1]["event_hash"] = "sha256:review-workspace-corruption"
            event_path.write_text(json.dumps(event), encoding="utf-8")
            report = build_persisted_review_workspace(runtime, dossier.run_id)
            self.assertFalse(report.accepted)
            self.assertEqual(report.state, ReviewWorkspaceState.ABSTAINED)
            self.assertEqual(report.edges, ())
            self.assertEqual(report.evidence, ())
            self.assertTrue(any("withheld" in warning for warning in report.warnings))

    def test_config_and_contract_surfaces_are_bounded(self) -> None:
        config = ReviewWorkspaceConfig.from_mapping(
            {"uncertainty_review_threshold": 0.4, "context_fit_review_threshold": 0.8}
        )
        self.assertEqual(config.uncertainty_review_threshold, 0.4)
        self.assertEqual(review_workspace_schema()["version"], "review-workspace-schema-v1")
        self.assertTrue(review_workspace_capabilities()["replay_gate"]["current_run_required"])
        self.assertTrue(review_workspace_capabilities()["exports"]["portable_release"])

    def test_exports_are_deterministic_and_release_is_exact_byte_verified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier = self._runtime(directory)
            report = build_persisted_review_workspace(runtime, dossier.run_id)
            first = review_workspace_export_payloads(report)
            second = review_workspace_export_payloads(report)
            self.assertEqual(first, second)
            self.assertEqual(first["review-workspace.md"], render_review_workspace_markdown(report).encode("utf-8"))
            rows = list(csv.DictReader(io.StringIO(first["hypotheses.csv"].decode("utf-8"))))
            self.assertEqual(len(rows), len(report.hypotheses))
            self.assertEqual(rows[0]["hypothesis_id"], report.hypotheses[0].hypothesis_id)

            bundle = build_review_workspace_release(report)
            self.assertEqual(len({item.artifact_id for item in bundle.artifacts}), len(bundle.artifacts))
            release = Path(directory) / "review-release"
            write_review_workspace_release(bundle, release)
            verified = verify_review_workspace_release(release)
            self.assertTrue(verified.accepted)
            self.assertEqual(verified.artifact_count, 9)
            (release / "edges.csv").write_bytes((release / "edges.csv").read_bytes() + b"tamper")
            tampered = verify_review_workspace_release(release)
            self.assertFalse(tampered.accepted)
            self.assertIn("edges.csv", tampered.tampered_files)

    def test_export_cli_and_raw_api_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier = self._runtime(directory)
            markdown = Path(directory) / "review.md"
            self.assertEqual(
                main([
                    "review-workspace-export", dossier.run_id, "--data-root", directory,
                    "--format", "markdown", "--output", str(markdown),
                ]),
                0,
            )
            self.assertIn("# Review workspace", markdown.read_text(encoding="utf-8"))
            release = Path(directory) / "portable"
            self.assertEqual(
                main([
                    "review-workspace-release", dossier.run_id, "--data-root", directory,
                    "--output", str(release),
                ]),
                0,
            )
            verification = Path(directory) / "verification.json"
            self.assertEqual(
                main(["review-workspace-release-verify", str(release), "--output", str(verification)]),
                0,
            )
            self.assertTrue(json.loads(verification.read_text(encoding="utf-8"))["accepted"])

            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                connection.request("GET", f"/v1/runs/{dossier.run_id}/review-workspace/export?format=markdown")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertIn("text/markdown", response.getheader("Content-Type", ""))
                self.assertIn("# Review workspace", response.read().decode("utf-8"))
                connection.request(
                    "GET",
                    f"/v1/runs/{dossier.run_id}/review-workspace/export?format=csv&collection=edges",
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertIn("text/csv", response.getheader("Content-Type", ""))
                self.assertIn("edge_id", response.read().decode("utf-8").splitlines()[0])
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_cli_and_api_surfaces_return_the_same_review_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, dossier = self._runtime(directory)
            output = Path(directory) / "review.json"
            self.assertEqual(
                main(
                    [
                        "review-workspace",
                        dossier.run_id,
                        "--data-root",
                        directory,
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            cli_payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(cli_payload["accepted"])
            self.assertEqual(cli_payload["state"], "review")

            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                connection.request("GET", "/v1/review-workspace/schema")
                schema_response = connection.getresponse()
                self.assertEqual(schema_response.status, 200)
                self.assertEqual(json.loads(schema_response.read())["version"], "review-workspace-schema-v1")
                connection.request("GET", f"/v1/runs/{dossier.run_id}/review-workspace")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                api_payload = json.loads(response.read())
                self.assertEqual(api_payload["content_address"], cli_payload["content_address"])
                self.assertEqual(len(api_payload["edges"]), len(cli_payload["edges"]))
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
