"""Deep contract tests for persisted dossier history and semantic comparisons."""

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
from glio_noncode.models import ReviewDecision, ReviewState
from glio_noncode.run_comparison import (
    build_dossier_comparison,
    build_run_history,
    compare_persisted_runs,
    compare_run_snapshots,
)
from glio_noncode.runtime import CaseRuntime

from .helpers import fixture_manifest


def accepted_review(run_id: str, case_id: str, hypothesis_id: str, claim_ids: tuple[str, ...]) -> ReviewDecision:
    return ReviewDecision(
        review_id=f"review-comparison-{run_id}",
        case_id=case_id,
        reviewer="scientific-reviewer",
        state=ReviewState.ACCEPTED,
        reviewed_hypothesis_ids=(hypothesis_id,),
        rationale="The review transition is retained as a research-only snapshot for comparison.",
        checked_claim_ids=claim_ids,
    )


class RunComparisonTests(unittest.TestCase):
    def test_review_history_retains_ordered_snapshot_addresses(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            original = runtime.evaluate(fixture_manifest())
            initial_history = build_run_history(runtime, original.run_id)
            self.assertTrue(initial_history.accepted)
            self.assertEqual(initial_history.snapshot_count, 1)
            self.assertEqual(initial_history.current_snapshot_index, 0)
            self.assertEqual(initial_history.snapshots[0].dossier_address, original.content_address)

            reviewed = runtime.review_run(
                original.run_id,
                accepted_review(
                    original.run_id,
                    original.case_id,
                    original.hypotheses[0].hypothesis_id,
                    tuple(item.evidence_id for item in original.evidence),
                ),
            )
            history = build_run_history(runtime, original.run_id)
            self.assertTrue(history.accepted)
            self.assertEqual(history.snapshot_count, 2)
            self.assertEqual(history.current_snapshot_index, 1)
            self.assertEqual(
                [item.dossier_address for item in history.snapshots],
                [original.content_address, reviewed.content_address],
            )
            self.assertEqual(history.snapshots[0].status, "review_required")
            self.assertEqual(history.snapshots[1].status, "released_research")
            self.assertTrue(history.content_address.startswith("run-history:"))

    def test_duplicate_history_address_is_not_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            run_path = Path(directory) / "runs" / f"{dossier.run_id}.json"
            record = json.loads(run_path.read_text(encoding="utf-8"))
            record["dossier_history"] = [dossier.content_address, dossier.content_address]
            run_path.write_text(json.dumps(record), encoding="utf-8")

            history = build_run_history(runtime, dossier.run_id)
            self.assertFalse(history.accepted)
            self.assertTrue(any("duplicate" in warning for warning in history.warnings))

    def test_review_transition_comparison_is_semantic_and_replay_gated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            original = runtime.evaluate(fixture_manifest())
            runtime.review_run(
                original.run_id,
                accepted_review(
                    original.run_id,
                    original.case_id,
                    original.hypotheses[0].hypothesis_id,
                    tuple(item.evidence_id for item in original.evidence),
                ),
            )
            comparison = compare_run_snapshots(runtime, original.run_id, 0, 1)

            self.assertTrue(comparison.accepted)
            self.assertTrue(comparison.same_case)
            self.assertTrue(comparison.changed)
            self.assertEqual(comparison.source_status, "review_required")
            self.assertEqual(comparison.target_status, "released_research")
            self.assertEqual(comparison.summary["hypothesis_changed_count"], 0)
            self.assertEqual(comparison.summary["evidence_changed_count"], 0)
            self.assertEqual(comparison.summary["experiment_changed_count"], 0)
            self.assertGreaterEqual(comparison.summary["metadata_change_count"], 2)
            self.assertEqual(comparison.failed_check_ids, ())
            self.assertTrue(comparison.content_address.startswith("dossier-comparison:"))

    def test_same_case_runs_compare_without_identity_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            source = runtime.evaluate(fixture_manifest())
            target_manifest = fixture_manifest()
            target_manifest = type(target_manifest).from_dict(
                {**target_manifest.to_dict(), "requested_by": "researcher-2"}
            )
            target = runtime.evaluate(target_manifest)
            comparison = compare_persisted_runs(runtime, source.run_id, target.run_id)

            self.assertTrue(comparison.accepted)
            self.assertTrue(comparison.same_case)
            self.assertEqual(comparison.source_case_id, comparison.target_case_id)
            self.assertIn("same-case", [item.check_id for item in comparison.checks])

    def test_cross_case_comparison_preserves_a_failed_check_and_diff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            source = runtime.evaluate(fixture_manifest())
            target_manifest = type(fixture_manifest()).from_dict(
                {**fixture_manifest().to_dict(), "case_id": "case-different"}
            )
            target = runtime.evaluate(target_manifest)
            comparison = compare_persisted_runs(runtime, source.run_id, target.run_id)

            self.assertFalse(comparison.accepted)
            self.assertFalse(comparison.same_case)
            self.assertIn("same-case", comparison.failed_check_ids)
            self.assertTrue(any("different cases" in warning for warning in comparison.warnings))

    def test_corrupted_historical_snapshot_is_reported_and_not_selected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            original = runtime.evaluate(fixture_manifest())
            runtime.review_run(
                original.run_id,
                accepted_review(
                    original.run_id,
                    original.case_id,
                    original.hypotheses[0].hypothesis_id,
                    tuple(item.evidence_id for item in original.evidence),
                ),
            )
            history = build_run_history(runtime, original.run_id)
            first_path = runtime.store.store.objects / f"{original.content_address.split(':', 1)[1]}.json"
            first_payload = json.loads(first_path.read_text(encoding="utf-8"))
            first_payload["status"] = "tampered"
            first_path.write_text(json.dumps(first_payload), encoding="utf-8")

            corrupted = build_run_history(runtime, original.run_id)
            self.assertFalse(corrupted.accepted)
            self.assertFalse(corrupted.snapshots[0].address_valid)
            self.assertTrue(corrupted.warnings)
            with self.assertRaises(ValidationError):
                compare_run_snapshots(runtime, original.run_id, 0, history.current_snapshot_index)

    def test_change_limit_and_direct_comparison_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dossier = CaseRuntime(directory).evaluate(fixture_manifest())
            with self.assertRaises(ValueError):
                build_dossier_comparison(dossier, dossier, change_limit=0)
            comparison = build_dossier_comparison(dossier, dossier)
            self.assertTrue(comparison.accepted)
            self.assertFalse(comparison.changed)
            self.assertEqual(comparison.metadata.change_count, 0)
            self.assertEqual(comparison.summary["complete"], True)

    def test_cli_history_and_comparison_commands_write_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            original = runtime.evaluate(fixture_manifest())
            runtime.review_run(
                original.run_id,
                accepted_review(
                    original.run_id,
                    original.case_id,
                    original.hypotheses[0].hypothesis_id,
                    tuple(item.evidence_id for item in original.evidence),
                ),
            )
            history_path = Path(directory) / "history.json"
            comparison_path = Path(directory) / "comparison.json"
            self.assertEqual(
                main(
                    [
                        "run-history",
                        original.run_id,
                        "--data-root",
                        directory,
                        "--output",
                        str(history_path),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "run-compare",
                        original.run_id,
                        original.run_id,
                        "--source-snapshot",
                        "0",
                        "--target-snapshot",
                        "1",
                        "--data-root",
                        directory,
                        "--output",
                        str(comparison_path),
                    ]
                ),
                0,
            )
            self.assertEqual(json.loads(history_path.read_text(encoding="utf-8"))["snapshot_count"], 2)
            self.assertTrue(json.loads(comparison_path.read_text(encoding="utf-8"))["accepted"])

    def test_http_history_and_comparison_routes_support_snapshot_queries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                connection.request(
                    "POST",
                    "/v1/evaluate",
                    body=json.dumps(fixture_manifest().to_dict()).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                evaluated = connection.getresponse()
                self.assertEqual(evaluated.status, 200)
                dossier = json.loads(evaluated.read())
                run_id = dossier["run_id"]
                review = accepted_review(
                    run_id,
                    dossier["case_id"],
                    dossier["hypotheses"][0]["hypothesis_id"],
                    tuple(item["evidence_id"] for item in dossier["evidence"]),
                )
                connection.request(
                    "POST",
                    f"/v1/runs/{run_id}/review",
                    body=json.dumps(review.to_dict()).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                reviewed = connection.getresponse()
                self.assertEqual(reviewed.status, 200)
                reviewed.read()

                connection.request("GET", f"/v1/runs/{run_id}/history")
                history_response = connection.getresponse()
                self.assertEqual(history_response.status, 200)
                self.assertEqual(json.loads(history_response.read())["snapshot_count"], 2)

                connection.request(
                    "GET",
                    f"/v1/runs/{run_id}/compare/{run_id}?source_snapshot=0&target_snapshot=1",
                )
                comparison_response = connection.getresponse()
                self.assertEqual(comparison_response.status, 200)
                comparison = json.loads(comparison_response.read())
                self.assertTrue(comparison["accepted"])
                self.assertEqual(comparison["source_snapshot_index"], 0)
                self.assertEqual(comparison["target_snapshot_index"], 1)
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
