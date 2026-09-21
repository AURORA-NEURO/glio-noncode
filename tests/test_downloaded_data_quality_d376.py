"""Focused regression coverage for the D376 history diff runtime layer."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import downloaded_data_quality_d375_history_diff as diff_model
from glio_noncode import downloaded_data_quality_d376_history_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_d376_history_diff_runtime_audit as audit_model
from glio_noncode import downloaded_data_quality_d376_history_diff_runtime_query as query_model
from glio_noncode import downloaded_data_quality_d376_history_diff_runtime_query_audit as query_audit_model
from glio_noncode.errors import ValidationError
from glio_noncode.serialization import canonical_json


class D376DiffRuntimeTests(unittest.TestCase):
    def test_runtime_replays_strict_release_audit_and_query(self) -> None:
        history_model = diff_model.history_model
        source_runtime_model = history_model.registry_model.runtime_model
        source_history_model = source_runtime_model.diff_model.history_model
        source_registry_model = source_history_model.registry_model
        source_registry = source_registry_model.build_registry((), registry_id="d376-source-registry")
        source_left = source_history_model.build_history(source_registry, history_id="d376-source-history", snapshot_id="baseline")
        source_right = source_history_model.build_history(source_registry, history_id="d376-source-history", snapshot_id="candidate")
        source_diff = source_runtime_model.diff_model.build_diff(source_left, source_right, diff_id="d376-source-diff")
        ready_runtime = source_runtime_model.build_runtime(source_diff, runtime_id="d376-ready-source-runtime", policy=source_runtime_model.build_policy("d376-ready-source-policy", source_diff.diff_id, maximum_changed=1))
        blocked_runtime = source_runtime_model.build_runtime(source_diff, runtime_id="d376-blocked-source-runtime", policy=source_runtime_model.build_policy("d376-blocked-source-policy", source_diff.diff_id, maximum_changed=0))
        blocked_registry = history_model.registry_model.build_registry((blocked_runtime,), registry_id="d376-registry")
        ready_registry = history_model.registry_model.build_registry((ready_runtime,), registry_id="d376-registry")
        baseline = history_model.build_history(blocked_registry, history_id="d376-history", snapshot_id="blocked")
        candidate = history_model.append_history(baseline, ready_registry, snapshot_id="ready", expected_head=baseline.entries[-1].content_address)
        diff = diff_model.build_diff(baseline, candidate, diff_id="d376-diff")
        strict = runtime_model.run_runtime(diff, runtime_id="d376-strict-runtime", policy=runtime_model.build_policy("d376-strict-policy", diff.diff_id, maximum_added=0, maximum_removed=0, maximum_changed=0, allowed_directions=("improved", "changed", "unchanged"), require_accepted=True, require_state_change=False, allow_unchanged=True))
        release = runtime_model.run_runtime(diff, runtime_id="d376-release-runtime", policy=runtime_model.build_policy("d376-release-policy", diff.diff_id, maximum_added=1, maximum_removed=0, maximum_changed=0, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True))
        strict_audit = audit_model.audit_runtime(strict, diff)
        release_audit = audit_model.audit_runtime(release, diff)
        release_query = query_model.query_runtime(release, resources=query_model.RESOURCES, limit=query_model.MAX_LIMIT)
        release_query_audit = query_audit_model.audit_query(release_query, release)
        self.assertFalse(strict.release_ready)
        self.assertTrue(release.release_ready)
        self.assertEqual((strict.passed_count, strict.check_count, strict.release_ready), (14, 15, False))
        self.assertEqual((strict_audit.check_count, strict_audit.passed_count, strict_audit.accepted), (15, 15, True))
        self.assertEqual((release_audit.check_count, release_audit.passed_count, release_audit.accepted), (15, 15, True))
        self.assertFalse(release_query.truncated)
        self.assertEqual((release_query_audit.check_count, release_query_audit.passed_count, release_query_audit.accepted), (12, 12, True))

        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "release"
            runtime_model.persist_runtime(release, destination)
            reloaded = runtime_model.load_runtime(destination, diff)
            self.assertEqual(reloaded.content_address, release.content_address)
            self.assertEqual(runtime_model.summary_json(reloaded), runtime_model.summary_json(release))

            runtime_document = json.loads((destination / "runtime.json").read_text(encoding="utf-8"))
            runtime_document["release_ready"] = False
            (destination / "runtime.json").write_text(canonical_json(runtime_document), encoding="utf-8")
            with self.assertRaises(ValidationError):
                runtime_model.load_runtime(destination, diff)


if __name__ == "__main__":
    unittest.main()
