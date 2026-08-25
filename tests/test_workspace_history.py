"""Deep tests for historical workspace reconstruction and transitions."""

from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.models import ReviewDecision, ReviewState
from glio_noncode.run_workspace import build_persisted_run_workspace
from glio_noncode.runtime import CaseRuntime
from glio_noncode.workspace_history import (
    WORKSPACE_HISTORY_MAX_CHANGES,
    WorkspaceHistorySnapshot,
    _transition,
    build_persisted_workspace_history,
    compare_persisted_workspace_snapshots,
)

from .helpers import fixture_manifest


def accepted_review(case_id: str, hypothesis_id: str, claim_ids: tuple[str, ...]) -> ReviewDecision:
    return ReviewDecision(
        review_id="workspace-history-review",
        case_id=case_id,
        reviewer="scientific-reviewer",
        state=ReviewState.ACCEPTED,
        reviewed_hypothesis_ids=(hypothesis_id,),
        rationale="The historical workspace transition retains the research boundary.",
        checked_claim_ids=claim_ids,
    )


class WorkspaceHistoryTests(unittest.TestCase):
    def _reviewed_runtime(self, directory: str) -> tuple[CaseRuntime, object, object]:
        runtime = CaseRuntime(directory)
        original = runtime.evaluate(fixture_manifest())
        reviewed = runtime.review_run(
            original.run_id,
            accepted_review(
                original.case_id,
                original.hypotheses[0].hypothesis_id,
                tuple(item.evidence_id for item in original.evidence),
            ),
        )
        return runtime, original, reviewed

    def test_history_rebuilds_all_snapshots_and_retains_review_metadata_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, original, reviewed = self._reviewed_runtime(directory)
            history = build_persisted_workspace_history(runtime, original.run_id)
            self.assertTrue(history.accepted)
            self.assertTrue(history.replay_accepted)
            self.assertEqual(history.snapshot_count, 2)
            self.assertEqual(history.transition_count, 1)
            self.assertEqual(history.current_snapshot_index, 1)
            self.assertEqual(
                [item.dossier_address for item in history.snapshots],
                [original.content_address, reviewed.content_address],
            )
            self.assertEqual(history.snapshots[0].record_count, 18)
            self.assertEqual(history.snapshots[1].record_count, 18)
            transition = history.transitions[0]
            self.assertTrue(transition.metadata_changed)
            self.assertTrue(transition.changed)
            self.assertEqual(transition.source_status, "review_required")
            self.assertEqual(transition.target_status, "released_research")
            self.assertEqual(transition.source_review_state, None)
            self.assertEqual(transition.target_review_state, "accepted")
            self.assertEqual(transition.change_count, 0)
            self.assertEqual(history.total_change_count, 1)
            self.assertTrue(history.content_address.startswith("workspace-history:"))

    def test_history_is_deterministic_and_public(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, original, _ = self._reviewed_runtime(directory)
            first = build_persisted_workspace_history(runtime, original.run_id)
            second = build_persisted_workspace_history(runtime, original.run_id)
            self.assertEqual(first.to_dict(), second.to_dict())
            serialized = json.dumps(first.to_dict(), sort_keys=True).lower()
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

    def test_direct_snapshot_compare_reuses_history_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, original, _ = self._reviewed_runtime(directory)
            transition = compare_persisted_workspace_snapshots(runtime, original.run_id, 0, 1)
            self.assertTrue(transition.accepted)
            self.assertTrue(transition.changed)
            self.assertEqual(transition.source_snapshot_index, 0)
            self.assertEqual(transition.target_snapshot_index, 1)
            self.assertTrue(transition.content_address.startswith("workspace-transition:"))

            with self.assertRaises(ValidationError):
                compare_persisted_workspace_snapshots(runtime, original.run_id, -1, 1)
            with self.assertRaises(ValidationError):
                compare_persisted_workspace_snapshots(runtime, original.run_id, 0, 4)
            with self.assertRaises(ValidationError):
                build_persisted_workspace_history(
                    runtime,
                    original.run_id,
                    change_limit=WORKSPACE_HISTORY_MAX_CHANGES + 1,
                )

    def test_record_diff_reports_added_removed_changed_and_truncation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            current = build_persisted_run_workspace(runtime, dossier.run_id)
            first_workspace = deepcopy(current.workspace)
            second_workspace = deepcopy(current.workspace)
            assert first_workspace is not None
            assert second_workspace is not None
            first_records = first_workspace["records"]
            second_records = second_workspace["records"]
            second_records = [row for row in second_records if row["record_id"] != "var-demo-001"]
            second_records[0] = dict(second_records[0])
            second_records[0]["label"] = "changed public label"
            second_records.append(
                {
                    "record_id": "added-record",
                    "record_type": "summary",
                    "label": "added summary",
                    "context_key": second_workspace["context_key"],
                    "state": "partial",
                    "source_ids": [],
                    "tags": [],
                    "fields": {},
                    "searchable_text": "added summary",
                }
            )
            first_snapshot = WorkspaceHistorySnapshot(
                index=0,
                dossier_address="sha256:first",
                is_current=False,
                status="review_required",
                review_state=None,
                workspace_id="case:demo",
                workspace_state="supported",
                record_count=len(first_records),
                record_type_counts={},
                state_counts={},
                workspace=first_workspace,
                warnings=(),
                accepted=True,
                content_address="sha256:first-snapshot",
            )
            second_snapshot = WorkspaceHistorySnapshot(
                index=1,
                dossier_address="sha256:second",
                is_current=True,
                status="released_research",
                review_state="accepted",
                workspace_id="case:demo",
                workspace_state="supported",
                record_count=len(second_records),
                record_type_counts={},
                state_counts={},
                workspace=second_workspace | {"records": second_records},
                warnings=(),
                accepted=True,
                content_address="sha256:second-snapshot",
            )
            transition = _transition(first_snapshot, second_snapshot, change_limit=1)
            self.assertTrue(transition.accepted)
            self.assertEqual(transition.added_count, 1)
            self.assertEqual(transition.removed_count, 1)
            self.assertEqual(transition.changed_count, 1)
            self.assertEqual(transition.unchanged_count, len(first_records) - 2)
            self.assertTrue(transition.truncated)
            self.assertEqual(len(transition.changes), 1)
            self.assertTrue(any("truncated" in warning for warning in transition.warnings))

    def test_corrupted_historical_snapshot_withholds_every_workspace_projection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, original, _ = self._reviewed_runtime(directory)
            history_path = Path(directory) / "runs" / f"{original.run_id}.json"
            run_record = json.loads(history_path.read_text(encoding="utf-8"))
            old_address = run_record["dossier_history"][0].split(":", 1)[1]
            old_path = runtime.store.store.objects / f"{old_address}.json"
            old_payload = json.loads(old_path.read_text(encoding="utf-8"))
            old_payload["status"] = "tampered"
            old_path.write_text(json.dumps(old_payload), encoding="utf-8")

            history = build_persisted_workspace_history(runtime, original.run_id)
            self.assertFalse(history.accepted)
            self.assertTrue(history.replay_accepted)
            self.assertFalse(history.snapshots[0].accepted)
            self.assertIsNone(history.snapshots[0].workspace)
            self.assertIsNone(history.snapshots[1].workspace)
            self.assertEqual(history.transitions[0].accepted, False)
            self.assertTrue(history.warnings)

    def test_cli_and_http_history_surfaces_return_addressed_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, original, _ = self._reviewed_runtime(directory)
            history_path = Path(directory) / "workspace-history.json"
            compare_path = Path(directory) / "workspace-compare.json"
            self.assertEqual(
                main(
                    [
                        "run-workspace-history",
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
                        "run-workspace-compare",
                        original.run_id,
                        "0",
                        "1",
                        "--data-root",
                        directory,
                        "--output",
                        str(compare_path),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(history_path.read_text(encoding="utf-8"))["accepted"])
            self.assertTrue(json.loads(compare_path.read_text(encoding="utf-8"))["changed"])

            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                connection.request("GET", f"/v1/runs/{original.run_id}/workspace/history")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                history = json.loads(response.read())
                self.assertTrue(history["accepted"])
                self.assertEqual(history["snapshot_count"], 2)

                connection.request(
                    "GET",
                    f"/v1/runs/{original.run_id}/workspace/compare?source_snapshot=0&target_snapshot=1",
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                transition = json.loads(response.read())
                self.assertTrue(transition["accepted"])
                self.assertTrue(transition["metadata_changed"])

                connection.request("GET", f"/v1/runs/{original.run_id}/workspace/compare")
                response = connection.getresponse()
                self.assertEqual(response.status, 400)
                self.assertEqual(json.loads(response.read())["error"], "invalid_query")
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
