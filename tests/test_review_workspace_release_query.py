from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.cli import main
from glio_noncode.review_workspace import build_persisted_review_workspace, build_review_workspace
from glio_noncode.review_workspace_exports import build_review_workspace_release, write_review_workspace_release
from glio_noncode.review_workspace_query import ReviewWorkspaceQuery, query_review_workspace
from glio_noncode.review_workspace_release_query import (
    diff_review_workspace_releases,
    index_review_workspace_release,
    load_review_workspace_release,
    query_review_workspace_release,
)
from glio_noncode.runtime import CaseRuntime

from .helpers import fixture_manifest


def _keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return {str(key) for key in value} | {
            nested
            for item in value.values()
            for nested in _keys(item)
        }
    if isinstance(value, list):
        return {nested for item in value for nested in _keys(item)}
    return set()


class ReviewWorkspaceReleaseQueryTests(unittest.TestCase):
    def _release(self, directory: str, name: str, report) -> Path:
        destination = Path(directory) / name
        write_review_workspace_release(build_review_workspace_release(report), destination)
        return destination

    def test_verified_release_loads_and_matches_live_query(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            report = build_persisted_review_workspace(runtime, dossier.run_id)
            release = self._release(directory, "release", report)
            loaded = load_review_workspace_release(release)
            self.assertTrue(loaded.accepted)
            self.assertEqual(loaded.workspace_address, report.content_address)
            self.assertEqual(index_review_workspace_release(release).record_count, 34)
            query = ReviewWorkspaceQuery(collection="evidence", limit=3)
            live = query_review_workspace(report, query)
            offline = query_review_workspace_release(release, query)
            self.assertEqual(offline.to_dict(), live.to_dict())
            self.assertNotIn("payload", _keys(loaded.to_dict(include_report=True)))
            self.assertNotIn("produced_by", _keys(loaded.to_dict(include_report=True)))

    def test_tampering_and_unexpected_files_block_offline_loading(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            report = build_persisted_review_workspace(runtime, dossier.run_id)
            release = self._release(directory, "release", report)
            report_path = release / "review-workspace.json"
            report_path.write_bytes(report_path.read_bytes() + b"x")
            with self.assertRaises(ValidationError):
                load_review_workspace_release(release)

            clean_release = self._release(directory, "clean-release", report)
            (clean_release / "unexpected.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                load_review_workspace_release(clean_release)

    def test_diff_reports_artifact_and_collection_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            left_report = build_persisted_review_workspace(runtime, dossier.run_id)
            changed_hypothesis = replace(
                dossier.hypotheses[0],
                support=round(dossier.hypotheses[0].support + 0.1, 6),
            )
            right_dossier = replace(dossier, hypotheses=(changed_hypothesis,))
            right_report = build_review_workspace(right_dossier, run_id="changed-run")
            left = self._release(directory, "left", left_report)
            right = self._release(directory, "right", right_report)
            diff = diff_review_workspace_releases(left, right)
            self.assertTrue(diff.accepted)
            self.assertTrue(diff.changed_artifact_ids)
            hypothesis_diff = next(item for item in diff.collections if item.collection == "hypotheses")
            self.assertEqual(hypothesis_diff.added_ids, ())
            self.assertEqual(hypothesis_diff.removed_ids, ())
            self.assertEqual(len(hypothesis_diff.changed_ids), 1)
            self.assertEqual(diff.to_dict(), diff_review_workspace_releases(left, right).to_dict())

            identity = diff_review_workspace_releases(left, left)
            self.assertTrue(identity.accepted)
            self.assertEqual(identity.changed_artifact_ids, ())
            self.assertTrue(all(not item.changed_ids for item in identity.collections))

    def test_release_report_address_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            report = build_persisted_review_workspace(runtime, dossier.run_id)
            release = self._release(directory, "release", report)
            manifest_path = release / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["workspace_address"] = "review-workspace:wrong"
            # The exact bytes are intentionally invalid; independent verification
            # must fail before the loader exposes the altered projection.
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(ValidationError):
                load_review_workspace_release(release)

    def test_offline_cli_surfaces_reopen_query_index_and_diff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            report = build_persisted_review_workspace(runtime, dossier.run_id)
            release = self._release(directory, "release", report)
            loaded_output = Path(directory) / "loaded.json"
            index_output = Path(directory) / "index.json"
            query_output = Path(directory) / "query.json"
            diff_output = Path(directory) / "diff.json"
            self.assertEqual(
                main(["review-workspace-release-load", str(release), "--output", str(loaded_output)]),
                0,
            )
            self.assertTrue(json.loads(loaded_output.read_text(encoding="utf-8"))["accepted"])
            self.assertEqual(
                main(["review-workspace-release-index", str(release), "--output", str(index_output)]),
                0,
            )
            self.assertEqual(json.loads(index_output.read_text(encoding="utf-8"))["record_count"], 34)
            self.assertEqual(
                main([
                    "review-workspace-release-query", str(release),
                    "--collection", "edges", "--limit", "2", "--output", str(query_output),
                ]),
                0,
            )
            self.assertEqual(len(json.loads(query_output.read_text(encoding="utf-8"))["rows"]), 2)
            self.assertEqual(
                main([
                    "review-workspace-release-diff", str(release), str(release),
                    "--output", str(diff_output),
                ]),
                0,
            )
            self.assertEqual(json.loads(diff_output.read_text(encoding="utf-8"))["changed_artifact_ids"], [])


if __name__ == "__main__":
    unittest.main()
