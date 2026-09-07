from __future__ import annotations

import json
import tempfile
import unittest
from unittest.mock import patch

from glio_noncode.errors import StoreError, ValidationError
from glio_noncode.run_catalog import inspect_run
from glio_noncode.run_comparison import build_run_history
from glio_noncode.run_workspace import build_persisted_run_workspace
from glio_noncode.runtime import CaseRuntime, VerifiedRunSnapshot
from glio_noncode.serialization import canonical_json, jsonable
from glio_noncode.storage import ObjectStore
from glio_noncode.workspace_history import build_persisted_workspace_history

from .helpers import fixture_manifest


class RuntimeBoundedReadTests(unittest.TestCase):
    def test_all_non_batch_reopen_paths_avoid_legacy_unbounded_get(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())

            with patch.object(
                ObjectStore,
                "get",
                side_effect=AssertionError("legacy unbounded read used"),
            ):
                snapshot = runtime.load_run_snapshot(dossier.run_id)
                inspection = inspect_run(runtime, dossier.run_id)
                history = build_run_history(runtime, dossier.run_id)
                workspace = build_persisted_run_workspace(runtime, dossier.run_id)
                workspace_history = build_persisted_workspace_history(runtime, dossier.run_id)

            self.assertEqual(snapshot.dossier, dossier)
            self.assertTrue(inspection.accepted)
            self.assertTrue(history.accepted)
            self.assertTrue(workspace.accepted)
            self.assertTrue(workspace_history.accepted)

    def test_verified_snapshot_is_closed_and_returns_detached_event_logs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            snapshot = runtime.load_run_snapshot(dossier.run_id)
            original_head = snapshot.event_log.head

            detached = snapshot.event_log
            detached.append("test_probe", {}, event_id="evt-detached-test-probe")

            self.assertEqual(snapshot.event_log.head, original_head)
            self.assertNotEqual(detached.head, original_head)
            forged_record = snapshot.run_record_dict()
            forged_record["event_history"] = ["sha256:not-an-address"]
            with self.assertRaises(ValidationError):
                VerifiedRunSnapshot(
                    run_record=forged_record,
                    manifest=snapshot.manifest,
                    event_record=jsonable(snapshot.event_record),
                    dossier=snapshot.dossier,
                    replay=snapshot.replay,
                )

    def test_bounded_diagnostic_reader_rejects_oversize_and_invalid_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ObjectStore(directory)
            address = store.put({"value": "bounded"})
            with self.assertRaisesRegex(StoreError, "exceeds 1 bytes"):
                store.get_bounded(address, max_bytes=1)
            for invalid in (True, 0, -1):
                with self.subTest(invalid=invalid):
                    with self.assertRaises(StoreError):
                        store.get_bounded(address, max_bytes=invalid)  # type: ignore[arg-type]

    def test_noncanonical_corrupt_event_is_visible_but_payload_is_withheld(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            run = runtime.get_run(dossier.run_id)
            event_address = str(run["event_address"])
            event_path = runtime.store.store.objects / f"{event_address.split(':', 1)[1]}.json"
            raw = json.loads(event_path.read_text(encoding="utf-8"))
            raw["events"][0]["event_hash"] = "sha256:" + "0" * 64
            event_path.write_text(json.dumps(raw), encoding="utf-8")

            inspection = inspect_run(runtime, dossier.run_id)

            self.assertFalse(inspection.accepted)
            self.assertEqual(inspection.event_record["events"], [])
            self.assertNotIn("0000000000000000", json.dumps(inspection.to_dict()))
            with self.assertRaises(ValidationError):
                runtime.load_run_snapshot(dossier.run_id)

    def test_dossier_loader_rejects_canonical_payload_at_wrong_address(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            run = runtime.get_run(dossier.run_id)
            dossier_address = str(run["dossier_address"])
            path = runtime.store.store.objects / f"{dossier_address.split(':', 1)[1]}.json"
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["warnings"] = ["tampered"]
            path.write_text(canonical_json(raw), encoding="utf-8")

            with self.assertRaises(ValidationError):
                runtime.load_dossier(dossier_address)


if __name__ == "__main__":
    unittest.main()
